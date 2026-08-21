import os
import re
import json
import time
import hashlib
import http.cookiejar
import urllib.request
import urllib.parse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

# Roster of Top Fighters across all 8 Men's Divisions
MENS_DIVISIONS_ROSTER = {
    "Flyweight": [
        "Alexandre Pantoja", "Brandon Royval", "Brandon Moreno", "Kai Kara-France", 
        "Amir Albazi", "Tatsuro Taira", "Manel Kape", "Joshua Van", "Muhammad Mokaev", 
        "Steve Erceg", "Asu Almabayev", "Alex Perez", "Tagir Ulanbekov", "Tim Elliott", 
        "Matheus Nicolau", "Cody Durden"
    ],
    "Bantamweight": [
        "Merab Dvalishvili", "Sean O'Malley", "Umar Nurmagomedov", "Petr Yan", 
        "Cory Sandhagen", "Deiveson Figueiredo", "Marlon Vera", "Henry Cejudo", 
        "Song Yadong", "Mario Bautista", "Rob Font", "Kyler Phillips", "Marcus McGhee", 
        "Payton Talbott", "Aiemann Zahabi", "Jonathan Martinez", "Farid Basharat"
    ],
    "Featherweight": [
        "Ilia Topuria", "Alexander Volkanovski", "Max Holloway", "Diego Lopes", 
        "Yair Rodriguez", "Brian Ortega", "Movsar Evloev", "Arnold Allen", 
        "Josh Emmett", "Aljamain Sterling", "Lerone Murphy", "Dan Ige", 
        "Edson Barboza", "Bryce Mitchell", "Jean Silva", "Joanderson Brito", "Steve Garcia"
    ],
    "Lightweight": [
        "Islam Makhachev", "Arman Tsarukyan", "Charles Oliveira", "Justin Gaethje", 
        "Dustin Poirier", "Dan Hooker", "Michael Chandler", "Mateusz Gamrot", 
        "Beneil Dariush", "Rafael Fiziev", "Paddy Pimblett", "Renato Moicano", 
        "Benoit Saint Denis", "Grant Dawson", "Joel Alvarez", "Jalin Turner", "King Green", "Jim Miller"
    ],
    "Welterweight": [
        "Belal Muhammad", "Shavkat Rakhmonov", "Leon Edwards", "Kamaru Usman", 
        "Jack Della Maddalena", "Ian Machado Garry", "Colby Covington", "Sean Brady", 
        "Gilbert Burns", "Joaquin Buckley", "Geoff Neal", "Carlos Prates", 
        "Michael Morales", "Vicente Luque", "Kevin Holland", "Neil Magny", "Bryan Battle"
    ],
    "Middleweight": [
        "Dricus Du Plessis", "Sean Strickland", "Israel Adesanya", "Robert Whittaker", 
        "Khamzat Chimaev", "Nassourdine Imavov", "Caio Borralho", "Marvin Vettori", 
        "Jared Cannonier", "Brendan Allen", "Roman Dolidze", "Paulo Costa", 
        "Michel Pereira", "Anthony Hernandez", "Paul Craig", "Gregory Rodrigues", "Joe Pyfer"
    ],
    "Light Heavyweight": [
        "Alex Pereira", "Magomed Ankalaev", "Jiri Prochazka", "Jamahal Hill", 
        "Jan Blachowicz", "Aleksandar Rakic", "Khalil Rountree Jr.", "Carlos Ulberg", 
        "Volkan Oezdemir", "Nikita Krylov", "Azamat Murzakanov", "Bogdan Guskov", 
        "Dominick Reyes", "Anthony Smith", "Alonzo Menifield", "Vitor Petrino", "Johnny Walker"
    ],
    "Heavyweight": [
        "Jon Jones", "Tom Aspinall", "Ciryl Gane", "Alexander Volkov", 
        "Sergei Pavlovich", "Curtis Blaydes", "Jailton Almeida", "Derrick Lewis", 
        "Marcin Tybura", "Serghei Spivac", "Tai Tuivasa", "Marcos Rogerio de Lima", 
        "Waldo Cortes-Acosta", "Mick Parkin", "Shamil Gaziev", "Martin Buday", "Jairzinho Rozenstruik"
    ]
}

