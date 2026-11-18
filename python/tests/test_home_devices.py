"""Homepage device band: every device page has its small photo, and the photos stay small."""
import json
from pathlib import Path

SITE = Path(__file__).resolve().parents[2] / "site"
THUMBS = SITE / "public/media/home-devices"


def test_every_device_page_has_a_home_photo():
    slugs = {f.stem for f in (SITE / "src/data/sensors").glob("*.json")} | {"virig"}
    have = {f.stem for f in THUMBS.glob("*.webp")}
    assert slugs - have == set(), "run python site/scripts/export_home_devices.py"
    assert have - slugs == set(), "photo for a device page that is gone"


def test_home_photos_stay_small():
    assert sum(f.stat().st_size for f in THUMBS.glob("*.webp")) < 150_000
    for f in (SITE / "src/data/sensors").glob("*.json"):
        assert json.loads(f.read_text())["card"]["maker"]
