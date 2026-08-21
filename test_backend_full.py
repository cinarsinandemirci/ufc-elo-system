import json
import os
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

print("==========================================================================================")
print("  UFC ELO RATING & PREDICTIVE ML SYSTEM: FULL BACKEND COMPREHENSIVE TEST SUITE")
print("==========================================================================================")

TOTAL_TESTS = 0
PASSED_TESTS = 0
FAILED_TESTS = 0

def run_assertion(test_name, condition, error_msg=""):
    global TOTAL_TESTS, PASSED_TESTS, FAILED_TESTS
    TOTAL_TESTS += 1
    if condition:
        PASSED_TESTS += 1
        print(f"  [PASS] {test_name}")
        return True
    else:
        FAILED_TESTS += 1
        print(f"  [FAIL] {test_name} - {error_msg}")
        return False

# =========================================================================
# TEST SUITE 1: DATA FILES & SCHEMA INTEGRITY
# =========================================================================
print("\n--- [SUITE 1: DATA FILES & SCHEMA INTEGRITY] ---")

data_files = [
    ("matches.json", 8000, 10000),
    ("fighter_rankings.json", 2000, 3000),
    ("fighter_biometrics.json", 2000, 5000),
    ("fighter_details.json", 1000, 3000),
    ("fighter_component_elos.json", 2000, 3000),
    ("fighter_archetypes.json", 2000, 3000),
    ("fighter_rolling_features.json", 2000, 3000),
    ("bout_rolling_features.json", 8000, 10000),
    ("upcoming_events_with_signals.json", 1, 100),
    ("upcoming_raw_odds.json", 1, 100),
    ("advanced_model_results.json", 1, 10),
    ("all_time_comparison.json", 40, 60),
    ("pedigree_database.json", 10, 100),
]

for filename, min_count, max_count in data_files:
    if run_assertion(f"File exists: {filename}", os.path.exists(filename), f"File {filename} is missing"):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            count = len(data) if isinstance(data, (list, dict)) else 1
            run_assertion(
                f"Data volume check: {filename} (count: {count})",
                min_count <= count <= max_count or (isinstance(data, dict) and count >= min_count),
                f"Unexpected item count {count} (expected {min_count}-{max_count})"
            )
        except Exception as e:
            run_assertion(f"JSON Parseable: {filename}", False, str(e))

# =========================================================================
# TEST SUITE 2: ELO & BIOMETRIC NUMERICAL VALIDITY
# =========================================================================
print("\n--- [SUITE 2: ELO & BIOMETRIC NUMERICAL VALIDITY] ---")

with open('fighter_rankings.json', 'r', encoding='utf-8') as f:
    rankings = json.load(f)

with open('fighter_component_elos.json', 'r', encoding='utf-8') as f:
    comp_elos = json.load(f)

with open('fighter_archetypes.json', 'r', encoding='utf-8') as f:
    archetypes = json.load(f)

elo_values_valid = True
peak_gte_current = True
records_valid = True
no_nans_in_elos = True

for f in rankings:
    elo = f.get('elo')
    peak = f.get('peak_elo')
    w = f.get('wins', 0)
    l = f.get('losses', 0)
    
    if elo is None or peak is None or np.isnan(elo) or np.isnan(peak):
        no_nans_in_elos = False
    if not (1000.0 <= elo <= 2300.0):
        elo_values_valid = False
    if peak < elo - 1e-4:
        peak_gte_current = False
    if w < 0 or l < 0:
        records_valid = False

run_assertion("All fighter Elos are finite non-NaN floats", no_nans_in_elos)
run_assertion("Elo values within plausible boundaries (1000.0 - 2300.0)", elo_values_valid)
run_assertion("Peak Elo is always >= Current Elo for all fighters", peak_gte_current)
run_assertion("Fight win/loss records are non-negative integers", records_valid)

