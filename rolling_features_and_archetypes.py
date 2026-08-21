import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

# Load matches, biometrics, rankings, and component elos
with open('matches.json', 'r', encoding='utf-8') as f:
    matches = json.load(f)

with open('fighter_biometrics.json', 'r', encoding='utf-8') as f:
    bio_db = json.load(f)

with open('fighter_rankings.json', 'r', encoding='utf-8') as f:
    rankings = json.load(f)

print(f"[INFO] Processing 25-Year dataset ({len(matches)} bouts) for Phase 1 Feature Engineering...")

# High altitude event locations
ALTITUDE_KEYWORDS = ['salt lake city', 'denver', 'mexico', 'albuquerque', 'bogota', 'utah', 'colorado']

def parse_date(d_str):
    try:
        return datetime.strptime(d_str, '%Y-%m-%d')
    except Exception:
        return datetime(2000, 1, 1)

sorted_matches = sorted(matches, key=lambda m: parse_date(m.get('date', '2000-01-01')))

fighter_fight_history = defaultdict(list)
bout_features_list = []

for m in sorted_matches:
    f1_name = m.get('fighter1', '')
    f2_name = m.get('fighter2', '')
    if not f1_name or not f2_name:
        continue

    m_date = m.get('date', '2000-01-01')
    event_name = m.get('event_name', '').lower()
    
    # Environmental tags
    is_apex = 1 if ('apex' in event_name or 'vegas' in event_name and parse_date(m_date) >= datetime(2020, 5, 1) and 'ufc 2' not in event_name and 'ufc 3' not in event_name) else 0
    is_high_alt = 1 if any(alt in event_name for alt in ALTITUDE_KEYWORDS) else 0
    
    winner = m.get('winner', '')
    is_f1_winner = (winner == f1_name)
    
    # Parse fight statistics
    w_str = float(m.get('winner_str', 25.0) or 25.0)
    l_str = float(m.get('loser_str', 20.0) or 20.0)
    w_td = float(m.get('winner_td', 1.0) or 1.0)
    l_td = float(m.get('loser_td', 0.0) or 0.0)
    w_kd = float(m.get('winner_kd', 0.0) or 0.0)
    l_kd = float(m.get('loser_kd', 0.0) or 0.0)
    
    f1_str = w_str if is_f1_winner else l_str
    f2_str = l_str if is_f1_winner else w_str
    f1_td = w_td if is_f1_winner else l_td
    f2_td = l_td if is_f1_winner else w_td
    f1_kd = w_kd if is_f1_winner else l_kd
    f2_kd = l_kd if is_f1_winner else w_kd
    
    try:
        r_num = int(m.get('round', 3) or 3)
    except Exception:
        r_num = 3
    tot_time_min = max(1.0, float(r_num) * 4.5)

    def compute_ewma_stats(history, window=4):
        if not history:
            return {
                'slpm': 3.5,
                'sapm': 3.5,
                'str_acc': 0.45,
                'str_def': 0.55,
                'td_avg_15m': 1.5,
                'kd_rate': 0.2,
                'recent_damage_index': 3.5,
                'win_streak_recent': 0,
                'finish_rate_recent': 0.3
            }
        recent = history[-window:]
        weights = [math.exp(0.5 * i) for i in range(len(recent))]
        tot_w = sum(weights)
        
        slpm = sum(r['slpm'] * w for r, w in zip(recent, weights)) / tot_w
        sapm = sum(r['sapm'] * w for r, w in zip(recent, weights)) / tot_w
        str_acc = sum(r['str_acc'] * w for r, w in zip(recent, weights)) / tot_w
        str_def = sum(r['str_def'] * w for r, w in zip(recent, weights)) / tot_w
        td_avg = sum(r['td_avg'] * w for r, w in zip(recent, weights)) / tot_w
        kd = sum(r['kd'] * w for r, w in zip(recent, weights)) / tot_w
        wins = sum(1 for r in recent if r.get('won', False))
        finishes = sum(1 for r in recent if r.get('finish', False))
        
        return {
            'slpm': round(slpm, 2),
            'sapm': round(sapm, 2),
            'str_acc': round(str_acc, 3),
            'str_def': round(str_def, 3),
            'td_avg_15m': round(td_avg, 2),
            'kd_rate': round(kd, 2),
            'recent_damage_index': round(sapm * (1.0 - max(0.2, str_def)), 2),
            'win_streak_recent': wins,
            'finish_rate_recent': round(finishes / max(1, len(recent)), 2)
        }

    f1_pre = compute_ewma_stats(fighter_fight_history[f1_name])
    f2_pre = compute_ewma_stats(fighter_fight_history[f2_name])
    
    y = 1 if is_f1_winner else (0 if winner == f2_name else 0.5)
    method_str = m.get('method', 'U-DEC').upper()
    is_finish = ('KO' in method_str or 'TKO' in method_str or 'SUB' in method_str)
    
    bout_features_list.append({
        'date': m_date,
        'fighter1': f1_name,
        'fighter2': f2_name,
        'winner': winner,
        'target': y,
        'method': method_str,
        'round': r_num,
        'is_finish': 1 if is_finish else 0,
        'is_apex': is_apex,
        'is_high_altitude': is_high_alt,
        'f1_rolling': f1_pre,
        'f2_rolling': f2_pre
    })
    
    # Update post fight
    fighter_fight_history[f1_name].append({
        'slpm': (f1_str / tot_time_min),
        'sapm': (f2_str / tot_time_min),
        'str_acc': min(0.9, f1_str / max(1.0, f1_str + 20.0)),
        'str_def': max(0.2, 1.0 - (f2_str / max(1.0, f2_str + 20.0))),
        'td_avg': (f1_td / tot_time_min) * 15.0,
        'kd': f1_kd,
        'won': is_f1_winner,
        'finish': is_finish if is_f1_winner else False
    })
    
    fighter_fight_history[f2_name].append({
        'slpm': (f2_str / tot_time_min),
        'sapm': (f1_str / tot_time_min),
        'str_acc': min(0.9, f2_str / max(1.0, f2_str + 20.0)),
        'str_def': max(0.2, 1.0 - (f1_str / max(1.0, f1_str + 20.0))),
        'td_avg': (f2_td / tot_time_min) * 15.0,
        'kd': f2_kd,
        'won': (winner == f2_name),
        'finish': is_finish if (winner == f2_name) else False
    })

