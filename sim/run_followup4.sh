#!/bin/sh
set -e
cd "$(dirname "$0")/.."
python3 sim/run_traits.py --iters 4 --fights 150 --procs 4
python3 sim/tune_bosses.py --rounds 6 --fights 32 --procs 4
python3 sim/make_vectors.py
python3 sim/report_md.py
python3 tools/export_md.py
python3 sim/fill_doc.py
echo FOLLOWUP4_DONE
