#!/bin/sh
set -e
cd "$(dirname "$0")/.."
python3 sim/run_balance.py --phase item --item-iters 8 --item-fights 60 --procs 4
python3 sim/validate_battles.py --calibrate 4 --sample 240 --fights 12 --procs 4
python3 sim/report_md.py
python3 tools/export_md.py
python3 sim/fill_doc.py
echo FINISH_DONE
