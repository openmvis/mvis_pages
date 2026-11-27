import json
from pathlib import Path

import pytest
import yaml

import make_fixtures as F
from mvis_site import DATA, REPO
from mvis_site import results_eval as R
from mvis_site import leaderboard as L
from mvis_site import space as S

SHA = "0123456789abcdef0123456789abcdef01234567"
SITE = REPO / "site/src/data"
PAIRS = [["mk", "mvis", "kalibr", "MVIS", "− Kalibr"], ["bk", "basalt", "kalibr", "Basalt", "− Kalibr"],
         ["bm", "basalt", "mvis", "Basalt", "− MVIS"]]
DECS = {"fx": 2, "td_ms": 3, "Dw": 5, "dist": 5, "reproj_median": 3, "Tg": 3}
SID = {"cam0 – A": "cam0", "base IMU – B": "imu0"}
NONE = {"value": None, "marked": False, "unequal_n": False, "reason": None}


# ---------------------------------------------------------------- synthetic inputs
def cell(med, sd=0.1, n=4, state="ok", reason="no data"):
    return {"med": med, "sd": sd, "n": n, "state": state, "reason": reason}


def row(sensor, key, label=None, unit="", **cells):
    r = {"sensor": sensor, "key": key, "label": label or key, "unit": unit,
         **{c: cells.get(c) for c in ("mvis", "calyx", "kalibr", "basalt")}}
    r["deltas"] = {p[0]: NONE for p in PAIRS}
    return r


def with_delta(r, pair, value, marked, unequal_n=False):
    r["deltas"][pair] = {"value": value, "marked": marked, "unequal_n": unequal_n, "reason": None}
    return r


def stats_row(sensor, key, **values):
    return {"sensor": sensor, "key": key, **values}


def camimu_family():
    rows = [
        row("cam0 – A", "fx", unit="px", mvis=cell(450.0, 1.0), calyx=cell(450.1, 1.0), kalibr=cell(449.0, 2.0, state="fixed")),
        with_delta(row("cam0 – A", "td_ms", "time offset td", "ms", mvis=cell(-4.0, 0.1), calyx=cell(-4.1, 0.1),
                       kalibr=cell(-5.0, 0.2)), "mk", 1.0, True),
        row("cam0 – A", "t_ga_ms", "gyro–accel delay", "ms", mvis=cell(1.25, 0.3), calyx=cell(1.2, 0.3), kalibr=cell(None, None, 0, "missing", "not in model")),
        row("cam0 – A", "reproj_median", unit="px", mvis=cell(0.25, 0.01), kalibr=cell(0.3, 0.02)),
        with_delta(row("base IMU – B", "Dw[0,0]", "gyro scale x", mvis=cell(1.001, 0.001), kalibr=cell(1.0, 0.002)), "mk", 0.001, False, True),
        row("base IMU – B", "Dw[1,0]", "gyro cross", mvis=cell(0.002, 0.001), kalibr=cell(0.0, 0.001, state="shown")),
        row("base IMU – B", "Tg[0,1]", mvis=cell(0.01, 0.002), kalibr=cell(-0.02, 0.003)),
        row("base IMU – B", "Tg[1,1]", kalibr=cell(0.5, 0.1, state="missing")),
    ]
    stats = {"rows": [stats_row("cam0 – A", "fx", calyx={"r1": 449.0, "r2": 450.0, "r3": 450.2, "r4": 451.0},
                                mvis_all={"r1": 449.1, "r2": 450.0, "r3": 450.1, "r4": 451.2},
                                kalibr={"r1": 447.0, "r2": 449.0, "r3": 449.5, "r4": 452.0}),
                      stats_row("cam0 – A", "td_ms", calyx={"a": -4.2, "b": -4.0, "c": -4.1, "d": float("nan"), "e": -4.15},
                                mvis_all={"a": -4.1, "b": -3.9, "c": -4.0, "d": float("nan"), "e": -4.05}, kalibr={"a": -5.2, "b": -4.9, "c": -5.0, "d": -5.1})]}
    return {"rows": rows, "read_first": "Read this.", "notes": [["Note", "A note."]]}, stats


def records(ran=("MVIS", "Kalibr"), n=4, kalibr_model_n=None):
    """MVIS holds its two record methods: the default model ("MVIS") and Kalibr's IMU model."""
    methods = lambda t: {m: {"ran": True, "n_recordings": k} for m, k in
                         ([(t, n), (R.METHOD["mvis"], n if kalibr_model_n is None else kalibr_model_n)] if t == "MVIS" else [(t, n)])}
    return {"families": {"families": {"T1": {"mode": "camera+imu", "title": "Cam + IMU", "n_recordings": n}}},
            "tools": {t: ({"T1": {"methods": methods(t)}} if t in ran else {}) for t in ("MVIS", "Kalibr", "Basalt")}}


def fam(**kw):
    sp, st = camimu_family()
    args = dict(T="T1", meta={"mode": "camera+imu", "title": "Cam + IMU", "n_recordings": 4}, shutter="global", sp=sp,
                pairs=PAIRS, decs=DECS, records=records(), stats_fam=st, sid=SID, hub=R.hub_links("T1", "b1", SHA))
    args.update(kw)
    return R.family(**args)


# ---------------------------------------------------------------- helpers
@pytest.mark.parametrize("key, cls", [("fx", "intr"), ("cy", "intr"), ("dist[2]", "dist"), ("baseline_mm", "length"),
                                      ("lever_mm", "length"), ("td_ms", "time"), ("tr_ms", "time"), ("t_ga_ms", "time"),
                                      ("Dw[1,1]", "scale"), ("Da[2,2]", "scale"), ("Dw[2,0]", "cross"), ("Tg[0,0]", None),
                                      ("reproj_median", None)])
def test_param_class(key, cls):
    assert R.param_class(key) == cls


