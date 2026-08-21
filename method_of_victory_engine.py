import json
import math
import os
import sys
from collections import defaultdict
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss

sys.stdout.reconfigure(encoding='utf-8')

print("==========================================================================================")
print("  PHASE 3: MULTI-TARGET METHOD OF VICTORY & ROUND PROP ENGINE (KO / SUB / DEC / OVER-UNDER)")
print("==========================================================================================")

with open('bout_rolling_features.json', 'r', encoding='utf-8') as f:
    bouts = json.load(f)

with open('fighter_rankings.json', 'r', encoding='utf-8') as f:
    rankings = json.load(f)
rank_db = {f['name'].lower(): f for f in rankings}

with open('fighter_biometrics.json', 'r', encoding='utf-8') as f:
    bio_db = json.load(f)

with open('fighter_component_elos.json', 'r', encoding='utf-8') as f:
    comp_db = json.load(f)

with open('fighter_archetypes.json', 'r', encoding='utf-8') as f:
    arch_db = json.load(f)

# Historical division finish baseline rates
DIVISION_FINISH_RATES = {
    'Heavyweight': {'ko': 0.52, 'sub': 0.18, 'dec': 0.30},
    'Light Heavyweight': {'ko': 0.45, 'sub': 0.18, 'dec': 0.37},
    'Middleweight': {'ko': 0.40, 'sub': 0.20, 'dec': 0.40},
    'Welterweight': {'ko': 0.33, 'sub': 0.20, 'dec': 0.47},
    'Lightweight': {'ko': 0.32, 'sub': 0.22, 'dec': 0.46},
    'Featherweight': {'ko': 0.28, 'sub': 0.20, 'dec': 0.52},
    'Bantamweight': {'ko': 0.25, 'sub': 0.21, 'dec': 0.54},
    'Flyweight': {'ko': 0.22, 'sub': 0.22, 'dec': 0.56},
    "Women's Strawweight": {'ko': 0.16, 'sub': 0.18, 'dec': 0.66},
    "Women's Flyweight": {'ko': 0.18, 'sub': 0.19, 'dec': 0.63},
    "Women's Bantamweight": {'ko': 0.24, 'sub': 0.22, 'dec': 0.54}
}

