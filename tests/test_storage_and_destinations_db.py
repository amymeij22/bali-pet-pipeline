import sys
from pathlib import Path

import pytest

# Agar import modul di folder induk `cloudrun/` berfungsi saat pytest dari root/repo
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from destinations_source_db import validate_destination_configs
from storage import _content_type


def test_storage_content_type():
    assert _content_type("x.json") == "application/json"
    assert _content_type("x.JSON") == "application/json"
    assert _content_type("x.csv") == "text/csv"
    assert _content_type("x.CSV") == "text/csv"
    assert _content_type("x.bin") == "application/octet-stream"


def test_validate_destination_configs_missing_fields_raises():
    destinations = [
        {
            "destination_name": "Pantai Kuta",
            "kdepum_code": "51.03.01.1002",
            "village_name": "Kuta",
            "regency": "Badung",
            "district": "",  # invalid
            "latitude": -8.7,
            "longitude": 115.1,
            "sea_level_height": 5.0,
        }
    ]
    with pytest.raises(ValueError, match=r"tidak lengkap"):
        validate_destination_configs(destinations)  # type: ignore[arg-type]


def test_validate_destination_configs_ok():
    destinations = [
        {
            "destination_name": "Pantai Kuta",
            "kdepum_code": "51.03.01.1002",
            "village_name": "Kuta",
            "regency": "Badung",
            "district": "Kuta",
            "latitude": -8.7,
            "longitude": 115.1,
            "sea_level_height": 5.0,
        }
    ]
    validate_destination_configs(destinations)  # should not raise

