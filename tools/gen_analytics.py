# -*- coding: utf-8 -*-
"""애널리틱스 이벤트 사전: data/analytics_events.json + docs/22_애널리틱스_이벤트_명세.md 생성."""
import json, os
ROOT = os.path.join(os.path.dirname(__file__), "..")

CONTEXT = [
    ("event_id", "uuid", "클라이언트 생성, 서버 중복 제거 키"), ("ts", "datetime", "클라이언트 시각(서버 수신 시각 별도 기록)"),
    ("session_id", "string", "앱 포그라운드 세션"), ("player_id", "string(hash)", "분석 저장소에는 해시만"),
    ("client_version", "string", ""), ("data_version", "string", "data/*.json 번들"), ("balance_version", "string", "BalancePatch"),
    ("platform", "ios|android", ""), ("os_version", "string", ""), ("device_model", "string", ""), ("device_tier", "low|mid|high", "GPU·RAM 기준 자동 분류"),
    ("locale", "string", "ko-KR 등"), ("player_level", "int", ""), ("act", "int", "현재 막"), ("hero_count", "int", "보유 영웅 수"),
    ("ab_group", "string", "실험 배정"), ("network", "wifi|cell|offline", ""), ("is_subscriber", "bool", "월정액"),
]

# (name, source, props{name: type/desc}, desc)
EVENTS = {
    "세션·앱": [
        ("app_open", "client", {"cold_start": "bool", "launch_ms": "int"}, "앱 실행"),
        ("session_start", "client", {}, "포그라운드 진입"),
        ("session_end", "client", {"duration_sec": "int", "battles": "int", "screens": "int"}, "백그라운드/종료"),
        ("boot_step", "client", {"step": "patch|registry|addressables|login", "ms": "int", "ok": "bool"}, "부팅 단계별 시간"),
        ("error", "client", {"code": "string", "screen": "string", "endpoint": "string", "http_status": "int"}, "API/런타임 오류(크래시는 Crashlytics)"),
    ],
    "FTUE": [
        ("ftue_step", "client", {"step_id": "string", "elapsed_sec_from_open": "int", "skipped": "bool"}, "20 문서 단계 완료"),
        ("ftue_complete", "client", {"total_sec": "int"}, "필수 10단계 완료"),
        ("cutscene_view", "client", {"cutscene_id": "string", "skipped": "bool", "shot_index": "int"}, "컷신 시청/스킵"),
    ],
    "화면·UI": [
        ("screen_view", "client", {"screen_id": "S01..S15", "from_screen": "string", "load_ms": "int"}, "화면 진입"),
        ("ui_click", "client", {"screen_id": "string", "element_id": "string"}, "주요 버튼(샘플 10%)"),
        ("coachmark_shown", "client", {"key": "string", "dismissed_by": "next|skip|action"}, "코치마크"),
        ("dialog_view", "client", {"dialog_id": "string", "result": "string"}, "모달/팝업"),
    ],
    "전투": [
        ("battle_prepare", "client", {"battle_id": "string", "kind": "string", "type": "string", "difficulty": "string", "conditions_met": "bool", "team_size": "int", "team_power": "number"}, "S05/S06 진입"),
        ("battle_start", "server", {"session_id": "string", "battle_id": "string", "kind": "string", "type": "string", "difficulty": "string", "team_size": "int", "team_hero_ids": "string[]", "team_stars": "int[]", "items_equipped": "int", "active_traits": "object", "stamina_cost": "int", "pledge_used": "string|null", "attempt_no": "int"}, "세션 발급"),
        ("battle_end", "server", {"session_id": "string", "battle_id": "string", "difficulty": "string", "outcome": "win|lose|timeout|abort", "elapsed_sec": "number", "ticks": "int", "skipped": "bool", "speed": "int", "survivors": "int", "no_death": "bool", "verified": "match|mismatch|sampled_out", "adopted": "client|server", "client_sim_ms": "int", "fps_avg": "number", "fps_min": "number"}, "결과 제출·검증"),
        ("battle_reward", "server", {"session_id": "string", "gold": "int", "exp": "int", "gem": "int", "items": "string[]", "materials": "object", "first_clear": "bool"}, "보상 지급"),
        ("battle_retry", "client", {"battle_id": "string", "attempt_no": "int", "changed_formation": "bool"}, "재도전"),
    ],
    "영웅": [
        ("hero_acquired", "server", {"hero_id": "string", "tier": "int", "origin": "string", "class": "string", "source": "drop|pity|quest|story|gift", "encounter_count": "int", "rolled_pct": "number"}, "영입"),
        ("hero_duplicate", "server", {"hero_id": "string", "shards": "int"}, "중복 → 파편"),
        ("affinity_change", "server", {"hero_id": "string", "delta": "int", "source": "fail|duplicate|charm", "total": "int"}, "호감도"),
        ("star_up", "server", {"hero_id": "string", "from": "int", "to": "int", "gold": "int", "materials": "object"}, "승급"),
        ("equip_change", "client", {"hero_id": "string", "slot": "int", "item_id": "string|null", "prev_item_id": "string|null"}, "장비 변경"),
        ("preset_save", "client", {"preset_index": "int", "slot_count": "int"}, "프리셋"),
    ],
    "경제·상점": [
        ("currency_change", "server", {"currency": "gold|gem|M001|M002|M003", "delta": "int", "balance_after": "int", "reason": "battle_reward|first_clear|quest|sell|buy|craft|star_up|exchange|iap|mail|checkin|commission|subscription", "ref_id": "string"}, "원장 파생(모든 재화 변동)"),
        ("shop_view", "client", {"tab": "forge|armory|relic|supply|gem|sell"}, "탭 진입"),
        ("shop_buy", "server", {"sku": "string", "item_id": "string", "qty": "int", "currency": "gold|gem", "price": "int", "discount_pct": "int"}, "구매"),
        ("craft", "server", {"component_a": "string", "component_b": "string", "result": "string", "first": "bool"}, "조합"),
        ("sell", "server", {"item_ids": "string[]", "gold": "int"}, "판매"),
        ("consumable_use", "server", {"item_id": "string", "target_hero_id": "string|null", "qty": "int"}, "소모품"),
        ("exchange", "server", {"gems": "int", "gold": "int"}, "보석→골드"),
    ],
    "BM": [
        ("iap_view", "client", {"product_id": "string", "screen": "string"}, "상품 노출(클릭 기준)"),
        ("iap_start", "client", {"product_id": "string", "price_local": "number", "currency": "string"}, "결제 시작"),
        ("iap_result", "server", {"product_id": "string", "status": "granted|already_granted|pending|failed|cancelled", "order_hash": "string", "revenue_usd": "number"}, "결제 결과"),
        ("subscription_state", "server", {"active": "bool", "days_left": "int", "daily_gem_claimed": "bool"}, "월정액 일일 상태"),
        ("stamina_gem_buy", "server", {"count_today": "int", "gems": "int"}, "보석 스태미너 구매"),
        ("pledge_use", "server", {"tier": "normal|advanced|legend", "battle_id": "string", "target_hero_id": "string"}, "서약서"),
        ("charm_use", "server", {"hero_id": "string", "qty": "int", "affinity_after": "int"}, "매력 징표"),
    ],
    "진행·퀘스트": [
        ("progress_unlock", "server", {"kind": "act|nation|region|battle|feature|difficulty", "key": "string"}, "해금"),
        ("quest_step", "server", {"quest_id": "string", "step": "int", "passed": "bool", "failed_conditions": "string[]"}, "퀘스트 단계 판정"),
        ("quest_claim", "server", {"quest_id": "string", "kind": "string", "reward_hero_id": "string|null"}, "보상 수령"),
        ("daily_checkin", "server", {"day": "int", "streak": "int"}, "출석"),
        ("commission_claim", "server", {"key": "string"}, "일일 의뢰"),
        ("mail_claim", "server", {"mail_id": "string", "type": "string"}, "우편"),
    ],
    "설정·기술": [
        ("settings_change", "client", {"key": "string", "value": "string"}, "설정"),
        ("push_permission", "client", {"granted": "bool", "prompt_no": "int"}, "푸시 권한"),
        ("perf_sample", "client", {"screen": "string", "fps_avg": "number", "fps_1pct_low": "number", "mem_mb": "int", "units": "int"}, "성능(세션 1% 샘플)"),
        ("network_retry", "client", {"endpoint": "string", "attempts": "int", "final_status": "int"}, "재시도"),
        ("asset_download", "client", {"bundle": "string", "bytes": "int", "ms": "int", "ok": "bool"}, "어드레서블"),
    ],
}

