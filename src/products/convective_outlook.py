# src/products/convective_outlook.py
from src.products.base import BaseProduct
import urllib.request
import json

class ConvectiveOutlookProduct(BaseProduct):
    def __init__(self, day=1):
        self.day = day
        self.risk_colors = [
            ("TSTM", "#B7E9C1"),
            ("MRGL", "#7FE57F"),
            ("SLGT", "#FFE57F"),
            ("ENH",  "#FFA54F"),
            ("MDT",  "#E50000"),
            ("HIGH", "#E500E5")
        ]

    @property
    def name(self) -> str:
        return f"SPC Day {self.day} Convective Outlook"

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
        """Queries SPC Day 1-3 Categorical GeoJSON layers directly from NOAA servers."""
        url = f"https://www.spc.noaa.gov/products/outlook/day{self.day}otlk_cat.lyr.geojson"
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode('utf-8'))
                return data.get("features", [])
        except Exception as e:
            print(f"Error fetching SPC GeoJSON: {e}")
            return []
