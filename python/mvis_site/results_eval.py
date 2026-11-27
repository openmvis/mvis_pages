"""The Results pages: the Leaderboard (one row per family) and one Dataset eval page per dataset. Pure: dicts in, texts
out; site/scripts/export_results.py reads the inputs and writes what `render` returns, or nothing.

Inputs
  pub     python/data/public_results.yaml: every word that is not computed, the page order and the sensor ids
  space   space.space_rows / space.uzh_rows: the Space's merged rows, cell states and ◆ differences (app.delta), so the
          site counts ◆ with the board's own code
  records repeatability.load_records of the same snapshot: solved n of N per tool
  stats   the private stats file of the batch: only min and max per (row, tool) leave it, as named keys
  rep     repeatability.json: the cells are read there by the page; here only for the legacy hashes
  boards  {dataset id: rendered board HTML} (board.json, uzh_fpv.json): the ◆ tallies must equal the board's

A leaderboard page may also hold study families (public_results.yaml `extra`): separate runs fed by a --study stats
file, appended after the batch families and kept off the Leaderboard (extra_families).

No total, rank or score is computed. Rows keep record order (sensor, then parameter), never a value order.
Rotation rows are not shown (none in the records; they wait for a user OK).
"""
from __future__ import annotations

import html
import json
import re
import statistics

from .lint import public_problems, refusals, strip_urls
from .repeatability import check_public, finite, recordings

RESULTS = "/benchmark/results/"
HUB_RESULTS = "https://huggingface.co/datasets/calibench-vi/results"
OUT_DIR = "site/src/data/eval"
NAV_FILE = "site/src/data/results-nav.json"
MDX_DIR = "site/src/content/docs/benchmark/results"

# Space column -> the tool it stands for (shape and colour mark identity only) and the record method behind it.
TOOL_OF = {"calyx": "MVIS", "mvis": "MVIS", "kalibr": "Kalibr", "basalt": "Basalt"}
METHOD = {"calyx": "MVIS", "mvis": "MVIS (Kalibr IMU model)", "kalibr": "Kalibr", "basalt": "Basalt"}
# The per-recording dict of the stats row behind each column (repeatability.BLOCK_DICT, the gate checks the pairing).
STATS_DICT = {"calyx": "calyx", "mvis": "mvis_all", "kalibr": "kalibr", "basalt": "basalt"}
KIMU = "MVIS (K-IMU)"
TOOLS = ("MVIS", "Kalibr", "Basalt")

CLASSES = (("intr", "Focal length + principal point"), ("dist", "Distortion"), ("length", "Baseline and lever"),
           ("time", "Time"), ("scale", "IMU scale"), ("cross", "IMU cross-axis"))
STATE_WORD = {"fixed": "input", "shown": "different model, not compared",
              "shown_no_value": "different model, no value", "other_model": "different model, not compared"}
# The Space's missing_reason words, as a lane says them.
MISSING_WORD = {"no data": "no value", "no run": "not run", "not in model": "not in this tool's model",
                "not in one run": "not in one run", "not reported": "not reported"}
ON_AXIS = ("ok", "fixed")  # a value of another model would stretch the axis; it is printed, not drawn


# ---------------------------------------------------------------- small helpers
def base(key: str) -> str:
    return key.split("[")[0]


def param_class(key: str) -> str | None:
    """The chart class of a parameter key; None for rows that are not charted (fit, Kalibr model terms)."""
    b = base(key)
    if b in ("fx", "fy", "cx", "cy"):
        return "intr"
    if b == "dist":
        return "dist"
    if b in ("baseline_mm", "lever_mm"):
        return "length"
    if b in ("td_ms", "tr_ms", "t_ga_ms"):
        return "time"
    if b in ("Dw", "Da"):
        i, j = re.findall(r"\d+", key)
        return "scale" if i == j else "cross"
    return None


def fmt(v: float, dec: int, sign: bool = False) -> str:
    s = "%.*f" % (dec, v)
    if float(s) == 0:
        s = s.lstrip("-")
    if sign and float(s) > 0:
        s = "+" + s
    return s.replace("-", "−")


def decimals(decs: dict, key: str, values=()) -> int:
    """The Space's precision per row (app.DECIMALS, and _row_dec's 3 decimals for large distortion coefficients)."""
    if base(key) == "dist" and any(abs(v) >= 10 for v in values):
        return 3
    return decs.get(base(key), 4)


def sig(x: float, n: int = 6) -> float:
    return float(f"{x:.{n}g}")


def is_camimu(mode: str) -> bool:
    return mode not in ("camera", "camera only")


def columns(camimu: bool, kalibr_model: bool = True) -> list[tuple[str, str]]:
    """(Space column, label) of a family: one MVIS column, always labelled "MVIS". On a camera + IMU family it is the
    run with Kalibr's IMU model (Space column `mvis`), so its IMU terms mean the same as Kalibr's; kalibr_model False
    (the family has no such run) gives the default-model run (`calyx`) instead. family() says which as `imu_model`."""
    return [("calyx" if camimu and not kalibr_model else "mvis", "MVIS"), ("kalibr", "Kalibr"), ("basalt", "Basalt")]


def shown_method(col: str, camimu: bool) -> str:
    """The record method behind a column on a Dataset eval page (a camera-only family has the one method "MVIS")."""
    return METHOD[col] if camimu or TOOL_OF[col] != "MVIS" else "MVIS"


def board_name(tool: str, camimu: bool) -> str:
    """A tool as the Leaderboard names it: there the Kalibr-IMU-model run keeps its long label."""
    return KIMU if camimu and tool == "MVIS" else tool


