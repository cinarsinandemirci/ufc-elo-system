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

    f1 = _CACHE['fighters_by_name'].get(f1_name)
    f2 = _CACHE['fighters_by_name'].get(f2_name)

    if not f1 or not f2:
        return jsonify({'error': 'One or both fighters not found'}), 400

    r1 = f1['elo']
    r2 = f2['elo']

    prob1 = 1.0 / (1.0 + 10.0 ** ((r2 - r1) / 400.0))
    prob2 = 1.0 - prob1

    k_base = 32.0 * (1.2 if is_title else 1.0)
    u1 = f1.get('uncertainty_mult', 1.0)
    u2 = f2.get('uncertainty_mult', 1.0)

    f1_dec_delta = round((k_base * 1.0 * u1) * (1.0 - prob1), 1)
    f1_dom_fin_delta = round((k_base * 1.5 * 1.2 * u1) * (1.0 - prob1), 1)
    
    f2_dec_delta = round((k_base * 1.0 * u2) * (1.0 - prob2), 1)
    f2_dom_fin_delta = round((k_base * 1.5 * 1.2 * u2) * (1.0 - prob2), 1)

    return jsonify({
        'fighter1': {
            'name': f1['name'],
            'elo': f1['elo'],
            'peak_elo': f1['peak_elo'],
            'win_probability': round(prob1 * 100, 1),
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
            'peak_elo': f2['peak_elo'],
            'win_probability': round(prob2 * 100, 1),
            'win_by_decision_delta': f2_dec_delta,
            'win_by_finish_delta': f2_dom_fin_delta,
            'weight_class': f2['primary_weight_class'],
            'is_active': f2.get('is_active', True),
            'months_inactive': f2.get('months_inactive', 0.0),
            'uncertainty_mult': u2
        },
        'is_title': is_title
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"[INFO] Starting UFC Elo Dashboard on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
