# -*- coding: utf-8 -*-
"""
스토리 대본 통합 → data/story_script.json, docs/16_스토리_대본.md
입력: tools/script_data_1.py, script_data_2.py (전투 전후 대화·컷신), tools/script_lines.py (영웅 영입·로비 대사), data/battles.json, data/heroes.json
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from script_data_1 import BATTLE_SCRIPTS as B1, CUTSCENES as C1
from script_data_2 import BATTLE_SCRIPTS as B2, CUTSCENES as C2
try:
    from script_lines import RECRUIT, LOBBY, EXTRA_SPEAKERS
except ImportError:
    RECRUIT, LOBBY, EXTRA_SPEAKERS = {}, {}, {}

ROOT = os.path.join(os.path.dirname(__file__), "..")
battles = json.load(open(os.path.join(ROOT, "data", "battles.json"), encoding="utf-8"))["battles"]
heroes = json.load(open(os.path.join(ROOT, "data", "heroes.json"), encoding="utf-8"))["heroes"]
story = [b for b in battles if b["kind"] == "story"]
scripts = {**B1, **B2}; cuts = {**C1, **C2}
HN = {h["name_ko"]: h["id"] for h in heroes}


def speaker_id(name):
    if name == "N": return "narration"
    if name == "레온": return "P000"
    if name == "엘리아": return "NPC_ELIA"
    if name in HN: return HN[name]
    return "NPC_" + str(abs(hash(name)) % 10**6)


def main():
    out = {"version": 1, "battles": [], "cutscenes": [], "recruit": [], "lobby": []}
    missing = []
    for b in story:
        sc = scripts.get(b["name_ko"])
        if not sc:
            missing.append(b["name_ko"]); continue
        out["battles"].append({"battle_id": b["id"], "name_ko": b["name_ko"], "act": b["act"],
                               "pre": [{"speaker": s, "speaker_id": speaker_id(s), "line": l} for s, l in sc["pre"]],
                               "post": [{"speaker": s, "speaker_id": speaker_id(s), "line": l} for s, l in sc["post"]],
                               "direction": sc.get("dir", "")})
    for cid, c in sorted(cuts.items()):
        out["cutscenes"].append({"id": cid, "title": c["title"], "shots": [{"visual": s["visual"], "lines": [{"speaker": sp, "speaker_id": speaker_id(sp), "line": l} for sp, l in s["text"]]} for s in c["shots"]]})
    for h in heroes:
        r = RECRUIT.get(h["name_ko"]); lo = LOBBY.get(h["name_ko"])
        out["recruit"].append({"hero_id": h["id"], "name_ko": h["name_ko"], "line": r or ""})
        out["lobby"].append({"hero_id": h["id"], "name_ko": h["name_ko"], "lines": lo or []})
    json.dump(out, open(os.path.join(ROOT, "data", "story_script.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 문서
    L = ["# 16. 스토리 대본", "", "자동 생성: `python tools/gen_story.py` (원본 `tools/script_data_1.py`, `script_data_2.py`, `script_lines.py`). 데이터: `data/story_script.json`.",
         "화자 규칙: 레온(과묵, 계약·약속의 언어), 카시안(냉소 + 온기, 아버지에 대한 양가감정), 엘리아(온기), 재의 장군들(스카르 조롱 / 베스카 냉정 / 이르자 광신 / 모르가스 충성), 바르그라드(고대적·비통·위압), N = 내레이션.",
         "연출 지시(dir)는 전투 유형·보스·영입 연출·컷신 연결을 명시한다. 전투 전 대화는 전투 정보 모달 → 편성 전에, 전투 후 대화는 결과 화면 직전에 재생한다(첫 클리어 시에만, 이후 스킵 가능).", ""]
    for act in range(1, 6):
        L += [f"## {act}막", ""]
        for s in out["battles"]:
            if s["act"] != act: continue
            L += [f"### {s['battle_id']} {s['name_ko']}", ""]
            if s["direction"]: L += [f"_연출: {s['direction']}_", ""]
            L += ["**전투 전**", ""]
            for x in s["pre"]: L.append(f"- {'(내레이션)' if x['speaker']=='N' else '**'+x['speaker']+'**'}: {x['line']}")
            L += ["", "**전투 후**", ""]
            for x in s["post"]: L.append(f"- {'(내레이션)' if x['speaker']=='N' else '**'+x['speaker']+'**'}: {x['line']}")
            L.append("")
        cs = [c for c in out["cutscenes"] if int(c["id"].split("-")[1]) in range(*{1: (0, 5), 2: (5, 13), 3: (13, 18), 4: (18, 21), 5: (21, 25)}[act])]
        if cs:
            L += [f"### {act}막 컷신", ""]
            for c in cs:
                L += [f"**{c['id']} {c['title']}**", ""]
                for i, sh in enumerate(c["shots"]):
                    L.append(f"- 샷 {i+1} · _{sh['visual']}_")
                    for x in sh["lines"]: L.append(f"  - {'(내레이션)' if x['speaker']=='N' else '**'+x['speaker']+'**'}: {x['line']}")
                L.append("")
    if RECRUIT:
        L += ["## 영웅 영입 대사 · 로비 터치 대사", "", "| 영웅 | 영입 대사 | 로비 대사 |", "|---|---|---|"]
        for r, lo in zip(out["recruit"], out["lobby"]):
            L.append(f"| {r['name_ko']} | {r['line']} | {' / '.join(lo['lines'])} |")
    open(os.path.join(ROOT, "docs", "16_스토리_대본.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    n_lines = sum(len(s["pre"]) + len(s["post"]) for s in out["battles"]) + sum(len(sh["lines"]) for c in out["cutscenes"] for sh in c["shots"])
    print(f"story battles scripted: {len(out['battles'])}/{len(story)}, cutscenes: {len(out['cutscenes'])}, dialogue lines: {n_lines}, recruit lines: {sum(1 for r in out['recruit'] if r['line'])}, missing: {missing}")


if __name__ == "__main__":
    main()
