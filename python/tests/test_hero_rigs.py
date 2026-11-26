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


def test_each_credit_carries_the_licence_of_where_its_recording_is_hosted():
    """Recordings in calibench-vi/datasets are CC BY 4.0 since 2026-11-25. GiLabs data is CC BY 4.0 too (user, 2026-11-25), which
    covers the EGO1GS clip although its take is not in the hosted GiLabs folders. A re-rendered rigs.json with an old credit fails here."""
    by, nc = ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"), ("CC BY-NC 4.0", "https://creativecommons.org/licenses/by-nc/4.0/")
    want = {"virig4": by, "virig3": by, "looper": by, "mic": by, "alg_rs2": nc, "gilabs": by, "cyperstereo": by, "dibuli": by}
    got = {r["key"]: (r["credit"].get("licence"), r["credit"].get("licence_url")) for r in RIGS}
    assert {k: got[k] for k in want} == want
    assert not {k for k, v in got.items() if v == (None, None)}   # dibuli is CC BY 4.0 since 2026-11-26 (user)
    for r in RIGS:
        if "calibench-vi/datasets/" in r["credit"].get("url", ""):
            assert got[r["key"]] == by, r["key"]


def test_reprojection_median_is_a_px_value_or_a_dash():
    for r in RIGS:
        assert PX.match(r["rms"]) or r["rms"] == "—", (r["key"], r["rms"])
    # the published solves' medians (2026-11-16 re-render; Valve Index now MIC04)
    assert {r["key"]: r["rms"].split()[0] for r in RIGS} == {
        "virig4": "0.25", "virig3": "0.25", "looper": "0.17", "dibuli": "0.18", "cyperstereo": "0.14",
        "alg_rs2": "0.15", "gilabs": "0.13", "mic": "0.19"}
