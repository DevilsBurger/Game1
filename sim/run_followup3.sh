#!/bin/sh
set -e
cd "$(dirname "$0")/.."
python3 sim/tune_bosses.py --reset --rounds 6 --fights 24 --procs 4
python3 sim/run_context_items.py --per 10 --procs 4
python3 sim/make_vectors.py
python3 sim/report_md.py
python3 tools/export_md.py
python3 sim/fill_doc.py
echo FOLLOWUP3_DONE