def pair_label(pair: list, camimu: bool) -> str:
    """The Leaderboard's label of a tool pair. The Dataset eval pages say "MVIS" (diffs())."""
    return f"{board_name(TOOL_OF[pair[1]], camimu)} − {board_name(TOOL_OF[pair[2]], camimu)}"


def short(sensor: str) -> str:
    return sensor.split(" – ")[-1]


# ---------------------------------------------------------------- min / max from the private stats file
def minmax(stats_row: dict | None, col: str, n: int) -> dict | None:
    """{min, max} of the per-recording values behind one record cell, or None. Only these two named numbers leave the
    stats file. The count must be the record's n, else the stats row is not the record's and the export stops."""
    if not stats_row or not n:
        return None
    v = list(finite(stats_row.get(STATS_DICT[col])).values())
    if len(v) != n:
        raise ValueError(f"{stats_row['sensor']} {stats_row['key']} {col}: {len(v)} values in the stats file, record n {n}")
    return {"min": sig(min(v)), "max": sig(max(v))}


# ---------------------------------------------------------------- one family
def lane(col: str, label: str, cell: dict | None, stats_row: dict | None, dec: int, other_model: bool = False,
         poor: bool = False) -> dict:
    """One tool's lane of a parameter chart. other_model: the Space says the tools' models differ on this row (its
    delta reason "model"), so a non-MVIS value is printed, not drawn, as repeatability.MODEL_DIFFERS treats it.
    poor: this tool has poor solves in this family (public_results.yaml `poor`): the lane is greyed and keeps its
    values; the reason is printed once, under the family's read-first line."""
    out = {"col": col, "tool": TOOL_OF[col], "label": label}
    if poor:
        out["poor"] = True
    if not cell:
        return dict(out, state="missing", note="no value")
    if cell["state"] in ("missing", "shown_no_value"):
        return dict(out, state="missing", note=STATE_WORD.get(cell["state"]) or MISSING_WORD.get(cell["reason"], cell["reason"]))
    if other_model and TOOL_OF[col] != "MVIS" and cell["state"] in ON_AXIS:
        cell = dict(cell, state="other_model")
    out.update(state=cell["state"], med=cell["med"], sd=cell["sd"], n=cell["n"], text=fmt(cell["med"], dec))
    if cell["state"] != "ok":
        out["note"] = STATE_WORD[cell["state"]]
    if cell["state"] not in ON_AXIS:
        return out
    mm = minmax(stats_row, col, cell["n"])
    if mm:
        out.update(mm)
    return out


def axis(lanes: list[dict], centre: str | None = None, ref: float | None = None) -> dict | None:
    """Shared axis of one parameter: centred on the cross-tool median, half-width to the farthest whisker or box edge.
    centre: a tool (public_results.yaml `axis_centre`) whose first drawn lane gives the centre instead, so another
    tool's outliers do not move it; the cross-tool median when that tool has no drawn lane on this parameter.
    ref: the dataset's reference value of this parameter (public_results.yaml `reference`), which is the centre when
    given, before any tool.
    A lane with poor solves (lane `poor`) does not set the axis either, unless every drawn lane has them: it is drawn
    on the others' scale, and what falls outside is marked at the edge (Parameters.astro). `by` names the centre."""
    on = [x for x in lanes if x["state"] in ON_AXIS]
    if not on:
        return None
    on = [x for x in on if not x.get("poor")] or on
    own = [x for x in on if centre and x.get("tool") == centre]
    c = ref if ref is not None else own[0]["med"] if own else statistics.median(x["med"] for x in on)
    far = [abs(v - c) for x in on
           for v in (x["med"], x["med"] - (x["sd"] or 0), x["med"] + (x["sd"] or 0), x.get("min", x["med"]), x.get("max", x["med"]))]
    h = max(far) * 1.1 or max(abs(c) * 1e-6, 1e-9)
    out = {"c": sig(c), "h": sig(h)}
    if ref is not None:
        out["by"] = "reference"
    elif own:
        out["by"] = f"{centre} median"
    return out


def tg_tiles(rows: list[dict], cols: list[tuple[str, str]], sid: dict) -> list[dict]:
    """Kalibr IMU-model terms (Tg), one 3x3 tile per sensor and tool that has values; never on the Dw scale."""
    out = []
    sensors = list(dict.fromkeys(r["sensor"] for r in rows if base(r["key"]) == "Tg"))
    for s in sensors:
        for col, label in cols:
            cells = {}
            for r in rows:
                c = r.get(col)
                if r["sensor"] == s and base(r["key"]) == "Tg" and c and c["state"] == "ok":
                    i, j = re.findall(r"\d+", r["key"])
                    cells[f"{i}{j}"] = {"med": c["med"], "sd": c["sd"], "text": fmt(c["med"], 3)}
            if cells:
                out.append({"sensor": short(s), "sensor_id": sid[s], "col": col, "tool": TOOL_OF[col], "label": label,
                            "cells": cells})
    return out


def fit_rows(rows: list[dict], cols: list[tuple[str, str]], decs: dict) -> list[dict]:
    """Reprojection median per camera and tool: fit of each tool's own model, not accuracy; never in differences."""
    out = []
    for r in rows:
        if r["key"] != "reproj_median":
            continue
        vals = {col: fmt(r[col]["med"], decimals(decs, r["key"])) for col, _ in cols
                if r.get(col) and r[col]["state"] == "ok"}
        if vals:
            out.append({"sensor": short(r["sensor"]), "by_col": vals})
    return out


