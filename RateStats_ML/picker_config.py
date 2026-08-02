#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""推理阶段融合参数（由 tune_picker.py 写入 models/picker_tuning.json）。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from _portable import MODEL_DIR

TUNING_FILE = MODEL_DIR / "picker_tuning.json"

DEFAULT_TUNING = {
    "blend_rule_weight": 0.28,
    "min_ml_proba": 0.18,
    "use_ambiguous_gate": True,
    "ambiguous_rule_margin": 0.12,
}


@dataclass
class PickerTuning:
    blend_rule_weight: float = 0.28
    min_ml_proba: float = 0.18
    use_ambiguous_gate: bool = True
    ambiguous_rule_margin: float = 0.12


def load_picker_tuning(path: Path | None = None) -> PickerTuning:
    p = path or TUNING_FILE
    if not p.is_file():
        return PickerTuning(**DEFAULT_TUNING)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return PickerTuning(
            blend_rule_weight=float(raw.get("blend_rule_weight", DEFAULT_TUNING["blend_rule_weight"])),
            min_ml_proba=float(raw.get("min_ml_proba", DEFAULT_TUNING["min_ml_proba"])),
            use_ambiguous_gate=bool(raw.get("use_ambiguous_gate", DEFAULT_TUNING["use_ambiguous_gate"])),
            ambiguous_rule_margin=float(
                raw.get("ambiguous_rule_margin", DEFAULT_TUNING["ambiguous_rule_margin"])
            ),
        )
    except (json.JSONDecodeError, TypeError, ValueError):
        return PickerTuning(**DEFAULT_TUNING)


def save_picker_tuning(tuning: PickerTuning, path: Path | None = None) -> Path:
    p = path or TUNING_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "blend_rule_weight": tuning.blend_rule_weight,
        "min_ml_proba": tuning.min_ml_proba,
        "use_ambiguous_gate": tuning.use_ambiguous_gate,
        "ambiguous_rule_margin": tuning.ambiguous_rule_margin,
    }
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return p
