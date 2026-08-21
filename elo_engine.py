import os
import json
from collections import defaultdict
from datetime import datetime

# Division numerical hierarchy (weight in lbs & division tier)
DIVISION_HIERARCHY = {
    "Women's Strawweight": 0,
    "Women's Flyweight": 1,
    "Women's Bantamweight": 2,
    "Women's Featherweight": 3,
    "Flyweight": 1,
    "Bantamweight": 2,
    "Featherweight": 3,
    "Lightweight": 4,
    "Welterweight": 5,
    "Middleweight": 6,
    "Light Heavyweight": 7,
    "Heavyweight": 8,
}

# Curated registry of famous UFC short-notice replacement bouts (fighter, opponent, event/date)
KNOWN_SHORT_NOTICE_REPLACEMENTS = {
    ("Alexander Volkanovski", "Islam Makhachev", "2023-10-21"): "11 Days Notice (UFC 294 Replacement)",
    ("Kamaru Usman", "Khamzat Chimaev", "2023-10-21"): "10 Days Notice (UFC 294 Replacement)",
    ("Jorge Masvidal", "Kamaru Usman", "2020-07-11"): "6 Days Notice (UFC 251 Replacement)",
    ("Michael Bisping", "Luke Rockhold", "2016-06-04"): "17 Days Notice (UFC 199 Title Replacement)",
    ("Nate Diaz", "Conor McGregor", "2016-03-05"): "11 Days Notice (UFC 196 Replacement)",
    ("Al Iaquinta", "Khabib Nurmagomedov", "2018-04-07"): "1 Day Notice (UFC 223 Title Replacement)",
    ("Paul Felder", "Rafael Dos Anjos", "2020-11-14"): "5 Days Notice (UFC Vegas 14)",
    ("Sean Strickland", "Nassourdine Imavov", "2023-01-14"): "5 Days Notice (UFC Vegas 67)",
    ("Diego Lopes", "Movsar Evloev", "2023-05-06"): "5 Days Notice (UFC 288)",
    ("Dan Hooker", "Islam Makhachev", "2021-10-30"): "4 Weeks Notice (UFC 267)",
    ("Renato Moicano", "Rafael Dos Anjos", "2022-03-05"): "4 Days Notice (UFC 272 Catchweight)",
    ("Bobby Green", "Islam Makhachev", "2022-02-26"): "10 Days Notice (UFC Vegas 49)",
    ("Chris Leben", "Yoshihiro Akiyama", "2010-07-03"): "14 Days Turnaround (UFC 116)",
    ("Khamzat Chimaev", "Rhys McKee", "2020-07-25"): "10 Days Turnaround (Fight Island)",
    ("Kevin Holland", "Charlie Ontiveros", "2020-10-31"): "Short Turnaround",
    ("Donald Cerrone", "Benson Henderson", "2015-01-18"): "15 Days Turnaround",
    ("Dan Henderson", "Michael Bisping", "2016-10-08"): "Short Camp Veteran",
    ("Ovince Saint Preux", "Jon Jones", "2016-04-23"): "3 Weeks Notice (UFC 197)"
}

