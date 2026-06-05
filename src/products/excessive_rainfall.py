# src/products/excessive_rainfall.py
from src.products.base import BaseProduct
import urllib.request
import json

class ExcessiveRainfallProduct(BaseProduct):
    def __init__(self, day=1):
        self.day = day
        self.risk_colors = [
            ("MRGL", "#55aa55"),
            ("SLGT", "#ffe066"),
            ("MDT",  "#cc1111"),
            ("HIGH", "#e500e5")
        ]

    @property
    def name(self) -> str:
        return f"WPC Day {self.day} Excessive Rainfall Outlook"

    @property
    def unit_label(self) -> str:
        return ""

    @property
    def val_suffix(self) -> str:
        return ""

    @property
    def colormap_ticks(self) -> list:
        return []

    @property
    def color_points(self) -> list:
        return []

    @property
    def vmin(self) -> float:
        return 0.0

    @property
    def vmax(self) -> float:
        return 1.0

    def get_candidates(self, model_endpoint: dict, map_type: str) -> list:
        return []

    def process_units(self, subset_data, raw_unit_string: str):
        return subset_data

    def aggregate_time(self, subset_day, time_dim: str, map_type: str):
        return subset_day

    def fetch_geojson(self):
        """Queries WPC Day 1-5 Excessive Rainfall Outlook GeoJSON files directly from WPC servers."""
        url = f"https://www.wpc.ncep.noaa.gov/exper/eromap/geojson/Day{self.day}_Latest.geojson"
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode('utf-8'))
                return data.get("features", [])
        except Exception as e:
            print(f"Error fetching WPC Excessive Rainfall GeoJSON: {e}")
            return []
