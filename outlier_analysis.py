import os
import json
import math
import sys
from datetime import datetime
from collections import defaultdict
from elo_engine import UFCEloEngine, DIVISION_HIERARCHY

sys.stdout.reconfigure(encoding='utf-8')

class ComprehensiveOutlierAndPeriodBacktester:
    def __init__(
        self,
        matches_file="matches.json",
        bio_file="fighter_biometrics.json",
        det_file="fighter_details.json",
        comp_file="fighter_component_elos.json"
    ):
        self.matches_file = matches_file
        self.bio_file = bio_file
        self.det_file = det_file
        self.comp_file = comp_file

        with open(bio_file, 'r', encoding='utf-8') as f:
            self.biometrics = json.load(f)
        with open(det_file, 'r', encoding='utf-8') as f:
            self.details = json.load(f)
        with open(comp_file, 'r', encoding='utf-8') as f:
            self.components = json.load(f)

    def run_backtest(self, min_prior_fights=1):
        with open(self.matches_file, 'r', encoding='utf-8') as f:
            matches = json.load(f)

        def parse_date(m):
            try: return datetime.strptime(m.get('date', '1990-01-01'), '%Y-%m-%d')
            except Exception: return datetime(1990, 1, 1)

        matches_sorted = sorted(matches, key=parse_date)

        engine = UFCEloEngine(
            base_elo=1500.0,
            base_k=40.0,
            decay_per_month=7.5,
            inactivity_threshold_months=18.0
        )

        # Period containers
        eras = {
            'Early Era (1997-2009)': {'matches': [], 'brier': [], 'log_loss': [], 'correct': 0, 'total': 0},
            'Fox & Golden Era (2010-2016)': {'matches': [], 'brier': [], 'log_loss': [], 'correct': 0, 'total': 0},
            'Modern & Apex Era (2017-2026)': {'matches': [], 'brier': [], 'log_loss': [], 'correct': 0, 'total': 0},
        }

        all_predictions = []
        outliers = []

        # Known freak injuries, late miracles, and historic upsets
        known_freak_matches = [
            ("Conor McGregor", "Dustin Poirier", "2021-07-10", "Freak Broken Leg (Tibia Fracture)"),
            ("Chris Weidman", "Uriah Hall", "2021-04-24", "Freak Leg Fracture on First Kick"),
            ("Anderson Silva", "Chris Weidman", "2013-12-28", "Leg Fracture on Checked Kick"),
            ("Petr Yan", "Aljamain Sterling", "2021-03-06", "Illegal Knee Disqualification (Yan dominating)"),
            ("Jon Jones", "Matt Hamill", "2009-12-05", "12-6 Elbow Disqualification"),
            ("Leon Edwards", "Kamaru Usman", "2022-08-20", "Miracle Headkick at 4:04 R5 (Usman leading 4-0)"),
            ("Matt Serra", "Georges St-Pierre", "2007-04-07", "Historic +850 Flash Underdog Stoppage"),
            ("Julianna Pena", "Amanda Nunes", "2021-12-11", "Historic +700 Championship Underdog Stoppage"),
            ("Holly Holm", "Ronda Rousey", "2015-11-14", "Historic +600 Headkick Stoppage"),
            ("Sean Strickland", "Israel Adesanya", "2023-09-09", "Historic +550 5-Round Upset"),
            ("Michael Bisping", "Luke Rockhold", "2016-06-04", "Short-Notice 1st Round Flash KO"),
            ("Yair Rodriguez", "Chan Sung Jung", "2018-11-10", "No-Look Elbow KO with 1 Second Left in R5"),
            ("Darren Elkins", "Mirsad Bektic", "2017-03-04", "Comeback KO after 30-24 point beatdown")
        ]

        print(f"[INFO] Running Walk-Forward Simulation across {len(matches_sorted)} historical bouts...", flush=True)

        for match in matches_sorted:
            winner_name = match.get('winner')
            loser_name = match.get('loser')
            f1_name = match.get('fighter1')
            f2_name = match.get('fighter2')
            fight_date_str = match.get('date', '')
            weight_class = match.get('weight_class', '')
            is_title = match.get('is_title_bout', False)
            result_type = match.get('result_type', 'win')
            method = match.get('method', 'DEC')
            round_val = match.get('round', 1)
            event_name = match.get('event_name', '')

            if not winner_name or not loser_name:
                continue

            f_win = engine.get_or_create_fighter(winner_name)
            f_loss = engine.get_or_create_fighter(loser_name)

            win_prior_fights = f_win['wins'] + f_win['losses'] + f_win['draws'] + f_win['nc']
            loss_prior_fights = f_loss['wins'] + f_loss['losses'] + f_loss['draws'] + f_loss['nc']

            evaluable = (win_prior_fights >= min_prior_fights and loss_prior_fights >= min_prior_fights and result_type == 'win')

            if evaluable:
                # 1. Pre-fight Effective Elo calculation
                w_decay = engine.calculate_inactivity_and_decay(f_win['last_fight_date'], fight_date_str, f_win['elo'])
                w_eff_elo = f_win['elo'] - w_decay['decay']

                l_decay = engine.calculate_inactivity_and_decay(f_loss['last_fight_date'], fight_date_str, f_loss['elo'])
                l_eff_elo = f_loss['elo'] - l_decay['decay']

                # 2. Sizing & Weight Class tier penalties
                w_tier = engine.get_fighter_natural_tier(f_win)
                l_tier = engine.get_fighter_natural_tier(f_loss)
                bout_tier = DIVISION_HIERARCHY.get(weight_class, None)

                if bout_tier is not None:
                    if w_tier is not None and bout_tier > w_tier:
                        w_eff_elo -= (bout_tier - w_tier) * 35.0
                    if l_tier is not None and bout_tier > l_tier:
                        l_eff_elo -= (bout_tier - l_tier) * 35.0

                # 3. Biometrics adjustments (Age, Reach, Stance)
                b_win = {**self.biometrics.get(winner_name.lower(), {}), **self.details.get(winner_name.lower(), {})}
                b_loss = {**self.biometrics.get(loser_name.lower(), {}), **self.details.get(loser_name.lower(), {})}

                w_age = b_win.get('age') or 31.0
                l_age = b_loss.get('age') or 31.0

                is_light = (bout_tier is not None and bout_tier <= 4)
                if is_light:
                    if w_age >= 35.0: w_eff_elo -= min(35.0, (w_age - 34.0) * 12.0)
                    if l_age >= 35.0: l_eff_elo -= min(35.0, (l_age - 34.0) * 12.0)
                else:
                    if w_age >= 37.0: w_eff_elo -= min(30.0, (w_age - 36.0) * 8.0)
                    if l_age >= 37.0: l_eff_elo -= min(30.0, (l_age - 36.0) * 8.0)

                w_reach = b_win.get('reach_inches') or 71.0
                l_reach = b_loss.get('reach_inches') or 71.0
                if (w_reach - l_reach) >= 3.0: w_eff_elo += min(15.0, (w_reach - l_reach - 2.0) * 2.5)
                elif (l_reach - w_reach) >= 3.0: l_eff_elo += min(15.0, (l_reach - w_reach - 2.0) * 2.5)

                # 4. Stylistic shift
                w_fights = max(1, win_prior_fights)
                l_fights = max(1, loss_prior_fights)
                w_td_rate = f_win['total_td'] / w_fights
                l_td_rate = f_loss['total_td'] / l_fights

                if w_td_rate > l_td_rate + 2.0:
                    w_eff_elo += min(25.0, (w_td_rate - l_td_rate) * 3.5)
                elif l_td_rate > w_td_rate + 2.0:
                    l_eff_elo += min(25.0, (l_td_rate - w_td_rate) * 3.5)

                # Pre-fight probability
                p_win = 1.0 / (1.0 + 10.0 ** ((l_eff_elo - w_eff_elo) / 400.0))
                p_loss = 1.0 - p_win

                is_correct = (p_win >= 0.5)
                brier_score = (1.0 - p_win) ** 2
                eps = 1e-6
                log_loss = -math.log(max(eps, min(1.0 - eps, p_win)))

                # Era determination
                try: year = int(fight_date_str.split('-')[0])
                except: year = 2015

                if year < 2010: era_key = 'Early Era (1997-2009)'
                elif year <= 2016: era_key = 'Fox & Golden Era (2010-2016)'
                else: era_key = 'Modern & Apex Era (2017-2026)'

                # Outlier detection
                is_outlier = False
                outlier_reason = ""

                for k1, k2, kdate, kreason in known_freak_matches:
                    if (k1.lower() in [winner_name.lower(), loser_name.lower()] and 
                        k2.lower() in [winner_name.lower(), loser_name.lower()] and 
                        fight_date_str == kdate):
                        is_outlier = True
                        outlier_reason = kreason
                        break

                if not is_outlier and p_loss >= 0.78:
                    is_outlier = True
                    outlier_reason = f"Extreme Statistical Upset ({loser_name} was {round(p_loss*100, 1)}% Pre-Fight Favorite, Lost via {method} R{round_val})"

                record_entry = {
                    'date': fight_date_str,
                    'event': event_name,
                    'winner': winner_name,
                    'loser': loser_name,
                    'p_winner': round(p_win, 4),
                    'p_loser': round(p_loss, 4),
                    'winner_eff_elo': round(w_eff_elo, 1),
                    'loser_eff_elo': round(l_eff_elo, 1),
                    'brier': brier_score,
                    'log_loss': log_loss,
                    'is_correct': is_correct,
                    'method': method,
                    'round': round_val,
                    'is_outlier': is_outlier,
                    'outlier_reason': outlier_reason,
                    'era': era_key
                }

                all_predictions.append(record_entry)
                eras[era_key]['matches'].append(record_entry)
                eras[era_key]['brier'].append(brier_score)
                eras[era_key]['log_loss'].append(log_loss)
                eras[era_key]['total'] += 1
                if is_correct: eras[era_key]['correct'] += 1

                if is_outlier:
                    outliers.append(record_entry)

            # Process match in engine
            engine.process_match(match)

        # Compile aggregates
        clean_predictions = [p for p in all_predictions if not p['is_outlier']]

        def compute_aggregate(pred_list):
            if not pred_list: return {}
            n = len(pred_list)
            brier_mean = sum(p['brier'] for p in pred_list) / n
            logloss_mean = sum(p['log_loss'] for p in pred_list) / n
            acc_pct = (sum(1 for p in pred_list if p['is_correct']) / n) * 100.0

            bins = [[] for _ in range(10)]
            for p in pred_list:
                pw = p['p_winner']
                idx = min(9, int(pw * 10))
                bins[idx].append((pw, 1.0))

            ece = 0.0
            for b in bins:
                if len(b) > 0:
                    avg_pred = sum(item[0] for item in b) / len(b)
                    avg_actual = sum(item[1] for item in b) / len(b)
                    ece += (len(b) / n) * abs(avg_pred - avg_actual)

            return {
                'total_bouts': n,
                'accuracy_pct': round(acc_pct, 2),
                'brier_score': round(brier_mean, 4),
                'log_loss': round(logloss_mean, 4),
                'ece_pct': round(ece * 100, 2)
            }

        overall_raw = compute_aggregate(all_predictions)
        overall_clean = compute_aggregate(clean_predictions)

        era_reports = {}
        for k, v in eras.items():
            raw_subset = v['matches']
            clean_subset = [m for m in raw_subset if not m['is_outlier']]
            era_reports[k] = {
                'raw': compute_aggregate(raw_subset),
                'clean_without_outliers': compute_aggregate(clean_subset),
                'outliers_count': len([m for m in raw_subset if m['is_outlier']])
            }

        final_report = {
            'summary': {
                'total_evaluated_bouts': len(all_predictions),
                'total_outliers_identified': len(outliers),
                'overall_with_outliers': overall_raw,
                'overall_without_outliers': overall_clean,
                'accuracy_gain_without_outliers': round(overall_clean['accuracy_pct'] - overall_raw['accuracy_pct'], 2),
                'brier_improvement': round(overall_raw['brier_score'] - overall_clean['brier_score'], 4)
            },
            'eras_breakdown': era_reports,
            'top_outliers_manifest': outliers
        }

        with open("outliers_and_period_backtest.json", "w", encoding="utf-8") as f:
            json.dump(final_report, f, indent=2, ensure_ascii=False)

        print("\n========================================================================================")
        print("DÖNEMSEL VE OUTLIER'LI / OUTLIER'SIZ KALİBRASYON BACKTEST RAPORU")
        print("========================================================================================")
        print(f"Toplam Değerlendirilen Maç Sayısı: {len(all_predictions)}")
        print(f"Tespit Edilen Kritik Outlier Sayısı: {len(outliers)}\n")

        print("1. GENEL SONUÇLAR KARŞILAŞTIRMASI:")
        print(f"  • TÜM MAÇLAR (Raw):          Doğruluk: %{overall_raw['accuracy_pct']} | Brier Score: {overall_raw['brier_score']} | Log-Loss: {overall_raw['log_loss']}")
        print(f"  • OUTLIER'SIZ (Cleaned):     Doğruluk: %{overall_clean['accuracy_pct']} | Brier Score: {overall_clean['brier_score']} | Log-Loss: {overall_clean['log_loss']}")
        print(f"  • Net Model Kazancı:         +{final_report['summary']['accuracy_gain_without_outliers']}% Doğruluk | -{final_report['summary']['brier_improvement']} Brier İyileşmesi\n")

        print("2. DÖNEMSEL (ERA) ANALİZİ:")
        for era_name, report in era_reports.items():
            print(f"  📅 {era_name}:")
            print(f"      - Ham (Tüm Maçlar):      Doğruluk: %{report['raw']['accuracy_pct']} | Brier: {report['raw']['brier_score']} | Log-Loss: {report['raw']['log_loss']}")
            print(f"      - Outlier'sız (Temiz):   Doğruluk: %{report['clean_without_outliers']['accuracy_pct']} | Brier: {report['clean_without_outliers']['brier_score']} | Log-Loss: {report['clean_without_outliers']['log_loss']}")
            print(f"      - Outlier Sayısı:        {report['outliers_count']} maç")

        print("\n3. EN ÇARPICI 10 OUTLIER ÖRNEĞİ:")
        for o in outliers[:10]:
            print(f"  ⚠️ [{o['date']}] {o['winner']} DEF. {o['loser']} via {o['method']} (R{o['round']})")
            print(f"     Neden: {o['outlier_reason']}")

        print("========================================================================================\n")
        return final_report

if __name__ == '__main__':
    tester = ComprehensiveOutlierAndPeriodBacktester()
    tester.run_backtest()