def test_formatting_follows_the_space():
    assert R.fmt(-0.0001, 3) == "0.000" and R.fmt(-1.5, 2) == "−1.50" and R.fmt(1.25, 2, sign=True) == "+1.25"
    assert R.decimals(DECS, "dist[0]", [0.1]) == 5 and R.decimals(DECS, "dist[0]", [12.0]) == 3 and R.decimals(DECS, "q") == 4
    assert R.is_camimu("camera+imu") and not R.is_camimu("camera") and not R.is_camimu("camera only")
    assert [c for c, _ in R.columns(False)] == ["mvis", "kalibr", "basalt"]
    # one MVIS column, always labelled "MVIS": the Kalibr-IMU-model run, or the default-model run where there is no such run
    assert R.columns(True) == [("mvis", "MVIS"), ("kalibr", "Kalibr"), ("basalt", "Basalt")]
    assert R.columns(True, kalibr_model=False)[0] == ("calyx", "MVIS") and R.columns(False, kalibr_model=False)[0] == ("mvis", "MVIS")
    assert R.shown_method("mvis", True) == "MVIS (Kalibr IMU model)" and R.shown_method("calyx", True) == "MVIS"
    assert R.shown_method("mvis", False) == "MVIS" and R.shown_method("kalibr", True) == "Kalibr"
    # the Leaderboard keeps the long label
    assert R.pair_label(PAIRS[2], True) == "Basalt − MVIS (K-IMU)" and R.pair_label(PAIRS[0], False) == "MVIS − Kalibr"


def test_minmax_reads_only_min_and_max_and_checks_the_count():
    sr = stats_row("cam0 – A", "fx", kalibr={"a": 2.0, "b": float("nan"), "c": 1.0, "d": "x"})
    assert R.minmax(sr, "kalibr", 2) == {"min": 1.0, "max": 2.0}
    assert R.minmax(None, "kalibr", 2) is None and R.minmax(sr, "kalibr", 0) is None
    with pytest.raises(ValueError, match="1 values in the stats file, record n 2"):
        R.minmax(stats_row("s", "k", basalt={"a": 1.0}), "basalt", 2)


def test_lanes_by_state():
    assert R.lane("basalt", "Basalt", None, None, 2) == {"col": "basalt", "tool": "Basalt", "label": "Basalt", "state": "missing", "note": "no value"}
    gone = R.lane("kalibr", "Kalibr", cell(None, None, 0, "missing", "not in model"), None, 2)
    assert gone["state"] == "missing" and gone["note"] == "not in this tool's model"
    odd = R.lane("kalibr", "Kalibr", cell(None, None, 0, "missing", "a new reason"), None, 2)
    assert odd["note"] == "a new reason"
    shown = R.lane("kalibr", "Kalibr", cell(3.0, state="shown"), stats_row("s", "k", kalibr={"a": 1.0}), 2)
    assert shown["note"] == "different model, not compared" and "min" not in shown and shown["text"] == "3.00"
    fixed = R.lane("kalibr", "Kalibr", cell(2.0, n=2, state="fixed"), stats_row("s", "k", kalibr={"a": 1.0, "b": 3.0}), 2)
    assert fixed["note"] == "input" and (fixed["min"], fixed["max"]) == (1.0, 3.0)


def test_axis_is_centred_on_the_cross_tool_median_of_drawn_lanes():
    lanes = [{"state": "ok", "med": 1.0, "sd": 0.1}, {"state": "ok", "med": 2.0, "sd": 0.1, "min": 0.5, "max": 2.2},
             {"state": "fixed", "med": 3.0, "sd": None}, {"state": "shown", "med": 99.0, "sd": 1.0}]
    assert R.axis(lanes) == {"c": 2.0, "h": pytest.approx(1.65)}
    assert R.axis([{"state": "ok", "med": 5.0, "sd": 0.0}]) == {"c": 5.0, "h": 5e-06}
    assert R.axis([{"state": "missing"}]) is None



def test_axis_centre_tool_holds_the_centre_against_another_tools_poor_solves():
    lanes = [{"tool": "MVIS", "state": "ok", "med": 1.0, "sd": 0.1},
             {"tool": "Kalibr", "state": "ok", "med": 9.0, "sd": 0.1, "min": 1.0, "max": 30.0},
             {"tool": "Basalt", "state": "ok", "med": 1.2, "sd": 0.1}]
    assert R.axis(lanes, "MVIS") == {"c": 1.0, "h": pytest.approx(31.9), "by": "MVIS median"}
    assert R.axis(lanes)["c"] == 1.2 and "by" not in R.axis(lanes)
    assert R.axis(lanes[1:], "MVIS") == R.axis(lanes[1:])  # no MVIS lane drawn: the cross-tool median
    poor = [lanes[0], dict(lanes[1], poor="Poor."), lanes[2]]  # a poor lane is drawn on the others' scale
    assert R.axis(poor, "MVIS") == {"c": 1.0, "h": pytest.approx(0.33), "by": "MVIS median"}
    assert R.axis(poor, "MVIS", ref=0.5) == {"c": 0.5, "h": pytest.approx(0.88), "by": "reference"}
    assert R.axis([dict(lanes[1], poor="Poor.")])["c"] == 9.0  # every lane poor: they set the axis after all


def test_a_lane_with_poor_solves_keeps_its_values_and_carries_the_reason():
    x = R.lane("kalibr", "Kalibr", {"state": "ok", "med": 2.0, "sd": 0.5, "n": 4}, None, 2, poor=True)
    assert (x["state"], x["text"], x["n"], x["poor"]) == ("ok", "2.00", 4, True)
    assert "poor" not in R.lane("kalibr", "Kalibr", {"state": "ok", "med": 2.0, "sd": 0.5, "n": 4}, None, 2)


# ---------------------------------------------------------------- one family
def test_a_camimu_family_page():
    f = fam()
    assert [(c["col"], c["label"]) for c in f["columns"]] == [("mvis", "MVIS"), ("kalibr", "Kalibr")]  # one MVIS lane; Basalt did not run
    assert f["imu_model"] == "kalibr" and "K-IMU" not in json.dumps(f)
    assert f["solved"][2] == {"n": 0, "of": 4, "reason": "not run on this family", "tool": "Basalt"}
    assert f["read_first"] == "Read this." and f["notes"] == [["Note", "A note."]] and f["has_tga"]
    assert f["records"]["Kalibr"].endswith(f"/blob/{SHA}/Kalibr/b1/T1.json")
    assert f["fit"] == [{"sensor": "A", "by_col": {"mvis": "0.250", "kalibr": "0.300"}}]
    cam, imu = f["sensors"]
    assert [p["key"] for p in cam["params"]] == ["fx", "td_ms", "t_ga_ms"] and [p["key"] for p in imu["params"]] == ["Dw[0,0]", "Dw[1,0]"]
    fx = cam["params"][0]
    assert [(x["col"], x.get("min"), x.get("max")) for x in fx["lanes"]] == [("mvis", 449.1, 451.2), ("kalibr", 447.0, 452.0)]
    assert fx["axis"]["c"] == 449.5
    td = cam["params"][1]["lanes"][0]
    assert (td["min"], td["max"], td["n"]) == (-4.1, -3.9, 4)  # the NaN recording is not a value
    assert [x["state"] for x in imu["params"][1]["lanes"]] == ["ok", "shown"]


