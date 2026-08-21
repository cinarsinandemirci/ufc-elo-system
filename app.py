import os
import json
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
RANKINGS_FILE = os.path.join(DATA_DIR, "fighter_rankings.json")
MATCHES_FILE = os.path.join(DATA_DIR, "matches.json")
HISTORY_FILE = os.path.join(DATA_DIR, "elo_history.json")

# In-Memory Cache Store
_CACHE = {
    'rankings': [],
    'fighters_by_name': {},
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
        print("[CACHE] Loading rankings and precomputing statistics into memory...", flush=True)
        with open(RANKINGS_FILE, 'r', encoding='utf-8') as f:
            rankings = json.load(f)
            
        matches = []
        if os.path.exists(MATCHES_FILE):
            with open(MATCHES_FILE, 'r', encoding='utf-8') as f:
                matches = json.load(f)

        _CACHE['rankings'] = rankings
        _CACHE['fighters_by_name'] = {f['name'].lower(): f for f in rankings}
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
    f = _CACHE['fighters_by_name'].get(fighter_name.strip().lower())
    if f:
        return jsonify(f)
    return jsonify({'error': 'Fighter not found'}), 404

@app.route('/api/matchup')
def simulate_matchup():
    reload_cache_if_needed()
    f1_name = request.args.get('f1', '').strip().lower()
    f2_name = request.args.get('f2', '').strip().lower()
    is_title = request.args.get('is_title', 'false').lower() == 'true'
    target_weight_class = request.args.get('weight_class', 'auto').strip()

    f1 = _CACHE['fighters_by_name'].get(f1_name)
    f2 = _CACHE['fighters_by_name'].get(f2_name)

    if not f1 or not f2:
        return jsonify({'error': 'One or both fighters not found'}), 400

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
        # Find division name for this tier
        target_div_name = next((k for k, v in div_hierarchy.items() if v == target_tier and not k.startswith("Women")), f1.get('primary_weight_class'))
    else:
        target_tier = div_hierarchy.get(target_weight_class, max(t1, t2))
        target_div_name = target_weight_class

    # 1. Weight Class Jump, Size & Reach Frame Adjustment
    size_adj_1 = 0.0
    size_adj_2 = 0.0

    f1_all_wc = f1.get('all_weight_classes', [])
    f2_all_wc = f2.get('all_weight_classes', [])
    f1_exp_at_target = 1 if target_div_name in f1_all_wc else 0
    f2_exp_at_target = 1 if target_div_name in f2_all_wc else 0

    if target_tier > t1:
        tier_gap = target_tier - t1
        base_pen = tier_gap * 35.0
        if f1_exp_at_target: base_pen *= 0.5 # Acclimated multi-division fighter
        size_adj_1 = -base_pen

    if target_tier > t2:
        tier_gap = target_tier - t2
        base_pen = tier_gap * 35.0
        if f2_exp_at_target: base_pen *= 0.5
        size_adj_2 = -base_pen

    eff_elo_1 = f1['elo'] + size_adj_1
    eff_elo_2 = f2['elo'] + size_adj_2

    # 2. Stylistic Grappling vs Striking Clash
    f1_fights = max(1, f1.get('total_fights', 1))
    f2_fights = max(1, f2.get('total_fights', 1))
    f1_wins = max(1, f1.get('wins', 1))
    f2_wins = max(1, f2.get('wins', 1))

    g1 = (f1.get('total_td', 0) / f1_fights) * 1.5 + (f1['methods'].get('SUB_win', 0) / f1_wins) * 10.0
    g2 = (f2.get('total_td', 0) / f2_fights) * 1.5 + (f2['methods'].get('SUB_win', 0) / f2_wins) * 10.0

    s1 = (f1.get('total_sig_str', 0) / f1_fights) * 0.08 + (f1.get('total_kd', 0) / f1_fights) * 6.0 + (f1['methods'].get('KO/TKO_win', 0) / f1_wins) * 8.0
    s2 = (f2.get('total_sig_str', 0) / f2_fights) * 0.08 + (f2.get('total_kd', 0) / f2_fights) * 6.0 + (f2['methods'].get('KO/TKO_win', 0) / f2_wins) * 8.0

    style_shift = 0.0
    if g1 > g2 + 4.0:
        style_shift += min(25.0, (g1 - g2) * 2.5)
    elif g2 > g1 + 4.0:
        style_shift -= min(25.0, (g2 - g1) * 2.5)

    eff_elo_1 += style_shift

    # 3. Bradley-Terry Win Probabilities
    prob1 = 1.0 / (1.0 + 10.0 ** ((eff_elo_2 - eff_elo_1) / 400.0))
    prob2 = 1.0 - prob1

    # 4. Finish Method Probability Distribution
    f1_ko_ratio = f1['methods'].get('KO/TKO_win', 0) / f1_wins
    f1_sub_ratio = f1['methods'].get('SUB_win', 0) / f1_wins
    f1_dec_ratio = (f1['methods'].get('DEC_win', 0) + f1['methods'].get('OTHER_win', 0)) / f1_wins

    f2_losses = max(1, f2.get('losses', 1))
    f2_ko_vuln = (f2['methods'].get('KO/TKO_loss', 0) + 0.5) / (f2_losses + 1.5)
    f2_sub_vuln = (f2['methods'].get('SUB_loss', 0) + 0.5) / (f2_losses + 1.5)

    f1_ko_w = f1_ko_ratio * (0.8 + 0.4 * f2_ko_vuln)
    f1_sub_w = f1_sub_ratio * (0.8 + 0.4 * f2_sub_vuln)
    f1_dec_w = f1_dec_ratio * 1.0
    f1_tot_w = (f1_ko_w + f1_sub_w + f1_dec_w) or 1.0

    f1_ko_pct = round(prob1 * (f1_ko_w / f1_tot_w) * 100, 1)
    f1_sub_pct = round(prob1 * (f1_sub_w / f1_tot_w) * 100, 1)
    f1_dec_pct = round(prob1 * (f1_dec_w / f1_tot_w) * 100, 1)

    f2_ko_ratio = f2['methods'].get('KO/TKO_win', 0) / f2_wins
    f2_sub_ratio = f2['methods'].get('SUB_win', 0) / f2_wins
    f2_dec_ratio = (f2['methods'].get('DEC_win', 0) + f2['methods'].get('OTHER_win', 0)) / f2_wins

    f1_losses = max(1, f1.get('losses', 1))
    f1_ko_vuln = (f1['methods'].get('KO/TKO_loss', 0) + 0.5) / (f1_losses + 1.5)
    f1_sub_vuln = (f1['methods'].get('SUB_loss', 0) + 0.5) / (f1_losses + 1.5)

    f2_ko_w = f2_ko_ratio * (0.8 + 0.4 * f1_ko_vuln)
    f2_sub_w = f2_sub_ratio * (0.8 + 0.4 * f1_sub_vuln)
    f2_dec_w = f2_dec_ratio * 1.0
    f2_tot_w = (f2_ko_w + f2_sub_w + f2_dec_w) or 1.0

    f2_ko_pct = round(prob2 * (f2_ko_w / f2_tot_w) * 100, 1)
    f2_sub_pct = round(prob2 * (f2_sub_w / f2_tot_w) * 100, 1)
    f2_dec_pct = round(prob2 * (f2_dec_w / f2_tot_w) * 100, 1)

    # Over / Under 2.5 Rounds
    tot_finish = (f1_ko_pct + f1_sub_pct + f2_ko_pct + f2_sub_pct) / 100.0
    under_2_5 = round(min(85.0, max(15.0, tot_finish * 75.0)), 1)
    over_2_5 = round(100.0 - under_2_5, 1)

    # Elo Delta Stakes
    k_base = 32.0 * (1.2 if is_title else 1.0)
    u1 = f1.get('uncertainty_mult', 1.0)
    u2 = f2.get('uncertainty_mult', 1.0)

    f1_dec_delta = round((k_base * 1.0 * u1) * (1.0 - prob1), 1)
    f1_dom_fin_delta = round((k_base * 1.5 * 1.2 * u1) * (1.0 - prob1), 1)
    f2_dec_delta = round((k_base * 1.0 * u2) * (1.0 - prob2), 1)
    f2_dom_fin_delta = round((k_base * 1.5 * 1.2 * u2) * (1.0 - prob2), 1)

    # Helper for UFC Betting Odds Conversions
    def to_odds(p):
        p_safe = max(0.005, min(0.995, p))
        # Fair American
        if p_safe >= 0.5:
            american_fair = f"-{round((p_safe / (1.0 - p_safe)) * 100)}"
        else:
            american_fair = f"+{round(((1.0 - p_safe) / p_safe) * 100)}"
        
        # Decimal Odds
        decimal_fair = round(1.0 / p_safe, 2)
        
        return {
            'american': american_fair,
            'decimal': decimal_fair,
            'implied_prob': round(p_safe * 100, 1)
        }

    # Vegas Bookmaker Lines with standard 4.5% market vig
    def to_vegas_odds(p_w, p_l):
        # Apply ~4.5% total overround
        vig_mult = 1.045
        p1_vig = (p_w * vig_mult) / (p_w + p_l)
        p2_vig = (p_l * vig_mult) / (p_w + p_l)
        
        o1 = to_odds(p1_vig / vig_mult) # fair
        o2 = to_odds(p2_vig / vig_mult)
        
        # Vegas adjusted lines
        if p_w >= 0.5:
            v1 = f"-{round((p1_vig / (1.0 - p1_vig + 0.0001)) * 100)}"
            v2 = f"+{round(((1.0 - p2_vig + 0.0001) / p2_vig) * 100)}"
        else:
            v1 = f"+{round(((1.0 - p1_vig + 0.0001) / p1_vig) * 100)}"
            v2 = f"-{round((p2_vig / (1.0 - p2_vig + 0.0001)) * 100)}"
            
        return v1, v2

    v1_line, v2_line = to_vegas_odds(prob1, prob2)

    # Prop Bet Odds
    props = {
        'over_2_5_rounds': to_odds(over_2_5 / 100.0),
        'under_2_5_rounds': to_odds(under_2_5 / 100.0),
        'f1_ko_tko': to_odds(f1_ko_pct / 100.0),
        'f1_submission': to_odds(f1_sub_pct / 100.0),
        'f1_decision': to_odds(f1_dec_pct / 100.0),
        'f2_ko_tko': to_odds(f2_ko_pct / 100.0),
        'f2_submission': to_odds(f2_sub_pct / 100.0),
        'f2_decision': to_odds(f2_dec_pct / 100.0)
    }

    return jsonify({
        'bout_context': {
            'simulated_weight_class': target_div_name,
            'is_title': is_title,
            'style_shift': round(style_shift, 1),
            'over_2_5_rounds': over_2_5,
            'under_2_5_rounds': under_2_5,
            'props': props
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
            'odds': {
                'fair': to_odds(prob1),
                'vegas_line': v1_line
            },
            'methods': {
                'ko_tko_pct': f1_ko_pct,
                'submission_pct': f1_sub_pct,
                'decision_pct': f1_dec_pct
            },
            'win_by_decision_delta': f1_dec_delta,
            'win_by_finish_delta': f1_dom_fin_delta,
            'weight_class': f1['primary_weight_class'],
            'is_active': f1.get('is_active', True),
            'months_inactive': f1.get('months_inactive', 0.0),
            'uncertainty_mult': u1
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
            'odds': {
                'fair': to_odds(prob2),
                'vegas_line': v2_line
            },
            'methods': {
                'ko_tko_pct': f2_ko_pct,
                'submission_pct': f2_sub_pct,
                'decision_pct': f2_dec_pct
            },
            'win_by_decision_delta': f2_dec_delta,
            'win_by_finish_delta': f2_dom_fin_delta,
            'weight_class': f2['primary_weight_class'],
            'is_active': f2.get('is_active', True),
            'months_inactive': f2.get('months_inactive', 0.0),
            'uncertainty_mult': u2
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"[INFO] Starting UFC Elo Dashboard on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
