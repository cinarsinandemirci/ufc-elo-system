import json
import math
import os
import sys
import random
import numpy as np
import lightgbm as lgb
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, accuracy_score
from sklearn.preprocessing import StandardScaler

sys.stdout.reconfigure(encoding='utf-8')
random.seed(42)
np.random.seed(42)

print("==========================================================================================")
print("  PHASE 2: NON-LINEAR ENSEMBLE ENGINE (LIGHTGBM + STYLISTIC INTERACTION + ROLLING EWMA)")
print("==========================================================================================")

with open('bout_rolling_features.json', 'r', encoding='utf-8') as f:
    bouts = json.load(f)

with open('fighter_rankings.json', 'r', encoding='utf-8') as f:
    rankings = json.load(f)
rank_db = {f['name'].lower(): f for f in rankings}

with open('fighter_biometrics.json', 'r', encoding='utf-8') as f:
    bio_db = json.load(f)

with open('fighter_details.json', 'r', encoding='utf-8') as f:
    det_db = json.load(f)

with open('fighter_component_elos.json', 'r', encoding='utf-8') as f:
    comp_db = json.load(f)

with open('fighter_archetypes.json', 'r', encoding='utf-8') as f:
    arch_db = json.load(f)

# Stylistic advantage matrix (Rock-paper-scissors tilts)
STYLE_ADVANTAGE = {
    ('Pressure Wrestler', 'Distance Out-Fighter'): 0.08,
    ('Pressure Wrestler', 'Inside Pressure Boxer'): 0.05,
    ('Sprawl-and-Brawler', 'Pressure Wrestler'): 0.09,
    ('Submission Hunter', 'Clinch Grinder'): 0.06,
    ('Distance Out-Fighter', 'Sprawl-and-Brawler'): 0.06,
    ('Inside Pressure Boxer', 'Distance Out-Fighter'): 0.04,
    ('Sprawl-and-Brawler', 'Submission Hunter'): 0.07,
    ('Clinch Grinder', 'Inside Pressure Boxer'): 0.05
}

def get_style_adv(a1, a2):
    if (a1, a2) in STYLE_ADVANTAGE:
        return STYLE_ADVANTAGE[(a1, a2)]
    if (a2, a1) in STYLE_ADVANTAGE:
        return -STYLE_ADVANTAGE[(a2, a1)]
    return 0.0

X_list = []
y_list = []
dates_list = []
base_elo_probs = []

