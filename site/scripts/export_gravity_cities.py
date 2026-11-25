"""Write site/public/data/gravity-cities.json, the Local gravity calculator's city list, from GeoNames files.

  curl -O https://download.geonames.org/export/dump/cities15000.zip  (unzip it)
  curl -O https://download.geonames.org/export/dump/admin1CodesASCII.txt
  curl -O https://download.geonames.org/export/dump/countryInfo.txt
  python site/scripts/export_gravity_cities.py <folder with the three files> --date YYYY-MM-DD
"""
import argparse
from pathlib import Path

import _lib  # noqa: F401  (puts python/ on the path)
from mvis_site import SITE
from mvis_site.gravity_cities import build, write

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("folder", type=Path)
ap.add_argument("--date", required=True, help="download date, shown as the list's source")
ap.add_argument("--out", type=Path, default=SITE / "public/data/gravity-cities.json")
a = ap.parse_args()
read = lambda n: (a.folder / n).read_text(encoding="utf-8")
obj = build(read("cities15000.txt"), read("admin1CodesASCII.txt"), read("countryInfo.txt"), a.date)
a.out.parent.mkdir(parents=True, exist_ok=True)
n = write(obj, a.out)
print(f"{a.out}: {len(obj['cities'])} cities, {len(obj['countries'])} countries, {n / 1e6:.2f} MB")
