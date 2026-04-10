from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib

from app.config import settings

TARGET_COLS = [
    "lift_6h",
    "lift_24h",
    "lift_48h",
    "lift_72h",
    "lift_96h",
    "peak_lift_pct",
    "decay_lambda",
]


def try_load_model1() -> tuple[Any | None, list[str] | None, list[str]]:
    msgs: list[str] = []
    model = None
    feats: list[str] | None = None
    mp = settings.best_model_path()
    fp = settings.feature_cols_path()
    if not mp.is_file():
        msgs.append(f"Missing MODEL1 artifact: {mp}")
        return None, None, msgs
    if not fp.is_file():
        msgs.append(f"Missing feature list: {fp}")
        return None, None, msgs
    try:
        model = joblib.load(mp)
        feats = list(joblib.load(fp))
    except ModuleNotFoundError as e:
        msgs.append(f"MODEL1 load failed — install missing lib (e.g. catboost if trained there): {e}")
        return None, None, msgs
    except Exception as e:
        msgs.append(f"Failed to load MODEL1: {e}")
        return None, None, msgs
    return model, feats, msgs


def try_load_model2_bundle() -> tuple[dict[str, Any], dict[str, list[str]], list[str]]:
    """Returns (models_by_target, features_by_target, messages)."""
    msgs: list[str] = []
    models: dict[str, Any] = {}
    feat_map: dict[str, list[str]] = {}
    root = settings.root() / settings.influencer_model_dir
    if not root.is_dir():
        msgs.append(f"Missing influencer model dir: {root}")
        return models, feat_map, msgs
    import json

    for t in TARGET_COLS:
        pkl = root / f"{t}_best.pkl"
        js = root / f"{t}_features.json"
        if not pkl.is_file() or not js.is_file():
            continue
        try:
            models[t] = joblib.load(pkl)
            with open(js, encoding="utf-8") as f:
                feat_map[t] = json.load(f)
        except ModuleNotFoundError as e:
            msgs.append(f"MODEL2 {t}: missing dependency (e.g. pip install catboost): {e}")
        except Exception as e:
            msgs.append(f"MODEL2 {t}: {e}")
    return models, feat_map, msgs
