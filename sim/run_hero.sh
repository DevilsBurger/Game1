#!/bin/sh
set -e
cd "$(dirname "$0")/.."
python3 sim/run_balance.py --phase hero --iters 14 --appearances 500 --procs 4
python3 sim/run_balance.py --phase hero --iters 6 --appearances 1200 --exp 0.3 --clamp 0.08 --procs 4
echo HERO_DONE
