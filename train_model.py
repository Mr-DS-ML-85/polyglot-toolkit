#!/usr/bin/env python3
"""
PolyglotShield — Model Trainer
Trains CatBoost on the generated training dataset.

Usage:
  python train_model.py --data training_dataset.csv
  python train_model.py --data training_dataset.csv --gpu
  python train_model.py --data training_dataset.csv --eval-only --model models/polyglot_shield.cbm

Author: Mr-DS-ML-85
"""

import sys, os, json, time, argparse
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from engines.model import PolyglotModel, HAS_CATBOOST
from engines.features import get_feature_names


def load_dataset(csv_path):
    """Load training CSV, separate features + labels."""
    df = pd.read_csv(csv_path)
    feature_names = get_feature_names()

    # Verify columns
    missing = [f for f in feature_names if f not in df.columns]
    if missing:
        print(f"[!] Missing {len(missing)} feature columns: {missing[:5]}...")
        return None, None, None, None

    X = df[feature_names].values.astype(np.float64)
    y = df["label"].values.astype(int)

    # Metadata
    meta = df[["filepath", "polyglot_type", "severity"]].copy() if "filepath" in df.columns else None

    return X, y, feature_names, meta


def train(csv_path, task_type="GPU", output="models/polyglot_shield.cbm"):
    """Train CatBoost model on the dataset."""
    print("=" * 60)
    print("  POLYGLOTSHIELD — Model Training")
    print("=" * 60)

    if not HAS_CATBOOST:
        print("[!] catboost not installed. Run: pip install catboost")
        sys.exit(1)

    # Load data
    print(f"\n[*] Loading dataset: {csv_path}")
    X, y, feature_names, meta = load_dataset(csv_path)
    if X is None:
        print("[!] Failed to load dataset")
        sys.exit(1)

    n_mal = int(np.sum(y == 1))
    n_ben = int(np.sum(y == 0))
    print(f"    Samples: {len(X)} ({n_mal} malicious, {n_ben} benign)")
    print(f"    Features: {X.shape[1]}")

    # Train/eval split (stratified)
    from sklearn.model_selection import train_test_split
    X_train, X_eval, y_train, y_eval = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"    Train: {len(X_train)}, Eval: {len(X_eval)}")

    # Train model
    print(f"\n[*] Training CatBoost ({task_type})...")
    config = {
        "task_type": task_type,
        "iterations": 1500,
        "learning_rate": 0.03,
        "depth": 8,
        "l2_leaf_reg": 5,
        "early_stopping_rounds": 100,
        "auto_class_weights": "Balanced",  # Auto-balance classes
    }

    model = PolyglotModel(config)
    meta_info = model.train(X_train, y_train, X_eval, y_eval)

    # Save
    model.save(output)
    print(f"\n[✓] Model saved: {output}")

    # Feature importance
    print("\n[*] Top 20 features:")
    imp = model.get_feature_importance(20)
    for name, score in imp:
        bar = "█" * int(score * 2)
        print(f"    {name:30s} {score:8.4f} {bar}")

    # Eval metrics
    if model.is_loaded:
        from sklearn.metrics import classification_report, confusion_matrix
        y_pred, y_conf = model.predict(X_eval)
        print("\n[*] Evaluation Results:")
        print(classification_report(y_eval, y_pred, target_names=["benign", "polyglot"]))

        cm = confusion_matrix(y_eval, y_pred)
        print(f"    Confusion Matrix:")
        print(f"    TN={cm[0][0]:5d}  FP={cm[0][1]:5d}")
        print(f"    FN={cm[1][0]:5d}  TP={cm[1][1]:5d}")

    # Save metadata
    meta_out = output + ".meta.json"
    with open(meta_out, 'w') as f:
        json.dump({
            "train_samples": len(X_train),
            "eval_samples": len(X_eval),
            "n_features": X.shape[1],
            "n_malicious": n_mal,
            "n_benign": n_ben,
            "polyglot_types": int(len(set(meta["polyglot_type"]))) if meta is not None else 0,
            "training_time": meta_info.get("training_time_sec", 0),
            "task_type": task_type,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, f, indent=2)

    print(f"\n[✓] Training complete!")
    print(f"    Model: {output}")
    print(f"    Meta:  {meta_out}")


def evaluate(csv_path, model_path):
    """Evaluate a trained model on a dataset."""
    print(f"[*] Evaluating: {model_path}")
    X, y, _, meta = load_dataset(csv_path)
    if X is None:
        sys.exit(1)

    model = PolyglotModel()
    model.load(model_path)

    from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
    y_pred, y_conf = model.predict(X)

    print("\n" + classification_report(y, y_pred, target_names=["benign", "polyglot"]))

    cm = confusion_matrix(y, y_pred)
    print(f"Confusion Matrix:")
    print(f"  TN={cm[0][0]:5d}  FP={cm[0][1]:5d}")
    print(f"  FN={cm[1][0]:5d}  TP={cm[1][1]:5d}")

    auc = roc_auc_score(y, y_conf)
    print(f"\nROC-AUC: {auc:.4f}")

    # Per-type accuracy
    if meta is not None:
        print("\nPer-type detection rate:")
        for ptype in sorted(meta["polyglot_type"].unique()):
            mask = meta["polyglot_type"] == ptype
            if y[mask].sum() > 0:
                detected = y_pred[mask][y[mask] == 1].sum()
                total = y[mask].sum()
                print(f"  {ptype:30s} {detected}/{total} ({100*detected/total:.1f}%)")


def main():
    parser = argparse.ArgumentParser(description="PolyglotShield Model Trainer")
    parser.add_argument("--data", required=True, help="Training CSV file")
    parser.add_argument("--gpu", action="store_true", help="Use GPU training")
    parser.add_argument("--cpu", action="store_true", help="Use CPU training")
    parser.add_argument("--output", default="models/polyglot_shield.cbm", help="Output model path")
    parser.add_argument("--eval-only", action="store_true", help="Evaluate existing model")
    parser.add_argument("--model", help="Model path for evaluation")
    args = parser.parse_args()

    task_type = "CPU" if args.cpu else "GPU" if args.gpu else "GPU"

    if args.eval_only:
        model_path = args.model or args.output
        evaluate(args.data, model_path)
    else:
        train(args.data, task_type, args.output)


if __name__ == "__main__":
    main()