for b in bouts:
    # 50% random swap to guarantee balanced classes 0 and 1
    swap = random.choice([True, False])
    
    if not swap:
        f1_name = b['fighter1']
        f2_name = b['fighter2']
        y = 1 if b['winner'] == f1_name else (0 if b['winner'] == f2_name else 0.5)
        r1 = b['f1_rolling']
        r2 = b['f2_rolling']
    else:
        f1_name = b['fighter2']
        f2_name = b['fighter1']
        y = 1 if b['winner'] == f1_name else (0 if b['winner'] == f2_name else 0.5)
        r1 = b['f2_rolling']
        r2 = b['f1_rolling']

    if y not in [0, 1]:
        continue

    f1 = rank_db.get(f1_name.lower())
    f2 = rank_db.get(f2_name.lower())
    if not f1 or not f2:
        continue

    b1 = {**bio_db.get(f1_name.lower(), {}), **det_db.get(f1_name.lower(), {})}
    b2 = {**bio_db.get(f2_name.lower(), {}), **det_db.get(f2_name.lower(), {})}
    c1 = comp_db.get(f1_name.lower(), {'striking_elo': 1500.0, 'grappling_elo': 1500.0, 'cardio_elo': 1500.0})
    c2 = comp_db.get(f2_name.lower(), {'striking_elo': 1500.0, 'grappling_elo': 1500.0, 'cardio_elo': 1500.0})
    arch1 = arch_db.get(f1_name.lower(), {}).get('archetype', 'Distance Out-Fighter')
    arch2 = arch_db.get(f2_name.lower(), {}).get('archetype', 'Distance Out-Fighter')

    elo_diff = (f1['elo'] - f2['elo']) / 400.0
    str_elo_diff = (c1['striking_elo'] - c2['striking_elo']) / 400.0
    grp_elo_diff = (c1['grappling_elo'] - c2['grappling_elo']) / 400.0
    card_elo_diff = (c1['cardio_elo'] - c2['cardio_elo']) / 400.0

    age1 = b1.get('age') or 30.0
    age2 = b2.get('age') or 30.0
    age_cliff_1 = max(0.0, age1 - 34.0)
    age_cliff_2 = max(0.0, age2 - 34.0)
    age_cliff_diff = (age_cliff_2 - age_cliff_1) / 10.0

    reach1 = b1.get('reach_inches') or 71.0
    reach2 = b2.get('reach_inches') or 71.0
    reach_diff = (reach1 - reach2) / 10.0

    stance1 = b1.get('stance', 'Orthodox')
    stance2 = b2.get('stance', 'Orthodox')
    stance_adv = 1.0 if (stance1 == 'Southpaw' and stance2 == 'Orthodox') else (-1.0 if (stance2 == 'Southpaw' and stance1 == 'Orthodox') else 0.0)

    tdd1 = (b1.get('tactical', {}).get('td_def_pct', 70.0) if b1.get('tactical') else 70.0) / 100.0
    tdd2 = (b2.get('tactical', {}).get('td_def_pct', 70.0) if b2.get('tactical') else 70.0) / 100.0
    tdd_diff = tdd1 - tdd2

    # Rolling EWMA differences
    slpm_diff = (r1['slpm'] - r2['slpm']) / 5.0
    sapm_diff = (r2['sapm'] - r1['sapm']) / 5.0
    str_acc_diff = (r1['str_acc'] - r2['str_acc'])
    str_def_diff = (r1['str_def'] - r2['str_def'])
    td_avg_diff = (r1['td_avg_15m'] - r2['td_avg_15m']) / 5.0
    kd_rate_diff = (r1['kd_rate'] - r2['kd_rate'])
    damage_diff = (r2['recent_damage_index'] - r1['recent_damage_index']) / 5.0
    finish_diff = (r1['finish_rate_recent'] - r2['finish_rate_recent'])
    streak_diff = (r1['win_streak_recent'] - r2['win_streak_recent']) / 4.0

    # Stylistic interaction & Environmental factors
    style_adv = get_style_adv(arch1, arch2)
    is_apex = float(b.get('is_apex', 0))
    is_high_alt = float(b.get('is_high_altitude', 0))

    feat = [
        elo_diff,
        str_elo_diff,
        grp_elo_diff,
        card_elo_diff,
        age_cliff_diff,
        reach_diff,
        stance_adv,
        tdd_diff,
        slpm_diff,
        sapm_diff,
        str_acc_diff,
        str_def_diff,
        td_avg_diff,
        kd_rate_diff,
        damage_diff,
        finish_diff,
        streak_diff,
        style_adv,
        is_apex,
        is_high_alt
    ]

    base_p1 = 1.0 / (1.0 + 10.0 ** (-elo_diff))
    base_elo_probs.append(base_p1)

    X_list.append(feat)
    y_list.append(y)
    dates_list.append(b['date'])

X = np.array(X_list)
y = np.array(y_list)
dates = np.array(dates_list)
base_p = np.array(base_elo_probs)

print(f"[DATA] Total samples: {len(X)} bouts (Class 1: {sum(y==1)}, Class 0: {sum(y==0)})")

# =========================================================================
# WALK-FORWARD EXPANDING VALIDATION ACROSS MODERN ERA BOUTS
# =========================================================================
INITIAL_TRAIN = 2500
STEP = 250
N = len(X)

y_true_all = []
base_preds_all = []
logistic_preds_all = []
lgbm_preds_all = []
ensemble_preds_all = []

feature_names = [
    'elo_diff', 'str_elo_diff', 'grp_elo_diff', 'card_elo_diff',
    'age_cliff_diff', 'reach_diff', 'stance_adv', 'tdd_diff',
    'slpm_diff', 'sapm_diff', 'str_acc_diff', 'str_def_diff',
    'td_avg_diff', 'kd_rate_diff', 'damage_diff', 'finish_diff',
    'streak_diff', 'style_adv', 'is_apex', 'is_high_alt'
]

