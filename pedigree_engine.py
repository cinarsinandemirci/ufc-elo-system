import json
import os

class PedigreeCalibrationEngine:
    def __init__(self, database_path=None):
        if database_path is None:
            database_path = os.path.join(os.path.dirname(__file__), 'pedigree_database.json')
        
        self.pedigrees = {}
        if os.path.exists(database_path):
            with open(database_path, 'r', encoding='utf-8') as f:
                self.pedigrees = json.load(f)

    def get_pedigree(self, fighter_name):
        if not fighter_name:
            return None
        return self.pedigrees.get(fighter_name.strip().lower())

    def calibrate_fighter_ratings(self, fighter_name, current_elo, ufc_fights_count, comp_elos=None):
        """
        Applies non-invasive Bayesian Prior & Latent Skill Floor Imputation
        for fighters in their first 1-3 UFC bouts.
        
        Guarantees 0.00% effect on established fighters (ufc_fights_count >= max_fights_decay).
        """
        ped = self.get_pedigree(fighter_name)
        if not ped:
            return {
                'has_pedigree': False,
                'effective_elo': current_elo,
                'pedigree_badge': None,
                'alpha_decay': 0.0,
                'comp_elos': comp_elos or {'striking_elo': 1500.0, 'grappling_elo': 1500.0, 'cardio_elo': 1500.0}
            }

        max_decay = ped.get('max_fights_decay', 3)
        if ufc_fights_count >= max_decay:
            # Pedigree has completely decayed to 0.0, empirical UFC ledger has taken over 100%
            return {
                'has_pedigree': True,
                'pedigree_active': False,
                'effective_elo': current_elo,
                'pedigree_badge': f"⚡ Verified Pedigree Veteran: {ped['title']}",
                'alpha_decay': 0.0,
                'comp_elos': comp_elos or {'striking_elo': 1500.0, 'grappling_elo': 1500.0, 'cardio_elo': 1500.0}
            }

        # Alpha decay: 1.0 at 0 fights, 0.67 at 1 fight, 0.33 at 2 fights, 0.0 at 3 fights
        alpha = max(0.0, 1.0 - (float(ufc_fights_count) / float(max_decay)))
        prior_elo = ped.get('prior_elo', 1600.0)

        # Bayesian weighted average for base Elo
        effective_elo = round((alpha * prior_elo) + ((1.0 - alpha) * current_elo), 1)

        # Latent Component Skill Floor Imputation
        curr_comps = comp_elos or {'striking_elo': 1500.0, 'grappling_elo': 1500.0, 'cardio_elo': 1500.0}
        str_anchor = ped.get('striking_anchor', 1500.0)
        grp_anchor = ped.get('grappling_anchor', 1500.0)

        adj_striking = max(curr_comps.get('striking_elo', 1500.0), round((alpha * str_anchor) + ((1.0 - alpha) * curr_comps.get('striking_elo', 1500.0)), 1))
        adj_grappling = max(curr_comps.get('grappling_elo', 1500.0), round((alpha * grp_anchor) + ((1.0 - alpha) * curr_comps.get('grappling_elo', 1500.0)), 1))
        adj_cardio = curr_comps.get('cardio_elo', 1500.0)

        return {
            'has_pedigree': True,
            'pedigree_active': True,
            'effective_elo': effective_elo,
            'prior_elo': prior_elo,
            'alpha_decay': round(alpha, 2),
            'alpha_pct': round(alpha * 100.0, 1),
            'pedigree_title': ped['title'],
            'pedigree_badge': f"🥇 Elite Fast-Track Pedigree ({ped['title']}) [Prior Weight: {round(alpha*100)}%]",
            'comp_elos': {
                'striking_elo': adj_striking,
                'grappling_elo': adj_grappling,
                'cardio_elo': adj_cardio
            },
            'notes': ped.get('notes', '')
        }
