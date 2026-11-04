#!/bin/sh
# 전체 밸런스 파이프라인 (4코어 기준 약 25분)
set -e
cd "$(dirname "$0")/.."
python3 sim/run_balance.py --phase hero --iters 14 --appearances 500 --procs 4
python3 sim/run_balance.py --phase hero --iters 6 --appearances 1200 --exp 0.3 --clamp 0.08 --procs 4
python3 sim/run_balance.py --phase item --item-iters 4 --item-fights 40 --procs 4
python3 sim/validate_battles.py --calibrate 4 --sample 240 --fights 12 --procs 4
python3 sim/report_md.py
python3 tools/export_md.py
echo PIPELINE_DONE
