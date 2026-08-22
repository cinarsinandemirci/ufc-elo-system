import os
import json
from collections import defaultdict
from datetime import datetime
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
RANKINGS_FILE = os.path.join(DATA_DIR, "fighter_rankings.json")
MATCHES_FILE = os.path.join(DATA_DIR, "matches.json")
HISTORY_FILE = os.path.join(DATA_DIR, "elo_history.json")
BIOMETRICS_FILE = os.path.join(DATA_DIR, "fighter_biometrics.json")
DETAILS_FILE = os.path.join(DATA_DIR, "fighter_details.json")
COMPONENTS_FILE = os.path.join(DATA_DIR, "fighter_component_elos.json")
UPCOMING_FILE = os.path.join(DATA_DIR, "upcoming_events_with_signals.json")

ARCHETYPES_FILE = os.path.join(DATA_DIR, "fighter_archetypes.json")
ROLLING_FILE = os.path.join(DATA_DIR, "fighter_rolling_features.json")
ADVANCED_RESULTS_FILE = os.path.join(DATA_DIR, "advanced_model_results.json")
PEDIGREE_FILE = os.path.join(DATA_DIR, "pedigree_database.json")

from pedigree_engine import PedigreeCalibrationEngine
pedigree_engine = PedigreeCalibrationEngine(PEDIGREE_FILE)

try:
    from method_of_victory_engine import MethodOfVictoryPredictor
    mov_engine = MethodOfVictoryPredictor()
except Exception:
    mov_engine = None

# In-Memory Cache Store
_CACHE = {
    'rankings': [],
    'fighters_by_name': {},
    'biometrics': {},
    'details': {},
    'components': {},
    'archetypes': {},
    'rolling': {},
    'advanced_results': {},
    'upcoming': {},
    'stats': {},
    'weight_classes': [],
    'mtime': 0
}

def reload_cache_if_needed():
    if not os.path.exists(RANKINGS_FILE):
        return

    mtime = os.path.getmtime(RANKINGS_FILE)
    if _CACHE['mtime'] == mtime and _CACHE['rankings']:
        return

    try:
        print("[CACHE] Loading rankings, archetypes, and rolling features into memory...", flush=True)
        with open(RANKINGS_FILE, 'r', encoding='utf-8') as f:
            rankings = json.load(f)
            
        matches = []
        if os.path.exists(MATCHES_FILE):
            with open(MATCHES_FILE, 'r', encoding='utf-8') as f:
                matches = json.load(f)

        biometrics = {}
        if os.path.exists(BIOMETRICS_FILE):
            try:
                with open(BIOMETRICS_FILE, 'r', encoding='utf-8') as f:
                    biometrics = json.load(f)
            except Exception:
                pass

        details = {}
        if os.path.exists(DETAILS_FILE):
            try:
                with open(DETAILS_FILE, 'r', encoding='utf-8') as f:
                    details = json.load(f)
            except Exception:
                pass

        components = {}
        if os.path.exists(COMPONENTS_FILE):
            try:
                with open(COMPONENTS_FILE, 'r', encoding='utf-8') as f:
                    components = json.load(f)
            except Exception:
                pass

        archetypes = {}
        if os.path.exists(ARCHETYPES_FILE):
            try:
                with open(ARCHETYPES_FILE, 'r', encoding='utf-8') as f:
                    archetypes = json.load(f)
            except Exception:
                pass

        rolling = {}
        if os.path.exists(ROLLING_FILE):
            try:
                with open(ROLLING_FILE, 'r', encoding='utf-8') as f:
                    rolling = json.load(f)
            except Exception:
                pass

        advanced_results = {}
        if os.path.exists(ADVANCED_RESULTS_FILE):
            try:
                with open(ADVANCED_RESULTS_FILE, 'r', encoding='utf-8') as f:
                    advanced_results = json.load(f)
            except Exception:
                pass

        upcoming = {}
        if os.path.exists(UPCOMING_FILE):
            try:
                with open(UPCOMING_FILE, 'r', encoding='utf-8') as f:
                    upcoming = json.load(f)
            except Exception:
                pass

        # Enrich rankings with components, archetypes, and rolling features
        for f in rankings:
            k = f['name'].lower()
            c = components.get(k, {})
            f['striking_elo'] = c.get('striking_elo', 1500.0)
            f['grappling_elo'] = c.get('grappling_elo', 1500.0)
            f['cardio_elo'] = c.get('cardio_elo', 1500.0)
            f['archetype'] = archetypes.get(k, {}).get('archetype', 'Distance Out-Fighter')
            f['rolling'] = rolling.get(k, {})

        _CACHE['rankings'] = rankings
        _CACHE['fighters_by_name'] = {f['name'].lower(): f for f in rankings}
        _CACHE['biometrics'] = biometrics
        _CACHE['details'] = details
        _CACHE['components'] = components
        _CACHE['archetypes'] = archetypes
        _CACHE['rolling'] = rolling
        _CACHE['advanced_results'] = advanced_results
        _CACHE['upcoming'] = upcoming
        _CACHE['mtime'] = mtime

        # Precompute stats
        active_fighters = [f for f in rankings if f.get('is_active', True)]
        p4p_king = active_fighters[0] if active_fighters else (rankings[0] if rankings else None)
        all_time_king = max(rankings, key=lambda x: x.get('peak_elo', 0)) if rankings else None

        sorted_by_streak = sorted(active_fighters, key=lambda x: x.get('win_streak', 0), reverse=True)
        highest_streak = sorted_by_streak[0] if sorted_by_streak else None

        sorted_by_finishes = sorted(
            active_fighters,
            key=lambda x: x.get('methods', {}).get('KO/TKO_win', 0) + x.get('methods', {}).get('SUB_win', 0),
            reverse=True
        )
        most_finishes = sorted_by_finishes[0] if sorted_by_finishes else None
        title_matches_count = sum(1 for m in matches if m.get('is_title_bout'))

        _CACHE['stats'] = {
            'total_fighters': len(rankings),
            'total_active_fighters': len(active_fighters),
            'total_matches': len(matches),
            'title_matches_count': title_matches_count,
            'p4p_king': {
                'name': p4p_king['name'],
                'elo': p4p_king['elo'],
                'peak_elo': p4p_king['peak_elo'],
                'weight_class': p4p_king['primary_weight_class'],
                'wins': p4p_king['wins'],
                'losses': p4p_king['losses'],
                'win_streak': p4p_king['win_streak']
            } if p4p_king else None,
            'all_time_king': {
                'name': all_time_king['name'],
                'peak_elo': all_time_king['peak_elo'],
                'current_elo': all_time_king['elo'],
                'weight_class': all_time_king['primary_weight_class']
            } if all_time_king else None,
            'highest_streak': {
                'name': highest_streak['name'],
                'streak': highest_streak['win_streak'],
                'weight_class': highest_streak['primary_weight_class'],
                'elo': highest_streak['elo']
            } if highest_streak else None,
            'most_finishes': {
                'name': most_finishes['name'],
                'finishes': most_finishes['methods']['KO/TKO_win'] + most_finishes['methods']['SUB_win'],
                'ko': most_finishes['methods']['KO/TKO_win'],
                'sub': most_finishes['methods']['SUB_win'],
                'elo': most_finishes['elo']
            } if most_finishes else None
        }

        # Precompute weight classes
        wc_dict = {}
        for f in rankings:
            wc = f.get('primary_weight_class', 'Other')
            if wc not in wc_dict:
                wc_dict[wc] = {
                    'name': wc,
                    'count': 0,
                    'active_count': 0,
                    'top_fighter': f['name'],
                    'top_elo': f['elo']
                }
            wc_dict[wc]['count'] += 1
            if f.get('is_active', True):
                wc_dict[wc]['active_count'] += 1

        standard_order = [
            "Heavyweight",
            "Light Heavyweight",
            "Middleweight",
            "Welterweight",
            "Lightweight",
            "Featherweight",
            "Bantamweight",
            "Flyweight",
            "Women's Featherweight",
            "Women's Bantamweight",
            "Women's Flyweight",
            "Women's Strawweight",
            "Catchweight"
        ]
        
        ordered_list = []
        for wc_name in standard_order:
            if wc_name in wc_dict:
                ordered_list.append(wc_dict[wc_name])
                
        for wc_name, data in wc_dict.items():
            if wc_name not in standard_order:
                ordered_list.append(data)

        _CACHE['weight_classes'] = ordered_list
        print("[CACHE] Cache precomputation complete.", flush=True)

    except Exception as e:
        print(f"[ERROR] Reload cache failed: {e}", flush=True)

