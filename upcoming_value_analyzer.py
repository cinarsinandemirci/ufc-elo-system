import json
import re
import sys
from datetime import datetime
from elo_engine import UFCEloEngine, DIVISION_HIERARCHY
from pedigree_engine import PedigreeCalibrationEngine

sys.stdout.reconfigure(encoding='utf-8')

# Load all databases
with open('upcoming_raw_odds.json', 'r', encoding='utf-8') as f:
    events_raw = json.load(f)

with open('fighter_rankings.json', 'r', encoding='utf-8') as f:
    rankings = json.load(f)
fighters_db = {f['name'].lower(): f for f in rankings}

with open('fighter_biometrics.json', 'r', encoding='utf-8') as f:
    bio_db = json.load(f)

with open('fighter_details.json', 'r', encoding='utf-8') as f:
    det_db = json.load(f)

with open('fighter_component_elos.json', 'r', encoding='utf-8') as f:
    comp_db = json.load(f)

engine = UFCEloEngine(base_elo=1500.0, base_k=40.0, decay_per_month=7.5, inactivity_threshold_months=18.0)
pedigree_engine = PedigreeCalibrationEngine()

def find_fighter(name):
    key = name.strip().lower()
    if key in fighters_db:
        return fighters_db[key]
    
    # Try partial / lastname matching
    for k, v in fighters_db.items():
        if key in k or k in key:
            return v
    
    # Fallback default fighter object
    return {
        'name': name.strip(),
        'elo': 1500.0,
        'peak_elo': 1500.0,
        'wins': 2,
        'losses': 1,
        'draws': 0,
        'nc': 0,
        'primary_weight_class': 'Lightweight',
        'is_active': True,
        'last_fight_date': '2025-10-01',
        'uncertainty_mult': 1.0,
        'total_fights': 3,
        'win_streak': 1,
        'methods': {'KO/TKO_win': 1, 'SUB_win': 0, 'DEC_win': 1, 'KO/TKO_loss': 0}
    }

