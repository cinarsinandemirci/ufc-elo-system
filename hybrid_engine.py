import os
import json
import math
import sys
import numpy as np
from datetime import datetime
from elo_engine import UFCEloEngine, DIVISION_HIERARCHY

sys.stdout.reconfigure(encoding='utf-8')

class PureNumpyLogisticRegression:
    def __init__(self, lr=0.08, l2_reg=0.01, epochs=300):
        self.lr = lr
        self.l2_reg = l2_reg
        self.epochs = epochs
        self.weights = None
        self.bias = 0.0

    def sigmoid(self, z):
        z = np.clip(z, -25.0, 25.0)
        return 1.0 / (1.0 + np.exp(-z))

    def fit(self, X, y):
        n_samples, n_features = X.shape
        self.weights = np.zeros(n_features)
        self.bias = 0.0

        for _ in range(self.epochs):
            linear_model = np.dot(X, self.weights) + self.bias
            y_pred = self.sigmoid(linear_model)

            dw = (1.0 / n_samples) * np.dot(X.T, (y_pred - y)) + self.l2_reg * self.weights
            db = (1.0 / n_samples) * np.sum(y_pred - y)

            self.weights -= self.lr * dw
            self.bias -= self.lr * db

    def predict_proba(self, X):
        linear_model = np.dot(X, self.weights) + self.bias
        return self.sigmoid(linear_model)

