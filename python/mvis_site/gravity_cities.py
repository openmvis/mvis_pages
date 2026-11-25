"""The city list behind the Local gravity calculator's search box (site/public/data/gravity-cities.json).

Built from GeoNames (CC BY 4.0, https://www.geonames.org/): `cities15000.txt` (every place over 15,000 people),
`admin1CodesASCII.txt` (region names) and `countryInfo.txt` (country names), from
https://download.geonames.org/export/dump/. Gravity needs only latitude and altitude, so a row keeps
[name, country code, region code, latitude to 2 decimals, altitude in m]; the browser folds accents for the
search and computes g. Rows are sorted by population, largest first, which is the search's ranking. Altitude is GeoNames'
elevation, else its terrain-model height (dem), else 0.
"""
from __future__ import annotations

import json
from pathlib import Path

SOURCE = "GeoNames cities15000 (CC BY 4.0, geonames.org), every place over 15,000 people"


def _altitude(elevation: str, dem: str) -> int:
    for v in (elevation, dem):
        if v.strip() and int(float(v)) > -1000:   # dem is -9999 where it has no value
            return int(round(float(v)))
    return 0


def build(cities: str, admin1: str, countries: str, date: str) -> dict:
    """The JSON object from the three GeoNames files' text. A region code without a name in admin1 is dropped."""
    known = dict(f[:2] for f in (line.split("\t") for line in admin1.splitlines()) if len(f) >= 2)
    rows, regions, used_countries = [], {}, set()
    for line in cities.splitlines():
        f = line.split("\t")
        if len(f) < 17:
            continue
        name, lat, cc, a1, pop = f[1], float(f[4]), f[8], f[10], int(f[14] or 0)
        region = f"{cc}.{a1}" if f"{cc}.{a1}" in known else ""
        if region:
            regions[region] = known[region]
        rows.append((pop, [name, cc, region, round(lat, 2), _altitude(f[15], f[16])]))
        used_countries.add(cc)
    rows.sort(key=lambda r: -r[0])   # stable: equal populations keep the file's order
    country_names = {}
    for line in countries.splitlines():
        f = line.split("\t")
        if not line.startswith("#") and len(f) >= 5 and f[0] in used_countries:
            country_names[f[0]] = f[4]
    return {"source": f"{SOURCE}, downloaded {date}", "countries": dict(sorted(country_names.items())),
            "regions": dict(sorted(regions.items())), "cities": [r for _, r in rows]}


def write(obj: dict, out: Path) -> int:
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    out.write_text(text + "\n", encoding="utf-8")
    return len(text.encode("utf-8"))
