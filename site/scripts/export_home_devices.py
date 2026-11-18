"""Small photos for the homepage device band: one 360×240 WebP per device page, plus the VI-Rig.

    python site/scripts/export_home_devices.py      # writes site/public/media/home-devices/<slug>.webp
"""
import json
from pathlib import Path

from PIL import Image, ImageOps

SITE = Path(__file__).resolve().parents[1]
OUT = SITE / "public/media/home-devices"
SIZE = (360, 240)


def sources() -> dict[str, Path]:
    """slug -> full-size photo: every device card, and the VI-Rig photo."""
    out = {"virig": SITE / "src/assets/vi_rig.jpg"}
    for f in sorted((SITE / "src/data/sensors").glob("*.json")):
        out[f.stem] = SITE / "public" / json.loads(f.read_text())["card"]["image"].lstrip("/")
    return out


def thumb(src: Path, dst: Path) -> None:
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    ImageOps.fit(im, SIZE, Image.LANCZOS).save(dst, "WEBP", quality=72, method=6)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for slug, src in sources().items():
        thumb(src, OUT / f"{slug}.webp")
        print(slug, (OUT / f"{slug}.webp").stat().st_size)