def test_the_shown_mvis_run_solved_what_coverage_prints():
    """Coverage prints the larger count of the two MVIS runs; the export stops when the shown run solved fewer."""
    assert next(s for s in fam()["solved"] if s["tool"] == "MVIS")["n"] == 4
    with pytest.raises(ValueError, match=r"T1: Coverage prints MVIS 4 of 4, but the shown run \(MVIS \(Kalibr IMU model\)\) solved 3"):
        fam(records=records(kalibr_model_n=3))


def test_differences_keep_record_order_and_count_like_the_board():
    f = fam()
    (mk,) = f["diffs"]
    assert mk["label"] == "MVIS − Kalibr" and (mk["marked"], mk["compared"]) == (1, 2) and f["tally"] == {"mk": [1, 2]}
    assert [r["key"] for r in mk["rows"]] == ["td_ms", "Dw[0,0]"]
    td, dw = mk["rows"]
    assert (td["text"], td["spread"], td["z"], td["marked"], td["sensor_id"]) == ("+1.000", "0.200", 5.0, True, "cam0")
    assert dw["unequal_n"] and not dw["marked"]


def test_a_zero_spread_has_no_gauge_position():
    sp, st = camimu_family()
    sp["rows"] = [with_delta(row("cam0 – A", "td_ms", mvis=cell(1.0, 0.0), kalibr=cell(0.0, 0.0)), "mk", 1.0, False)]
    assert fam(sp=sp, stats_fam={"rows": []})["diffs"][0]["rows"][0]["z"] is None


def test_kalibr_model_terms_are_tiles_never_lanes():
    f = fam()
    assert [(t["col"], sorted(t["cells"])) for t in f["model_terms"]] == [("mvis", ["01"]), ("kalibr", ["01"])]
    assert f["model_terms"][1]["cells"]["01"]["text"] == "−0.020"
    assert not any(p["key"].startswith("Tg") for s in f["sensors"] for p in s["params"])


def test_an_unmapped_sensor_stops_the_export():
    with pytest.raises(ValueError, match="sensors without an id"):
        fam(sid={"cam0 – A": "cam0"})


def test_a_camera_only_family_has_one_mvis_column_and_no_hub_links_without_a_commit():
    f = fam(meta={"mode": "camera", "title": "Cam", "n_recordings": 4}, hub=R.hub_links("T1", "b1", None))
    assert [c["label"] for c in f["columns"]] == ["MVIS", "Kalibr"] and f["records"] == {} and f["mode"] == "cam"
    assert "imu_model" not in f
    assert f["diffs"][0]["label"] == "MVIS − Kalibr"


# ---------------------------------------------------------------- the board's ◆ tallies
def _board(T, cells_by_table, calyx=""):
    tables = "".join(
        '<details class="sn"><summary>s</summary><table><thead><tr><th class="p" scope="col">Parameter</th>'
        + "".join(f'<th class="d" scope="col">{h}<small>{t}</small></th>' for h, t in heads)
        + "</tr></thead><tbody>" + "".join(f'<tr data-k="m|s|k">{"".join(f"<td class={chr(34)}{c}{chr(34)}>{x}</td>" for c, x in tr)}</tr>' for tr in trs)
        + "</tbody></table></details>" for heads, trs in cells_by_table)
    return f'<details class="fam"><summary><h3>{T} · title</h3></summary>{tables}{calyx}</details>'


def test_board_tallies_count_marked_and_compared_cells_per_pair():
    html = _board("T6", [([("MVIS", "− Kalibr"), ("Basalt", "− MVIS")],
                          [[("v", "1"), ("d fl", '<span class="mk">◆</span> +1.2'), ("d", "+0.1")],
                           [("v", "1"), ("d na", "≠ model"), ("d", "")],
                           [("v", "1"), ("d", "−0.3 <small>≠n</small>"), ("d fl", "◆ +3")]])],
                  calyx='<details class="sn calyx"><table><thead><tr><th class="d" scope="col">default</th></tr></thead><tbody><tr data-k="c|s|k"><td class="d fl">◆ 1</td></tr></tbody></table></details>')
    assert R.board_tallies(html, PAIRS) == {"T6": {"mk": [1, 2], "bm": [1, 2]}}
    fams = [{"id": "T6", "tally": {"mk": [1, 2], "bm": [1, 2]}}, {"id": "T7", "tally": {"mk": [0, 1]}}]
    assert R.tally_problems(fams, R.board_tallies(html, PAIRS)) == ["T7: ◆ {'mk': [0, 1]} here, board None"]


def test_committed_diamond_counts_equal_the_committed_board():
    """The golden test: every family's ◆ marked / compared per pair on the Leaderboard equals the rendered board."""
    board = json.loads((SITE / "leaderboard/board.json").read_text())
    uzh = json.loads((SITE / "leaderboard/uzh_fpv.json").read_text())
    want = {**{k: R.board_tallies(v, PAIRS) for k, v in board["datasets"].items()}, "uzh_fpv": R.board_tallies(uzh["fragment"], PAIRS)}
    seen = 0
    for p in json.loads((SITE / "results-nav.json").read_text()):
        page = json.loads((SITE / f"eval/{p['slug']}.json").read_text())
        if page["id"] not in want:  # a study with no board (VI-Rig 5 IMUs, MVIS only) has nothing to count
            assert page["study"] and all(f["tally"] == {} and f["diffs"] == [] for f in page["families"]), page["id"]
            continue
        for f in page["families"]:
            assert f["tally"] == want[page["id"]][f["id"]], (page["id"], f["id"])
            seen += 1
    assert seen == 15
    lb = json.loads((SITE / "eval/index.json").read_text())
    got = {f["id"]: {k: [d["marked"], d["compared"]] for k, d in f["diffs"].items()} for ds in lb["datasets"] for f in ds["families"]}
    assert got["T6"] == {"mk": [21, 48]} and got["T6c"] == {"mk": [5, 24], "bk": [2, 16], "bm": [6, 16]}
    assert got == {T: v for d in want.values() for T, v in d.items() if T in got}


