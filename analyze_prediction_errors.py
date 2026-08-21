import json
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

with open('bout_rolling_features.json', 'r', encoding='utf-8') as f:
    bouts = json.load(f)

with open('fighter_rankings.json', 'r', encoding='utf-8') as f:
    rankings = json.load(f)
rank_db = {f['name'].lower(): f for f in rankings}

with open('fighter_archetypes.json', 'r', encoding='utf-8') as f:
    arch_db = json.load(f)

fighter_stats = defaultdict(lambda: {
    'total': 0, 
    'correct': 0, 
    'wrong': 0, 
    'underdog_wins': 0, 
    'fav_losses': 0, 
    'upset_fights': []
})

confidence_tiers = {
    '50.0% - 55.0% (Coin-flip / Toss-up)': {'correct': 0, 'total': 0},
    '55.1% - 65.0% (Moderate Edge)': {'correct': 0, 'total': 0},
    '65.1% - 75.0% (Strong Favorite)': {'correct': 0, 'total': 0},
    '75.1% - 90.0%+ (Heavy Favorite)': {'correct': 0, 'total': 0}
}

division_accuracy = defaultdict(lambda: {'correct': 0, 'total': 0})

total_evaluated = 0
correct_total = 0

for b in bouts:
    f1 = b['fighter1']
    f2 = b['fighter2']
    winner = b['winner']
    if not winner or winner not in [f1, f2]:
        continue

    f1_obj = rank_db.get(f1.lower())
    f2_obj = rank_db.get(f2.lower())
    if not f1_obj or not f2_obj:
        continue

    elo1 = f1_obj['elo']
    elo2 = f2_obj['elo']
    p1 = 1.0 / (1.0 + 10.0 ** ((elo2 - elo1) / 400.0))
    p2 = 1.0 - p1

    pred_winner = f1 if p1 >= 0.5 else f2
    actual_winner = winner
    is_correct = (pred_winner == actual_winner)
    max_p = max(p1, p2)

    total_evaluated += 1
    if is_correct:
        correct_total += 1

    div = f1_obj.get('primary_weight_class', 'Other')
    division_accuracy[div]['total'] += 1
    if is_correct:
        division_accuracy[div]['correct'] += 1

    if max_p <= 0.55:
        tier_key = '50.0% - 55.0% (Coin-flip / Toss-up)'
    elif max_p <= 0.65:
        tier_key = '55.1% - 65.0% (Moderate Edge)'
    elif max_p <= 0.75:
        tier_key = '65.1% - 75.0% (Strong Favorite)'
    else:
        tier_key = '75.1% - 90.0%+ (Heavy Favorite)'

    confidence_tiers[tier_key]['total'] += 1
    if is_correct:
        confidence_tiers[tier_key]['correct'] += 1

    # Fighter 1 tracking
    fighter_stats[f1]['total'] += 1
    if is_correct:
        fighter_stats[f1]['correct'] += 1
    else:
        fighter_stats[f1]['wrong'] += 1
        if winner == f1 and p1 < 0.5:
            fighter_stats[f1]['underdog_wins'] += 1
            fighter_stats[f1]['upset_fights'].append(f"WON as underdog vs {f2} ({p1*100:.1f}%)")
        elif winner == f2 and p1 >= 0.5:
            fighter_stats[f1]['fav_losses'] += 1
            fighter_stats[f1]['upset_fights'].append(f"LOST as favorite vs {f2} ({p1*100:.1f}%)")

    # Fighter 2 tracking
    fighter_stats[f2]['total'] += 1
    if is_correct:
        fighter_stats[f2]['correct'] += 1
    else:
        fighter_stats[f2]['wrong'] += 1
        if winner == f2 and p2 < 0.5:
            fighter_stats[f2]['underdog_wins'] += 1
            fighter_stats[f2]['upset_fights'].append(f"WON as underdog vs {f1} ({p2*100:.1f}%)")
        elif winner == f1 and p2 >= 0.5:
            fighter_stats[f2]['fav_losses'] += 1
            fighter_stats[f2]['upset_fights'].append(f"LOST as favorite vs {f1} ({p2*100:.1f}%)")

print("==========================================================================================")
print(f"  OVERALL 25-YEAR PREDICTIVE ACCURACY: {correct_total} / {total_evaluated} -> {correct_total/total_evaluated*100:.2f}%")
print("==========================================================================================")

print("\n--- ACCURACY BREAKDOWN BY CONFIDENCE TIER ---")
for t_name, t_data in confidence_tiers.items():
    acc = (t_data['correct'] / t_data['total'] * 100) if t_data['total'] > 0 else 0
    print(f"  • {t_name:38s}: {t_data['correct']:4d} / {t_data['total']:4d} ({acc:5.2f}%)")

print("\n--- ACCURACY BY WEIGHT CLASS ---")
for div_name, d_data in sorted(division_accuracy.items(), key=lambda x: (x[1]['correct']/x[1]['total'] if x[1]['total']>0 else 0), reverse=True):
    if d_data['total'] >= 100:
        acc = (d_data['correct'] / d_data['total'] * 100)
        print(f"  • {div_name:24s}: {d_data['correct']:4d} / {d_data['total']:4d} ({acc:5.2f}%)")

# Filter fighters with min 10 UFC bouts
min_10_fighters = [(name, s) for name, s in fighter_stats.items() if s['total'] >= 10]
min_10_fighters.sort(key=lambda x: (x[1]['wrong'] / x[1]['total']), reverse=True)

print("\n=========================================================================================================================")
print(f"{'FIGHTER':24s} | {'ERROR %':8s} | {'WRONG/TOT':9s} | {'ARCHETYPE':20s} | {'UPSET WINS':10s} | {'FAV LOSSES':10s} | {'KEY ANOMALY'}")
print("=========================================================================================================================")
for name, s in min_10_fighters[:25]:
    err_pct = (s['wrong'] / s['total']) * 100
    arch = arch_db.get(name.lower(), {}).get('archetype', 'N/A')
    sample_upsets = ", ".join(s['upset_fights'][:2])
    print(f"{name:24s} | {err_pct:5.1f}%  | {s['wrong']:2d}/{s['total']:2d}   | {arch:20s} | {s['underdog_wins']:2d} wins   | {s['fav_losses']:2d} losses  | {sample_upsets}")
print("=========================================================================================================================\n")
