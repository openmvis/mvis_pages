"""Board-shape figure for /why/board-shape/: one all-corner camera–IMU solve, drawn like the device pages.

  python site/scripts/export_why_board_shape.py <run folder with cam_imu_board_shape.yaml>
      # writes site/src/data/why/board-shape.html
The page uses VI-Rig 4 IMUs + 4 cameras recording 3, all corners, MVIS main f902d39 (2026-11-11).
"""
import argparse
from pathlib import Path

import _lib
from mvis_site.markup import board_shape_svg
from mvis_site.results import read_board_shape

BOARD = {"rows": 6, "cols": 6, "tag_mm": 88, "spacing": 0.3}      # VI-Rig AprilGrid, t36h11
OUT = _lib.REPO / "site/src/data/why/board-shape.html"

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("run", type=Path)
shape = read_board_shape(ap.parse_args().run.expanduser())
if shape is None:
    raise SystemExit("no cam_imu_board_shape.yaml in that folder")
OUT.write_text(board_shape_svg(BOARD, shape) + "\n")
print("wrote", OUT, f"p2p {shape['p2p_mm']:.2f} mm, rms {shape['rms_mm']:.2f} mm")
