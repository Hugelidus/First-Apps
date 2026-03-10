"""Tests para el pipeline de predicciones y datos históricos."""

import pytest
import pandas as pd

from src.data.historical import (
    load_football_data_csv,
    get_team_results,
    get_league_averages,
)
from src.predictions.engine import PredictionEngine
from src.predictions.context import (
    build_analyzer_context,
    format_context_summary,
    _empty_context,
)


@pytest.fixture
def sample_df():
    """DataFrame de ejemplo con partidos."""
    return load_football_data_csv("data/historical/champions_league.csv")


@pytest.fixture
def trained_engine(sample_df):
    """Motor de predicciones entrenado."""
    engine = PredictionEngine()
    engine.train_from_dataframe(sample_df)
    return engine


class TestHistoricalData:
    def test_load_csv(self, sample_df):
        assert len(sample_df) > 100
        assert "home_team" in sample_df.columns
        assert "away_team" in sample_df.columns
        assert "home_goals" in sample_df.columns
        assert "away_goals" in sample_df.columns
        assert "date" in sample_df.columns

    def test_result_column(self, sample_df):
        assert "result_numeric" in sample_df.columns
        assert set(sample_df["result_numeric"].dropna().unique()).issubset({0, 1, 2})

    def test_total_goals(self, sample_df):
        assert "total_goals" in sample_df.columns
        assert (sample_df["total_goals"] >= 0).all()

    def test_get_team_results(self, sample_df):
        results = get_team_results(sample_df, "Real Madrid")
        assert len(results) > 0
        assert all("points" in r for r in results)
        assert all("goals_for" in r for r in results)
        assert all("is_home" in r for r in results)

    def test_get_team_results_n_last(self, sample_df):
        results = get_team_results(sample_df, "Real Madrid", n_last=5)
        assert len(results) <= 5

    def test_league_averages(self, sample_df):
        avgs = get_league_averages(sample_df)
        assert avgs["avg_total_goals"] > 0
        assert avgs["avg_home_goals"] > 0
        assert avgs["avg_away_goals"] > 0

    def test_empty_averages(self):
        avgs = get_league_averages(pd.DataFrame())
        assert avgs["avg_goals_per_team"] == 1.3


class TestPredictionEngine:
    def test_train(self, trained_engine):
        assert trained_engine.is_trained

    def test_predict_match(self, trained_engine):
        pred = trained_engine.predict_match("Real Madrid", "Bayern Munich")
        assert "probabilities" in pred
        probs = pred["probabilities"]
        assert abs(sum(probs.values()) - 1.0) < 0.01
        assert all(0 <= v <= 1 for v in probs.values())

    def test_predict_returns_all_fields(self, trained_engine):
        pred = trained_engine.predict_match("Real Madrid", "Bayern Munich")
        assert "goals" in pred
        assert "ratings" in pred
        assert "form" in pred
        assert "strength" in pred
        assert "value_bets" in pred

    def test_goals_prediction(self, trained_engine):
        pred = trained_engine.predict_match("Real Madrid", "Bayern Munich")
        goals = pred["goals"]
        assert goals["expected_home"] > 0
        assert goals["expected_away"] > 0
        assert "over_under" in goals
        assert "most_likely_scores" in goals

    def test_form_data(self, trained_engine):
        pred = trained_engine.predict_match("Real Madrid", "Bayern Munich")
        form = pred["form"]
        assert "home" in form and "away" in form
        assert "last_matches" in form["home"]
        assert "momentum" in form["home"]

    def test_team_profile(self, trained_engine):
        profile = trained_engine.get_team_profile("Real Madrid")
        assert profile["team"] == "Real Madrid"
        assert "elo" in profile
        assert "pi_ratings" in profile
        assert "form" in profile
        assert "last_5" in profile

    def test_predict_multiple(self, trained_engine):
        fixtures = [("Real Madrid", "Bayern Munich"), ("Man City", "Barcelona")]
        preds = trained_engine.predict_multiple(fixtures)
        assert len(preds) == 2
        assert all("probabilities" in p for p in preds)

    def test_predict_unknown_team_uses_defaults(self, trained_engine):
        # Un equipo desconocido debería funcionar con ratings por defecto
        pred = trained_engine.predict_match("Equipo Ficticio", "Real Madrid")
        assert "probabilities" in pred


class TestContext:
    def test_empty_context(self):
        ctx = _empty_context("TeamA", "TeamB")
        assert "home_team" in ctx
        assert "away_team" in ctx
        assert "match_context" in ctx

    def test_build_analyzer_context(self):
        ctx = _empty_context("Real Madrid", "Bayern Munich")
        ctx["home_team"]["injuries"] = [
            {"player": "Vinicius Jr", "status": "lesionado", "impact": "alto"}
        ]
        analyzer_ctx = build_analyzer_context(ctx)
        assert "injuries" in analyzer_ctx
        assert len(analyzer_ctx["injuries"]) == 1

    def test_format_context_summary(self):
        ctx = _empty_context("Real Madrid", "Bayern Munich")
        ctx["home_team"]["form_narrative"] = "En gran momento"
        summary = format_context_summary(ctx)
        assert "En gran momento" in summary
        assert "LOCAL" in summary
