"""Write the data of /why/imu/ (site/src/data/why/imu.json) from the OpenVINS runs on the Monado recordings (stdlib only).

  PYTHONNOUSERSITE=1 python3 site/scripts/export_why_imu.py <inputs folder> [--out FILE]

The inputs folder holds four CSV files, made beside the run report by its make_page_inputs.py:
  pairs.csv          one row per recording, comparison and metric: baseline and treatment values on the common
                     time window of the two runs, their winner and the pair status;
  pairs_summary.csv  the medians, wins and two-sided Wilcoxon signed-rank p of each comparison, per headset and 'all';
  imu_intrinsics.csv the IMU maps OpenVINS ended with when it estimated them online, beside the MVIS maps;
  mvis_calibration.csv the MVIS IMU and time terms each corrected recording was written from.

Comparisons (names in pairs.csv, <cam> = stereo or mono):
  <cam>__raw_vs_corrected                as published -> corrected, nothing online (section 2);
  <cam>__raw_<x>_vs_corrected            as published + <x> online -> corrected, nothing online (section 3);
  <cam>__corrected_vs_corrected_<x>      corrected -> corrected + <x> online (section 3, last part);
with <x> = td, imu (IMU intrinsics), imu_td (both).

Computed here, so the page never types a number twice: every median, win count and p the page prints; per recording
the values of the two figures; on how many recordings the corrected recording beats every online setting; the online
td and accel scales against MVIS per headset. Lengths in mm, times in ms, scales as (s - 1) in %. The output is
refused if it holds a local path or a word the public-text lint bans.
"""
import argparse
import csv
import json
import statistics as st
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE.parent / "python"))
from mvis_site import lint  # noqa: E402  (pure stdlib module)

OUT = SITE / "src/data/why/imu.json"
DEVICES = [("valve_index", "Valve Index", "/devices/valve-index/"),
           ("reverb_g2", "HP Reverb G2", "/devices/hp-reverb-g2/"),
           ("odyssey_plus", "Samsung Odyssey+", "/devices/samsung-odyssey-plus/")]
ONLINE = [("td", "td"), ("imu", "IMU intrinsics"), ("imu_td", "IMU intrinsics + td")]
METRICS = {"ate": ("ate_se3_pos_rmse_m", 1e3), "rpe": ("rpe_1s_trans_rmse_m", 1e3),
           "scale": ("sim3_scale_abs_err", 1e2)}


def num(v):
    return float(v) if v not in ("", None) else None


def summary(summ, comp, metric, scale, device="all"):
    """Medians, wins and p of one comparison. wins = recordings where the treatment wins."""
    r = summ[(comp, device, metric)]
    return {"n": int(r["n_paired"]), "baseline": round(float(r["baseline_median"]) * scale, 2),
            "treatment": round(float(r["treatment_median"]) * scale, 2), "wins": int(r["wins_treatment"]),
            "losses": int(r["wins_baseline"]), "p": float(f"{float(r['wilcoxon_p']):.2g}")}


def per_recording(pairs, comp):
    """{recording: (baseline, treatment)} in mm for the paired recordings of one comparison, primary ATE."""
    out = {}
    for r in pairs:
        if r["comparison"] == comp and r["metric"] == METRICS["ate"][0] and r["pair_status"] == "paired":
            out[r["condition"].split("_")[0]] = (float(r["baseline"]) * 1e3, float(r["treatment"]) * 1e3)
    return out


def scales(pairs, comp):
    return {r["condition"].split("_")[0]: (num(r["baseline"]), num(r["treatment"])) for r in pairs
            if r["comparison"] == comp and r["metric"] == "sim3_scale" and r["pair_status"] == "paired"}


