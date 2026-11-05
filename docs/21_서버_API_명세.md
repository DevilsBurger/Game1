# 21. 서버 API 명세 (설계 요약)

> 정본은 [`server/openapi.yaml`](../server/openapi.yaml)(OpenAPI 3.1, 40 오퍼레이션). 이 문서는 프로토콜·정책·에러·보안을 설명한다. Unity 클라이언트 `Arken.Net`(15 §3.6)과 .NET 서버가 공유하며, `tests/test_openapi.py`가 정합성을 검사한다.

## 1. 개요
- **서버 권위 메타 + 클라이언트 전투 시뮬 + 서버 재시뮬 검증**(10 §7). 보상·드랍·호감도 RNG는 서버.
- 권장 스택: ASP.NET Core 8(Core DLL 재사용으로 동일 결정론), PostgreSQL(계정·인벤토리·원장), Redis(세션·멱등 키·일일 한도·속도 제한), 오브젝트 스토리지 + CDN(Addressables·밸런스 패치), 큐 + 워커(재시뮬·텔레메트리).
- 태그별 엔드포인트:

| 태그 | 경로 | 비고 |
|---|---|---|
| config | `GET /time`, `GET /config/version`, `GET /config/balance` | 인증 불필요(balance 제외), ETag |
| auth | `POST /auth/guest`, `/auth/link`, `/auth/switch`, `/auth/refresh`, `DELETE /auth/session`, `DELETE /account` | |
| profile | `GET/PATCH /profile` | 닉네임·설정 |
| roster | `GET /roster`, `PATCH /roster/{hero_id}`, `POST …/star-up`, `PUT …/equip`, `GET/PUT /roster/presets` | |
| inventory | `GET /inventory`, `POST /inventory/craft`, `/sell`, `/use` | |
| battle | `POST /battle/start`, `/battle/finish`, `/battle/abort`, `GET /battle/sessions` | §4 |
| shop | `GET /shop/catalog`, `POST /shop/buy`, `/shop/exchange`, `/shop/iap/verify` | |
| quest | `GET /quests`, `POST /quests/{id}/claim`, `GET /daily`, `POST /daily/checkin`, `/daily/commissions/{id}/claim` | |
| progress | `GET /progress` | 해금·클리어·기능 플래그 |
| mail | `GET /mail`, `POST /mail/{id}/claim` | 커서 페이지 |
| ftue | `GET /ftue`, `POST /ftue/steps` | 20 문서 |
| telemetry | `POST /telemetry/events` | 22 문서 |

## 2. 인증
- 게스트 로그인: `device_id`(앱 설치 UUID, 키체인/키스토어) → `player_id` + JWT(액세스 1h, 리프레시 30d). `is_new`로 FTUE 진입 판단.
- 연동: Apple / Google / Game Center / Play Games `id_token` → 기기 변경 복구. 다른 계정에 이미 연동됐으면 `409 ACCOUNT_CONFLICT` → 클라이언트 확인 모달 → `/auth/switch`(현 게스트 데이터 포기).
- 토큰 payload: `sub`(player_id), `dev`(device hash), `ver`(토큰 버전), `iat/exp`. 서명 키 RS256, 90일 롤링. 리프레시 토큰은 1회용(회전), 재사용 감지 시 전체 세션 폐기.
- 공통 헤더: `Authorization: Bearer`, `X-Client-Version`, `X-Data-Version`, `Accept-Language`. 서버는 `426 VERSION_OUTDATED`(강제 업데이트), `503 MAINTENANCE`(점검 화면, `details.until`)로 응답할 수 있다.

## 3. 공통 규약
- JSON snake_case, 시각은 ISO-8601 UTC, 재화는 정수. 데이터 ID는 문자열 그대로(H001, I008, S001, B0101, HQ001).
- **멱등성**: 변경 POST/PUT은 `Idempotency-Key`(UUID) 필수. Redis 24h 보관, 같은 키의 재요청은 최초 응답을 그대로 반환. 같은 키 + 다른 바디는 `422 VALIDATION_ERROR`. 오프라인 큐·재시도가 안전해진다.
- **에러**: `{ code, message, details, request_id }`. 사용자 문구는 클라이언트 문자열 `ui.error.{CODE}`(17 문서, 27개 + `ui.error.NETWORK`).

