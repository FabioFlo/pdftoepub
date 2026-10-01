"""Reusable conversion preferences, excluding document-specific edits."""
from __future__ import annotations

from dataclasses import asdict

from .model import Options


PREFERENCE_FIELDS = ("mode", "quality", "table_mode", "language", "remove_margins",
                     "detect_borderless", "preserve_links")
PROFILES = {
    "balanced": {"mode": "hybrid", "quality": "balanced", "table_mode": "auto"},
    "technical": {"mode": "hybrid", "quality": "balanced", "table_mode": "image"},
    "compact": {"mode": "hybrid", "quality": "compact", "table_mode": "auto"},
}


def preferences(options: Options) -> dict:
    values = asdict(options)
    return {key: values[key] for key in PREFERENCE_FIELDS}


def checked_preferences(values: dict) -> dict:
    if not isinstance(values, dict):
        raise ValueError("A profile must contain conversion settings.")
    selected = {key: values[key] for key in PREFERENCE_FIELDS if key in values}
    for key in ("remove_margins", "detect_borderless", "preserve_links"):
        if key in selected and not isinstance(selected[key], bool):
            raise ValueError("Profile switches must be true or false.")
    options = Options(**selected)
    options.validate()
    return preferences(options)
