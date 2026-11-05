# 15. Unity 아키텍처 및 개발 계획

> 코드는 로컬에서 작성한다. 이 문서는 프로젝트 구조·모듈 경계·핵심 클래스/인터페이스·데이터 흐름·씬 플로우·작업 계획(WBS)을 정의한다. 전투 규칙의 기준 구현은 `sim/engine/*.py`(파이썬)이며, C# 포팅은 `tests/vectors/battle_vectors.json` 41개 벡터를 재현해야 한다.

## 1. 기술 스택 결정
| 항목 | 결정 | 근거 |
|---|---|---|
| Unity | **Unity 6 LTS**, URP 2D Renderer | 2D 라이트/셰이더 그래프, 장기 지원 |
| 언어/표준 | C# 10, .NET Standard 2.1, `Nullable` 활성 | |
| UI | **UI Toolkit**(화면·HUD) + UGUI(월드 스페이스 체력바·드래그 전용 최소) | 데이터 바인딩·스타일시트(USS)로 디자인 토큰 직결, 가로 비율 대응 |
| 2D 애니메이션 | **Spine 2D**(spine-unity) | 파츠 리깅·스킨·믹스 |
| 에셋 | Addressables (국가별 그룹, 원격 CDN) | 초기 용량 150MB 제한 |
| 데이터 | JSON(`data/*.json`) → 빌드 시 **ScriptableObject 변환**(에디터 임포터) + 런타임 핫픽스는 JSON 패치(밸런스 배율·보정 곡선) | 디자이너 파이프라인 유지, 런타임 파싱 비용 제거 |
| 결정론 | 전투 코어는 **IEEE 754 double + xorshift64\* RNG(splitmix64 시드)**, 연산 순서 고정, 초월함수 금지, Burst fast-math 금지 | 파이썬 레퍼런스(CPython double)와 비트 단위 동일 결과 → 서버 재검증·리플레이. 고정소수점 전면 정수화보다 포팅 위험이 작다 |
| 네트워크 | REST(UnityWebRequest) + JWT, 전투 결과 서버 재시뮬 검증 | |
| 저장 | 서버 권위, 로컬 캐시(설정·프리셋) | |
| 테스트 | Unity Test Framework(EditMode: 코어, PlayMode: UI 스모크), 벡터 재현 테스트 | |
| CI | GitHub Actions + GameCI(빌드·테스트), 에셋 검증 스크립트 | |

## 2. 프로젝트 구조
```
Assets/
  _Project/
    Scripts/
      Core/          (asmdef: Arken.Core)        — 순수 C#, Unity 의존 없음: 전투 규칙·데이터 모델·계산
      Data/          (Arken.Data)                — ScriptableObject 정의·JSON 임포터·레지스트리
      Meta/          (Arken.Meta)                — 계정·인벤토리·스태미너·퀘스트·드랍·경제(클라이언트 측 모델/서비스)
      Net/           (Arken.Net)                 — API 클라이언트, DTO, 재시도/큐
      Presentation/  (Arken.Presentation)        — 전투 뷰(보드·유닛 뷰·VFX), 씬 컨트롤러
      UI/            (Arken.UI)                  — UI Toolkit 화면·뷰모델·컴포넌트
      Infra/         (Arken.Infra)               — 로깅·이벤트 버스·DI(VContainer)·시간·로컬 저장
      Editor/        (Arken.Editor)              — 임포터, 밸런스 뷰어, 리플레이 뷰어
    UI/ (UXML, USS, 테마), Art/ (12 §11 규칙), Audio/, Prefabs/, Scenes/, Spine/, Addressables/
    Resources/ (최소), StreamingAssets/data/ (JSON 핫픽스 폴백)
  Plugins/ (spine-unity, VContainer, UniTask, Newtonsoft.Json)
Tests/ EditMode/ (Core 벡터 재현, 데이터 무결성)  PlayMode/ (씬 전환, 편성 드래그)
```
의존 방향: `UI → Presentation → Meta → Core`, `Data`는 모두가 참조, `Net`은 Meta만 참조. Core는 Unity API 금지(서버 .NET에서 동일 DLL 재사용).

