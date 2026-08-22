#!/usr/bin/env python3
"""
UFC Elo & Predictive Value Engine - Phase 4.3: Camp Quality & Head Coach Matrix
--------------------------------------------------------------------------------
Models the profound tactical and physical impact of MMA training camps,
head coaches (Javier Mendez, Eugene Bareman, Trevor Wittman, Mike Brown, etc.),
sparring partner depth, and style-camp gameplan synergies.
"""

import os
import sys
import json

# Ensure stdout uses utf-8 on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GYM_DB_FILE = os.path.join(BASE_DIR, "gym_and_coaches_database.json")

class CampAndCoachEngine:
    def __init__(self, db_path=GYM_DB_FILE):
        self.db_path = db_path
        self.gyms = {}
        self.fighter_gym_map = {}
        self.load_database()

    def load_database(self):
        if not os.path.exists(self.db_path):
            print(f"[WARN] Gym database not found at {self.db_path}. Initializing empty.")
            return

        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.gyms = data.get("gyms", {})

            # Build inverted mapping for fast fighter lookup
            for gym_key, gym_data in self.gyms.items():
                for fighter_name in gym_data.get("roster", []):
                    clean_name = fighter_name.strip().lower()
                    self.fighter_gym_map[clean_name] = gym_data
        except Exception as e:
            print(f"[ERROR] Failed to load gym database: {e}")

    def get_fighter_camp(self, fighter_name):
        """Finds fighter's gym and head coach using exact and partial name matching."""
        if not fighter_name:
            return self.get_default_camp("Unknown Fighter")

        clean_name = fighter_name.strip().lower()

        # 1. Exact match
        if clean_name in self.fighter_gym_map:
            return self.fighter_gym_map[clean_name]

        # 2. Partial match in roster
        for gym_key, gym_data in self.gyms.items():
            for member in gym_data.get("roster", []):
                m_clean = member.lower()
                if clean_name in m_clean or m_clean in clean_name:
                    return gym_data

        # 3. Regional / Independent fallback
        return self.get_default_camp(fighter_name)

    def get_default_camp(self, fighter_name):
        """Returns standard regional gym profile."""
        reg = self.gyms.get("Universal Independent / Regional Gym", {})
        if reg:
            return reg
        return {
            "id": "regional",
            "name": "Regional / Independent Camp",
            "head_coach": "Regional MMA Staff",
            "location": "Local Training Center",
            "tier": "Regional",
            "rating_bonus": 5.0,
            "gameplan_execution": 1.00,
            "specialties": ["Standard MMA Fundamentals"],
            "synergy_archetypes": [],
            "title_fight_win_rate": 35.0,
            "roster": []
        }

    def evaluate_camp_matchup(self, f1_name, f2_name, f1_archetype="Universal Balanced", f2_archetype="Universal Balanced"):
        """
        Evaluates the head-to-head camp, head coach tactical pedigree,
        and archetype-camp synergy between two fighters.
        """
        camp1 = self.get_fighter_camp(f1_name)
        camp2 = self.get_fighter_camp(f2_name)

        r1 = camp1.get("rating_bonus", 5.0)
        r2 = camp2.get("rating_bonus", 5.0)

        # Style-Camp Synergy Bonus
        synergy1_active = False
        synergy1_bonus = 0.0
        if f1_archetype in camp1.get("synergy_archetypes", []):
            synergy1_active = True
            synergy1_bonus = 15.0

        synergy2_active = False
        synergy2_bonus = 0.0
        if f2_archetype in camp2.get("synergy_archetypes", []):
            synergy2_active = True
            synergy2_bonus = 15.0

        total_rating_1 = r1 + synergy1_bonus
        total_rating_2 = r2 + synergy2_bonus

        delta_rating = total_rating_1 - total_rating_2
        # Win probability swing (-10% to +10%)
        prob_swing_pct = round((delta_rating / 400.0) * 100.0 * 0.35, 2)

        if delta_rating >= 10.0:
            adv_side = f1_name
            adv_tier = f"{camp1.get('name')} ({camp1.get('tier')})"
        elif delta_rating <= -10.0:
            adv_side = f2_name
            adv_tier = f"{camp2.get('name')} ({camp2.get('tier')})"
        else:
            adv_side = "Neutral"
            adv_tier = "Dengeli Kamp Seviyesi"

        # Generate insightful tactical narrative
        breakdown_points = []
        if synergy1_active:
            breakdown_points.append(f"{f1_name}: {camp1.get('name')} ile '{f1_archetype}' stili arasında %100 taktiksel uyum (+15 Elo).")
        if synergy2_active:
            breakdown_points.append(f"{f2_name}: {camp2.get('name')} ile '{f2_archetype}' stili arasında %100 taktiksel uyum (+15 Elo).")

        if camp1.get("tier") == "S-Tier" and camp2.get("tier") != "S-Tier":
            breakdown_points.append(f"{camp1.get('head_coach')} yönetimindeki şampiyonluk hazırlık tecrübesi ({camp1.get('title_fight_win_rate')}% unvan maçı galibiyeti) belirgin avantaj sağlar.")
        elif camp2.get("tier") == "S-Tier" and camp1.get("tier") != "S-Tier":
            breakdown_points.append(f"{camp2.get('head_coach')} yönetimindeki şampiyonluk hazırlık tecrübesi ({camp2.get('title_fight_win_rate')}% unvan maçı galibiyeti) belirgin avantaj sağlar.")

        return {
            "fighter1": {
                "name": f1_name,
                "camp_name": camp1.get("name"),
                "head_coach": camp1.get("head_coach"),
                "location": camp1.get("location"),
                "tier": camp1.get("tier"),
                "base_rating_bonus": r1,
                "synergy_active": synergy1_active,
                "synergy_bonus": synergy1_bonus,
                "total_camp_score": total_rating_1,
                "specialties": camp1.get("specialties", [])
            },
            "fighter2": {
                "name": f2_name,
                "camp_name": camp2.get("name"),
                "head_coach": camp2.get("head_coach"),
                "location": camp2.get("location"),
                "tier": camp2.get("tier"),
                "base_rating_bonus": r2,
                "synergy_active": synergy2_active,
                "synergy_bonus": synergy2_bonus,
                "total_camp_score": total_rating_2,
                "specialties": camp2.get("specialties", [])
            },
            "advantage_side": adv_side,
            "advantage_tier": adv_tier,
            "net_elo_delta": round(delta_rating, 1),
            "win_prob_swing_pct": prob_swing_pct,
            "breakdown_points": breakdown_points
        }

    def get_all_camps_summary(self):
        """Returns all registered gyms and their rosters."""
        return {
            "total_registered_gyms": len(self.gyms),
            "gyms": list(self.gyms.values())
        }

