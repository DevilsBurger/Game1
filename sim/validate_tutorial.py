# -*- coding: utf-8 -*-
"""
FTUE 구간(1막 스토리 S001~S015) 검증 (20 문서 §5·§10).
플레이어 유닛 레온(P000, heroes.json player_unit)과 1막 영입 일정대로 늘어나는 기대 로스터(전원 ★1, 장비 없음)로 보통 난이도 승률을 측정한다.
S001·S002는 튜토리얼 보정(적 전력 ×0.85, FtueState 미완료 계정 한정) 유무를 비교한다.
출력: sim/reports/tutorial_validation.json + docs/20 §5 결과 블록(마커 사이) 갱신.
"""
import json, os, sys, random, argparse
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(__file__))
from engine import GameData, Battle
from scenario import build_scenario

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data")
REP = os.path.join(os.path.dirname(__file__), "reports")
DOC = os.path.join(ROOT, "docs", "20_FTUE_온보딩_설계.md")
ORDER = ["S%03d" % i for i in range(1, 16)]
ASSIST = {"S001": 0.85, "S002": 0.85}
TARGET = {"S001": 0.97, "S002": 0.95, "S003": 0.90, "S004": 0.85}
DEFAULT_TARGET = 0.75
# 전투 전 보유한 '추가 영웅' 수 (레온·브랜든 제외). 20 §10 영입 일정.
EXTRA_BEFORE = {"S001": 0, "S002": 0, "S003": 0, "S004": 0, "S005": 1, "S006": 1, "S007": 2, "S008": 2, "S009": 3, "S010": 4, "S011": 4, "S012": 4, "S013": 4, "S014": 5, "S015": 5}
_G = {}


def _init():
    battles = json.load(open(os.path.join(DATA, "battles.json"), encoding="utf-8"))
    econ = json.load(open(os.path.join(DATA, "economy.json"), encoding="utf-8"))
    _G["d"] = GameData(battles=battles)
    _G["b"] = {b["id"]: b for b in battles["battles"]}
    _G["curve"] = econ.get("enemy_power_curve", {})
    _G["econ"] = econ
    STORY_EXP.update(story_exp_table(_G["b"]))


ROLE_PRIORITY = ["knight", "priest", "guardian", "ranger", "mage", "warrior", "duelist", "assassin", "bard", "shaman", "artillerist", "summoner", "engineer", "dragoon"]
STORY_EXP = {}  # bid -> 누적 스토리 EXP (전투 전)


def story_exp_table(bmap):
    """1막 스토리 순서대로 '전투 전 누적 스토리 EXP'."""
    out, acc = {}, 0
    for bid in ORDER:
        out[bid] = acc; acc += bmap[bid]["difficulties"]["normal"]["rewards"]["exp"]
    return out


def extra_pool(d):
    """1막 조우·지역 드랍으로 얻을 법한 영웅: 아스텔·자유용병 계층 1 → 2, 역할 우선순위(전열·치유·원거리 순)로 정렬. 브랜든 제외."""
    cands = [h for h in d.heroes.values() if h["origin"] in ("astel", "freelancer") and h["tier"] <= 2 and h["id"] != "H009"]
    cands.sort(key=lambda h: (ROLE_PRIORITY.index(h["class"]) if h["class"] in ROLE_PRIORITY else 99, h["tier"], h["id"]))
    return [h["id"] for h in cands]


def expected_level(econ, exp_total):
    lvl = 1
    while lvl < 60 and exp_total >= econ["player_level_exp"][str(lvl)]:
        exp_total -= econ["player_level_exp"][str(lvl)]; lvl += 1
    return lvl


def ftue_team(d, b, econ, story_exp=None):
    """기대 팀: 로스터 = 레온 + 브랜든(S003~) + 영입 일정만큼의 추가 영웅. 인원 = clamp(max(레벨 슬롯, 최소 인원), 최소, 최대).
    레벨은 '스토리 1회당 지역·조우 2회'(누적 EXP ≈ 스토리 EXP × 3, 20 §4) 가정으로 추정."""
    bid = b["id"]
    roster = ["P000"] + (["H009"] if ORDER.index(bid) >= 2 else []) + extra_pool(d)[:EXTRA_BEFORE[bid]]
    p = b["participation"]
    if p["mode"] == "solo":
        return [d.hero_spec("P000", 1)], 1
    lvl = expected_level(econ, (story_exp or STORY_EXP)[bid] * 3)
    slots = econ["team_size_by_player_level"][str(min(60, lvl))]
    size = max(p["min"], min(p["max"], slots))
    team = (roster + [h for h in extra_pool(d) if h not in roster])[:size]
    return [d.hero_spec(h, 1) for h in team], lvl