def diffs(rows: list[dict], pairs: list, decs: dict, sid: dict) -> list[dict]:
    """Per tool pair, every compared row in record order: Δ = a − b (the Space's app.delta) and Δ in units of the
    larger sd. A pair with nothing compared is left out."""
    out = []
    for p in pairs:
        items = []
        for r in rows:
            d = r["deltas"][p[0]]
            if d["value"] is None:
                continue
            a, b = r[p[1]], r[p[2]]
            spread = max(a["sd"] or 0.0, b["sd"] or 0.0)
            dec = decimals(decs, r["key"], [x["med"] for x in (a, b)])
            items.append({"sensor": short(r["sensor"]), "sensor_id": sid[r["sensor"]], "key": r["key"], "label": r["label"],
                          "unit": r["unit"], "text": fmt(d["value"], dec, sign=True), "spread": fmt(spread, dec),
                          "z": None if spread == 0 else round(d["value"] / spread, 3),
                          "marked": bool(d["marked"]), "unequal_n": bool(d["unequal_n"])})
        if items:
            out.append({"pair": p[0], "label": f"{TOOL_OF[p[1]]} − {TOOL_OF[p[2]]}", "a": TOOL_OF[p[1]], "b": TOOL_OF[p[2]],
                        "marked": sum(x["marked"] for x in items), "compared": len(items), "rows": items})
    return out


def sensors(rows: list[dict], cols: list[tuple[str, str]], stats_rows: dict, decs: dict, sid: dict,
            centre: str | None = None, poor: dict | None = None, ref: dict | None = None) -> list[dict]:
    """Charted parameters by sensor, in record order: one lane per tool column. centre: axis() centre tool; poor:
    {tool: {"n", "text"}} of this family (public_results.yaml `poor`)."""
    out = {}
    for r in rows:
        cls = param_class(r["key"])
        if cls is None:
            continue
        srow = stats_rows.get((r["sensor"], r["key"]))
        vals = [r[c]["med"] for c, _ in cols if r.get(c) and r[c]["med"] is not None]
        dec = decimals(decs, r["key"], vals)
        other = any(d.get("reason") == "model" for d in r["deltas"].values())
        lanes = [lane(c, label, r.get(c), srow, dec, other, TOOL_OF[c] in (poor or {})) for c, label in cols]
        if not any(x["state"] in ON_AXIS for x in lanes):
            continue
        s = out.setdefault(sid[r["sensor"]], {"id": sid[r["sensor"]], "label": short(r["sensor"]), "params": []})
        s["params"].append({"key": r["key"], "label": r["label"], "unit": r["unit"], "cls": cls,
                            "axis": axis(lanes, centre, ((ref or {}).get(r["sensor"]) or {}).get(r["key"])), "lanes": lanes})
    return list(out.values())


def solved(records: dict, T: str, of: int) -> list[dict]:
    """Solved n of N per tool, from the records' n_recordings (repeatability.recordings); a reason where a tool did not run."""
    rec = recordings(records, T, of)
    return [dict(rec[t], tool=t) for t in TOOLS]


def family(T: str, meta: dict, shutter: str, sp: dict, pairs: list, decs: dict, records: dict, stats_fam: dict,
           sid: dict, hub: dict, centre: str | None = None, poor: dict | None = None, ref: dict | None = None) -> dict:
    camimu = is_camimu(meta["mode"])
    of = meta.get("n_recordings") or 0
    done = solved(records, T, of)
    for s in done:  # poor solves still count as run, but Coverage shows them apart from the good ones
        if (poor or {}).get(s["tool"]):
            s["poor"] = poor[s["tool"]]["n"]
            if s["poor"] > s["n"]:
                raise ValueError(f"{T}: poor says {s['poor']} {s['tool']} solves, but only {s['n']} of {of} solved")
    ran = {x["tool"] for x in done if "reason" not in x}
    rows = sp["rows"]
    has = lambda c: any((r.get(c) or {}).get("med") is not None for r in rows)
    # a tool that did not run gets no lanes; a family without the Kalibr-IMU-model run shows the default-model run
    cols = [(c, l) for c, l in columns(camimu, has("mvis")) if TOOL_OF[c] in ran and has(c)]
    shown = next((c for c, _ in cols if TOOL_OF[c] == "MVIS"), None)
    if shown:  # Coverage prints the larger count of the two MVIS runs; it must be the count of the run that is shown
        n = (((records["tools"]["MVIS"].get(T) or {}).get("methods") or {}).get(shown_method(shown, camimu)) or {}).get("n_recordings")
        printed = next(x["n"] for x in done if x["tool"] == "MVIS")
        if n != printed:
            raise ValueError(f"{T}: Coverage prints MVIS {printed} of {of}, but the shown run "
                             f"({shown_method(shown, camimu)}) solved {n}")
    unmapped = sorted({r["sensor"] for r in rows} - set(sid))
    if unmapped:
        raise ValueError(f"{T}: sensors without an id in public_results.yaml: {unmapped}")
    stats_rows = {(r["sensor"], r["key"]): r for r in stats_fam["rows"]}
    ds = diffs(rows, pairs, decs, sid)
    out = {"id": T, "title": meta.get("title") or T, "mode": "cam+imu" if camimu else "cam", "shutter": shutter,
            "n": of, "columns": [{"col": c, "tool": TOOL_OF[c], "label": l} for c, l in cols],
            "solved": done, "read_first": _no_notes_ref(sp["read_first"]),
            "poor": [{"tool": t, "n": v["n"], "text": v["text"]} for t, v in (poor or {}).items()],
            "notes": sp["notes"], "records": hub, "fit": fit_rows(rows, cols, decs),
            "diffs": ds, "tally": {d["pair"]: [d["marked"], d["compared"]] for d in ds},
            "sensors": sensors(rows, cols, stats_rows, decs, sid, centre, poor, ref), "model_terms": tg_tiles(rows, cols, sid),
            "has_tga": any(base(r["key"]) == "t_ga_ms" for r in rows)}
    if camimu and shown:  # which IMU model the one MVIS lane is: Kalibr's, or MVIS's default where no such run exists
        out["imu_model"] = "kalibr" if shown == "mvis" else "default"
    return out


