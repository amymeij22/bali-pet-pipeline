import sys
from pathlib import Path

import pandas as pd

# Agar import modul di folder induk `src/` berfungsi saat pytest dari root/repo
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from biometeo_worker.main import build_grp_and_exports


def test_build_grp_and_exports_destination_name_in_row_overrides_mapping():
    produced_at = "2026-01-01T00:00:00Z"
    grp = pd.DataFrame(
        [
            {
                "kdepum_code": "51.03.01.1002",
                "village_name": "Kuta",
                "destination_name": "Pantai Kuta",
                "utc_datetime": "2026-01-01T00:00:00Z",
                "local_datetime": "2026-01-01T08:00:00+08:00",
                "t": 28.0,
                "hu": 65.0,
                "ws": 10.0,
                "wd": "E",
                "weather_desc": "Cerah",
                "vs_text": "Baik",
                "tcc": 50.0,
                "latitude": -8.7,
                "longitude": 115.1,
                "sea_level_height": 5.0,
                "N_oktas": 4.0,
                "wind_speed_1_1m_ms": 0.6,
                "cloud_cover_percent": 50.0,
                "tmrt": 30.0,
                "vapor_pressure": 20.0,
                "pet_value": 31.0,
            }
        ]
    )
    kdep_to_dests = {"51.03.01.1002": ["A", "B"]}

    db_rows, raw_df, proc_df, class_df, final_df = build_grp_and_exports(
        grp, kdep_to_dests, produced_at, include_db_rows=False
    )

    assert db_rows == []
    assert len(raw_df) == 1
    assert set(raw_df["lokasi_wisata"].tolist()) == {"Pantai Kuta"}
    assert len(proc_df) == 1
    assert len(class_df) == 1
    assert len(final_df) == 1
    assert set(final_df["destination_name"].tolist()) == {"Pantai Kuta"}


def test_build_grp_and_exports_falls_back_to_mapping_when_destination_name_missing():
    produced_at = "2026-01-01T00:00:00Z"
    grp = pd.DataFrame(
        [
            {
                "kdepum_code": "51.03.01.1002",
                "village_name": "Kuta",
                "utc_datetime": "2026-01-01T00:00:00Z",
                "local_datetime": "2026-01-01T08:00:00+08:00",
                "t": 28.0,
                "hu": 65.0,
                "ws": 10.0,
                "wd": "E",
                "weather_desc": "Cerah",
                "vs_text": "Baik",
                "tcc": 50.0,
                "latitude": -8.7,
                "longitude": 115.1,
                "sea_level_height": 5.0,
                "N_oktas": 4.0,
                "wind_speed_1_1m_ms": 0.6,
                "cloud_cover_percent": 50.0,
                "tmrt": 30.0,
                "vapor_pressure": 20.0,
                "pet_value": 31.0,
            }
        ]
    )
    kdep_to_dests = {"51.03.01.1002": ["Dest A", "Dest B"]}

    _, raw_df, _, _, final_df = build_grp_and_exports(grp, kdep_to_dests, produced_at, include_db_rows=False)

    assert set(raw_df["lokasi_wisata"].tolist()) == {"Dest A", "Dest B"}
    assert set(final_df["destination_name"].tolist()) == {"Dest A", "Dest B"}

