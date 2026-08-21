import json
import sys
import numpy as np
from collections import defaultdict
from elo_engine import UFCEloEngine

sys.stdout.reconfigure(encoding='utf-8')

# 1. Load matches
with open('matches.json', 'r', encoding='utf-8') as f:
    matches = json.load(f)

with open('pedigree_database.json', 'r', encoding='utf-8') as f:
    ped_db = json.load(f)

print("==========================================================================================")
print("  PEDIGREE CALIBRATION & ROLLING BACKTEST GRID OPTIMIZATION (8,515 BOUTS)")
print("==========================================================================================")

# Test different prior dampening scaling factors
# Scale 0.0 = Pure Base 1500 (No ledger inflation)
# Scale 0.25 = Dampened +25-35 Elo (e.g. 1535 for Olympic, 1525 for Glory)
# Scale 0.50 = Moderate +50-70 Elo
# Scale 1.00 = Full unconstrained +120-150 Elo (Caused the overshoot)

scales_to_test = [
    ("Pure Zero-Sum (0.0x - Baseline 1500)", 0.0),
    ("Conservative Dampened (0.25x - +25 to +35 Elo)", 0.25),
    ("Moderate Dampened (0.40x - +40 to +60 Elo)", 0.40),
    ("High Injection (0.75x - +80 to +110 Elo)", 0.75),
    ("Full Unconstrained (1.00x - Current Overshoot)", 1.00)
]

results = []

for label, scale in scales_to_test:
    engine = UFCEloEngine(base_elo=1500.0, base_k=32.0, decay_per_month=5.0, inactivity_threshold_months=18.0)
    
    # Custom get_or_create_fighter with scaled prior
    def make_get_or_create(scale_val):
        def custom_get(name):
            if name not in engine.fighters:
                init_elo = 1500.0
                if name.lower() in ped_db and scale_val > 0.0:
                    raw_prior = ped_db[name.lower()].get('prior_elo', 1500.0)
                    bonus = (raw_prior - 1500.0) * scale_val
                    init_elo = 1500.0 + bonus

                engine.fighters[name] = {
                    'name': name,
                    'elo': init_elo,
                    'peak_elo': init_elo,
                    'lowest_elo': init_elo,
                    'wins': 0, 'losses': 0, 'draws': 0, 'nc': 0,
                    'win_streak': 0, 'best_win_streak': 0,
                    'title_fights': 0, 'title_wins': 0,
                    'methods': {
                        'KO/TKO_win': 0, 'SUB_win': 0, 'DEC_win': 0,
                        'U-DEC_win': 0, 'S-DEC_win': 0, 'OTHER_win': 0,
                        'KO/TKO_loss': 0, 'SUB_loss': 0, 'DEC_loss': 0,
                        'U-DEC_loss': 0, 'S-DEC_loss': 0, 'OTHER_loss': 0,
                    },
                    'total_kd': 0, 'total_sig_str': 0, 'total_td': 0,
                    'weight_classes': defaultdict(int),
                    'recent_divisions': [],
                    'last_fight_date': None,
                    'last_delta': 0.0,
                    'total_decay': 0.0,
                    'fights_history': []
                }
            return engine.fighters[name]
        return custom_get

    engine.get_or_create_fighter = make_get_or_create(scale)
    
    # Process all matches and evaluate chronological walk-forward metrics
    correct = 0
    total_bouts = 0
    brier_scores = []
    log_losses = []

    for m in matches:
        f1_name = m.get('fighter1')
        f2_name = m.get('fighter2')
        winner = m.get('winner')
        if not winner or winner not in [f1_name, f2_name]:
            continue

        f1 = engine.get_or_create_fighter(f1_name)
        f2 = engine.get_or_create_fighter(f2_name)

        r1 = f1['elo']
        r2 = f2['elo']
        p1 = 1.0 / (1.0 + 10.0 ** ((r2 - r1) / 400.0))
        p2 = 1.0 - p1

        p1_safe = max(1e-5, min(1.0 - 1e-5, p1))
        actual_1 = 1.0 if winner == f1_name else 0.0

        brier = (p1 - actual_1) ** 2
        logloss = -(actual_1 * np.log(p1_safe) + (1.0 - actual_1) * np.log(1.0 - p1_safe))

        brier_scores.append(brier)
        log_losses.append(logloss)

        if (p1 >= 0.5 and actual_1 == 1.0) or (p1 < 0.5 and actual_1 == 0.0):
            correct += 1
        total_bouts += 1

        engine.process_match(m)

    acc = (correct / total_bouts) * 100.0
    mean_brier = np.mean(brier_scores)
    mean_logloss = np.mean(log_losses)

    # Get sample peak Elos
    fighters_list = engine.fighters
    cormier_peak = fighters_list.get('Daniel Cormier', {}).get('peak_elo', 0.0)
    pereira_peak = fighters_list.get('Alex Pereira', {}).get('peak_elo', 0.0)
    conor_peak = fighters_list.get('Conor McGregor', {}).get('peak_elo', 0.0)
    islam_peak = fighters_list.get('Islam Makhachev', {}).get('peak_elo', 0.0)
    jones_peak = fighters_list.get('Jon Jones', {}).get('peak_elo', 0.0)

    results.append({
        'label': label,
        'scale': scale,
        'accuracy': acc,
        'brier': mean_brier,
        'logloss': mean_logloss,
        'cormier_peak': cormier_peak,
        'pereira_peak': pereira_peak,
        'conor_peak': conor_peak,
        'islam_peak': islam_peak,
        'jones_peak': jones_peak
    })

print(f"{'CONFIGURATION':40s} | {'ACCURACY':9s} | {'BRIER':7s} | {'LOG-LOSS':8s} | {'CORMIER':8s} | {'PEREIRA':8s} | {'MCGREGOR':8s} | {'ISLAM':8s}")
print("-" * 115)
for r in results:
    print(f"{r['label']:40s} | {r['accuracy']:6.2f}%   | {r['brier']:6.4f}  | {r['logloss']:7.4f}  | {r['cormier_peak']:6.1f}   | {r['pereira_peak']:6.1f}   | {r['conor_peak']:6.1f}     | {r['islam_peak']:6.1f}")

print("==========================================================================================\n")
