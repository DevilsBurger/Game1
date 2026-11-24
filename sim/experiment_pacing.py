# -*- coding: utf-8 -*-
"""
진행 속도 조정안 실험(게임 데이터는 바꾸지 않는다). 경제 시뮬레이션에 가정만 바꿔 넣어 3프로필 × 12회 × 90일을 돌린다.
  python3 sim/experiment_pacing.py <이름> [m003cost=4,5,6,7,8] [shop=1] [drop=0.5] [calib=enemy_star|enemy_star_nm125] [radiant=0]
    m003cost: ★2→★3 별의 결정 수량(계층 1~5) / shop: 보급소 별의 결정 일일 한도 / drop: 별의 결정 확률 드랍 배율
    calib: 적 강화 가정으로 잰 전력 환산표(sim/calibrate_power.py --variant ...)
결과: sim/reports/pacing/<이름>.json
"""
import os
ROOT = os.path.dirname(os.path.abspath(__file__))
import sys, json, statistics
sys.path.insert(0, ROOT)
import run_economy as R
name = sys.argv[1]; opts = dict(a.split('=') for a in sys.argv[2:])
if 'm003cost' in opts:
    for t, v in zip('12345', opts['m003cost'].split(',')): R.E["star_up_cost"]["2_to_3"][t]["M003"] = int(v)
if 'shop' in opts: R.MAT_DAILY_LIMIT["M003"] = int(opts['shop'])
if 'drop' in opts: R.M003_DROP_SCALE = float(opts['drop'])
if opts.get('radiant') == '0': R.PRICE_RADIANT = 10 ** 12   # 빛나는 아이템 골드 구매 불가(드랍 전용) 가정
if 'calib' in opts:
    R.POWER_TABLE, R.ITEM_POWER_COMPLETED, R.ITEM_POWER_RADIANT, R.WIN_K = R.load_power_model(os.path.join(ROOT, 'reports', f'power_calibration_{opts["calib"]}.json'))
out = {'power_table': {d: [R.hero_power(t, s, d) for t in range(1, 6) for s in (1, 2, 3)] for d in R.POWER_TABLE}, 'items': [R.ITEM_POWER_COMPLETED, R.ITEM_POWER_RADIANT]}
for prof in R.PROFILES:
    runs = [R.simulate(prof, 90, s) for s in range(12)]
    m = lambda d, k: statistics.mean(r[0][d][k] for r in runs)
    acts = {}
    for r in runs:
        for day, ev in r[1]: acts.setdefault(ev, []).append(day)
    out[prof] = {str(d): dict(earn=m(d, 'gold_earned'), spent=m(d, 'gold_spent'), fac=m(d, 'facility_levels'), s3=m(d, 'star3'), s2=m(d, 'star2'), heroes=m(d, 'heroes'), power=m(d, 'power'), level=m(d, 'level'), wr=m(d, 'winrate'), m003=m(d, 'm003'),
                              nm=statistics.mean(r[0][d]['gold_by']['nightmare'] for r in runs) / max(1, m(d, 'gold_earned')), nmw=statistics.mean(r[0][d]['wins_by']['nightmare'] for r in runs) / max(1, statistics.mean(sum(r[0][d]['wins_by'].values()) for r in runs))) for d in (7, 30, 60, 90)}
    out[prof]['acts'] = {k: (round(statistics.mean(v), 1), len(v)) for k, v in acts.items()}
out['options'] = opts
os.makedirs(os.path.join(ROOT, 'reports', 'pacing'), exist_ok=True)
json.dump(out, open(os.path.join(ROOT, 'reports', 'pacing', f'{name}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
