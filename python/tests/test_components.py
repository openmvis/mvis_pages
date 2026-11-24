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
    text = "OV9282 OV4689 SC136HGS SC132GS SC235HGS SC3336 EV76C560ABT IMX415 BMI055 BMI160 BMI270 BNO055 ICM-42670-P ICM-45686 MPU-9250 AR0234"
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
    got = C.label({"maker": "Bosch", "part": "BMI088", "src": "report", "via": "iFixit", "note": ""}, "imus")
    assert {k: v for k, v in got.items() if k != "html"} == {"maker": "Bosch", "part": "BMI088", "via": "iFixit", "count": 1, "src": "Teardown"}
    assert got["html"] == C.label_html("imus", {"maker": "Bosch", "part": "BMI088", "src": "report", "via": "iFixit"})
    assert C.label({"module": "Xsens MTi-100", "device": "VI-Rig"}, "imus").keys() == {"module", "device", "count", "html"}
    assert C.label({"count": 2}, "cameras")["count"] == 2


def test_label_html_named_chip_on_a_card_and_in_a_header():
    x = {"maker": "OmniVision", "part": "OV9282", "count": 2, "src": "report", "via": "Trade press", "note": "IR pair", "url": "https://x.org/a?b=1&c=2"}
    card = C.label_html("cameras", x)
    assert card.startswith('<span class="cl cam" title="Trade press · IR pair"><svg') and "<b>OmniVision</b> <span class=p>OV9282</span>" in card
    assert "<span class=x>×2</span>" in card and "cl-src" not in card and "<a" not in card   # a card is one link already
    head = C.label_html("cameras", x, link=True)
    assert head.endswith('<a class=cl-src href="https://x.org/a?b=1&amp;c=2">Teardown</a></span>')
    no_url = C.label_html("imus", {"maker": "Bosch", "part": "BMI088", "src": "maker", "via": "Manual, no public link"}, link=True)
    assert 'class="cl imu"' in no_url and no_url.endswith("<span class=cl-src>Maker</span></span>")


def test_label_html_module_unknown_and_escaping():
    m = C.label_html("imus", {"module": "Xsens MTi-100", "count": 1})
    assert 'class="cl imu mod"' in m and "<b>Xsens MTi-100</b>" in m and "<span class=cl-chip>chip not known</span>" in m and "×" not in m
    assert C.label_html("cameras", {"count": 4}).endswith("<span class=t>Camera not known <span class=x>×4</span></span></span>")
    assert "IMU not known" in C.label_html("imus", {})
    assert 'class="cl cam"' in C.label_html("uncalibrated", {"maker": "Sony", "part": "IMX1", "src": "maker", "via": "v"})
    assert "<b>A&lt;b&gt;</b>" in C.label_html("cameras", {"module": "A<b>"})


PUB = {"groups": [{"id": "g1", "title": "First"}, {"id": "g2", "title": "Second"}],
       "sensors": {"b": {"title": "B", "group": "g2", "card": {},
                         "components": {"cameras": [{"maker": "OmniVision", "part": "OV1", "src": "maker", "via": "v"}], "imus": [{"module": "Xsens MTi"}]}},
                   "a": {"title": "A", "group": "g1", "card": {"name": "A1"},
                         "components": {"cameras": [{"maker": "Sony", "part": "IMX1", "count": 2, "src": "report", "via": "v"}, {"count": 1}],
                                        "imus": [{"maker": "Bosch", "part": "BMI088", "src": "maker", "via": "v"}]}}}}
SETS = [{"slug": "s", "label": "Set S", "ours": True,
         "components": {"cameras": [{"maker": "Sony", "part": "IMX1", "count": 9, "device": "x", "src": "dataset", "via": "v"}], "imus": [{"device": "x"}]}}]


def test_catalog_counts_devices_only_in_sidebar_group_order():
    cat = C.catalog(PUB, SETS, "/devices/", "/benchmark/results/")
    assert cat["counts"] == {"cameras": {"total": 4, "not_known": 1, "by_maker": {"OmniVision": 1, "Sony": 2}},
                             "imus": {"total": 2, "not_known": 1, "by_maker": {"Bosch": 1}}}
    assert [(d["slug"], d["name"], d["group"], d["href"]) for d in cat["devices"]] == [("a", "A1", "First", "/devices/a/"), ("b", "B", "Second", "/devices/b/")]
    assert {k: v for k, v in cat["datasets"][0].items() if k not in ("cameras", "imus")} == {"slug": "s", "name": "Set S", "ours": True, "href": "/benchmark/results/s/"}


def test_by_maker_lists_parts_devices_first_with_their_source_tags():
    makers = C.catalog(PUB, SETS, "/devices/", "/r/")["makers"]
    assert [(m["kind"], m["maker"], m["key"]) for m in makers] == [("cameras", "OmniVision", "omnivision"), ("cameras", "Sony", "sony"), ("imus", "Bosch", "bosch")]
    sony = makers[1]
    assert (sony["on_devices"], sony["in_datasets"]) == (2, 9)
    assert sony["parts"] == [{"part": "IMX1", "tags": ["Teardown", "Dataset"], "uses": [
        {"name": "A1", "href": "/devices/a/", "count": 2, "dataset": False}, {"name": "Set S", "href": "/r/s/", "count": 9, "dataset": True}]}]
    assert makers[0]["parts"][0]["tags"] == []   # a maker source needs no tag


def test_not_known_lists_devices_only():
    assert C.catalog(PUB, SETS, "/devices/", "/r/")["not_known"] == {"cameras": [{"name": "A1", "href": "/devices/a/", "count": 1}],
                                                                       "imus": [{"name": "B", "href": "/devices/b/", "count": 1}]}


def test_catalog_refuses_a_sensor_in_no_group():
    pub = {**PUB, "groups": PUB["groups"][:1]}
    with pytest.raises(ValueError, match=r"in no group.*\['b'\]"):
        C.catalog(pub, [], "/devices/", "/r/")


def test_committed_catalog_matches_the_plan_totals():
    """Devices: 45 cameras and 19 IMUs; cameras without a named chip 10, IMUs 3 (2026-11-20, after the second chip search)."""
    pub = yaml.safe_load((DATA / "public_sensors.yaml").read_text(encoding="utf-8"))
    c = C.catalog(pub, DATASETS, "/devices/", "/r/")["counts"]
    assert (c["cameras"]["total"], c["cameras"]["not_known"], c["imus"]["total"], c["imus"]["not_known"]) == (45, 10, 19, 3)
