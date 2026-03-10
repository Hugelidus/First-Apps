"""Modelo de predicción 1X2 con XGBoost y CatBoost."""

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, log_loss
from xgboost import XGBClassifier
from catboost import CatBoostClassifier


FEATURE_COLS = [
    "elo_diff", "elo_prob_home", "elo_prob_draw", "elo_prob_away",
    "pi_home_rating", "pi_away_rating",
    "pi_expected_home_goals", "pi_expected_away_goals",
    "home_form_points", "home_form_gf", "home_form_ga", "home_form_gd", "home_form_wr",
    "away_form_points", "away_form_gf", "away_form_ga", "away_form_gd", "away_form_wr",
    "home_momentum", "away_momentum",
    "home_attack", "home_defense", "away_attack", "away_defense",
    "h2h_home_wr", "h2h_draw_rate", "h2h_home_gf", "h2h_home_ga",
]


class MatchPredictor:
    """Predictor 1X2 usando ensemble de XGBoost + CatBoost."""

    def __init__(self):
        self.xgb = XGBClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            objective="multi:softprob",
            num_class=3,
            eval_metric="mlogloss",
            random_state=42,
            verbosity=0,
        )
        self.cat = CatBoostClassifier(
            iterations=200,
            depth=5,
            learning_rate=0.05,
            loss_function="MultiClass",
            random_seed=42,
            verbose=0,
        )
        self.is_trained = False

    def train(self, df: pd.DataFrame, target_col: str = "result"):
        """Entrena ambos modelos. target: 0=away, 1=draw, 2=home."""
        X = df[FEATURE_COLS].values
        y = df[target_col].values

        self.xgb.fit(X, y)
        self.cat.fit(X, y)
        self.is_trained = True

    def predict_proba(self, features: dict | pd.DataFrame) -> dict[str, float]:
        """Predice probabilidades 1X2.

        Returns:
            Dict con home, draw, away probabilities.
        """
        if not self.is_trained:
            raise RuntimeError("El modelo no ha sido entrenado. Llama a train() primero.")

        if isinstance(features, dict):
            X = np.array([[features[c] for c in FEATURE_COLS]])
        else:
            X = features[FEATURE_COLS].values

        # Promedio de probabilidades de ambos modelos (voting soft)
        xgb_proba = self.xgb.predict_proba(X)
        cat_proba = self.cat.predict_proba(X)
        avg_proba = (xgb_proba + cat_proba) / 2

        if len(avg_proba) == 1:
            p = avg_proba[0]
            return {"away": float(p[0]), "draw": float(p[1]), "home": float(p[2])}

        return avg_proba

    def evaluate(self, df: pd.DataFrame, target_col: str = "result", n_splits: int = 5) -> dict:
        """Evalúa con walk-forward (TimeSeriesSplit)."""
        X = df[FEATURE_COLS].values
        y = df[target_col].values

        tscv = TimeSeriesSplit(n_splits=n_splits)
        accuracies = []
        log_losses = []

        for train_idx, test_idx in tscv.split(X):
            X_train, X_test = X[train_idx], X[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]

            self.xgb.fit(X_train, y_train)
            self.cat.fit(X_train, y_train)

            xgb_p = self.xgb.predict_proba(X_test)
            cat_p = self.cat.predict_proba(X_test)
            avg_p = (xgb_p + cat_p) / 2

            preds = np.argmax(avg_p, axis=1)
            accuracies.append(accuracy_score(y_test, preds))
            log_losses.append(log_loss(y_test, avg_p, labels=[0, 1, 2]))

        self.is_trained = True
        return {
            "accuracy_mean": round(np.mean(accuracies), 4),
            "accuracy_std": round(np.std(accuracies), 4),
            "log_loss_mean": round(np.mean(log_losses), 4),
        }

    def feature_importance(self) -> dict[str, float]:
        """Importancia de features del modelo XGBoost."""
        if not self.is_trained:
            return {}
        imp = self.xgb.feature_importances_
        return {col: round(float(v), 4) for col, v in zip(FEATURE_COLS, imp)}
