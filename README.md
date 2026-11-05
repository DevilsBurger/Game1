# 아르켄: 잿빛 날개 (ARKEN: Ashen Wings)

2D 가로(Landscape) 모바일 수집형 오토배틀러 RPG. TFT(롤토체스) 방식의 헥스 그리드 자동전투 + PvE 캠페인.

- 문서: [docs/00_문서_색인.md](docs/00_문서_색인.md) (GDD, 세계관, 영웅/아이템/전투/경제/BM, 기술, UI, 밸런스, 그래픽 가이드/디자인 시스템, 에셋·프롬프트, Unity 아키텍처, 스토리 대본, 로컬라이즈, 사운드, VFX, FTUE, 서버 API, 애널리틱스, QA)
- 디자인: `design/` — 토큰·국가 팔레트·스타일가이드 미리보기(`styleguide.html`)
- 데이터: `data/` — 영웅 196, 아이템 282, 국가 24, 전투 1,604, 퀘스트 103, 스토리 대본, 문자열 6,987키, 아트 트래커 1,240행, 애널리틱스 사전
- 서버: `server/openapi.yaml` — 메타 API 계약(OpenAPI 3.1, 40 오퍼레이션)
- 시뮬레이터: `sim/` — 결정론적 자동전투 엔진 + 등가모델 밸런스 러너 + 전투 난이도 검증
- 생성기: `tools/`

```bash
python3 tools/gen_heroes.py && python3 tools/gen_items.py && python3 tools/gen_world.py
sh sim/run_all.sh        # 밸런스 파이프라인 (영웅 → 아이템 → 전투 검증 → 보고서), 4코어 약 25분
python3 sim/fill_doc.py  # 09 문서 결과 요약 갱신
python3 -m pytest tests -q
```