comp_valid = True
for name, c in comp_elos.items():
    s = c.get('striking_elo', 0)
    g = c.get('grappling_elo', 0)
    card = c.get('cardio_elo', 0)
    if not (1100 <= s <= 2200 and 1100 <= g <= 2200 and 1100 <= card <= 2200):
        comp_valid = False
        break
run_assertion("3D Component Elos (Striking, Grappling, Cardio) are well-scaled", comp_valid)

arch_valid = True
valid_archetypes = {
    'Pressure Wrestler', 'Sprawl-and-Brawler', 'Submission Hunter',
    'Distance Out-Fighter', 'Inside Pressure Boxer', 'Clinch Grinder'
}
for name, a in archetypes.items():
    if a.get('archetype') not in valid_archetypes:
        arch_valid = False
        break
run_assertion("Fighter tactical archetypes adhere to the 6 valid categories", arch_valid)

# =========================================================================
# TEST SUITE 3: METHOD OF VICTORY ENGINE PROBABILITY CALIBRATION
# =========================================================================
print("\n--- [SUITE 3: METHOD OF VICTORY & PROPS LOGICAL CONSISTENCY] ---")

from method_of_victory_engine import MethodOfVictoryPredictor
mov_engine = MethodOfVictoryPredictor()

test_pairs = [
    ("Islam Makhachev", "Arman Tsarukyan", 0.65, "Lightweight"),
    ("Jon Jones", "Stipe Miocic", 0.72, "Heavyweight"),
    ("Alexander Volkanovski", "Ilia Topuria", 0.48, "Featherweight"),
    ("Alexandre Pantoja", "Brandon Royval", 0.60, "Flyweight"),
    ("Alex Pereira", "Magomed Ankalaev", 0.52, "Light Heavyweight")
]

props_valid = True
for f1, f2, p1, div in test_pairs:
    res = mov_engine.predict_detailed_props(f1, f2, p1, div)
    
    f1_m = res['f1_methods']
    f1_sum = f1_m['ko_tko'] + f1_m['submission'] + f1_m['decision']
    if abs(f1_sum - res['f1_win_prob']) > 1.0:
        props_valid = False

    f2_m = res['f2_methods']
    f2_sum = f2_m['ko_tko'] + f2_m['submission'] + f2_m['decision']
    if abs(f2_sum - res['f2_win_prob']) > 1.0:
        props_valid = False

    tot = f1_sum + f2_sum
    if abs(tot - 100.0) > 1.5:
        props_valid = False

    rp = res['round_props']
    if not (0 < rp['over_1_5_prob'] < 100 and 0 < rp['over_2_5_prob'] < 100 and 0 < rp['goes_distance_prob'] < 100):
        props_valid = False

run_assertion("Method of Victory probabilities partition cleanly across all test pairs", props_valid)

# Pedigree Engine Verification
from pedigree_engine import PedigreeCalibrationEngine
ped_engine = PedigreeCalibrationEngine()
gable_test = ped_engine.calibrate_fighter_ratings("Gable Steveson", 1500.0, 0)
islam_test = ped_engine.calibrate_fighter_ratings("Islam Makhachev", 1864.0, 16)

run_assertion("Gable Steveson correctly receives 1650 Prior Elo & 1820 Grappling Anchor", gable_test['effective_elo'] == 1650.0 and gable_test['comp_elos']['grappling_elo'] == 1820.0)
run_assertion("Islam Makhachev (16 fights) has alpha=0.0 and 0.00% pedigree inflation", islam_test['effective_elo'] == 1864.0 and islam_test['alpha_decay'] == 0.0)

# =========================================================================
# TEST SUITE 4: LIVE FLASK BACKEND REST API ENDPOINTS
# =========================================================================
print("\n--- [SUITE 4: LIVE FLASK BACKEND REST API ENDPOINTS] ---")

BASE_URL = "http://127.0.0.1:5000"

