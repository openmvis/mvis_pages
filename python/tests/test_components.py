"""The chip labels: the components blocks of the committed public data, and the checks and counts in mvis_site.components."""
import re

import pytest
import yaml

from mvis_site import DATA
from mvis_site import components as C

SENSORS = yaml.safe_load((DATA / "public_sensors.yaml").read_text(encoding="utf-8"))["sensors"]
DATASETS = yaml.safe_load((DATA / "public_results.yaml").read_text(encoding="utf-8"))["datasets"]


def test_every_committed_block_passes_the_checks():
    found = [x for slug, p in SENSORS.items() for x in C.problems(p.get("components"), slug)]
    found += [x for d in DATASETS for x in C.problems(d.get("components"), d["slug"], dataset=True)]
    assert found == []


@pytest.mark.parametrize("slug", sorted(SENSORS))
def test_device_cameras_match_the_card_tag(slug):
    """The card says "N cameras"; the labels must add up to the same N."""
    p = SENSORS[slug]
    tag = next(t for t in p["card"]["tags"] if re.fullmatch(r"\d+ cameras?", t))
    assert C.count(p["components"], "cameras") == int(tag.split()[0])
    assert C.count(p["components"], "imus") == 1   # every device page solves one IMU


@pytest.mark.parametrize("d", DATASETS, ids=lambda d: d["slug"])
def test_dataset_parts_match_its_sensor_list(d):
    """Each camera and IMU of the results page (distinct names in its sensor map) has exactly one label slot."""
    names = {label.split(" – ", 1)[1] for label in d["sensors"]}
    imus = {label.split(" – ", 1)[1] for label in d["sensors"] if "IMU –" in label}
    assert C.count(d["components"], "imus") == len(imus)
    assert C.count(d["components"], "cameras") == len(names - imus)


def _text_parts(entry: dict) -> set[str]:
    return set(C.PART_RE.findall(yaml.safe_dump({k: v for k, v in entry.items() if k != "components"}, allow_unicode=True)))


def _labelled(c: dict) -> str:
    return " ".join(x.get("part", "") for kind in (*C.KINDS, "uncalibrated") for x in c.get(kind) or [])


@pytest.mark.parametrize("entry", [*SENSORS.values(), *DATASETS], ids=lambda e: e.get("slug") or e["title"])
def test_a_chip_named_in_page_text_has_its_label(entry):
    """A part number anywhere in a page's words must also be a label, so the spec rows and the labels can't disagree."""
    missing = [p for p in _text_parts(entry) if p not in _labelled(entry["components"])]
    assert missing == []


def test_part_re_finds_the_chips_we_name():
    text = "OV9282 SC136HGS SC132GS IMX415 BMI055 BMI160 ICM-42670-P ICM-45686 MPU-9250 AR0234"
    assert C.PART_RE.findall(text) == text.split()


@pytest.mark.parametrize("part, msg", [
    ({"maker": "Acme", "part": "X1", "src": "maker", "via": "v"}, "not in CHIP_MAKERS"),
    ({"maker": "Bosch", "src": "maker", "via": "v"}, "needs its part"),
    ({"maker": "Bosch", "part": "BMI088", "src": "guess", "via": "v"}, "src must be"),
    ({"maker": "Bosch", "part": "BMI088", "src": "maker"}, "needs via"),
    ({"maker": "Bosch", "part": "BMI088", "src": "maker", "via": "v", "module": "M"}, "not both"),
    ({"part": "BMI088"}, "need a maker"),
    ({"count": 0}, "at least 1"),
    ({"colour": "red"}, "unknown key colour"),
])
def test_part_problems(part, msg):
    found = C.problems({"cameras": [{"count": 1}], "imus": [part]}, "x")
    assert len(found) == 1 and msg in found[0]


def test_block_problems():
    assert C.problems(None, "x") == ["x: no components"]
    assert any("imus must list" in x for x in C.problems({"cameras": [{}]}, "x"))
    assert C.problems({"cameras": [{}], "imus": [{}]}, "x", dataset=True) == ["x cameras[0]: a dataset part needs device, the device it sits on",
                                                                              "x imus[0]: a dataset part needs device, the device it sits on"]


def test_label_drops_empty_fields_and_shows_the_source_tag():
    assert C.label({"maker": "Bosch", "part": "BMI088", "src": "report", "via": "iFixit", "note": ""}) == \
        {"maker": "Bosch", "part": "BMI088", "via": "iFixit", "count": 1, "src": "Teardown"}
    assert C.label({"module": "Xsens MTi-100", "device": "VI-Rig"}) == {"module": "Xsens MTi-100", "device": "VI-Rig", "count": 1}
    assert C.label({"count": 2}) == {"count": 2}


def test_catalog_counts_devices_only_by_maker_in_list_order():
    sensors = {"a": {"title": "A", "group": "g", "card": {"name": "A"},
                     "components": {"cameras": [{"maker": "Sony", "part": "IMX1", "count": 2, "src": "maker", "via": "v"}, {"count": 1}],
                                    "imus": [{"maker": "Bosch", "part": "BMI088", "src": "maker", "via": "v"}]}},
               "b": {"title": "B", "group": "g", "card": {},
                     "components": {"cameras": [{"maker": "OmniVision", "part": "OV1", "src": "maker", "via": "v"}], "imus": [{"module": "Xsens MTi"}]}}}
    datasets = [{"slug": "s", "label": "S", "components": {"cameras": [{"maker": "Sony", "part": "IMX1", "count": 9, "device": "x", "src": "maker", "via": "v"}],
                                                           "imus": [{"device": "x"}]}}]
    cat = C.catalog(sensors, datasets, "/devices/", "/benchmark/results/")
    assert cat["counts"] == {"cameras": {"total": 4, "not_known": 1, "by_maker": {"OmniVision": 1, "Sony": 2}},
                             "imus": {"total": 2, "not_known": 1, "by_maker": {"Bosch": 1}}}
    assert [d["href"] for d in cat["devices"]] == ["/devices/a/", "/devices/b/"] and cat["devices"][1]["name"] == "B"
    assert cat["datasets"][0] == {"slug": "s", "label": "S", "ours": False, "href": "/benchmark/results/s/",
                                  "cameras": [{"maker": "Sony", "part": "IMX1", "device": "x", "via": "v", "count": 9, "src": "Maker"}],
                                  "imus": [{"device": "x", "count": 1}]}
