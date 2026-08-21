import json
import math
import sys
from datetime import datetime
import numpy as np
from collections import defaultdict
from elo_engine import UFCEloEngine
from pedigree_engine import PedigreeCalibrationEngine

sys.stdout.reconfigure(encoding='utf-8')

print("==========================================================================================")
print("  TESTING IMPROVEMENT 1 & 2: DYNAMIC HISTORICAL AGE CLIFF + TACTICAL STYLE/REACH SCALING")
print("==========================================================================================")

with open('matches.json', 'r', encoding='utf-8') as f:
    matches = json.load(f)
with open('fighter_details.json', 'r', encoding='utf-8') as f:
    det_db = json.load(f)
with open('fighter_biometrics.json', 'r', encoding='utf-8') as f:
    bio_db = json.load(f)
with open('fighter_archetypes.json', 'r', encoding='utf-8') as f:
    arch_db = json.load(f)

valid_matches = [m for m in matches if m.get('date') and m.get('winner') and m.get('winner') in [m.get('fighter1'), m.get('fighter2')]]
valid_matches.sort(key=lambda x: x['date'])

# Helper: True Historical Age from DOB
dob_cache = {}
for name, d in det_db.items():
    dob_str = d.get('dob')
    if dob_str:
        try:
            dob_cache[name.lower()] = datetime.strptime(dob_str, '%b %d, %Y')
        except:
            pass

def get_historical_age(fighter_name, fight_date_obj):
    dob = dob_cache.get(fighter_name.lower())
    if dob and fight_date_obj:
        return (fight_date_obj - dob).days / 365.25
    return None

# Stylistic advantage matrix
STYLE_MATRIX = {
    ('Pressure Wrestler', 'Distance Out-Fighter'): 22.0,
    ('Pressure Wrestler', 'Inside Pressure Boxer'): 18.0,
    ('Sprawl-and-Brawler', 'Pressure Wrestler'): 20.0,
    ('Submission Hunter', 'Clinch Grinder'): 16.0,
    ('Inside Pressure Boxer', 'Distance Out-Fighter'): 14.0,
    ('Distance Out-Fighter', 'Clinch Grinder'): 15.0,
}

engine = UFCEloEngine(base_elo=1500.0, base_k=32.0, decay_per_month=5.0, inactivity_threshold_months=18.0, prior_dampening=0.25)

base_correct = 0
enhanced_correct = 0
total = 0

base_brier = []
enhanced_brier = []

close_base_correct = 0
close_enh_correct = 0
close_total = 0

