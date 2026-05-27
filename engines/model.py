"""
CatBoost classifier — GPU-accelerated polyglot detection.
Optimized for RTX 4060 with Ryzen 7 7700 + 32 GB RAM.
"""

import os, json, time, logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np

try:
    from catboost import CatBoostClassifier, Pool
    HAS_CATBOOST = True
except ImportError:
    HAS_CATBOOST = False
    CatBoostClassifier = None  # type: ignore[assignment,misc]
    Pool = None  # type: ignore[assignment,misc]

from .features import get_feature_names

logger = logging.getLogger("polyglot_shield.model")


class PolyglotModel:
    """CatBoost-based polyglot file classifier with confidence scoring."""

    def __init__(self, config: dict = None):
        if not HAS_CATBOOST:
            raise ImportError("catboost not installed: pip install catboost")
        self.config = config or {}
        self.model: Optional[CatBoostClassifier] = None
        self.feature_names = get_feature_names()
        self.meta: Dict = {}

    def _build(self) -> CatBoostClassifier:
        c = self.config
        params = {
            "iterations": c.get("iterations", 1200),
            "learning_rate": c.get("learning_rate", 0.04),
            "depth": c.get("depth", 8),
            "l2_leaf_reg": c.get("l2_leaf_reg", 5),
            "border_count": c.get("border_count", 254),
            "random_seed": c.get("random_seed", 42),
            "eval_metric": c.get("eval_metric", "Logloss"),
            "task_type": c.get("task_type", "GPU"),
            "devices": "0",
            "verbose": c.get("verbose", 0),
            "early_stopping_rounds": c.get("early_stopping_rounds", 80),
            "loss_function": "Logloss",
            "max_ctr_complexity": 4,
            "boosting_type": "Plain",
            "bootstrap_type": "Bayesian",
            "bagging_temperature": 0.8,
            "od_type": "Iter",
            "allow_writing_files": False,
        }
        cw = c.get("class_weights")
        if cw:
            params["class_weights"] = cw
        acw = c.get("auto_class_weights")
        if acw:
            params["auto_class_weights"] = acw
        if c.get("task_type", "GPU") == "GPU":
            params["gpu_ram_part"] = c.get("gpu_ram_fraction", 0.7)
            logger.info("CatBoost GPU mode (RTX 4060 optimized)")
        else:
            logger.info("CatBoost CPU mode")
        return CatBoostClassifier(**params)

    def train(self, X_train: np.ndarray, y_train: np.ndarray,
              X_eval: np.ndarray = None, y_eval: np.ndarray = None) -> Dict:
        logger.info(f"Training: {X_train.shape[0]} samples, {X_train.shape[1]} features")
        self.model = self._build()
        t0 = time.time()
        # Use CatBoost Pool for feature names (fit() doesn't accept feature_names kwarg)
        from catboost import Pool
        train_pool = Pool(X_train, y_train, feature_names=list(self.feature_names) if self.feature_names is not None else None)
        eval_pool = Pool(X_eval, y_eval, feature_names=list(self.feature_names) if self.feature_names is not None else None) if X_eval is not None else None
        self.model.fit(train_pool, eval_set=eval_pool)
        elapsed = time.time() - t0
        best_iter = getattr(self.model, "best_iteration_", self.config.get("iterations", 1200))
        best_score = getattr(self.model, "best_score_", {})
        self.meta = {
            "train_samples": int(X_train.shape[0]),
            "eval_samples": int(X_eval.shape[0]) if X_eval is not None else 0,
            "n_features": int(X_train.shape[1]),
            "best_iteration": int(best_iter) if best_iter else 0,
            "best_score": {k: float(v) if not isinstance(v, dict) else {kk: float(vv) for kk, vv in v.items()}
                           for k, v in best_score.items()} if best_score else {},
            "training_time_sec": round(elapsed, 2),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        logger.info(f"Training done in {elapsed:.1f}s, best_iter={best_iter}")
        return self.meta

    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        if self.model is None:
            raise RuntimeError("Model not loaded")
        proba = self.model.predict_proba(X)
        poly_probs = proba[:, 1]
        labels = (poly_probs >= 0.5).astype(int)
        confidences = np.maximum(proba[:, 0], proba[:, 1])
        return labels, confidences

    def predict_single(self, features: np.ndarray) -> Dict:
        if features.ndim == 1:
            features = features.reshape(1, -1)
        proba = self.model.predict_proba(features)[0]
        pp, bp = float(proba[1]), float(proba[0])
        label = "polyglot" if pp >= 0.5 else "benign"
        conf = max(pp, bp)
        risk = pp * 100.0
        return {
            "label": label, "confidence": round(conf, 4),
            "polyglot_probability": round(pp, 4),
            "benign_probability": round(bp, 4),
            "risk_score": round(risk, 2),
            "risk_level": self._risk_level(risk),
        }

    def get_feature_importance(self, top_n: int = 20) -> List[Tuple[str, float]]:
        if self.model is None:
            return []
        imp = self.model.feature_importances_
        idx = np.argsort(imp)[::-1][:top_n]
        return [(self.feature_names[i], round(float(imp[i]), 4)) for i in idx]

    def save(self, path: str):
        if self.model is None:
            raise RuntimeError("No model to save")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.model.save_model(path)
        with open(path + ".meta.json", "w") as f:
            json.dump(self.meta, f, indent=2)
        logger.info(f"Model saved → {path} ({os.path.getsize(path)/1024:.0f} KB)")

    def load(self, path: str):
        if not Path(path).exists():
            raise FileNotFoundError(f"Model not found: {path}")
        self.model = CatBoostClassifier()
        self.model.load_model(path)
        mp = path + ".meta.json"
        if Path(mp).exists():
            with open(mp) as f:
                self.meta = json.load(f)
        logger.info(f"Model loaded ← {path}")

    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    @staticmethod
    def _risk_level(score: float) -> str:
        if score >= 80: return "CRITICAL"
        if score >= 60: return "HIGH"
        if score >= 40: return "MEDIUM"
        if score >= 20: return "LOW"
        return "SAFE"
