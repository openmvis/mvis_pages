"""The Local gravity city list (mvis_site.gravity_cities): GeoNames rows -> [name, country, region, lat, alt]."""
from mvis_site import gravity_cities as G


def _row(gid, name, lat, cc, a1, pop, elev, dem):
    f = [""] * 19
    f[0], f[1], f[2], f[4], f[5], f[8], f[10], f[14], f[15], f[16] = gid, name, name, lat, "0", cc, a1, pop, elev, dem
    return "\t".join(f)


CITIES = "\n".join([
    _row("1", "Small", "10.123", "AA", "01", "20000", "", "77"),        # no elevation: the dem
    _row("2", "Big", "-31.4065", "AA", "02", "900000", "380", "378"),   # elevation wins
    _row("3", "Sea", "1.0", "BB", "09", "50000", "", "-9999"),          # dem has no value: 0; region 09 unknown
    "broken line",
])
ADMIN1 = "AA.01\tNorth\tNorth\t11\nAA.02\tSouth\tSouth\t12\nZZ.01\tUnused\tUnused\t13\n"
COUNTRIES = "#ISO\tISO3\tnum\tfips\tCountry\nAA\tAAA\t1\tAA\tAland\nBB\tBBB\t2\tBB\tBeeland\nZZ\tZZZ\t3\tZZ\tUnused\n"


def test_rows_sorted_by_population_with_altitude_fallbacks():
    obj = G.build(CITIES, ADMIN1, COUNTRIES, "2026-11-25")
    assert obj["cities"] == [["Big", "AA", "AA.02", -31.41, 380], ["Sea", "BB", "", 1.0, 0], ["Small", "AA", "AA.01", 10.12, 77]]
    assert obj["regions"] == {"AA.01": "North", "AA.02": "South"}
    assert obj["countries"] == {"AA": "Aland", "BB": "Beeland"}
    assert "GeoNames" in obj["source"] and "2026-11-25" in obj["source"]


def test_write_is_compact_utf8(tmp_path):
    out = tmp_path / "c.json"
    n = G.write({"cities": [["Zürich", "CH", "", 47.37, 408]]}, out)
    assert out.read_text(encoding="utf-8") == '{"cities":[["Zürich","CH","",47.37,408]]}\n' and n == len(out.read_bytes()) - 1