class CareerScraper:
    def __init__(self, cache_dir="cache_career", base_url="http://ufcstats.com"):
        self.base_url = base_url
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        self.fighter_index_file = os.path.join(cache_dir, "fighter_index.json")

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

    def build_fighter_index(self):
        """Builds or loads a mapping of fighter name -> profile URL from ufcstats.com."""
        if os.path.exists(self.fighter_index_file):
            try:
                with open(self.fighter_index_file, 'r', encoding='utf-8') as f:
                    index = json.load(f)
                    if len(index) > 500:
                        print(f"[INFO] Loaded {len(index)} fighters from cache.", flush=True)
                        return index
            except Exception:
                pass

        print("[INFO] Indexing all UFC fighters from ufcstats.com...", flush=True)
        import string
        index = {}

        def scrape_char(char):
            url = f"{self.base_url}/statistics/fighters?char={char}&page=all"
            html = self.fetch_page(url)
            if not html:
                return {}
            soup = BeautifulSoup(html, 'html.parser')
            rows = soup.select('tr.b-statistics__table-row')
            char_map = {}
            for r in rows:
                links = r.select('a.b-link')
                if len(links) >= 2:
                    first = links[0].text.strip()
                    last = links[1].text.strip()
                    full_name = f"{first} {last}".strip()
                    profile_url = links[0].get('href', '').strip()
                    if full_name and profile_url:
                        char_map[full_name.lower()] = {
                            'name': full_name,
                            'url': profile_url
                        }
            return char_map

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(scrape_char, c) for c in string.ascii_lowercase]
            for f in as_completed(futures):
                index.update(f.result())

        print(f"[INFO] Indexed a total of {len(index)} fighters.", flush=True)
        with open(self.fighter_index_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
        return index

    def parse_int_stat(self, text, default=0):
        try:
            cleaned = re.sub(r'[^\d]', '', text)
            return int(cleaned) if cleaned else default
        except Exception:
            return default

    def scrape_fighter_career(self, fighter_name, profile_url, primary_wc=""):
        """Scrapes the complete career fight log for a fighter."""
        cache_id = profile_url.split('/')[-1]
        fighter_cache_file = os.path.join(self.cache_dir, f"fighter_{cache_id}.json")
        
        if os.path.exists(fighter_cache_file):
            try:
                with open(fighter_cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass

        html = self.fetch_page(profile_url)
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        fight_rows = soup.select('tr.b-fight-details__table-row')
        
        fights = []
        for row in fight_rows:
            cols = row.select('td.b-fight-details__table-col')
            if len(cols) < 10:
                continue

            # Outcome: win / loss / draw / nc
            outcome_tag = cols[0].select_one('i.b-flag__text') or cols[0].select_one('p') or cols[0]
            outcome_text = outcome_tag.text.strip().lower() if outcome_tag else ""
            
            # Fighter names
            fighter_links = cols[1].select('a.b-link')
            if len(fighter_links) < 2:
                continue
            
            f1_name = fighter_links[0].text.strip()
            f2_name = fighter_links[1].text.strip()
            
            # Column 2: Knockdowns (KD)
            kd_ps = cols[2].select('p')
            kd1 = self.parse_int_stat(kd_ps[0].text if len(kd_ps) > 0 else "")
            kd2 = self.parse_int_stat(kd_ps[1].text if len(kd_ps) > 1 else "")

            # Column 3: Significant Strikes (Str)
            str_ps = cols[3].select('p')
            str1 = self.parse_int_stat(str_ps[0].text if len(str_ps) > 0 else "")
            str2 = self.parse_int_stat(str_ps[1].text if len(str_ps) > 1 else "")

            # Column 4: Takedowns (TD)
            td_ps = cols[4].select('p')
            td1 = self.parse_int_stat(td_ps[0].text if len(td_ps) > 0 else "")
            td2 = self.parse_int_stat(td_ps[1].text if len(td_ps) > 1 else "")

            # Column 5: Submissions (Sub)
            sub_ps = cols[5].select('p')
            sub1 = self.parse_int_stat(sub_ps[0].text if len(sub_ps) > 0 else "")
            sub2 = self.parse_int_stat(sub_ps[1].text if len(sub_ps) > 1 else "")

            # Column 6: Event & Date
            event_link = cols[6].select_one('a.b-link')
            event_name = event_link.text.strip() if event_link else cols[6].text.strip()
            event_url = event_link.get('href', '').strip() if event_link else ""
            
            date_ps = cols[6].select('p')
            date_str = date_ps[1].text.strip() if len(date_ps) > 1 else ""
            
            # Parse date e.g. "Aug. 15, 2026", "Jun. 01, 2024", "Oct. 22, 2022"
            formatted_date = ""
            for fmt in ["%b. %d, %Y", "%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"]:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    formatted_date = dt.strftime("%Y-%m-%d")
                    break
                except ValueError:
                    pass
            
            if not formatted_date:
                formatted_date = date_str

            # Column 7: Method & Detail
            method_ps = cols[7].select('p')
            method_type = method_ps[0].text.strip() if len(method_ps) > 0 else ""
            method_detail = method_ps[1].text.strip() if len(method_ps) > 1 else ""

            # Column 8: Round
            round_num = cols[8].text.strip()

            # Column 9: Time
            time_str = cols[9].text.strip()

            # Classify Winner/Loser
            if "win" in outcome_text:
                result_type = "win"
                winner = f1_name
                loser = f2_name
                w_kd, l_kd = kd1, kd2
                w_str, l_str = str1, str2
                w_td, l_td = td1, td2
                w_sub, l_sub = sub1, sub2
            elif "loss" in outcome_text or "loss" in cols[0].text.lower():
                result_type = "loss"
                winner = f2_name
                loser = f1_name
                w_kd, l_kd = kd2, kd1
                w_str, l_str = str2, str1
                w_td, l_td = td2, td1
                w_sub, l_sub = sub2, sub1
            elif "draw" in outcome_text:
                result_type = "draw"
                winner = None
                loser = None
                w_kd, l_kd = kd1, kd2
                w_str, l_str = str1, str2
                w_td, l_td = td1, td2
                w_sub, l_sub = sub1, sub2
            else:
                result_type = "nc"
                winner = None
                loser = None
                w_kd, l_kd = kd1, kd2
                w_str, l_str = str1, str2
                w_td, l_td = td1, td2
                w_sub, l_sub = sub1, sub2

            # Normalize method
            norm_method = self.normalize_method(method_type)

            # Check title bout
            row_imgs = [img.get('src', '').lower() for img in row.select('img')]
            is_title = any('belt' in src for src in row_imgs) or "championship" in event_name.lower() or "title" in method_detail.lower()

            fights.append({
                'event_name': event_name,
                'event_url': event_url,
                'date': formatted_date,
                'fighter1': f1_name,
                'fighter2': f2_name,
                'winner': winner,
                'loser': loser,
                'result_type': 'win' if result_type == 'loss' else result_type, # in global matches, store as win
                'winner_kd': w_kd,
                'loser_kd': l_kd,
                'winner_str': w_str,
                'loser_str': l_str,
                'winner_td': w_td,
                'loser_td': l_td,
                'winner_sub': w_sub,
                'loser_sub': l_sub,
                'method': norm_method,
                'raw_method': method_type,
                'method_detail': method_detail,
                'round': round_num,
                'time': time_str,
                'weight_class': primary_wc or "UFC Bout",
                'is_title_bout': is_title
            })

        with open(fighter_cache_file, 'w', encoding='utf-8') as f:
            json.dump(fights, f, indent=2, ensure_ascii=False)

        return fights

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

    def scrape_all_men_divisions_career(self, output_file="career_matches.json"):
        index = self.build_fighter_index()
        all_unique_fights = {}
        
        target_roster = []
        for division, fighters in MENS_DIVISIONS_ROSTER.items():
            for name in fighters:
                target_roster.append((name, division))

        print(f"[INFO] Fetching full career fight logs for {len(target_roster)} elite fighters across 8 men's divisions...", flush=True)

        def fetch_fighter_career(item):
            name, division = item
            name_lower = name.lower()
            fighter_info = index.get(name_lower)
            if not fighter_info:
                # Fuzzy search
                for k, v in index.items():
                    if name_lower in k or all(part in k for part in name_lower.split()):
                        fighter_info = v
                        break
            
            if not fighter_info:
                print(f"[WARN] Fighter not found in index: {name}", flush=True)
                return []
            
            return self.scrape_fighter_career(fighter_info['name'], fighter_info['url'], division)

        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_fighter = {executor.submit(fetch_fighter_career, item): item for item in target_roster}
            for future in as_completed(future_to_fighter):
                item = future_to_fighter[future]
                try:
                    fights = future.result()
                    for fight in fights:
                        # Deduplicate by key (date + sorted fighter names)
                        fighters_key = tuple(sorted([fight['fighter1'].lower(), fight['fighter2'].lower()]))
                        match_key = f"{fight['date']}_{fighters_key}"
                        if match_key not in all_unique_fights:
                            all_unique_fights[match_key] = fight
                except Exception as e:
                    print(f"[ERROR] Failed {item[0]}: {e}", flush=True)

        matches_list = list(all_unique_fights.values())
        matches_list.sort(key=lambda x: x['date'])

        print(f"[SUCCESS] Scraped {len(matches_list)} total unique career matches with strike, KD, and TD stats.", flush=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(matches_list, f, indent=2, ensure_ascii=False)
            
        print(f"[INFO] Saved career dataset to {output_file}", flush=True)
        return matches_list

if __name__ == '__main__':
    scraper = CareerScraper()
    scraper.scrape_all_men_divisions_career(output_file="career_matches.json")