# Initial load
reload_cache_if_needed()

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stats')
def get_stats():
    reload_cache_if_needed()
    return jsonify(_CACHE['stats'])

@app.route('/api/weight-classes')
def get_weight_classes():
    reload_cache_if_needed()
    return jsonify(_CACHE['weight_classes'])

@app.route('/api/rankings')
def get_rankings():
    reload_cache_if_needed()
    rankings = _CACHE['rankings']
    
    weight_class = request.args.get('weight_class', 'all')
    search = request.args.get('search', '').strip().lower()
    sort_by = request.args.get('sort_by', 'elo')
    sort_order = request.args.get('sort_order', 'desc')
    min_fights = int(request.args.get('min_fights', 1))
    active_only = request.args.get('active_only', 'true').lower() == 'true'

    filtered = []
    for f in rankings:
        if active_only and not f.get('is_active', True):
            continue

        if f.get('total_fights', 0) < min_fights:
            continue
            
        if weight_class != 'all':
            if f.get('primary_weight_class') != weight_class and weight_class not in f.get('all_weight_classes', []):
                continue
                
        if search:
            if search not in f['name'].lower():
                continue
                
        filtered.append(f)

    reverse = (sort_order == 'desc')
    if sort_by == 'elo':
        filtered.sort(key=lambda x: x.get('elo', 0), reverse=reverse)
    elif sort_by == 'peak_elo':
        filtered.sort(key=lambda x: x.get('peak_elo', 0), reverse=reverse)
    elif sort_by == 'win_streak':
        filtered.sort(key=lambda x: (x.get('win_streak', 0), x.get('elo', 0)), reverse=reverse)
    elif sort_by == 'wins':
        filtered.sort(key=lambda x: (x.get('wins', 0), x.get('elo', 0)), reverse=reverse)
    elif sort_by == 'win_rate':
        filtered.sort(key=lambda x: (x.get('win_rate', 0), x.get('elo', 0)), reverse=reverse)
    elif sort_by == 'total_fights':
        filtered.sort(key=lambda x: (x.get('total_fights', 0), x.get('elo', 0)), reverse=reverse)
    elif sort_by == 'name':
        filtered.sort(key=lambda x: x.get('name', ''), reverse=reverse)

    return jsonify({
        'total': len(filtered),
        'active_only': active_only,
        'fighters': filtered
    })