def get_api(endpoint, timeout=10):
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Backend-Test-Suite'})
    start = time.time()
    resp = urllib.request.urlopen(req, timeout=timeout)
    elapsed = time.time() - start
    data = json.loads(resp.read().decode('utf-8'))
    return resp.status, data, elapsed

# 1. /api/stats
try:
    status, data, elapsed = get_api('/api/stats')
    run_assertion("API /api/stats returns 200 OK", status == 200)
    run_assertion(f"/api/stats payload valid (Total matches: {data.get('total_matches')}, Response: {elapsed*1000:.1f}ms)", data.get('total_matches') >= 8000)
except Exception as e:
    run_assertion("API /api/stats accessible", False, str(e))

# 2. /api/weight-classes
try:
    status, data, elapsed = get_api('/api/weight-classes')
    run_assertion("API /api/weight-classes returns 200 OK", status == 200)
    run_assertion(f"/api/weight-classes returns all UFC weight classes (count: {len(data)})", len(data) >= 11)
except Exception as e:
    run_assertion("API /api/weight-classes accessible", False, str(e))

# 3. /api/rankings
try:
    status, data, elapsed = get_api('/api/rankings?weight_class=all&sort_by=elo&min_fights=3&active_only=true')
    run_assertion("API /api/rankings returns 200 OK", status == 200)
    fighters = data.get('fighters', [])
    run_assertion(f"/api/rankings returns populated list (count: {len(fighters)}, Response: {elapsed*1000:.1f}ms)", len(fighters) >= 50)
    top_p4p = fighters[0]['name'] if fighters else ''
    run_assertion(f"/api/rankings #1 P4P fighter: {top_p4p}", len(top_p4p) > 0)
except Exception as e:
    run_assertion("API /api/rankings accessible", False, str(e))

# 4. /api/fighter/<name>
try:
    status, data, elapsed = get_api('/api/fighter/Islam%20Makhachev')
    run_assertion("API /api/fighter/Islam Makhachev returns 200 OK", status == 200)
    run_assertion("Fighter profile has biometrics, fights_history, and methods", 'biometrics' in data and 'fights_history' in data and 'methods' in data)
except Exception as e:
    run_assertion("API /api/fighter accessible", False, str(e))

# 5. /api/matchup (Phase 1, 2, 3 simulation)
try:
    status, data, elapsed = get_api('/api/matchup?f1=Jon%20Jones&f2=Stipe%20Miocic&weight_class=Heavyweight')
    run_assertion("API /api/matchup returns 200 OK", status == 200)
    
    f1_res = data.get('fighter1', {})
    f2_res = data.get('fighter2', {})
    bout_ctx = data.get('bout_context', {})
    
    has_archetypes = bool(f1_res.get('archetype') and f2_res.get('archetype'))
    has_methods = bool(f1_res.get('methods') and f2_res.get('methods'))
    has_props = bool(bout_ctx.get('round_props'))
    has_value_signal = 'value_betting' in f1_res
    
    run_assertion(f"/api/matchup returns Archetypes ({f1_res.get('archetype')} vs {f2_res.get('archetype')})", has_archetypes)
    run_assertion("/api/matchup returns Phase 3 Method of Victory breakdown", has_methods)
    run_assertion("/api/matchup returns Phase 3 Round Props (Over/Under/Distance)", has_props)
    run_assertion("/api/matchup returns +EV Quantitative Value Signal & Kelly Stake", has_value_signal)
    run_assertion(f"/api/matchup calculation latency: {elapsed*1000:.1f}ms (< 50ms target)", elapsed < 0.050)
except Exception as e:
    run_assertion("API /api/matchup accessible", False, str(e))

# 6. /api/upcoming-cards
try:
    status, data, elapsed = get_api('/api/upcoming-cards')
    run_assertion("API /api/upcoming-cards returns 200 OK", status == 200)
    events = data.get('events', [])
    run_assertion(f"/api/upcoming-cards returns future UFC cards (count: {len(events)})", len(events) >= 3)