def test_committed_solved_counts_equal_the_records_behind_repeatability():
    rep = json.loads((SITE / "leaderboard/repeatability.json").read_text())
    want = {f["id"]: {t: r["n"] for t, r in f["recordings"].items()} for d in rep["datasets"] for f in d["families"]}
    lb = json.loads((SITE / "eval/index.json").read_text())
    got = {f["id"]: {s["tool"]: s["n"] for s in f["solved"]} for d in lb["datasets"] for f in d["families"]}
    assert got == want


# ---------------------------------------------------------------- legacy hashes
def test_legacy_hashes_follow_the_old_page_ids():
    rep_ds = {"groups": ["focal_pp", "gyro"], "families": [
        {"id": "T1", "cells": {"focal_pp": {"state": "most", "caveats": ["x", "y"]}, "gyro": {"state": "na"}}},
        {"id": "T2", "cells": {"focal_pp": {"state": "tie", "caveats": ["y"]}, "gyro": {"state": "input", "caveats": ["z"]}}}]}
    assert R.caveat_letters(rep_ds) == ["a", "b", "c"]
    assert R.legacy(rep_ds, "ds") == ["ds-ds", "rp-cav-ds-a", "rp-cav-ds-b", "rp-cav-ds-c", "rp-T1-focal_pp", "rp-T2-focal_pp", "rp-T2-gyro"]
    assert R.legacy(None, "uzh") == []


# ---------------------------------------------------------------- pages, lint, write
def _pub():
    return yaml.safe_load((DATA / "public_results.yaml").read_text(encoding="utf-8"))


def _page(entry=None, **kw):
    sp, st = camimu_family()
    entry = entry or {"slug": "x-rig", "id": "x", "label": "X rig", "title": "X: a rig", "ours": True, "licence": "CC BY 4.0",
                      "intro": "A rig.", "chips": ["2 cameras"], "links": {"dataset": "/reference/datasets/x/"},
                      "families": [{"id": "T1", "shutter": "global"}], "sensors": SID}
    rec = records()
    return R.dataset(entry, {"pairs": PAIRS, "decimals": DECS, "families": {"T1": sp}}, rec, {"families": {"T1": st}},
                     "b1", kw.get("commit", SHA), kw.get("rep_ds"))


def test_a_dataset_page_and_its_mdx():
    p = _page(rep_ds={"groups": [], "families": []})
    assert p["link"] == "/benchmark/results/x-rig/" and p["has_repeatability"] and not p["study"] and p["legacy"] == ["ds-x"]
    text = R.mdx(p)
    assert "## T1 · camera + IMU" in text and "### Coverage" in text and "### Parameters by sensor" in text
    for gone in ("Repeatability", "Where the tools differ", "Model notes", "Full tables", "Reading these results"):
        assert f"## {gone}" not in text and f"### {gone}" not in text
    assert "RepeatabilityMatrix" not in R.mdx(dict(_page(), reading=["<b>x</b>"]))


def test_a_twin_block_gets_its_own_section_after_the_notes():
    twin = dict(title="Does the motion calibrate the IMU?", paras=["p"], bullets=["b"],
                table=dict(caption="c", head=["h"], rows=[["r"]]))
    text = R.mdx(dict(_page(), reading=["<b>x</b>"], twin=twin))
    assert text.index("## Notes") < text.index("## Does the motion calibrate the IMU?") < text.index("## T1 ·")
    assert "<E.Twin page={page} />" in text and "<E.Twin" not in R.mdx(_page())


def test_the_public_text_holds_every_dataset_in_page_order_ours_first():
    pub = _pub()
    ds = pub["datasets"]
    assert [d["slug"] for d in ds] == ["virig-4imus-3cams", "virig-4imus-4cams", "virig-5imus-4cams", "tum-vi", "looper-insight9",
                                       "monado-mic", "monado-mgc", "monado-moc", "uzh-fpv"]
    assert [d["ours"] for d in ds[:3]] == [True, True, True] and not any(d["ours"] for d in ds[3:])
    assert [d["slug"] for d in ds if d.get("study")] == ["virig-5imus-4cams", "monado-mic", "monado-moc", "uzh-fpv"]
    assert all(d["study_note"] for d in ds if d.get("study"))
    assert R.problems({"public_results.yaml": (DATA / "public_results.yaml").read_text(encoding="utf-8")}, SHA) == []
    for d in ds:
        assert "image" not in d or (REPO / "site/public" / d["image"]["src"].lstrip("/")).exists(), d["slug"]


def test_leaderboard_and_nav_keep_the_yaml_order():
    pub = _pub()
    a, b = _page(), dict(_page(), slug="y-rig", id="y", label="Y rig", link="/benchmark/results/y-rig/", study=True)
    lb = R.leaderboard([a, b], pub, "b1", SHA)
    assert [d["slug"] for d in lb["datasets"]] == ["x-rig"] and lb["studies"] == [{"label": "Y rig", "link": "/benchmark/results/y-rig/", "batch": "b1", "note": ""}]
    assert lb["datasets"][0]["families"][0]["diffs"] == {"mk": {"label": "MVIS (K-IMU) − Kalibr", "marked": 1, "compared": 2}}
    assert [n["slug"] for n in R.nav([a, b])] == ["x-rig", "y-rig"]
    committed = json.loads((SITE / "results-nav.json").read_text())
    assert [n["slug"] for n in committed] == [d["slug"] for d in pub["datasets"]]


def test_render_refuses_counts_that_differ_from_the_board():
    p = _page()
    board_ok = _board("T1", [([("MVIS", "− Kalibr")], [[("d fl", "◆ +1")], [("d", "+0.1")]])])
    files = R.render([p], _pub(), "b1", SHA, {"x": board_ok}, PAIRS)
    assert sorted(files) == ["site/src/content/docs/benchmark/results/x-rig.mdx", "site/src/data/eval/index.json",
                             "site/src/data/eval/x-rig.json", "site/src/data/results-nav.json"]
    with pytest.raises(ValueError, match=r"T1: ◆ \{'mk': \[1, 2\]\} here, board \{'mk': \[0, 1\]\}"):
        R.render([p], _pub(), "b1", SHA, {"x": _board("T1", [([("MVIS", "− Kalibr")], [[("d", "+1")]])])}, PAIRS)


