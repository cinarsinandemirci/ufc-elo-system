import json
import math
import sys
from datetime import datetime
from elo_engine import UFCEloEngine, DIVISION_HIERARCHY

sys.stdout.reconfigure(encoding='utf-8')

with open('matches.json', 'r', encoding='utf-8') as f:
    matches = json.load(f)

with open('fighter_biometrics.json', 'r', encoding='utf-8') as f:
    bio = json.load(f)

with open('fighter_details.json', 'r', encoding='utf-8') as f:
    det = json.load(f)

engine = UFCEloEngine(base_elo=1500.0, base_k=40.0, decay_per_month=7.5, inactivity_threshold_months=18.0)

def parse_date(m):
    try: return datetime.strptime(m.get('date', '1990-01-01'), '%Y-%m-%d')
    except Exception: return datetime(1990, 1, 1)

matches_sorted = sorted(matches, key=parse_date)

vig = 0.045 # 4.5% standard bookmaker vigorish
thresholds = [0.03, 0.05, 0.08, 0.10, 0.12]
bets_placed = {t: {'bets': 0, 'wins': 0, 'staked': 0.0, 'profit': 0.0} for t in thresholds}

for m in matches_sorted:
    w_name = m.get('winner')
    l_name = m.get('loser')
    f_date = m.get('date', '')
    res = m.get('result_type', 'win')
    w_class = m.get('weight_class', '')

    if not w_name or not l_name:
        continue

    fw = engine.get_or_create_fighter(w_name)
    fl = engine.get_or_create_fighter(l_name)

    w_priors = fw['wins'] + fw['losses'] + fw['draws'] + fw['nc']
    l_priors = fl['wins'] + fl['losses'] + fl['draws'] + fl['nc']

    if w_priors >= 1 and l_priors >= 1 and res == 'win':
        w_dec = engine.calculate_inactivity_and_decay(fw['last_fight_date'], f_date, fw['elo'])
        l_dec = engine.calculate_inactivity_and_decay(fl['last_fight_date'], f_date, fl['elo'])
        w_eff = fw['elo'] - w_dec['decay']
        l_eff = fl['elo'] - l_dec['decay']

        w_tier = engine.get_fighter_natural_tier(fw)
        l_tier = engine.get_fighter_natural_tier(fl)
        b_tier = DIVISION_HIERARCHY.get(w_class, None)
        if b_tier is not None:
            if w_tier is not None and b_tier > w_tier: w_eff -= (b_tier - w_tier) * 35.0
            if l_tier is not None and b_tier > l_tier: l_eff -= (b_tier - l_tier) * 35.0

        bw = {**bio.get(w_name.lower(), {}), **det.get(w_name.lower(), {})}
        bl = {**bio.get(l_name.lower(), {}), **det.get(l_name.lower(), {})}

        w_age = bw.get('age') or 31.0
        l_age = bl.get('age') or 31.0
        is_light = (b_tier is not None and b_tier <= 4)
        if is_light:
            if w_age >= 35.0: w_eff -= min(35.0, (w_age - 34.0) * 12.0)
            if l_age >= 35.0: l_eff -= min(35.0, (l_age - 34.0) * 12.0)
        else:
            if w_age >= 37.0: w_eff -= min(30.0, (w_age - 36.0) * 8.0)
            if l_age >= 37.0: l_eff -= min(30.0, (l_age - 36.0) * 8.0)

        w_reach = bw.get('reach_inches') or 71.0
        l_reach = bl.get('reach_inches') or 71.0
        if (w_reach - l_reach) >= 3.0: w_eff += min(15.0, (w_reach - l_reach - 2.0) * 2.5)
        elif (l_reach - w_reach) >= 3.0: l_eff += min(15.0, (l_reach - w_reach - 2.0) * 2.5)

        p_w_model = 1.0 / (1.0 + 10.0 ** ((l_eff - w_eff) / 400.0))
        p_l_model = 1.0 - p_w_model

        # Market unadjusted baseline + vig
        p_w_market = 1.0 / (1.0 + 10.0 ** ((fl['elo'] - fw['elo']) / 400.0))
        p_l_market = 1.0 - p_w_market

        odds_w = (1.0 - (vig / 2.0)) / max(0.01, p_w_market)
        odds_l = (1.0 - (vig / 2.0)) / max(0.01, p_l_market)

        ev_w = (p_w_model * odds_w) - 1.0
        ev_l = (p_l_model * odds_l) - 1.0

        for t in thresholds:
            # Bet Winner
            if ev_w >= t:
                bets_placed[t]['bets'] += 1
                bets_placed[t]['staked'] += 100.0
                bets_placed[t]['wins'] += 1
                bets_placed[t]['profit'] += (100.0 * (odds_w - 1.0))
            # Bet Loser
            if ev_l >= t:
                bets_placed[t]['bets'] += 1
                bets_placed[t]['staked'] += 100.0
                bets_placed[t]['profit'] -= 100.0

    engine.process_match(m)

print("=" * 80)
print("  UFC DEĞERLİ BAHİS SİNYALİ (+EV) TARİHSEL KÂRLILIK VE ROI SİMÜLASYONU")
print("  (Bahis Şirketi Kar Marjı / Vig: %4.5 | Sabit Bahis: 100$)")
print("=" * 80)

for t in thresholds:
    s = bets_placed[t]
    roi = (s['profit'] / s['staked'] * 100.0) if s['staked'] > 0 else 0.0
    win_rate = (s['wins'] / s['bets'] * 100.0) if s['bets'] > 0 else 0.0
    print(f"🎯 Sinyal Eşiği: EV >= +%{int(t*100):<2} | Toplam Bahis: {s['bets']:<4} | Kazanma: %{win_rate:<5.1f} | Yatırılan: ${s['staked']:<8.0f} | Net Kâr: ${s['profit']:<8.2f} | ROI: +%{roi:.2f}")

print("=" * 80)
