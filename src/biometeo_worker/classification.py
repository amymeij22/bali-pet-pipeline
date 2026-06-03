"""Klasifikasi PET (temperate vs sub_tropic) sesuai ambang skripsi revisi."""

from __future__ import annotations

import math
from typing import Literal

Standard = Literal["temperate", "sub_tropic"]


def classify_pet(pet_value: float | None, standard: str) -> str | None:
    """
    Mengembalikan category_key atau None jika pet_value tidak valid.
    Tidak pernah mengembalikan 'neutral' untuk NaN/None.
    """
    if standard not in ("temperate", "sub_tropic"):
        raise ValueError(f"standard tidak dikenal: {standard!r} (harus 'temperate' atau 'sub_tropic')")

    if pet_value is None:
        return None
    if isinstance(pet_value, float) and math.isnan(pet_value):
        return None

    p = float(pet_value)

    if standard == "temperate":
        # Konsisten dengan WebGIS (tanpa overlap):
        # very_hot: p > 41
        # hot: 35 <= p <= 41
        # warm: 29 <= p < 35
        # slight_warm: 23 <= p < 29
        # neutral: 18 <= p < 23
        # slight_cool: 13 <= p < 18
        # cool: 8 <= p < 13
        # cold: 4 <= p < 8
        # very_cold: p < 4
        if p > 41:
            return "very_hot"
        if 35 <= p <= 41:
            return "hot"
        if 29 <= p < 35:
            return "warm"
        if 23 <= p < 29:
            return "slight_warm"
        if 18 <= p < 23:
            return "neutral"
        if 13 <= p < 18:
            return "slight_cool"
        if 8 <= p < 13:
            return "cool"
        if 4 <= p < 8:
            return "cold"
        return "very_cold"

    # sub_tropic
    # very_hot: p > 42
    # hot: 38 <= p <= 42
    # warm: 34 <= p < 38
    # slight_warm: 30 <= p < 34
    # neutral: 26 <= p < 30
    # slight_cool: 22 <= p < 26
    # cool: 18 <= p < 22
    # cold: 14 <= p < 18
    # very_cold: p < 14
    if p > 42:
        return "very_hot"
    if 38 <= p <= 42:
        return "hot"
    if 34 <= p < 38:
        return "warm"
    if 30 <= p < 34:
        return "slight_warm"
    if 26 <= p < 30:
        return "neutral"
    if 22 <= p < 26:
        return "slight_cool"
    if 18 <= p < 22:
        return "cool"
    if 14 <= p < 18:
        return "cold"
    return "very_cold"