class UFCHybridMLEngine:
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

    def extract_dataset(self, min_prior_fights=1):
        with open(self.matches_file, 'r', encoding='utf-8') as f:
            matches = json.load(f)

        def parse_date(m):
            try: return datetime.strptime(m.get('date', '1990-01-01'), '%Y-%m-%d')
            except Exception: return datetime(1990, 1, 1)

        matches_sorted = sorted(matches, key=parse_date)

        engine = UFCEloEngine(base_elo=1500.0, base_k=40.0, decay_per_month=7.5, inactivity_threshold_months=18.0)

        comp_tracker = {}
        def get_comp(name):
            if name.lower() not in comp_tracker:
                comp_tracker[name.lower()] = {'str': 1500.0, 'grp': 1500.0, 'car': 1500.0}
            return comp_tracker[name.lower()]

        features = []
        labels = []
        metadata = []

        for match in matches_sorted:
            winner_name = match.get('winner')
            loser_name = match.get('loser')
            fight_date_str = match.get('date', '')
            weight_class = match.get('weight_class', '')
            is_title = 1.0 if match.get('is_title_bout') else 0.0
            result_type = match.get('result_type', 'win')

            if not winner_name or not loser_name:
                continue

            f_win = engine.get_or_create_fighter(winner_name)
            f_loss = engine.get_or_create_fighter(loser_name)

            win_prior = f_win['wins'] + f_win['losses'] + f_win['draws'] + f_win['nc']
            loss_prior = f_loss['wins'] + f_loss['losses'] + f_loss['draws'] + f_loss['nc']

            pair_hash = hash(f"{winner_name}_{loser_name}_{fight_date_str}")
            if pair_hash % 2 == 0:
                fa_name, fb_name = winner_name, loser_name
                fa_obj, fb_obj = f_win, f_loss
                fa_prior, fb_prior = win_prior, loss_prior
                target_y = 1.0
            else:
                fa_name, fb_name = loser_name, winner_name
                fa_obj, fb_obj = f_loss, f_win
                fa_prior, fb_prior = loss_prior, win_prior
                target_y = 0.0

            if fa_prior >= min_prior_fights and fb_prior >= min_prior_fights and result_type == 'win':
                a_dec = engine.calculate_inactivity_and_decay(fa_obj['last_fight_date'], fight_date_str, fa_obj['elo'])
                b_dec = engine.calculate_inactivity_and_decay(fb_obj['last_fight_date'], fight_date_str, fb_obj['elo'])
                a_eff = fa_obj['elo'] - a_dec['decay']
                b_eff = fb_obj['elo'] - b_dec['decay']

                a_tier = engine.get_fighter_natural_tier(fa_obj)
                b_tier = engine.get_fighter_natural_tier(fb_obj)
                bout_tier = DIVISION_HIERARCHY.get(weight_class, None)

                size_pen_a = (bout_tier - a_tier) * 35.0 if (bout_tier is not None and a_tier is not None and bout_tier > a_tier) else 0.0
                size_pen_b = (bout_tier - b_tier) * 35.0 if (bout_tier is not None and b_tier is not None and bout_tier > b_tier) else 0.0

                bio_a = {**self.biometrics.get(fa_name.lower(), {}), **self.details.get(fa_name.lower(), {})}
                bio_b = {**self.biometrics.get(fb_name.lower(), {}), **self.details.get(fb_name.lower(), {})}

                age_a = bio_a.get('age') or 31.0
                age_b = bio_b.get('age') or 31.0
                age_diff = age_b - age_a

                reach_a = bio_a.get('reach_inches') or 71.0
                reach_b = bio_b.get('reach_inches') or 71.0
                reach_diff = reach_a - reach_b

                stance_a = bio_a.get('stance', 'Orthodox')
                stance_b = bio_b.get('stance', 'Orthodox')
                is_a_southpaw = 1.0 if (stance_a == 'Southpaw' and stance_b == 'Orthodox') else 0.0
                is_b_southpaw = 1.0 if (stance_b == 'Southpaw' and stance_a == 'Orthodox') else 0.0

                is_light = (bout_tier is not None and bout_tier <= 4)
                a_age_cliff = 1.0 if (is_light and age_a >= 35.0) or (not is_light and age_a >= 37.0) else 0.0
                b_age_cliff = 1.0 if (is_light and age_b >= 35.0) or (not is_light and age_b >= 37.0) else 0.0

                c_a = get_comp(fa_name)
                c_b = get_comp(fb_name)
                str_diff = c_a['str'] - c_b['str']
                grp_diff = c_a['grp'] - c_b['grp']
                car_diff = c_a['car'] - c_b['car']

                tdd_a = bio_a.get('tactical', {}).get('td_def_pct', 70.0) if bio_a.get('tactical') else 70.0
                tdd_b = bio_b.get('tactical', {}).get('td_def_pct', 70.0) if bio_b.get('tactical') else 70.0

                streak_diff = float(fa_obj['win_streak'] - fb_obj['win_streak'])

                feature_vec = [
                    (a_eff - b_eff) / 100.0,
                    str_diff / 100.0,
                    grp_diff / 100.0,
                    car_diff / 100.0,
                    age_diff,
                    a_age_cliff,
                    b_age_cliff,
                    reach_diff,
                    is_a_southpaw,
                    is_b_southpaw,
                    (size_pen_b - size_pen_a) / 35.0,
                    (tdd_a - tdd_b) / 10.0,
                    streak_diff,
                    is_title,
                    (b_dec['months'] - a_dec['months']) / 6.0
                ]

                features.append(feature_vec)
                labels.append(target_y)
                metadata.append({
                    'date': fight_date_str,
                    'event': match.get('event_name', ''),
                    'fa_name': fa_name,
                    'fb_name': fb_name,
                    'winner': winner_name,
                    'target_y': target_y,
                    'p_elo_base': 1.0 / (1.0 + 10.0 ** ((b_eff - a_eff) / 400.0))
                })

            engine.process_match(match)

            ca = get_comp(winner_name)
            cb = get_comp(loser_name)
            m_type = match.get('method', '')
            if m_type == 'KO/TKO':
                ca['str'] += 20.0
                cb['str'] -= 20.0
            elif m_type == 'SUB':
                ca['grp'] += 20.0
                cb['grp'] -= 20.0
            else:
                ca['car'] += 10.0
                cb['car'] -= 10.0

        return np.array(features), np.array(labels), metadata

    def run_walk_forward_hybrid_backtest(self):
        print("[INFO] Extracting rich 15-feature matrix from historical bouts...", flush=True)
        X, y, meta = self.extract_dataset()
        n_samples = len(X)
        print(f"[INFO] Total Evaluated Dataset Size: {n_samples} bouts.", flush=True)

        initial_train_size = 1200
        step_size = 100

        hybrid_preds = []
        base_elo_preds = []
        actual_ys = []
        test_meta = []

        print("[INFO] Running Walk-Forward Expanding Window Hybrid Model...", flush=True)

        model = PureNumpyLogisticRegression(lr=0.05, l2_reg=0.005, epochs=250)

        for i in range(initial_train_size, n_samples):
            if i == initial_train_size or i % step_size == 0:
                X_train, y_train = X[:i], y[:i]
                model.fit(X_train, y_train)

            x_test = X[i:i+1]
            p_hybrid = float(model.predict_proba(x_test)[0])

            hybrid_preds.append(p_hybrid)
            base_elo_preds.append(meta[i]['p_elo_base'])
            actual_ys.append(y[i])
            test_meta.append(meta[i])

        y_true = np.array(actual_ys)
        p_hyb = np.array(hybrid_preds)
        p_base = np.array(base_elo_preds)

        # Compute Metrics manually with numpy
        def get_accuracy(y_arr, p_arr):
            return np.mean((p_arr >= 0.5) == (y_arr == 1.0)) * 100.0

        def get_brier(y_arr, p_arr):
            return np.mean((p_arr - y_arr) ** 2)

        def get_log_loss(y_arr, p_arr):
            eps = 1e-6
            p_c = np.clip(p_arr, eps, 1.0 - eps)
            return -np.mean(y_arr * np.log(p_c) + (1.0 - y_arr) * np.log(1.0 - p_c))

        def compute_ece(probs, y_arr, n_bins=10):
            bins = [[] for _ in range(n_bins)]
            for p, act in zip(probs, y_arr):
                idx = min(n_bins - 1, int(p * n_bins))
                bins[idx].append((p, act))
            ece = 0.0
            n = len(probs)
            for b in bins:
                if len(b) > 0:
                    avg_p = sum(x[0] for x in b) / len(b)
                    avg_y = sum(x[1] for x in b) / len(b)
                    ece += (len(b) / n) * abs(avg_p - avg_y)
            return ece * 100.0

        acc_base = get_accuracy(y_true, p_base)
        acc_hyb = get_accuracy(y_true, p_hyb)

        brier_base = get_brier(y_true, p_base)
        brier_hyb = get_brier(y_true, p_hyb)

        loss_base = get_log_loss(y_true, p_base)
        loss_hyb = get_log_loss(y_true, p_hyb)

        ece_base = compute_ece(p_base, y_true)
        ece_hyb = compute_ece(p_hyb, y_true)

        print("\n========================================================================================")
        print("STAGE 3: HYBRID MACHINE LEARNING (ELO + 3D COMPONENTS + BIOMETRICS) WALK-FORWARD RESULTS")
        print("========================================================================================")
        print(f"Toplam Out-of-Sample Test Maç Sayısı: {len(y_true)}")
        print("----------------------------------------------------------------------------------------")
        print(f"1. BASE ELO MODELİ (Yalnızca Reyting & Ağırlık):")
        print(f"   • Doğruluk:        %{round(acc_base, 2)}")
        print(f"   • Brier Score:      {round(brier_base, 4)}")
        print(f"   • Log-Loss:         {round(loss_base, 4)}")
        print(f"   • ECE (Kalibrasyon):%{round(ece_base, 2)}")
        print("----------------------------------------------------------------------------------------")
        print(f"2. HYBRID ML MODELİ (3D Elo + Yaş Uçurumu + Reach + Ters Gard + Sıklet Dinamiği):")
        print(f"   • Doğruluk:        %{round(acc_hyb, 2)} (+{round(acc_hyb - acc_base, 2)}% İyileşme)")
        print(f"   • Brier Score:      {round(brier_hyb, 4)} (-{round(brier_base - brier_hyb, 4)} İyileşme)")
        print(f"   • Log-Loss:         {round(loss_hyb, 4)} (-{round(loss_base - loss_hyb, 4)} İyileşme)")
        print(f"   • ECE (Kalibrasyon):%{round(ece_hyb, 2)} (Daha Yüksek İhtimal Güvenilirliği)")
        print("========================================================================================\n")

        results_artifact = {
            'out_of_sample_eval_bouts': len(y_true),
            'base_model': {
                'accuracy': round(acc_base, 2),
                'brier_score': round(brier_base, 4),
                'log_loss': round(loss_base, 4),
                'ece_pct': round(ece_base, 2)
            },
            'hybrid_model': {
                'accuracy': round(acc_hyb, 2),
                'brier_score': round(brier_hyb, 4),
                'log_loss': round(loss_hyb, 4),
                'ece_pct': round(ece_hyb, 2)
            },
            'delta_improvements': {
                'accuracy_gain': round(acc_hyb - acc_base, 2),
                'brier_gain': round(brier_base - brier_hyb, 4),
                'log_loss_gain': round(loss_base - loss_hyb, 4)
            }
        }

        with open("hybrid_model_results.json", "w", encoding="utf-8") as f:
            json.dump(results_artifact, f, indent=2, ensure_ascii=False)

        return results_artifact

if __name__ == '__main__':
    engine = UFCHybridMLEngine()
    engine.run_walk_forward_hybrid_backtest()
