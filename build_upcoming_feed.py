import json
import re
import sys
from bs4 import BeautifulSoup
from elo_engine import UFCEloEngine, DIVISION_HIERARCHY

sys.stdout.reconfigure(encoding='utf-8')

with open(r'C:\Users\sinan\.gemini\antigravity-ide\brain\7afe4106-5779-401d-aa0b-f51da46f128f\.system_generated\steps\1355\content.md', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

with open('fighter_rankings.json', 'r', encoding='utf-8') as f:
    rankings = json.load(f)
fighters_db = {f['name'].lower(): f for f in rankings}

with open('fighter_biometrics.json', 'r', encoding='utf-8') as f:
    bio_db = json.load(f)

with open('fighter_details.json', 'r', encoding='utf-8') as f:
    det_db = json.load(f)

with open('fighter_component_elos.json', 'r', encoding='utf-8') as f:
    comp_db = json.load(f)

# Helper function to convert American odds string to decimal
def american_to_decimal(odd_str):
    if not odd_str: return 2.0
    odd_clean = re.sub(r'[^\d\+\-]', '', odd_str)
    try:
        val = float(odd_clean)
        if val > 0:
            return round(1.0 + (val / 100.0), 2)
        elif val < 0:
            return round(1.0 + (100.0 / abs(val)), 2)
        return 2.0
    except Exception:
        return 2.0

def decimal_to_american(d):
    if d <= 1.01: return "-10000"
    p = 1.0 / d
    if p >= 0.5:
        return f"-{round((p / (1.0 - p)) * 100)}"
    else:
        return f"+{round(((1.0 - p) / p) * 100)}"

# Real Bookmakers list from BestFightOdds table
books_list = ["DraftKings", "FanDuel", "BetMGM", "Caesars", "BetRivers", "Polymarket", "Kalshi"]

upcoming_events = []

for ediv in soup.find_all('div', class_='table-div'):
    header = ediv.find('div', class_='table-header')
    if not header: continue
    h1 = header.find('h1')
    title = h1.text.strip().replace(' Odds', '') if h1 else ''
    date_el = header.find('span', class_='table-header-date')
    date_txt = date_el.text.strip() if date_el else ''

    if 'UFC' not in title:
        continue

    left_table = ediv.find('table', class_='odds-table-responsive-header')
    left_names = []
    if left_table:
        for r in left_table.find_all('tr'):
            th = r.find('th', scope='row')
            if th:
                span = th.find('span', class_='t-b-fcc')
                left_names.append(span.text.strip() if span else th.text.strip())

    scroller = ediv.find('div', class_='table-scroller')
    if not scroller: continue
    rows = scroller.find_all('tr')

    fights = []
    current_pair = []
    row_idx = 0

    for r in rows:
        tds = r.find_all('td')
        if not tds: continue
        f_name = left_names[row_idx] if row_idx < len(left_names) else f"Fighter {row_idx}"
        row_idx += 1

        # Skip prop rows like Over/Under, round props, etc.
        skip_words = ['over', 'under', 'round', 'decision', 'inside distance', 'wins by', 'fight ends', 'draw', 'starts round', 'result']
        if any(w in f_name.lower() for w in skip_words):
            continue

        # Extract bookmaker odds
        sportsbook_odds = {}
        all_decimals = []
        for idx, td in enumerate(tds):
            span_best = td.find('span', class_='bestbet')
            txt = span_best.text.strip() if span_best else td.text.strip()
            if txt and ('+' in txt or '-' in txt) and len(txt) <= 7:
                b_name = books_list[idx % len(books_list)]
                dec = american_to_decimal(txt)
                sportsbook_odds[b_name] = {'american': txt, 'decimal': dec}
                all_decimals.append(dec)

        # Best odds available
        best_dec = max(all_decimals) if all_decimals else 2.0
        best_american = decimal_to_american(best_dec)

        current_pair.append({
            'name': f_name,
            'best_decimal': best_dec,
            'best_american': best_american,
            'sportsbooks': sportsbook_odds
        })

        if len(current_pair) == 2:
            fights.append({
                'fighter1': current_pair[0],
                'fighter2': current_pair[1]
            })
            current_pair = []

    if fights:
        upcoming_events.append({
            'event_title': title,
            'event_date': date_txt,
            'fights': fights
        })

print(f"Parsed {len(upcoming_events)} UFC events with {sum(len(e['fights']) for e in upcoming_events)} actual matchups!")
for e in upcoming_events:
    print(f"\n🏟️ {e['event_title']} ({e['event_date']}):")
    for f in e['fights']:
        f1 = f['fighter1']
        f2 = f['fighter2']
        print(f"   • {f1['name']} ({f1['best_american']} / {f1['best_decimal']}) vs {f2['name']} ({f2['best_american']} / {f2['best_decimal']})")

with open('upcoming_raw_odds.json', 'w', encoding='utf-8') as f:
    json.dump(upcoming_events, f, indent=2, ensure_ascii=False)
