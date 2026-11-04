#!/bin/sh
set -e
cd "$(dirname "$0")/.."
python3 sim/run_traits.py --iters 3 --fights 150 --procs 4
python3 sim/tune_bosses.py --rounds 4 --fights 16 --procs 4
python3 sim/validate_battles.py --calibrate 8 --sample 240 --fights 12 --procs 4
python3 sim/make_vectors.py
python3 sim/report_md.py
python3 tools/export_md.py
python3 sim/fill_doc.py
echo FOLLOWUP2_DONE
