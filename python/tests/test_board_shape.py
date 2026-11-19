"""Board shape on a sensor page: read from a run folder, drawn per corner, shown only when the run estimated it."""
import numpy as np
import pytest
import yaml

from mvis_site.markup import board_shape_svg
from mvis_site.results import read_board_shape
from mvis_site.sensor_parts import board_shape_section

BOARD = {"rows": 2, "cols": 3, "tag_mm": 50.0, "spacing": 0.3}


def _shape(n=24, unseen=()):
    h = np.linspace(-0.003, 0.005, n)
    obs = [0 if i in unseen else 7 for i in range(n)]
    return h, obs


def test_read_board_shape_uses_seen_corners_only(tmp_path):
    h, obs = _shape(unseen=(23,))
    (tmp_path / "cam_imu_board_shape.yaml").write_text(yaml.safe_dump({"board_shape": {"heights_m": h.tolist(), "n_obs": obs}}))
    s = read_board_shape(tmp_path)
    assert s["p2p_mm"] == pytest.approx(np.ptp(h[:23]) * 1e3) and s["rms_mm"] == pytest.approx(np.std(h[:23]) * 1e3)
    assert read_board_shape(tmp_path / "missing") is None


def test_svg_draws_every_corner_and_marks_unseen():
    h, obs = _shape(unseen=(0,))
    svg = board_shape_svg(BOARD, {"heights_m": h.tolist(), "n_obs": obs, "p2p_mm": 8.0, "rms_mm": 2.0})
    assert svg.count("<circle") == 24 and svg.count("not seen") == 1
    assert "peak to peak 8.0 mm" in svg and "+5.0 mm" in svg            # colour scale symmetric about flat
    # corner 0 of tag 0 sits bottom-left: smallest x, largest y in SVG coordinates
    first = svg.index('<circle cx="0.0" cy="115.0"')
    assert first > 0


def test_svg_refuses_heights_for_another_board():
    with pytest.raises(ValueError, match="AprilGrid"):
        board_shape_svg(BOARD, {"heights_m": [0.0] * 5, "n_obs": [1] * 5, "p2p_mm": 0, "rms_mm": 0})


def test_section_only_when_a_run_estimated_the_shape():
    flat = {"board_shape": None}
    assert board_shape_section([flat, flat], BOARD) == ""
    h, obs = _shape()
    shaped = {"board_shape": {"heights_m": h.tolist(), "n_obs": obs, "p2p_mm": 8.0, "rms_mm": 2.0}}
    html = board_shape_section([shaped, flat], BOARD)
    assert "<svg" in html and "assumed a flat board" in html



def test_svg_labels_tags_and_ticks_the_scale():
    h, obs = _shape()
    svg = board_shape_svg(BOARD, {"heights_m": h.tolist(), "n_obs": obs, "p2p_mm": 8.0, "rms_mm": 2.0})
    assert 'class="board bshape"' in svg
    labels = [s.split(">")[-1] for s in svg.split("</text>")[:-1]]
    assert labels[:5] == ["0", "1", "2", "0", "1"]                          # 3 tag columns, then 2 tag rows
    assert labels[5:] == ["-5.0 mm", "-2.5 mm", "flat", "+2.5 mm", "+5.0 mm"]
    assert svg.count("<line ") == 5


def test_corner_dots_never_touch_the_next_tag():
    import re
    for spacing in (0.1, 0.25, 0.3):
        b = dict(BOARD, spacing=spacing)
        h, obs = _shape()
        r = float(re.search(r' r="([\d.]+)"', board_shape_svg(b, {"heights_m": h.tolist(), "n_obs": obs, "p2p_mm": 8.0, "rms_mm": 2.0})).group(1))
        assert 2 * r < b["tag_mm"] * spacing


def test_chessboard_run_carries_its_board_and_draws_row_major(tmp_path):
    h, obs = _shape(n=6, unseen=(5,))
    (tmp_path / "cam_imu_board_shape.yaml").write_text(yaml.safe_dump({"board_shape": {"heights_m": h.tolist(), "n_obs": obs}}))
    (tmp_path / "cam_imu.yaml").write_text(yaml.safe_dump({"board": {"board_type": "chessboard", "rows": 2, "cols": 3, "square_size": 0.04}}))
    s = read_board_shape(tmp_path)
    assert s["board"] == {"type": "chessboard", "rows": 2, "cols": 3, "square_mm": 40.0}
    svg = board_shape_svg(BOARD, s)                                     # the sensor's AprilGrid is not used
    assert svg.count("<circle") == 6 and svg.count("not seen") == 1 and "chessboard 2 by 3" in svg
    assert svg.index('<circle cx="0.0" cy="40.0"') < svg.index('<circle cx="80.0" cy="40.0"') < svg.index('<circle cx="0.0" cy="0.0"')
    assert "corner column and row" in svg
    with pytest.raises(ValueError, match="chessboard"):
        board_shape_svg(BOARD, {**s, "heights_m": [0.0] * 5, "n_obs": [1] * 5})


def test_aprilgrid_run_keeps_the_sensor_board(tmp_path):
    h, obs = _shape()
    (tmp_path / "cam_imu_board_shape.yaml").write_text(yaml.safe_dump({"board_shape": {"heights_m": h.tolist(), "n_obs": obs}}))
    (tmp_path / "cam_imu.yaml").write_text(yaml.safe_dump({"board": {"board_type": "aprilgrid", "rows": 2, "cols": 3}}))
    assert "board" not in read_board_shape(tmp_path)