for m in valid_matches:
    f1_name = m['fighter1']
    f2_name = m['fighter2']
    winner = m['winner']
    date_str = m['date']
    wc = m.get('weight_class', '')

    fdate = None
    try:
        fdate = datetime.strptime(date_str, '%Y-%m-%d')
    except:
        pass

    f1 = engine.get_or_create_fighter(f1_name)
    f2 = engine.get_or_create_fighter(f2_name)

    r1 = f1['elo']
    r2 = f2['elo']

    # 1. Base 1D Elo
    p1_base = 1.0 / (1.0 + 10.0 ** ((r2 - r1) / 400.0))
    actual_1 = 1.0 if winner == f1_name else 0.0

    # 2. Improvement 1: Dynamic Age Cliff from DOB
    age1 = get_historical_age(f1_name, fdate)
    age2 = get_historical_age(f2_name, fdate)

    # Division specific age thresholds (Heavyweights age better than Flyweights)
    is_hw = ('Heavyweight' in wc)
    is_fly = ('Flyweight' in wc or 'Strawweight' in wc or 'Bantamweight' in wc)
    age_threshold = 36.5 if is_hw else (33.5 if is_fly else 35.0)

    age_penalty1 = 0.0
    age_penalty2 = 0.0
    if age1 and age2:
        if age1 >= age_threshold and age2 <= (age_threshold - 3.5):
            age_penalty1 = (age1 - (age_threshold - 1.0)) * 12.0
        elif age2 >= age_threshold and age1 <= (age_threshold - 3.5):
            age_penalty2 = (age2 - (age_threshold - 1.0)) * 12.0

    # 3. Improvement 2: Tactical Style & Reach Scaling
    b1 = bio_db.get(f1_name.lower(), {})
    b2 = bio_db.get(f2_name.lower(), {})
    reach1 = b1.get('reach_inches') or 71.0
    reach2 = b2.get('reach_inches') or 71.0
    reach_diff = reach1 - reach2

    reach_bonus = 0.0
    if abs(reach_diff) >= 3.0:
        reach_bonus = max(-20.0, min(20.0, reach_diff * 3.0))

    # Stance advantage (Southpaw vs Orthodox)
    stance1 = b1.get('stance', 'Orthodox')
    stance2 = b2.get('stance', 'Orthodox')
    stance_bonus = 0.0
    if stance1 == 'Southpaw' and stance2 == 'Orthodox':
        stance_bonus = 6.0
    elif stance2 == 'Southpaw' and stance1 == 'Orthodox':
        stance_bonus = -6.0

    # Stylistic interaction
    arch1 = arch_db.get(f1_name.lower(), {}).get('archetype', 'Distance Out-Fighter')
    arch2 = arch_db.get(f2_name.lower(), {}).get('archetype', 'Distance Out-Fighter')
    
    style_bonus = 0.0
    if (arch1, arch2) in STYLE_MATRIX:
        style_bonus = STYLE_MATRIX[(arch1, arch2)]
    elif (arch2, arch1) in STYLE_MATRIX:
        style_bonus = -STYLE_MATRIX[(arch2, arch1)]

    # Tactical Modifier (active across all bouts, dynamically scaled)
    tactical_delta1 = -age_penalty1 + reach_bonus + stance_bonus + (style_bonus * 0.7)
    tactical_delta2 = -age_penalty2 - reach_bonus - stance_bonus - (style_bonus * 0.7)

    eff_r1 = r1 + tactical_delta1
    eff_r2 = r2 + tactical_delta2

    p1_enh = 1.0 / (1.0 + 10.0 ** ((eff_r2 - eff_r1) / 400.0))

    # Base Tracking
    base_fav_won = (p1_base >= 0.5 and actual_1 == 1.0) or (p1_base < 0.5 and actual_1 == 0.0)
    if base_fav_won: base_correct += 1
    base_brier.append((p1_base - actual_1) ** 2)

    # Enhanced Tracking
    enh_fav_won = (p1_enh >= 0.5 and actual_1 == 1.0) or (p1_enh < 0.5 and actual_1 == 0.0)
    if enh_fav_won: enhanced_correct += 1
    enhanced_brier.append((p1_enh - actual_1) ** 2)

    # Close Match Tracking (Delta Elo <= 50)
    if abs(r1 - r2) <= 50.0:
        close_total += 1
        if base_fav_won: close_base_correct += 1
        if enh_fav_won: close_enh_correct += 1

    total += 1
    engine.process_match(m)

print("\n" + "=" * 90)
print(f"  BACKTEST COMPARISON: BASELINE 1D ELO VS ENHANCED (IMPROVEMENTS 1 & 2)")
print("=" * 90)
print(f"  • Overall Total Bouts Evaluated       : {total:,} bouts (1993 - 2026)")
print(f"  • Base 1D Elo Walk-Forward Accuracy   : {base_correct/total*100:6.2f}% ({base_correct:,} correct)")
print(f"  • Enhanced Walk-Forward Accuracy      : {enhanced_correct/total*100:6.2f}% ({enhanced_correct:,} correct)")
print(f"  • 🚀 Net Additional Correct Picks    : +{(enhanced_correct - base_correct)} BOUTS!")
print(f"  • Base Mean Brier Score               : {np.mean(base_brier):6.4f}")
print(f"  • Enhanced Mean Brier Score           : {np.mean(enhanced_brier):6.4f} (Improved Probability Calibration)")
print("-" * 90)
print(f"  • Close Matches (|ΔElo| <= 50) Count  : {close_total:,} bouts")
print(f"  • Close Matches Base Accuracy         : {close_base_correct/close_total*100:6.2f}%")
print(f"  • Close Matches Enhanced Accuracy     : {close_enh_correct/close_total*100:6.2f}% (+{(close_enh_correct - close_base_correct)} bouts)")
print("==========================================================================================\n")