@app.route('/api/fighter/<fighter_name>')
def get_fighter(fighter_name):
    reload_cache_if_needed()
    key = fighter_name.strip().lower()
    f = _CACHE['fighters_by_name'].get(key)
    if f:
        comp = _CACHE['components'].get(key, {})
        bio = {**_CACHE['biometrics'].get(key, {}), **_CACHE['details'].get(key, {})}
        res = dict(f)
        res['components'] = {
            'striking_elo': comp.get('striking_elo', 1500.0),
            'grappling_elo': comp.get('grappling_elo', 1500.0),
            'cardio_elo': comp.get('cardio_elo', 1500.0),
            'peak_striking_elo': comp.get('peak_striking_elo', 1500.0),
            'peak_grappling_elo': comp.get('peak_grappling_elo', 1500.0),
            'peak_cardio_elo': comp.get('peak_cardio_elo', 1500.0)
        }
        res['biometrics'] = bio
        return jsonify(res)
    return jsonify({'error': 'Fighter not found'}), 404

def compute_detailed_matchup(f1, f2, target_weight_class='auto', is_title=False, is_apex=False, is_high_altitude=False):
    div_hierarchy = {
        "Women's Strawweight": 0,
        "Women's Flyweight": 1,
        "Women's Bantamweight": 2,
        "Women's Featherweight": 3,
        'Flyweight': 1,
        'Bantamweight': 2,
        'Featherweight': 3,
        'Lightweight': 4,
        'Welterweight': 5,
        'Middleweight': 6,
        'Light Heavyweight': 7,
        'Heavyweight': 8,
    }
    t1 = div_hierarchy.get(f1.get('primary_weight_class', 'Lightweight'), 4)
    t2 = div_hierarchy.get(f2.get('primary_weight_class', 'Lightweight'), 4)

    if not target_weight_class or target_weight_class == 'auto':
        target_tier = max(t1, t2)
        target_div_name = next((k for k, v in div_hierarchy.items() if v == target_tier and not k.startswith("Women")), f1.get('primary_weight_class'))
    else:
        target_tier = div_hierarchy.get(target_weight_class, max(t1, t2))
        target_div_name = target_weight_class

    # 1. Weight Class Jump & Size Adjustment
    size_adj_1 = 0.0
    size_adj_2 = 0.0

    f1_all_wc = f1.get('all_weight_classes', [])
    f2_all_wc = f2.get('all_weight_classes', [])
    f1_exp_at_target = 1 if target_div_name in f1_all_wc else 0
    f2_exp_at_target = 1 if target_div_name in f2_all_wc else 0

    if target_tier > t1:
        tier_gap = target_tier - t1
        base_pen = tier_gap * 35.0
        if f1_exp_at_target: base_pen *= 0.5
        size_adj_1 = -base_pen

    if target_tier > t2:
        tier_gap = target_tier - t2
        base_pen = tier_gap * 35.0
        if f2_exp_at_target: base_pen *= 0.5
        size_adj_2 = -base_pen

    # 2. Biometrics & Physical Dynamics
    bio_db = _CACHE.get('biometrics', {})
    det_db = _CACHE.get('details', {})

    raw_bio_1 = bio_db.get(f1['name'].lower(), {})
    raw_det_1 = det_db.get(f1['name'].lower(), {})
    b1 = {**raw_bio_1, **raw_det_1}

    raw_bio_2 = bio_db.get(f2['name'].lower(), {})
    raw_det_2 = det_db.get(f2['name'].lower(), {})
    b2 = {**raw_bio_2, **raw_det_2}

    now_str = "2026-08-21"

    def parse_age(detail_dict, fallback=32.0):
        dob_str = detail_dict.get('dob')
        if dob_str:
            try:
                dob = datetime.strptime(dob_str, '%b %d, %Y')
                now = datetime.strptime(now_str, '%Y-%m-%d')
                return (now - dob).days / 365.25
            except Exception:
                pass
        return detail_dict.get('age') or fallback

    f1_age = parse_age(b1, 32.0 if f1.get('is_active') else 38.0)
    f2_age = parse_age(b2, 32.0 if f2.get('is_active') else 38.0)

    age_adj_1 = 0.0
    age_adj_2 = 0.0
    is_lighter_division = (target_tier <= 4)

    if is_lighter_division:
        if f1_age >= 34.5: age_adj_1 -= min(35.0, (f1_age - 33.5) * 12.0)
        if f2_age >= 34.5: age_adj_2 -= min(35.0, (f2_age - 33.5) * 12.0)
    else:
        if f1_age >= 36.5: age_adj_1 -= min(30.0, (f1_age - 35.5) * 8.0)
        if f2_age >= 36.5: age_adj_2 -= min(30.0, (f2_age - 35.5) * 8.0)

    age_gap = f2_age - f1_age
    if age_gap >= 6.0 and f1_age < 34.0:
        age_adj_1 += min(15.0, (age_gap - 5.0) * 2.5)
    elif age_gap <= -6.0 and f2_age < 34.0:
        age_adj_2 += min(15.0, (-age_gap - 5.0) * 2.5)

    f1_reach = b1.get('reach_inches') or 71.0
    f2_reach = b2.get('reach_inches') or 71.0
    f1_height_raw = b1.get('height_raw', '--')
    f2_height_raw = b2.get('height_raw', '--')
    f1_reach_raw = b1.get('reach_raw', '--')
    f2_reach_raw = b2.get('reach_raw', '--')

    reach_adj_1 = 0.0
    reach_adj_2 = 0.0
    reach_gap = f1_reach - f2_reach
    if reach_gap >= 3.0:
        reach_adj_1 += min(16.0, (reach_gap - 2.0) * 3.0)
    elif reach_gap <= -3.0:
        reach_adj_2 += min(16.0, (-reach_gap - 2.0) * 3.0)

    f1_stance = b1.get('stance', 'Orthodox')
    f2_stance = b2.get('stance', 'Orthodox')
    stance_adj_1 = 0.0
    stance_adj_2 = 0.0
    if f1_stance == 'Southpaw' and f2_stance == 'Orthodox':
        stance_adj_1 += 8.0
    elif f2_stance == 'Southpaw' and f1_stance == 'Orthodox':
        stance_adj_2 += 8.0
    elif f1_stance == 'Switch':
        stance_adj_1 += 4.0
    elif f2_stance == 'Switch':
        stance_adj_2 += 4.0

    f1_ko_losses = f1.get('methods', {}).get('KO/TKO_loss', 0)
    f2_ko_losses = f2.get('methods', {}).get('KO/TKO_loss', 0)
    f1_ko_wins = f1.get('methods', {}).get('KO/TKO_win', 0)
    f2_ko_wins = f2.get('methods', {}).get('KO/TKO_win', 0)

    chin_adj_1 = 0.0
    chin_adj_2 = 0.0
    if f1_ko_losses >= 2 and f2_ko_wins >= 4:
        chin_adj_1 -= min(20.0, 10.0 + (f1_ko_losses - 2) * 4.0)
    if f2_ko_losses >= 2 and f1_ko_wins >= 4:
        chin_adj_2 -= min(20.0, 10.0 + (f2_ko_losses - 2) * 4.0)

    f1_tact = b1.get('tactical', {}) or {}
    f2_tact = b2.get('tactical', {}) or {}
    f1_tdd = f1_tact.get('td_def_pct', 70.0)
    f2_tdd = f2_tact.get('td_def_pct', 70.0)
    f1_slpm = f1_tact.get('slpm', 3.8)
    f2_slpm = f2_tact.get('slpm', 3.8)

    g1 = f1.get('grappling_index', 0.0)
    g2 = f2.get('grappling_index', 0.0)
    s1 = f1.get('striking_index', 0.0)
    s2 = f2.get('striking_index', 0.0)

    # 3. Stylistic & Archetype Interactions
    arch1 = f1.get('archetype', 'Distance Out-Fighter')
    arch2 = f2.get('archetype', 'Distance Out-Fighter')
    
    style_matrix = {
        ('Pressure Wrestler', 'Distance Out-Fighter'): 20.0,
        ('Pressure Wrestler', 'Inside Pressure Boxer'): 16.0,
        ('Sprawl-and-Brawler', 'Pressure Wrestler'): 18.0,
        ('Submission Hunter', 'Clinch Grinder'): 15.0,
        ('Inside Pressure Boxer', 'Distance Out-Fighter'): 14.0,
        ('Distance Out-Fighter', 'Clinch Grinder'): 14.0,
    }
    
    style_bonus_1 = 0.0
    if (arch1, arch2) in style_matrix:
        style_bonus_1 = style_matrix[(arch1, arch2)]
    elif (arch2, arch1) in style_matrix:
        style_bonus_1 = -style_matrix[(arch2, arch1)]

    # TDD Neutralizer: If opponent has >= 82% TDD, neutralize wrestler advantage
    if 'Wrestler' in arch1 and f2_tdd >= 82.0 and style_bonus_1 > 0:
        style_bonus_1 *= 0.35
    if 'Wrestler' in arch2 and f1_tdd >= 82.0 and style_bonus_1 < 0:
        style_bonus_1 *= 0.35

    style_shift = style_bonus_1

    # 3b. Improvement 3: Decision-Heavy & Women's Volume Scoring
    is_women_div = target_div_name.startswith("Women's")
    vol_multiplier = 4.0 if is_women_div else 1.8
    vol_diff = (f1_slpm - f2_slpm) * vol_multiplier
    vol_adj_1 = max(-18.0, min(18.0, vol_diff)) if vol_diff > 0 else 0.0
    vol_adj_2 = max(-18.0, min(18.0, -vol_diff)) if vol_diff < 0 else 0.0

    # 3c. Improvement 4: Environmental Cage Size & High Altitude Venue
    apex_adj_1 = 0.0
    apex_adj_2 = 0.0
    if is_apex:
        if arch1 in ['Pressure Wrestler', 'Inside Pressure Boxer', 'Clinch Grinder'] and arch2 == 'Distance Out-Fighter':
            apex_adj_1 += 12.0
        elif arch2 in ['Pressure Wrestler', 'Inside Pressure Boxer', 'Clinch Grinder'] and arch1 == 'Distance Out-Fighter':
            apex_adj_2 += 12.0

    c1 = _CACHE.get('components', {}).get(f1['name'].lower(), {})
    c2 = _CACHE.get('components', {}).get(f2['name'].lower(), {})
    alt_adj_1 = 0.0
    alt_adj_2 = 0.0
    if is_high_altitude:
        c1_card = c1.get('cardio_elo', 1500.0)
        c2_card = c2.get('cardio_elo', 1500.0)
        card_diff = (c1_card - c2_card) / 400.0
        if card_diff > 0:
            alt_adj_1 += min(18.0, card_diff * 35.0)
        elif card_diff < 0:
            alt_adj_2 += min(18.0, -card_diff * 35.0)

    # 4. Inactivity & Decay
    now_str = "2026-08-21"
    last_1 = f1.get('last_fight_date', '2025-01-01')
    last_2 = f2.get('last_fight_date', '2025-01-01')

    def calc_decay(last_date_str, current_elo):
        try:
            d_last = datetime.strptime(last_date_str, "%Y-%m-%d")
            d_now = datetime.strptime(now_str, "%Y-%m-%d")
            months = max(0.0, (d_now - d_last).days / 30.4375)
            if months <= 18.0: return 0.0
            excess = months - 18.0
            return round(min(current_elo - 1200.0, excess * 7.5), 1)
        except Exception:
            return 0.0

    inact_decay_1 = calc_decay(last_1, f1['elo'])
    inact_decay_2 = calc_decay(last_2, f2['elo'])

    # 5. Bayesian Pre-UFC Combat Pedigree Prior & Latent Skill Imputation
    c1_raw = _CACHE.get('components', {}).get(f1['name'].lower(), {})
    c2_raw = _CACHE.get('components', {}).get(f2['name'].lower(), {})
    ped1 = pedigree_engine.calibrate_fighter_ratings(f1['name'], f1['elo'], f1.get('total_fights', 0), c1_raw)
    ped2 = pedigree_engine.calibrate_fighter_ratings(f2['name'], f2['elo'], f2.get('total_fights', 0), c2_raw)

    ped_adj_1 = round(ped1['effective_elo'] - f1['elo'], 1) if ped1.get('pedigree_active') else 0.0
    ped_adj_2 = round(ped2['effective_elo'] - f2['elo'], 1) if ped2.get('pedigree_active') else 0.0

    eff_elo_1 = f1['elo'] - inact_decay_1 + size_adj_1 + age_adj_1 + reach_adj_1 + stance_adj_1 + chin_adj_1 + style_shift + vol_adj_1 + apex_adj_1 + alt_adj_1 + ped_adj_1
    eff_elo_2 = f2['elo'] - inact_decay_2 + size_adj_2 + age_adj_2 + reach_adj_2 + stance_adj_2 + chin_adj_2 + vol_adj_2 + apex_adj_2 + alt_adj_2 + ped_adj_2

    # Model Probabilities
    prob1 = 1.0 / (1.0 + 10.0 ** ((eff_elo_2 - eff_elo_1) / 400.0))
    prob2 = 1.0 - prob1

    # Props
    over_2_5 = max(10, min(90, int(50 + ((eff_elo_1 + eff_elo_2)/2 - 1500) * 0.05)))
    under_2_5 = 100 - over_2_5

    m1_total = max(1, f1.get('wins', 1))
    m2_total = max(1, f2.get('wins', 1))
    f1_ko_pct = round((f1_ko_wins / m1_total) * 100, 1)
    f1_sub_pct = round((f1.get('methods', {}).get('SUB_win', 0) / m1_total) * 100, 1)
    f1_dec_pct = round((f1.get('methods', {}).get('DEC_win', 0) / m1_total) * 100, 1)

    f2_ko_pct = round((f2_ko_wins / m2_total) * 100, 1)
    f2_sub_pct = round((f2.get('methods', {}).get('SUB_win', 0) / m2_total) * 100, 1)
    f2_dec_pct = round((f2.get('methods', {}).get('DEC_win', 0) / m2_total) * 100, 1)

    k_base = 32.0 * (1.2 if is_title else 1.0)
    u1 = f1.get('uncertainty_mult', 1.0)
    u2 = f2.get('uncertainty_mult', 1.0)

    f1_dec_delta = round((k_base * 1.0 * u1) * (1.0 - prob1), 1)
    f1_dom_fin_delta = round((k_base * 1.5 * 1.2 * u1) * (1.0 - prob1), 1)
    f2_dec_delta = round((k_base * 1.0 * u2) * (1.0 - prob2), 1)
    f2_dom_fin_delta = round((k_base * 1.5 * 1.2 * u2) * (1.0 - prob2), 1)

    def to_odds(p):
        p_safe = max(0.005, min(0.995, p))
        if p_safe >= 0.5:
            american_fair = f"-{round((p_safe / (1.0 - p_safe)) * 100)}"
        else:
            american_fair = f"+{round(((1.0 - p_safe) / p_safe) * 100)}"
        decimal_fair = round(1.0 / p_safe, 2)
        return {
            'american': american_fair,
            'decimal': decimal_fair,
            'implied_prob': round(p_safe * 100, 1)
        }

    # Vegas Consensus Market Line (4.5% vig + public unadjusted elo)
    p1_mkt = 1.0 / (1.0 + 10.0 ** ((f2['elo'] - f1['elo']) / 400.0))
    p2_mkt = 1.0 - p1_mkt
    vig = 0.045
    p1_vig = (p1_mkt * (1.0 + vig))
    p2_vig = (p2_mkt * (1.0 + vig))

    v1_line = f"-{round((p1_vig / max(0.001, 1.0 - p1_vig)) * 100)}" if p1_mkt >= 0.5 else f"+{round(((1.0 - p1_vig) / max(0.001, p1_vig)) * 100)}"
    v2_line = f"-{round((p2_vig / max(0.001, 1.0 - p2_vig)) * 100)}" if p2_mkt >= 0.5 else f"+{round(((1.0 - p2_vig) / max(0.001, p2_vig)) * 100)}"

    market_decimal_1 = round((1.0 - (vig / 2.0)) / max(0.01, p1_mkt), 2)
    market_decimal_2 = round((1.0 - (vig / 2.0)) / max(0.01, p2_mkt), 2)

    # Calculate Expected Value (+EV)
    ev_1 = round(((prob1 * market_decimal_1) - 1.0) * 100, 2)
    ev_2 = round(((prob2 * market_decimal_2) - 1.0) * 100, 2)

    # Fractional Kelly (0.25x)
    def get_kelly(p, dec_odds):
        b = dec_odds - 1.0
        q = 1.0 - p
        if b <= 0: return 0.0
        raw_k = (b * p - q) / b
        return round(max(0.0, min(0.05, raw_k * 0.25)) * 100, 1)

    kelly_1 = get_kelly(prob1, market_decimal_1)
    kelly_2 = get_kelly(prob2, market_decimal_2)

    # Edge Drivers
    drivers_1 = []
    drivers_2 = []
    if ped_adj_1 > 0: drivers_1.append(f"🥇 Fast-Track Pedigree: {ped1.get('pedigree_title', 'Elite Title')} (+{round(ped_adj_1, 1)} Elo)")
    if age_adj_1 > 0: drivers_1.append(f"⚡ Prime Speed Edge (+{round(age_adj_1, 1)} Elo)")
    if age_adj_2 < 0: drivers_1.append(f"⚠️ Opponent Age Cliff ({round(age_adj_2, 1)} Elo)")
    if reach_adj_1 > 0: drivers_1.append(f"📏 +{round(reach_gap, 1)}\" Reach Advantage (+{round(reach_adj_1, 1)} Elo)")
    if stance_adj_1 > 0: drivers_1.append(f"🥊 Open Stance Southpaw Angle (+{round(stance_adj_1, 1)} Elo)")
    if f1_tdd >= 80.0 and 'Wrestler' in arch2: drivers_1.append(f"🛡️ {round(f1_tdd)}% TDD Neutralizer")
    if style_shift > 5.0: drivers_1.append(f"🥋 Tactical Style Edge (+{round(style_shift, 1)} Elo)")
    if vol_adj_1 >= 5.0: drivers_1.append(f"📊 High Volume Output Edge (+{round(vol_adj_1, 1)} Elo)")
    if is_apex and apex_adj_1 > 0: drivers_1.append(f"🏟️ 25-ft Apex Cage Leverage (+{round(apex_adj_1, 1)} Elo)")
    if is_high_altitude and alt_adj_1 > 0: drivers_1.append(f"🏔️ High Altitude Cardio Edge (+{round(alt_adj_1, 1)} Elo)")

    if ped_adj_2 > 0: drivers_2.append(f"🥇 Fast-Track Pedigree: {ped2.get('pedigree_title', 'Elite Title')} (+{round(ped_adj_2, 1)} Elo)")
    if age_adj_2 > 0: drivers_2.append(f"⚡ Prime Speed Edge (+{round(age_adj_2, 1)} Elo)")
    if age_adj_1 < 0: drivers_2.append(f"⚠️ Opponent Age Cliff ({round(age_adj_1, 1)} Elo)")
    if reach_adj_2 > 0: drivers_2.append(f"📏 +{round(-reach_gap, 1)}\" Reach Advantage (+{round(reach_adj_2, 1)} Elo)")
    if stance_adj_2 > 0: drivers_2.append(f"🥊 Open Stance Southpaw Angle (+{round(stance_adj_2, 1)} Elo)")
    if f2_tdd >= 80.0 and 'Wrestler' in arch1: drivers_2.append(f"🛡️ {round(f2_tdd)}% TDD Neutralizer")
    if style_shift < -5.0: drivers_2.append(f"🥋 Tactical Style Edge (+{round(-style_shift, 1)} Elo)")
    if vol_adj_2 >= 5.0: drivers_2.append(f"📊 High Volume Output Edge (+{round(vol_adj_2, 1)} Elo)")
    if is_apex and apex_adj_2 > 0: drivers_2.append(f"🏟️ 25-ft Apex Cage Leverage (+{round(apex_adj_2, 1)} Elo)")
    if is_high_altitude and alt_adj_2 > 0: drivers_2.append(f"🏔️ High Altitude Cardio Edge (+{round(alt_adj_2, 1)} Elo)")

    # Value Tier Assignment
    if ev_1 >= 10.0: tier_1 = "💎 ULTRA VALUE"
    elif ev_1 >= 5.0: tier_1 = "⚡ STRONG VALUE"
    elif ev_1 >= 3.0: tier_1 = "🎯 MODERATE VALUE"
    else: tier_1 = "⚖️ FAIR / NO EDGE"

    if ev_2 >= 10.0: tier_2 = "💎 ULTRA VALUE"
    elif ev_2 >= 5.0: tier_2 = "⚡ STRONG VALUE"
    elif ev_2 >= 3.0: tier_2 = "🎯 MODERATE VALUE"
    else: tier_2 = "⚖️ FAIR / NO EDGE"

    c1 = _CACHE.get('components', {}).get(f1['name'].lower(), {})
    c2 = _CACHE.get('components', {}).get(f2['name'].lower(), {})

    # Phase 3: Method of Victory & Round Prop Engine
    try:
        if mov_engine is not None:
            mov_props = mov_engine.predict_detailed_props(f1['name'], f2['name'], prob1, target_div_name)
        else:
            raise RuntimeError("mov_engine is None")
    except Exception as e:
        mov_props = {
            'f1_methods': {'ko_tko': f1_ko_pct, 'submission': f1_sub_pct, 'decision': f1_dec_pct},
            'f2_methods': {'ko_tko': f2_ko_pct, 'submission': f2_sub_pct, 'decision': f2_dec_pct},
            'round_props': {
                'over_1_5_prob': 70.0, 'under_1_5_prob': 30.0,
                'over_2_5_prob': float(over_2_5), 'under_2_5_prob': float(under_2_5),
                'goes_distance_prob': 45.0, 'finish_inside_distance_prob': 55.0
            },
            'f1_archetype': f1.get('archetype', 'Distance Out-Fighter'),
            'f2_archetype': f2.get('archetype', 'Distance Out-Fighter')
        }

    arch1 = mov_props.get('f1_archetype', f1.get('archetype', 'Distance Out-Fighter'))
    arch2 = mov_props.get('f2_archetype', f2.get('archetype', 'Distance Out-Fighter'))
    roll1 = _CACHE.get('rolling', {}).get(f1['name'].lower(), {})
    roll2 = _CACHE.get('rolling', {}).get(f2['name'].lower(), {})

    return {
        'bout_context': {
            'simulated_weight_class': target_div_name,
            'is_title': is_title,
            'style_shift': round(style_shift, 1),
            'f1_archetype': arch1,
            'f2_archetype': arch2,
            'method_distribution': {
                'fighter1': mov_props.get('f1_methods'),
                'fighter2': mov_props.get('f2_methods')
            },
            'round_props': mov_props.get('round_props'),
            'over_2_5_rounds': over_2_5,
            'under_2_5_rounds': under_2_5,
            'props': {
                'over_1_5_rounds': to_odds(mov_props.get('round_props', {}).get('over_1_5_prob', 70.0) / 100.0),
                'under_1_5_rounds': to_odds(mov_props.get('round_props', {}).get('under_1_5_prob', 30.0) / 100.0),
                'over_2_5_rounds': to_odds(over_2_5 / 100.0),
                'under_2_5_rounds': to_odds(under_2_5 / 100.0),
                'f1_ko_tko': to_odds(mov_props.get('f1_methods', {}).get('ko_tko', f1_ko_pct) / 100.0),
                'f1_submission': to_odds(mov_props.get('f1_methods', {}).get('submission', f1_sub_pct) / 100.0),
                'f1_decision': to_odds(mov_props.get('f1_methods', {}).get('decision', f1_dec_pct) / 100.0),
                'f2_ko_tko': to_odds(mov_props.get('f2_methods', {}).get('ko_tko', f2_ko_pct) / 100.0),
                'f2_submission': to_odds(mov_props.get('f2_methods', {}).get('submission', f2_sub_pct) / 100.0),
                'f2_decision': to_odds(mov_props.get('f2_methods', {}).get('decision', f2_dec_pct) / 100.0)
            }
        },
        'fighter1': {
            'name': f1['name'],
            'elo': f1['elo'],
            'effective_elo': round(eff_elo_1, 1),
            'peak_elo': f1['peak_elo'],
            'win_probability': round(prob1 * 100, 1),
            'size_adjustment': round(size_adj_1, 1),
            'grappling_index': round(g1, 1),
            'striking_index': round(s1, 1),
            'archetype': arch1,
            'rolling_stats': roll1,
            'odds': {
                'fair': to_odds(prob1),
                'vegas_line': v1_line,
                'market_decimal': market_decimal_1
            },
            'value_betting': {
                'ev_pct': ev_1,
                'kelly_stake_pct': kelly_1,
                'tier': tier_1,
                'has_value': ev_1 >= 3.0,
                'edge_drivers': drivers_1
            },
            'methods': {
                'ko_tko_pct': mov_props.get('f1_methods', {}).get('ko_tko', f1_ko_pct),
                'submission_pct': mov_props.get('f1_methods', {}).get('submission', f1_sub_pct),
                'decision_pct': mov_props.get('f1_methods', {}).get('decision', f1_dec_pct)
            },
            'win_by_decision_delta': f1_dec_delta,
            'win_by_finish_delta': f1_dom_fin_delta,
            'weight_class': f1['primary_weight_class'],
            'is_active': f1.get('is_active', True),
            'months_inactive': f1.get('months_inactive', 0.0),
            'uncertainty_mult': u1,
            'pedigree': ped1,
            'components': {
                'striking_elo': ped1['comp_elos'].get('striking_elo', c1.get('striking_elo', 1500.0)),
                'grappling_elo': ped1['comp_elos'].get('grappling_elo', c1.get('grappling_elo', 1500.0)),
                'cardio_elo': ped1['comp_elos'].get('cardio_elo', c1.get('cardio_elo', 1500.0))
            }
        },
        'fighter2': {
            'name': f2['name'],
            'elo': f2['elo'],
            'effective_elo': round(eff_elo_2, 1),
            'peak_elo': f2['peak_elo'],
            'win_probability': round(prob2 * 100, 1),
            'size_adjustment': round(size_adj_2, 1),
            'grappling_index': round(g2, 1),
            'striking_index': round(s2, 1),
            'archetype': arch2,
            'rolling_stats': roll2,
            'odds': {
                'fair': to_odds(prob2),
                'vegas_line': v2_line,
                'market_decimal': market_decimal_2
            },
            'value_betting': {
                'ev_pct': ev_2,
                'kelly_stake_pct': kelly_2,
                'tier': tier_2,
                'has_value': ev_2 >= 3.0,
                'edge_drivers': drivers_2
            },
            'methods': {
                'ko_tko_pct': mov_props.get('f2_methods', {}).get('ko_tko', f2_ko_pct),
                'submission_pct': mov_props.get('f2_methods', {}).get('submission', f2_sub_pct),
                'decision_pct': mov_props.get('f2_methods', {}).get('decision', f2_dec_pct)
            },
            'win_by_decision_delta': f2_dec_delta,
            'win_by_finish_delta': f2_dom_fin_delta,
            'weight_class': f2['primary_weight_class'],
            'is_active': f2.get('is_active', True),
            'pedigree': ped2,
            'components': {
                'striking_elo': ped2['comp_elos'].get('striking_elo', c2.get('striking_elo', 1500.0)),
                'grappling_elo': ped2['comp_elos'].get('grappling_elo', c2.get('grappling_elo', 1500.0)),
                'cardio_elo': ped2['comp_elos'].get('cardio_elo', c2.get('cardio_elo', 1500.0))
            }
        },
        'biometrics': {
            'fighter1': {
                'age': f1_age,
                'height': f1_height_raw,
                'reach': f1_reach_raw,
                'reach_inches': f1_reach,
                'stance': f1_stance,
                'tdd_pct': f1_tdd,
                'slpm': f1_slpm,
                'pedigree': ped1,
                'adjustments': {
                    'pedigree_elo': round(ped_adj_1, 1),
                    'age_elo': round(age_adj_1, 1),
                    'reach_elo': round(reach_adj_1, 1),
                    'stance_elo': round(stance_adj_1, 1),
                    'chin_elo': round(chin_adj_1, 1)
                }
            },
            'fighter2': {
                'age': f2_age,
                'height': f2_height_raw,
                'reach': f2_reach_raw,
                'reach_inches': f2_reach,
                'stance': f2_stance,
                'tdd_pct': f2_tdd,
                'slpm': f2_slpm,
                'pedigree': ped2,
                'adjustments': {
                    'pedigree_elo': round(ped_adj_2, 1),
                    'age_elo': round(age_adj_2, 1),
                    'reach_elo': round(reach_adj_2, 1),
                    'stance_elo': round(stance_adj_2, 1),
                    'chin_elo': round(chin_adj_2, 1)
                }
            },
            'comparisons': {
                'reach_diff_in': round(reach_gap, 1),
                'age_diff_years': round(age_gap, 1)
            }
        }
    }