def main():
    flat = []
    for group, evs in EVENTS.items():
        for name, src, props, desc in evs:
            flat.append({"name": name, "group": group, "source": src, "props": props, "desc": desc})
    names = [e["name"] for e in flat]
    assert len(names) == len(set(names))
    json.dump({"version": 1, "context": [{"name": n, "type": t, "desc": d} for n, t, d in CONTEXT], "events": flat},
              open(os.path.join(ROOT, "data", "analytics_events.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    L = []
    L.append("# 22. 애널리틱스 이벤트 명세\n")
    L.append("> 목적: FTUE 퍼널(20 문서), 경제·밸런스 검증(07·09의 예측 vs 실측), BM 지표. 수집: 클라이언트 `AnalyticsService` → `POST /telemetry/events` 배치(21 문서), 서버 이벤트는 서버 핸들러에서 직접 발행. 기계 판독 사전은 `data/analytics_events.json`(이 문서와 함께 `tools/gen_analytics.py`가 생성).\n")
    L.append("## 1. 원칙")
    L.append("- 이름·속성은 snake_case, 이벤트 ≤ 40자, 속성 ≤ 20개. 클라이언트 이벤트는 '의도/UI', 서버 이벤트는 '사실'(재화·보상·검증). **재화 변동은 서버 원장에서만** 기록한다.")
    L.append("- 개인정보 없음: 닉네임·이메일·광고 ID 미수집. `player_id`는 분석 저장소에서 해시. iOS ATT 요청 없음.")
    L.append("- 모든 이벤트에 공통 컨텍스트(§2)를 자동 첨부. 서버 중복 제거 키는 `event_id`.")
    L.append("- 샘플링: `perf_sample` 세션 1%, `ui_click` 10%, 나머지 100%.\n")
    L.append("## 2. 공통 컨텍스트")
    L.append("| 필드 | 타입 | 비고 |\n|---|---|---|")
    for n, t, d in CONTEXT: L.append(f"| `{n}` | {t} | {d} |")
    L.append("")
    L.append(f"## 3. 이벤트 카탈로그 ({len(flat)})")
    for group, evs in EVENTS.items():
        L.append(f"### 3.{list(EVENTS).index(group)+1} {group}")
        L.append("| 이벤트 | 출처 | 속성 | 설명 |\n|---|---|---|---|")
        for name, src, props, desc in evs:
            ps = ", ".join(f"`{k}`:{v}" for k, v in props.items()) or "—"
            L.append(f"| `{name}` | {src} | {ps} | {desc} |")
        L.append("")
    L.append("""## 4. 퍼널·KPI
- **FTUE 퍼널**(20 §8): `app_open` → `cutscene_view(CS-00)` → `ftue_step(deploy_drag)` → `battle_end(S001, win)` → `battle_end(S002, win)` → `hero_acquired(H009)` → `screen_view(S02)` → `battle_end(S004, win)` → `craft(first)` → `battle_end(kind=encounter)` → D1 복귀. 목표 누적 97/92/88/85/75/65/55/40%.
- **리텐션**: D1 40% · D7 18% · D30 8%. 세션 길이 중앙값 12분, 일 세션 3회.
- **전투**: 난이도별 승률(실측 vs 09 예측 보통 82 / 어려움 62 / 악몽 37%). 전투별 승률 < 40% 또는 재시도 중앙값 ≥ 3 → 밸런스 플래그. 스킵율, 배속 분포, 평균 전투 시간, `verified=mismatch` 비율 < 0.1%(초과 시 결정론 버그 의심).
- **영웅**: 영웅별 편성 포함률(상·하위 5% → 09 재수렴 입력), 계층별 획득까지 조우 횟수(설계 계층 5 평균 11.4회), 천장(호감도 100) 도달 비율, 승급 분포.
- **경제**: 골드 수입/지출 비율(07 §2 목표), 재료 일일 한도 소진율, 보석 잔액 분포, 4막 진입 일수(07 §9 예측: 무과금 미도달·소과금 77일) 실측.
- **BM**: 전환율, ARPDAU, ARPPU, 월정액 유지율, 상품별 매출 비중, 보석 스태미너 10회 상한 도달 비율, 서약서 사용당 영입 확률 실측.
- **기술**: 크래시율 < 0.5%, 평균 fps(중급 60 / 저사양 30), 부팅 시간 p90 < 8s, API 오류율 < 0.5%.

## 5. 대시보드
1. 일간 운영: DAU·신규·매출·크래시·API 오류.
2. FTUE 퍼널: 단계별 도달·소요 시간·이탈 경보.
3. 밸런스: 전투 1,604 × 난이도 3 승률 히트맵, 영웅 196 사용률·승률, 아이템 장착률 → `sim/` 재조정 입력.
4. 경제: 재화 소스/싱크 일별, 플레이어 레벨·막 분포, 경제 시뮬(07 §9) 곡선과 실측 겹쳐 보기.
5. 라이브 검증: mismatch 추이, 의심 계정, 밸런스 패치 버전별 승률 변화.

## 6. 구현 (Unity `Arken.Infra.AnalyticsService`)
- `Track(name, props)`: 공통 컨텍스트 병합 → 메모리 큐 → 디스크 `analytics_queue.jsonl`(최대 5,000건/2MB, 초과 시 오래된 것부터 폐기).
- 플러시: 20건 또는 30초 또는 백그라운드 진입. 전송 실패는 보존·지수 백오프, `event_id`로 서버 중복 제거.
- 서버 이벤트는 핸들러 → 큐(Kafka 등) → 같은 스키마로 적재. 원본 JSONL 일별 파티션 → DWH(BigQuery/ClickHouse) `events` 테이블 + 그룹별 뷰.
- 스키마 검증: CI에서 클라이언트가 발행하는 이벤트 이름·속성이 `data/analytics_events.json`에 있는지 검사(`tests/test_data.py` 확장 예정).
- 서드파티(Firebase/GA4 등) 미러링은 선택. 사용 시 동일 이름, 속성 25개 제한에 맞춰 축약.

## 7. 개인정보·보관
- 첫 실행 시 개인정보 처리방침 동의(필수: 서비스 운영 로그). 마케팅 동의 없음(광고 없음).
- 계정 삭제 시 `player_id` 해시 키 폐기(익명화), 원본 13개월·집계 영구 보관.
""")
    open(os.path.join(ROOT, "docs", "22_애널리틱스_이벤트_명세.md"), "w", encoding="utf-8").write("\n".join(L))
    print("analytics events:", len(flat), "groups:", len(EVENTS))

if __name__ == "__main__":
    main()
