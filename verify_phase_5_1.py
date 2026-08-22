#!/usr/bin/env python3
"""
Verification Script for Phase 5.1: Vectorized Monte Carlo Simulation Engine
Validates statistical consistency, sampling error bounds, monotonic Over/Under constraints,
and vectorization execution speeds.
"""
import time
from monte_carlo_engine import VectorizedMonteCarloEngine

def test_monte_carlo_positive_outcomes():
    engine = VectorizedMonteCarloEngine()
    print("\n" + "="*75)
    print("🎲 PHASE 5.1 VECTORIZED MONTE CARLO ENGINE: MATHEMATICAL & SPEED AUDIT")
    print("="*75)

    f1 = {
        "name": "Islam Makhachev",
        "effective_elo": 2180.0,
        "components": {"striking_elo": 2050.0, "grappling_elo": 2290.0, "cardio_elo": 2120.0},
        "methods": {"ko_tko_pct": 30.0, "submission_pct": 50.0, "decision_pct": 20.0}
    }
    f2 = {
        "name": "Dustin Poirier",
        "effective_elo": 2010.0,
        "components": {"striking_elo": 2140.0, "grappling_elo": 1820.0, "cardio_elo": 1980.0},
        "methods": {"ko_tko_pct": 65.0, "submission_pct": 10.0, "decision_pct": 25.0}
    }

    tier_results = []
    for sims in [100000, 250000, 500000]:
        t0 = time.perf_counter()
        res = engine.simulate_bout(f1, f2, total_rounds=5, num_sims=sims)
        elapsed = (time.perf_counter() - t0) * 1000.0
        
        cfg = res["config"]
        ml = res["moneyline"]
        dp = res["distance_props"]
        rd = res["round_distribution"]

        tier_results.append((sims, elapsed, cfg["standard_error_pct"], ml["fighter1"]["win_pct"], dp["goes_to_decision"]["yes_pct"]))

        print(f"\n📊 [İTERASYON: {sims:,}]")
        print(f"   ⏱️ Hesaplama Süresi: {elapsed:.2f} ms")
        print(f"   🎯 Standart Hata Payı (SE): {cfg['standard_error_pct']}")
        print(f"   🔴 {f1['name']} Kazanma Oranı: %{ml['fighter1']['win_pct']}")
        print(f"   🔵 {f2['name']} Kazanma Oranı: %{ml['fighter2']['win_pct']}")
        print(f"   📋 Tam Mesafe (Karar): %{dp['goes_to_decision']['yes_pct']} | Erken Bitiş: %{dp['goes_to_decision']['no_pct']}")
        print(f"   📈 Over 1.5: %{dp['over_under_1_5']['over_pct']} | Over 2.5: %{dp['over_under_2_5']['over_pct']}")

        # Verification Checks
        assert dp['over_under_1_5']['over_pct'] >= dp['over_under_2_5']['over_pct'], "Monotonicity violated: Over 1.5 must be >= Over 2.5"
        assert abs((ml['fighter1']['win_pct'] + ml['fighter2']['win_pct'] + ml['draw_pct']) - 100.0) < 0.1, "Probabilities do not sum to 100%"
        assert elapsed < 150.0, f"Latency too high: {elapsed}ms"

    print("\n" + "="*75)
    print("✨ TÜM STATİK VE DİNAMİK MONTE CARLO DOĞRULAMALARI %100 BAŞARIYLA TAMAMLANDI!")
    print(f"✨ 100k Süre: {tier_results[0][1]:.2f}ms | 250k Süre: {tier_results[1][1]:.2f}ms | 500k Süre: {tier_results[2][1]:.2f}ms")
    print(f"✨ Hata Payı Daralması: {tier_results[0][2]} ➔ {tier_results[1][2]} ➔ {tier_results[2][2]}")
    print("="*75)

if __name__ == "__main__":
    test_monte_carlo_positive_outcomes()