def analyze_matchup(f1_obj, f2_obj, book_dec_1, book_dec_2, is_title=False, is_apex=False, is_high_altitude=False):
    t1 = DIVISION_HIERARCHY.get(f1_obj.get('primary_weight_class', 'Lightweight'), 4)
    t2 = DIVISION_HIERARCHY.get(f2_obj.get('primary_weight_class', 'Lightweight'), 4)
    target_tier = max(t1, t2)

    # 1. Size adjustment
    size_adj_1 = -(target_tier - t1) * 35.0 if target_tier > t1 else 0.0
    size_adj_2 = -(target_tier - t2) * 35.0 if target_tier > t2 else 0.0

    # 2. Biometrics & DOB Parsing
    b1 = {**bio_db.get(f1_obj['name'].lower(), {}), **det_db.get(f1_obj['name'].lower(), {})}
    b2 = {**bio_db.get(f2_obj['name'].lower(), {}), **det_db.get(f2_obj['name'].lower(), {})}

    def parse_age(detail_dict, fallback=30.0):
        dob_str = detail_dict.get('dob')
        if dob_str:
            try:
                dob = datetime.strptime(dob_str, '%b %d, %Y')
                now = datetime.strptime('2026-08-21', '%Y-%m-%d')
                return (now - dob).days / 365.25
            except Exception:
                pass
        return detail_dict.get('age') or fallback

    age1 = parse_age(b1, 30.0)
    age2 = parse_age(b2, 30.0)
    is_light = (target_tier <= 4)

    age_adj_1 = 0.0
    age_adj_2 = 0.0
    if is_light:
        if age1 >= 34.5: age_adj_1 -= min(35.0, (age1 - 33.5) * 12.0)
        if age2 >= 34.5: age_adj_2 -= min(35.0, (age2 - 33.5) * 12.0)
    else:
        if age1 >= 36.5: age_adj_1 -= min(30.0, (age1 - 35.5) * 8.0)
        if age2 >= 36.5: age_adj_2 -= min(30.0, (age2 - 35.5) * 8.0)

    age_gap = age2 - age1
    if age_gap >= 6.0 and age1 < 34.0:
        age_adj_1 += min(15.0, (age_gap - 5.0) * 2.5)
    elif age_gap <= -6.0 and age2 < 34.0:
        age_adj_2 += min(15.0, (-age_gap - 5.0) * 2.5)

    reach1 = b1.get('reach_inches') or 71.0
    reach2 = b2.get('reach_inches') or 71.0
    reach_gap = reach1 - reach2

    reach_adj_1 = 0.0
    reach_adj_2 = 0.0
    if reach_gap >= 3.0: reach_adj_1 += min(16.0, (reach_gap - 2.0) * 3.0)
    elif reach_gap <= -3.0: reach_adj_2 += min(16.0, (-reach_gap - 2.0) * 3.0)

    stance1 = b1.get('stance', 'Orthodox')
    stance2 = b2.get('stance', 'Orthodox')
    stance_adj_1 = 8.0 if (stance1 == 'Southpaw' and stance2 == 'Orthodox') else (4.0 if stance1 == 'Switch' else 0.0)
    stance_adj_2 = 8.0 if (stance2 == 'Southpaw' and stance1 == 'Orthodox') else (4.0 if stance2 == 'Switch' else 0.0)

    tdd1 = b1.get('tactical', {}).get('td_def_pct', 70.0) if b1.get('tactical') else 70.0
    tdd2 = b2.get('tactical', {}).get('td_def_pct', 70.0) if b2.get('tactical') else 70.0

    # Stylistic interaction
    arch1 = f1_obj.get('archetype', 'Distance Out-Fighter')
    arch2 = f2_obj.get('archetype', 'Distance Out-Fighter')
    style_matrix = {
        ('Pressure Wrestler', 'Distance Out-Fighter'): 20.0,
        ('Pressure Wrestler', 'Inside Pressure Boxer'): 16.0,
        ('Sprawl-and-Brawler', 'Pressure Wrestler'): 18.0,
        ('Submission Hunter', 'Clinch Grinder'): 15.0,
        ('Inside Pressure Boxer', 'Distance Out-Fighter'): 14.0,
        ('Distance Out-Fighter', 'Clinch Grinder'): 14.0,
    }
    style_bonus = 0.0
    if (arch1, arch2) in style_matrix:
        style_bonus = style_matrix[(arch1, arch2)]
    elif (arch2, arch1) in style_matrix:
        style_bonus = -style_matrix[(arch2, arch1)]

    if 'Wrestler' in arch1 and tdd2 >= 82.0 and style_bonus > 0:
        style_bonus *= 0.35
    if 'Wrestler' in arch2 and tdd1 >= 82.0 and style_bonus < 0:
        style_bonus *= 0.35

    style_shift = style_bonus

    # 2b. Women's Division Volume Output
    is_women_div = f1_obj.get('primary_weight_class', '').startswith("Women's") or f2_obj.get('primary_weight_class', '').startswith("Women's")
    slpm1 = b1.get('tactical', {}).get('slpm', 3.8) if b1.get('tactical') else 3.8
    slpm2 = b2.get('tactical', {}).get('slpm', 3.8) if b2.get('tactical') else 3.8
    vol_multiplier = 4.0 if is_women_div else 1.8
    vol_diff = (slpm1 - slpm2) * vol_multiplier
    vol_adj_1 = max(-18.0, min(18.0, vol_diff)) if vol_diff > 0 else 0.0
    vol_adj_2 = max(-18.0, min(18.0, -vol_diff)) if vol_diff < 0 else 0.0

    # 2c. Environmental Adjustments (Apex 25ft Cage + High Altitude)
    apex_adj_1 = 0.0
    apex_adj_2 = 0.0
    if is_apex:
        if arch1 in ['Pressure Wrestler', 'Inside Pressure Boxer', 'Clinch Grinder'] and arch2 == 'Distance Out-Fighter':
            apex_adj_1 += 12.0
        elif arch2 in ['Pressure Wrestler', 'Inside Pressure Boxer', 'Clinch Grinder'] and arch1 == 'Distance Out-Fighter':
            apex_adj_2 += 12.0

    c1_comp = comp_db.get(f1_obj['name'].lower(), {})
    c2_comp = comp_db.get(f2_obj['name'].lower(), {})
    alt_adj_1 = 0.0
    alt_adj_2 = 0.0
    if is_high_altitude:
        c1_card = c1_comp.get('cardio_elo', 1500.0) if c1_comp else 1500.0
        c2_card = c2_comp.get('cardio_elo', 1500.0) if c2_comp else 1500.0
        card_diff = (c1_card - c2_card) / 400.0
        if card_diff > 0:
            alt_adj_1 += min(18.0, card_diff * 35.0)
        elif card_diff < 0:
            alt_adj_2 += min(18.0, -card_diff * 35.0)

    # 3. Inactivity decay
    d1 = engine.calculate_inactivity_and_decay(f1_obj.get('last_fight_date', '2025-01-01'), '2026-08-21', f1_obj['elo'])
    d2 = engine.calculate_inactivity_and_decay(f2_obj.get('last_fight_date', '2025-01-01'), '2026-08-21', f2_obj['elo'])

    # 4. Bayesian Pre-UFC Combat Pedigree Prior
    ped1 = pedigree_engine.calibrate_fighter_ratings(f1_obj['name'], f1_obj['elo'], f1_obj.get('total_fights', 0), comp_db.get(f1_obj['name'].lower()))
    ped2 = pedigree_engine.calibrate_fighter_ratings(f2_obj['name'], f2_obj['elo'], f2_obj.get('total_fights', 0), comp_db.get(f2_obj['name'].lower()))
    ped_adj_1 = round(ped1['effective_elo'] - f1_obj['elo'], 1) if ped1.get('pedigree_active') else 0.0
    ped_adj_2 = round(ped2['effective_elo'] - f2_obj['elo'], 1) if ped2.get('pedigree_active') else 0.0

    eff_1 = f1_obj['elo'] - d1['decay'] + size_adj_1 + age_adj_1 + reach_adj_1 + stance_adj_1 + style_shift + vol_adj_1 + apex_adj_1 + alt_adj_1 + ped_adj_1
    eff_2 = f2_obj['elo'] - d2['decay'] + size_adj_2 + age_adj_2 + reach_adj_2 + stance_adj_2 + vol_adj_2 + apex_adj_2 + alt_adj_2 + ped_adj_2

    p1 = 1.0 / (1.0 + 10.0 ** ((eff_2 - eff_1) / 400.0))
    p2 = 1.0 - p1

    fair_dec_1 = round(1.0 / max(0.01, p1), 2)
    fair_dec_2 = round(1.0 / max(0.01, p2), 2)

    # Real EV calculation vs Actual Sportsbook Odds
    ev_1 = round(((p1 * book_dec_1) - 1.0) * 100.0, 2)
    ev_2 = round(((p2 * book_dec_2) - 1.0) * 100.0, 2)

    def calc_kelly(prob, dec_odds):
        b = dec_odds - 1.0
        q = 1.0 - prob
        if b <= 0: return 0.0
        raw_k = (b * prob - q) / b
        return round(max(0.0, min(0.06, raw_k * 0.25)) * 100.0, 1)

    kelly_1 = calc_kelly(p1, book_dec_1)
    kelly_2 = calc_kelly(p2, book_dec_2)

    drivers_1 = []
    drivers_2 = []
    if ped_adj_1 > 0: drivers_1.append(f"🥇 Pedigree Prior (+{round(ped_adj_1, 1)} Elo)")
    if age_adj_1 > 0: drivers_1.append(f"⚡ Prime Speed (+{round(age_adj_1, 1)} Elo)")
    if age_adj_2 < 0: drivers_1.append(f"⚠️ Opponent Age Cliff ({round(age_adj_2, 1)} Elo)")
    if reach_adj_1 > 0: drivers_1.append(f"📏 +{round(reach_gap, 1)}\" Reach Edge (+{round(reach_adj_1, 1)} Elo)")
    if stance_adj_1 > 0: drivers_1.append(f"🥊 Open Stance Southpaw (+{round(stance_adj_1, 1)} Elo)")
    if style_shift > 5.0: drivers_1.append(f"🥋 Tactical Style Edge (+{round(style_shift, 1)} Elo)")
    if vol_adj_1 >= 5.0: drivers_1.append(f"📊 High Volume Output (+{round(vol_adj_1, 1)} Elo)")
    if is_apex and apex_adj_1 > 0: drivers_1.append(f"🏟️ 25-ft Apex Cage (+12.0 Elo)")
    if is_high_altitude and alt_adj_1 > 0: drivers_1.append(f"🏔️ Altitude Cardio (+{round(alt_adj_1, 1)} Elo)")
    if stance_adj_1 > 0: drivers_1.append(f"🥊 Open Stance Southpaw (+{round(stance_adj_1, 1)} Elo)")
    if tdd1 >= 80.0 and 'Wrestler' in arch2: drivers_1.append(f"🛡️ {round(tdd1)}% TDD Wall")
    if style_shift > 5.0: drivers_1.append(f"🥋 Tactical Style Edge (+{round(style_shift, 1)} Elo)")

    if ped_adj_2 > 0: drivers_2.append(f"🥇 Pedigree Prior (+{round(ped_adj_2, 1)} Elo)")
    if age_adj_2 > 0: drivers_2.append(f"⚡ Prime Speed (+{round(age_adj_2, 1)} Elo)")
    if age_adj_1 < 0: drivers_2.append(f"⚠️ Opponent Age Cliff ({round(age_adj_1, 1)} Elo)")
    if reach_adj_2 > 0: drivers_2.append(f"📏 +{round(-reach_gap, 1)}\" Reach Edge (+{round(reach_adj_2, 1)} Elo)")
    if stance_adj_2 > 0: drivers_2.append(f"🥊 Open Stance Southpaw (+{round(stance_adj_2, 1)} Elo)")
    if tdd2 >= 80.0 and 'Wrestler' in arch1: drivers_2.append(f"🛡️ {round(tdd2)}% TDD Wall")
    if style_shift < -5.0: drivers_2.append(f"🥋 Tactical Style Edge (+{round(-style_shift, 1)} Elo)")

    c1 = comp_db.get(f1_obj['name'].lower(), {'striking_elo': 1500.0, 'grappling_elo': 1500.0, 'cardio_elo': 1500.0})
    c2 = comp_db.get(f2_obj['name'].lower(), {'striking_elo': 1500.0, 'grappling_elo': 1500.0, 'cardio_elo': 1500.0})

    return {
        'fighter1': {
            'name': f1_obj['name'],
            'elo': f1_obj['elo'],
            'effective_elo': round(eff_1, 1),
            'model_prob': round(p1 * 100.0, 1),
            'fair_odds': fair_dec_1,
            'bookmaker_odds': book_dec_1,
            'ev_pct': ev_1,
            'kelly_pct': kelly_1,
            'has_value': ev_1 >= 3.0,
            'edge_drivers': drivers_1,
            'components': c1
        },
        'fighter2': {
            'name': f2_obj['name'],
            'elo': f2_obj['elo'],
            'effective_elo': round(eff_2, 1),
            'model_prob': round(p2 * 100.0, 1),
            'fair_odds': fair_dec_2,
            'bookmaker_odds': book_dec_2,
            'ev_pct': ev_2,
            'kelly_pct': kelly_2,
            'has_value': ev_2 >= 3.0,
            'edge_drivers': drivers_2,
            'components': c2
        }
    }