| HTTP | code | 클라이언트 동작 |
|---|---|---|
| 401 | `AUTH_EXPIRED`, `AUTH_INVALID` | 리프레시 1회 → 실패 시 타이틀로 |
| 402 | `INSUFFICIENT_GOLD/GEM/MATERIAL`, `STAMINA_INSUFFICIENT` | 부족 모달(상점·물약 바로가기) |
| 403 | `BATTLE_LOCKED`, `DIFFICULTY_LOCKED` | 해금 조건 안내 |
| 404 | `SESSION_EXPIRED` | 결과 폐기, 스태미너 환불 표시 |
| 409 | `SESSION_ACTIVE`, `STAR_MAX`, `ITEM_IN_USE`, `EMBLEM_DUPLICATE`, `ALREADY_CLAIMED`, `QUEST_INCOMPLETE`, `ACCOUNT_CONFLICT`, `NICKNAME_TAKEN` | 상태 재동기화 후 안내 |
| 422 | `CONDITION_UNMET`(details.failed[]), `RECIPE_INVALID`, `RECEIPT_INVALID`, `SNAPSHOT_MISMATCH`, `VALIDATION_ERROR` | 조건 체크리스트 표시 / 데이터 재동기화 |
| 426 | `VERSION_OUTDATED` | 스토어 이동 |
| 429 | `DAILY_LIMIT`, `RATE_LIMITED`(`Retry-After`) | 한도 안내 / 백오프 |
| 503 | `MAINTENANCE` | 점검 화면 |
| 500 | `INTERNAL` | 재시도 3회(지수 백오프) 후 오류 토스트 |

- 속도 제한: 사용자당 10 req/s(버스트 30), `/battle/start` 분당 20, `/telemetry/events` 분당 6.
- 페이지네이션: 우편만 커서. 나머지는 전체 반환(영웅 196 ≈ 60KB, 인벤토리 ≈ 100KB, gzip).
- 버전: URL `/v1`. 필드 추가만 하위 호환, 제거·의미 변경은 `/v2`.

## 4. 전투 프로토콜
```
클라 ──POST /battle/start {battle_id, difficulty, formation, pledge?, skip?}──▶ 서버
        검증: 해금 → 난이도 → 참전 모드(min/max, 제약 11종) → 레벨 슬롯(20 §4 규칙) → 스태미너 → 서약서
        세션 생성: seed(CSPRNG 64bit), snapshot(서버 보유 데이터로 구성), hash, balance_version 고정, 만료 10분
        스태미너 차감(난이도 비용 × 웨이브형 1.5)
클라 ◀── {session_id, seed, snapshot, snapshot_hash, stamina_charged, expires_at}
클라: 로컬 Registry + BalancePatch로 동일 스냅샷 구성 → hash 비교(불일치 → 재동기화 후 재시도)
      Core.Battle.Run()/Step() → BattleResult + EventChecksum
클라 ──POST /battle/finish {session_id, outcome, ticks, checksum, stats, skipped}──▶ 서버
        검증 정책: 전수(첫 클리어·영웅 드랍 발생·보스/결전/레이드·의심 계정) / 샘플 10%(일반 반복) / skip은 서버 계산이므로 불필요
        재시뮬: Core DLL 동일 seed·snapshot·balance_version → checksum 비교
        채택: match → client, mismatch → server(+ 계정 플래그), sampled_out → client
        보상: 서버 RNG(드랍·호감도·천장), 첫 클리어, 퀘스트 조건 재판정(stats가 아닌 재시뮬/서명 결과 기준), 레벨업·해금
클라 ◀── {verified, adopted, rewards, quest_progress, unlocked, level_up, stamina_refund}
```
- **skip**: `skip=true`면 서버가 즉시 `Run()`하고 `BattleStartResponse.result`에 결과를 담아 finish 없이 끝낸다(첫 클리어는 불가, 13 §7).
- **패배/포기**: `lose`/`timeout`/`abort`는 스태미너 50% 환불(`stamina_refund`). 세션 만료(10분)는 자동 abort.
- **오프라인**: finish 실패 시 로컬 큐(`session_id`, 동일 멱등 키)에 저장하고 만료 전 재전송. 보상은 서버 응답 후 반영(낙관적 UI 금지).
- **의심 계정**: mismatch 7일 내 3회 → 전수 검증 + 운영 알림. 하루 전투 300회 초과·불가능 시간(클라 sim_ms < 1) 도 플래그.
- 응답 목표: start p95 200ms, finish p95 400ms(재시뮬 포함, 10v10 30초 ≤ 20ms).

