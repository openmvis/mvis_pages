"""export_why_imu.py on synthetic inputs, and the committed /why/imu/ data against the page's description."""
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

from mvis_site import REPO, lint

SCRIPT = REPO / "site/scripts/export_why_imu.py"
DATA = REPO / "site/src/data/why/imu.json"
PAGE = REPO / "site/src/content/docs/why/imu.mdx"
DEVICES = {"MIC01": "valve_index", "MIC02": "valve_index", "MGC01": "reverb_g2", "MGC02": "reverb_g2",
           "MOC01": "odyssey_plus", "MOC02": "odyssey_plus"}


def write(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def make_inputs(tmp):
    pairs, summ = [], []
    comps = []
    for cam in ("stereo", "mono"):
        comps.append((f"{cam}__raw_vs_corrected", f"raw_{cam}", f"roundtrip_{cam}", 2.0, 1.0))
        for k, x in (("td", 1.6), ("imu", 1.8), ("imu_td", 1.4)):
            comps.append((f"{cam}__raw_{k}_vs_corrected", f"raw_{cam}_{k}", f"roundtrip_{cam}", 2.0 * x / 2, 1.0))
            comps.append((f"{cam}__corrected_vs_corrected_{k}", f"roundtrip_{cam}", f"roundtrip_{cam}_{k}", 1.0, 1.1))
    for name, bl, tl, b, t in comps:
        for i, (rec, dev) in enumerate(DEVICES.items()):
            cond = f"{rec}_imucalib__cam0-cam1"
            for metric, bv, tv in (("ate_se3_pos_rmse_m", b * 0.01 * (1 + i / 10), t * 0.01 * (1 + i / 10)),
                                   ("rpe_1s_trans_rmse_m", b * 0.005, t * 0.005),
                                   ("sim3_scale_abs_err", 0.05, 0.02), ("sim3_scale", 0.95, 0.98),
                                   ("ov_cam_imu_dt_tail20_median_s", -0.0012, 0.00002)):
                pairs.append({"comparison": name, "condition": cond, "device": dev, "metric": metric,
                              "pair_status": "paired", "baseline": bv, "treatment": tv,
                              "baseline_leaf": bl, "treatment_leaf": tl})
        for dev in ("all", *sorted(set(DEVICES.values()))):
            for metric in ("ate_se3_pos_rmse_m", "rpe_1s_trans_rmse_m", "sim3_scale_abs_err"):
                summ.append({"comparison": name, "device": dev, "metric": metric, "n_paired": 6,
                             "baseline_median": b * 0.01, "treatment_median": t * 0.01, "wins_treatment": 5,
                             "wins_baseline": 1, "wilcoxon_p": 0.03125})
    write(tmp / "pairs.csv", pairs)
    write(tmp / "pairs_summary.csv", summ)
    mvis = [{"condition": f"{r}_imucalib__cam0-cam1", "device": d, "Da_x": 1.06, "Da_y": 1.05, "Da_z": 1.07,
             "cam0_td_s": -0.0013} for r, d in DEVICES.items()]
    write(tmp / "mvis_calibration.csv", mvis)
    imu = [{"condition": f"{r}_imucalib__cam0-cam1", "device": d, "arm": "raw", "mode": "stereo_imu_td",
            "repeat": "False", "status": "ok", "Ma_recovered_reach": 0.6, "Ma_diag_x": 1.03, "Ma_diag_y": 1.03,
            "Ma_diag_z": 1.04} for r, d in DEVICES.items()]
    write(tmp / "imu_intrinsics.csv", imu)


def test_export_on_synthetic_inputs(tmp_path):
    make_inputs(tmp_path)
    out = tmp_path / "imu.json"
    subprocess.run([sys.executable, str(SCRIPT), str(tmp_path), "--out", str(out)], check=True,
                   capture_output=True, text=True)
    d = json.loads(out.read_text())
    m = d["mono"]
    assert m["main"]["ate"] == {"n": 6, "baseline": 20.0, "treatment": 10.0, "wins": 5, "losses": 1, "p": 0.031}
    assert [o["key"] for o in m["online_raw"]] == ["td", "imu", "imu_td"]
    assert m["beats_every_online"] == {"k": 6, "n": 6}
    assert len(m["recordings"]) == 6 and m["recordings"][0]["raw"] > m["recordings"][0]["corrected"]
    v = {x["id"]: x for x in d["online_values"]}["reverb_g2"]
    assert v["mvis_td_ms"] == -1.3 and v["ov_td_ms"] == -1.2 and v["ov_reached"] == 0.6
    assert [x["n"] for x in d["devices"]] == [2, 2, 2]


def test_committed_data_is_public_and_matches_the_description():
    text = DATA.read_text()
    assert not lint.public_problems(lint.process_strings(text))
    d = json.loads(text)
    ate = d["mono"]["main"]["ate"]
    # The description says the correction cuts mono position error "by more than half".
    assert ate["treatment"] / ate["baseline"] < 0.5
    assert re.search(r"by more than half", PAGE.read_text())