@pytest.mark.parametrize("text, why", [("A tool scores higher", "rating"), ("from /home/someone", "internal path"),
                                       ('{"v": [1.5, 2.5, 3.5]}', "per-recording array"), ('{"values": {}}', "private key"),
                                       ('{"t": "rec_007 ran"}', "private name"), ('{"t": "roll"}', "RPY")])
def test_problems_refuse_what_may_not_be_public(text, why):
    name = "x.json" if text.startswith("{") else "x.mdx"
    assert any(why in p for p in R.problems({name: text}, SHA, ("rec_007",)))


def test_our_own_results_paths_and_the_commit_pass_the_lint():
    text = json.dumps({"link": "/benchmark/results/tum-vi/", "u": f"https://huggingface.co/datasets/calibench-vi/results/tree/{SHA}", "c": SHA})
    assert R.problems({"x.json": text}, SHA) == []
    assert R.problems({"x.mdx": "import p from '../data/results/x.json'"}, SHA)  # any other results/ path is still refused


def test_committed_outputs_pass_the_lint():
    files = {p.name: p.read_text(encoding="utf-8") for p in [*(SITE / "eval").glob("*.json"), SITE / "results-nav.json",
                                                             *(REPO / R.MDX_DIR).glob("*.mdx")]}
    assert len(files) == 20 and R.problems(files, json.loads((SITE / "eval/index.json").read_text())["results_commit"]) == []


def test_write_writes_all_or_nothing_and_drops_stale_pages(tmp_path):
    (tmp_path / R.MDX_DIR).mkdir(parents=True)
    (tmp_path / R.MDX_DIR / "old.mdx").write_text("x")
    with pytest.raises(SystemExit, match="refusing to write"):
        R.write({"a.json": '{"t": "best"}', "b.json": "{}"}, tmp_path, SHA)
    assert not (tmp_path / "b.json").exists() and (tmp_path / R.MDX_DIR / "old.mdx").exists()
    out = R.write({f"{R.MDX_DIR}/new.mdx": "ok", "d/b.json": "{}"}, tmp_path, SHA)
    assert sorted(p.name for p in out) == ["b.json", "new.mdx"]
    assert not (tmp_path / R.MDX_DIR / "old.mdx").exists() and (tmp_path / "d/b.json").read_text() == "{}"


# ---------------------------------------------------------------- the Space adapter
def _rows_records(lb):
    r = lb / "records"
    (r / "rows.json").write_text(json.dumps({"T1": [
        {"sensor": "cam0 – A", "key": "fx", "label": "fx", "unit": "px", "mvis": {"med": 2.0, "sd": 0.5, "n": 3},
         "kalibr": {"med": 1.0, "sd": 0.2, "n": 4}, "basalt": None, "calyx": None}]}))
    return r


def test_space_rows_use_the_spaces_own_delta_and_states(tmp_path):
    lb = F.write_leaderboard(tmp_path / "lb")
    out = S.space_rows(lb, _rows_records(lb), SHA)
    assert out["pairs"][0][0] == "mk" and out["decimals"]["fx"] == 2 and set(out["families"]) == {"T1", "T2"}
    (r,) = out["families"]["T1"]["rows"]
    assert r["mvis"]["state"] == "ok" and r["mvis"]["reason"] == "not in one run" and r["basalt"] is None
    assert r["deltas"]["mk"] == {"value": 1.0, "marked": True, "unequal_n": True, "reason": None} and r["deltas"]["bk"]["value"] is None
    assert out["families"]["T2"]["rows"] == []
    with pytest.raises(ValueError, match="full 40-hex sha"):
        S.space_rows(lb, lb / "records", "abc1234")


def test_uzh_rows_write_records_and_use_the_uzh_read_first(tmp_path):
    lb = F.write_leaderboard(tmp_path / "lb")
    root = F.write_uzh(tmp_path / "uzh")
    stats = json.loads((root / "three_way/three_way_comparison_stats.json").read_text())
    out = S.uzh_rows(lb, L.without_repeated_weights_note(L.rekey(stats)), tmp_path / "rec")
    assert json.loads((tmp_path / "rec/families.json").read_text())["batch"] == "2026-11-26"
    assert set(out["families"]) == {"DAVIS", "SNAP"}
    assert out["families"]["DAVIS"]["read_first"].startswith("All three tools use each bag's IMU weights")
    assert out["families"]["DAVIS"]["notes"][0][0] == "Like for like"


def test_a_camera_without_fit_values_has_no_fit_row():
    r = row("cam0 – A", "reproj_median", mvis=cell(None, None, 0, "missing"))
    assert R.fit_rows([r, row("cam0 – A", "fx")], R.columns(False), DECS) == []


def test_write_keeps_an_mdx_page_it_rewrites(tmp_path):
    (tmp_path / R.MDX_DIR).mkdir(parents=True)
    (tmp_path / R.MDX_DIR / "keep.mdx").write_text("old")
    R.write({f"{R.MDX_DIR}/keep.mdx": "new"}, tmp_path, SHA)
    assert (tmp_path / R.MDX_DIR / "keep.mdx").read_text() == "new"


@pytest.mark.real_data
def test_the_real_export_reproduces_the_committed_files():
    """collect + render on the batch's private inputs give the committed files byte for byte.
    MVIS_LEADERBOARD=<Space folder> MVIS_RESULTS_RECORDS=<records snapshot> MVIS_RESULTS_STATS=<its stats file>
    MVIS_UZH_ROOT=<uzh study dir>. The separate studies are given no stats file, so their committed pages are carried
    forward (three warnings) and must come back unchanged."""
    from conftest import env_path
    lb = json.loads((SITE / "eval/index.json").read_text())
    with pytest.warns(UserWarning, match="NOT RE-EXPORTED"):
        pages, pub, pairs, boards, private = R.collect(env_path("MVIS_LEADERBOARD"), env_path("MVIS_RESULTS_RECORDS"),
                                                       env_path("MVIS_RESULTS_STATS"), lb["batch"], lb["results_commit"],
                                                       env_path("MVIS_UZH_ROOT"), REPO)
    files = R.render(pages, pub, lb["batch"], lb["results_commit"], boards, pairs)
    assert R.problems(files, lb["results_commit"], private) == []
    for path, text in files.items():
        assert (REPO / path).read_text(encoding="utf-8") == text, path


