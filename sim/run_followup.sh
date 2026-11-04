#!/bin/sh
# 후속 밸런스 파이프라인 (영웅 재수렴 이후). 4코어 약 20분.
set -e
cd "$(dirname "$0")/.."
python3 sim/run_balance.py --phase item --item-iters 3 --item-fights 60 --procs 4
python3 sim/run_traits.py --iters 3 --fights 120 --procs 4
python3 sim/run_item_combos.py --pairs 240 --triples 120 --per 4 --procs 4
python3 sim/run_context_items.py --per 10 --procs 4
python3 sim/tune_bosses.py --rounds 3 --fights 16 --procs 4
python3 sim/validate_battles.py --calibrate 8 --sample 240 --fights 12 --procs 4
python3 sim/make_vectors.py
python3 sim/report_md.py
python3 tools/export_md.py
python3 sim/fill_doc.py
echo FOLLOWUP_DONE