def hub_links(T: str, batch: str, commit: str | None) -> dict:
    """The public record files behind a family's numbers, at the results commit."""
    if not commit:
        return {}
    return {t: f"{HUB_RESULTS}/blob/{commit}/{t}/{batch}/{T}.json" for t in TOOLS}


# ---------------------------------------------------------------- ◆ tallies of a rendered board
_TH_D = re.compile(r'<th class="d" scope="col">(.*?)</th>', re.S)
_TD = re.compile(r'<td class="([^"]*)">(.*?)</td>', re.S)


def _text(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def board_tallies(board_html: str, pairs: list) -> dict:
    """{family: {pair: [marked, compared]}} read off the rendered board (main tables only, not the MVIS-default fold):
    a ◆ cell is marked, a cell with a number is compared."""
    head = {(p[3] + p[4]).replace(" ", ""): p[0] for p in pairs}
    out = {}
    for fam in re.split(r'<details class="fam"', board_html)[1:]:
        T = _text(re.search(r"<h3>(.*?)</h3>", fam).group(1)).split(" · ")[0]
        tally = out.setdefault(T, {})
        for sn in re.split(r'<details class="sn', fam)[1:]:
            if sn.startswith(' calyx"'):
                continue
            pids = [head[_text(h).replace(" ", "")] for h in _TH_D.findall(sn)]
            for tr in re.findall(r"<tr[^>]*data-k[^>]*>(.*?)</tr>", sn, re.S):
                dcells = [(c, t) for c, t in _TD.findall(tr) if c.split()[0] == "d"]
                for pid, (cls, txt) in zip(pids, dcells):
                    if "na" in cls.split() or not _text(txt):
                        continue
                    m, n = tally.get(pid, [0, 0])
                    tally[pid] = [m + ("fl" in cls.split()), n + 1]
    return out


def tally_problems(fams: list[dict], board: dict) -> list[str]:
    """Families whose ◆ counts differ from the rendered board's. The board wins."""
    return [f"{f['id']}: ◆ {f['tally']} here, board {board.get(f['id'])}" for f in fams if f["tally"] != board.get(f["id"], {})]


# ---------------------------------------------------------------- legacy hashes
def caveat_letters(rep_ds: dict) -> list[str]:
    """The caveat letters the old page used for a dataset (RepeatabilityMatrix: first use, a, b, c, ...)."""
    seen = []
    for f in rep_ds["families"]:
        for g in rep_ds["groups"]:
            for c in (f["cells"].get(g) or {}).get("caveats", []):
                if c not in seen:
                    seen.append(c)
    return list("abcdefghijklmnop"[:len(seen)])


def legacy(rep_ds: dict | None, ds_id: str) -> list[str]:
    """Old hashes of /benchmark/results/ that now live on this dataset's page. ds-<id> goes to the page's top; the
    caveat (rp-cav-*) and cell (rp-<family>-<group>) ids keep their names there, made by the same components."""
    if rep_ds is None:
        return []
    return [f"ds-{ds_id}", *(f"rp-cav-{ds_id}-{l}" for l in caveat_letters(rep_ds)),
            *(f"rp-{f['id']}-{g}" for f in rep_ds["families"] for g, c in f["cells"].items() if c["state"] != "na")]


# ---------------------------------------------------------------- pages
def _no_notes_ref(text: str) -> str:
    """The Space's read-first line points at a Notes section the dataset pages no longer show (2026-11-11)."""
    return text.replace("Data settings differ: see Notes.", "Data settings differ between the tools.")


FAMILY_TEXTS = ("poor", "gravity", "no_mvis")  # public_results.yaml texts keyed by family id


def outside(f: dict) -> bool:
    """A study family on a leaderboard page (public_results.yaml `extra`): not part of the leaderboard batch."""
    return bool((f.get("run") or {}).get("outside"))


def dress(f: dict, entry: dict, fe: dict, run: dict | None = None) -> dict:
    """The hand-written parts of one family, each only where public_results.yaml has it (a family without them is
    unchanged). fe: the family's own yaml entry.
    pair     the camera pair of the family, printed beside its title ("pair 02 · cam0 + cam2")
    gravity  entry `gravity` {family: text}: which tool ran at which gravity
    no_mvis  entry `no_mvis` {family: text}: why MVIS has no value on some charts of this family (it solved each
             camera alone, so there is no baseline). MVIS's empty lanes are taken off those charts and the text is
             printed once; the export stops when MVIS has a value on every chart, since the text would be wrong.
    run      {batch, mvis, outside[, mvis_url]}: the runs behind this family, on a page whose families are not one
             batch. mvis is a public name of the MVIS version (a release, or a commit as a link through mvis_url: the
             public lint refuses a bare commit hash, here as everywhere)"""
    if fe.get("pair"):
        f["pair"] = fe["pair"]
    if (entry.get("gravity") or {}).get(f["id"]):
        f["gravity"] = entry["gravity"][f["id"]]
    text = (entry.get("no_mvis") or {}).get(f["id"])
    if text:
        gone = 0
        for s in f["sensors"]:
            for q in s["params"]:
                keep = [x for x in q["lanes"] if not (x["tool"] == "MVIS" and x["state"] == "missing")]
                gone += len(q["lanes"]) - len(keep)
                q["lanes"] = keep
        if not gone:
            raise ValueError(f"{f['id']}: no_mvis is set, but MVIS has a value on every chart of this family")
        f["no_mvis"] = text
    if run:
        f["run"] = run
    return f


def dataset(entry: dict, sp: dict, records: dict, stats: dict, batch: str, commit: str | None, rep_ds: dict | None,
            extra: tuple | None = None) -> dict:
    """One Dataset eval page. extra: (sp, records, stats) of the page's study families (entry `extra`), which
    collect() builds from their --study stats file; they follow the batch families and stay off the Leaderboard."""
    sid = entry["sensors"]
    x = entry.get("extra")
    listed = [*entry["families"], *(x or {}).get("families", [])]
    ids = [f["id"] for f in listed]
    poor = entry.get("poor") or {}
    unknown = sorted({T for k in FAMILY_TEXTS for T in entry.get(k) or {}} - set(ids))
    bad = [(T, t) for T, by in poor.items() for t, v in by.items()
           if t not in TOOLS or not isinstance(v, dict) or not isinstance(v.get("n"), int) or not v.get("text")]
    bad += [("reference", s) for s in (entry.get("reference") or {}).get("values", {}) if s not in sid]
    if unknown or bad or (entry.get("axis_centre") or "MVIS") not in TOOLS or len(set(ids)) != len(ids):
        raise ValueError(f"{entry['slug']}: {', '.join(FAMILY_TEXTS)} name families {unknown} it does not list, malformed "
                         f"poor {bad} (tool: {{n, text}}), a family is listed twice, or axis_centre is not a tool")
    if x and (extra is None or entry.get("study") or not x.get("mvis") or not entry.get("mvis")):
        raise ValueError(f"{entry['slug']}: extra families need their stats file (--study {entry['slug']}=<file>), "
                         "extra.mvis and the page's mvis (the MVIS version of each), and a page that is not itself a study")

    def build(fe, sp, records, stats, hub, run):
        T = fe["id"]
        f = family(T, records["families"]["families"][T], fe["shutter"], sp["families"][T], sp["pairs"], sp["decimals"],
                   records, stats["families"][T], sid, hub, entry.get("axis_centre"), poor.get(T),
                   (entry.get("reference") or {}).get("values"))
        for s in f["solved"]:  # a study names why the other tools did not run (repeatability.NOT_RUN covers the board's families)
            if "reason" in s and entry.get("not_run"):
                s["reason"] = entry["not_run"]
        return dress(f, entry, fe, run)

    run = lambda src, batch, out: {"batch": batch, "mvis": src["mvis"], "outside": out,
                                   **({"mvis_url": src["mvis_url"]} if src.get("mvis_url") else {})}
    here = run(entry, batch, False) if x else None
    fams = [build(f, sp, records, stats, hub_links(f["id"], batch, commit), here) for f in entry["families"]]
    if entry.get("study") and entry["id"] != "uzh_fpv":
        for f in fams:  # no rendered board to count a separate study's ◆ against (UZH-FPV has its own), so none are kept
            f["diffs"], f["tally"] = [], {}
    for fe in (x or {}).get("families", []):  # study families: no public record files, and no ◆ counts, as a separate study
        f = build(fe, *extra, {}, run(x, x["batch"], True))
        f["diffs"], f["tally"] = [], {}
        fams.append(f)
    keep = ("slug", "id", "label", "title", "ours", "licence", "intro", "chips", "image", "links", "reading",
            "no_repeatability", "study_note", "twin")
    return {**{k: entry[k] for k in keep if k in entry}, "study": bool(entry.get("study")), "batch": batch,
            "results_commit": commit, "link": f"{RESULTS}{entry['slug']}/", "has_repeatability": rep_ds is not None,
            "legacy": legacy(rep_ds, entry["id"]), "families": fams,
            "full_tables": "study" if entry["id"] == "uzh_fpv" else None if entry.get("study") else "board"}


def leaderboard(pages: list[dict], pub: dict, batch: str, commit: str) -> dict:
    """The Leaderboard rows: every batch family of every dataset in page order; solved and ◆ tallies only. A page's
    study families (outside()) have no row. The repeatability cells are read from repeatability.json by the page itself."""
    rows = []
    for p in pages:
        if p["study"]:
            continue
        rows.append({"slug": p["slug"], "id": p["id"], "label": p["label"], "ours": p["ours"], "link": p["link"],
                     "families": [{"id": f["id"], "title": f["title"], "mode": f["mode"], "shutter": f["shutter"],
                                   "n": f["n"], "solved": f["solved"],
                                   "diffs": {d["pair"]: {"label": " − ".join(board_name(d[k], f["mode"] == "cam+imu") for k in "ab"),
                                                         "marked": d["marked"], "compared": d["compared"]}
                                             for d in f["diffs"]}} for f in p["families"] if not outside(f)]})
    study = [{"label": p["label"], "link": p["link"], "batch": p["batch"], "note": p.get("study_note", "")} for p in pages if p["study"]]
    return {"batch": batch, "results_commit": commit, "honest": pub["leaderboard"]["honest"], "datasets": rows,
            "studies": study}


def nav(pages: list[dict], pub: dict | None = None) -> list[dict]:
    """The Results sidebar in page order. An entry with `nav_group` in public_results.yaml joins the collapsed group
    of that name (astro.config.mjs), listed under its `nav_label`."""
    entry = {e["slug"]: e for e in (pub or {}).get("datasets", [])}
    out = []
    for p in pages:
        e = entry.get(p["slug"], {})
        n = {"label": p["label"], "link": p["link"], "slug": p["slug"], "legacy": p["legacy"]}
        if e.get("nav_group"):
            n.update(group=e["nav_group"], nav_label=e.get("nav_label") or p["label"])
        out.append(n)
    return out


def page_tools(page: dict) -> list[str]:
    """The tools with a column on this page, in TOOLS order (an MVIS-only study names MVIS alone)."""
    have = {c["tool"] for f in page["families"] for c in f["columns"]}
    return [t for t in TOOLS if t in have]


def and_list(words: list[str]) -> str:
    return words[0] if len(words) == 1 else f"{', '.join(words[:-1])} and {words[-1]}"


def mdx(page: dict, script: str = "export_results.py") -> str:
    """The thin page wrapper: headings in MDX so they reach the table of contents; every part from the page JSON.
    Coverage and parameters by sensor, plus a study's reading notes (python/data/public_results.yaml `reading`);
    repeatability, tool differences, model notes and full tables stay in the JSON and are left off the page for now.
    The title says "results", so it differs from the example page of the same dataset. script: the CLI that writes it.
    A family heading carries its camera pair where the yaml names one; a page with study families says, above the
    first family, which ones are outside the leaderboard batch."""
    s = page["slug"]
    tools = page_tools(page)
    who = "what each tool solved" if len(tools) > 1 else "what it solved"
    desc = (f"{and_list(tools)} over every recording of {page['label']}: {who}, and each "
            "parameter's spread per sensor. Repeatability, not accuracy.")
    title = f"{page['title']} results"
    head = f"{title}: {and_list(tools)}{'' if len(tools) > 1 else ' only'} | OpenMVIS"
    q = lambda t: json.dumps(t, ensure_ascii=False)
    parts = [f"---\ntitle: {q(title)}\ndescription: {q(desc)}\n"
             f"head:\n  - tag: title\n    content: {q(head)}\n"
             "pageType: reference\nwide: true\n---\n",
             f"{{/* Generated by site/scripts/{script} from python/data/public_results.yaml and the records. Edit those, not this file. */}}\n",
             "import * as E from '../../../../components/eval/index';",
             f"import page from '../../../../data/eval/{s}.json';\n",
             "<E.EvalHeader page={page} />\n",
             "<E.RpOpen />\n"]
    if page.get("reading"):
        parts += ["## Notes\n", "<E.Reading page={page} />\n"]
    if page.get("twin"):
        parts += [f"## {page['twin']['title']}\n", "<E.Twin page={page} />\n"]
    out = [f for f in page["families"] if outside(f)]
    if out:
        runs = and_list(sorted({f"{f['run']['batch']} (MVIS {f['run']['mvis']})" for f in out}))
        parts.append(f"**Outside the leaderboard batch:** {and_list([f['id'] for f in out])} {'are' if len(out) > 1 else 'is'} "
                     f"from separate runs, {runs}, added to this page beside the families of batch {page['batch']}. "
                     f"{'They have' if len(out) > 1 else 'It has'} no row on the Leaderboard and no ◆ counts.\n")
    for i, f in enumerate(page["families"]):
        pair = f" · {f['pair']}" if f.get("pair") else ""
        parts.append(f"## {f['id']} · {'camera + IMU' if f['mode'] == 'cam+imu' else 'camera only'}{pair}\n")
        parts.append(f"<E.FamilyHead page={{page}} i={{{i}}} />\n")
        parts.append("### Coverage\n")
        parts.append(f"<E.Coverage page={{page}} i={{{i}}} />\n")
        parts.append("### Parameters by sensor\n")
        parts.append(f"<E.Parameters page={{page}} i={{{i}}} />\n")
    return "\n".join(parts)


# ---------------------------------------------------------------- checks and the plan
def lint_text(text: str, commit: str | None) -> str:
    """What the public lint sees: links, our own /benchmark/results/ paths and the results commit taken out."""
    text = strip_urls(text)
    text = re.sub(r"/benchmark/results/[a-z0-9-]*/?", "/", text)
    return text.replace(commit, "") if commit else text


def problems(files: dict[str, str], commit: str, private: tuple[str, ...] = ()) -> list[str]:
    """Every output through the public lint and repeatability.check_public (no recording names or per-recording arrays)."""
    out = []
    for name, text in files.items():
        clean = lint_text(text, commit)
        found = check_public(clean, commit, private) if name.endswith(".json") else public_problems(clean)
        found += [f"refused: {w}" for w in refusals(text)]
        out += [f"{name}: {p}" for p in found]
    return out


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"


def render(pages: list[dict], pub: dict, batch: str, commit: str, boards: dict[str, str], pairs: list) -> dict[str, str]:
    """{path relative to the checkout: text}. Refuses (ValueError) when a ◆ tally differs from its rendered board."""
    bad = []
    for p in pages:
        if p["id"] in boards:
            bad += tally_problems([f for f in p["families"] if not outside(f)], board_tallies(boards[p["id"]], pairs))
        elif not p["study"] or any(f["tally"] for f in p["families"]):
            bad.append(f"{p['id']}: no rendered board to check its ◆ counts against")
    if bad:
        raise ValueError("◆ counts differ from the rendered board:\n  " + "\n  ".join(bad))
    files = {f"{OUT_DIR}/index.json": dumps(leaderboard(pages, pub, batch, commit)), NAV_FILE: dumps(nav(pages, pub))}
    for p in pages:
        files[f"{OUT_DIR}/{p['slug']}.json"] = dumps(p)
        files[f"{MDX_DIR}/{p['slug']}.mdx"] = mdx(p)
    return files


def check_studies(pub: dict, given, carry=()) -> tuple[dict, dict, list[str]]:
    """({slug: entry} of the separate studies other than UZH-FPV, {slug: entry} of the leaderboard pages with study
    families (`extra`), problems). Every one of them needs its --study stats file. A separate study may instead be
    named in `carry`, on purpose: its committed page is then kept as it is (carried()). A page with study families
    cannot be carried: its batch families are rebuilt, and the two halves must come from one export."""
    other = {e["slug"]: e for e in pub["datasets"] if e.get("study") and e["slug"] != "uzh-fpv"}
    extras = {e["slug"]: e for e in pub["datasets"] if e.get("extra")}
    given, carry = set(given), set(carry)
    found = [f"study stats given for {s}, which public_results.yaml lists neither as a separate study nor with extra families"
             for s in sorted(given - set(other) - set(extras))]
    found += [f"--carry {s}: only a separate study can be carried, and {s} is not one" for s in sorted(carry - set(other))]
    found += [f"{s}: both --study and --carry" for s in sorted(given & carry)]
    found += [f"{s}: no --study stats file. Pass --study {s}=<its stats file>"
              + (f", or --carry {s} to keep its committed page as it is" if s in other else " (its extra families)")
              for s in sorted((set(other) | set(extras)) - given - carry)]
    return other, extras, found


def carried(slugs, site) -> tuple[dict, list[str]]:
    """({slug: page}, problems) of the separate studies named with --carry: the committed page as it is, with a loud
    warning. Its numbers and its texts from public_results.yaml stay as last exported."""
    import warnings
    from pathlib import Path

    pages, found = {}, []
    for slug in sorted(slugs):
        p = Path(site) / OUT_DIR / f"{slug}.json"
        if not p.exists():
            found.append(f"--carry {slug}: no committed {OUT_DIR}/{slug}.json to carry forward")
            continue
        pages[slug] = json.loads(p.read_text(encoding="utf-8"))
        warnings.warn(f"NOT RE-EXPORTED: {slug} is carried (--carry). Its committed page is kept: the numbers and the "
                      "texts from public_results.yaml stay as last exported.", stacklevel=2)
    return pages, found


def study_inputs(leaderboard_dir, e: dict, st: dict) -> tuple[tuple, list[str]]:
    """((Space rows, records, stats), problems) of one --study stats file. e: the study's public_results.yaml entry, or
    a leaderboard page's `extra` block with the page's id and label (both name batch, stats_key, read_first and
    like_for_like)."""
    import tempfile
    from pathlib import Path

    from . import space
    from .repeatability import gate, load_records

    with tempfile.TemporaryDirectory(prefix="results_eval_") as tmp:
        rows = space.study_rows(leaderboard_dir, st, Path(tmp) / "rec", e["batch"], (e["id"], e["stats_key"], e["label"]),
                                e["read_first"], e["like_for_like"])
        recs = load_records(Path(tmp) / "rec", e["batch"])
    return (rows, recs, st), gate(st, recs, e["batch"])


# ---------------------------------------------------------------- reading and writing (the only steps with files)
def collect(leaderboard_dir, records_dir, stats_file, batch: str, commit: str, uzh_root, site,
            studies: dict | None = None, carry=()) -> tuple[list[dict], dict, list, dict, tuple]:
    """(pages, pub, pairs, boards, private words) from the inputs. Stops when the records, the stats file,
    repeatability.json and board.json are not one batch and one commit. studies: {slug: stats file} of the separate
    studies other than UZH-FPV and of the leaderboard pages with study families (the public_results.yaml entry, or its
    `extra` block, names batch, read_first and like_for_like). A stats file left out stops the export, unless the
    study is named in carry (check_studies)."""
    import tempfile
    from pathlib import Path

    import yaml

    from . import DATA
    from . import leaderboard as L
    from . import space
    from .repeatability import gate, load_records, private_words

    if not re.fullmatch(r"[0-9a-f]{40}", commit or ""):
        raise ValueError("results_commit must be the full 40-hex sha of the records snapshot")
    site = Path(site)
    pub = yaml.safe_load((DATA / "public_results.yaml").read_text(encoding="utf-8"))
    other, extras, found = check_studies(pub, studies or {}, carry)
    if found:  # before any solve data is read: a forgotten --study is the common mistake
        raise SystemExit("inputs disagree:\n  " + "\n  ".join(found))
    stats = json.loads(Path(stats_file).read_text())
    records = load_records(records_dir, batch)
    found = gate(stats, records, batch)
    rep = json.loads((site / "site/src/data/leaderboard/repeatability.json").read_text())
    board = json.loads((site / "site/src/data/leaderboard/board.json").read_text())
    if (rep["batch"], rep["results_commit"]) != (batch, commit):
        found.append(f"repeatability.json is {rep['batch']} {rep['results_commit']}, not {batch} {commit}")
    if (board["batch"], board["results_commit"]) != (batch, commit[:7]):
        found.append(f"board.json is {board['batch']} {board['results_commit']}, not {batch} {commit[:7]}")
    sp = space.space_rows(leaderboard_dir, records_dir, commit)
    ustats = L.without_repeated_weights_note(L.rekey(json.loads((Path(uzh_root) / L.UZH_STATS).read_text())))
    with tempfile.TemporaryDirectory(prefix="results_eval_") as tmp:
        usp = space.uzh_rows(leaderboard_dir, ustats, Path(tmp) / "rec")
        urec = load_records(Path(tmp) / "rec", L.BATCH)
    found += gate(ustats, urec, L.BATCH)
    kept, bad = carried(carry, site)
    found += bad
    srows = {}
    for slug, path in (studies or {}).items():
        e = other[slug] if slug in other else dict(extras[slug]["extra"], id=extras[slug]["id"], label=extras[slug]["label"])
        srows[slug], bad = study_inputs(leaderboard_dir, e, json.loads(Path(path).read_text()))
        found += bad
    if found:
        raise SystemExit("inputs disagree:\n  " + "\n  ".join(found[:40]))
    boards = dict(board["datasets"], uzh_fpv=json.loads((site / L.UZH_FILE).read_text())["fragment"])
    reps = {d["id"]: d for d in rep["datasets"]}
    pages = [kept[e["slug"]] if e["slug"] in kept
             else dataset(e, *srows[e["slug"]], e["batch"], None, None) if e["slug"] in other
             else dataset(e, usp, urec, ustats, L.BATCH, None, None) if e.get("study")
             else dataset(e, sp, records, stats, batch, commit, reps[e["id"]], srows.get(e["slug"])) for e in pub["datasets"]]
    # UZH bag names are UZH's own public sequence names, already on its page; only the batch's recording names are private.
    return pages, pub, sp["pairs"], boards, private_words(stats) + tuple(w for _, _, st in srows.values() for w in private_words(st))


def write(files: dict[str, str], site, commit: str, private: tuple = (), prune: bool = True) -> list:
    """Writes every file, or none when one has a problem. Generated MDX of a dataset no longer listed is removed
    (prune; off when only some pages are written)."""
    from pathlib import Path

    found = problems(files, commit, private)
    if found:
        raise SystemExit("refusing to write:\n  " + "\n  ".join(found[:20]))
    site = Path(site)
    keep = {site / p for p in files}
    for old in (site / MDX_DIR).glob("*.mdx") if prune else ():
        if old not in keep:
            old.unlink()
    for p, text in files.items():
        (site / p).parent.mkdir(parents=True, exist_ok=True)
        (site / p).write_text(text, encoding="utf-8")
    return sorted(keep)


# ---------------------------------------------------------------- separate studies alone (site/scripts/export_study.py)
def collect_studies(leaderboard_dir, studies: dict) -> tuple[list[dict], dict, tuple]:
    """(pages, pub, private words) of the separate studies in `studies` ({slug: stats file}), without the leaderboard
    batch inputs. Every other page, its sidebar entry and the Leaderboard rows stay as they were last exported.
    A leaderboard page with study families (`extra`) is refused: its batch families need the batch inputs, and the
    page is written whole by export_results.py."""
    from pathlib import Path

    import yaml

    from . import DATA
    from .repeatability import private_words

    pub = yaml.safe_load((DATA / "public_results.yaml").read_text(encoding="utf-8"))
    other, extras, _ = check_studies(pub, studies)
    found = [f"{s}: a leaderboard page with extra study families. export_study.py cannot rebuild it, because its batch "
             f"families need the batch inputs: run export_results.py with --study {s}=<its stats file>" if s in extras
             else f"{s}: not a separate study in public_results.yaml" for s in studies if s not in other]
    pages, private = [], ()
    for slug, path in studies.items():
        if slug not in other:
            continue
        e = other[slug]
        (rows, recs, st), bad = study_inputs(leaderboard_dir, e, json.loads(Path(path).read_text()))
        found += bad
        pages.append(dataset(e, rows, recs, st, e["batch"], None, None))
        private += private_words(st)
    if found:
        raise SystemExit("inputs disagree:\n  " + "\n  ".join(found[:40]))
    order = [e["slug"] for e in pub["datasets"]]
    return sorted(pages, key=lambda p: order.index(p["slug"])), pub, private


def render_studies(pages: list[dict], pub: dict, nav_old: list[dict], board: dict) -> dict[str, str]:
    """{path: text}: the study pages' JSON and MDX; the sidebar in page order with these entries replaced and every
    entry's group taken from public_results.yaml; the Leaderboard's study list with these studies replaced."""
    fresh = {n["slug"]: n for n in nav(pages, pub)}
    have = {n["slug"]: n for n in nav_old}
    side = []
    for e in pub["datasets"]:
        n = dict(fresh.get(e["slug"]) or have.get(e["slug"]) or {})
        if not n:
            continue
        n.pop("group", None)
        n.pop("nav_label", None)
        if e.get("nav_group"):
            n.update(group=e["nav_group"], nav_label=e.get("nav_label") or n["label"])
        side.append(n)
    links = [f"{RESULTS}{e['slug']}/" for e in pub["datasets"]]
    study = {s["link"]: s for s in board.get("studies", [])}
    study.update({p["link"]: {"label": p["label"], "link": p["link"], "batch": p["batch"], "note": p.get("study_note", "")}
                  for p in pages})
    board = dict(board, studies=sorted(study.values(), key=lambda s: links.index(s["link"]) if s["link"] in links else len(links)))
    files = {NAV_FILE: dumps(side), f"{OUT_DIR}/index.json": dumps(board)}
    for p in pages:
        files[f"{OUT_DIR}/{p['slug']}.json"] = dumps(p)
        files[f"{MDX_DIR}/{p['slug']}.mdx"] = mdx(p, "export_study.py")
    return files
