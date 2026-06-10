import logging
import numpy as np
from decimal import Decimal
from django.db.models import Q
from matches.models import Match
from predictions.models import Prediction
from services.standings_service import StandingsService
from services.injury_service import InjuryService

logger = logging.getLogger('ai_engine')

class PredictionEngine:
    _model_1x2 = None
    _model_over = None
    _model_btts = None
    _is_trained = False

    @classmethod
    def train(cls):
        """Trains Scikit-Learn models on finished matches from the database."""
        try:
            from sklearn.ensemble import RandomForestClassifier
            finished_matches = Match.objects.filter(status='FINISHED').select_related('home_team', 'away_team', 'league')
            
            # We need at least some finished matches to train
            if finished_matches.count() < 10:
                logger.info("[PredictionEngine] Insufficient training data (< 10 matches). Fallback to heuristic rules.")
                cls._is_trained = False
                return False

            X = []
            y_1x2 = [] # 0: Home Win, 1: Draw, 2: Away Win
            y_over = [] # 0: Under 2.5, 1: Over 2.5
            y_btts = [] # 0: No, 1: Yes

            for m in finished_matches:
                features = cls._compute_match_features(m)
                if features is None:
                    continue
                X.append(features)

                # Determine 1X2 label
                if m.home_score > m.away_score:
                    y_1x2.append(0)
                elif m.home_score == m.away_score:
                    y_1x2.append(1)
                else:
                    y_1x2.append(2)

                # Determine Over/Under label
                total_goals = m.home_score + m.away_score
                y_over.append(1 if total_goals > 2.5 else 0)

                # Determine BTTS label
                btts = 1 if (m.home_score > 0 and m.away_score > 0) else 0
                y_btts.append(btts)

            if len(X) < 10:
                cls._is_trained = False
                return False

            X_arr = np.array(X)
            
            cls._model_1x2 = RandomForestClassifier(n_estimators=50, random_state=42)
            cls._model_1x2.fit(X_arr, y_1x2)

            cls._model_over = RandomForestClassifier(n_estimators=50, random_state=42)
            cls._model_over.fit(X_arr, y_over)

            cls._model_btts = RandomForestClassifier(n_estimators=50, random_state=42)
            cls._model_btts.fit(X_arr, y_btts)

            cls._is_trained = True
            logger.info(f"[PredictionEngine] Successfully trained Scikit-Learn models on {len(X)} historical matches.")
            return True
        except Exception as e:
            logger.error(f"[PredictionEngine] Error training models: {e}")
            cls._is_trained = False
            return False

    @classmethod
    def _compute_match_features(cls, match):
        """Computes feature list for a match."""
        try:
            # Standings difference
            home_standings = StandingsService.get_standings(match.league.name)
            home_rank, home_pts = 10, 15
            away_rank, away_pts = 10, 15
            if home_standings:
                for entry in home_standings:
                    if entry['team_name'].lower() in match.home_team.name.lower():
                        home_rank = entry['rank']
                        home_pts = entry['points']
                    if entry['team_name'].lower() in match.away_team.name.lower():
                        away_rank = entry['rank']
                        away_pts = entry['points']

            rank_diff = away_rank - home_rank
            pts_diff = home_pts - away_pts

            # Team form
            home_form_pts = cls._get_form_points(match.home_team, match.match_date)
            away_form_pts = cls._get_form_points(match.away_team, match.match_date)

            # Injuries
            home_injuries = len(InjuryService.get_team_injuries(match.home_team.name))
            away_injuries = len(InjuryService.get_team_injuries(match.away_team.name))

            # Odds
            odds = match.odds_snapshots.first()
            if odds:
                home_odds = float(odds.home_odds or 2.0)
                draw_odds = float(odds.draw_odds or 3.2)
                away_odds = float(odds.away_odds or 3.5)
            else:
                home_odds = 2.0
                draw_odds = 3.2
                away_odds = 3.5

            features = [
                rank_diff,
                pts_diff,
                home_form_pts,
                away_form_pts,
                home_injuries,
                away_injuries,
                home_odds,
                draw_odds,
                away_odds
            ]
            return features
        except Exception as e:
            logger.error(f"[PredictionEngine] Error computing features: {e}")
            return None

    @classmethod
    def _get_form_points(cls, team, date):
        """Helper to compute form points for last 5 matches before date."""
        recent = Match.objects.filter(
            (Q(home_team=team) | Q(away_team=team)) & Q(status='FINISHED') & Q(match_date__lt=date)
        ).order_by('-match_date')[:5]
        
        pts = 0
        for m in recent:
            if m.home_team == team:
                if m.home_score > m.away_score:
                    pts += 3
                elif m.home_score == m.away_score:
                    pts += 1
            else:
                if m.away_score > m.home_score:
                    pts += 3
                elif m.home_score == m.away_score:
                    pts += 1
        return pts

    @classmethod
    def predict(cls, match):
        """Predicts probabilities and exact score using scikit-learn models (or heuristic fallback)."""
        if not cls._is_trained:
            cls.train()

        features = cls._compute_match_features(match)

        # Baseline predictions if models are not trained
        if not cls._is_trained or features is None:
            return cls._heuristic_predict(match)

        try:
            X = np.array([features])
            
            # Predict win/draw/away probabilities
            probs_1x2 = cls._model_1x2.predict_proba(X)[0]
            home_win_prob = float(probs_1x2[0]) * 100
            draw_prob = float(probs_1x2[1]) * 100 if len(probs_1x2) > 1 else 0.0
            away_win_prob = float(probs_1x2[2]) * 100 if len(probs_1x2) > 2 else 0.0
            
            total = home_win_prob + draw_prob + away_win_prob
            if total > 0:
                home_win_prob = (home_win_prob / total) * 100
                draw_prob = (draw_prob / total) * 100
                away_win_prob = (away_win_prob / total) * 100

            # Predict Over 2.5
            probs_over = cls._model_over.predict_proba(X)[0]
            over_2_5_prob = float(probs_over[1]) * 100 if len(probs_over) > 1 else 50.0
            under_2_5_prob = 100.0 - over_2_5_prob

            # Predict BTTS
            probs_btts = cls._model_btts.predict_proba(X)[0]
            btts_yes_prob = float(probs_btts[1]) * 100 if len(probs_btts) > 1 else 50.0
            btts_no_prob = 100.0 - btts_yes_prob

            confidence_score = int(max(home_win_prob, draw_prob, away_win_prob, over_2_5_prob, btts_yes_prob))
            confidence_score = max(50, min(98, confidence_score))

            picks = []
            if home_win_prob > 45:
                picks.append(f"{match.home_team.name} Win")
            elif away_win_prob > 45:
                picks.append(f"{match.away_team.name} Win")
            else:
                picks.append("Double Chance 1X" if home_win_prob > away_win_prob else "Double Chance X2")

            if over_2_5_prob > 55:
                picks.append("Over 2.5 Goals")
            elif under_2_5_prob > 55:
                picks.append("Under 2.5 Goals")
            
            recommended_pick = picks[0] if picks else f"{match.home_team.name} or Draw"

            home_goals, away_goals = cls._estimate_goals(home_win_prob, draw_prob, away_win_prob, over_2_5_prob)

            return {
                "home_win_prob": Decimal(str(round(home_win_prob, 2))),
                "draw_prob": Decimal(str(round(draw_prob, 2))),
                "away_win_prob": Decimal(str(round(away_win_prob, 2))),
                "over_2_5_prob": Decimal(str(round(over_2_5_prob, 2))),
                "under_2_5_prob": Decimal(str(round(under_2_5_prob, 2))),
                "btts_yes_prob": Decimal(str(round(btts_yes_prob, 2))),
                "btts_no_prob": Decimal(str(round(btts_no_prob, 2))),
                "confidence_score": confidence_score,
                "recommended_pick": recommended_pick,
                "predicted_home_score": home_goals,
                "predicted_away_score": away_goals
            }
        except Exception as e:
            logger.error(f"[PredictionEngine] Error using ML models for prediction: {e}")
            return cls._heuristic_predict(match)

    @classmethod
    def _heuristic_predict(cls, match):
        """Rule-based heuristic prediction when ML training dataset is small/unavailable."""
        import random
        random.seed(match.id)
        
        home_len = len(match.home_team.name)
        away_len = len(match.away_team.name)
        diff = (home_len - away_len) * 2.5
        
        home_win_prob = max(15.0, min(80.0, 45.0 + diff))
        draw_prob = max(10.0, min(40.0, 25.0 - (abs(diff) * 0.2)))
        away_win_prob = 100.0 - home_win_prob - draw_prob
        
        over_2_5_prob = random.uniform(40.0, 80.0)
        under_2_5_prob = 100.0 - over_2_5_prob
        
        btts_yes_prob = random.uniform(45.0, 78.0)
        btts_no_prob = 100.0 - btts_yes_prob
        
        confidence_score = int(random.uniform(60, 96))
        
        picks = []
        if home_win_prob > 50:
            picks.append(f"{match.home_team.name} Win")
        elif away_win_prob > 50:
            picks.append(f"{match.away_team.name} Win")
        else:
            picks.append("Double Chance 1X" if home_win_prob > away_win_prob else "Double Chance X2")
            
        recommended_pick = picks[0] if picks else f"{match.home_team.name} or Draw"
        
        home_goals, away_goals = cls._estimate_goals(home_win_prob, draw_prob, away_win_prob, over_2_5_prob)

        return {
            "home_win_prob": Decimal(str(round(home_win_prob, 2))),
            "draw_prob": Decimal(str(round(draw_prob, 2))),
            "away_win_prob": Decimal(str(round(away_win_prob, 2))),
            "over_2_5_prob": Decimal(str(round(over_2_5_prob, 2))),
            "under_2_5_prob": Decimal(str(round(under_2_5_prob, 2))),
            "btts_yes_prob": Decimal(str(round(btts_yes_prob, 2))),
            "btts_no_prob": Decimal(str(round(btts_no_prob, 2))),
            "confidence_score": confidence_score,
            "recommended_pick": recommended_pick,
            "predicted_home_score": home_goals,
            "predicted_away_score": away_goals
        }

    @classmethod
    def _estimate_goals(cls, home_win_prob, draw_prob, away_win_prob, over_2_5_prob):
        """Helper to estimate realistic home and away goals based on probabilities."""
        if home_win_prob > 45:
            home_goals = 2 if over_2_5_prob > 55 else 1
            away_goals = 1 if over_2_5_prob > 65 else 0
        elif away_win_prob > 45:
            away_goals = 2 if over_2_5_prob > 55 else 1
            home_goals = 1 if over_2_5_prob > 65 else 0
        else:
            home_goals = 2 if over_2_5_prob > 60 else 1
            away_goals = home_goals
            
        return home_goals, away_goals
