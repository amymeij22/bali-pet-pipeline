"""
Master destinasi wisata → desa (KDEPUM) + koordinat dan elevasi statis untuk biometeo.

Koordinat dan sea_level_height harus sesuai metodologi penelitian (titik referensi / sumber resmi).
"""

from __future__ import annotations

from typing import Any, TypedDict


class DestinationConfig(TypedDict):
    destination_name: str
    kdepum_code: str
    village_name: str
    regency: str
    district: str
    latitude: float
    longitude: float
    sea_level_height: float


# 49 destinasi (data skripsi terbaru)
DESTINATIONS: list[DestinationConfig] = [
    {"destination_name": "Alas Pala", "kdepum_code": "51.03.03.2013", "village_name": "Sangeh", "regency": "Badung", "district": "Abiansemal", "latitude": -8.4815663, "longitude": 115.0623502, "sea_level_height": 156},
    {"destination_name": "Bali Elephant Camp", "kdepum_code": "51.03.04.2001", "village_name": "Carangsari", "regency": "Badung", "district": "Petang", "latitude": -8.4342062, "longitude": 115.2113454, "sea_level_height": 406},
    {"destination_name": "Pantai Kuta", "kdepum_code": "51.03.01.1002", "village_name": "Kuta", "regency": "Badung", "district": "Kuta", "latitude": -8.7180324, "longitude": 115.1577348, "sea_level_height": 0},
    {"destination_name": "Pantai Legian", "kdepum_code": "51.03.01.1004", "village_name": "Legian", "regency": "Badung", "district": "Kuta", "latitude": -8.703364, "longitude": 115.1589967, "sea_level_height": 0},
    {"destination_name": "Pantai Labuan Sait", "kdepum_code": "51.03.05.2001", "village_name": "Pecatu", "regency": "Badung", "district": "Kuta Selatan", "latitude": -8.8116192, "longitude": 115.0828843, "sea_level_height": 0},
    {"destination_name": "Pantai Melasti", "kdepum_code": "51.03.05.2002", "village_name": "Ungasan", "regency": "Badung", "district": "Kuta Selatan", "latitude": -8.8116097, "longitude": 115.0210808, "sea_level_height": 0},
    {"destination_name": "Pantai Pandawa", "kdepum_code": "51.03.05.2003", "village_name": "Kutuh", "regency": "Badung", "district": "Kuta Selatan", "latitude": -8.8448081, "longitude": 115.1813756, "sea_level_height": 86},
    {"destination_name": "Pantai Nusa Dua", "kdepum_code": "51.03.05.1005", "village_name": "Tanjung Benoa", "regency": "Badung", "district": "Kuta Selatan", "latitude": -8.7958519, "longitude": 115.2312122, "sea_level_height": 16},
    {"destination_name": "Pantai Tanjung Benoa", "kdepum_code": "51.03.05.1005", "village_name": "Tanjung Benoa", "regency": "Badung", "district": "Kuta Selatan", "latitude": -8.7604004, "longitude": 115.2176213, "sea_level_height": 4},
    {"destination_name": "Water Blow Peninsula", "kdepum_code": "51.03.05.1005", "village_name": "Tanjung Benoa", "regency": "Badung", "district": "Kuta Selatan", "latitude": -8.8038567, "longitude": 115.237289, "sea_level_height": 0},
    {"destination_name": "Wisata Agro Pelaga", "kdepum_code": "51.03.04.2004", "village_name": "Pelaga", "regency": "Badung", "district": "Petang", "latitude": -8.2845269, "longitude": 115.222886, "sea_level_height": 985},
    {"destination_name": "Desa Songan", "kdepum_code": "51.06.04.2024", "village_name": "Songan A", "regency": "Bangli", "district": "Kintamani", "latitude": -8.2284399, "longitude": 115.3693253, "sea_level_height": 1250},
    {"destination_name": "Pendakian Gunung Abang", "kdepum_code": "51.06.04.2021", "village_name": "Suter", "regency": "Bangli", "district": "Kintamani", "latitude": -8.228431, "longitude": 115.3075218, "sea_level_height": 1385},
    {"destination_name": "Pendakian Gunung Batur", "kdepum_code": "51.06.04.2025", "village_name": "Songan B", "regency": "Bangli", "district": "Kintamani", "latitude": -8.2616912, "longitude": 115.3888049, "sea_level_height": 1056},
    {"destination_name": "Goa Raja Waterfall", "kdepum_code": "51.06.03.2001", "village_name": "Jehem", "regency": "Bangli", "district": "Tembuku", "latitude": -8.441662, "longitude": 115.3734351, "sea_level_height": 470},
    {"destination_name": "Air Panas Desa Banjar", "kdepum_code": "51.08.04.2013", "village_name": "Banjar", "regency": "Buleleng", "district": "Banjar", "latitude": -8.2106057, "longitude": 114.9644437, "sea_level_height": 99},
    {"destination_name": "Air Panas Banyuwedang", "kdepum_code": "51.08.01.2002", "village_name": "Pejarakan", "regency": "Buleleng", "district": "Gerokgak", "latitude": -8.13925, "longitude": 114.5681101, "sea_level_height": 0},
    {"destination_name": "Taman Laut Pemuteran", "kdepum_code": "51.08.01.2002", "village_name": "Pejarakan", "regency": "Buleleng", "district": "Gerokgak", "latitude": -8.1368627, "longitude": 114.5959239, "sea_level_height": 0},
    {"destination_name": "Air Terjun Aling-Aling", "kdepum_code": "51.08.05.2010", "village_name": "Sambangan", "regency": "Buleleng", "district": "Sukasada", "latitude": -8.1746122, "longitude": 115.1021535, "sea_level_height": 291},
    {"destination_name": "Air Terjun Banyumala", "kdepum_code": "51.08.05.2002", "village_name": "Wanagiri", "regency": "Buleleng", "district": "Sukasada", "latitude": -8.2171873, "longitude": 115.0991062, "sea_level_height": 1108},
    {"destination_name": "Air Terjun Campuhan", "kdepum_code": "51.08.05.2004", "village_name": "Gitgit", "regency": "Buleleng", "district": "Sukasada", "latitude": -8.2838505, "longitude": 115.0692169, "sea_level_height": 939},
    {"destination_name": "Air Terjun Fiji", "kdepum_code": "51.08.07.2001", "village_name": "Lemukih", "regency": "Buleleng", "district": "Sawan", "latitude": -8.1804559, "longitude": 115.178985, "sea_level_height": 515},
    {"destination_name": "Air Terjun Sekumpul", "kdepum_code": "51.08.07.2003", "village_name": "Sekumpul", "regency": "Buleleng", "district": "Sawan", "latitude": -8.1775304, "longitude": 115.1641284, "sea_level_height": 761},
    {"destination_name": "Hutan Raya Selat", "kdepum_code": "51.08.05.2014", "village_name": "Selat", "regency": "Buleleng", "district": "Sukasada", "latitude": -8.1931077, "longitude": 115.0616015, "sea_level_height": 493},
    {"destination_name": "Pantai Lovina", "kdepum_code": "51.08.06.2001", "village_name": "Kalibukbuk", "regency": "Buleleng", "district": "Buleleng", "latitude": -8.1606083, "longitude": 115.0093154, "sea_level_height": 0},
    {"destination_name": "Desa Budaya Kertalangu", "kdepum_code": "51.71.02.1003", "village_name": "Kesiman", "regency": "Denpasar", "district": "Denpasar Timur", "latitude": -8.6422868, "longitude": 115.2539177, "sea_level_height": 33},
    {"destination_name": "Pantai Sanur", "kdepum_code": "51.71.01.2009", "village_name": "Sanur Kaja", "regency": "Denpasar", "district": "Denpasar Selatan", "latitude": -8.6958045, "longitude": 115.2389267, "sea_level_height": 5},
    {"destination_name": "Air Terjun Tegenungan", "kdepum_code": "51.04.01.2008", "village_name": "Kemenuh", "regency": "Gianyar", "district": "Sukawati", "latitude": -8.5753621, "longitude": 115.286385, "sea_level_height": 91},
    {"destination_name": "Ceking (Panorama)", "kdepum_code": "51.04.06.2002", "village_name": "Tegallalang", "regency": "Gianyar", "district": "Tegallalang", "latitude": -8.4317112, "longitude": 115.2767281, "sea_level_height": 435},
    {"destination_name": "Lembu Putih", "kdepum_code": "51.04.06.2007", "village_name": "Taro", "regency": "Gianyar", "district": "Tegallalang", "latitude": -8.3923938, "longitude": 115.2828888, "sea_level_height": 607},
    {"destination_name": "Wanara Wana (Pura Dalem)", "kdepum_code": "51.04.05.1005", "village_name": "Padang Tegal", "regency": "Gianyar", "district": "Ubud", "latitude": -8.3923853, "longitude": 115.2030606, "sea_level_height": 513},
    {"destination_name": "Pantai Selukat", "kdepum_code": "51.04.02.2003", "village_name": "Keramas", "regency": "Gianyar", "district": "Blahbatuh", "latitude": -8.5991131, "longitude": 115.3351202, "sea_level_height": 8},
    {"destination_name": "Teluk Gilimanuk", "kdepum_code": "51.01.04.1001", "village_name": "Gilimanuk", "regency": "Jembrana", "district": "Melaya", "latitude": -8.1644317, "longitude": 114.4354295, "sea_level_height": 2},
    {"destination_name": "Agro Kebun Salak Sibetan", "kdepum_code": "51.07.06.2004", "village_name": "Sibetan", "regency": "Karangasem", "district": "Bebandem", "latitude": -8.4458761, "longitude": 115.5196318, "sea_level_height": 589},
    {"destination_name": "Bukit Surga", "kdepum_code": "51.07.06.2005", "village_name": "Jungutan", "regency": "Karangasem", "district": "Bebandem", "latitude": -8.4458739, "longitude": 115.4835816, "sea_level_height": 495},
    {"destination_name": "Pesona Bukit Lempuyang", "kdepum_code": "51.07.05.2014", "village_name": "Tri Buana", "regency": "Karangasem", "district": "Abang", "latitude": -8.8229519, "longitude": 115.1430077, "sea_level_height": 194},
    {"destination_name": "Pesona Kebun Bunga Besakih", "kdepum_code": "51.07.01.2004", "village_name": "Besakih", "regency": "Karangasem", "district": "Rendang", "latitude": -8.4383019, "longitude": 115.4300515, "sea_level_height": 501},
    {"destination_name": "Hutan Mangrove", "kdepum_code": "51.05.01.2013", "village_name": "Jungutbatu", "regency": "Klungkung", "district": "Nusa Penida", "latitude": -8.7243311, "longitude": 115.1891994, "sea_level_height": 2},
    {"destination_name": "Kawasan Tukad Melangit", "kdepum_code": "51.05.02.2005", "village_name": "Bakas", "regency": "Klungkung", "district": "Banjarangkan", "latitude": -8.6253266, "longitude": 115.2148915, "sea_level_height": 47},
    {"destination_name": "Lingkungan Goa Lawah", "kdepum_code": "51.05.04.2008", "village_name": "Pesinggahan", "regency": "Klungkung", "district": "Dawan", "latitude": -8.5530688, "longitude": 115.4469457, "sea_level_height": 9},
    {"destination_name": "Alas Kedaton", "kdepum_code": "51.02.07.2001", "village_name": "Kukuh", "regency": "Tabanan", "district": "Marga", "latitude": -8.5275338, "longitude": 115.1518152, "sea_level_height": 151},
    {"destination_name": "Areal Batukaru", "kdepum_code": "51.02.08.2014", "village_name": "Wangaya Gede", "regency": "Tabanan", "district": "Penebel", "latitude": -8.4366533, "longitude": 114.9299979, "sea_level_height": 277},
    {"destination_name": "Hutan Mekori", "kdepum_code": "51.02.10.2001", "village_name": "Belimbing", "regency": "Tabanan", "district": "Pupuan", "latitude": -8.3838457, "longitude": 115.0241855, "sea_level_height": 627},
    {"destination_name": "Jatiluwih", "kdepum_code": "51.02.08.2013", "village_name": "Jatiluwih", "regency": "Tabanan", "district": "Penebel", "latitude": -8.3565704, "longitude": 115.0775998, "sea_level_height": 1312},
    {"destination_name": "Kebun Raya Eka Karya Bedugul", "kdepum_code": "51.02.09.2008", "village_name": "Candikuning", "regency": "Tabanan", "district": "Baturiti", "latitude": -8.2761215, "longitude": 115.151628, "sea_level_height": 1359},
    {"destination_name": "Ulun Danau Beratan", "kdepum_code": "51.02.09.2008", "village_name": "Candikuning", "regency": "Tabanan", "district": "Baturiti", "latitude": -8.2751807, "longitude": 115.1642485, "sea_level_height": 1246},
    {"destination_name": "Tanah Lot", "kdepum_code": "51.02.06.2004", "village_name": "Braban", "regency": "Tabanan", "district": "Kediri", "latitude": -8.6212129, "longitude": 115.0860205, "sea_level_height": 0},
    {"destination_name": "Yeh Panas dan Hutan Bambu Angseri", "kdepum_code": "51.02.09.2004", "village_name": "Angseri", "regency": "Tabanan", "district": "Baturiti", "latitude": -8.3620025, "longitude": 115.1514628, "sea_level_height": 678},
    {"destination_name": "Yeh Panes Penatahan", "kdepum_code": "51.02.08.2007", "village_name": "Penatahan", "regency": "Tabanan", "district": "Penebel", "latitude": -8.4340624, "longitude": 115.1223064, "sea_level_height": 357},
]


def build_unique_villages(destinations: list[DestinationConfig]) -> list[dict[str, Any]]:
    """Satu entri per kdepum_code: gabungkan daftar nama destinasi pada desa yang sama."""
    by_kdep: dict[str, dict[str, Any]] = {}
    for d in destinations:
        k = d["kdepum_code"]
        if k not in by_kdep:
            by_kdep[k] = {
                "kdepum_code": k,
                "village_name": d["village_name"],
                "latitude": d["latitude"],
                "longitude": d["longitude"],
                "sea_level_height": d["sea_level_height"],
                "destination_names": [],
            }
        name = d["destination_name"]
        if name not in by_kdep[k]["destination_names"]:
            by_kdep[k]["destination_names"].append(name)
    return list(by_kdep.values())
