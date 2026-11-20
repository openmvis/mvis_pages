"""Who made the cameras and IMUs we calibrated: the `components` blocks of public_sensors.yaml (one per device) and
public_results.yaml (one per dataset evaluation), checked here and turned into the device cards' labels and
site/src/data/components.json, which the Cameras and IMUs page reads.

A part is {maker, part, count, src, via, url, note} for a named chip, {module, count} for a packaged module whose
chip no source names (Xsens, MicroStrain), and {count} alone when nothing names it ("not known"). Dataset
parts also say `device`, the device they sit on. src says who named the chip: the device maker (also a private file or
message, then without url), the dataset authors, or a teardown / trade report. We never name a chip from a guess.
"""
from __future__ import annotations

import re
from html import escape as e

CHIP_MAKERS = ("OmniVision", "SmartSens", "Sony", "onsemi", "iniVation", "Bosch", "TDK InvenSense", "STMicroelectronics", "e2v")
SOURCES = {"maker": "Maker", "dataset": "Dataset", "report": "Teardown"}
KINDS = ("cameras", "imus")
KEYS = {"maker", "part", "count", "src", "via", "url", "note", "module", "device"}
# A chip part number in page text; each one must also be a component, so no part sits in a spec row without its label.
PART_RE = re.compile(r"\b(?:OV\d{4}|SC\d{3,4}(?:H?GS)?|EV76C\d{3}[A-Z]*|IMX\d{3}|AR0\d{3}|BMI0\d\d|BMI1\d\d|BMI2\d\d|BNO0\d\d|ICM-\d{5}(?:-P)?|MPU-\d{4})\b")


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


# Lens and chip outlines; the kind reads from the icon as well as the colour.
ICONS = {"cameras": '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="1.5" y="4" width="13" height="9" rx="2"/><circle cx="8" cy="8.5" r="2.6"/>'
                    '<path d="M5.5 4l1-1.6h3l1 1.6"/></svg>',
         "imus": '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="4" y="4" width="8" height="8" rx="1.2"/>'
                 '<path d="M6.5 4V2M9.5 4V2M6.5 14v-2M9.5 14v-2M4 6.5H2M4 9.5H2M14 6.5h-2M14 9.5h-2"/></svg>'}
NOT_KNOWN = {"cameras": "Camera not known", "imus": "IMU not known"}


def label_html(kind: str, x: dict, link: bool = False) -> str:
    """One label, the same on cards, device headers and the Cameras and IMUs page (styles: .cl in custom.css). With link,
    a named chip ends in its source tag, linked when the source has a url; cards leave the tag to the device page."""
    n = x.get("count", 1)
    times = f" <span class=x>×{n}</span>" if n > 1 else ""
    icon, k = (ICONS["imus"], "imu") if kind == "imus" else (ICONS["cameras"], "cam")   # uncalibrated parts are cameras
    if named(x):
        tip = " · ".join(v for v in (x["via"], x.get("note")) if v)
        tag = SOURCES[x["src"]]
        src = (f' <a class=cl-src href="{e(x["url"])}">{tag} ↗</a>' if x.get("url") else f" <span class=cl-src>{tag}</span>") if link else ""
        return f'<span class="cl {k}" title="{e(tip)}">{icon}<span class=t><b>{e(x["maker"])}</b> <span class=p>{e(x["part"])}</span>{times}</span>{src}</span>'
    if x.get("module"):
        return (f'<span class="cl {k} mod" title="Packaged module; no source names the chip inside">{icon}'
                f'<span class=t><b>{e(x["module"])}</b>{times}</span><span class=cl-chip>chip not known</span></span>')
    return f'<span class="cl {k} unk">{icon}<span class=t>{NOT_KNOWN["imus" if kind == "imus" else "cameras"]}{times}</span></span>'


def label(x: dict, kind: str) -> dict:
    """One part as the site reads it: no empty fields, src as its shown tag, and its label's html."""
    out = {k: x[k] for k in ("maker", "part", "module", "note", "device", "via", "url") if x.get(k)}
    out["count"] = x.get("count", 1)
    if named(x):
        out["src"] = SOURCES[x["src"]]
    out["html"] = label_html(kind, x)
    return out


def labels(c: dict) -> dict:
    return {kind: [label(x, kind) for x in c.get(kind) or []] for kind in (*KINDS, "uncalibrated") if c.get(kind)}


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


def by_maker(devices: list[dict], evals: list[dict]) -> list[dict]:
    """The "By chip maker" view: per kind and maker (CHIP_MAKERS order), each part with its source tags and where it is
    used, devices first, then dataset evaluations."""
    out = []
    for kind in KINDS:
        for maker in CHIP_MAKERS:
            parts: dict[str, dict] = {}
            for rows, is_set in ((devices, False), (evals, True)):
                for r in rows:
                    for x in r[kind]:
                        if x.get("maker") != maker:
                            continue
                        p = parts.setdefault(x["part"], {"part": x["part"], "tags": [], "uses": []})
                        if x["src"] != SOURCES["maker"] and x["src"] not in p["tags"]:
                            p["tags"].append(x["src"])
                        p["uses"].append({"name": r["name"], "href": r["href"], "count": x["count"], "dataset": is_set})
            if parts:
                n = lambda s: sum(u["count"] for p in parts.values() for u in p["uses"] if u["dataset"] is s)
                out.append({"kind": kind, "maker": maker, "key": slug(maker), "on_devices": n(False), "in_datasets": n(True),
                            "parts": list(parts.values())})
    return out


def not_known(devices: list[dict]) -> dict:
    """Devices with a part that no source names, per kind (devices only, like the tiles)."""
    return {kind: [{"name": r["name"], "href": r["href"], "count": sum(x["count"] for x in r[kind] if not x.get("maker"))}
                   for r in devices if any(not x.get("maker") for x in r[kind])] for kind in KINDS}


def slug(maker: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", maker.lower()).strip("-")


def catalog(pub: dict, datasets: list[dict], device_base: str, results_base: str) -> dict:
    """components.json: every device (in the sidebar's group order) and every dataset evaluation with its labels, the
    views' groupings, and the device-only tally the page's tiles and bars show (a T265 used in three evaluations would
    count four times if datasets were added)."""
    sensors = pub["sensors"]
    devices = [{"slug": slug_, "title": p["title"], "name": p["card"].get("name", p["title"]), "group": g["title"],
                "href": f"{device_base}{slug_}/", **labels(p["components"])}
               for g in pub["groups"] for slug_, p in sensors.items() if p["group"] == g["id"]]
    if len(devices) != len(sensors):
        raise ValueError(f"sensors in no group of public_sensors.yaml: {sorted(set(sensors) - {d['slug'] for d in devices})}")
    evals = [{"slug": d["slug"], "name": d["label"], "ours": bool(d.get("ours")), "href": f"{results_base}{d['slug']}/",
              **labels(d["components"])} for d in datasets]
    return {"devices": devices, "datasets": evals, "counts": tally(devices), "makers": by_maker(devices, evals),
            "not_known": not_known(devices)}