analyzed_events = []
all_value_signals = []

ALTITUDE_KEYWORDS = ['salt lake city', 'denver', 'mexico', 'albuquerque', 'bogota', 'utah', 'colorado']

for e in events_raw:
    ev_title = e['event_title']
    ev_date = e['event_date']
    ev_lower = ev_title.lower()
    is_apex = ('apex' in ev_lower or ('vegas' in ev_lower and 'ufc 3' not in ev_lower and 'ufc 2' not in ev_lower))
    is_high_alt = any(alt in ev_lower for alt in ALTITUDE_KEYWORDS)
    analyzed_fights = []

    for f in e['fights']:
        raw_f1 = f['fighter1']
        raw_f2 = f['fighter2']

        f1_obj = find_fighter(raw_f1['name'])
        f2_obj = find_fighter(raw_f2['name'])

        book_1 = raw_f1['best_decimal']
        book_2 = raw_f2['best_decimal']

        analysis = analyze_matchup(f1_obj, f2_obj, book_1, book_2, is_title=False, is_apex=is_apex, is_high_altitude=is_high_alt)

        fight_entry = {
            'event': ev_title,
            'date': ev_date,
            'fighter1': {
                **analysis['fighter1'],
                'sportsbooks': raw_f1['sportsbooks']
            },
            'fighter2': {
                **analysis['fighter2'],
                'sportsbooks': raw_f2['sportsbooks']
            }
        }

        # Check if either side is +EV
        v1 = analysis['fighter1']
        v2 = analysis['fighter2']

        if v1['ev_pct'] >= 3.0:
            all_value_signals.append({
                'event': ev_title,
                'date': ev_date,
                'value_fighter': v1['name'],
                'opponent': v2['name'],
                'model_prob': v1['model_prob'],
                'fair_odds': v1['fair_odds'],
                'best_book_odds': v1['bookmaker_odds'],
                'ev_pct': v1['ev_pct'],
                'kelly_stake': v1['kelly_pct'],
                'tier': "💎 ULTRA VALUE" if v1['ev_pct'] >= 10.0 else ("⚡ STRONG VALUE" if v1['ev_pct'] >= 5.0 else "🎯 MODERATE VALUE"),
                'edge_drivers': v1['edge_drivers'],
                'sportsbooks': raw_f1['sportsbooks']
            })

        if v2['ev_pct'] >= 3.0:
            all_value_signals.append({
                'event': ev_title,
                'date': ev_date,
                'value_fighter': v2['name'],
                'opponent': v1['name'],
                'model_prob': v2['model_prob'],
                'fair_odds': v2['fair_odds'],
                'best_book_odds': v2['bookmaker_odds'],
                'ev_pct': v2['ev_pct'],
                'kelly_stake': v2['kelly_pct'],
                'tier': "💎 ULTRA VALUE" if v2['ev_pct'] >= 10.0 else ("⚡ STRONG VALUE" if v2['ev_pct'] >= 5.0 else "🎯 MODERATE VALUE"),
                'edge_drivers': v2['edge_drivers'],
                'sportsbooks': raw_f2['sportsbooks']
            })

        analyzed_fights.append(fight_entry)

    if analyzed_fights:
        analyzed_events.append({
            'event_title': ev_title,
            'event_date': ev_date,
            'fights': analyzed_fights
        })