def _run(args):
    bid, assist, seed = args
    d = _G["d"]; b = _G["b"][bid]
    rng = random.Random(seed)
    allies, enemies, rules = build_scenario(d, b, "normal", rng, curve=_G["curve"], allies=ftue_team(d, b, _G["econ"])[0])
    if assist:
        f = ASSIST[bid]
        def scale(units):
            out = []
            for u in units:
                u = dict(u)
                if not u.get("is_structure"):
                    u["hp"] *= f; u["ad"] *= f; u["ap"] *= f
                out.append(u)
            return out
        enemies = scale(enemies)
        if "waves" in rules: rules = dict(rules, waves=[scale(w) for w in rules["waves"]])
    r = Battle(d, allies, enemies, seed=seed, rules=rules).run()
    return bid, assist, (1 if r["winner"] == 0 else 0), r["time"]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--fights", type=int, default=200); ap.add_argument("--procs", type=int, default=4)
    args = ap.parse_args()
    jobs = []
    for bid in ORDER:
        variants = [False, True] if bid in ASSIST else [False]
        for a in variants:
            jobs += [(bid, a, 5000 + i) for i in range(args.fights)]
    res = {}
    with Pool(args.procs, initializer=_init) as pool:
        for bid, a, w, t in pool.imap_unordered(_run, jobs, chunksize=16):
            res.setdefault((bid, a), []).append((w, t))
    _init()
    d = _G["d"]
    rows = []
    for bid in ORDER:
        b = _G["b"][bid]
        specs, lvl = ftue_team(d, b, _G["econ"])
        team = [u["id"] for u in specs]
        base = res[(bid, False)]
        wr = sum(w for w, _ in base) / len(base); avg_t = sum(t for _, t in base) / len(base)
        row = {"id": bid, "name": b["name_ko"], "type": b["type_ko"], "mode": b["participation"]["name"], "level": b["level"], "player_level": lvl, "team": team,
               "win_rate": round(wr, 3), "avg_time": round(avg_t, 1), "target": TARGET.get(bid, DEFAULT_TARGET), "n": len(base)}
        if bid in ASSIST:
            ab = res[(bid, True)]
            row["win_rate_assist"] = round(sum(w for w, _ in ab) / len(ab), 3)
        row["ok"] = (row.get("win_rate_assist", row["win_rate"]) >= row["target"])
        rows.append(row)
    json.dump({"fights": args.fights, "assist": ASSIST, "rows": rows}, open(os.path.join(REP, "tutorial_validation.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    L = [f"(자동 생성: `python3 sim/validate_tutorial.py --fights {args.fights}`, 보통 난이도, 전원 ★1·장비 없음)", "",
         "| 전투 | 유형 · 참전 | 전투 레벨 | 기대 용병 레벨 → 참전 | 승률 | 보정(×0.85) 승률 | 목표 | 평균 시간 | 판정 |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['id']} {r['name']} | {r['type']} · {r['mode']} | {r['level']} | Lv{r['player_level']} → {len(r['team'])}명 | {r['win_rate']:.0%} | " +
                 (f"{r['win_rate_assist']:.0%}" if 'win_rate_assist' in r else "—") + f" | ≥ {r['target']:.0%} | {r['avg_time']:.1f}s | {'✅' if r['ok'] else '❌'} |")
    fails = [r for r in rows if not r["ok"]]
    L.append("")
    L.append("- 판정 요약: " + (f"목표 미달 {len(fails)}건 — " + ", ".join(f"{r['id']}({r.get('win_rate_assist', r['win_rate']):.0%}/≥{r['target']:.0%})" for r in fails) if fails else "전 구간 목표 충족."))
    block = "\n".join(L)
    doc = open(DOC, encoding="utf-8").read()
    s, e = "<!-- tutorial_validation:start -->", "<!-- tutorial_validation:end -->"
    i, j = doc.index(s) + len(s), doc.index(e)
    open(DOC, "w", encoding="utf-8").write(doc[:i] + "\n" + block + "\n" + doc[j:])
    for r in rows:
        print(r["id"], r["name"], f"Lv{r['player_level']}", len(r["team"]), r["team"], f"{r['win_rate']:.0%}", (f"assist {r['win_rate_assist']:.0%}" if 'win_rate_assist' in r else ""), "OK" if r["ok"] else "FAIL")


if __name__ == "__main__":
    main()
