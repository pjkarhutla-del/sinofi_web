"""Klien API SIPONGI (opsroom) — padanan pemanggilan fetch() pada Monitor Hotspot lama."""
import logging
from datetime import date

import requests
from django.conf import settings

log = logging.getLogger(__name__)


def build_params(date_from=None, date_to=None):
    """Parameter query identik dengan aplikasi lama. Tanpa tanggal = periode default server."""
    use_period = bool(date_from and date_to)
    params = [
        ("wilayah", "IN"),
        ("filterperiode", "true" if use_period else "false"),
        ("from", date_from.isoformat() if use_period else ""),
        ("to", date_to.isoformat() if use_period else ""),
        ("late", "custom"),
    ]
    params += [("satelit[]", s) for s in settings.SIPONGI_SATELIT]
    params += [("confidence[]", c) for c in ("low", "medium", "high")]
    params += [("provinsi", ""), ("kabkota", "")]
    return params


def extract_features(payload):
    """API dapat mengembalikan FeatureCollection, {features: FeatureCollection}, atau list."""
    feats = payload.get("features", []) if isinstance(payload, dict) else payload
    if isinstance(feats, dict):
        feats = feats.get("features", [])
    return feats if isinstance(feats, list) else []


def fetch_features(date_from=None, date_to=None, session=None):
    http = session or requests
    resp = http.get(settings.SIPONGI_API_URL, params=build_params(date_from, date_to),
                    timeout=settings.SIPONGI_TIMEOUT, headers={"Accept": "application/json"})
    resp.raise_for_status()
    return extract_features(resp.json())


def parse_feature(feature):
    """Feature GeoJSON -> dict siap simpan, atau None bila tidak valid."""
    try:
        props = feature.get("properties") or {}
        lon, lat = (float(v) for v in feature["geometry"]["coordinates"][:2])
    except (KeyError, TypeError, ValueError, AttributeError):
        return None
    hs_id = str(props.get("hs_id") or "").strip()
    conf = str(props.get("confidence_level") or "").strip().lower()
    waktu = str(props.get("date_hotspot") or "")
    tanggal = None
    for candidate in (hs_id[:10], waktu[:10]):
        try:
            tanggal = date.fromisoformat(candidate)
            break
        except ValueError:
            continue
    if not hs_id or not conf or tanggal is None:
        return None
    return {"hs_id": hs_id, "tanggal": tanggal, "waktu": waktu[:60], "confidence": conf,
            "satelit": str(props.get("satelit") or props.get("satellite") or "")[:60],
            "lat": lat, "lon": lon}
