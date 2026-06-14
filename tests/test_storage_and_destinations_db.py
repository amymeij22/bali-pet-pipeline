import sys
from pathlib import Path

import pytest

# Agar import modul di folder induk `src/` berfungsi saat pytest dari root/repo
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from biometeo_worker.destinations_source_db import validate_destination_configs
from biometeo_worker.storage import _content_type


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


def test_build_unique_villages():
    from biometeo_worker.destinations import build_unique_villages, DESTINATIONS
    
    # 1. Test using the real DESTINATIONS list
    results = build_unique_villages(DESTINATIONS)
    assert len(results) > 0
    
    # 2. Test custom list to hit all logic branches (same kdepum_code with different names, same kdepum_code with same name)
    custom_dests = [
        {
            "destination_name": "Dest A",
            "kdepum_code": "code1",
            "village_name": "Vil A",
            "regency": "Reg A",
            "district": "Dist A",
            "latitude": 1.0,
            "longitude": 2.0,
            "sea_level_height": 10.0
        },
        {
            "destination_name": "Dest B",
            "kdepum_code": "code1",
            "village_name": "Vil A",
            "regency": "Reg A",
            "district": "Dist A",
            "latitude": 1.0,
            "longitude": 2.0,
            "sea_level_height": 10.0
        },
        {
            "destination_name": "Dest A",
            "kdepum_code": "code1",
            "village_name": "Vil A",
            "regency": "Reg A",
            "district": "Dist A",
            "latitude": 1.0,
            "longitude": 2.0,
            "sea_level_height": 10.0
        }
    ]
    unique = build_unique_villages(custom_dests)  # type: ignore[arg-type]
    assert len(unique) == 1
    assert unique[0]["kdepum_code"] == "code1"
    assert unique[0]["destination_names"] == ["Dest A", "Dest B"]


