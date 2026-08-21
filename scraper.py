import os
import re
import json
import time
import hashlib
import http.cookiejar
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

class UFCScraper:
    def __init__(self, cache_dir="cache_25yr", base_url="http://ufcstats.com"):
        self.base_url = base_url
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }

    def _get_opener(self):
        cj = http.cookiejar.CookieJar()
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    def fetch_page(self, url, max_retries=3):
        opener = self._get_opener()
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url, headers=self.headers)
                resp = opener.open(req, timeout=20)
                html = resp.read().decode('utf-8', errors='ignore')
                
                # Check for PoW challenge
                if "Checking your browser" in html or "nonce=" in html:
                    nonce_match = re.search(r'var nonce="([^"]+)"', html)
                    if nonce_match:
                        nonce = nonce_match.group(1)
                        target_match = re.search(r'target=new Array\((\d+)\+1\)\.join\(\'0\'\)', html)
                        zeros = int(target_match.group(1)) if target_match else 2
                        target = '0' * zeros
                        n = 0
                        while True:
                            candidate = f"{nonce}:{n}"
                            h = hashlib.sha256(candidate.encode('utf-8')).hexdigest()
                            if h.startswith(target):
                                break
                            n += 1
                        
                        post_data = urllib.parse.urlencode({'nonce': nonce, 'n': str(n)}).encode('utf-8')
                        post_req = urllib.request.Request(
                            f"{self.base_url}/__c",
                            data=post_data,
                            headers={
                                'Content-Type': 'application/x-www-form-urlencoded',
                                'User-Agent': self.headers['User-Agent']
                            }
                        )
                        opener.open(post_req, timeout=20)
                        resp = opener.open(urllib.request.Request(url, headers=self.headers), timeout=20)
                        html = resp.read().decode('utf-8', errors='ignore')
                return html
            except Exception:
                time.sleep(0.5 + attempt * 0.5)
        return ""

    def get_completed_events(self, years=25):
        """Fetches list of completed events from the last N years."""
        cutoff_date = datetime.now() - timedelta(days=years * 365.25)
        print(f"[INFO] Fetching completed events since {cutoff_date.strftime('%Y-%m-%d')}...", flush=True)
        
        events_url = f"{self.base_url}/statistics/events/completed?page=all"
        html = self.fetch_page(events_url)
        if not html:
            print("[ERROR] Failed to fetch events page.", flush=True)
            return []

        soup = BeautifulSoup(html, 'html.parser')
        rows = soup.select('tr.b-statistics__table-row')
        
        events = []
        for r in rows:
            link_tag = r.select_one('a.b-link')
            date_tag = r.select_one('span.b-statistics__date')
            location_tag = r.select('td.b-statistics__table-col')
            
            if not link_tag or not date_tag:
                continue
            
            event_name = link_tag.text.strip()
            event_url = link_tag.get('href', '').strip()
            date_str = date_tag.text.strip()
            location = location_tag[1].text.strip() if len(location_tag) > 1 else ""
            
            try:
                event_date = datetime.strptime(date_str, "%B %d, %Y")
            except ValueError:
                try:
                    event_date = datetime.strptime(date_str, "%b %d, %Y")
                except ValueError:
                    continue
            
            if event_date < cutoff_date:
                continue
            
            events.append({
                'name': event_name,
                'url': event_url,
                'date': event_date.strftime('%Y-%m-%d'),
                'date_raw': date_str,
                'location': location
            })
        
        print(f"[INFO] Found {len(events)} events within the last {years} years.", flush=True)
        return events

    def parse_int_stat(self, text, default=0):
        try:
            cleaned = re.sub(r'[^\d]', '', text)
            return int(cleaned) if cleaned else default
        except Exception:
            return default

    def scrape_event_fights(self, event):
        """Scrapes all fights for a specific event with strike, KD, TD, Sub stats."""
        event_cache_id = re.sub(r'[^a-zA-Z0-9]', '_', event['url'].split('/')[-1])
        event_cache_file = os.path.join(self.cache_dir, f"event_{event_cache_id}.json")
        
        if os.path.exists(event_cache_file):
            try:
                with open(event_cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass

        html = self.fetch_page(event['url'])
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        fight_rows = soup.select('tr.b-fight-details__table-row')
        
        fights = []
        for row in fight_rows:
            cols = row.select('td.b-fight-details__table-col')
            if len(cols) < 8:
                continue
            
            # Fighter names and status
            fighter_links = cols[1].select('a.b-link')
            if len(fighter_links) < 2:
                continue
            
            fighter1_name = fighter_links[0].text.strip()
            fighter2_name = fighter_links[1].text.strip()
            
            flag_text = cols[0].text.strip().lower()
            is_draw = "draw" in flag_text or "nc" in flag_text
            
            winner = fighter1_name
            loser = fighter2_name
            result_type = "win"
            
            if is_draw:
                result_type = "draw" if "draw" in flag_text else "nc"
                winner = None
                loser = None

            # Column 2: Knockdowns (KD)
            kd_ps = cols[2].select('p') if len(cols) > 2 else []
            kd1 = self.parse_int_stat(kd_ps[0].text if len(kd_ps) > 0 else "")
            kd2 = self.parse_int_stat(kd_ps[1].text if len(kd_ps) > 1 else "")

            # Column 3: Significant Strikes (Str)
            str_ps = cols[3].select('p') if len(cols) > 3 else []
            str1 = self.parse_int_stat(str_ps[0].text if len(str_ps) > 0 else "")
            str2 = self.parse_int_stat(str_ps[1].text if len(str_ps) > 1 else "")

            # Column 4: Takedowns (TD)
            td_ps = cols[4].select('p') if len(cols) > 4 else []
            td1 = self.parse_int_stat(td_ps[0].text if len(td_ps) > 0 else "")
            td2 = self.parse_int_stat(td_ps[1].text if len(td_ps) > 1 else "")

            # Column 5: Submissions (Sub)
            sub_ps = cols[5].select('p') if len(cols) > 5 else []
            sub1 = self.parse_int_stat(sub_ps[0].text if len(sub_ps) > 0 else "")
            sub2 = self.parse_int_stat(sub_ps[1].text if len(sub_ps) > 1 else "")
            
            # Weight Class and Title Bout
            weight_text = cols[6].text.strip()
            row_imgs = [img.get('src', '').lower() for img in row.select('img')]
            has_belt_img = any('belt' in src for src in row_imgs)
            is_title = has_belt_img or "title" in weight_text.lower() or "championship" in weight_text.lower() or "belt" in weight_text.lower()
            
            clean_weight = self.normalize_weight_class(weight_text)
            
            # Method
            method_ps = cols[7].select('p')
            method_type = method_ps[0].text.strip() if len(method_ps) > 0 else cols[7].text.strip()
            method_detail = method_ps[1].text.strip() if len(method_ps) > 1 else ""
            
            # Round & Time
            round_num = cols[8].text.strip() if len(cols) > 8 else "1"
            time_str = cols[9].text.strip() if len(cols) > 9 else "5:00"
            
            norm_method = self.normalize_method(method_type)

            fights.append({
                'event_name': event['name'],
                'event_url': event['url'],
                'date': event['date'],
                'fighter1': fighter1_name,
                'fighter2': fighter2_name,
                'winner': winner,
                'loser': loser,
                'result_type': result_type,
                'winner_kd': kd1 if winner == fighter1_name else kd2,
                'loser_kd': kd2 if winner == fighter1_name else kd1,
                'winner_str': str1 if winner == fighter1_name else str2,
                'loser_str': str2 if winner == fighter1_name else str1,
                'winner_td': td1 if winner == fighter1_name else td2,
                'loser_td': td2 if winner == fighter1_name else td1,
                'winner_sub': sub1 if winner == fighter1_name else sub2,
                'loser_sub': sub2 if winner == fighter1_name else sub1,
                'weight_class': clean_weight,
                'raw_weight_class': weight_text,
                'is_title_bout': is_title,
                'method': norm_method,
                'raw_method': method_type,
                'method_detail': method_detail,
                'round': round_num,
                'time': time_str
            })

        with open(event_cache_file, 'w', encoding='utf-8') as f:
            json.dump(fights, f, indent=2, ensure_ascii=False)
            
        return fights

    def normalize_weight_class(self, raw_str):
        raw = raw_str.lower()
        if "women's strawweight" in raw or "strawweight" in raw:
            return "Women's Strawweight"
        if "women's flyweight" in raw:
            return "Women's Flyweight"
        if "women's bantamweight" in raw:
            return "Women's Bantamweight"
        if "women's featherweight" in raw:
            return "Women's Featherweight"
        if "flyweight" in raw:
            return "Flyweight"
        if "bantamweight" in raw:
            return "Bantamweight"
        if "featherweight" in raw:
            return "Featherweight"
        if "lightweight" in raw:
            return "Lightweight"
        if "welterweight" in raw:
            return "Welterweight"
        if "middleweight" in raw:
            return "Middleweight"
        if "light heavyweight" in raw:
            return "Light Heavyweight"
        if "heavyweight" in raw:
            return "Heavyweight"
        if "catch weight" in raw or "catchweight" in raw:
            return "Catchweight"
        if "super heavyweight" in raw or "open weight" in raw:
            return "Heavyweight"
        return "Catchweight"

    def normalize_method(self, raw_method):
        m = raw_method.upper()
        if "KO" in m or "TKO" in m:
            return "KO/TKO"
        if "SUB" in m:
            return "SUB"
        if "U-DEC" in m or "UNANIMOUS" in m:
            return "U-DEC"
        if "S-DEC" in m or "SPLIT" in m:
            return "S-DEC"
        if "M-DEC" in m or "MAJORITY" in m:
            return "M-DEC"
        if "DEC" in m:
            return "DEC"
        if "DQ" in m:
            return "DQ"
        if "CNC" in m or "NO CONTEST" in m or "OVERTURNED" in m:
            return "NC"
        return "OTHER"

    def scrape_all(self, years=25, output_file="matches.json", max_workers=16):
        events = self.get_completed_events(years=years)
        all_matches = []
        
        print(f"[INFO] Scraping {len(events)} events over {years} years with {max_workers} concurrent workers...", flush=True)
        completed_count = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_event = {executor.submit(self.scrape_event_fights, ev): ev for ev in events}
            for future in as_completed(future_to_event):
                ev = future_to_event[future]
                completed_count += 1
                try:
                    fights = future.result()
                    all_matches.extend(fights)
                    if completed_count % 50 == 0 or completed_count == len(events):
                        print(f"[{completed_count}/{len(events)}] Processed: {ev['name']} -> Total Matches so far: {len(all_matches)}", flush=True)
                except Exception as e:
                    print(f"[ERROR] Failed {ev['name']}: {e}", flush=True)

        all_matches.sort(key=lambda x: x['date'])
        
        print(f"[SUCCESS] Scraped a total of {len(all_matches)} matches across {len(events)} events (25-year span).", flush=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_matches, f, indent=2, ensure_ascii=False)
            
        print(f"[INFO] Saved clean match records to {output_file}", flush=True)
        return all_matches

if __name__ == '__main__':
    scraper = UFCScraper(cache_dir="cache_25yr")
    scraper.scrape_all(years=25, output_file="matches.json", max_workers=16)