## 5. 경제·상점 서버 규칙 체크리스트
- 가격: `items.json price`(07 §2.3). 월정액 상점 10% 할인은 카탈로그 `discount_pct`에 반영.
- 일일 한도: 재료 M001 200 / M002 20 / M003 2, 보석 스태미너 구매 10회, 서약서 사용 제한 없음. 리셋 05:00 KST(`daily_reset_at`).
- 보석 → 골드 1:100 일방향. 무료 보석 먼저 소모, 유료 잔량(`gem_paid`)은 환불 산정용으로 분리 보관.
- IAP: Apple App Store Server API v2 / Google Play Developer API로 서버 검증, `order_id` 유니크, 월정액 갱신은 App Store Server Notifications v2 / Google RTDN 웹훅으로 반영. 지급은 `wallet_ledger`에 `reason=iap`.
- 판매 30%, 조합은 `recipes`, 상징 중복 장착 금지, 지원 아이템 슬롯 규칙은 서버가 최종 판정.
- 모든 재화 변동은 **append-only 원장**(`wallet_ledger`: reason, delta, balance_after, ref_id) → 22 문서 `currency_change` 이벤트의 원천.

## 6. 밸런스 패치 배포
- `sim/run_balance.py` 등 출력 → `balance.json`(`BalancePatch` 스키마) → S3/CDN + `GET /config/balance`(ETag). 클라이언트는 Boot 1회 + 로비 복귀 시 ETag 확인.
- 전투 세션은 시작 시점 `balance_version`에 고정. 서버는 최근 3개 버전을 보관해 세션 중 패치가 바뀌어도 같은 버전으로 재시뮬한다.
- 롤아웃: 스테이징 → 10% → 100%, mismatch율·승률 대시보드(22 §4) 감시, 롤백은 이전 버전 ETag 재게시.

## 7. 보안·치트 방어
| 위협 | 대응 |
|---|---|
| 메모리 변조(재화·스탯) | 서버 권위, 클라이언트 수치는 표시용 |
| 전투 결과 위조 | 시드·스냅샷 서버 발급 + 재시뮬 + 체크섬 |
| 리플레이(결과 재전송) | `session_id` 1회성 + 멱등 키 |
| 시간 조작(스태미너) | 서버 시각 기준 계산, 클라는 보간만 |
| 봇/매크로 | 속도 제한, 일일 전투 상한 경보, 기기 다중 계정 탐지 |
| 영수증 위조 | 스토어 서버 검증, order_id 유니크 |
| 토큰 탈취 | 짧은 액세스 토큰, 리프레시 회전, 기기 해시 바인딩 |
- 전송: TLS 1.2+, 인증서 피닝(선택). 개인정보: `device_id` 해시 저장, 이메일 미수집(연동 토큰의 `sub`만), 삭제 요청 7일 유예 후 영구 삭제.

## 8. 데이터 모델 (PostgreSQL 요약)
`players`, `auth_links`, `player_heroes`(hero_id, star, shards, stamina, stamina_at, affinity, favorite, lobby_display), `affinity_others`, `items`(instance_id, item_id, equipped_by), `consumables`, `wallet_ledger`(append-only), `battle_sessions`(seed, snapshot jsonb, balance_version, status, result jsonb, verified), `progress`(jsonb), `quest_state`, `daily_state`, `mail`, `ftue_steps`, `iap_orders`, `subscriptions`, `telemetry_raw`(일별 파티션). 핫 데이터(세션·멱등·한도)는 Redis.

## 9. 클라이언트 구현 메모 (Arken.Net)
- `ApiClient`: UnityWebRequest + UniTask. 5xx/네트워크 오류는 3회 지수 백오프(1/2/4s, 멱등 키 유지), 401은 리프레시 1회 후 재시도. 변경 요청은 직렬 큐(동시 1건), 읽기는 병렬.
- DTO: `unity/Generated/Dtos.cs`(게임 데이터)와 별도로 `tools/gen_netdtos.py`가 OpenAPI에서 생성한 `unity/Generated/NetDtos.cs`(네임스페이스 `Arken.Net.Generated`: 스키마 33 + 인라인 중첩 클래스, `ErrorCodes`, `Enums.*` 문자열 상수, `Routes` 메서드+경로 상수). 필드명은 JSON 키 그대로(snake_case)이므로 Newtonsoft/JsonUtility 모두 그대로 매핑된다. `tests/test_openapi.py`가 스펙과의 일치를 검사한다.
- 목 서버: M3까지는 같은 OpenAPI로 Prism 모킹 + 로컬 JSON 상태, M5에서 실서버 교체(15 §6 WBS).
- 시각: 모든 화면 타이머는 `server_time` 기준 오프셋으로 계산, 기기 시각 사용 금지.
