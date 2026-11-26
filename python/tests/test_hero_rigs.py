"""The homepage carousel's rigs.json: the recordings and their order (the user's order, 2026-11-15; ALG AVS115D-Y added 2026-11-16), and that
every rig carries the readouts and credit the hero shows. The media files per rig are checked in
site/scripts/home-hero.test.mjs; their frame counts and sizes in check_hero_media."""
import json
import re

from mvis_site import SITE

RIGS = json.loads((SITE / "public/media/hero/rigs.json").read_text(encoding="utf-8"))["rigs"]
HOMEPAGE_ORDER = ["virig4", "virig3", "looper", "dibuli", "cyperstereo", "alg_rs2", "gilabs", "mic"]
READOUTS = ("sensors", "window", "rms", "td", "corners", "xlabel", "xval", "caption", "chip")
PX = re.compile(r"^\d+\.\d\d <small>px</small>$")


def test_the_carousel_plays_these_recordings_in_this_order():
    assert [r["key"] for r in RIGS] == HOMEPAGE_ORDER


def test_removed_recordings_stay_out_of_the_cycle():
    assert not {"uzhs", "uzhd", "tumvi", "mgc", "moc"} & {r["key"] for r in RIGS}


def test_every_rig_has_its_readouts_timing_tiles_and_credit():
    for r in RIGS:
        for k in READOUTS:
            assert r.get(k) not in (None, ""), (r["key"], k)
        assert r["duration"] == 15.0 and r["live_cycle"] == 5.0, r["key"]        # one shared clock
        assert len(r["tiles"]) >= 1 and all(len(t) == 6 for t in r["tiles"]), r["key"]
        c = r["credit"]
        assert c.get("holder") and c.get("dataset") and (c.get("licence") or c.get("terms")), r["key"]


def test_each_credit_names_its_licence_and_links_its_row_on_the_license_page():
    """The credit sits with the clip, so it names the licence; the link goes to the recording's row on About → License
    (user, 2026-11-26), not to creativecommons.org. test_licences_in_step checks that the rows exist."""
    for r in RIGS:
        c = r["credit"]
        assert c["licence"] == "CC BY 4.0" and re.fullmatch(r"/about/license/#[a-z0-9-]+", c["licence_url"]), r["key"]


def test_reprojection_median_is_a_px_value_or_a_dash():
    for r in RIGS:
        assert PX.match(r["rms"]) or r["rms"] == "—", (r["key"], r["rms"])
    # the published solves' medians (2026-11-16 re-render; Valve Index now MIC04)
    assert {r["key"]: r["rms"].split()[0] for r in RIGS} == {
        "virig4": "0.25", "virig3": "0.25", "looper": "0.17", "dibuli": "0.18", "cyperstereo": "0.14",
        "alg_rs2": "0.15", "gilabs": "0.13", "mic": "0.19"}
