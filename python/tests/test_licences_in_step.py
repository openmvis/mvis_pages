"""One list of dataset licences: site/src/data/licences.json, rendered on About → License. Device pages, the homepage clip
credits and the page text keep short notices of their own; these tests fail when one of them disagrees with the list.
With MVIS_MIRA set to the private workspace, the Hugging Face community card source is checked too."""
import json
import os
import re
from pathlib import Path

import pytest
import yaml

from mvis_site import SITE

DATA = Path(__file__).resolve().parents[1] / "data"
LIC = json.loads((SITE / "src/data/licences.json").read_text(encoding="utf-8"))
HOSTED, LINKED = LIC["hosted"], LIC["linked"]
KNOWN = {"CC BY 4.0", "CC BY-NC-SA 3.0", "CC BY, no version given", "GPL-2.0", "none stated", "none stated; citation asked"}
BY_URL = "https://creativecommons.org/licenses/by/4.0/"


def test_ids_are_unique_stable_anchors_and_licences_come_from_the_fixed_list():
    ids = [r["id"] for r in HOSTED + LINKED]
    assert len(ids) == len(set(ids)) and all(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", i) for i in ids)
    assert {r["licence"] for r in HOSTED + LINKED} <= KNOWN
    assert all(r["licence_url"] == BY_URL for r in HOSTED if r["licence"] == "CC BY 4.0")
    assert all(re.fullmatch(r"\d{4}-\d\d-\d\d|upstream", r["since"]) for r in HOSTED)


def test_every_recording_we_host_is_cc_by():
    """User decisions of 2026-11-25 and 2026-11-26: nothing hosted is non-commercial. A new row under another licence is a
    decision, not a data edit: change this test with it. The page shows no licence history (user, 2026-11-26)."""
    assert {r["licence"] for r in HOSTED} == {"CC BY 4.0"} and not any("was" in r for r in HOSTED)


def test_every_device_page_has_a_row_and_agrees_with_it():
    sensors = yaml.safe_load((DATA / "public_sensors.yaml").read_text(encoding="utf-8"))["sensors"]
    assert {r["device"] for r in HOSTED if "device" in r} == set(sensors)
    for slug in sensors:
        text = yaml.safe_dump(sensors[slug], allow_unicode=True)
        assert "BY-NC 4.0" not in text and "by request" not in text, slug
        if slug != "robobaton-neo":   # its page gives the licence inside the Data row only
            assert "CC BY" in text, slug


def test_homepage_clip_credits_use_a_listed_licence():
    rigs = json.loads((SITE / "public/media/hero/rigs.json").read_text(encoding="utf-8"))["rigs"]
    for r in rigs:
        c = r["credit"]
        assert (c["licence"], c["licence_url"]) == ("CC BY 4.0", BY_URL), r["key"]


def test_pages_point_to_the_list_and_state_no_old_default():
    docs = SITE / "src/content/docs"
    page = (docs / "about/license.mdx").read_text(encoding="utf-8")
    assert page.count("<LicenceTables part=") == 2 and "history" not in page.lower() and "## Datasets" in page and f"**Last change:** {LIC['updated']}" in page
    for rel in ("datasets/index.mdx", "about/faq.mdx", "getting-started/quickstart.mdx", "contribute/submit-dataset.mdx",
                "datasets/virig-4imus-3cams.mdx", "datasets/virig-4imus-3cams-aruco.mdx", "datasets/virig-4imus-4cams.mdx",
                "datasets/virig-5imus-4cams.mdx"):
        text = (docs / rel).read_text(encoding="utf-8")
        assert "/about/license/#datasets" in text and "BY-NC 4.0" not in text, rel
    assert "about/license/#datasets" in (SITE / "public/llms.txt").read_text(encoding="utf-8")
    assert "BY-NC 4.0" not in (docs / "about/changelog.mdx").read_text(encoding="utf-8")   # no earlier licences (user, 2026-11-26)


def test_hub_community_card_source_agrees():
    mira = os.environ.get("MVIS_MIRA")
    if not mira:
        pytest.skip("MVIS_MIRA not set")
    card = (Path(mira) / "tasks/mvis/huggingface/community-card.md").read_text(encoding="utf-8")
    assert "license: cc-by-4.0" in card
    folders = {r.get("device") for r in HOSTED if r["repo"] == "calibench-vi/community"}
    for f in folders:
        row = next(line for line in card.splitlines() if f"[`{f}/`]" in line)
        assert "CC BY 4.0" in row and "BY-NC 4.0" not in row, f
