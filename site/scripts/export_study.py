"""Write the Dataset eval page of one or more separate studies (public_results.yaml `study: true`) without the
leaderboard batch inputs: the page JSON and MDX, its sidebar entry and its line in the Leaderboard's study list. Every
other page, sidebar entry and Leaderboard row stays as export_results.py last wrote it.

It cannot rebuild a leaderboard page that lists study families (public_results.yaml extra:, as Monado MGC with its
pairs 02 and 13): that page's batch families need the batch inputs, so it is written whole by export_results.py with
--study <slug>=<stats file>. Such a slug stops this script.

  PYTHONNOUSERSITE=1 python3 site/scripts/export_study.py --leaderboard <Space folder> --study <slug>=<stats file> [...]

The stats file is the study's three-way stats file (gen_kalibr_compare.py schema); it is private: only min and max
per row and tool leave it, and the export refuses output with a path, a banned word or a recording name.
"""
import argparse
import json
from pathlib import Path

import _lib
from mvis_site.env import require_numpy_1

require_numpy_1()
from mvis_site import results_eval as R

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--leaderboard", type=Path, required=True, help="the leaderboard Space folder (app.py, export_threeway.py)")
ap.add_argument("--study", action="append", required=True, metavar="SLUG=FILE", help="a study's stats file; one per study")
ap.add_argument("--site", type=Path, default=_lib.REPO, help="the checkout to write into")
a = ap.parse_args()
if any("=" not in s for s in a.study):
    ap.error("--study takes SLUG=FILE, e.g. monado-mic=stats.json")
x = lambda p: Path(p).expanduser()
pages, pub, private = R.collect_studies(x(a.leaderboard), {k: x(v) for k, v in (s.split("=", 1) for s in a.study)})
site = x(a.site)
board = json.loads((site / R.OUT_DIR / "index.json").read_text())
files = R.render_studies(pages, pub, json.loads((site / R.NAV_FILE).read_text()), board)
for p in R.write(files, site, board["results_commit"], private, prune=False):
    print("wrote", p)
