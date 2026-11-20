"""Who made the cameras and IMUs we calibrated: the `components` blocks of public_sensors.yaml (one per device) and
public_results.yaml (one per dataset evaluation), checked here and turned into the device cards' labels and
site/src/data/components.json, which the Cameras and IMUs page reads.

A part is {maker, part, count, src, via, url, note} for a named chip, {module, count} for a packaged module whose
chip no source names (Xsens, MicroStrain, ELP, IDS), and {count} alone when nothing names it ("not known"). Dataset
parts also say `device`, the device they sit on. src says who named the chip: the device maker (also a private file or
message, then without url), the dataset authors, or a teardown / trade report. We never name a chip from a guess.
"""
from __future__ import annotations

import re

CHIP_MAKERS = ("OmniVision", "SmartSens", "Sony", "onsemi", "iniVation", "Bosch", "TDK InvenSense", "STMicroelectronics")
SOURCES = {"maker": "Maker", "dataset": "Dataset", "report": "Teardown"}
KINDS = ("cameras", "imus")
KEYS = {"maker", "part", "count", "src", "via", "url", "note", "module", "device"}
# A chip part number in page text; each one must also be a component, so no part sits in a spec row without its label.
PART_RE = re.compile(r"\b(?:OV\d{4}|SC1\d\dH?GS|IMX\d{3}|AR0\d{3}|BMI0\d\d|BMI1\d\d|ICM-\d{5}(?:-P)?|MPU-\d{4})\b")


def named(x: dict) -> bool:
    return bool(x.get("maker"))


def part_problems(x: dict, where: str, dataset: bool) -> list[str]:
    out = [f"{where}: unknown key {k}" for k in sorted(set(x) - KEYS)]
    if not isinstance(x.get("count", 1), int) or x.get("count", 1) < 1:
        out.append(f"{where}: count must be a whole number of at least 1")
    if named(x):
        if x["maker"] not in CHIP_MAKERS:
            out.append(f"{where}: {x['maker']} is not in CHIP_MAKERS")
        if not x.get("part"):
            out.append(f"{where}: a named chip needs its part")
        if x.get("src") not in SOURCES:
            out.append(f"{where}: src must be one of {', '.join(SOURCES)}")
        if not x.get("via"):
            out.append(f"{where}: a named chip needs via, the source in words")
        if "module" in x:
            out.append(f"{where}: a part is a named chip or a module, not both")
    elif any(k in x for k in ("part", "src", "via", "url")):
        out.append(f"{where}: part, src, via and url need a maker")
    if dataset and not x.get("device"):
        out.append(f"{where}: a dataset part needs device, the device it sits on")
    return out


def problems(c: dict | None, where: str, dataset: bool = False) -> list[str]:
    """Everything wrong with one components block; empty when it is fine."""
    if not c:
        return [f"{where}: no components"]
    out = [f"{where}: unknown key {k}" for k in sorted(set(c) - {*KINDS, "uncalibrated"})]
    for kind in KINDS:
        if not c.get(kind):
            out.append(f"{where}: {kind} must list at least one part (a part without a maker is 'not known')")
    for kind in (*KINDS, "uncalibrated"):
        for i, x in enumerate(c.get(kind) or []):
            out += part_problems(x, f"{where} {kind}[{i}]", dataset)
    return out


def count(c: dict, kind: str) -> int:
    return sum(x.get("count", 1) for x in c[kind])


def label(x: dict) -> dict:
    """One part as the site's label component reads it: no empty fields, src as its shown tag."""
    out = {k: x[k] for k in ("maker", "part", "module", "note", "device", "via", "url") if x.get(k)}
    out["count"] = x.get("count", 1)
    if named(x):
        out["src"] = SOURCES[x["src"]]
    return out


def labels(c: dict) -> dict:
    return {kind: [label(x) for x in c.get(kind) or []] for kind in (*KINDS, "uncalibrated") if c.get(kind)}


def tally(rows: list[dict]) -> dict:
    """Per kind: parts calibrated, how many have no named chip, and the count per chip maker (in CHIP_MAKERS order)."""
    out = {}
    for kind in KINDS:
        by, total, unknown = {}, 0, 0
        for r in rows:
            for x in r[kind]:
                total += x["count"]
                if x.get("maker"):
                    by[x["maker"]] = by.get(x["maker"], 0) + x["count"]
                else:
                    unknown += x["count"]
        out[kind] = {"total": total, "not_known": unknown, "by_maker": {m: by[m] for m in CHIP_MAKERS if m in by}}
    return out


def catalog(sensors: dict, datasets: list[dict], device_base: str, results_base: str) -> dict:
    """components.json: every device and every dataset evaluation with its labels, and the device-only tally the page's
    tiles and bars show (a T265 used in three evaluations would count four times if datasets were added)."""
    devices = [{"slug": slug, "title": p["title"], "name": p["card"].get("name", p["title"]), "group": p["group"],
                "href": f"{device_base}{slug}/", **labels(p["components"])} for slug, p in sensors.items()]
    evals = [{"slug": d["slug"], "label": d["label"], "ours": bool(d.get("ours")), "href": f"{results_base}{d['slug']}/",
              **labels(d["components"])} for d in datasets]
    return {"devices": devices, "datasets": evals, "counts": tally(devices)}