def test_a_row_whose_models_differ_draws_only_mvis():
    r = row("cam0 – A", "fx", mvis=cell(1.0), kalibr=cell(2.0), basalt=cell(3.0, state="fixed"))
    r["deltas"]["mk"] = dict(NONE, reason="model")
    (s,) = R.sensors([r], R.columns(False), {}, DECS, SID)
    assert [x["state"] for x in s["params"][0]["lanes"]] == ["ok", "other_model", "other_model"]
    assert s["params"][0]["axis"]["c"] == 1.0 and s["params"][0]["lanes"][1]["note"] == "different model, not compared"


# ---------------------------------------------------------------- a second separate study (MVIS only)
def _mvis_only_page():
    """A study where only MVIS ran, with its default IMU model alone (no Kalibr-model run): no Kalibr, no mvis values."""
    sp, st = camimu_family()
    for r in sp["rows"]:
        r["mvis"] = r["kalibr"] = None
        r["deltas"] = {q[0]: NONE for q in PAIRS}   # nothing to compare: the Space gives no difference
    entry = {"slug": "v-rig", "id": "v", "label": "V rig", "title": "V: a rig", "ours": True, "licence": "CC BY-NC 4.0",
             "intro": "A rig.", "chips": [], "links": {}, "families": [{"id": "T1", "shutter": "global"}], "sensors": SID,
             "study": True, "study_note": "MVIS only.", "not_run": "not run on this set"}
    return R.dataset(entry, {"pairs": PAIRS, "decimals": DECS, "families": {"T1": sp}}, records(ran=("MVIS",)),
                     {"families": {"T1": st}}, "b9", None, None)


def test_an_mvis_only_study_has_one_column_no_differences_and_no_full_tables():
    p = _mvis_only_page()
    f = p["families"][0]
    assert [(c["col"], c["label"]) for c in f["columns"]] == [("calyx", "MVIS")]  # the fallback: the default-model run
    assert f["imu_model"] == "default"
    assert f["diffs"] == [] and f["tally"] == {}
    assert [s.get("reason") for s in f["solved"]] == [None, "not run on this set", "not run on this set"]
    assert p["full_tables"] is None and p["study_note"] == "MVIS only."
    text = R.mdx(p)
    assert "### Parameters by sensor" in text and "Where the tools differ" not in text and "Full tables" not in text


def test_render_takes_a_study_without_a_board_only_when_it_has_nothing_to_count():
    p = _mvis_only_page()
    files = R.render([p], _pub(), "b1", SHA, {}, PAIRS)
    assert "site/src/data/eval/v-rig.json" in files
    assert json.loads(files[f"{R.OUT_DIR}/index.json"])["studies"] == [{"label": "V rig", "link": "/benchmark/results/v-rig/",
                                                                      "batch": "b9", "note": "MVIS only."}]
    with pytest.raises(ValueError, match="no rendered board"):
        R.render([_page()], _pub(), "b1", SHA, {}, PAIRS)          # a leaderboard dataset always needs its board


def test_study_rows_write_the_study_board_with_its_own_texts(tmp_path):
    lb = F.write_leaderboard(tmp_path / "lb")
    stats = L.rekey(json.loads((F.write_uzh(tmp_path / "uzh") / "three_way/three_way_comparison_stats.json").read_text()))
    stats = dict(stats, families={k.replace("DAVIS", "V5").replace("SNAP", "V5c"): dict(f, dataset="v5")
                                  for k, f in stats["families"].items()})
    out = S.study_rows(lb, stats, tmp_path / "rec", "b9", ("v5id", "v5", "V5 rig"), "MVIS only.", "One config.")
    fams = json.loads((tmp_path / "rec/families.json").read_text())
    assert fams["batch"] == "b9" and fams["datasets"] == [{"id": "v5id", "title": "V5 rig", "families": ["V5", "V5c"]}]
    assert set(out["families"]) == {"V5", "V5c"} and out["families"]["V5"]["read_first"] == "MVIS only."
    assert ["Like for like", "One config."] in out["families"]["V5"]["notes"]
    out = S.study_rows(lb, stats, tmp_path / "rec2", "b9", ("v5id", "v5", "V5 rig"),
                       {"V5": "Camera + IMU.", "V5c": "Cameras only."}, {"V5": "One config.", "V5c": "Two configs."})
    assert out["families"]["V5"]["read_first"] == "Camera + IMU." and out["families"]["V5c"]["read_first"] == "Cameras only."
    assert ["Like for like", "Two configs."] in out["families"]["V5c"]["notes"]


def test_read_first_drops_the_notes_reference():
    assert R._no_notes_ref("Kalibr is GS. Data settings differ: see Notes.") == "Kalibr is GS. Data settings differ between the tools."


def test_methodology_explains_every_label_a_results_page_prints():
    text = (REPO / "site/src/content/docs/benchmark/methodology.mdx").read_text(encoding="utf-8")
    for word in {*R.STATE_WORD.values(), *R.MISSING_WORD.values()}:
        assert f"| `{word}` |" in text, word


def test_the_mdx_title_says_results_and_names_only_the_tools_that_ran():
    p = _page()
    text = R.mdx(p)
    assert 'title: "X: a rig results"' in text and "content: \"X: a rig results: MVIS and Kalibr | OpenMVIS\"" in text
    only = dict(p, families=[dict(f, columns=[c for c in f["columns"] if c["tool"] == "MVIS"]) for f in p["families"]])
    text = R.mdx(only)
    assert "description: \"MVIS over every recording of X rig: what it solved," in text and "MVIS only | OpenMVIS" in text


def test_reading_notes_reach_the_page_only_when_there_are_some():
    assert "<E.Reading" not in R.mdx(_page())
    assert "## Notes\n" in R.mdx(dict(_page(), reading=["<b>x</b>"])) and "<E.Reading page={page} />" in R.mdx(dict(_page(), reading=["x"]))