# Sort all signals descending by EV %
all_value_signals.sort(key=lambda x: x['ev_pct'], reverse=True)

final_data = {
    'total_upcoming_events': len(analyzed_events),
    'total_value_signals_found': len(all_value_signals),
    'events': analyzed_events,
    'top_upcoming_value_bets': all_value_signals
}

with open('upcoming_events_with_signals.json', 'w', encoding='utf-8') as f:
    json.dump(final_data, f, indent=2, ensure_ascii=False)

print("\n==========================================================================================")
print(f"  YAKLAŞAN GERÇEK UFC KARTLARI İÇİN +EV DEĞERLİ BAHİS ANALİZİ ({len(all_value_signals)} FIRSAT BULUNDU)")
print("==========================================================================================")

for s in all_value_signals[:10]:
    print(f"\n💎 [{s['event']} - {s['date']}] {s['value_fighter']} vs {s['opponent']}")
    print(f"   • Model Kazanma İhtimali: %{s['model_prob']} (Adil Oran: {s['fair_odds']})")
    print(f"   • En İyi Bahis Sitesi Oranı: {s['best_book_odds']} -> Net Beklenen Değer: +%{s['ev_pct']} EV ({s['tier']})")
    print(f"   • Önerilen Quarter-Kelly Bahis Payı: %{s['kelly_stake']} Kasa")
    print(f"   • Model Alpha Nedenleri: {', '.join(s['edge_drivers'])}")
    if s['sportsbooks']:
        sb_str = " | ".join([f"{k}: {v['american']}" for k, v in list(s['sportsbooks'].items())[:4]])
        print(f"   • Bahis Siteleri: {sb_str}")

print("==========================================================================================\n")
