"""Tests para los modelos de predicción."""

import pytest
from src.features.ratings import EloRating, PiRating
from src.models.goals_model import GoalsModel, poisson_score_matrix, dixon_coles_correction
from src.betting.kelly import kelly_fraction, recommended_stake
from src.betting.value_bets import find_value_bets
from src.features.form import weighted_form, momentum


class TestEloRating:
    def test_initial_rating(self):
        elo = EloRating()
        assert elo.get_rating("TeamA") == 1500.0

    def test_update_adjusts_ratings(self):
        elo = EloRating()
        elo.update("TeamA", "TeamB", 3, 0)
        assert elo.get_rating("TeamA") > 1500.0
        assert elo.get_rating("TeamB") < 1500.0

    def test_predict_sums_to_one(self):
        elo = EloRating()
        pred = elo.predict("TeamA", "TeamB")
        total = pred["home"] + pred["draw"] + pred["away"]
        assert abs(total - 1.0) < 0.001


class TestPiRating:
    def test_initial_predict(self):
        pi = PiRating()
        lh, la = pi.predict_goals("TeamA", "TeamB")
        assert lh > 0
        assert la > 0

    def test_update_changes_predictions(self):
        pi = PiRating()
        before = pi.predict_goals("TeamA", "TeamB")
        pi.update("TeamA", "TeamB", 5, 0)
        after = pi.predict_goals("TeamA", "TeamB")
        assert after[0] > before[0]  # Home team should predict more goals


class TestGoalsModel:
    def test_matrix_sums_to_one(self):
        matrix = poisson_score_matrix(1.5, 1.2)
        assert abs(matrix.sum() - 1.0) < 0.01

    def test_dixon_coles_sums_to_one(self):
        matrix = poisson_score_matrix(1.5, 1.2)
        corrected = dixon_coles_correction(matrix, 1.5, 1.2)
        assert abs(corrected.sum() - 1.0) < 0.001

    def test_predict_returns_all_markets(self):
        model = GoalsModel()
        pred = model.predict(1.5, 1.2)
        assert "over_under" in pred
        assert "result_1x2" in pred
        assert "handicaps" in pred
        assert "most_likely_scores" in pred

    def test_1x2_sums_to_one(self):
        model = GoalsModel()
        pred = model.predict(1.5, 1.2)
        total = sum(pred["result_1x2"].values())
        assert abs(total - 1.0) < 0.01

    def test_over_under_sums_to_one(self):
        model = GoalsModel()
        pred = model.predict(1.5, 1.2)
        for line, ou in pred["over_under"].items():
            assert abs(ou["over"] + ou["under"] - 1.0) < 0.01


class TestKelly:
    def test_no_value_returns_zero(self):
        assert kelly_fraction(0.4, 2.0) == 0.0  # 0.4*2=0.8 < 1

    def test_value_bet_returns_positive(self):
        result = kelly_fraction(0.6, 2.5)
        assert result > 0

    def test_max_5_percent(self):
        # Even with huge edge, should be capped
        result = kelly_fraction(0.95, 10.0, fraction=1.0)
        assert result <= 0.05

    def test_recommended_stake(self):
        result = recommended_stake(1000, 0.55, 2.10)
        assert result["is_value_bet"] is True
        assert result["stake"] >= 0
        assert result["value"] > 0


class TestValueBets:
    def test_finds_value_when_exists(self):
        predictions = {"home": 0.55, "draw": 0.25, "away": 0.20}
        odds = {"home": 2.10, "draw": 3.50, "away": 5.00}
        bets = find_value_bets(predictions, odds)
        # home: 0.55*2.10=1.155 > 1, so value exists
        assert len(bets) > 0
        assert bets[0]["is_value_bet"] is True

    def test_no_value_when_overpriced(self):
        predictions = {"home": 0.55, "draw": 0.25, "away": 0.20}
        odds = {"home": 1.50, "draw": 3.00, "away": 4.00}
        bets = find_value_bets(predictions, odds, min_value=0.05)
        # home: 0.55*1.50=0.825 < 1, no value
        home_bets = [b for b in bets if b["outcome"] == "home"]
        assert len(home_bets) == 0


class TestForm:
    def test_empty_results(self):
        form = weighted_form([])
        assert form["points_avg"] == 0.0

    def test_all_wins(self):
        results = [
            {"points": 3, "goals_for": 2, "goals_against": 0, "is_home": True}
            for _ in range(5)
        ]
        form = weighted_form(results)
        assert form["points_avg"] == 3.0
        assert form["win_rate"] == 1.0

    def test_momentum_positive(self):
        recent_wins = [{"points": 3, "goals_for": 2, "goals_against": 0, "is_home": True}] * 5
        old_losses = [{"points": 0, "goals_for": 0, "goals_against": 2, "is_home": True}] * 5
        m = momentum(recent_wins + old_losses)
        assert m > 0