def family(cam, pairs, summ, device_of):
    main = f"{cam}__raw_vs_corrected"
    rec = per_recording(pairs, main)
    s = scales(pairs, main)
    fam = {
        "main": {k: summary(summ, main, m, f) for k, (m, f) in METRICS.items()},
        "by_device": [{"id": d, **summary(summ, main, METRICS["ate"][0], 1e3, d)} for d, _, _ in DEVICES],
        "recordings": [{"id": k, "device": device_of[k], "raw": round(a, 2), "corrected": round(b, 2),
                        "raw_s": round(s[k][0], 3), "corrected_s": round(s[k][1], 3)}
                       for k, (a, b) in sorted(rec.items())],
    }
    online = []
    for key, label in ONLINE:
        comp = f"{cam}__raw_{key}_vs_corrected"
        r = per_recording(pairs, comp)
        online.append({"key": key, "label": label, **summary(summ, comp, METRICS["ate"][0], 1e3),
                       "values": {k: round(a, 2) for k, (a, _) in sorted(r.items())},
                       "corrected": {k: round(b, 2) for k, (_, b) in sorted(r.items())}})
    fam["online_raw"] = online
    # The corrected recording against every online setting on the published one, each on its own common window.
    common = set.intersection(*(set(o["values"]) for o in online))
    beats = [k for k in common if all(o["corrected"][k] < o["values"][k] for o in online)]
    fam["beats_every_online"] = {"k": len(beats), "n": len(common)}
    fam["online_corrected"] = [{"key": key, "label": label,
                                **summary(summ, f"{cam}__corrected_vs_corrected_{key}", METRICS["ate"][0], 1e3)}
                               for key, label in ONLINE]
    return fam


def online_values(pairs, imu, mvis):
    """Per headset: MVIS cam0 td and the online OpenVINS td (as published and corrected, stereo + td), in ms;
    MVIS and online OpenVINS accel scales (stereo + IMU intrinsics + td, as published), (s - 1) in %."""
    td = {}
    for r in pairs:
        if r["metric"] == "ov_cam_imu_dt_tail20_median_s" and r["pair_status"] == "paired":
            if r["comparison"] == "stereo__raw_td_vs_corrected":
                td.setdefault(r["device"], {}).setdefault("raw", []).append(float(r["baseline"]) * 1e3)
            if r["comparison"] == "stereo__corrected_vs_corrected_td":
                td.setdefault(r["device"], {}).setdefault("corrected", []).append(float(r["treatment"]) * 1e3)
    out = []
    for d, label, _ in DEVICES:
        m = [r for r in mvis if r["device"] == d]
        o = [r for r in imu if r["device"] == d and r["arm"] == "raw" and r["mode"] == "stereo_imu_td"
             and r["repeat"] == "False" and r["status"] == "ok"]
        med = lambda rows, k: st.median(float(r[k]) for r in rows)
        out.append({
            "id": d, "label": label,
            "mvis_td_ms": round(med(m, "cam0_td_s") * 1e3, 2),
            "ov_td_ms": round(st.median(td[d]["raw"]), 2), "ov_td_corrected_ms": round(st.median(td[d]["corrected"]), 2),
            "mvis_da_pct": [round((med(m, f"Da_{a}") - 1) * 100, 2) for a in "xyz"],
            "ov_da_pct": [round((med(o, f"Ma_diag_{a}") - 1) * 100, 2) for a in "xyz"],
            "ov_reached": round(med(o, "Ma_recovered_reach"), 2), "n": len(o),
        })
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("inputs", type=Path)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    read = lambda name: list(csv.DictReader(open(a.inputs / name, encoding="utf-8")))
    pairs, imu, mvis = read("pairs.csv"), read("imu_intrinsics.csv"), read("mvis_calibration.csv")
    summ = {(r["comparison"], r["device"], r["metric"]): r for r in read("pairs_summary.csv")}
    device_of = {r["condition"].split("_")[0]: r["device"] for r in mvis}
    out = {
        "devices": [{"id": d, "label": l, "link": k, "n": sum(v == d for v in device_of.values())}
                    for d, l, k in DEVICES],
        "mvis": [{"id": d, "da_pct": [round((st.median(float(r[f"Da_{x}"]) for r in mvis if r["device"] == d) - 1)
                                            * 100, 1) for x in "xyz"],
                  "da_spread_pct": round(max(st.pstdev(float(r[f"Da_{x}"]) for r in mvis if r["device"] == d)
                                             for x in "xyz") * 100, 2)} for d, _, _ in DEVICES],
        "mono": family("mono", pairs, summ, device_of),
        "stereo": family("stereo", pairs, summ, device_of),
        "online_values": online_values(pairs, imu, mvis),
    }
    text = json.dumps(out, indent=1, ensure_ascii=False)
    problems = lint.public_problems(lint.process_strings(text)) + lint.refusals(text)
    if problems:
        raise SystemExit("refused: " + "; ".join(problems))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(text + "\n", encoding="utf-8")
    m = out["mono"]["main"]["ate"]
    print("wrote", a.out, f"mono ATE {m['baseline']} -> {m['treatment']} mm, {m['wins']}/{m['n']}")


if __name__ == "__main__":
    main()