def test_a_page_centred_on_mvis_with_a_poor_tool_and_its_sidebar_group():
    entry = {"slug": "x-rig", "id": "x", "label": "X rig", "title": "X: a rig", "ours": False, "licence": "CC BY 4.0",
             "intro": "A rig.", "chips": ["2 cameras"], "links": {}, "families": [{"id": "T1", "shutter": "global"}], "sensors": SID,
             "axis_centre": "MVIS", "poor": {"T1": {"Kalibr": {"n": 1, "text": "Poor on 1 of 4."}}}, "nav_group": "G", "nav_label": "X"}
    p = _page(entry)
    lanes = [x for s in p["families"][0]["sensors"] for q in s["params"] for x in q["lanes"]]
    assert {x["tool"] for x in lanes if x.get("poor")} == {"Kalibr"}  # greyed lanes; the reason once, on the family
    assert p["families"][0]["poor"] == [{"tool": "Kalibr", "n": 1, "text": "Poor on 1 of 4."}]
    k = next(s for s in p["families"][0]["solved"] if s["tool"] == "Kalibr")
    assert k["poor"] == 1 and all("poor" not in s for s in p["families"][0]["solved"] if s["tool"] != "Kalibr")
    assert all(q["axis"].get("by") == "MVIS median" for s in p["families"][0]["sensors"] for q in s["params"]
               if any(x["tool"] == "MVIS" and x["state"] in R.ON_AXIS for x in q["lanes"]))
    assert R.nav([p], {"datasets": [entry]}) == [{"label": "X rig", "link": "/benchmark/results/x-rig/", "slug": "x-rig",
                                                  "legacy": [], "group": "G", "nav_label": "X"}]
    for wrong in ({"poor": {"T9": {"Kalibr": {"n": 1, "text": "x"}}}}, {"poor": {"T1": {"Kalibr": "no count"}}},
                  {"reference": {"values": {"cam9 – nowhere": {"fx": 1.0}}}}):
        with pytest.raises(ValueError):
            _page(dict(entry, **wrong))


def test_studies_alone_replace_their_own_entries_and_keep_every_other():
    y = dict(_page(), slug="y-rig", id="y", label="Y rig", link="/benchmark/results/y-rig/", study=True, batch="b2")
    pub = {"datasets": [{"slug": "x-rig"}, {"slug": "y-rig", "study": True, "nav_group": "G"}, {"slug": "z-rig", "study": True}]}
    old_nav = [{"label": "X rig", "link": "/benchmark/results/x-rig/", "slug": "x-rig", "legacy": ["ds-x"]},
               {"label": "Z rig", "link": "/benchmark/results/z-rig/", "slug": "z-rig", "legacy": []}]
    z = {"label": "Z rig", "link": "/benchmark/results/z-rig/", "batch": "b0", "note": "z"}
    files = R.render_studies([y], pub, old_nav, {"batch": "b1", "datasets": ["kept"], "studies": [z]})
    nav = json.loads(files[R.NAV_FILE])
    assert [(n["slug"], n.get("group"), n["legacy"]) for n in nav] == [("x-rig", None, ["ds-x"]), ("y-rig", "G", []), ("z-rig", None, [])]
    board = json.loads(files[f"{R.OUT_DIR}/index.json"])
    assert board["datasets"] == ["kept"] and [s["link"] for s in board["studies"]] == ["/benchmark/results/y-rig/", "/benchmark/results/z-rig/"]
    assert set(files) == {R.NAV_FILE, f"{R.OUT_DIR}/index.json", f"{R.OUT_DIR}/y-rig.json", f"{R.MDX_DIR}/y-rig.mdx"}


def test_a_reference_value_centres_its_chart_and_other_charts_keep_the_mvis_median():
    entry = {"slug": "x-rig", "id": "x", "label": "X rig", "title": "X: a rig", "ours": False, "licence": "CC BY 4.0",
             "intro": "A rig.", "chips": ["2 cameras"], "links": {}, "families": [{"id": "T1", "shutter": "global"}], "sensors": SID,
             "axis_centre": "MVIS"}
    plain = _page(entry)
    s0 = plain["families"][0]["sensors"][0]
    sensor = next(k for k, v in SID.items() if v == s0["id"])
    key = s0["params"][0]["key"]
    p = _page(dict(entry, reference={"source": "x", "values": {sensor: {key: 123.0}}}))
    q = p["families"][0]["sensors"][0]["params"]
    assert (q[0]["axis"]["c"], q[0]["axis"]["by"]) == (123.0, "reference")
    assert all(x["axis"].get("by") != "reference" for x in q[1:])


# ---------------------------------------------------------------- one MVIS lane on a carried page
ENTRY = {"slug": "x-rig", "id": "x", "label": "X rig", "title": "X: a rig", "ours": False, "licence": "CC BY 4.0", "intro": "A rig.",
         "chips": [], "links": {}, "families": [{"id": "T1", "shutter": "global"}], "sensors": SID, "axis_centre": "MVIS",
         "reference": {"source": "x", "values": {"cam0 – A": {"td_ms": -4.5}}}}


def _two_lane(page):
    """The page as it was exported before: a default-model lane "MVIS" beside the Kalibr-model lane "MVIS (K-IMU)"."""
    old = json.loads(json.dumps(page))
    for f in old["families"]:
        both = lambda xs: [y for x in xs for y in ((dict(x, col="calyx"), dict(x, label="MVIS (K-IMU)")) if x["col"] == "mvis" else (x,))]
        f["columns"], f["model_terms"] = both(f["columns"]), both(f["model_terms"])
        for s in f["sensors"]:
            for q in s["params"]:
                q["lanes"] = [dict(x, med=x["med"] + 50, text="far") if x["col"] == "calyx" and "med" in x else x for x in both(q["lanes"])]
                q["axis"] = R.axis(q["lanes"])
        for r in f["fit"]:
            r["by_col"] = {"calyx": "9.999", **r["by_col"]}
        for d in f["diffs"]:
            d["label"] = d["label"].replace("MVIS", "MVIS (K-IMU)")
        del f["imu_model"]
    return old


def test_one_lane_turns_a_committed_two_lane_page_into_what_the_export_writes():
    page = _page(ENTRY)
    old = _two_lane(page)
    assert "K-IMU" in json.dumps(old) and old != page
    assert R.one_lane(old, ENTRY) == page and R.one_lane(page, ENTRY) == page   # and it changes nothing the second time
    assert json.dumps(R.one_lane(old, ENTRY)) == json.dumps(page)               # key order too: the files are compared as text