class MethodOfVictoryPredictor:
    def __init__(self):
        self.rank_db = rank_db
        self.bio_db = bio_db
        self.comp_db = comp_db
        self.arch_db = arch_db

    def predict_detailed_props(self, f1_name, f2_name, f1_win_prob, weight_class='Lightweight'):
        k1 = f1_name.lower()
        k2 = f2_name.lower()

        f1 = self.rank_db.get(k1, {'methods': {'KO/TKO_win': 2, 'SUB_win': 2, 'DEC_win': 2}, 'wins': 6, 'losses': 2})
        f2 = self.rank_db.get(k2, {'methods': {'KO/TKO_win': 2, 'SUB_win': 2, 'DEC_win': 2}, 'wins': 6, 'losses': 2})
        b1 = self.bio_db.get(k1, {})
        b2 = self.bio_db.get(k2, {})
        c1 = self.comp_db.get(k1, {'striking_elo': 1500.0, 'grappling_elo': 1500.0, 'cardio_elo': 1500.0})
        c2 = self.comp_db.get(k2, {'striking_elo': 1500.0, 'grappling_elo': 1500.0, 'cardio_elo': 1500.0})
        arch1 = self.arch_db.get(k1, {}).get('archetype', 'Distance Out-Fighter')
        arch2 = self.arch_db.get(k2, {}).get('archetype', 'Distance Out-Fighter')

        div_base = DIVISION_FINISH_RATES.get(weight_class, {'ko': 0.35, 'sub': 0.20, 'dec': 0.45})

        m1 = f1.get('methods', {})
        m2 = f2.get('methods', {})
        w1 = max(1, f1.get('wins', 1))
        w2 = max(1, f2.get('wins', 1))

        # Fighter 1 method distribution
        f1_ko_rate = (m1.get('KO/TKO_win', 0) / w1) * 0.6 + div_base['ko'] * 0.4
        f1_sub_rate = (m1.get('SUB_win', 0) / w1) * 0.6 + div_base['sub'] * 0.4
        f1_dec_rate = (m1.get('DEC_win', 0) / w1) * 0.6 + div_base['dec'] * 0.4

        # Fighter 2 method distribution
        f2_ko_rate = (m2.get('KO/TKO_win', 0) / w2) * 0.6 + div_base['ko'] * 0.4
        f2_sub_rate = (m2.get('SUB_win', 0) / w2) * 0.6 + div_base['sub'] * 0.4
        f2_dec_rate = (m2.get('DEC_win', 0) / w2) * 0.6 + div_base['dec'] * 0.4

        # Vulnerability / Chin & Sub defense adjustments
        chin2_deg = b2.get('chin_degradation_pct', 0.0) / 100.0
        chin1_deg = b1.get('chin_degradation_pct', 0.0) / 100.0

        f1_ko_rate *= (1.0 + chin2_deg * 0.5)
        f2_ko_rate *= (1.0 + chin1_deg * 0.5)

        # Grappling & Striking Elo skew
        if c1['striking_elo'] - c2['striking_elo'] > 60:
            f1_ko_rate *= 1.2
        if c1['grappling_elo'] - c2['grappling_elo'] > 60:
            f1_sub_rate *= 1.25

        if c2['striking_elo'] - c1['striking_elo'] > 60:
            f2_ko_rate *= 1.2
        if c2['grappling_elo'] - c1['grappling_elo'] > 60:
            f2_sub_rate *= 1.25

        # Normalize F1 methods so sum == 1
        s1 = f1_ko_rate + f1_sub_rate + f1_dec_rate
        f1_ko_norm = f1_ko_rate / s1
        f1_sub_norm = f1_sub_rate / s1
        f1_dec_norm = f1_dec_rate / s1

        # Normalize F2 methods so sum == 1
        s2 = f2_ko_rate + f2_sub_rate + f2_dec_rate
        f2_ko_norm = f2_ko_rate / s2
        f2_sub_norm = f2_sub_rate / s2
        f2_dec_norm = f2_dec_rate / s2

        f2_win_prob = 1.0 - f1_win_prob

        # Joint 6-way outcome probabilities
        p_f1_ko = round(f1_win_prob * f1_ko_norm, 4)
        p_f1_sub = round(f1_win_prob * f1_sub_norm, 4)
        p_f1_dec = round(f1_win_prob * f1_dec_norm, 4)

        p_f2_ko = round(f2_win_prob * f2_ko_norm, 4)
        p_f2_sub = round(f2_win_prob * f2_sub_norm, 4)
        p_f2_dec = round(f2_win_prob * f2_dec_norm, 4)

        # Round Props (Over/Under & Distance)
        total_finish_prob = (p_f1_ko + p_f1_sub + p_f2_ko + p_f2_sub)
        goes_distance_prob = round(p_f1_dec + p_f2_dec, 4)

        # Early finish estimation (KO/Sub in Round 1/2)
        over_1_5_prob = round(1.0 - (total_finish_prob * 0.42), 4)
        over_2_5_prob = round(1.0 - (total_finish_prob * 0.72), 4)

        return {
            'f1_name': f1_name,
            'f2_name': f2_name,
            'f1_win_prob': round(f1_win_prob * 100, 1),
            'f2_win_prob': round(f2_win_prob * 100, 1),
            'f1_methods': {
                'ko_tko': round(p_f1_ko * 100, 1),
                'submission': round(p_f1_sub * 100, 1),
                'decision': round(p_f1_dec * 100, 1)
            },
            'f2_methods': {
                'ko_tko': round(p_f2_ko * 100, 1),
                'submission': round(p_f2_sub * 100, 1),
                'decision': round(p_f2_dec * 100, 1)
            },
            'round_props': {
                'over_1_5_prob': round(over_1_5_prob * 100, 1),
                'under_1_5_prob': round((1.0 - over_1_5_prob) * 100, 1),
                'over_2_5_prob': round(over_2_5_prob * 100, 1),
                'under_2_5_prob': round((1.0 - over_2_5_prob) * 100, 1),
                'goes_distance_prob': round(goes_distance_prob * 100, 1),
                'finish_inside_distance_prob': round(total_finish_prob * 100, 1)
            },
            'f1_archetype': arch1,
            'f2_archetype': arch2
        }

if __name__ == '__main__':
    predictor = MethodOfVictoryPredictor()
    sample = predictor.predict_detailed_props("Islam Makhachev", "Arman Tsarukyan", 0.645, "Lightweight")
    print("\n=== SAMPLE MATCHUP PROPS: Islam Makhachev vs Arman Tsarukyan ===")
    print(json.dumps(sample, indent=2))
    
    with open('method_of_victory_sample.json', 'w', encoding='utf-8') as f:
        json.dump(sample, f, indent=2)
    print("\n[OK] Phase 3 Method of Victory engine ready!")