if __name__ == "__main__":
    engine = CampAndCoachEngine()
    print("\n" + "="*75)
    print("🥊 UFC CAMP QUALITY & HEAD COACH MATRIX (PHASE 4.3)")
    print("="*75)
    print(f"🏢 Kayıtlı Elit Kamp Sayısı: {len(engine.gyms)}")
    print(f"🥋 Eşleştirilen Dövüşçü Sayısı: {len(engine.fighter_gym_map)}")
    print("="*75)

    test_pairs = [
        ("Islam Makhachev", "Dustin Poirier", "Pressure Wrestler", "Distance Out-Fighter"),
        ("Alexander Volkanovski", "Ilia Topuria", "Distance Out-Fighter", "Pressure Wrestler"),
        ("Kamaru Usman", "Caio Borralho", "Pressure Wrestler", "Counter Striker"),
        ("Charles Oliveira", "Regional Prospect", "BJJ Specialist", "Universal Balanced")
    ]

    for f1, f2, a1, a2 in test_pairs:
        res = engine.evaluate_camp_matchup(f1, f2, a1, a2)
        c1 = res["fighter1"]
        c2 = res["fighter2"]
        print(f"👉 {f1} [{c1['camp_name']} - {c1['tier']}] vs {f2} [{c2['camp_name']} - {c2['tier']}]")
        print(f"   Antrenörler: {c1['head_coach']} vs {c2['head_coach']}")
        print(f"   Net Kamp Skoru: {c1['total_camp_score']} vs {c2['total_camp_score']} (Δ: {res['net_elo_delta']} Elo, Olasılık Etkisi: {res['win_prob_swing_pct']:+}%)")
        print(f"   Avantaj: {res['advantage_side']} ({res['advantage_tier']})")
        if res["breakdown_points"]:
            print(f"   Analiz: {' | '.join(res['breakdown_points'])}")
        print()
