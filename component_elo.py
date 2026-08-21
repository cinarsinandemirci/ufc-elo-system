import os
import json
import math
from datetime import datetime

class ComponentEloEngine:
    def __init__(self, matches_file="matches.json", output_file="fighter_component_elos.json"):
        self.matches_file = matches_file
        self.output_file = output_file
        self.fighters = {}
        self.k_str = 28.0
        self.k_grp = 28.0
        self.k_car = 22.0

    def get_or_init_fighter(self, name):
        if name not in self.fighters:
            self.fighters[name] = {
                'name': name,
                'striking_elo': 1500.0,
                'grappling_elo': 1500.0,
                'cardio_elo': 1500.0,
                'peak_striking_elo': 1500.0,
                'peak_grappling_elo': 1500.0,
                'peak_cardio_elo': 1500.0,
                'total_fights': 0,
                'striking_fights': 0,
                'grappling_fights': 0,
                'history': []
            }
        return self.fighters[name]

    def expected_prob(self, r_a, r_b):
        return 1.0 / (1.0 + 10.0 ** ((r_b - r_a) / 400.0))

    def process_all_matches(self):
        print("[INFO] Processing chronological 3D Component Elo ratings...", flush=True)
        if not os.path.exists(self.matches_file):
            print(f"[ERROR] Matches file '{self.matches_file}' not found.")
            return {}

        with open(self.matches_file, 'r', encoding='utf-8') as f:
            matches = json.load(f)

        # Sort strictly chronologically
        sorted_matches = sorted(matches, key=lambda m: m.get('date', '1970-01-01'))
        print(f"[INFO] Evaluating {len(sorted_matches)} bouts for 3D Component Elo...", flush=True)

        for match in sorted_matches:
            f1_name = match.get('fighter1')
            f2_name = match.get('fighter2')
            winner = match.get('winner')
            res_type = match.get('result_type', 'win')
            method = match.get('method', 'DEC')
            date_str = match.get('date', '')
            event_name = match.get('event_name', '')
            round_str = str(match.get('round', '1'))
            try: round_num = int(round_str)
            except: round_num = 1

            if not f1_name or not f2_name:
                continue

            f1 = self.get_or_init_fighter(f1_name)
            f2 = self.get_or_init_fighter(f2_name)

            f1.setdefault('total_fights', 0)
            f2.setdefault('total_fights', 0)
            f1['total_fights'] += 1
            f2['total_fights'] += 1

            # Extract bout stats
            # Fighter 1 vs Fighter 2 stats
            if winner == f1_name:
                w_kd, l_kd = match.get('winner_kd', 0), match.get('loser_kd', 0)
                w_str, l_str = match.get('winner_str', 0), match.get('loser_str', 0)
                w_td, l_td = match.get('winner_td', 0), match.get('loser_td', 0)
                w_sub, l_sub = match.get('winner_sub', 0), match.get('loser_sub', 0)
                f1_won = True
            elif winner == f2_name:
                w_kd, l_kd = match.get('winner_kd', 0), match.get('loser_kd', 0)
                w_str, l_str = match.get('winner_str', 0), match.get('loser_str', 0)
                w_td, l_td = match.get('winner_td', 0), match.get('loser_td', 0)
                w_sub, l_sub = match.get('winner_sub', 0), match.get('loser_sub', 0)
                f1_won = False
            else:
                # Draw / NC
                w_kd, l_kd = 0, 0
                w_str, l_str = 20, 20
                w_td, l_td = 0, 0
                w_sub, l_sub = 0, 0
                f1_won = None

            # Stats mapped to F1 and F2
            if f1_won is True:
                f1_kd, f2_kd = w_kd, l_kd
                f1_str, f2_str = w_str, l_str
                f1_td, f2_td = w_td, l_td
                f1_sub, f2_sub = w_sub, l_sub
            elif f1_won is False:
                f1_kd, f2_kd = l_kd, w_kd
                f1_str, f2_str = l_str, w_str
                f1_td, f2_td = l_td, w_td
                f1_sub, f2_sub = l_sub, w_sub
            else:
                f1_kd, f2_kd = 0, 0
                f1_str, f2_str = 0, 0
                f1_td, f2_td = 0, 0
                f1_sub, f2_sub = 0, 0

            # -------------------------------------------------------------
            # 1. Striking Component Elo
            # -------------------------------------------------------------
            exp_str_1 = self.expected_prob(f1['striking_elo'], f2['striking_elo'])
            exp_str_2 = 1.0 - exp_str_1

            str_diff = f1_str - f2_str
            kd_diff = f1_kd - f2_kd
            
            # Outcome score for striking in [0, 1]
            if f1_won is True and method == 'KO/TKO':
                s1_actual = 1.0
            elif f1_won is False and method == 'KO/TKO':
                s1_actual = 0.0
            else:
                # Decision / Submission with striking stats
                base_score = 0.5 + (str_diff * 0.005) + (kd_diff * 0.15)
                if f1_won is True: base_score += 0.15
                elif f1_won is False: base_score -= 0.15
                s1_actual = max(0.05, min(0.95, base_score))

            s2_actual = 1.0 - s1_actual

            delta_str_1 = self.k_str * (s1_actual - exp_str_1)
            delta_str_2 = self.k_str * (s2_actual - exp_str_2)

            f1['striking_elo'] += delta_str_1
            f2['striking_elo'] += delta_str_2
            f1['peak_striking_elo'] = max(f1['peak_striking_elo'], f1['striking_elo'])
            f2['peak_striking_elo'] = max(f2['peak_striking_elo'], f2['striking_elo'])

            # -------------------------------------------------------------
            # 2. Grappling Component Elo
            # -------------------------------------------------------------
            exp_grp_1 = self.expected_prob(f1['grappling_elo'], f2['grappling_elo'])
            exp_grp_2 = 1.0 - exp_grp_1

            td_diff = f1_td - f2_td
            sub_diff = f1_sub - f2_sub

            if f1_won is True and method == 'SUB':
                g1_actual = 1.0
            elif f1_won is False and method == 'SUB':
                g1_actual = 0.0
            else:
                g_base = 0.5 + (td_diff * 0.08) + (sub_diff * 0.10)
                if f1_won is True and (f1_td > 0 or f1_sub > 0): g_base += 0.10
                elif f1_won is False and (f2_td > 0 or f2_sub > 0): g_base -= 0.10
                g1_actual = max(0.05, min(0.95, g_base))

            g2_actual = 1.0 - g1_actual

            delta_grp_1 = self.k_grp * (g1_actual - exp_grp_1)
            delta_grp_2 = self.k_grp * (g2_actual - exp_grp_2)

            f1['grappling_elo'] += delta_grp_1
            f2['grappling_elo'] += delta_grp_2
            f1['peak_grappling_elo'] = max(f1['peak_grappling_elo'], f1['grappling_elo'])
            f2['peak_grappling_elo'] = max(f2['peak_grappling_elo'], f2['grappling_elo'])

            # -------------------------------------------------------------
            # 3. Cardio & Durability Component Elo
            # -------------------------------------------------------------
            exp_car_1 = self.expected_prob(f1['cardio_elo'], f2['cardio_elo'])
            exp_car_2 = 1.0 - exp_car_1

            # Cardio evaluates late-round performance (R2+) and distance decisions
            if round_num >= 3:
                if f1_won is True:
                    c1_actual = 0.85 if method != 'DEC' else 0.70
                elif f1_won is False:
                    c1_actual = 0.15 if method != 'DEC' else 0.30
                else:
                    c1_actual = 0.5
            elif round_num == 1:
                # 1st round finishes give less cardio data
                c1_actual = 0.60 if f1_won is True else (0.40 if f1_won is False else 0.50)
            else:
                c1_actual = 0.70 if f1_won is True else (0.30 if f1_won is False else 0.50)

            c2_actual = 1.0 - c1_actual

            delta_car_1 = self.k_car * (c1_actual - exp_car_1)
            delta_car_2 = self.k_car * (c2_actual - exp_car_2)

            f1['cardio_elo'] += delta_car_1
            f2['cardio_elo'] += delta_car_2
            f1['peak_cardio_elo'] = max(f1['peak_cardio_elo'], f1['cardio_elo'])
            f2['peak_cardio_elo'] = max(f2['peak_cardio_elo'], f2['cardio_elo'])

        # Save formatted dictionary
        output_db = {}
        for name, data in self.fighters.items():
            output_db[name.lower()] = {
                'name': data['name'],
                'striking_elo': round(data['striking_elo'], 1),
                'grappling_elo': round(data['grappling_elo'], 1),
                'cardio_elo': round(data['cardio_elo'], 1),
                'peak_striking_elo': round(data['peak_striking_elo'], 1),
                'peak_grappling_elo': round(data['peak_grappling_elo'], 1),
                'peak_cardio_elo': round(data['peak_cardio_elo'], 1),
                'total_fights': data['total_fights']
            }

        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(output_db, f, indent=2, ensure_ascii=False)

        print(f"[SUCCESS] Saved 3D Component Elos for {len(output_db)} fighters to '{self.output_file}'.", flush=True)
        return output_db

if __name__ == '__main__':
    engine = ComponentEloEngine()
    engine.process_all_matches()