@app.route('/api/matchup')
def simulate_matchup():
    reload_cache_if_needed()
    f1_name = request.args.get('f1', '').strip().lower()
    f2_name = request.args.get('f2', '').strip().lower()
    is_title = request.args.get('is_title', 'false').lower() == 'true'
    is_apex = request.args.get('is_apex', 'false').lower() == 'true'
    is_high_altitude = request.args.get('is_high_altitude', 'false').lower() == 'true'
    target_weight_class = request.args.get('weight_class', 'auto').strip()

    f1 = _CACHE['fighters_by_name'].get(f1_name)
    f2 = _CACHE['fighters_by_name'].get(f2_name)

    if not f1 or not f2:
        return jsonify({'error': 'One or both fighters not found'}), 400

    payload = compute_detailed_matchup(f1, f2, target_weight_class, is_title, is_apex=is_apex, is_high_altitude=is_high_altitude)
    return jsonify(payload)

@app.route('/api/upcoming-cards')
def get_upcoming_cards():
    reload_cache_if_needed()
    upcoming_data = _CACHE.get('upcoming', {})
    return jsonify(upcoming_data)

@app.route('/api/value-bets')
def get_value_bets():
    reload_cache_if_needed()
    min_ev = float(request.args.get('min_ev', 3.0))
    limit = int(request.args.get('limit', 30))
    source = request.args.get('source', 'upcoming').strip().lower()

    if source == 'upcoming' and _CACHE.get('upcoming') and _CACHE['upcoming'].get('top_upcoming_value_bets'):
        raw_signals = _CACHE['upcoming']['top_upcoming_value_bets']
        filtered = [s for s in raw_signals if s['ev_pct'] >= min_ev]
        return jsonify({
            'source': 'upcoming_live_sportsbooks',
            'total_opportunities_found': len(filtered),
            'min_ev_filter': min_ev,
            'signals': filtered[:limit]
        })

    # Fallback / Alternate mode: Pairwise divisional contenders
    active_fighters = [f for f in _CACHE['rankings'] if f.get('is_active', True) and f.get('total_fights', 0) >= 3]
    by_div = defaultdict(list)
    for f in active_fighters:
        by_div[f.get('primary_weight_class', 'Lightweight')].append(f)

    value_signals = []
    for div, fighters in by_div.items():
        top_tier = fighters[:10]
        n = len(top_tier)
        for i in range(n):
            for j in range(i + 1, n):
                f1, f2 = top_tier[i], top_tier[j]
                match_data = compute_detailed_matchup(f1, f2, target_weight_class=div)
                
                vb1 = match_data['fighter1']['value_betting']
                if vb1['ev_pct'] >= min_ev:
                    value_signals.append({
                        'event': f"UFC Simulation: {div}",
                        'date': "Active Contenders",
                        'value_fighter': f1['name'],
                        'opponent': f2['name'],
                        'division': div,
                        'model_prob': match_data['fighter1']['win_probability'],
                        'fair_odds': match_data['fighter1']['odds']['fair']['decimal'],
                        'best_book_odds': match_data['fighter1']['odds']['market_decimal'],
                        'ev_pct': vb1['ev_pct'],
                        'kelly_stake': vb1['kelly_stake_pct'],
                        'tier': vb1['tier'],
                        'edge_drivers': vb1['edge_drivers'],
                        'sportsbooks': {
                            'Consensus Market': {'american': match_data['fighter1']['odds']['vegas_line'], 'decimal': match_data['fighter1']['odds']['market_decimal']}
                        }
                    })

                vb2 = match_data['fighter2']['value_betting']
                if vb2['ev_pct'] >= min_ev:
                    value_signals.append({
                        'event': f"UFC Simulation: {div}",
                        'date': "Active Contenders",
                        'value_fighter': f2['name'],
                        'opponent': f1['name'],
                        'division': div,
                        'model_prob': match_data['fighter2']['win_probability'],
                        'fair_odds': match_data['fighter2']['odds']['fair']['decimal'],
                        'best_book_odds': match_data['fighter2']['odds']['market_decimal'],
                        'ev_pct': vb2['ev_pct'],
                        'kelly_stake': vb2['kelly_stake_pct'],
                        'tier': vb2['tier'],
                        'sportsbooks': {
                            'Consensus Market': {'american': match_data['fighter2']['odds']['vegas_line'], 'decimal': match_data['fighter2']['odds']['market_decimal']}
                        }
                    })

    value_signals.sort(key=lambda x: x['ev_pct'], reverse=True)
    return jsonify({
        'source': 'divisional_simulation',
        'total_opportunities_found': len(value_signals),
        'min_ev_filter': min_ev,
        'signals': value_signals[:limit]
    })

@app.route('/api/ml-benchmarks')
def get_ml_benchmarks():
    reload_cache_if_needed()
    results = _CACHE.get('advanced_results', {})
    return jsonify(results)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"[INFO] Starting UFC Elo Dashboard on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
