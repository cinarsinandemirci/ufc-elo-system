import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('all_time_comparison.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Sort by biggest positive discrepancy (Algo ranks much higher than consensus)
higher_in_algo = sorted([d for d in data if d['diff'] > 0 and d['algo_rank'] < 999], key=lambda x: x['diff'], reverse=True)
print("=== BIGGEST POSITIVE DISCREPANCIES (ALGORITHM RANKS HIGHER) ===")
for d in higher_in_algo[:10]:
    print(f"{d['name']:22s} | Consensus: #{d['consensus_rank']:2d} -> Algo: #{d['algo_rank']:2d} (Δ +{d['diff']:2d}) | Peak Elo: {d['peak_elo']:.1f} | Rec: {d['record']}")

# Sort by biggest negative discrepancy (Consensus ranks much higher than algorithm)
lower_in_algo = sorted([d for d in data if d['diff'] < 0], key=lambda x: x['diff'])
print("\n=== BIGGEST NEGATIVE DISCREPANCIES (CONSENSUS RANKS HIGHER) ===")
for d in lower_in_algo[:10]:
    print(f"{d['name']:22s} | Consensus: #{d['consensus_rank']:2d} -> Algo: #{d['algo_rank']:2d} (Δ {d['diff']:3d}) | Peak Elo: {d['peak_elo']:.1f} | Rec: {d['record']}")

