#!/bin/sh
set -e
cd "$(dirname "$0")/.."
python3 sim/run_balance.py --phase item --item-iters 3 --item-fights 60 --procs 4
python3 sim/run_traits.py --iters 4 --fights 150 --procs 4
python3 sim/tune_bosses.py --rounds 8 --fights 48 --procs 4
python3 sim/run_context_items.py --per 8 --procs 4
python3 sim/make_vectors.py
python3 sim/report_md.py
python3 tools/export_md.py
python3 sim/fill_doc.py
echo FOLLOWUP5_DONE