for start_idx in range(INITIAL_TRAIN, N, STEP):
    end_idx = min(N, start_idx + STEP)
    
    X_train, y_train = X[:start_idx], y[:start_idx]
    X_test, y_test = X[start_idx:end_idx], y[start_idx:end_idx]
    base_test = base_p[start_idx:end_idx]
    
    # 1. Standardize for Logistic Regression
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    log_model = LogisticRegression(C=0.15, max_iter=200, random_state=42)
    log_model.fit(X_train_scaled, y_train)
    p_log = log_model.predict_proba(X_test_scaled)[:, 1]
    
    # 2. LightGBM Classifier
    lgb_train = lgb.Dataset(X_train, y_train, feature_name=feature_names)
    params = {
        'objective': 'binary',
        'metric': 'binary_logloss',
        'boosting_type': 'gbdt',
        'learning_rate': 0.03,
        'num_leaves': 15,
        'max_depth': 4,
        'feature_fraction': 0.85,
        'lambda_l2': 2.0,
        'verbose': -1,
        'seed': 42
    }
    
    gbm = lgb.train(params, lgb_train, num_boost_round=75)
    p_lgb = gbm.predict(X_test)
    
    # 3. Non-Linear Ensemble Blend
    p_ens = 0.55 * p_lgb + 0.45 * p_log
    
    y_true_all.extend(y_test)
    base_preds_all.extend(base_test)
    logistic_preds_all.extend(p_log)
    lgbm_preds_all.extend(p_lgb)
    ensemble_preds_all.extend(p_ens)

y_true = np.array(y_true_all)
p_base = np.array(base_preds_all)
p_log = np.array(logistic_preds_all)
p_lgb = np.array(lgbm_preds_all)
p_ens = np.array(ensemble_preds_all)

# Evaluation metrics
def eval_model(name, probs, truths):
    acc = accuracy_score(truths, (probs >= 0.5).astype(int)) * 100.0
    brier = brier_score_loss(truths, probs)
    loss = log_loss(truths, probs)
    return {'name': name, 'accuracy': round(acc, 2), 'brier_score': round(brier, 4), 'log_loss': round(loss, 4)}

m_base = eval_model("Standard Base Elo", p_base, y_true)
m_log = eval_model("Calibrated Logistic ML", p_log, y_true)
m_lgb = eval_model("LightGBM Boosted Trees", p_lgb, y_true)
m_ens = eval_model("Phase 2 Non-Linear Ensemble", p_ens, y_true)

print("\n==========================================================================================")
print(f"{'MODEL ARCHITECTURE':32s} | {'ACCURACY':10s} | {'BRIER SCORE':12s} | {'LOG-LOSS':10s}")
print("==========================================================================================")
for m in [m_base, m_log, m_lgb, m_ens]:
    print(f"{m['name']:32s} | {m['accuracy']:5.2f}%    | {m['brier_score']:8.4f}     | {m['log_loss']:8.4f}")
print("==========================================================================================")

# Feature Importances from final LightGBM model
lgb_full = lgb.train(params, lgb.Dataset(X, y, feature_name=feature_names), num_boost_round=80)
importances = lgb_full.feature_importance(importance_type='gain')
imp_tuples = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)

print("\n=== TOP 10 NON-LINEAR FEATURE DRIVERS (LIGHTGBM GAIN) ===")
for feat_name, imp in imp_tuples[:10]:
    print(f"  • {feat_name:24s}: {imp:8.2f} gain")

results_payload = {
    'total_evaluated_bouts': len(y_true),
    'benchmark_models': [m_base, m_log, m_lgb, m_ens],
    'top_feature_importances': [{'feature': f, 'importance': round(float(imp), 2)} for f, imp in imp_tuples],
    'performance_delta': {
        'accuracy_gain': round(m_ens['accuracy'] - m_base['accuracy'], 2),
        'brier_improvement': round(m_base['brier_score'] - m_ens['brier_score'], 4),
        'log_loss_reduction': round(m_base['log_loss'] - m_ens['log_loss'], 4)
    }
}

with open('advanced_model_results.json', 'w', encoding='utf-8') as f:
    json.dump(results_payload, f, indent=2, ensure_ascii=False)

print("\n[OK] Phase 2 Complete! Model artifacts and benchmarks saved to advanced_model_results.json.")
