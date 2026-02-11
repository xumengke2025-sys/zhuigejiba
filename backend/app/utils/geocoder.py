import json
import os
import threading
import time
from typing import Any, Dict, Optional

import requests


class NominatimGeocoder:
    def __init__(self, cache_path: Optional[str] = None, min_interval_sec: float = 1.0):
        self.cache_path = cache_path
        self.min_interval_sec = min_interval_sec
        self._lock = threading.Lock()
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._last_request_ts = 0.0
        self._unsaved_changes = 0
        self._load_cache()

    def _load_cache(self) -> None:
        if not self.cache_path:
            return
        try:
            if os.path.exists(self.cache_path):
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._cache = data
        except Exception:
            self._cache = {}

    def _save_cache(self, force: bool = False) -> None:
        if not self.cache_path:
            return
        
        self._unsaved_changes += 1
        if not force and self._unsaved_changes < 10:
            return

        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
            self._unsaved_changes = 0
        except Exception:
            pass

    def flush(self) -> None:
        with self._lock:
            self._save_cache(force=True)

    def geocode(self, query: str) -> Optional[Dict[str, Any]]:
        query = (query or '').strip()
        if not query:
            return None

        # Fast path: check cache without lock (dict get is atomic in Python)
        cached = self._cache.get(query)
        if isinstance(cached, dict):
            return cached

        with self._lock:
            # Double-check locking
            cached = self._cache.get(query)
            if isinstance(cached, dict):
                return cached

            now = time.time()
            wait = self.min_interval_sec - (now - self._last_request_ts)
            if wait > 0:
                time.sleep(wait)

            url = "https://nominatim.openstreetmap.org/search"

            params = {
                "q": query,
                "format": "json",
                "limit": 1,
                "addressdetails": 1
            }
            headers = {
                "User-Agent": "footprints/0.1 (local project)"
            }
            try:
                resp = requests.get(url, params=params, headers=headers, timeout=15)
                self._last_request_ts = time.time()
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, list) and data:
                    item = data[0]
                    lat = item.get("lat")
                    lon = item.get("lon")
                    if lat is None or lon is None:
                        return None
                    result = {
                        "lat": float(lat),
                        "lon": float(lon),
                        "display_name": item.get("display_name"),
                        "provider": "nominatim",
                        "confidence": 0.6
                    }
                    self._cache[query] = result
                    self._save_cache()
                    return result
            except Exception:
                self._last_request_ts = time.time()
                return None

        return None

