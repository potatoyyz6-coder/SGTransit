"""Coordinate discovery only: distance is not pedestrian accessibility."""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class CatalogStop:
    id: str
    name: str
    longitude: float
    latitude: float

    def __post_init__(self):
        if not self.id or not self.name:
            raise ValueError('A stop needs an ID and name')
        for value, bound in ((self.longitude, 180), (self.latitude, 90)):
            if isinstance(value, bool) or not math.isfinite(value) or not -bound <= value <= bound:
                raise ValueError('Invalid stop coordinates')


def distance_m(a, b):
    """Great-circle distance; no street crossing or walk-time inference."""
    lat1, lat2 = math.radians(a.latitude), math.radians(b.latitude)
    dlat, dlon = lat2-lat1, math.radians(b.longitude-a.longitude)
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 2 * 6371008.8 * math.asin(math.sqrt(min(1, max(0, h))))


class StationCatalog:
    def __init__(self, stops):
        records = list(stops)
        self.stops = {s.id: s for s in records}
        if len(self.stops) != len(records):
            raise ValueError('Duplicate catalog stop ID')

    def search(self, text, limit=25):
        text = text.strip().casefold()
        matches = [s for s in self.stops.values() if text in s.id.casefold() or text in s.name.casefold()]
        matches.sort(key=lambda s: (s.id.casefold() != text, s.name.casefold(), s.id))
        return matches[:limit], len(matches)

    def nearby(self, center, radius=400, cap=3):
        if center not in self.stops:
            raise KeyError(center)
        if isinstance(radius, bool) or not math.isfinite(radius) or not 0 <= radius <= 2000:
            raise ValueError('Radius must be between 0 and 2000 metres')
        if isinstance(cap, bool) or not isinstance(cap, int) or not 1 <= cap <= 3:
            raise ValueError('Select at most three stops per end')
        origin = self.stops[center]
        candidates = [(s, distance_m(origin, s)) for s in self.stops.values()]
        candidates = [(s, d) for s, d in candidates if d <= radius + 1e-8 or s.id == center]
        candidates.sort(key=lambda item: (item[0].id != center, item[1], item[0].id))
        return candidates, [s.id for s, _ in candidates[:cap]]
