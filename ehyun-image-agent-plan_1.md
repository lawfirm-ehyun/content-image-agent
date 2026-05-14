# 이현 블로그 이미지 에이전트 — Plan (v1.7.3-plan)

> 노션 콘텐츠에 자동으로 이미지 카드 박는 에이전트.
>
> 압축 룰 / 절대 룰 → [CLAUDE.md](CLAUDE.md)
> 운영 계약 / Phase 게이트 → [AGENT_GUIDE.md](AGENT_GUIDE.md)
> 사실/스펙 디테일 → [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)
> Changelog v0.1~v1.6.3 / archive 카드 / paper-only 가드 → [plan_history.md](plan_history.md)

---

## 1. 한 줄 정의

노션 콘텐츠 DB `이미지 필요` 페이지 → LLM이 슬롯 결정 → 카드 자동 생성 + 노션 inline 삽입 + status 변경.

진화 축은 **카드 종류 하나만**. 나머지 (가드, cap, 인프라, 메서드)는 stable.

## 2. 절대 룰

전체 룰 SSOT → [CLAUDE.md](CLAUDE.md) 절대 룰 #1-#8. **룰 변경 시 CLAUDE.md를 먼저 갱신**, plan은 참조만 (drift 방지).

plan 안에서 자주 참조하는 핵심 4개:

1. **사실 정확성 #1** (CLAUDE.md #1) — 사실 필드(숫자/values/labels/source/messages.text/excerpt) 1자도 변경 X. 라벨링 필드(title/headers/cells/scene/mood)는 본문 안 직관 합성 OK.
2. **변호사법 §23** (CLAUDE.md #2) — 키워드 master: `tools/compliance/keywords.py`.
3. **모바일 가독성 40px+** (CLAUDE.md #3) — 본문 40px / 메타 32px.
4. **AI prompt 자연어** (CLAUDE.md #8) — 사실 필드만 `exact_korean_strings` 엄격.

## 3. MVP 흐름

```
[fetch "이미지 필요" 페이지]
        ↓
[LLM analyze: 슬롯 결정 — slot_selection.md 룰 기반]
        ↓
[for each slot]
        ↓
  ┌──── [review_input: 본문 일치 + §23 검사] ────┐
  │                                              │
  │   template path                AI path       │
  │   (chart / table /             (illustration /
  │    timeline / key_points)       kakao_dialogue)
  │        ↓                            ↓        │
  │   Playwright render          gpt-image API   │
  │        ↓                            ↓        │
  │      PNG → WebP                     ↓        │
  └─────────────┬────────────────────────────────┘
                ↓
[Notion file_upload → image block 삽입]
                ↓
[로그 DB row 기록]
                ↓
[status: "이미지 필요" → "발행 필요"]
```

진입점:
- 수동: `uv run python orchestrator.py` (`orchestrator.main()` → `process_database()` 블로그 + 웹 순차)
- 단건: `uv run python scripts/test_phase1.py <page_id> --source <블로그|웹>`
- cron: `orchestrator.main()`이 cron/workflow_dispatch 호출 전제로 작성됨. **단 `.github/workflows/cron.yml` 미작성** (2026-05-14 기준, `.github/workflows/`에 `.gitkeep`만 존재). workflow 파일 작성은 별 트랙 (README Phase 3).

## 4. 카드 카탈로그 (활성 7종)

| 카드 | 종류 | When | 상세 |
|---|---|---|---|
| `simple_table` | 정보형 template | 줄글 enumeration, 2-3 컬럼 표 데이터, 조건→결과 매핑 | [skill](skills/image_types/simple_table.md) |
| `chart` (line/bar/donut/pie) | 정보형 template | 시계열 추이(line) / 카테고리 비교(bar) / 분포(donut·pie) | [skill](skills/image_types/chart.md) |
| `comparison_table` | 정보형 template | 법적 절차/유형 비교 (협의 vs 재판). 다른 법무법인 비교 X (§23) | [skill](skills/image_types/comparison_table.md) |
| `key_points_card` | 정보형 template | 핵심 N가지 / 준비 서류 / 체크리스트 (3-5개) | [skill](skills/image_types/key_points_card.md) |
| `timeline` | 정보형 template | 4-6 순차 단계 (법률 절차 / 소송 흐름) | [skill](skills/image_types/timeline.md) |
| `illustration` | 감성형 AI instant | 도입부 사연/분위기 (라인 일러스트 단일 스타일) | [skill](skills/image_types/illustration.md) |
| `kakao_dialogue` | 감성형 AI thinking | 본문 카톡 대화 시나리오 재현 | [skill](skills/image_types/kakao_dialogue.md) |

**페이지당 mix 룰** → [CLAUDE.md](CLAUDE.md) 절대 룰 #5 (정보형 1-2 + 감성형 1-2 mix / 금지 패턴 명세). mix 알고리즘 → `skills/meta/slot_selection.md`.

**카드 카테고리별 사실 정확성**:
- 정보형 + kakao_dialogue: 본문 1자 변경 X (절대 룰 #1 엄격)
- illustration: scene/mood는 합성 OK. 이미지 안 텍스트 0 강제.

**Phase 4 검토 archive** (운영 데이터로 결정): `stat_highlight` (v1.5 정의 보존), `document_excerpt` (v1.5 정의 보존), `webtoon`, `app_ui_mockup`. spec → [plan_history.md](plan_history.md).

## 5. 활성 운영 가드 (5개 카테고리)

| 가드 | 코드 위치 | 사상 |
|---|---|---|
| **멱등성 + page try/except** | `orchestrator.py` (`get_logged_page_ids`, `process_database` try/except) | 동일 page_id 재처리 자동 skip + page-level 실패는 다음 페이지 진행 |
| **block UUID 검증** | `tools/notion/insert_image_block.py:_verify_ancestor` | LLM 환각으로 다른 페이지에 이미지 박힘 차단 |
| **API rate limit backoff** | `tools/notion/_retry.py` (Notion) + `tools/image/gpt_image_2.py` (OpenAI, tenacity) | 429/5xx 자동 지수 재시도 + 페이지 사이 0.5s sleep |
| **비용 cap (페이지/런/슬롯/analyze/review)** | `tools/limits.py` + `tools/budget.py` | RunBudget 누적, cap 초과 시 즉시 break + 슬롯 폐기 |
| **§23 컴플라이언스** | `tools/compliance/keywords.py` (1차 regex) + `tools/llm/review.py` (2차 LLM) | LLM 호출 전 키워드 차단 (호출당 $0.30 절약) + 본문 일치 + §23 LLM 재검토 |
| (보조) 렌더 안전 검증 | `tools/render/template_render.py` `wait_for_function` + `tools/llm/analyze_content.py:_compress_for_analyze` + 슬롯 0개/review 폐기 로그 | Chart.js·Pretendard 로드 검증, 본문 길이 초과 시 압축 fallback, 폐기 케이스 로그 기록 |

미구현 paper-only 가드 (cron 무인 가동 시 추가 검토) → [plan_history.md](plan_history.md) §2.

## 6. 비용 cap

**상수값 SSOT** → `tools/limits.py` (5개: PER_PAGE / PER_RUN / PER_SLOT_COST / ANALYZE_BUDGET / REVIEW_BUDGET). CLAUDE.md "비용 cap 단계"는 mirror — 값 변경은 `tools/limits.py` → CLAUDE.md → plan 변경 X 순.

**페이지당 평균 비용** (실측 + 예측):
- Phase 2 (정보형만): ~$0.40-0.80
- Phase 3 (정보 + 감성 mix): ~$0.70-1.00 (5/12 e2e 1페이지 4슬롯 $0.96 — illustration 포함)
- 월 비용 (40편 기준): ~$28-40

**안정화 목표**: PER_PAGE $1.20 복귀 — 시점/조건은 §10 미결정 참조.

**비용 분리 추적**: `RunBudget.anthropic_usd` / `openai_usd` 별도 (gpt-image 단가 변동성 대비).

## 7. 카드 추가 절차 (30분 가이드)

새 카드 1종 추가 시 다음 4단계로 끝남 (진화 축 — §1 참조):

1. **`skills/image_types/<name>.md` 작성** — When / Generation method / Variables / Style / Quality criteria. 자연어로.
2. **렌더 path 추가**:
   - **template**: `templates/<name>.html` 작성 + `tools/render/template_render.py` 분기 1개 (이미 generic하면 추가 불필요)
   - **AI**: `tools/render/ai_render.py`에 `_build_<name>_prompt()` 함수 1개 추가 + `render_ai_card` 분기 1개
3. **`orchestrator.SUPPORTED_TYPES`에 `<name>` 추가**. AI면 `AI_CARD_TYPES`에도.
4. **`orchestrator._render_slot`에 분기 1개 추가** (필요시 schema 검증 포함).

추가 작업 (선택):
- `reference_library/<name>/` 시드 1-2장 (AI 카드 톤 합의용)
- 로그 DB `타입` select 옵션은 첫 trigger 시 자동 생성 (5/12 검증됨)

**LLM은 자동으로 새 카드 trigger** — `slot_selection.md` 룰만 작성하면 됨. 별도 코드 등록 없음.

## 8. 기술 스택

상세 → [CLAUDE.md](CLAUDE.md) "기술 스택 한 줄" (의존성 + 모델 + ENV override + Phase 4 검토 모델 포함). plan에는 미러 두지 않음 — drift 방지.

## 9. 인프라

| 파일 | 역할 |
|---|---|
| `orchestrator.py` | cron 진입점 + page/slot 처리 흐름 + try/except |
| `tools/llm/analyze_content.py` | LLM 슬롯 결정 (slot_selection.md inject) |
| `tools/llm/review.py` | 슬롯 input 본문 일치 + §23 검사 |
| `tools/render/template_render.py` | HTML + Playwright 렌더 |
| `tools/render/chart_render.py` | Chart.js sub_type 4종 분기 |
| `tools/render/ai_render.py` | gpt-image 호출 wrapper (illustration / kakao) |
| `tools/image/gpt_image_2.py` | OpenAI client + tenacity backoff + 에러 sanitize |
| `tools/image/webp_converter.py` | PNG → WebP (lossless) |
| `tools/notion/*` | fetch / upload / insert / status / log + retry wrapper |
| `tools/compliance/keywords.py` | §23 키워드 regex master |
| `tools/limits.py` | 비용/타임아웃/모델 상수 단일 source |
| `tools/budget.py` | RunBudget (anthropic/openai 분리 누적) |

## 10. 미결정 사항

> **"Phase 4" 정의**: 운영 안정화 + archive 카드 활성화 + 비용 cap 복귀 단계 (Phase 3 v1.6.4 직후). §12 SDK migration 로드맵은 **병렬 트랙** — SDK migration scope 미결정은 §12.7 참조.

| 항목 | 결정 시점 |
|---|---|
| cron schedule 활성화 (workflow_dispatch → schedule) | `cron.yml` 작성 후 운영자 검수 부담과 함께 결정 (2026-05-14: `cron.yml` 자체 미작성 — §3 참조) |
| chatgpt-image-latest 비교 | OpenAI organization verification 완료 후 (15분 propagate) |
| gpt-image-1.5 콘텐츠별 라우팅 | 5/12 비교에서 라인 일러스트 톤 최고였음. 운영 데이터로 결정. |
| kakao_dialogue OCR Levenshtein 검증 | kakao 실제 trigger 시 추가 (현재 0건). §12.6 subagent 활성화도 이 시점에 연동. |
| Phase 4 검토 카드 (stat_highlight / document_excerpt / webtoon / app_ui_mockup) 활성화 | 운영 데이터 + 콘텐츠 적합도 |
| 페이지 cap $1.20 복귀 | analyze prompt 슬림 + slot_selection 다이어트 후 |
| 실패 알림 채널 (이메일 → Slack/Discord) | 운영 안정화 후 |

## 11. 사용자 사전 작업 체크리스트

완료된 setup (figma 디자인 시스템 / Notion integration / 3개 DB ID·권한 / status 옵션 / Anthropic·OpenAI key / GitHub secret / kakao_dialogue 시드) → 생략. **미완료만**:

- [ ] 이현 로고 svg/png (선택)
- [ ] `reference_library/illustration/` 라인 일러스트 시드 (운영하면서 좋은 결과물 1-2장 저장 권장)
- [ ] OpenAI organization verification (`chatgpt-image-latest` 사용 — §10 미결정 연동)
- [ ] 노션 로그 DB legacy select 옵션 정리 (`table_simple` / `table_comparison` 제거, `출처` 영문 `web`/`blog` 제거 — 한글 통일)

## 12. SDK migration + chart_bar parametric 로드맵 (v1.7.0-plan)

> **한 줄 사상**: "차트는 코드로, 그림은 AI로" — 이미 가진 architecture 그대로. SDK 얹어서 자가 수정 + 차트 4종 → `master_chart.html` 통합 + 2축 parametric.
>
> **목표**: agent loop / hooks / subagents를 들이면서 차트 4 sub-type을 단일 `master_chart`로 통합 + 2축 parametric화. "AI가 결과 보고 자가 수정" + "같은 데이터로 다양한 시각 출력" 동시 검증.
>
> **🔒 Plan freeze (v1.7.3+)**: Week 0 spike 실측 데이터 받기 전까지 추가 refine 없음. mid-checkpoint decision gate / falsifiable Week 4 기준 / composition phase reframing 등 후속 보강은 *그 시점 데이터 보고* 결정. plan은 지도이지 destination이 아님 — 코드 작성 우선.

### 12.1 배경 — SDK 우회의 후유증

v1.6.4까지 `tools/llm/_common.py`가 bundled `claude.exe` subprocess 호출 (옵션 A). 이유는 (a) claude-agent-sdk 0.1.74가 Opus 4.7 호출 불가 (b) skills 위치 충돌. 결과로 얻은 것: Opus 4.7 사용 + `skills/` 레이아웃 유지. 잃은 것:

- **agent loop** — LLM이 결과 보고 재시도 못 함
- **hooks** — §23 게이트가 코드 분기(`tools/llm/review.py`)에 박혀서 policy로 추출 안 됨
- **subagents** — OCR/review 분리 못 함, 메인 context에 혼재

0.2.111+에서 Opus 4.7이 풀린 것으로 보이므로 **제자리 마이그레이션 가능 시점**. 풀 리빌드 X — `orchestrator.main()` + `tools/llm/_common.py` 껍데기만 갈아끼움.

> **Week 0 spike 노트 (2026-05-12, N=4 한계)**: claude-agent-sdk 0.1.77 + Sonnet 4.6 + `max_turns=1 + setting_sources=[]` 가드 하에 SDK 호출이 subprocess 대비 일관 **0.34-0.64x cost** 측정됨 (N=4, `scripts/_spike_sdk.py`). 위 "토큰 비용 3배+" 우려 frame 재측정 트리거. 다만 N 한계 + 합성 본문(`tests/fixtures/spike_sdk_baseline.json`) + cache miss 조건이므로 단정 X. Week 1-2 통합 시 실제 본문 + cache hit 포함 N≥3 재측정 예정.
>
> **Week 1-2 production 측정 (2026-05-13, N=3, `scripts/_spike_n3_cost.py`)**: 블로그 DB 1페이지 (73 compacted blocks, ~5825c 본문) `analyze_content` N=3 → mean **$0.2617**, max $0.3357, min $0.1459, **cache ratio min/max 0.43x** (cache hit 자동 작동). `ANALYZE_BUDGET_USD=$0.80` cap 안전. SDK path는 functional regression 0 — spike fixture에서 사실 데이터(values/rows) 1자 보존 + title/headers 라벨링은 LLM stochastic 변동(절대 룰 #1 허용 영역), review_input passed=True. spike의 0.34-0.64x는 *vs subprocess 비교*, production 0.43x는 *vs same-page cache miss 비교* — 별도 척도.

### 12.2 4주 스코프

| 주차 | 작업 | 결과물 |
|---|---|---|
| Week 0 | SDK spike (§12.4 가드 1) | 4개 검증 항목 통과 |
| Week 1-2 | **claude-agent-sdk 0.1.77 `query()` 직접 호출**로 `tools/llm/_common.py:query_json` 갈아끼움 (subprocess 경로 dead reference). agent loop / hooks / subagents 풀 도입 X — §12.6 "처음부터 다 빼지 말기" 정신. 단발 `query()` 1회 + `max_turns=1` + `setting_sources=[]` 가드 유지. 자가 수정 / 차트 자동화는 Week 3a+ 이후 별도 진입. | SDK 경로로 `analyze_content` + `review_input` 통과. spike fixture e2e (b7fe789) + production 1페이지 N=3 측정 (§12.1). |
| Week 3a | `chart_bar/line/donut/pie.html` 4개 → `master_chart.html` 1개 통합. `ChartLineData/ChartBarData/ChartDonutData` → `ChartSpec` 단일 스키마 (`chart_type` 필드 분기). **회귀 검증 방법**: 4 sub-type 각 sample input 픽스처 1개씩 (`tests/fixtures/chart_*.json`) → pre-refactor 렌더 PNG 저장 → post-refactor 렌더 PNG → SHA 또는 OCR text diff 비교. 차이 0 → 통과. | `master_chart.html` + `ChartSpec` 단일 스키마 + 4 sub-type 회귀 0. |
| Week 3b | `master_chart`에 손잡이 2개 추가: ① `orientation: 'vertical'\|'horizontal'` — **bar/line 적용** (donut/pie는 원형이라 의미 없음, null 허용). ② `emphasis_index: int\|null` — **4 sub-type 공통**. `ChartSpec` / `skills/image_types/chart.md` 동기. donut/pie 전용 axis(`start_angle` / `label_position` / `slice_explode` 등)는 Week 5+ 별도 결정. | bar/line: 2축 곱 = 4-variant. donut/pie: emphasis만 적용. |
| Week 4 | **bar 3회 e2e** (같은 데이터셋, visually distinct 검증 — §12.4 가드 2) + **line/donut/pie 각 1회 e2e** (master_chart 통합 회귀 검증, Phase 3 v1.6.4 결과물과 시각/사실 동일). 총 6회. | bar 2/3 distinct + 비-bar 3종 회귀 통과 → Week 5 진행 |
| 이후 | distinct OK면 Week 4 압력 보고 `master_chart` 손잡이 추가 (schema emerge — 인간이 미리 박지 않음). 미달이면 §12.5 분기. | vocabulary 확장 또는 composition primitive 검토 |

### 12.3 안 하는 것 (확실히)

- ❌ **차트도 gpt-image-2로** — 환각/§23 검증 불가. plan_history v1.6.1 "62.5% → 65.2%" 사고 재발. 차트는 Chart.js 유지.
- ❌ **table/key_points/timeline까지 1개 generic으로 통합** (`generic_infographic.html`) — DOM 본질이 다름 (각각 `<table>`, grid `<div>`, ordered steps). 합치면 슬롯 스키마 가드 깨지고 절대 룰 #1 회귀. *(단, 차트 4 sub-type 통합은 별개 — DOM 동일하므로 §12.2 Week 3a에서 실행)*
- ❌ **illustration/kakao 갈아엎기** — v1.6.4에서 안정. 손대지 않음.

### 12.4 사전 가드

**가드 1 — Week 0 SDK spike (1일)**. 본격 마이그레이션 전 검증:

- claude-agent-sdk 0.2.111+ Opus 4.7 호출 OK
- `exact_korean_strings` 1자도 변경 X 보존 (절대 룰 #1 인프라)
- `token-ledger.ndjson` 비용 계상이 SDK 경로에서도 동일 작동
- skill markdown을 system_prompt에 inject (옵션 A) 가능

→ 4개 중 하나라도 막히면 fallback 3경로 중 spike 결과 보고 선택: **(a)** Opus 4.7 호출 실패 시 → Sonnet 4.6로 진행 / **(b)** skill inject 막힘 시 → 옵션 B (`.claude/skills/`로 이동 + SDK auto-load) 수용 / **(c)** 비용 계상 깨짐 시 → claude.exe wrapper 유지 + SDK는 hooks/subagents만 사용 (하이브리드).

→ **결과 (2026-05-12 spike b7fe789, 2026-05-13 Week 1-2 진입)**: 4개 항목 통과 (SDK 0.1.77 + Sonnet 4.6, `tests/fixtures/spike_sdk_baseline.json` N=4 byte-identical simple_table). 추가로 Week 1-2 진입 시 **Opus 4.7 ping 1회 = success** (subtype=success, cost $0.16, SDK 0.1.77 그대로) — fallback (a) 회피, 0.2.111+ 업그레이드 정당성 부재. token-ledger 비용 계상은 production 본격 통합 후 별도 검증 (`scripts/_spike_n3_cost.py`는 ledger 우회).

**가드 2 — Week 4 합격선** (두 갈래):

- **(a) bar 3회 e2e — parametric distinct**: 같은 데이터셋 → visually distinct 결과 **2/3 이상**. distinct 판정: orientation 변경 OR emphasis 위치 변경 OR 둘 다. 1/3 이하 → "parametric 가설 약함" 신호 → §12.5 분기.
- **(b) line/donut/pie 각 1회 e2e — 통합 회귀**: master_chart 단일 스키마로 렌더한 결과가 Phase 3 v1.6.4 chart_line/donut/pie 결과물과 시각/사실 동일. 차이 발생 시 Week 3a 회귀 검증 누락으로 간주, Week 3a 재진입.

### 12.5 Week 4 결과별 분기

| Week 4 결과 | 다음 단계 |
|---|---|
| distinct 2/3+ | Week 5-6 line/donut/pie 동일 parametric 작업 |
| distinct 1/3 이하 | parametric vocab 확장 X. **composition primitive 검토** (grid cell + callout slot + multi-panel). 25장 레퍼런스의 50-70%는 parametric이 아니라 composition 결정에서 옴 |
| **실제 결과 (2026-05-13, 4fd5aa8/1ece541)**: distinct **3/3 PASS** + 회귀 **4/4 SHA byte-identical**. | **§12.2 "이후" path 진입 (pause)** — Week 5-6 line/donut/pie parametric 즉시 진입 X. production 사용 패턴 누적 대기 (§12.8). |

> 분기 결정 배경 (2026-05-13): Week 4 distinct 검증은 같은 bar 데이터셋의 변형이 시각 분기를 만들어내는지만 검증 — sub_type별 (line/donut/pie) 데이터셋에서 emphasis가 의미 있는 시각 효과를 내는지는 별도 문제. 또한 LLM이 본문에서 orientation/emphasis_index를 얼마나 자주, 적절히 결정하는지는 spike 스크립트로 알 수 없음. parametric vocab 확장 전에 실사용 데이터를 보고 결정 — 80% plan으로 출발이 100% plan보다 빠름 (v1.7.3 freeze 정신 연속).

### 12.6 subagent 분리 기준 (Week 1-2 가이드)

claude-agent-sdk subagent는 자체 context 격리됨. 따라서:

- **stateless task → subagent**: §23 키워드 regex pass (구현됨), 이미지 vision 사실 검증, OCR Levenshtein 검사 (미구현 — kakao 실제 trigger 시 활성화, §10 참조)
- **stateful review → 메인 loop + hook**: "이 차트 에디토리얼 품질" 같은 원본 spec + 추론 맥락 필요한 평가

처음부터 다 subagent로 빼지 말기 — context 부족으로 평가 부실 위험.

### 12.7 미결정 (Week 0 이후 결정)

- ~~claude-agent-sdk 정확 버전 (0.2.111+ 중 어디 고정할지)~~ → **0.1.77 고정 (2026-05-13)**. Opus 4.7 호출 OK + spike 4 checks + production N=3 모두 0.1.77로 통과. 0.2.111+ 업그레이드는 hooks/subagents 풀 도입 필요 시점에 재평가.
- agent loop max iteration cap (비용 폭주 방지) — Week 3a+ agent loop 활성 시점에 결정
- `master_chart` emphasis_index의 시각 표현 (색상 강조 / 라벨 강조 / 둘 다) — **Week 3b/4 결과 (2026-05-13)**: 색상 강조 1개만 ship (line/bar 비강조 = neutral·옅은 mono / donut/pie 비강조 = mono-other). 라벨 강조·다중화는 §12.8 production 사용 패턴 누적 대기.
- donut/pie 전용 axis 후보 (`start_angle` / `label_position` / `slice_explode` 등) — Week 4 결과 받음 (distinct 3/3 + 회귀 0/4), **§12.8 pause 채택**. 누적 대기.
- bar/line `orientation`의 3번째 후보 (예: `diagonal` / 면적 chart 회전 등) — 같은 §12.8 대기 (현재 vertical/horizontal 2개로 충분 여부 누적 검증).
- ~~`tools/llm/models.py:CLAUDE_EXE` dead reference cleanup 시점~~ → **완료 (2026-05-13)**. 변수 제거 + `PROJECT_CONTEXT.md` §3 동기화.

### 12.8 §12.2 "이후" pause — Week 5-6 진입 조건 (2026-05-13 신설)

Week 4 distinct 3/3 + 회귀 0/4 PASS 후에도 parametric vocab 확장을 **즉시 진입 X**. 진입 조건 충족 후 재개:

**진입 트리거 (둘 중 하나라도 충족):**
1. **production page N ≥ 10** 처리 + `ChartSpec.emphasis_index != None` 사용률이 ≥ 30% (LLM이 본문에서 실제로 강조 신호를 자주 추출하는지 = parametric 손잡이가 production에서 의미 있는지 신호)
2. **본문 패턴이 새 axis 필요성을 명시적으로 신호** — 예: 시계열 강조 위치가 단일 인덱스로 부족 (구간 강조), donut/pie에서 slice 분리 강조 요구, line chart `area fill` 시각 톤 요구

> N=10은 cold-start 기준. 실제 threshold는 누적 후 패턴 보고 재조정. *80% plan 정신* — 정확한 cutoff는 데이터 보고.

**누적 메커니즘 (별 인프라 X) — 2026-05-14 drift 정정:**
- 신설 시점 plan은 `.bkit/runtime/token-ledger.ndjson`을 per-slot 기록처로 잘못 지목. 실제는 **Notion 로그 DB**(`NOTION_DB_LOG`)의 `입력(JSON)` rich_text가 `extracted_data` 전체(즉 `orientation`/`emphasis_index` 포함)를 직렬화해 보관(`tools/notion/log_metadata.py`). `.bkit/runtime/token-ledger.ndjson`은 bkit/CC 하네스의 turn 단위 토큰 텔레메트리로 슬롯 데이터와 무관.
- 따라서 트리거 평가 시 별도 emit 추가 **불필요** — Notion 로그 DB query만으로 sub_type / orientation / emphasis_index 집계 가능.
- **현재(2026-05-13) 코드 변경 0**: 진입 트리거 검토 시점에 결정.

**진입 후 (= 미래 Week 5-6) 작업 윤곽 (확정 X, 메모만):**
- line/donut/pie 각 sub_type 단일 series 데이터셋으로 emphasis 시각 분기 검증 (bar Week 3b/4 패턴 답습)
- §12.7 미결정 axis 후보 중 production 신호가 가장 강한 1개부터 (3개 다 미리 박지 X — 가드 #1 정신 연속)
- composition primitive 검토는 distinct 미달 시그널 없으면 별 트랙으로 보류

**pause 깨는 신호 (긴급 진입):**
- production 본문에서 chart 슬롯이 시각 단조로움으로 사용자 피드백 발생 (Week 4 distinct가 lab에서 PASS여도 production에서 약하면 거기서 끊고 진입)
- LLM이 본문 강조를 못 잡거나 잘못 잡아 chart 폐기율 상승 (orientation/emphasis_index 결정 품질 문제)
- 위 신호 발견 시 N 조건 충족 전이라도 Week 5-6 진입 검토

### 12.8.1 1차 평가 (2026-05-14)

a644661 시점 Notion 로그 DB(`NOTION_DB_LOG`) 전수 query (67 row, 9 unique page).

| 항목 | 값 | 트리거 임계 | 판정 |
|---|---|---|---|
| 처리된 unique 페이지 | 9 | — | — |
| chart 슬롯 로그 row | 9 | — | — |
| **chart 슬롯이 박힌 unique 페이지** | **1** | N ≥ 10 | **MISS (gap 9)** |
| chart sub_type 분포 | `line` 9/9 | — | bar/donut/pie production 사용례 0 |
| `emphasis_index != None` 사용률 | 0/9 = **0%** | ≥ 30% | **MISS (단, 9 row 모두 Week 3b 박기 전 input — 의미 0)** |
| `orientation` 분포 | 9/9 null (= vertical default) | — | Week 3b 박기 전 input |
| 본문 신호(다중 강조 / slice 분리 / area fill 요구) | 0건 | — | 없음 |
| 긴급 신호(시각 단조 피드백 / 폐기율 급증) | 0건 | — | 없음 |

**판정**: §12.2 "이후" **pause 계속**. N=1 chart page, 트리거 1·2 모두 MISS, 긴급 신호 0.

**다음 평가 시점**: chart 슬롯이 박힌 unique production 페이지 **누적 N ≥ 10** 도달 시 (현재 1 → 9개 추가 누적 필요). 누적 속도가 느린 분야이므로 시간 기반 cron 평가 X, 이벤트 기반(N 도달 시) 1회.

**메모 (§12.8 본문엔 미박음, 관찰만)**:
- 9 chart row가 1 page에서 발생 → 동일 페이지가 schema 진화 동안 여러 차례 재처리됨(테스트 베드). 정상 production에선 page당 chart 1-3 row 예상.
- chart 외 production 슬롯 분포: `simple_table 52 / key_points_card 3 / timeline 1 / illustration 1 / comparison_table 1`. simple_table 압도. chart 사용률 낮은 콘텐츠 특성 = §12.8 누적 속도 느릴 가능성 시사. Week 5-6 진입 결정 보수적으로 가능.

### 12.8.2 2차 평가 (2026-05-14, 1차 직후)

2fec81a baseline에서 동일 query 재실행. **테스트 베드 필터** 적용:
- 정의: `page당 chart row ≥ 4` AND `해당 page 모든 chart row가 pre-Week 3b (orientation=null)`
- 의도: schema 진화 동안 동일 페이지를 반복 재처리한 케이스는 production 신호로 계산 X. 자연 production은 page당 chart 1-3 row가 정상이므로 ≥4는 비정상 누적 신호.
- 향후 자연 production 누적되면 정의 재검토 (현재는 1차에서 관찰된 단일 패턴 기반).

| 항목 | 1차 (2026-05-14) | 2차 (2026-05-14, 필터 적용) | 트리거 임계 | 판정 |
|---|---|---|---|---|
| 처리된 unique 페이지 | 9 | 9 | — | 변동 0 (간격 분 단위, production 미진행) |
| chart 로그 row | 9 | 9 | — | 변동 0 |
| chart unique 페이지 (필터 전) | 1 | 1 | — | — |
| **chart 자연 production 페이지 (테스트 베드 제외)** | — | **0** | N ≥ 10 | **MISS (gap 10)** |
| 테스트 베드 페이지 | — | 1 (`35943f95...`, 9 line row, all pre-W3b) | — | 정확히 1차의 그 페이지 |
| post-Week 3b chart row | — | **0** | — | emphasis/orientation 사용률 평가 불가 |
| 본문 axis 신호 | 0건 | 0건 | — | 없음 |
| 긴급 신호 | 0건 | 0건 | — | 없음 |

**판정**: §12.2 "이후" **pause 계속**. 1차보다 더 엄격한 판정 (N=0 자연 chart page). 트리거 1·2 모두 MISS, 긴급 신호 0.

**Trigger 재검토 (시기상조 결론)**: 사용자 guide("평가 2-3회 누적 후 trigger 재검토 가능, chart 자연 빈도 너무 낮으면 N=10 over-conservative")는 자연 빈도 측정 가능 후에 의미 있음. 현재 자연 chart 페이지 0 → 자연 빈도 측정 자체 불가 → trigger 갱신 시기상조. **N=10 임계 유지**.

**다음 평가 시점**: 다음 두 조건 중 하나 충족 시:
- 자연 chart 페이지 (테스트 베드 제외) **누적 N ≥ 5** 도달 시 (10 임계의 절반 — chart 빈도 자체를 측정할 첫 실측 데이터점)
- production 페이지 (모든 슬롯 포함) **30+ 추가 누적** 시 (현재 9 → 39+) chart 자연 빈도 추정 가능 시점

둘 다 이벤트 기반. 시간 기반 cron 평가 X. 다음 평가가 trigger 자체 재검토 의미 있는 첫 시점.

### 12.8.3 평가 트리거 cron 의존 (2026-05-14 신설)

§12.8.1/12.8.2 다음 평가 시점("자연 chart 페이지 N ≥ 5" / "production 페이지 30+ 추가 누적")은 **production page 자연 누적**에 의존. 이 누적은 cron schedule 가동을 전제로 함.

**현재 상태 (2026-05-14)**:
- `.github/workflows/cron.yml` **미작성** (§3 참조 — `.gitkeep`만 존재).
- 따라서 production page 누적은 **수동 trigger 빈도에 종속** (`uv run python orchestrator.py` 또는 `scripts/test_phase1.py` 직접 실행).
- cron.yml 작성 + schedule 활성화 = **§12.8 평가의 prerequisite**.

**함의**:
- cron.yml 작성 + schedule 활성화 전까지 §12.8 다음 평가 시점은 수동 실행 빈도 비례.
- §12.8 트리거 정의(N=10, emphasis ≥30%) 자체 갱신은 자연 누적 데이터 없이 시기상조 — cron 가동 후 자연 빈도 측정 후 결정.
- cron 작성·schedule 활성화·운영자 검수 부담 결정은 별 트랙 (§10 미결정 항목). 이 §12.8 트리거 평가 트랙과 직교.

## 13. SEO + a11y 메타데이터 (alt_text + filename_slug) — v1.7.2-plan

> **한 줄 사상**: LLM이 이미 카드의 모든 사실을 알고 있으므로 alt 한 줄 생성은 0 marginal. Notion = staging + 인간 검수 → 발행 path니까 caption→alt 매핑 검증 불필요, Notion *어디든* 들어가기만 하면 됨.
>
> **§12와 독립** — SDK migration 전/후 무관, 현재 `claude.exe` 경로에서 그대로 ship 가능. Week 0 SDK spike *전*에 끼우기로 결정.

### 13.1 목표

- **alt_text**: SEO 검색 노출 + a11y 스크린리더 지원 (한국 법률 콘텐츠 a11y 영역 의무에 가까움)
- **filename_slug**: 발행 시 CDN URL 의미 있는 파일명

### 13.2 적용 범위

7종 카드 모두 (`simple_table` / `chart` 4 sub-type / `comparison_table` / `key_points_card` / `timeline` / `illustration` / `kakao_dialogue`). 슬롯 단위 1쌍.

### 13.3 데이터 흐름

```
[analyze_content]
  └─ LLM이 alt_text + filename_slug 생성 (parametric 결정 전, data-only)
        ↓
[review_input]
  └─ alt_text 사실 일치 + §23 검사 (filename_slug는 길이/regex만)
        ↓
[Notion 삽입]
  ├─ image block
  └─ callout block (💡) 1개 — 이미지 직후 (인간 검수자 발견성 ↑)
        Content: [ALT] {alt_text}
                 [FILENAME] {filename_slug}.webp
```

### 13.4 가드

| 가드 | 적용 |
|---|---|
| 사실 정확성 #1 | 슬롯 데이터 안 내용만 기술. alt도 `review.py` 검사 대상 (라벨링 영역) |
| §23 컴플라이언스 | alt에 절대성/과장/시간 압박/비교 광고 표현 X. `tools/compliance/keywords.py` regex pass 적용 |
| 길이 제한 | `alt_text` 125자 이하 (Google 권장치), `filename_slug` 80자 이하 |
| `filename_slug` 형식 | snake_case, 영문 소문자/숫자/`_`만 (한글 X — CDN URL 호환성) |

### 13.5 작업 항목 (예상 1-2일)

1. 슬롯 스키마 7종 모두에 `alt_text: str`, `filename_slug: str` 필드 추가
2. `skills/meta/slot_selection.md` 또는 `analyze_content` system prompt에 생성 룰 추가 (한국어 125자 이하 / 차트 핵심 인사이트 1개 / 출처 포함 가능)
3. `tools/llm/review.py` alt_text 검사 항목 추가 (§23 + 본문 일치)
4. validator 추가 (길이 / filename regex) — `tools/limits.py` 또는 dataclass `__post_init__`
5. `tools/notion/insert_image_block.py` callout block 1개 삽입 로직 (image block 직후)
6. 1페이지 e2e 검증 — 7종 카드 중 활성 슬롯에 callout이 정확히 들어가는지

### 13.6 §12와의 관계

- 완전 독립 트랙. SDK migration 전/후 어느 쪽에서도 작동
- §12 Week 3b parametric 결정(`orientation` / `emphasis_index`)은 alt에 반영 X — alt는 **data-only**, 시각 강조 묘사 X
- §12 Week 1-2 SDK 마이그레이션 시 검증 항목: 새 SDK 경로에서도 `analyze_content`가 `alt_text` / `filename_slug`를 동일하게 emit하는지

### 13.7 미결정

- Notion 형식 — callout 채택했으나 검수자 워크플로우 1주일 운영 후 재검토 (caption / paragraph block 비교)
- `filename_slug` 한글→영문 변환 룰 — 첫 PR은 LLM이 영문 키워드 기반 생성 (음역 X). 운영 후 결정.
- 7종 카드 *공통* 룰 vs *카드별* 룰 — 첫 PR은 공통. illustration처럼 데이터 없는 카드는 prompt에 별도 가이드 필요할 수 있음.

---

## Changelog

- **v1.7.4-plan** (2026-05-13): §12.2 Week 4 종결 + §12.2 "이후" path 진입 (pause). **plan only — 코드는 4fd5aa8/1ece541에서 이미 ship.** 배경: Week 4 distinct 3/3 + 회귀 0/4 모두 PASS (lab 검증 OK)이나 (a) sub_type별 production 데이터셋에서 emphasis 의미 있는지는 별 검증, (b) LLM이 본문에서 orientation/emphasis_index를 실제로 자주·적절히 결정하는지는 spike로 알 수 없음. parametric vocab 즉시 확장 X, production 사용 패턴 누적 대기. **갱신 위치**: §12.5 표에 실제 결과 row 추가 + §12.7 미결정 항목 (emphasis 다중화 / donut·pie axis 후보 / orientation 3번째) status 갱신 + 새 §12.8 — Week 5-6 진입 트리거 (N≥10 + emphasis 사용률 ≥30% OR 본문 패턴 신호) + 누적 메커니즘 (기존 token-ledger 확장, 새 시스템 X) + 긴급 진입 신호 명시. *80% plan 정신 (v1.7.3 freeze) 연속*. 다음 plan 변경은 production page 누적 후.

- **v1.7.3-plan** (2026-05-12): §12.4 Week 0 spike fallback 3경로 1줄 enumerate (Sonnet 4.6 / 옵션 B skills 이동 / claude.exe + SDK 하이브리드). **Plan freeze 선언** — mid-checkpoint decision gate, falsifiable Week 4 기준, §12.5 composition phase reframing 등 후속 보강은 Week 0 spike 실측 데이터 받기 전까지 보류. 배경: plan-fixing이 회피 행동(procrastination dressed as rigor)으로 전환되는 패턴 감지. 80% plan으로 출발이 100% plan보다 빠름. 다음 plan 변경은 1주 코드 작업 후 재검토.

- **v1.7.2-plan** (2026-05-12): §13 SEO + a11y 메타데이터 트랙 신설. **plan only — 코드는 별도 PR**. 배경: Notion = staging + 인간 검수 → 발행 path 확인 (caption→HTML alt 매핑 검증 불필요). alt_text(125자, SEO+a11y) + filename_slug(snake_case 영문, CDN URL) 슬롯 1쌍 LLM 생성. Notion 형식: 이미지 직후 callout block 1개 (`[ALT] ... [FILENAME] ...`). 7종 카드 공통 적용. §12 SDK migration과 완전 독립 — Week 0 spike 전 standalone PR로 ship. 가드: 사실 정확성 #1 + §23 + 길이/regex validator.

- **v1.7.1-plan** (2026-05-12): plan 문서 정리. **plan only — 코드/스코프 변경 X**.
  - **A. CLAUDE.md 중복 제거 (drift source 차단)**: §2 절대 룰 / §4 페이지당 mix / §6 비용 cap 상수값 / §8 기술 스택 — 모두 CLAUDE.md를 SSOT로 위임, plan은 인덱스/cross-ref만.
  - **B. drift-prone 참조 제거**: §7 line 50 reference 제거.
  - **C. 내부 redundancy**: §1+§7 "진화 축" 중복 → §7에서 §1 cross-ref.
  - **D. 모순 / stale 해소**: §10 "Phase 4" 의미 명확화 (= 운영 안정화 단계, §12 SDK migration과 병렬 트랙) + §12.6 OCR 예시에 "미구현" 명시 + §10 OCR row에 §12.6 cross-ref.
  - **E. 완료 history 압축**: §11 사용자 사전 작업 체크리스트 — 완료 setup 생략, 미완료 4건만 유지.
  - plan 약 273줄 → 약 240줄.

- **v1.7.0-plan** (2026-05-12): §12 SDK migration + 차트 통합/parametric 로드맵 신설. **plan only — 코드 변경 X.** 배경: SDK 우회(옵션 A)의 후유증(agent loop / hooks / subagents 부재) 진단 + 4주 스코프 확정 (Week 0 spike → Week 1-2 SDK 마이그레이션 → **Week 3a 차트 4종 → `master_chart.html` 단일 통합 (회귀 검증: sample input PNG SHA/OCR diff = 0) → Week 3b 2축 parametric (orientation은 bar/line만, emphasis_index는 4 sub-type 공통)** → Week 4 bar 3회 distinct 검증 + line/donut/pie 각 1회 통합 회귀 검증, 총 6회). 차트 통합은 4 sub-type이 모두 canvas + Chart.js로 DOM 동일하므로 허용; table/key_points/timeline 통합은 DOM 본질 다르므로 거부. "차트도 gpt-image-2로 / 비차트까지 generic 통합" 등 절대 룰 #1 회귀 항목 명시 거부. Week 4 결과 미달 시 composition primitive 분기 예약. donut/pie 전용 axis는 Week 5+ 별도 결정 (미결정).

- **v1.6.4** (2026-05-12): 이미지 모델 5종 비교 + default `gpt-image-2-2026-04-21` 채택
  - **OpenAI 가용 모델 9종 발견**: `chatgpt-image-latest` (org verification 필요), `gpt-image-1`, `gpt-image-1-mini`, `gpt-image-1.5`, `gpt-image-2`, `gpt-image-2-2026-04-21`, `sora-2`, `sora-2-pro`, `dall-e-2/3`.
  - **5종 라인 일러스트 비교** (동일 prompt, 1024x1024 medium):
    - `gpt-image-1`: ❌ 한글 텍스트 환각 (§19.16 위반)
    - `gpt-image-1.5`: ★★★★★ 라인 톤·accent·일관성 최고 (Phase 4 검토)
    - `gpt-image-2-2026-04-21`: ★★★ 안정적 (default 채택)
    - `chatgpt-image-latest`: ❌ org verification 필요
  - **default 결정**: `gpt-image-2-2026-04-21` (최신 + 안정). `gpt-image-1.5`는 Phase 4 콘텐츠별 라우팅 검토.
  - **`.env` ENV**: `OPENAI_IMAGE_MODEL_INSTANT` / `OPENAI_IMAGE_MODEL_THINKING` = `gpt-image-2-2026-04-21`
  - **plan v1.6.4 다이어트**: 본 파일 2372줄 → 약 300줄. Changelog v0.1~v1.6.3, archive 카드 spec (stat_highlight v1.5, document_excerpt v1.5), paper-only 가드 (§19.10/14/16/17), Phase 2/3 통과 체크리스트 모두 [plan_history.md](plan_history.md)로 이관. 활성 plan은 사상·원칙·MVP 흐름·카드 카탈로그·활성 가드·비용 cap·카드 추가 절차만 유지.

이전 changelog (v0.1 ~ v1.6.3) → [plan_history.md](plan_history.md) §4
