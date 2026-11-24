# -*- coding: utf-8 -*-
"""
경제 진행 시뮬레이션: 가상 플레이어(무과금/소과금/헤비) 90일 몬테카를로.
모델:
  - 하루 세션: 프로필별 목표 참전 횟수. 영웅별 스태미너 100, 6분당 1 회복(하루 240), 참전 시 영웅당 난이도별 소모(웨이브형 ×1.5).
  - 전투 선택: 현재 '전력 레벨'(보유 상위 팀의 계층·성급) 근처의 지역/조우/스토리 전투. 난이도는 전력 여유에 따라 보통/어려움/악몽.
    승률 = 로지스틱((난이도별 전력 − 전투 레벨) / 기울기) (여유 0 → 76%). 전력 환산표·기울기는 실제 엔진 측정값(calibrate_power.py).
  - 보상: economy.json 공식(골드·재료·아이템 드랍·영웅 드랍·호감도 천장). 중복 영웅 → 파편.
  - 지출(07 §2.2의 골드 소비처 전부): 승급 골드, 부족 재료 상점 구매(일일 한도 M001 200/M002 20/M003 2), 조합 아이템(주력 팀 슬롯분)·빛나는 아이템 교체,
    골드 소모품(조우 서약서·매력 징표). 보석은 프로필별(물약·계층 4·5 조우 고급 서약서).
출력: sim/reports/economy_sim.json, docs/07 §9 자동 삽입
"""
import json, os, sys, random, statistics, math
ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data"); REP = os.path.join(os.path.dirname(__file__), "reports")
E = json.load(open(os.path.join(DATA, "economy.json"), encoding="utf-8"))
HEROES = json.load(open(os.path.join(DATA, "heroes.json"), encoding="utf-8"))["heroes"]
TIER_OF = {h["id"]: h["tier"] for h in HEROES}
BATTLES = [b for b in json.load(open(os.path.join(DATA, "battles.json"), encoding="utf-8"))["battles"] if b["kind"] in ("regional", "encounter", "story")]
PROFILES = {
    "free":  dict(name="무과금", battles_per_day=25, gems_per_month=0, pass_=False, potion_gems_cap=0, pact_on_t45=False),
    "light": dict(name="소과금(월 1,000보석+월정액)", battles_per_day=35, gems_per_month=1000, pass_=True, potion_gems_cap=200, pact_on_t45=True),
    "heavy": dict(name="헤비(월 10,000보석+월정액)", battles_per_day=60, gems_per_month=10000, pass_=True, potion_gems_cap=3000, pact_on_t45=True),
}
_ITEMS = {i["id"]: i for i in json.load(open(os.path.join(DATA, "items.json"), encoding="utf-8"))["items"]}
MAT_PRICE = {m: _ITEMS[m]["price_gold"] for m in ("M001", "M002", "M003")}
MAT_DAILY_LIMIT = {"M001": 200, "M002": 20, "M003": 2}   # 07 §1, 21 §5
PRICE_COMPLETED = next(i["price_gold"] for i in _ITEMS.values() if i["category"] == "completed")
PACT_GOLD = [(_ITEMS["X006"]["price_gold"], _ITEMS["X006"]["effect"]["hero_drop_mult"]), (_ITEMS["X005"]["price_gold"], _ITEMS["X005"]["effect"]["hero_drop_mult"])]
TOKEN_GOLD = _ITEMS["X008"]["price_gold"]; TOKEN_AFFINITY = _ITEMS["X008"]["effect"]["affinity"]; TOKENS_PER_DAY = 4
FAC = E["facilities"]; FAC_COST = {int(k): v for k, v in FAC["cost_by_level"].items()}; FAC_KEYS = [f["key"] for f in FAC["list"]]
FAC_BY_KEY = {f["key"]: f for f in FAC["list"]}
DECAY_STEPS = sorted(E["repeat_gold_decay"]["steps"], key=lambda x: -x["from_win"])
POTION_GOLD = _ITEMS["X003"]["price_gold"]; POTION_STAMINA = _ITEMS["X003"]["effect"]["stamina"]; POTION_GOLD_LIMIT = E["stamina"]["gold_potion_daily_limit"]
GIFT_BUDGET_SHARE = 0.25   # 보유 영웅 호감도 선물: 승급·시설 뒤 남은 골드의 이 비율까지
FACILITY_BUDGET_SHARE = 0.6
GOLD_SCALE = {"normal": 1.0, "hard": 1.0, "nightmare": 1.0}   # 난이도별 골드 보상 가정 실험용 배율(기본 1.0 = battles.json 그대로)
DAILY_GOLD_SOFTCAP = None   # 실험용: 하루 전투 골드가 (한도, 배율)의 한도를 넘으면 초과분에 배율 적용. None = 미적용(현재 규칙)
GOLD_RESERVE = 3000   # 소모품은 이만큼의 여유 골드가 있을 때만 산다(승급·아이템 우선)
# 전력 = '승률 76%가 되는 전투 레벨'. 실제 전투 엔진 측정값(sim/calibrate_power.py → reports/power_calibration.json)을 그대로 쓴다.
#   난이도별 (계층, 성급) 표, 조합·빛나는 아이템 3슬롯 장착 보정, 로지스틱 기울기. 몬스터 전력 보정 곡선을 바꾸면 calibrate_power.py를 다시 돌려야 한다.
WIN_BASE = math.log(0.76 / 0.24)   # 여유 0 → 76%
PRICE_RADIANT = next(i["price_gold"] for i in _ITEMS.values() if i["category"] == "radiant")
RADIANT_UNLOCK_ACT = 1    # 실험용: 빛나는 아이템 골드 구매가 열리는 막(기본 1 = 처음부터)
RADIANT_DAILY_LIMIT = None   # 실험용: 빛나는 아이템 하루 구매 한도(기본 없음)
M003_DROP_SCALE = 1.0   # 실험용: 별의 결정 확률 드랍 배율(기본 1.0)