# Compute current state for all fighters
fighter_rolling_db = {}
for f_name, hist in fighter_fight_history.items():
    fighter_rolling_db[f_name.lower()] = compute_ewma_stats(hist, window=4)

# =========================================================================
# 6-ARCHETYPE STYLISTIC CLASSIFICATION
# =========================================================================
archetypes_db = {}
archetype_counts = defaultdict(int)

for f in rankings:
    name = f['name']
    key = name.lower()
    bio = bio_db.get(key, {})
    roll = fighter_rolling_db.get(key, {})
    
    tdd = bio.get('tactical', {}).get('td_def_pct', 65.0) if bio.get('tactical') else 65.0
    td_avg = roll.get('td_avg_15m', 1.5)
    slpm = roll.get('slpm', 3.5)
    s_def = roll.get('str_def', 0.55)
    kd = roll.get('kd_rate', 0.2)
    methods = f.get('methods', {})
    sub_wins = methods.get('SUB_win', 0)
    ko_wins = methods.get('KO/TKO_win', 0)
    total_w = max(1, f.get('wins', 1))
    
    sub_ratio = sub_wins / total_w
    ko_ratio = ko_wins / total_w
    
    if td_avg >= 2.5:
        archetype = 'Pressure Wrestler'
    elif sub_ratio >= 0.35 or (sub_wins >= 4 and td_avg >= 1.2):
        archetype = 'Submission Hunter'
    elif tdd >= 75.0 and (ko_ratio >= 0.35 or kd >= 0.4):
        archetype = 'Sprawl-and-Brawler'
    elif slpm >= 4.5 and s_def <= 0.55:
        archetype = 'Inside Pressure Boxer'
    elif td_avg >= 1.5 and slpm <= 3.2:
        archetype = 'Clinch Grinder'
    else:
        archetype = 'Distance Out-Fighter'
        
    archetypes_db[key] = {
        'name': name,
        'archetype': archetype,
        'rolling_slpm': roll.get('slpm', 3.5),
        'rolling_sapm': roll.get('sapm', 3.5),
        'rolling_tdd': round(tdd, 1),
        'rolling_td_avg': roll.get('td_avg_15m', 1.5),
        'rolling_damage_index': roll.get('recent_damage_index', 1.5),
        'recent_form': f"{roll.get('win_streak_recent', 0)}W in last 4"
    }
    archetype_counts[archetype] += 1

print("\n=== 6-ARCHETYPE DISTRIBUTION ACROSS 2,540 FIGHTERS ===")
for arch, count in sorted(archetype_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"  • {arch:24s}: {count:4d} fighters ({count / len(rankings) * 100:.1f}%)")

with open('fighter_rolling_features.json', 'w', encoding='utf-8') as f:
    json.dump(fighter_rolling_db, f, indent=2, ensure_ascii=False)

with open('fighter_archetypes.json', 'w', encoding='utf-8') as f:
    json.dump(archetypes_db, f, indent=2, ensure_ascii=False)

with open('bout_rolling_features.json', 'w', encoding='utf-8') as f:
    json.dump(bout_features_list, f, indent=2, ensure_ascii=False)

print(f"\n[OK] Phase 1 Complete! Saved rolling EWMA features and archetypes for {len(archetypes_db)} fighters and {len(bout_features_list)} bouts.")