def test_one_lane_leaves_camera_only_families_and_flags_a_default_model_family():
    cam = R.dataset(dict(ENTRY, reference=None), {"pairs": PAIRS, "decimals": DECS, "families": {"T1": camimu_family()[0]}},
                    dict(records(), families={"families": {"T1": {"mode": "camera", "title": "Cam", "n_recordings": 4}}}),
                    {"families": {"T1": camimu_family()[1]}}, "b1", SHA, None)
    assert R.one_lane(cam, ENTRY)["families"][0] is cam["families"][0]
    v = _mvis_only_page()
    bare = dict(v, families=[{k: x for k, x in f.items() if k != "imu_model"} for f in v["families"]])
    assert R.one_lane(bare, {"sensors": SID}) == v
    gone = dict(v, families=[dict(f, sensors=[dict(s, params=[dict(q, lanes=[dict(x, state="missing") for x in q["lanes"]]) for q in s["params"]])
                                              for s in f["sensors"]], fit=[]) for f in v["families"]])
    assert R.one_lane(gone, ENTRY)["families"][0]["sensors"] == []   # a chart with no drawn lane is not kept, as in sensors()


def test_every_committed_page_has_one_mvis_lane():
    pub = {e["slug"]: e for e in _pub()["datasets"]}
    for p in sorted((SITE / "eval").glob("*.json")):
        if p.name == "index.json":
            continue
        page = json.loads(p.read_text())
        assert "K-IMU" not in p.read_text() and R.one_lane(page, pub[page["slug"]]) == page, p.name
        for f in page["families"]:
            assert [c["label"] for c in f["columns"] if c["tool"] == "MVIS"] == ["MVIS"], (p.name, f["id"])
            assert f.get("imu_model") == (None if f["mode"] == "cam" else "default" if f["id"] == "V5" else "kalibr"), (p.name, f["id"])


def test_a_study_without_stats_is_carried_forward_with_a_warning(tmp_path):
    page = _page(ENTRY)
    (tmp_path / R.OUT_DIR).mkdir(parents=True)
    (tmp_path / R.OUT_DIR / "x-rig.json").write_text(json.dumps(_two_lane(page)))
    other = {"x-rig": ENTRY, "y-rig": dict(ENTRY, slug="y-rig"), "z-rig": dict(ENTRY, slug="z-rig")}
    with pytest.warns(UserWarning, match="NOT RE-EXPORTED: x-rig") as seen:
        pages, found = R.carried(other, {"z-rig": "stats.json", "q-rig": "stats.json"}, tmp_path)
    assert len(seen) == 1 and pages == {"x-rig": page}
    assert len(found) == 2 and "q-rig, which public_results.yaml does not list" in found[0] and "y-rig: no --study stats file and no committed" in found[1]


# ---------------------------------------------------------------- separate studies alone
def _study_setup(tmp_path, monkeypatch):
    lb = F.write_leaderboard(tmp_path / "lb")
    stats = L.rekey(json.loads((F.write_uzh(tmp_path / "uzh") / "three_way/three_way_comparison_stats.json").read_text()))
    # the fake Space writes families.json alone (no tool records, no rows), so the pages hold the plumbing, not numbers
    stats = dict(stats, families={k.replace("DAVIS", "V5").replace("SNAP", "V5c"): dict(f, dataset="v5", rows=[], mode="camera+imu", n_recordings=2)
                                  for k, f in stats["families"].items()})
    (tmp_path / "stats.json").write_text(json.dumps(stats))
    study = {"slug": "v-rig", "id": "v5id", "stats_key": "v5", "label": "V5 rig", "title": "V5: a rig", "ours": True, "licence": "CC BY 4.0",
             "intro": "A rig.", "chips": [], "links": {}, "study": True, "study_note": "A study.", "batch": "b9", "read_first": "Read.",
             "like_for_like": "One config.", "families": [{"id": "V5", "shutter": "global"}, {"id": "V5c", "shutter": "global"}],
             "sensors": {}, "not_run": "not run on this set"}
    (tmp_path / "data").mkdir()
    (tmp_path / "data/public_results.yaml").write_text(yaml.safe_dump({"datasets": [{"slug": "a-rig"}, study, {"slug": "uzh-fpv", "study": True}]}))
    monkeypatch.setattr("mvis_site.DATA", tmp_path / "data")
    return lb, tmp_path / "stats.json"


def test_collect_studies_builds_the_named_studies_alone(tmp_path, monkeypatch):
    lb, stats = _study_setup(tmp_path, monkeypatch)
    pages, pub, private = R.collect_studies(lb, {"v-rig": stats})
    (p,) = pages
    assert (p["slug"], p["batch"], p["study"], p["results_commit"]) == ("v-rig", "b9", True, None)
    assert [f["id"] for f in p["families"]] == ["V5", "V5c"] and all(f["diffs"] == [] and f["tally"] == {} for f in p["families"])
    assert p["families"][0]["read_first"] == "Read." and p["families"][0]["notes"] == [["Like for like", "One config."]]
    assert [(s["n"], s["of"], s["reason"]) for s in p["families"][0]["solved"]] == [(0, 2, "not run on this set")] * 3
    assert [d["slug"] for d in pub["datasets"]] == ["a-rig", "v-rig", "uzh-fpv"]
    assert isinstance(private, tuple)
    shown = [dict(p, families=[dict(f, columns=[{"col": "calyx", "tool": "MVIS", "label": "MVIS"}]) for f in p["families"]])]
    files = R.render_studies(shown, pub, [], {"studies": []})
    assert "Generated by site/scripts/export_study.py from" in files[f"{R.MDX_DIR}/v-rig.mdx"]
    assert R.problems(files, SHA, private) == []


def test_collect_studies_stops_on_a_slug_that_is_not_a_separate_study(tmp_path, monkeypatch):
    lb, stats = _study_setup(tmp_path, monkeypatch)
    for slug in ("a-rig", "uzh-fpv", "nowhere"):
        with pytest.raises(SystemExit, match=f"{slug}: not a separate study"):
            R.collect_studies(lb, {slug: stats})


def test_the_mdx_header_names_the_script_that_wrote_the_page():
    assert "Generated by site/scripts/export_results.py from" in R.mdx(_page())
    assert "Generated by site/scripts/export_study.py from" in R.mdx(_page(), "export_study.py")
    assert "Edit those, not this file. */}\n" in R.mdx(_page())
