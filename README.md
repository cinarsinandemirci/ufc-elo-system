# 🥊 UFC Elo Rating System | 25-Year Algorithmic Analytics Engine

An end-to-end algorithmic **Elo Rating & Fight Analytics System** for UFC fighters, spanning the **entire 25-year modern era (2001–2026, 749 events, 8,515 fights, 2,540 fighters)** with live interactive dashboard and real-time matchup simulation.

---

## ⚡ Core Algorithmic Mechanics

1. **In-Fight Dominance Metric ($-20\%$ to $+20\%$)**:
   - **Strike Differential & Ratio**: Exponential scaling for lopsided striking vs comeback flash KOs.
   - **Knockdowns & Takedowns**: Reward for high-impact damage and control.
   - **Flash KO Dampener**: Lower K-multiplier for fighters who were behind on strikes before a sudden finish.
   - **Decision Margins**: Penalty for razor-thin Split Decisions vs dominant Unanimous Decisions.

2. **Elo Decay (Inactivity Penalty)**:
   - Activates when a fighter has been inactive for **$>18$ months**.
   - Decays rating by **$-5.0$ Elo / month** towards the $1500.0$ baseline, keeping the active championship pool clean while preserving all-time *Peak Elo*.

3. **Glicko-Style Comeback Volatility (Uncertainty Multiplier)**:
   - Scales the return fight K-factor by **$1.0\times$ to $1.60\times$** after long layoffs to rapidly calibrate true current skill level.

4. **Short Notice Replacement Dynamics**:
   - **$+40\%$ Elo Win Bonus** for accepting fights on $\le 14-21$ days notice.
   - **$50\%$ Loss Mitigation** for fighters stepping in without a full camp.

5. **Weight Class Jumps & Inter-Division Dynamics**:
   - **$+15\%$ Win Bonus** per division stepped up.
   - **$30\%$ Size Disadvantage Loss Protection** when losing to naturally larger opponents.

---

## 🚀 Quickstart & Local Setup

```bash
# 1. Clone repository
git clone https://github.com/<your-username>/ufc-elo-system.git
cd ufc-elo-system

# 2. Create virtual environment & install dependencies
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate
pip install -r requirements.txt

# 3. Run dashboard
python app.py
```
Open **`http://localhost:5000`** in your browser.

---

## ☁️ 24/7 Cloud Deployment (Render / Railway)

This repository includes [`render.yaml`](render.yaml) and [`Procfile`](Procfile) for 1-click free cloud hosting:
1. Link this repository to [Render.com](https://render.com).
2. Render will automatically detect the configuration and launch Gunicorn on Python 3.11.

---

## 📊 Dataset Specifications
- **Timeframe**: September 2001 (UFC 33) – August 2026 (UFC 330)
- **Total Events**: 749 Events
- **Total Fights**: 8,515 Bouts
- **Total Fighters**: 2,540 Ranked Fighters