## 2.1 사전 생성 산출물 (저장소 `unity/`, 복사해서 사용)
| 파일 | 내용 | 생성기 |
|---|---|---|
| `unity/Generated/Enums.cs` | Origin·HeroClass·Archetype·ItemCategory·StatKey·HookType·BattleType·BattleKind·Participation·Difficulty·QuestKind·BattleEventType + 문자열 키 변환 | `tools/gen_csharp.py` |
| `unity/Generated/Dtos.cs` | data/*.json 1:1 DTO(Newtonsoft), BalancePatchDoc, BattleEvent/EventChecksum | 〃 |
| `unity/Generated/DesignTokens.cs` | 색·폰트·크기·간격·모션 상수, NationPalettes 24 | 〃 (design/tokens.json) |
| `unity/Generated/TraitKeys.cs` | 특성 효과 키 열거 | 〃 |
| `unity/UI/theme.uss` | UI Toolkit 테마 변수(`--ember-500` …)와 기본 컴포넌트 클래스 | 〃 |
| `schemas/*.schema.json`, `schemas/enums.json` | 데이터 스키마·열거형 | `tools/gen_schemas.py` |
| `tests/vectors/battle_vectors.json` | RNG 알려진 답 + 전투 벡터 41(이벤트 체크섬 포함) | `sim/make_vectors.py` |
- `unity/Generated/NetDtos.cs` — 서버 API 요청/응답 DTO·에러 코드·라우트 상수 (`tools/gen_netdtos.py`, 원본 `server/openapi.yaml`, 21 문서).

## 3. 모듈 설계

### 3.1 Core (결정론 전투 코어) — `sim/engine` 1:1 포팅
```csharp
namespace Arken.Core.Combat {
  // 수치는 double. 파이썬 레퍼런스와 같은 순서로 연산한다(괄호·곱셈 순서 유지). Math.Round는 MidpointRounding.ToEven(파이썬 round와 동일).
  public sealed class Rng {   // sim/engine/rng.py 와 동일: splitmix64 시드, xorshift64*
    ulong s; public Rng(ulong seed);
    public ulong NextU64();                 // x^=x>>12; x^=x<<25; x^=x>>27; return x*0x2545F4914F6CDD1D (unchecked)
    public double Random();                 // (NextU64()>>11) * (1.0/9007199254740992.0)
    public int RandRange(int n);            // (int)(NextU64() % (ulong)n)
    public void Shuffle<T>(IList<T> a);     // Fisher–Yates i=n-1..1, j=RandRange(i+1)
    public List<T> Sample<T>(IList<T> a, int k);  // partial Fisher–Yates
  }
  // tests/vectors/battle_vectors.json 의 rng.known_answers(시드 5종 × u64/random/randrange/shuffle/sample)를 먼저 통과시킨다.
  public readonly struct Hex { public readonly int Col, Row; /* odd-q */ public static int Dist(Hex a, Hex b); public static Hex[] Neighbors(Hex h); }
  public sealed class UnitSpec { string Id; string Name; string Origin; string Class; int Tier; int Star; double Hp, Ad, As, Armor, Mr; int Range; double ManaStart, ManaMax, Crit, CritDmg, Ap; SkillSpec Skill; double SkillMult; ItemDef[] Items; UnitFlags Flags; Dictionary<string,object> State; }
  public sealed class Unit { /* combat.py Unit과 동일 필드: mod, buffs, shields, 타이머, hooks, stats */ }
  public interface IHook { void Register(Battle b, Unit u, HookParams p, Fx mult); }   // items.py / traits.py 훅 ↔ 이벤트 핸들러
  public enum HookEvent { Start, Attack, DamageDealt, Damaged, Cast, Kill, Death, Died, Tick1s, Crit, PreDamage, PreTaken, WaveEnd, Revived }
  public sealed class Battle {
    public Battle(GameData data, IReadOnlyList<UnitSpec> allies, IReadOnlyList<UnitSpec> enemies, ulong seed, BattleRules rules);
    public BattleResult Run();                 // 전체 시뮬 (서버·스킵)
    public bool Step();                        // 1틱(0.05s) 진행 → 뷰가 이벤트 큐를 소비 (클라이언트 렌더)
    public IReadOnlyList<BattleEvent> DrainEvents();   // Damage, Heal, Cast, Move, Death, Spawn, Wave, Stun …
  }
  public sealed class BattleRules { List<List<UnitSpec>> Waves; bool Assassination, Escape; Dictionary<int,HashSet<string>> DisableTraits; bool RecordEvents; }
  public sealed class BattleResult { int Winner; double Time; int Waves; List<UnitResult> Units; EventChecksum Events; }
  // BattleEvent (파이썬 Battle.emit 과 동일 필드): spawn{uid,team,name,cell,owner,hid,star,hp} move{uid,frm,to} attack{uid,target,empowered}
  //   cast{uid,skill,archetype,target} damage{src,dst,amount,kind,crit,skill} heal{src,dst,amount,vamp} death{uid,killer} revive{uid,hp} stun{uid,duration} wave{index,units} end{winner}; 모두 t(초) 포함
  // EventChecksum{count, by_type, damage_sum, heal_sum} — 벡터 검증·서버 결과 서명에 사용
  public static class Abilities { /* 34 원형 switch: abilities.py cast_ability */ }
  public static class Traits { /* 28 특성 적용: traits.py, scale_eff 포함 */ }
  public static class ItemHooks { /* 55 훅: items.py */ }
}
```
- 포팅 규칙: (1) 수치는 `double`, 파이썬과 같은 식·같은 순서로 계산(예: `raw * 100.0 / (100.0 + armor)`를 `raw / (1 + armor/100)`로 바꾸지 말 것). (2) RNG 호출 순서·횟수 동일(정렬 타이브레이크의 `rng.random()`은 후보를 같은 순서로 순회하며 키를 먼저 계산한 뒤 정렬). (3) 유닛 순회는 리스트 순서, 딕셔너리는 삽입 순서(C#은 `List`/순서 보장 컬렉션), 틱 순서는 짝수 틱 정방향·홀수 틱 역방향. (4) `round()`는 ToEven, 정수 변환은 절삭.
- 검증: `tests/vectors/battle_vectors.json` → EditMode 테스트가 RNG 알려진 답(5시드) → 승자·시간·생존자·총 피해·**이벤트 체크섬**(종류별 개수·피해/치유 합) 순으로 엄격 비교. 어긋나면 첫 불일치 이벤트(t, type)로 역추적한다.
- 성능: 10v10 30초 ≤ 20ms(Run), Step당 ≤ 0.3ms. 유닛/셀 조회는 배열 인덱스(`Unit[] byCell[56]`).

### 3.2 Data
```csharp
[CreateAssetMenu] class HeroDef : ScriptableObject { string Id; LocalizedString Name, Title, Lore; string Origin, Class; int Tier; BaseStats Stats; SkillDef Skill; float[] ArchetypePower; Balance Balance; AssetReferenceSprite Portrait; AssetReferenceT<SkeletonDataAsset> Battle; }
class ItemDef, NationDef, BattleDef(1,604 → 국가별 SO 묶음), QuestDef, TraitDef, EconomyDef, MonsterDef
class GameRegistry : ScriptableObject { 모든 Def 사전 + 인덱스(출신별, 국가별, 종류별) }
static class JsonImporter (Editor) { data/*.json → SO 생성/갱신; 체크섬으로 변경분만 }
class BalancePatch { 런타임 JSON: heroes.balance, items.balance, traits.balance, enemy_power_curve, tuned_power_mult — 서버가 배포, Registry에 오버레이 }
```
- 레지스트리 로드 ≤ 300ms(모바일). BattleDef는 Addressables로 국가 단위 지연 로드.

### 3.3 Meta (플레이어 상태·규칙)
| 서비스 | 책임 | 비고 |
|---|---|---|
| `AccountService` | 로그인·프로필·용병 레벨/EXP·팀 슬롯 | `economy.team_size_by_player_level` |
| `RosterService` | 보유 영웅(성급·스태미너·호감도·장비), 승급(`star_up_cost`), 프리셋 | 스태미너 회복 타이머(서버 시각 기준) |
| `InventoryService` | 아이템·재료·재화, 조합(레시피), 판매 | |
| `BattleService` | 전투 준비(조건 검증) → 서버 시드 발급 → 로컬 시뮬/렌더 → 결과 제출 → 보상 수령 | 결과 검증 실패 시 서버 결과 채택 |
| `RewardService` | 드랍 테이블 해석(아이템 풀·재료·영웅 드랍·호감도·서약서 배수) | 서버 RNG, 클라는 표시만 |
| `QuestService` | 103 퀘스트 진행·조건 판정(전원 생존·시간·인원·출신 수 등) | 조건 키 11종 |
| `ShopService` | 6탭 상점, 일일 한도, 보석 교환 | |
| `ProgressService` | 막/국가/지역/전투 해금, 첫 클리어, 호감도 천장, 참전 슬롯 = clamp(max(레벨 슬롯, participation.min), min, max) | 20 §4 |

### 3.4 Presentation (전투 뷰)
- `BoardView`: odd-q 헥스 8×7 렌더(스프라이트 타일 + 틴트), 셀 ↔ 월드 좌표, 배치 가능 하이라이트, 배경 스프라이트(국가·지역).
- `UnitView`: Spine `SkeletonAnimation`, 체력/마나 바(월드 스페이스 UGUI 또는 UI Toolkit 월드 패널), 성급·기절 아이콘, 좌우 반전(적).
- `BattlePresenter`: `Battle.Step()`을 고정 간격으로 호출(배속 1/2/3 = Step 횟수), `DrainEvents()`를 애니메이션 큐로 변환(이동 보간 0.5s, 공격 트리거, 시전 컷인, 피해 숫자 풀). 스킵 = `Run()` 후 결과.
- `VfxLibrary`: 원형 34 × 출신 색 파라미터(Shader Graph 틴트), 오브젝트 풀.
- `EncounterDirector`: 영웅 획득·승급·컷신 연출 타임라인(Timeline/UniTask).

### 3.5 UI (UI Toolkit)
- 테마: `design/tokens.json` → USS 변수(`--ash-800`, `--ember-500` …) 자동 생성(에디터 스크립트). 폰트·크기·간격 토큰 동일.
- 화면(S01~S15)은 각각 `UXML + UIView(ViewModel 바인딩)`. 네비게이션 스택(`ScreenRouter`): Push/Pop/Replace, 모달 레이어, 토스트 레이어.
- 리스트 가상화(ListView)로 영웅 196·전투 1,604·아이템 282 처리. 드래그 앤 드롭은 UI Toolkit `PointerManipulator`(벤치 → 보드는 화면 좌표 → 헥스 변환).
- 세이프 에어리어: 루트 패널 패딩을 `Screen.safeArea`로 갱신, 가로 고정(`Screen.orientation = LandscapeLeft/Right`).
- 로컬라이즈: Unity Localization, 키 = `hero.H001.name` 등 데이터 ID 기반.

### 3.6 Net
- 엔드포인트: `/auth`, `/profile`, `/roster`, `/inventory`, `/battle/start`(시드·스냅샷) `/battle/finish`(결과·통계) `/shop`, `/quest`, `/config/balance`(패치).
- 오프라인: 전투 결과 큐 저장 후 재전송, 보상은 서버 응답 후 반영(낙관적 UI 금지).

## 4. 씬 플로우·상태 머신
```
Boot(초기화·패치 다운로드·레지스트리 로드) → Title → [Prologue] → Lobby ⇄ {WorldMap → Nation → BattleInfo → Formation → Battle → Result}
                                                           ⇄ Heroes / Shop / Quests / Arena / Settings
```
- 씬: `Boot`, `Main`(로비 계열 UI 전부, 배경만 교체), `Battle`(보드·유닛·전투 HUD). 가벼운 화면은 씬 전환 없이 UI 스택.
- 전투 상태: `Prepare(조건 검증·서버 시드) → Loading(Addressables) → Deploy(편성 적용) → Running(Step 루프) → Resolved(결과 제출) → Reward`.

## 5. 핵심 데이터 흐름
```
tools/gen_*.py ──JSON──▶ Editor JsonImporter ──▶ ScriptableObjects(Registry) ──▶ 런타임
sim/run_balance.py 등 ──balance JSON──▶ 서버 /config/balance ──▶ BalancePatch 오버레이(핫픽스, 앱 업데이트 없음)
서버 /battle/start ─seed·snapshot─▶ Core.Battle.Run/Step ─result─▶ /battle/finish ─▶ 서버 재시뮬 비교 ─▶ 보상
```

## 6. 마일스톤·WBS (1인 개발 기준, 주 단위; 2~3인이면 병렬화)

| 단계 | 기간 | 산출물 | 주요 작업 |
|---|---|---|---|
| **M0 아트 앵커·프로토 준비** | 1~2주 | 앵커 세트 확정, 유닛 시트 파이프라인 검증, 프로젝트 셋업 | 12·14 문서 기준 앵커 생성, Spine 리깅 템플릿 2종, Unity 6 프로젝트·asmdef·CI |
| **M1 전투 코어** | 3주 | `Arken.Core` + 벡터 테스트 통과 | Fx·Rng·Hex, Unit/Battle, 원형 34, 특성 28, 훅 55, 규칙(웨이브·구조물·호위·구출·암살·탈출), EditMode 벡터 41 재현 |
| **M2 전투 뷰·편성** | 3주 | 보드·유닛 뷰, 편성 화면, 결과 화면 | BoardView, UnitView(Spine), BattlePresenter 이벤트 큐, VFX 10종 선행, S05~S08 UI, 배속/스킵 |
| **M3 메타 루프(1막)** | 4주 | 1막 플레이어블(스토리 15 + 지역 135 + 조우 42) | Registry 임포터, Meta 서비스 7종(로컬 목 서버), S02·S03·S04·S09~S11, 보상/드랍/호감도, 스태미너 |
| **M4 상점·퀘스트·경제** | 3주 | S12·S13·S14, 조합/판매, 퀘스트 103 조건 판정 | 대장간 레시피 UI, 일일 한도, 현상금/투기장, 일일 의뢰 |
| **M5 서버·라이브** | 4주 | 서버 API, 재시뮬 검증, 밸런스 패치, 어드레서블 CDN | .NET 서버에서 Core DLL 재사용, JWT, 결과 큐, 패치 배포 |
| **M6 콘텐츠 완성** | 6주 | 2~5막 전 콘텐츠, 컷신 25, 아트 전량 | 국가별 Addressables 그룹, 컷신 디렉터, 2차 밸런스(실플레이 데이터) |
| **M7 소프트 런치 준비** | 3주 | 스토어 빌드, 분석·결제·푸시, QA | IAP(월정액·보석), 애널리틱스 이벤트, 성능(저사양 30fps), 로컬라이즈 EN |
합계 약 27주. 아트 제작(미드저니 1,200장 + 리깅 329)은 M0부터 병렬 진행하며 M3 전까지 1막 분량, M6까지 전량.

### 6.1 M1 상세 작업 분해
1. `Rng`(xorshift64*) + 알려진 답 테스트 · 2. `Hex`(odd-q, 거리·이웃·반경) + 대칭 테스트 · 4. `UnitSpec/Unit/모드/버프/방어막` · 5. `Battle` 틱 루프(이동·타겟·공격·마나·시전·연장) · 6. 피해 공식·치유·사망·부활 · 7. 원형 34 · 8. 특성 28 + `scale_eff` · 9. 훅 55 + 오라 · 10. 규칙(웨이브/구조물/호위/구출/암살/탈출) · 11. `BattleEvent` 큐 + 체크섬 · 12. 벡터 테스트·성능 벤치.

### 6.2 리스크
| 리스크 | 대응 |
|---|---|
| 파이썬 ↔ C# double 연산 순서 차이로 벡터 미재현 | 이벤트 체크섬으로 첫 불일치 지점을 찾는다. 플랫폼 간(x86/ARM) 기본 사칙연산은 IEEE 동일. FMA 자동 결합·Burst fast-math·float32 사용 금지 |
| UI Toolkit 드래그·월드 좌표 변환 복잡 | 편성 보드만 UGUI로 대체 가능(인터페이스 분리) |
| 미드저니 일관성 | 앵커 `--sref` 고정, 영웅 `--cref`, 검수 체크리스트, 1막 분량으로 파이프라인 먼저 검증 |
| 어드레서블 용량 | 국가 단위 원격 번들, 초상 아틀라스 출신별 분할 |
| 서버 재시뮬 비용 | 결과 서명 + 샘플링 검증(10%) + 의심 계정 전수 |

## 7. 코딩 규칙(요약)
- Core는 `UnityEngine` 참조 금지, 할당 최소화(풀링), 이벤트는 구조체 리스트.
- 데이터 ID는 문자열(H001, I008, B0101) 그대로 사용, 열거형 변환 금지(핫픽스 호환).
- UI는 ViewModel ↔ UXML 바인딩, 뷰에 게임 규칙 금지. 모든 수치 포맷은 `NumberFormatter`(천 단위, 탭 숫자).
- 모든 문자열은 Localization 테이블, 하드코딩 금지.
