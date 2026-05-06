import math

import pytest

from classification import classify_pet


def test_temperate_boundaries():
    assert classify_pet(41.1, "temperate") == "very_hot"
    assert classify_pet(41.0, "temperate") == "hot"
    assert classify_pet(35.0001, "temperate") == "hot"
    assert classify_pet(35.0, "temperate") == "warm"
    assert classify_pet(4.0, "temperate") == "cold"
    assert classify_pet(3.9, "temperate") == "very_cold"


def test_subtropic_boundaries():
    assert classify_pet(42.1, "sub_tropic") == "very_hot"
    assert classify_pet(42.0, "sub_tropic") == "hot"
    assert classify_pet(14.0, "sub_tropic") == "cold"
    assert classify_pet(13.9, "sub_tropic") == "very_cold"


def test_nan_returns_none():
    assert classify_pet(float("nan"), "temperate") is None
    assert classify_pet(None, "sub_tropic") is None


def test_invalid_standard():
    with pytest.raises(ValueError):
        classify_pet(20.0, "tropical")