except Exception as e:
    run_assertion("API /api/upcoming-cards accessible", False, str(e))

# 7. /api/value-bets (upcoming and divisional modes)
try:
    status1, data1, elapsed1 = get_api('/api/value-bets?source=upcoming&min_ev=3.0')
    run_assertion("API /api/value-bets (upcoming mode) returns 200 OK", status1 == 200)
    run_assertion(f"Upcoming +EV opportunities found: {data1.get('total_opportunities_found')}", data1.get('total_opportunities_found', 0) > 0)

    status2, data2, elapsed2 = get_api('/api/value-bets?source=divisional&min_ev=3.0')
    run_assertion("API /api/value-bets (divisional mode) returns 200 OK", status2 == 200)
    run_assertion(f"Divisional +EV opportunities found: {data2.get('total_opportunities_found')}", data2.get('total_opportunities_found', 0) > 0)
except Exception as e:
    run_assertion("API /api/value-bets accessible", False, str(e))

# 8. /api/ml-benchmarks
try:
    status, data, elapsed = get_api('/api/ml-benchmarks')
    run_assertion("API /api/ml-benchmarks returns 200 OK", status == 200)
    models = data.get('benchmark_models', [])
    run_assertion(f"/api/ml-benchmarks contains Phase 2 models ({len(models)} architectures)", len(models) >= 4)
    run_assertion("Walk-forward evaluated bouts count >= 5,000", data.get('total_evaluated_bouts', 0) >= 5000)
except Exception as e:
    run_assertion("API /api/ml-benchmarks accessible", False, str(e))

# =========================================================================
# TEST SUITE 5: EDGE CASES & EXTREME STRESS TESTING
# =========================================================================
print("\n--- [SUITE 5: EDGE CASES & ROBUSTNESS STRESS TESTING] ---")

edge_case_queries = [
    ("/api/matchup?f1=Alexandre%20Pantoja&f2=Jon%20Jones", "Cross-weight class huge size gap"),
    ("/api/matchup?f1=Royce%20Gracie&f2=Ken%20Shamrock", "Historical early-era fighters with sparse metrics"),
    ("/api/matchup?f1=Georges%20St-Pierre&f2=Islam%20Makhachev", "Retired legend vs active champion decay handling"),
    ("/api/matchup?f1=Islam%20Makhachev&f2=Islam%20Makhachev", "Self-matchup symmetry"),
    ("/api/matchup?f1=%20%20isLam%20mAKhachev%20%20&f2=ARMAN%20tsarukyan", "Whitespace and case variation")
]

edge_passed = True
for endpoint, desc in edge_case_queries:
    try:
        status, data, elapsed = get_api(endpoint)
        if status != 200 or 'error' in data:
            edge_passed = False
            print(f"    [FAIL] Edge case: {desc} (Status: {status})")
        else:
            print(f"    [PASS] Edge case: {desc} (Status: {status}, Latency: {elapsed*1000:.1f}ms)")
    except Exception as e:
        edge_passed = False
        print(f"    [FAIL] Edge case: {desc} - {str(e)}")

run_assertion("All 5 extreme edge cases & stress simulations handled robustly without crashing", edge_passed)

# =========================================================================
# FINAL TEST REPORT
# =========================================================================
print("\n==========================================================================================")
print("  TEST SUMMARY REPORT")
print("==========================================================================================")
print(f"  TOTAL ASSERTIONS EXECUTED : {TOTAL_TESTS}")
print(f"  PASSED                    : {PASSED_TESTS} ({PASSED_TESTS/TOTAL_TESTS*100:.1f}%)")
print(f"  FAILED                    : {FAILED_TESTS}")
print("==========================================================================================")

if FAILED_TESTS == 0:
    print("✨ ALL BACKEND TESTS PASSED WITH 100% INTEGRITY!\n")
else:
    print(f"⚠️ {FAILED_TESTS} TEST(S) FAILED. Please review the output above.\n")
    sys.exit(1)
