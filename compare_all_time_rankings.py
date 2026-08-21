import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('fighter_rankings.json', 'r', encoding='utf-8') as f:
    rankings = json.load(f)

# Top 50 by Peak Elo in our Algorithm
by_peak = sorted(rankings, key=lambda x: x['peak_elo'], reverse=True)[:50]

print("=== OUR 25-YEAR ALGORITHMIC PEAK ELO TOP 50 ===")
for idx, f in enumerate(by_peak, 1):
    print(f"{idx:2d}. {f['name']:25s} | Peak Elo: {f['peak_elo']:6.1f} | Curr: {f['elo']:6.1f} | {f['wins']}W-{f['losses']}L | {f.get('primary_weight_class', 'N/A')}")