def load_power_model(path):
    """power_calibration*.json → (난이도별 {(계층, 성급): 전력}, 조합 아이템 보정, 빛나는 아이템 보정, 기울기).
    측정 범위(레벨 95) 밖이라 null인 칸은 난이도별 '계층 효과 + 성급 효과' 가법 모형(교대 최소제곱)의 외삽값으로 채운다."""
    C = json.load(open(path, encoding="utf-8"))["configs"]
    table = {}
    for d in ("normal", "hard", "nightmare"):
        cells = {(t, st): C[f"t{t}_s{st}_none_{d}"]["L76"] for t in range(1, 6) for st in (1, 2, 3)}
        meas = {k: v for k, v in cells.items() if v is not None}
        tt = {t: 0.0 for t in range(1, 6)}; ss = {1: 0.0, 2: 0.0, 3: 0.0}
        for _ in range(200):
            for t in tt:
                v = [meas[(t, x)] - ss[x] for x in ss if (t, x) in meas]; tt[t] = statistics.mean(v) if v else tt[t]
            for x in ss:
                v = [meas[(t, x)] - tt[t] for t in tt if (t, x) in meas]; ss[x] = statistics.mean(v) if v else ss[x]
        table[d] = {k: (meas[k] if k in meas else tt[k[0]] + ss[k[1]]) for k in cells}
    def bonus(kind):
        v = [C[f"t{t}_s{st}_{kind}_normal"]["L76"] - C[f"t{t}_s{st}_none_normal"]["L76"] for t in range(1, 6) for st in (1, 2, 3)
             if C[f"t{t}_s{st}_{kind}_normal"]["L76"] is not None and C[f"t{t}_s{st}_none_normal"]["L76"] is not None]
        return statistics.mean(v)
    ks = sorted(v["k"] for v in C.values() if v["k"] is not None and v["items"] == "none")
    return table, bonus("completed"), bonus("radiant"), ks[len(ks) // 2]


POWER_TABLE, ITEM_POWER_COMPLETED, ITEM_POWER_RADIANT, WIN_K = load_power_model(os.path.join(REP, "power_calibration.json"))


def hero_power(tier, star, diff="normal"):
    return POWER_TABLE[diff][(tier, star)]


class Player:
    def __init__(self, profile, rng):
        self.p = PROFILES[profile]; self.rng = rng
        self.gold = 500; self.gems = 100; self.mats = {"M001": 0, "M002": 0, "M003": 0}
        self.owned = {}   # hero_id -> star
        self.stamina = {}  # hero_id -> stamina
        self.affinity = {}
        self.items = {"component": 0, "completed": 0, "support": 0, "artifact": 0, "national": 0, "radiant": 0}
        self.level = 1; self.exp = 0; self.cleared = set(); self.act = 1
        self.log = []
        # 시작: 레온 + 1막 스토리 보상 2명(브랜든·마리엘 상당) 대신 계층1 영웅 2명
        for h in [x for x in HEROES if x["tier"] == 1][:2]: self.add_hero(h["id"])
        self.exp_total = 0
        self.gold_by = {}; self.wins_by = {}; self.gold_today = 0; self.gold_capped = 0
        self.fac = {k: 0 for k in FAC_KEYS}; self.wins_today = {}; self.gold_potions_today = 0; self.gold_decayed = 0; self.gifted_full = 0
        self.spent = {"star": 0, "items": 0, "mats": 0, "consumables": 0, "facilities": 0, "gifts": 0}; self.equipped_radiant = 0; self.tokens_today = 0
        self.gems_spent = 0; self.gold_earned = 0; self.gold_spent = 0; self.stamina_blocked_days = 0; self.battles_fought = 0; self.wins = 0; self.rotations = 0

    def add_hero(self, hid):
        if hid in self.owned:
            t = TIER_OF[hid]
            self.mats["M001"] += E["duplicate_hero_conversion"]["M001_by_tier"][str(t)]; self.affinity[hid] = self.affinity.get(hid, 0) + E["duplicate_hero_conversion"]["affinity"]
            return False
        self.owned[hid] = 1; self.stamina[hid] = 100; return True

    def team_slots(self): return E["team_size_by_player_level"][str(min(60, self.level))]

    def power_level(self, team=None, diff="normal"):
        """전력 레벨: 실제 출전 팀(미지정 시 최강 팀)의 평균 전력 + 인원·아이템 보정. 로테이션(약한 영웅 출전)은 승률 손실로 나타난다."""
        if team is None:
            pw = sorted([hero_power(TIER_OF[hid], st, diff) for hid, st in self.owned.items()], reverse=True)
            team_pw = pw[:max(1, min(self.team_slots(), len(pw)))]
        else:
            team_pw = [hero_power(TIER_OF[hid], self.owned[hid], diff) for hid in team]
        # 레온: 계층 3 상당, 스토리로 승급(2막 클리어 ★2, 4막 클리어 ★3 — 03 §5)
        team_pw = team_pw + [hero_power(3, 3 if self.act >= 5 else 2 if self.act >= 3 else 1, diff)]
        # 아이템: 장착 슬롯(영웅당 3) 기준. 빛나는 아이템이 먼저 슬롯을 차지하고 나머지를 조합 아이템이 채운다
        slots = 3 * len(team_pw)
        rad = min(self.items.get("radiant", 0), slots); comp = min(self.items["completed"], slots - rad)
        return statistics.mean(team_pw) + (ITEM_POWER_RADIANT * rad + ITEM_POWER_COMPLETED * comp) / slots

    def pick_battle(self):
        pl = self.power_level()
        cands = [b for b in BATTLES if b["act"] <= self.act and b["level"] <= pl + 2 * WIN_K]
        if not cands: cands = [b for b in BATTLES if b["act"] <= self.act]
        enc = [b for b in cands if b["kind"] == "encounter" and b["hero_id"] not in self.owned and b["level"] <= pl + WIN_K]
        story = [b for b in cands if b["kind"] == "story" and b["id"] not in self.cleared and b["level"] <= pl + 1.33 * WIN_K]
        reg = [b for b in cands if b["kind"] == "regional"]
        r = self.rng.random()
        if story and r < 0.25: return self.rng.choice(story)
        if enc and r < 0.6: return self.rng.choice(sorted(enc, key=lambda b: -b["level"])[:12])
        return self.rng.choice(sorted(reg, key=lambda b: -b["level"])[:30]) if reg else self.rng.choice(cands)

    def choose_difficulty(self, b):
        for diff in ("nightmare", "hard"):
            if self.power_level(None, diff) >= b["level"]: return diff
        return "normal"

    def win_prob(self, b, diff, team=None):
        margin = self.power_level(team, diff) - b["level"]
        return 1 / (1 + math.exp(-(margin / WIN_K + WIN_BASE)))   # margin 0 → 76%

    def fac_bonus(self, key):
        f = FAC_BY_KEY[key]; lv = self.fac[key]
        if "per_level" in f: return f["per_level"] * lv
        return max([v for k, v in f["milestones"].items() if int(k) <= lv and isinstance(v, (int, float))] or [0])

    def day(self, day_idx):
        p = self.p
        self.wins_today = {}; self.gold_potions_today = 0; self.gold_today = 0
        for hid in self.stamina: self.stamina[hid] = min(100, self.stamina[hid] + (240 * (1.5 if p["pass_"] else 1.0)) / 1)
        if day_idx % 30 == 0: self.gems += p["gems_per_month"] + (30 * 50 if p["pass_"] else 0)
        fought = 0; blocked = False
        for _ in range(p["battles_per_day"]):
            b = self.pick_battle(); diff = self.choose_difficulty(b)
            cost = b["difficulties"][diff]["stamina_per_hero"]
            n = max(b["participation"]["min"], min(b["participation"]["max"], self.team_slots()))
            ready = sorted([h for h, s in self.stamina.items() if s >= cost], key=lambda h: -hero_power(TIER_OF[h], self.owned[h]))
            best = sorted(self.stamina, key=lambda h: -hero_power(TIER_OF[h], self.owned[h]))[:n]
            # 골드 물약(일일 한도): 주력 영웅의 스태미너가 모자라면 여유 골드로 보충
            for h in best:
                if self.stamina[h] < cost and self.gold_potions_today < POTION_GOLD_LIMIT and self.gold >= GOLD_RESERVE + POTION_GOLD:
                    self.pay(POTION_GOLD, "consumables"); self.gold_potions_today += 1; self.stamina[h] = min(100, self.stamina[h] + POTION_STAMINA)
            if any(self.stamina[h] < cost for h in best): self.rotations += 1
            ready = sorted([h for h, s in self.stamina.items() if s >= cost], key=lambda h: -hero_power(TIER_OF[h], self.owned[h]))
            if len(ready) < min(n, 1):
                # 물약으로 보충 (보석)
                if p["potion_gems_cap"] and self.gems >= 22 and self.gems_spent_today < p["potion_gems_cap"] / 30:
                    self.gems -= 22; self.gems_spent += 22; self.gems_spent_today += 22
                    for h in list(self.stamina)[:1]: self.stamina[h] = min(100, self.stamina[h] + 50)
                    continue
                blocked = True; break
            team = ready[:n]
            for h in team: self.stamina[h] -= cost
            self.battles_fought += 1; fought += 1
            won = self.rng.random() < self.win_prob(b, diff, team)
            if not won:
                for h in team: self.stamina[h] += cost * 0.5
                continue
            self.wins += 1
            rw = b["difficulties"][diff]["rewards"]
            # 반복 클리어 골드 체감(같은 전투의 당일 N번째 승리)
            nth = self.wins_today.get(b["id"], 0) + 1; self.wins_today[b["id"]] = nth
            mult = next((st["gold_mult"] for st in DECAY_STEPS if nth >= st["from_win"]), 1.0)
            base_gold = rw["gold"] * GOLD_SCALE[diff]
            gold = int(base_gold * mult); self.gold_decayed += int(base_gold) - gold
            if DAILY_GOLD_SOFTCAP is not None:
                cap, cmult = DAILY_GOLD_SOFTCAP
                over = max(0, self.gold_today + gold - cap) if self.gold_today < cap else gold
                cut = int(over * (1 - cmult)); gold -= cut; self.gold_capped += cut
            self.gold_today += gold
            self.gold += gold; self.gold_earned += gold; self.gold_by[diff] = self.gold_by.get(diff, 0) + gold; self.wins_by[diff] = self.wins_by.get(diff, 0) + 1
            exp = int(rw["exp"] * (1 + self.fac_bonus("training_ground") / 100.0))
            self.exp += exp; self.exp_total += exp
            while self.level < 60 and self.exp >= E["player_level_exp"][str(self.level)]:
                self.exp -= E["player_level_exp"][str(self.level)]; self.level += 1
                for h in self.stamina: self.stamina[h] = 100
            for k, v in rw["materials"].items():
                if k.endswith("_chance"):
                    if self.rng.random() * 100 < v["pct"] * (M003_DROP_SCALE if k.startswith("M003") else 1.0): self.mats[k.split("_")[0]] += v["qty"]
                else: self.mats[k] += v
            for it in rw["items"]:
                if self.rng.random() * 100 < it["chance_pct"]: self.items[it["pool"]] = self.items.get(it["pool"], 0) + it["qty"]
            if b["id"] not in self.cleared:
                self.cleared.add(b["id"]); fc = b["difficulties"].get("first_clear_bonus", {})
                self.gold += fc.get("gold", 0); self.gold_earned += fc.get("gold", 0); self.gold_by["first_clear"] = self.gold_by.get("first_clear", 0) + fc.get("gold", 0); self.gems += fc.get("gems", 0)
                for k, v in fc.get("materials", {}).items(): self.mats[k] += v
                if fc.get("hero_guaranteed"): self.add_hero(fc["hero_guaranteed"]["hero_id"])
                if b["kind"] == "story" and b.get("story_order"):
                    last_of_act = max(x["story_order"] for x in BATTLES if x["kind"] == "story" and x["act"] == b["act"])
                    if b["story_order"] == last_of_act and self.act < 5: self.act += 1; self.log.append((day_idx, f"act{self.act}"))
            hd = rw.get("hero_drop")
            if hd:
                if "hero_id" in hd:
                    hid = hd["hero_id"]; tier = hd["tier"]; chance = hd["chance_pct"]
                    if p["pact_on_t45"] and tier >= 4 and self.gems >= 60: self.gems -= 60; self.gems_spent += 60; chance = min(90, chance * 2)
                    elif hid not in self.owned and tier >= 3 and self.affinity.get(hid, 0) < 100:
                        # 골드 서약서(07 §4): 여유 골드가 있으면 계층 3 이상 조우에 고급 → 일반 순으로 사용
                        for price, mult in PACT_GOLD:
                            if self.gold >= GOLD_RESERVE + price * 4:
                                self.pay(price, "consumables"); chance = min(E["hero_drop_cap_pct"], chance * mult); break
                    if self.affinity.get(hid, 0) >= 100 or self.rng.random() * 100 < chance:
                        if self.add_hero(hid): self.affinity[hid] = 0
                    else:
                        self.affinity[hid] = self.affinity.get(hid, 0) + E["affinity_pity"]["per_failed_encounter"][str(tier)] + self.fac_bonus("banquet_hall")
                        # 매력 징표(골드): 계층 4·5 조우 실패 시 천장까지의 거리를 줄인다
                        while tier >= 4 and self.tokens_today < TOKENS_PER_DAY and self.affinity[hid] < 100 and self.gold >= GOLD_RESERVE + TOKEN_GOLD * 6:
                            self.pay(TOKEN_GOLD, "consumables"); self.affinity[hid] += TOKEN_AFFINITY; self.tokens_today += 1
                elif hd.get("pool") == "native_random" and self.rng.random() * 100 < hd["chance_pct"]:
                    self.add_hero(self.rng.choice(hd["hero_ids"]))
        if blocked: self.stamina_blocked_days += 1
        self.spend()
        return fought

    def pay(self, gold, cat):
        self.gold -= gold; self.gold_spent += gold; self.spent[cat] += gold

    def spend(self):
        self.tokens_today = 0
        # 승급. 부족한 재료는 보급소에서 일일 한도 내로 구매(07 §1), 하루 한도로 못 채우면 여러 날에 걸쳐 비축
        bought = {"M001": 0, "M002": 0, "M003": 0}
        dep = 1 + self.fac_bonus("supply_depot") / 100.0
        limit = {m: int(MAT_DAILY_LIMIT[m] * (dep if m in FAC_BY_KEY["supply_depot"]["applies_to"] else 1)) for m in MAT_DAILY_LIMIT}

        def try_up(hid, stockpile):
            st = self.owned[hid]; cost = E["star_up_cost"]["1_to_2" if st == 1 else "2_to_3"][str(TIER_OF[hid])]
            need = {m: max(0, cost[m] - self.mats[m]) for m in bought}
            if any(need[m] > limit[m] - bought[m] for m in bought) or self.gold < cost["gold"] + sum(need[m] * MAT_PRICE[m] for m in bought):
                if stockpile:
                    for m in bought:
                        q = min(need[m], limit[m] - bought[m], int(max(0, self.gold - cost["gold"]) // MAT_PRICE[m]))
                        if q > 0: bought[m] += q; self.mats[m] += q; self.pay(q * MAT_PRICE[m], "mats")
                return False
            for m in bought:
                if need[m]: self.pay(need[m] * MAT_PRICE[m], "mats")
                bought[m] += need[m]; self.mats[m] += need[m] - cost[m]
            self.pay(cost["gold"], "star"); self.owned[hid] = st + 1
            return True

        # ① ★1 → ★2 (별의 결정 불필요): 전력 큰 영웅부터, 첫 번째로 막힌 영웅의 재료만 비축
        first_block = True
        for hid in sorted((h for h, st in self.owned.items() if st == 1), key=lambda h: -TIER_OF[h]):
            if not try_up(hid, first_block): first_block = False
        # ② ★2 → ★3: 별의 결정 1개당 주력 팀 전력 이득이 가장 큰 영웅을 목표로 삼고, 살 수 있을 때까지 결정을 그 영웅 몫으로 남겨 둔다.
        #    주력 팀에 더 올릴 영웅이 없으면(이득 0) 결정이 적게 드는 영웅부터 수집용으로 올린다.
        n = self.team_slots()
        while True:
            cands = [h for h, st in self.owned.items() if st == 2]
            if not cands: break
            top = sorted((hero_power(TIER_OF[h], st) for h, st in self.owned.items()), reverse=True)[:n]
            floor = top[-1] if len(top) >= n else 0.0

            def gain(h):
                cur = hero_power(TIER_OF[h], 2); post = hero_power(TIER_OF[h], 3)
                return max(0.0, post - max(cur, floor)) / max(1, E["star_up_cost"]["2_to_3"][str(TIER_OF[h])]["M003"])
            target = max(cands, key=lambda h: (gain(h), -E["star_up_cost"]["2_to_3"][str(TIER_OF[h])]["M003"], h))
            if not try_up(target, True): break
        # 아이템: 남은 골드의 35% 예산. 조합 아이템으로 주력 팀 슬롯(영웅당 3, 레온 포함)을 채운 뒤 빛나는 아이템으로 교체
        budget = self.gold * 0.35
        slots = 3 * (self.team_slots() + 1)
        while budget >= PRICE_COMPLETED and self.items["completed"] + self.items.get("radiant", 0) < slots:
            self.pay(PRICE_COMPLETED, "items"); budget -= PRICE_COMPLETED; self.items["completed"] += 1
        bought_rad = 0
        while (self.act >= RADIANT_UNLOCK_ACT and (RADIANT_DAILY_LIMIT is None or bought_rad < RADIANT_DAILY_LIMIT) and budget >= PRICE_RADIANT
               and self.items["completed"] + self.items.get("radiant", 0) >= slots and self.items.get("radiant", 0) < slots):
            self.pay(PRICE_RADIANT, "items"); budget -= PRICE_RADIANT; self.items["radiant"] = self.items.get("radiant", 0) + 1; bought_rad += 1
        # 용병단 본부 시설(2막부터): 승급·아이템 뒤 남은 골드의 일부로 가장 싼 다음 단계부터
        if self.act >= 2:
            budget = max(0, self.gold - GOLD_RESERVE) * FACILITY_BUDGET_SHARE
            while True:
                opts = sorted((FAC_COST[self.fac[k] + 1], i, k) for i, k in enumerate(FAC_KEYS) if self.fac[k] < FAC["max_level"])
                if not opts or opts[0][0] > budget: break
                c, _, k = opts[0]; self.pay(c, "facilities"); budget -= c; self.fac[k] += 1
        # 보유 영웅 호감도 선물(매력 징표, 100까지 — 전용 대사·초상 테두리)
        budget = max(0, self.gold - GOLD_RESERVE) * GIFT_BUDGET_SHARE
        cap = E["affinity_owned"]["cosmetic_unlock_at"]
        for hid in sorted(self.owned, key=lambda h: -hero_power(TIER_OF[h], self.owned[h])):
            while self.affinity.get(hid, 0) < cap and budget >= TOKEN_GOLD:
                self.pay(TOKEN_GOLD, "gifts"); budget -= TOKEN_GOLD; self.affinity[hid] = self.affinity.get(hid, 0) + TOKEN_AFFINITY
                if self.affinity[hid] >= cap: self.gifted_full += 1
            if budget < TOKEN_GOLD: break


def simulate(profile, days=90, seed=0):
    rng = random.Random(seed); pl = Player(profile, rng); pl.gems_spent_today = 0
    snaps = {}
    for d in range(1, days + 1):
        pl.gems_spent_today = 0
        pl.day(d)
        if d in (7, 30, 60, 90):
            tiers = {t: sum(1 for h, s in pl.owned.items() if TIER_OF[h] == t) for t in range(1, 6)}
            snaps[d] = dict(heroes=len(pl.owned), by_tier=tiers, star2=sum(1 for s in pl.owned.values() if s >= 2), star3=sum(1 for s in pl.owned.values() if s == 3),
                            power=round(pl.power_level(), 1), act=pl.act, level=pl.level, gold=int(pl.gold), gold_earned=int(pl.gold_earned), gold_spent=int(pl.gold_spent), spent_star=pl.spent["star"], spent_items=pl.spent["items"], spent_mats=pl.spent["mats"], spent_consumables=pl.spent["consumables"], spent_facilities=pl.spent["facilities"], spent_gifts=pl.spent["gifts"], facility_levels=sum(pl.fac.values()), gold_decayed=int(pl.gold_decayed), radiant=pl.items.get("radiant", 0), gold_by=dict({"normal": 0, "hard": 0, "nightmare": 0, "first_clear": 0}, **pl.gold_by), wins_by=dict({"normal": 0, "hard": 0, "nightmare": 0}, **pl.wins_by), gifted_full=pl.gifted_full, exp_total=pl.exp_total, gold_capped=int(pl.gold_capped),
                            gems_spent=pl.gems_spent, items_completed=pl.items["completed"], artifacts=pl.items["artifact"], battles=pl.battles_fought, winrate=round(pl.wins / max(1, pl.battles_fought), 3),
                            stamina_blocked_days=pl.stamina_blocked_days, rotation_rate=round(pl.rotations / max(1, pl.battles_fought), 3), cleared=len(pl.cleared), m001=pl.mats["M001"], m002=pl.mats["M002"], m003=pl.mats["M003"])
    return snaps, pl.log


def main():
    out = {}
    for prof in PROFILES:
        runs = [simulate(prof, 90, s) for s in range(12)]
        agg = {}
        for d in (7, 30, 60, 90):
            keys = runs[0][0][d].keys()
            agg[d] = {k: (round(statistics.mean(r[0][d][k] for r in runs), 1) if not isinstance(runs[0][0][d][k], dict) else {t: round(statistics.mean(r[0][d][k][t] for r in runs), 1) for t in runs[0][0][d][k]}) for k in keys}
        acts = {}
        for r in runs:
            for day, ev in r[1]: acts.setdefault(ev, []).append(day)
        out[prof] = {"profile": PROFILES[prof]["name"], "snapshots": agg, "act_reach_day_mean": {k: round(statistics.mean(v), 1) for k, v in acts.items()}}
        print(prof, {d: (agg[d]["heroes"], agg[d]["power"], agg[d]["act"], agg[d]["gold_earned"], agg[d]["stamina_blocked_days"]) for d in agg}, out[prof]["act_reach_day_mean"])
    os.makedirs(REP, exist_ok=True)
    json.dump(out, open(os.path.join(REP, "economy_sim.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 07 문서 삽입
    doc = os.path.join(ROOT, "docs", "07_경제_및_비즈니스모델.md")
    s = open(doc, encoding="utf-8").read()
    L = ["## 9. 경제 진행 시뮬레이션 결과 (자동 생성: `python sim/run_economy.py`)", "",
         "가상 플레이어 3프로필 × 12회 × 90일 몬테카를로. 전력은 '승률 76%가 되는 전투 레벨'로 환산하며 실제 전투 엔진 측정표를 쓴다(`sim/calibrate_power.py` → `sim/reports/power_calibration.json`: 난이도별 계층×성급 표, 아이템 보정, 기울기). 보상·드랍·호감도·승급·구매는 `economy.json`·`battles.json`·`items.json` 규칙 그대로.",
         "골드 지출은 승급 골드, 부족 재료의 보급소 구매(일일 한도 M001 200 / M002 20 / M003 2), 조합 아이템(주력 팀 슬롯분)과 빛나는 아이템 교체, 골드 서약서(계층 3 이상 조우)·매력 징표(계층 4·5, 일 4개), 골드 물약(일 3회 한도), 용병단 본부 시설, 보유 영웅 호감도 선물을 모두 포함한다. 반복 클리어 골드 체감을 적용한다. '누적 골드'는 첫 클리어 보너스를 포함한 총수입이다.", "",
         "| 프로필 | 일차 | 보유 영웅 | T4/T5 | ★2 이상 | 전력 | 막 | 용병 레벨 | 누적 골드 | 누적 지출 | 소진율 | 보석 지출 | 조합 아이템 | 클리어 전투 | 승률 | 최강팀 스태미너 소진 비율 | 참전 불가일 |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for prof, r in out.items():
        for d, s_ in r["snapshots"].items():
            L.append(f"| {r['profile']} | {d} | {s_['heroes']:.0f} | {s_['by_tier'][4]:.0f}/{s_['by_tier'][5]:.0f} | {s_['star2']:.0f} | {s_['power']:.0f} | {s_['act']:.1f} | {s_['level']:.0f} | {s_['gold_earned']:,.0f} | {s_['gold_spent']:,.0f} | {s_['gold_spent'] / max(1, s_['gold_earned']):.0%} | {s_['gems_spent']:,.0f} | {s_['items_completed']:.0f} | {s_['cleared']:.0f} | {s_['winrate']:.0%} | {s_['rotation_rate']:.0%} | {s_['stamina_blocked_days']:.0f} |")
    L += ["", "막 도달 평균 일차: " + "; ".join(f"{r['profile']}: " + ", ".join(f"{k} {v}일" for k, v in r["act_reach_day_mean"].items()) for r in out.values()), ""]
    f90 = out["free"]["snapshots"][90]; h90 = out["heavy"]["snapshots"][90]
    L += ["해석:",
          f"- 무과금 90일: 영웅 {f90['heroes']:.0f}명(196명 중 {f90['heroes']/196:.0%}), 전력 {f90['power']:.0f}, {f90['act']:.1f}막. 헤비 90일: {h90['heroes']:.0f}명({h90['heroes']/196:.0%}), 전력 {h90['power']:.0f}. 과금은 '수집 속도'를 사지 전력 상한을 사지 않는다(같은 전투는 같은 영웅으로 같은 승률).",
          f"- 스태미너: 최강 팀이 소진되어 약한 영웅으로 로테이션한 참전 비율 무과금 {f90['rotation_rate']:.0%}(승률 손실로 작용), 참전 자체가 불가능했던 날 {f90['stamina_blocked_days']:.0f}/90일. 스태미너는 '참전 횟수'가 아니라 '최강 팀 사용 횟수'를 제한한다 — 물약·월정액의 가치는 여기서 나온다(07 §3).",
          ]
    def ratio(k, d): return out[k]["snapshots"][d]["gold_spent"] / max(1, out[k]["snapshots"][d]["gold_earned"])
    tot = max(1, f90["gold_spent"])
    L += ["- 골드 소진율(누적 지출/누적 수입, 수입에 첫 클리어 보너스 포함): " + "; ".join(f"{out[k]['profile'].split('(')[0]} 30일 {ratio(k, 30):.0%} · 60일 {ratio(k, 60):.0%} · 90일 {ratio(k, 90):.0%}" for k in ("free", "light", "heavy"))
          + f". 무과금 90일 지출 구성은 승급 골드 {f90['spent_star']/tot:.0%}, 재료 구매 {f90['spent_mats']/tot:.0%}, 골드 소모품(서약서·징표·물약) {f90['spent_consumables']/tot:.0%}, 본부 시설 {f90['spent_facilities']/tot:.0%}, 호감도 선물 {f90['spent_gifts']/tot:.0%}, 아이템(조합·빛나는) {f90['spent_items']/tot:.0%}."
          " 모델은 승급·아이템 뒤 남은 골드의 60%를 시설에, 25%를 선물에 쓰는 적극적인 소비자를 가정하므로, 소진율은 '쓸 곳이 남아 있는 동안은 거의 다 쓴다'는 뜻으로 읽는다. 실제 지표는 소비처의 용량이다.",
          f"- 후반 소비처 용량(§2.5·§2.6): 본부 시설 5종 × 10단계 = {sum(FAC_COST.values()) * len(FAC_KEYS):,}골드, 보유 영웅 호감도 선물 약 {196 * TOKEN_GOLD * 10:,}골드. 90일 시점 시설 단계 합계(최대 {FAC['max_level'] * len(FAC_KEYS)}) — "
          + ", ".join(f"{out[k]['profile'].split('(')[0]} {out[k]['snapshots'][90]['facility_levels']:.0f}" for k in ("free", "light", "heavy"))
          + "; 호감도 100 달성 영웅 — " + ", ".join(f"{out[k]['profile'].split('(')[0]} {out[k]['snapshots'][90]['gifted_full']:.0f}명" for k in ("free", "light", "heavy"))
          + ". 시설과 선물을 모두 끝낸 프로필은 다시 골드가 쌓인다(헤비의 90일 소진율 하락).",
          "- 반복 클리어 골드 체감(§2.4)으로 줄어든 골드(90일 누적): " + ", ".join(f"{out[k]['profile'].split('(')[0]} {out[k]['snapshots'][90]['gold_decayed']:,.0f}({out[k]['snapshots'][90]['gold_decayed'] / max(1, out[k]['snapshots'][90]['gold_earned'] + out[k]['snapshots'][90]['gold_decayed']):.1%})" for k in ("free", "light", "heavy"))
          + ". 이 모델의 플레이어는 상위 30개 지역 전투를 고르게 돌기 때문에 체감에 거의 걸리지 않는다. 체감은 '한 전투만 반복하는' 플레이를 막는 장치이고, 수입 총량을 줄이는 효과는 작다.",
          "- 재료 병목은 별의 결정(M003: 악몽 드랍 + 보급소 일 2개)이며 ★3 승급이 엔드게임 목표로 작동한다. 무과금 ★3 영웅 수: "
          + ", ".join(f"{d}일 {out['free']['snapshots'][d]['star3']:.0f}명" for d in (30, 60, 90)) + ".",
          "- 용병 레벨(필요 EXP = 120 + 60×Lv + 40×max(0, Lv−20)²): " + "; ".join(f"{out[k]['profile'].split('(')[0]} " + " → ".join(f"{d}일 Lv{out[k]['snapshots'][d]['level']:.0f}" for d in (7, 30, 60, 90)) for k in ("free", "light", "heavy"))
          + ". 악몽 난이도는 EXP도 ×3.0이라, 악몽 위주로 도는 시점부터 레벨업이 빨라진다.",
          ]
    def actday(k, a):
        v = out[k]["act_reach_day_mean"].get(a); return ("%.0f일" % v) if v is not None else "90일 내 미도달"
    nm = {k: out[k]["snapshots"][90]["gold_by"]["nightmare"] / max(1, out[k]["snapshots"][90]["gold_earned"]) for k in ("free", "light", "heavy")}
    L += ["- **막 진행**: 4막 도달 — " + ", ".join(f"{out[k]['profile'].split('(')[0]} {actday(k, 'act4')}" for k in ("free", "light", "heavy"))
          + "; 5막 도달 — " + ", ".join(f"{out[k]['profile'].split('(')[0]} {actday(k, 'act5')}" for k in ("free", "light", "heavy"))
          + ".",
          "- **전력과 콘텐츠**: 엔진 측정 전력(보통 난이도, 아이템 없음) — " + ", ".join(f"계층 {t} ★1 {POWER_TABLE['normal'][(t, 1)]:.0f} / ★2 {POWER_TABLE['normal'][(t, 2)]:.0f} / ★3 {POWER_TABLE['normal'][(t, 3)]:.0f}" for t in (1, 3, 5))
          + f". 조합 아이템 3개 +{ITEM_POWER_COMPLETED:.0f}, 빛나는 3개 +{ITEM_POWER_RADIANT:.0f}. 악몽 기준으로는 계층 5 ★3이 {POWER_TABLE['nightmare'][(5, 3)]:.0f}이다(스토리 최고 레벨 100)."
          f" 90일 누적 골드 중 악몽 난이도 비중: 무과금 {nm['free']:.0%}, 소과금 {nm['light']:.0%}, 헤비 {nm['heavy']:.0%}."
          " 몬스터 전력 보정 곡선은 '레벨대별 실제 도달 팀'(scenario.expected_loadout)을 기준으로 맞춘 것이다(09 §4, 부록 B3).", ""]
    marker = "## 9. 경제 진행 시뮬레이션 결과"
    s = s[:s.index(marker)] if marker in s else s
    open(doc, "w", encoding="utf-8").write(s.rstrip() + "\n\n" + "\n".join(L))
    print("economy_sim.json + docs/07 §9 updated")


if __name__ == "__main__":
    main()