class UFCEloEngine:
    def __init__(self, base_elo=1500.0, base_k=32.0, decay_per_month=5.0, inactivity_threshold_months=18.0, current_date="2026-08-21", pedigree_file="pedigree_database.json"):
        self.base_elo = base_elo
        self.base_k = base_k
        self.decay_per_month = decay_per_month
        self.inactivity_threshold_months = inactivity_threshold_months
        self.current_date = current_date
        self.fighters = {}
        self.history = []
        self.ped_db = {}
        if os.path.exists(pedigree_file):
            try:
                with open(pedigree_file, 'r', encoding='utf-8') as f:
                    self.ped_db = json.load(f)
            except Exception:
                pass

    def get_or_create_fighter(self, name):
        if name not in self.fighters:
            init_elo = self.base_elo
            if self.ped_db and name.lower() in self.ped_db:
                init_elo = self.ped_db[name.lower()].get('prior_elo', self.base_elo)

            self.fighters[name] = {
                'name': name,
                'elo': init_elo,
                'peak_elo': init_elo,
                'lowest_elo': init_elo,
                'wins': 0,
                'losses': 0,
                'draws': 0,
                'nc': 0,
                'win_streak': 0,
                'best_win_streak': 0,
                'title_fights': 0,
                'title_wins': 0,
                'methods': {
                    'KO/TKO_win': 0,
                    'SUB_win': 0,
                    'DEC_win': 0,
                    'U-DEC_win': 0,
                    'S-DEC_win': 0,
                    'OTHER_win': 0,
                    'KO/TKO_loss': 0,
                    'SUB_loss': 0,
                    'DEC_loss': 0,
                    'U-DEC_loss': 0,
                    'S-DEC_loss': 0,
                    'OTHER_loss': 0,
                },
                'total_kd': 0,
                'total_sig_str': 0,
                'total_td': 0,
                'weight_classes': defaultdict(int),
                'recent_divisions': [],
                'last_fight_date': None,
                'last_delta': 0.0,
                'total_decay': 0.0,
                'fights_history': []
            }
        return self.fighters[name]

    def calculate_expected_score(self, elo_a, elo_b):
        """Calculates expected score of Fighter A against Fighter B."""
        return 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a) / 400.0))

    def get_fighter_natural_tier(self, fighter):
        """Determines the fighter's natural division tier from their most frequent recent divisions."""
        if not fighter['weight_classes']:
            return None
            
        # Check recent 4 fights or all-time frequency
        if fighter['recent_divisions']:
            recent_counts = defaultdict(int)
            for d in fighter['recent_divisions'][-4:]:
                recent_counts[d] += 1
            most_common = max(recent_counts.items(), key=lambda x: x[1])[0]
            if most_common in DIVISION_HIERARCHY:
                return DIVISION_HIERARCHY[most_common]

        # Fallback to all-time weight class counts
        sorted_wc = sorted(fighter['weight_classes'].items(), key=lambda x: x[1], reverse=True)
        for wc, _ in sorted_wc:
            if wc in DIVISION_HIERARCHY:
                return DIVISION_HIERARCHY[wc]
        return None

    def check_short_notice(self, fighter_name, opponent_name, fight_date_str, last_fight_date_str):
        """
        Detects if this bout is a short notice replacement:
        - Matched in known short notice registry
        - Fast turnaround (<= 21 days from previous fight)
        """
        key1 = (fighter_name, opponent_name, fight_date_str)
        if key1 in KNOWN_SHORT_NOTICE_REPLACEMENTS:
            return {'is_short_notice': True, 'reason': KNOWN_SHORT_NOTICE_REPLACEMENTS[key1]}

        # Check turnaround time
        if last_fight_date_str and fight_date_str:
            try:
                d_prev = datetime.strptime(last_fight_date_str, "%Y-%m-%d")
                d_curr = datetime.strptime(fight_date_str, "%Y-%m-%d")
                gap_days = (d_curr - d_prev).days
                if 1 <= gap_days <= 21:
                    return {'is_short_notice': True, 'reason': f"Fast Turnaround ({gap_days} Days Rest)"}
            except Exception:
                pass

        return {'is_short_notice': False, 'reason': ''}

    def calculate_inactivity_and_decay(self, prev_date_str, current_date_str, current_elo):
        """Calculates Elo decay and Glicko-style Uncertainty Multiplier for inactivity (>18 months)."""
        if not prev_date_str or not current_date_str:
            return {'months': 0.0, 'decay': 0.0, 'uncertainty_mult': 1.0, 'is_comeback': False}

        try:
            d_prev = datetime.strptime(prev_date_str, "%Y-%m-%d")
            d_curr = datetime.strptime(current_date_str, "%Y-%m-%d")
            days = (d_curr - d_prev).days
            if days <= 0:
                return {'months': 0.0, 'decay': 0.0, 'uncertainty_mult': 1.0, 'is_comeback': False}

            months = days / 30.4375
            if months > self.inactivity_threshold_months:
                excess_months = months - self.inactivity_threshold_months
                raw_decay = excess_months * self.decay_per_month
                
                if current_elo > self.base_elo:
                    actual_decay = min(raw_decay, current_elo - self.base_elo)
                else:
                    actual_decay = min(raw_decay, 25.0)

                uncertainty_mult = 1.0 + min(0.60, (excess_months / 6.0) * 0.15)

                return {
                    'months': round(months, 1),
                    'excess_months': round(excess_months, 1),
                    'decay': round(actual_decay, 1),
                    'uncertainty_mult': round(uncertainty_mult, 2),
                    'is_comeback': True
                }
        except Exception:
            pass

        return {'months': 0.0, 'decay': 0.0, 'uncertainty_mult': 1.0, 'is_comeback': False}

    def calculate_dominance_metric(self, match):
        """Calculates In-Fight Dominance Metric (-20% to +20%)."""
        w_str = match.get('winner_str', 0) or 0
        l_str = match.get('loser_str', 0) or 0
        w_kd = match.get('winner_kd', 0) or 0
        l_kd = match.get('loser_kd', 0) or 0
        w_td = match.get('winner_td', 0) or 0
        l_td = match.get('loser_td', 0) or 0
        w_sub = match.get('winner_sub', 0) or 0
        method = (match.get('method') or '').upper()
        raw_method = (match.get('raw_method') or '').upper()
        round_num = match.get('round', '1')
        time_str = match.get('time', '5:00')

        str_diff = w_str - l_str
        str_ratio = (w_str + 1.0) / (l_str + 1.0)
        kd_diff = w_kd - l_kd
        td_diff = w_td - l_td

        time_sec = 300
        try:
            parts = str(time_str).split(':')
            if len(parts) == 2:
                time_sec = int(parts[0]) * 60 + int(parts[1])
        except Exception:
            pass

        s_str = 0.0
        if str_ratio >= 3.0 or str_diff >= 40:
            s_str = 0.08
        elif str_ratio >= 2.0 or str_diff >= 20:
            s_str = 0.05
        elif str_ratio >= 1.3 or str_diff >= 10:
            s_str = 0.02
        elif str_ratio <= 0.70 and str_diff <= -12:
            s_str = -0.07 # Flash KO
        elif str_ratio <= 0.90:
            s_str = -0.03
        else:
            s_str = 0.0

        s_kd = 0.0
        if kd_diff >= 3:
            s_kd = 0.06
        elif kd_diff == 2:
            s_kd = 0.04
        elif kd_diff == 1:
            s_kd = 0.02
        elif kd_diff <= -1:
            s_kd = -0.05

        s_ctrl = 0.0
        if td_diff >= 4:
            s_ctrl = 0.04
        elif td_diff >= 2:
            s_ctrl = 0.02
        if w_sub >= 3:
            s_ctrl += 0.02

        s_method = 0.0
        dominance_tag = "Standard"

        if "KO" in method or "TKO" in method:
            is_flash_ko = (str_diff < 0 and kd_diff <= 0) or (str_ratio < 0.8)
            if is_flash_ko:
                s_method = -0.06
                dominance_tag = "Flash KO (Comeback)"
            elif round_num == '1' and time_sec <= 90:
                s_method = 0.06
                dominance_tag = "Blistering R1 KO"
            elif str_ratio >= 2.0 or kd_diff >= 2:
                s_method = 0.04
                dominance_tag = "Dominant TKO/KO"
            else:
                s_method = 0.02
                dominance_tag = "Clean KO/TKO"

        elif "SUB" in method:
            if round_num == '1' and time_sec <= 120:
                s_method = 0.05
                dominance_tag = "Quick R1 Submission"
            elif td_diff >= 2 or w_sub >= 2:
                s_method = 0.03
                dominance_tag = "Dominant Submission"
            else:
                s_method = 0.01
                dominance_tag = "Submission"

        elif "S-DEC" in method or "SPLIT" in raw_method:
            s_method = -0.12
            dominance_tag = "Split Decision (Razor-Thin)"
        elif "M-DEC" in method or "MAJORITY" in raw_method:
            s_method = -0.05
            dominance_tag = "Majority Decision"
        elif "U-DEC" in method or "DEC" in method or "UNANIMOUS" in raw_method:
            if str_diff >= 25 or kd_diff >= 1:
                s_method = 0.05
                dominance_tag = "Lopsided Unanimous Decision"
            else:
                s_method = 0.02
                dominance_tag = "Unanimous Decision"

        raw_dominance = s_str + s_kd + s_ctrl + s_method
        clipped_dominance = max(-0.20, min(0.20, raw_dominance))
        multiplier = 1.0 + clipped_dominance

        return {
            'score': round(clipped_dominance, 3),
            'multiplier': round(multiplier, 3),
            'percentage': round(clipped_dominance * 100, 1),
            'tag': dominance_tag,
            'str_diff': str_diff,
            'kd_diff': kd_diff,
            'td_diff': td_diff
        }

    def process_match(self, match):
        f1_name = match.get('fighter1')
        f2_name = match.get('fighter2')
        winner_name = match.get('winner')
        loser_name = match.get('loser')
        result_type = match.get('result_type', 'win')
        method = match.get('method', 'OTHER')
        is_title = match.get('is_title_bout', False)
        weight_class = match.get('weight_class', 'Catchweight')
        match_date = match.get('date', '')
        event_name = match.get('event_name', '')
        method_detail = match.get('method_detail', '')
        round_num = match.get('round', '')
        time_str = match.get('time', '')

        if not f1_name or not f2_name:
            return

        f1 = self.get_or_create_fighter(f1_name)
        f2 = self.get_or_create_fighter(f2_name)

        # 1. Short Notice Replacement Check
        sn_info1 = self.check_short_notice(f1_name, f2_name, match_date, f1['last_fight_date'])
        sn_info2 = self.check_short_notice(f2_name, f1_name, match_date, f2['last_fight_date'])

        # 2. Weight Class Hierarchy & Step-Up Check
        bout_tier = DIVISION_HIERARCHY.get(weight_class)
        f1_nat_tier = self.get_fighter_natural_tier(f1)
        f2_nat_tier = self.get_fighter_natural_tier(f2)

        # Division jump step: positive if fighter is fighting in a heavier class than their natural home
        f1_tier_jump = (bout_tier - f1_nat_tier) if (bout_tier is not None and f1_nat_tier is not None and bout_tier > f1_nat_tier) else 0
        f2_tier_jump = (bout_tier - f2_nat_tier) if (bout_tier is not None and f2_nat_tier is not None and bout_tier > f2_nat_tier) else 0

        # Inactivity Decay before fight
        inactivity1 = self.calculate_inactivity_and_decay(f1['last_fight_date'], match_date, f1['elo'])
        inactivity2 = self.calculate_inactivity_and_decay(f2['last_fight_date'], match_date, f2['elo'])

        if inactivity1['is_comeback'] and inactivity1['decay'] > 0:
            f1['elo'] -= inactivity1['decay']
            f1['total_decay'] += inactivity1['decay']
            f1['fights_history'].append({
                'date': match_date,
                'event': f"Inactivity Decay ({inactivity1['months']} Months Hiatus)",
                'opponent': "Inactivity",
                'opponent_elo_before': 0,
                'result': 'DECAY',
                'method': 'ELO_DECAY',
                'method_detail': f"-{inactivity1['decay']} pts ({inactivity1['excess_months']} mo past 18m)",
                'round': '-',
                'time': '-',
                'is_title': False,
                'weight_class': weight_class,
                'k_factor': 0,
                'dominance_tag': 'Inactivity Decay',
                'dominance_pct': 0,
                'str_diff': 0,
                'kd_diff': 0,
                'delta': -inactivity1['decay'],
                'new_elo': round(f1['elo'], 1)
            })

        if inactivity2['is_comeback'] and inactivity2['decay'] > 0:
            f2['elo'] -= inactivity2['decay']
            f2['total_decay'] += inactivity2['decay']
            f2['fights_history'].append({
                'date': match_date,
                'event': f"Inactivity Decay ({inactivity2['months']} Months Hiatus)",
                'opponent': "Inactivity",
                'opponent_elo_before': 0,
                'result': 'DECAY',
                'method': 'ELO_DECAY',
                'method_detail': f"-{inactivity2['decay']} pts ({inactivity2['excess_months']} mo past 18m)",
                'round': '-',
                'time': '-',
                'is_title': False,
                'weight_class': weight_class,
                'k_factor': 0,
                'dominance_tag': 'Inactivity Decay',
                'dominance_pct': 0,
                'str_diff': 0,
                'kd_diff': 0,
                'delta': -inactivity2['decay'],
                'new_elo': round(f2['elo'], 1)
            })

        # Update weight class history
        f1['weight_classes'][weight_class] += 1
        f2['weight_classes'][weight_class] += 1
        if weight_class in DIVISION_HIERARCHY:
            f1['recent_divisions'].append(weight_class)
            f2['recent_divisions'].append(weight_class)
            
        f1['last_fight_date'] = match_date
        f2['last_fight_date'] = match_date

        if is_title:
            f1['title_fights'] += 1
            f2['title_fights'] += 1

        # Track career cumulative stats
        if winner_name == f1_name:
            f1['total_sig_str'] += match.get('winner_str', 0) or 0
            f2['total_sig_str'] += match.get('loser_str', 0) or 0
            f1['total_kd'] += match.get('winner_kd', 0) or 0
            f2['total_kd'] += match.get('loser_kd', 0) or 0
            f1['total_td'] += match.get('winner_td', 0) or 0
            f2['total_td'] += match.get('loser_td', 0) or 0
        else:
            f2['total_sig_str'] += match.get('winner_str', 0) or 0
            f1['total_sig_str'] += match.get('loser_str', 0) or 0
            f2['total_kd'] += match.get('winner_kd', 0) or 0
            f1['total_kd'] += match.get('loser_kd', 0) or 0
            f2['total_td'] += match.get('winner_td', 0) or 0
            f1['total_td'] += match.get('loser_td', 0) or 0

        # Calculate Dominance Metric
        dom_metric = self.calculate_dominance_metric(match)
        dom_mult = dom_metric['multiplier']

        norm_method = (method or '').upper()
        method_multiplier = 1.5 if ("KO" in norm_method or "TKO" in norm_method or "SUB" in norm_method) else 1.0
        title_multiplier = 1.2 if is_title else 1.0

        base_match_k = self.base_k * method_multiplier * title_multiplier * dom_mult

        k1 = base_match_k * inactivity1['uncertainty_mult']
        k2 = base_match_k * inactivity2['uncertainty_mult']
        
        elo1_before = f1['elo']
        elo2_before = f2['elo']
        
        exp1 = self.calculate_expected_score(elo1_before, elo2_before)
        exp2 = 1.0 - exp1

        delta1 = 0.0
        delta2 = 0.0

        f1_tags = []
        f2_tags = []

        if result_type == 'nc':
            f1['nc'] += 1
            f2['nc'] += 1
            f1_outcome = 'NC'
            f2_outcome = 'NC'
        elif result_type == 'draw':
            delta1 = k1 * (0.5 - exp1)
            delta2 = k2 * (0.5 - exp2)
            f1['draws'] += 1
            f2['draws'] += 1
            f1['win_streak'] = 0
            f2['win_streak'] = 0
            f1_outcome = 'DRAW'
            f2_outcome = 'DRAW'
        else:
            if winner_name == f1_name:
                winner, loser = f1, f2
                k_w, k_l = k1, k2
                exp_w, exp_l = exp1, exp2
                w_sn, l_sn = sn_info1, sn_info2
                w_jump, l_jump = f1_tier_jump, f2_tier_jump
                f1_outcome = 'WIN'
                f2_outcome = 'LOSS'
            else:
                winner, loser = f2, f1
                k_w, k_l = k2, k1
                exp_w, exp_l = exp2, exp1
                w_sn, l_sn = sn_info2, sn_info1
                w_jump, l_jump = f2_tier_jump, f1_tier_jump
                f1_outcome = 'LOSS'
                f2_outcome = 'WIN'

            # 3. Apply Short Notice & Weight Jump Modifiers
            win_mult = 1.0
            loss_mult = 1.0

            # Short Notice: Winner gets +40% Elo bonus, Loser gets 50% loss mitigation
            if w_sn['is_short_notice']:
                win_mult *= 1.40
                if winner_name == f1_name: f1_tags.append(f"Short Notice Win (+40%)")
                else: f2_tags.append(f"Short Notice Win (+40%)")

            if l_sn['is_short_notice']:
                loss_mult *= 0.50 # 50% less penalty for taking fight on short notice
                if loser['name'] == f1_name: f1_tags.append(f"Short Notice Loss Protection (-50% Loss)")
                else: f2_tags.append(f"Short Notice Loss Protection (-50% Loss)")

            # Weight Class Step-Up:
            # - If lighter fighter stepped up and won: +15% per division jump
            if w_jump >= 1:
                weight_win_bonus = 1.0 + (0.15 * w_jump)
                win_mult *= weight_win_bonus
                tag_str = f"Weight Jump (+{int(w_jump*15)}% Bonus)"
                if winner_name == f1_name: f1_tags.append(tag_str)
                else: f2_tags.append(tag_str)

            # - If lighter fighter stepped up and lost: 30% loss mitigation for fighting bigger opponent
            if l_jump >= 1:
                weight_loss_mitigation = max(0.60, 1.0 - (0.30 * l_jump))
                loss_mult *= weight_loss_mitigation
                tag_str = f"Size Disadvantage Protection (-{int(l_jump*30)}% Loss)"
                if loser['name'] == f1_name: f1_tags.append(tag_str)
                else: f2_tags.append(tag_str)

            winner_delta = (k_w * win_mult) * (1.0 - exp_w)
            loser_delta = (k_l * loss_mult) * (0.0 - exp_l)

            if winner_name == f1_name:
                delta1 = winner_delta
                delta2 = loser_delta
            else:
                delta1 = loser_delta
                delta2 = winner_delta

            winner['wins'] += 1
            loser['losses'] += 1
            winner['win_streak'] += 1
            if winner['win_streak'] > winner['best_win_streak']:
                winner['best_win_streak'] = winner['win_streak']
            loser['win_streak'] = 0

            if is_title:
                winner['title_wins'] += 1

            if "KO" in method or "TKO" in method:
                winner['methods']['KO/TKO_win'] += 1
                loser['methods']['KO/TKO_loss'] += 1
            elif "SUB" in method:
                winner['methods']['SUB_win'] += 1
                loser['methods']['SUB_loss'] += 1
            elif "S-DEC" in method:
                winner['methods']['S-DEC_win'] += 1
                loser['methods']['S-DEC_loss'] += 1
                winner['methods']['DEC_win'] += 1
                loser['methods']['DEC_loss'] += 1
            elif "U-DEC" in method:
                winner['methods']['U-DEC_win'] += 1
                loser['methods']['U-DEC_loss'] += 1
                winner['methods']['DEC_win'] += 1
                loser['methods']['DEC_loss'] += 1
            elif "DEC" in method:
                winner['methods']['DEC_win'] += 1
                loser['methods']['DEC_loss'] += 1
            else:
                winner['methods']['OTHER_win'] += 1
                loser['methods']['OTHER_loss'] += 1

        f1['elo'] += delta1
        f2['elo'] += delta2
        
        f1['peak_elo'] = max(f1['peak_elo'], f1['elo'])
        f1['lowest_elo'] = min(f1['lowest_elo'], f1['elo'])
        f2['peak_elo'] = max(f2['peak_elo'], f2['elo'])
        f2['lowest_elo'] = min(f2['lowest_elo'], f2['elo'])

        f1['last_delta'] = delta1
        f2['last_delta'] = delta2

        f1_fight_record = {
            'date': match_date,
            'event': event_name,
            'opponent': f2_name,
            'opponent_elo_before': round(elo2_before, 1),
            'result': f1_outcome,
            'method': method,
            'method_detail': method_detail,
            'round': round_num,
            'time': time_str,
            'is_title': is_title,
            'weight_class': weight_class,
            'k_factor': round(k1, 1),
            'dominance_tag': dom_metric['tag'],
            'dominance_pct': dom_metric['percentage'],
            'short_notice': sn_info1['is_short_notice'],
            'short_notice_reason': sn_info1['reason'],
            'weight_jump': f1_tier_jump,
            'special_tags': f1_tags,
            'str_diff': dom_metric['str_diff'],
            'kd_diff': dom_metric['kd_diff'],
            'uncertainty_mult': inactivity1['uncertainty_mult'],
            'delta': round(delta1, 1),
            'new_elo': round(f1['elo'], 1)
        }
        f2_fight_record = {
            'date': match_date,
            'event': event_name,
            'opponent': f1_name,
            'opponent_elo_before': round(elo1_before, 1),
            'result': f2_outcome,
            'method': method,
            'method_detail': method_detail,
            'round': round_num,
            'time': time_str,
            'is_title': is_title,
            'weight_class': weight_class,
            'k_factor': round(k2, 1),
            'dominance_tag': dom_metric['tag'],
            'dominance_pct': dom_metric['percentage'],
            'short_notice': sn_info2['is_short_notice'],
            'short_notice_reason': sn_info2['reason'],
            'weight_jump': f2_tier_jump,
            'special_tags': f2_tags,
            'str_diff': -dom_metric['str_diff'],
            'kd_diff': -dom_metric['kd_diff'],
            'uncertainty_mult': inactivity2['uncertainty_mult'],
            'delta': round(delta2, 1),
            'new_elo': round(f2['elo'], 1)
        }

        f1['fights_history'].append(f1_fight_record)
        f2['fights_history'].append(f2_fight_record)

        self.history.append({
            'date': match_date,
            'event': event_name,
            'fighter1': f1_name,
            'fighter2': f2_name,
            'winner': winner_name,
            'result_type': result_type,
            'method': method,
            'is_title': is_title,
            'weight_class': weight_class,
            'f1_k': round(k1, 1),
            'f2_k': round(k2, 1),
            'dominance_tag': dom_metric['tag'],
            'dominance_pct': dom_metric['percentage'],
            'f1_tags': f1_tags,
            'f2_tags': f2_tags,
            'f1_delta': round(delta1, 1),
            'f2_delta': round(delta2, 1),
            'f1_new_elo': round(f1['elo'], 1),
            'f2_new_elo': round(f2['elo'], 1)
        })

    def run(self, matches_file="matches.json", rankings_output="fighter_rankings.json", history_output="elo_history.json"):
        print(f"[INFO] Loading matches from {matches_file}...")
        with open(matches_file, 'r', encoding='utf-8') as f:
            matches = json.load(f)

        print(f"[INFO] Processing {len(matches)} matches with Short Notice, Weight Class Jumps, Elo Decay & Dominance...")
        for match in matches:
            self.process_match(match)

        ranking_list = []
        for name, data in self.fighters.items():
            total_fights = data['wins'] + data['losses'] + data['draws'] + data['nc']
            if total_fights == 0:
                continue

            post_inactivity = self.calculate_inactivity_and_decay(data['last_fight_date'], self.current_date, data['elo'])
            current_elo = data['elo']
            if post_inactivity['is_comeback'] and post_inactivity['decay'] > 0:
                current_elo -= post_inactivity['decay']
                data['total_decay'] += post_inactivity['decay']

            is_active = post_inactivity['months'] <= self.inactivity_threshold_months

            primary_wc = "Catchweight"
            if data['weight_classes']:
                sorted_wc = sorted(data['weight_classes'].items(), key=lambda x: x[1], reverse=True)
                primary_wc = sorted_wc[0][0]
                if primary_wc in ["Catchweight", "Open Weight", "UFC Bout"] and len(sorted_wc) > 1:
                    primary_wc = sorted_wc[1][0]

            win_rate = (data['wins'] / total_fights * 100) if total_fights > 0 else 0
            finish_wins = data['methods']['KO/TKO_win'] + data['methods']['SUB_win']
            finish_rate = (finish_wins / data['wins'] * 100) if data['wins'] > 0 else 0

            ranking_list.append({
                'name': name,
                'elo': round(current_elo, 1),
                'elo_pre_decay': round(data['elo'], 1),
                'peak_elo': round(data['peak_elo'], 1),
                'lowest_elo': round(data['lowest_elo'], 1),
                'last_delta': round(data['last_delta'], 1),
                'wins': data['wins'],
                'losses': data['losses'],
                'draws': data['draws'],
                'nc': data['nc'],
                'total_fights': total_fights,
                'win_rate': round(win_rate, 1),
                'finish_rate': round(finish_rate, 1),
                'win_streak': data['win_streak'],
                'best_win_streak': data['best_win_streak'],
                'title_fights': data['title_fights'],
                'title_wins': data['title_wins'],
                'total_sig_str': data['total_sig_str'],
                'total_kd': data['total_kd'],
                'total_td': data['total_td'],
                'is_active': is_active,
                'months_inactive': post_inactivity['months'],
                'total_decay_applied': round(data['total_decay'], 1),
                'uncertainty_mult': post_inactivity['uncertainty_mult'],
                'primary_weight_class': primary_wc,
                'all_weight_classes': list(data['weight_classes'].keys()),
                'last_fight_date': data['last_fight_date'],
                'methods': data['methods'],
                'fights_history': data['fights_history']
            })

        ranking_list.sort(key=lambda x: x['elo'], reverse=True)

        division_counts = defaultdict(int)
        active_division_counts = defaultdict(int)
        for i, f in enumerate(ranking_list, 1):
            f['p4p_rank'] = i
            wc = f['primary_weight_class']
            division_counts[wc] += 1
            f['division_rank'] = division_counts[wc]
            if f['is_active']:
                active_division_counts[wc] += 1
                f['active_division_rank'] = active_division_counts[wc]
            else:
                f['active_division_rank'] = None

        print(f"[SUCCESS] Calculated Full Career Elo for {len(ranking_list)} UFC fighters.")

        with open(rankings_output, 'w', encoding='utf-8') as f:
            json.dump(ranking_list, f, indent=2, ensure_ascii=False)
            
        with open(history_output, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, indent=2, ensure_ascii=False)

        print(f"[INFO] Exported rankings to {rankings_output}")
        print(f"[INFO] Exported fight history to {history_output}")
        return ranking_list

if __name__ == '__main__':
    engine = UFCEloEngine()
    engine.run()
