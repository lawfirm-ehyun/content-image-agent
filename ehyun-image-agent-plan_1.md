# 이현 블로그 이미지 에이전트 — Plan (v1.8.0-plan)

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

진입점 (v1.8 — Phase 4 진입 시 sweep 폐기, fan-out only. 사용자 컨펌 2026-05-14):
- ~~수동 sweep: `uv run python orchestrator.py` (인자 없음)~~ → **Phase 4.1 Do 단계에서 argparse 분기 제거 예정**. 로컬 운영도 list → page-id 호출로 일원화.
- list 모드: `uv run python orchestrator.py --mode list` — "이미지 필요" 페이지(블로그 + 웹, 멱등성 filter 적용)를 `[{"page_id": "...", "source": "블로그"|"웹"}, ...]` JSON 으로 stdout 출력. cron fetch job 이 캡처해 matrix include 로 fan-out. 로컬에서도 동일 명령으로 페이지 목록 미리보기.
- 단일 페이지: `uv run python orchestrator.py --page-id <id> --source <블로그|웹>` — matrix process job 이 cell 마다 1회 호출. 자체 RunBudget(`PER_RUN_CAP_USD`) + 멱등성 + page-level try/except + per-page cap 모두 유지. **Phase 4 이후 주 entry point**.
- 단건 수동 (legacy): `uv run python scripts/test_phase1.py <page_id> --source <블로그|웹>`. Phase 4 진입 시 deprecated 표시만, 즉시 삭제 X.
- cron: **`.github/workflows/cron.yml` 2-step matrix fan-out (2026-05-14 갱신)** — `workflow_dispatch` 만 가동, `schedule` 미가동 (§10 미결정 결정 후 활성화).
  - **Job A `fetch`** (timeout 5분): checkout / setup-uv / `uv sync` 후 `uv run python orchestrator.py --mode list` 실행 → `outputs.pages` 로 JSON expose. env: `NOTION_TOKEN`, `NOTION_DB_BLOG`, `NOTION_DB_WEB`, `NOTION_DB_LOG`.
  - **Job B `process`** (timeout 15분): `needs: fetch` + `if: needs.fetch.outputs.pages != '[]'`. `strategy.matrix.include: ${{ fromJSON(needs.fetch.outputs.pages) }}` + `fail-fast: false` + `max-parallel: 5` (Notion/OpenAI rate-limit 보호). cell 마다 checkout / setup-uv / `uv sync` / `playwright install --with-deps chromium` / `bash scripts/download_fonts.sh` / `uv run python orchestrator.py --page-id "${{ matrix.page_id }}" --source "${{ matrix.source }}"`. env: 기존 cron.yml 과 동일 (`NOTION_TOKEN`, `NOTION_DB_BLOG`, `NOTION_DB_WEB`, `NOTION_DB_LOG`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` 필수 + `OPENAI_IMAGE_MODEL_INSTANT/THINKING` 선택).
  - **`PER_RUN_CAP_USD` 의미 변화**: 기존 단일 job 에서는 블로그 + 웹 sweep 누적 cap 이었으나, matrix 에서는 **cell 1개당 cap** 으로 작동 (각 cell 이 별 process). 총 spend = pages × `PER_PAGE_CAP_USD` (worst case). max-parallel 5 + `_DEFAULT_BATCH_LIMIT = 5` per-DB 로 한 run 당 페이지 10개 cap 자연 제한.
  - 사용자 별 작업: GitHub repo Settings → Secrets and variables → Actions 에 secret 박기 (변경 없음).

## 4. 카드 카탈로그 (활성 7종, v1.8 — illustration → ai_visual 전환 진행 중)

| 카드 | 종류 | When | 상세 |
|---|---|---|---|
| `simple_table` | 정보형 template | 줄글 enumeration, 2-3 컬럼 표 데이터, 조건→결과 매핑 | [skill](skills/image_types/simple_table.md) |
| `chart` (line/bar/donut/pie) | 정보형 template | 시계열 추이(line) / 카테고리 비교(bar) / 분포(donut·pie) | [skill](skills/image_types/chart.md) |
| `comparison_table` | 정보형 template | 법적 절차/유형 비교 (협의 vs 재판). 다른 법무법인 비교 X (§23) | [skill](skills/image_types/comparison_table.md) |
| `key_points_card` | 정보형 template | 핵심 N가지 / 준비 서류 / 체크리스트 (3-5개) | [skill](skills/image_types/key_points_card.md) |
| `timeline` | 정보형 template | 4-6 순차 단계 (법률 절차 / 소송 흐름) | [skill](skills/image_types/timeline.md) |
| `ai_visual` ★ Phase 4.2 신설 | 감성형 AI | 도입부 사연/분위기 / 콘텐츠 전환부 호흡 분기. LLM 이 본문 보고 [Visual Styles Library](docs/visual_styles_library_v1.md) 5종 중 best fit 결정 | §14 + [docs/visual_styles_library_v1.md](docs/visual_styles_library_v1.md) |
| `kakao_dialogue` | 감성형 AI thinking | 본문 카톡 대화 시나리오 재현 | [skill](skills/image_types/kakao_dialogue.md) |
| ~~`illustration`~~ deprecated (v1.8) | — | `ai_visual.visual_style=point_color_line` 로 흡수. 운영 인지 후 skill/code 제거 | §14.1 |

**페이지당 mix 룰** → [CLAUDE.md](CLAUDE.md) 절대 룰 #5 + §14.5 슬롯 3 cap (v1.8 하향). mix 알고리즘 → `skills/meta/slot_selection.md` (Phase 4.2 Do 단계 갱신 예정).

**카드 카테고리별 사실 정확성**:
- 정보형 + kakao_dialogue: 본문 1자 변경 X (절대 룰 #1 엄격)
- ai_visual: scene/mood/accent_target 은 합성 OK. 이미지 안 텍스트 0 강제 (vision 검증 = §19.16 Phase 4.3 진입 트리거).

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

> **"Phase 4" 정의 (v1.8 갱신)**: 운영 안정화 + **감성형 카드 사상 재설계 (illustration → ai_visual + Visual Styles Library)** + **토스피드 톤 정합 (정보형 light gray 배경 fix)** + **vision OCR 텍스트 환각 검증 (§19.16 실구현)** + archive 카드 활성화 + 비용 cap 복귀 단계. 상세 §14. §12 SDK migration 로드맵은 **병렬 트랙** — SDK migration scope 미결정은 §12.7 참조.

| 항목 | 결정 시점 |
|---|---|
| cron schedule 활성화 (workflow_dispatch → schedule) | `cron.yml` 2-step matrix fan-out 작성 완료 (2026-05-14, `workflow_dispatch` only — §3 참조). `schedule` 라인 추가는 운영자 검수 부담 결정과 함께 별 트랙. |
| chatgpt-image-latest 비교 | OpenAI organization verification 완료 후 (15분 propagate) |
| gpt-image-1.5 콘텐츠별 라우팅 | 5/12 비교에서 라인 일러스트 톤 최고였음. 운영 데이터로 결정. Visual Styles Library (§14.2) `point_color_line` 운영 1주 후 비교 데이터 확보. |
| kakao_dialogue OCR Levenshtein 검증 | kakao 실제 trigger 시 추가 (현재 0건). §12.6 subagent 활성화도 이 시점에 연동. §19.16 Phase 4.3 vision review 인프라와 연동. |
| Phase 4 검토 카드 (stat_highlight / document_excerpt / webtoon / app_ui_mockup) 활성화 | 운영 데이터 + 콘텐츠 적합도. v1.8 `ai_visual` 가 일부 use-case 흡수 가능성 있어 활성화 보류. |
| 페이지 cap $1.20 복귀 | analyze prompt 슬림 + slot_selection 다이어트 + **슬롯 3 cap (v1.8, §14.5)** 후 재측정. |
| 실패 알림 채널 (이메일 → Slack/Discord) | 운영 안정화 후 |
| **v1.8 신규** — vision review 모델 실측 spike (Sonnet 4.6 vision, 사용자 컨펌 2026-05-14) | Phase 4.3 Design 첫 작업. 한글 OCR 정확도 / latency / cost 1페이지 실측 후 PER_SLOT_VISION_COST cap 결정. |
| **v1.8 신규** — `quality=high` (cinematic_three_frame) 실비 vs 추정 ($0.25/장) 차이 | Phase 4.2 Do 첫 5건 e2e 후. PER_SLOT_COST_CAP_USD ($0.30) 안전 마진 결정. |
| **v1.8 신규** — reference image 의 LLM 매칭 품질 영향 | Phase 4.2 Do 1주 운영 후 (reference 있는 스타일 vs 없는 스타일 폐기율 비교). |
| **v1.8 신규** — `ai_visual` 슬롯 2개 trigger 시 같은 visual_style 연속 허용 여부 | Phase 4.2 Do — §19.17 mix 룰 갱신과 연동. |
| **v1.8 신규** — vision input path = anthropic SDK 별 path (사용자 컨펌 2026-05-18) | claude-agent-sdk 0.1.77 ContentBlock ImageBlock 부재 사유 (`types.py:992-999`). plan §12 SDK 통일 결정과 직교. vision_review.py 가 anthropic.Anthropic().messages.create() 직접 호출. token-ledger 환산 path 신설 사유. |

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
- `.github/workflows/cron.yml` **2-step matrix fan-out 작성 완료** (§3 참조) — `workflow_dispatch` 만 가동, `schedule` 미가동. 페이지 단위 fan-out 으로 wall-clock = max(page time), 페이지 수 N 무관 (직전 단일 job 구조에서는 N=3 시 20분 timeout 초과로 cancel 발생).
- 따라서 production page 누적은 **수동 trigger 빈도에 종속** (GitHub Actions UI "Run workflow" 또는 로컬 `uv run python orchestrator.py` / `scripts/test_phase1.py`).
- `schedule` 활성화 = **§12.8 평가의 prerequisite** (자연 누적 측정 위해).

**함의**:
- `schedule` 활성화 전까지 §12.8 다음 평가 시점은 수동 실행 빈도 비례.
- §12.8 트리거 정의(N=10, emphasis ≥30%) 자체 갱신은 자연 누적 데이터 없이 시기상조 — schedule 가동 후 자연 빈도 측정 후 결정.
- `schedule` 활성화·운영자 검수 부담 결정은 별 트랙 (§10 미결정 항목). 이 §12.8 트리거 평가 트랙과 직교.

## 13. SEO + a11y 메타데이터 (alt_text caption) — v1.9-plan

> **한 줄 사상**: LLM이 이미 카드의 모든 사실을 알고 있으므로 alt 한 줄 생성은 0 marginal. Notion image caption에 **alt 추천문** 으로 박고, **인간 검수자가 발행 시 alt 최종 결정** (caption 그대로 옮기거나 다듬어 사용). caption→alt 매핑 자동화 X — 검수자 손에 좋은 시드 한 줄 제공이 목표.
>
> **§12와 독립** — SDK migration 전/후 무관, 현재 `claude.exe` 경로에서 그대로 ship 가능.
>
> **v1.7.2 → v1.9 변경 (2026-05-19)**: filename_slug 트랙 드롭 / callout block → image caption only / 길이 125자 → 80자 (한국어 SEO 정합) / 7종 alt 룰 추가 / SEO 룰 6개 + 카드별 패턴 6개 명시.

### 13.1 목표

- **alt_text caption**: 발행 시 검수자가 그대로 옮길 수 있는 SEO/a11y 최적화 추천문. 한국어 80자 이하, target keyword 1회 자연스럽게 포함.
- **filename_slug**: 이번 트랙 드롭 (caption-only 결정에 따라 노션에 들어갈 자리 없음). 향후 CDN URL 트랙 부활 시 재논의.

### 13.2 적용 범위

7종 카드 모두 (`simple_table` / `chart` 4 sub-type / `comparison_table` / `key_points_card` / `timeline` / `ai_visual` / `kakao_dialogue`). 슬롯당 alt_text 1개.

### 13.3 데이터 흐름

```
[fetch_pages_by_status] page.title 함께 추출
       ↓
[analyze_content(blocks, page_title)]
  └─ LLM이 7종 카드 모두 extracted_data.alt_text 생성
       (data-only / parametric 결정 전 / target keyword 본문 제목에서 추출)
       ↓
[review_input(slot_type, slot_data, page_text, page_title)]
  └─ alt_text 사실 일치 + 길이 + target keyword + §23 검사
       ↓
[orchestrator] alt 길이/빈값 가드 → alt_text_status 결정
       ↓
[insert_image_block(caption=alt_text)]
  └─ Notion image block.caption 으로 박힘
       (검수자가 발행 시 alt 속성으로 옮김 — 자동 매핑 X)
```

### 13.4 가드

| 가드 | 적용 |
|---|---|
| 사실 정확성 #1 | alt는 카드 데이터/본문 안에서 합성 (라벨링 영역). 본문에 없는 사실/숫자/주체 삽입 X. `review.py` 검사 대상. |
| §23 컴플라이언스 | alt에 절대성/과장/시간 압박/비교 광고 표현 X. `tools/compliance/keywords.py` regex pass 가 `_collect_strings` 재귀로 자동 흡수. |
| 길이 제한 | `ALT_TEXT_MAX_CHARS = 80` (한국어 정보 밀도 ↑ — 영문 125자 ≈ 한국어 60-80자). |
| 빈값 정책 | LLM 생성 실패 / validator 초과 시 caption 생략, 슬롯은 살림. `alt_text_status` 로그로 추적 → 1주 운영 후 폐기 전환 재검토. |

### 13.5 SEO 생성 룰 (7개 — `slot_selection.md` 와 `analyze_content` system prompt)

1. **한국어 80자 이하**. 초과 시 review.py 가 슬롯 폐기 또는 caption 생략 분기.
2. **Front-load 키워드** — 핵심 명사를 앞에 배치. 서술문 prefix 지양 ("다음 표는 ~을 정리한" X).
3. **페이지 target keyword 1회 자연스럽게 포함** — `page_title` 의 핵심 명사 1회. stuffing(2회+) 금지.
4. **본문 단순 반복 X** — 카드 안 텍스트/본문 문장 통째 복붙 X. 카드가 표현하는 *관계/추이/패턴/주제* 묘사. (Levenshtein 거리 5 이하 시 review.py 경고)
5. **자기지시 단어 X** — "이미지" / "그림" / "사진" / "차트" / "표" 같은 자기 메타 단어 사용 X (SEO 안티패턴, "차트"는 데이터 추이 묘사로 대체).
6. **페이지 안 alt 중복 X** — 한 페이지 슬롯 N개의 alt 가 서로 달라야 함. orchestrator 가 페이지 단위 set 검사.
7. **ASCII 기호만 (v1.9.1, 2026-05-19 e2e 후 추가)** — em dash, en dash, 화살표 (→ ← ↔), bullet (· •), 줄임표 (…), smart quotes, 「」『』 사용 X. 한글/영문/숫자/공백/쉼표(,)/마침표(.)/괄호(())/하이픈(-) 만 허용. **운영 안전** — 검수자가 caption 을 다른 CMS 로 옮길 때 깨짐 방지 + Google word separator 정상 분해. LLM 1차 차단 + `orchestrator._sanitize_alt()` 가 caption 박히기 전 deterministic 안전망 (em dash → 쉼표, 화살표 → 공백 등 치환 + 공백/구두점 collapse).

### 13.6 카드별 패턴 (6개 — `slot_selection.md` 출력 형식 섹션)

| 카드 | alt 패턴 |
|---|---|
| `chart` | "[주제] [기간] 추이 — [시작값]에서 [끝값]로 [방향]" 예: "이혼소송 접수 2021-2024 추이, 2.9만→3.4만 증가" |
| `simple_table` / `comparison_table` | "[주제] [N]가지 [축]" 예: "세입자 권리 4가지 핵심 정리" |
| `key_points_card` | "[주제] 핵심 [N]가지" 예: "음주운전 면허정지 대응 핵심 3가지" |
| `timeline` | "[주제] [N]단계 절차" 예: "상속 분쟁 조정 5단계 절차" |
| `kakao_dialogue` | "[주제] 의뢰인-변호사 상담 발췌" 예: "음주운전 측정 0.08 상담 발췌" |
| `ai_visual` | 기존 룰 (scene 본문 합성) 유지 + 80자 / target keyword 1회 정합화 |

### 13.7 작업 항목 (예상 1일)

1. plan §13 SOT 갱신 (본 항목)
2. `feat/alt-text-caption` 브랜치 생성
3. `skills/meta/slot_selection.md` — 7종 카드 alt_text 필드 + SEO 룰 6개 + 카드별 패턴 6개 추가. `ai_visual.md` / `illustration.md` 의 기존 alt 룰 정합화 (80자).
4. `tools/limits.py` — `ALT_TEXT_MAX_CHARS: Final[int] = 80` 상수 추가.
5. `tools/llm/analyze_content.py` — `page_title: str` 인자 추가, system prompt 상단에 "PAGE TITLE: {page_title}" 명시 + 위 룰 inject.
6. `tools/llm/review.py` / `skills/meta/prompt_review.md` — alt_text 검사 항목 추가 (길이 / target keyword 1회 / 본문 통째 복붙 X / 자기지시 X). `page_title: str` 인자 추가.
7. `orchestrator.py` — caption 전달 + 가드 (80자 초과 시 caption 생략 + slot 살림) + `alt_text_status` 로그 (`ok` / `empty` / `truncated`).
8. 1페이지 e2e — 슬롯 caption 박힘 / analyze cost before-after / page cap $2.50 안전 / 페이지 안 alt 중복 X 확인.

> `insert_image_block.py` 는 변경 없음 (`caption: str = ""` 파라미터 기존 존재).

### 13.8 운영 모니터링 — `alt_text_status` 컬럼

`log_metadata.input_data` 에 슬롯별 `alt_text_status` 기록:
- `ok`: caption 박힘, 검수자 발견 OK
- `empty`: LLM 미생성 또는 validator 실패 → 검수자 직접 작성 필요
- `truncated`: 80자 초과로 caption 생략 (LLM 룰 재학습 신호)

1주 운영 후 메트릭 점검: empty 비율 ≥ 10% 면 slot 폐기 정책 전환, truncated 비율 ≥ 5% 면 LLM 룰 강화 또는 한도 재검토.

### 13.9 §12 (SDK migration) 와의 관계

- 완전 독립 트랙. SDK migration 전/후 어느 쪽에서도 작동.
- §12 Week 3b parametric 결정(`orientation` / `emphasis_index`)은 alt 에 반영 X — alt 는 **data-only**, 시각 강조 묘사 X.
- §12 Week 1-2 SDK 마이그레이션 시 검증 항목: 새 SDK 경로에서도 `analyze_content` 가 7종 alt_text 를 동일하게 emit 하는지.

### 13.10 미결정

- `alt_text_status: empty` 슬롯 폐기 vs 살림 정책 — 1주 운영 후 메트릭 기반 결정.
- target keyword 추출 source — 첫 PR 은 `page_title` (Notion title property). 미흡 시 H1/H2 명사 결합 추출 추가 검토.
- filename_slug 트랙 부활 — 향후 CDN URL / 자체 발행 인프라 필요 시점에 별도 트랙으로 재논의.

## 14. Phase 4 — 감성형 카드 사상 재설계 + 토스피드 톤 정합 (v1.8-plan)

> **한 줄 사상**: gpt-image-2-2026-04-21 한글 정확도 ↑ + 토스피드 톤("소프트 에디토리얼 미니멀리즘")과 정합 ↑ 를 동시 ship. illustration 단일 스타일 → 스타일 라이브러리(5종), LLM 본문 보고 best fit 선택. 정보형 카드 배경 light gray 로 fix, 텍스트 환각은 vision OCR 로 차단.
>
> **3단계 ship**: 4.1 정보형 톤 fix (1-2일) → 4.2 ai_visual + 스타일 라이브러리 (4-7일) → 4.3 vision OCR (3-5일).

### 14.1 배경

- 카드 배경 `#ffffff` 강제가 토스피드 톤과 불일치. drift 발생 위치 3곳: `styles/ehyun_default.yaml:87` `card_defaults.background: '#ffffff'` + `templates/_base.css:147` `.card { background: var(--neutral-0) }` + `tools/render/ai_render.py:58` `"clean white background"`.
- `reference_library/_meta.yaml` 은 **로컬 파일로 존재**하나 `reference_library/` 디렉터리 전체가 `.gitignore:90` 으로 untrack (commit `60ed019`) — git 이력 0회. 운영자 로컬 메타라 SOT 영향 0. **결정 (2026-05-15, 사용자 컨펌)**: meta.yaml 별도 신설 X, **yaml/css 토큰 직접 갱신 path 채택**. _meta.yaml 의 chart `background: light_gray` 명시는 토스피드 reference 의도 기록으로만 보존.
- **Pattern 1 배경 hex 결정 (2026-05-15, 사용자 컨펌)**: `#f5f5f5` literal + 신규 token `--card-bg` (yaml `card_bg`) 도입. 기존 Zinc cool-neutral 사상에 **카드 배경만 warm gray 예외** 허용 — CLAUDE.md "컬러 시스템" 도 동기 갱신.
- gpt-image-2-2026-04-21 한글 정확도가 v1.6.4 이후 상승 → AI 활용 비율 상향 정당화.
- 기존 illustration "라인 일러스트 단일 스타일 고정" → 콘텐츠 톤 다양성 부족. 본문 context 에 맞는 best fit 스타일 선택 필요.

### 14.2 Phase 4.1 — 정보형 카드 토스피드 톤 fix (1-2일)

**범위**: 정보형 5종 (`simple_table` / `chart` / `comparison_table` / `key_points_card` / `timeline`) HTML+CSS 를 토스피드 reference 와 동기화. **사실 정확성 절대 룰 #1 유지** — template path 보존 (사실 데이터 1자 변경 X). drift 처리 룰에 따라 plan 먼저 갱신 (본 §14 = SOT), 이후 코드 동기화.

**"소프트 에디토리얼 미니멀리즘" 핵심 8 패턴** (정보형 fix 기준):

| # | 패턴 | 코드 위치 |
|---|---|---|
| 1 | 배경 light warm gray — **fix `#f5f5f5` 신규 token `--card-bg`** (사용자 컨펌 2026-05-15, §14.1 참조) | `styles/ehyun_default.yaml` `card_defaults.background` + `card_bg` 신설 + `templates/_base.css` `--card-bg` 변수 + `.card { background: var(--card-bg) }` + `templates/master_chart.html` `.card` override `--neutral-100` → `--card-bg` 정합 |
| 2 | 카드 padding 80-100px 느낌 (현재 60px → 80px sp-3xl 사용) | `templates/_base.css` `.card { padding }` |
| 3 | 제목 좌상단 매우 bold (`--fw-bold` 유지, 위치만 좌상단 anchor) | `templates/_base.css` `.card__title` |
| 4 | 컬러 monochromatic 2-3색 + warm accent 1 (`brand.primary` + neutral + `chart.accent_warm`) — 현 정책 유지, 컬러 토큰 변경 X |
| 5 | 그리드 가로만 매우 옅음 (chart x-axis grid hidden, y-axis grid `neutral-200`) | `templates/master_chart.html` Chart.js config |
| 6 | 출처 좌하단 작고 옅게 (`--font-small` + `--neutral-400` 유지) — 현 정책 유지 |
| 7 | 데코레이션 0 (아이콘/일러스트/그림자/그라데이션 X) — 현 정책 유지, 신규 카드 작성 시 가드 |
| 8 | 콘텐츠:여백 ≈ 50:50 — **결정 (2026-05-15, 사용자 컨펌)**: padding 80 적용만 (Pattern 2). chart 만 기존 `min-height: 900px` 유지, 나머지 4종 `height: auto` 그대로. 짧은 콘텐츠 50:50 미보장은 4.2 진입 후 운영 데이터 보고 결정. | `.card` height 자동 (변경 X), `.card--chart { min-height: 900px }` 유지 |

**산출물 (Phase 4.1 Do)** — 2026-05-15 사용자 컨펌 commit slice 5개:
- `styles/ehyun_default.yaml` — `card_defaults.background` `#ffffff` → `#f5f5f5` + `card_defaults.padding` 64 → 80 + `colors.neutral.card_bg` 신설
- `templates/_base.css` — `--card-bg: #f5f5f5` 변수 신설 + `.card { background: var(--card-bg); padding: var(--sp-3xl) }` 동기 (Pattern 1+2)
- `templates/master_chart.html` — `.card` background override `var(--neutral-100)` → `var(--card-bg)` 정합 (line/bar/donut/pie 분기 모두). 나머지 4 templates (`simple_table`/`comparison_table`/`key_points_card`/`timeline`) 은 `.card` background override 없어 _base.css 갱신만으로 자동 적용 = 변경 0.
- `tools/render/ai_render.py:_build_illustration_prompt` 의 "clean white background" 표현 → "soft light gray warm neutral background" 로 정합 (Phase 4.2 deprecate 전까지 잠정)
- ~~`reference_library/_meta.yaml` 신설~~ → §14.1 결정대로 **skip** (yaml/css 토큰 직접 갱신 path 채택)
- Pattern 5 (chart x-axis grid hidden / y-axis `--neutral-200`) — 기존 master_chart.html:249/261 이미 구현됨, **변경 0**.
- Pattern 3 (제목 좌상단 매우 bold) — `_base.css` `.card { display: flex; flex-direction: column }` + `.card__title { font-weight: var(--fw-bold) }` 이미 만족, **변경 0**.

**Done 정의 (4.1)**:
- 5종 정보형 카드 e2e 1건 렌더 → 토스피드 reference 시각 비교 사용자 OK
- 사실 데이터 회귀 0 (`tests/fixtures/chart_*.json` SHA byte-identical 또는 OCR diff 0 — §12.2 Week 3a 회귀 검증 방식 답습)
- mobile 가독성 40px+ 유지

### 14.3 Phase 4.2 — `ai_visual` 카드 + 스타일 라이브러리 (4-7일)

**범위**: `illustration` 카드 deprecate → 새 카드 `ai_visual` 신설. LLM 이 본문 context + `skills/visual_styles/*.md` frontmatter 보고 best fit 스타일 결정.

**상세 정의** → [docs/visual_styles_library_v1.md](docs/visual_styles_library_v1.md) (5종 스타일 frontmatter + 자연어 prompt + 운영 룰).

**초기 5종 (사용자 확정 2026-05-14)**:
1. `point_color_line` — 포인트 컬러 라인 일러스트 (기존 illustration 톤 보존)
2. `miniature_stock` — 미니어처 스톡 이미지
3. `korean_court_scene` — 한국 법원 실제 풍경
4. `blueprint_poster` — 블루프린트 포스터
5. `cinematic_three_frame` — 시네마틱 3-프레임 필름 (사용자 제공 자연어 prompt)

**메타 구조** — frontmatter 필수 6 + 선택 3 (사용자 컨펌 2026-05-14):
- 필수: `name` / `tone` / `use_when` / `prompt_template` / `aspect_ratio` / `text_rule`
- 선택: `reference_dir` / `quality` / `accent_target_default`

**비율 정책 — A안 fix (사용자 컨펌 2026-05-14)**: 스타일별 비율 자유. frontmatter `aspect_ratio` 필드가 SOT.
- default 4종 → `1536x1024` (3:2 landscape)
- cinematic_three_frame → `1024x1536` (2:3 portrait, 사용자 원문 "가로 프레임을 세로로 쌓은 형태" 정합)

**텍스트 룰** — 스타일별 `text_rule` 필드로 분기:
- 5종 초기 모두 `zero` (텍스트 0 강제). vision 검증 = §19.16 (Phase 4.3 진입 트리거).
- `factual` (본문 사실 인용 OK) 스타일 추가는 vision OCR Levenshtein 인프라 완비 후 (§19.11 카드별 분기 갱신).

**운영 — 사용자 스타일 추가**: `skills/visual_styles/<name>.md` 1개 + `reference_library/visual_styles/<name>/` 폴더 1개 추가하면 LLM 이 자동 인식 (analyze_content 가 디렉터리 scan). 코드 변경 0.

**산출물 (Phase 4.2 Do)**:
- 새 디렉터리: `skills/visual_styles/` (5개 md) + `reference_library/visual_styles/` (5개 폴더, reference image 운영하며 추가)
- `tools/render/ai_render.py:_build_illustration_prompt` deprecate → `_build_ai_visual_prompt` 신설 (스타일 frontmatter load + placeholder 치환)
- `tools/llm/analyze_content.py` 스타일 매칭 단계 추가 (감성형 슬롯 trigger 시 `skills/visual_styles/*.md` 디렉터리 scan → LLM 매칭 prompt inject)
- `orchestrator.SUPPORTED_TYPES` 에 `ai_visual` 추가, `AI_CARD_TYPES` 갱신, `_render_slot` 분기 1개
- `skills/image_types/illustration.md` deprecate 표시 (즉시 삭제 X — 운영 인지 후)
- 노션 로그 DB `타입` select 옵션 `ai_visual` 자동 생성 (5/12 검증된 자동 추가 메커니즘 활용)
- 새 슬롯 스키마: `extracted_data.visual_style` (str, name 매칭) + 기존 `scene` / `mood` / `accent_target` / `alt_text` / `footnote?`

**Done 정의 (4.2)**:
- 5종 스타일 각 1회 e2e trigger 성공 (운영 페이지 또는 fixture)
- `quality=high` (cinematic_three_frame) 실비 측정 → `PER_SLOT_COST_CAP_USD` 안전 마진 확인 (`$0.30` cap, $0.25 예상)
- 사용자 스타일 추가 절차 1회 dry-run 검증 (운영자가 md + 폴더 추가 → 다음 trigger 자동 인식)
- 슬롯 3 cap 적용 (§14.5)

### 14.4 Phase 4.3 — vision OCR 텍스트 환각 검증 (3-5일)

**범위 (MVP 단순화, 2026-05-18 사용자 컨펌)**: §19.16 (plan_history) paper-only → 실구현 격상. AI 카드 산출물을 vision LLM 이 평가 — **text_rule=zero 단일 분기**:
- 텍스트 검출 (스타일 `text_rule=zero` 인 경우) → 텍스트 픽셀 ≥ 1% 또는 OCR token ≥ 3개 → retry 1회 → 폐기
- §23 키워드 검사는 `tools/compliance/keywords.py` + `tools/llm/review.py` 1차 pass 에서 본문 텍스트 단계에 작동 — **vision layer 중복 X**. AI 카드 prompt 는 본문 사실만 사용 (정보형 5종은 본문 사실 직접 인용, 감성형 ai_visual 은 scene/mood 합성, kakao_dialogue 는 본문 messages 인용) — keywords 검사는 본문 단계로 충분.
- `kakao_dialogue` 한글 정확성 (Levenshtein ≤ 2) — kakao trigger 0건이라 **paper-only 유지** (§19.11 보류 row 참조). 실제 trigger 시 §19.11 + vision_review 본문에 분기 추가.

**vision 모델 — Claude Sonnet 4.6 vision (사용자 컨펌 2026-05-14) / vision input path — anthropic SDK 별 path (사용자 컨펌 2026-05-18)**:
- **path**: anthropic SDK 별 신설 — `claude-agent-sdk` 0.1.77 ContentBlock 에 ImageBlock 정의 부재 (`claude_agent_sdk/types.py:992-999` 확인, 2026-05-18). vision 은 plan §12 SDK 통일 결정과 직교. `anthropic.Anthropic().messages.create()` 직접 호출, multimodal content array (image base64 source) 표준 path. (A) streaming dict raw passthrough 미문서화 path 의존 위험 (0.1.78+ breakage) 회피 사유로 (B) 단독 채택.
- **모델**: Sonnet 4.6 (`claude-sonnet-4-6`). LLM reasoning 톤 일관 — 기존 review.py 와 같은 모델.
- **비용 계상**: anthropic.Usage (input_tokens / output_tokens / cache_*) → cost 환산 path 신설 → token-ledger.ndjson 통합 일관성 유지.
- OCR 정확도 / latency / cost 1페이지 실측 spike → Phase 4.3 Design 첫 작업 (§10 미결정 row, vision spike).

**산출물 (Phase 4.3 Do)**:
- `tools/render/vision_review.py` (신규) — 이미지 → vision LLM → JSON {text_detected, text_pixels_pct, ocr_tokens, korean_text, §23_violations}
- `tools/llm/review.py` 또는 별 `image_review.py` — vision_review 호출 + 슬롯 폐기 분기 + 로그
- `tools/limits.py` — `PER_SLOT_VISION_COST_USD` 신설 (예상 $0.05/슬롯)
- 노션 로그 DB row 추가 필드 (옵션) — `vision_review_passed: checkbox`, `vision_review_reason: rich_text`

**Done 정의 (4.3, MVP 단순화 2026-05-18)**:
- 5종 스타일 각 1회 vision_review 통과 (text_rule=zero 단일 분기)
- 텍스트 환각 의도적 시뮬레이션 1건 → 폐기 동작 확인
- `PER_SLOT_VISION_COST_USD` 5건 실측 평균 < $0.10
- (§23 키워드 / kakao OCR 분기 — MVP scope 밖. 본문 1차 pass / trigger 시 추가)

### 14.5 페이지당 슬롯 cap — 3개로 하향 (v1.8)

**배경**: 현재 `skills/meta/slot_selection.md` "페이지당 슬롯 2-4개 권장" (v1.6 상향). v1.8 ai_visual 도입 + quality=high 스타일 (cinematic) 비용 변동성 + vision review 슬롯당 cost 추가 → 페이지 cap 안전 마진 필요.

**갱신**:
- 페이지당 슬롯 **3 cap 고정** (이전 2-4 권장 → 3 hard cap)
- mix 권장: 정보형 1-2 + 감성형 1-2, **합 ≤ 3**
- 4개+ trigger 시 slot_selection 결과에서 우선순위 낮은 1개 폐기 + warning 로그

**갱신 위치**:
- `skills/meta/slot_selection.md` "Page-level mix 권장 룰" 섹션 (Phase 4.2 Do)
- [CLAUDE.md](CLAUDE.md) 절대 룰 #5 mix 룰 (Phase 4.2 Do, plan 동기화 후)
- §19.17 (plan_history.md) — 슬롯 3 cap 명시 추가

### 14.6 Phase 4 진입 체크리스트

#### 4.1 진입 prerequisite
- [x] Phase 3 v1.6.4 종료 게이트 통과 (kakao_dialogue trigger 0 미해결만 제외)
- [x] CLAUDE.md drift 항목 1차 정리 (이 §14 SOT 갱신 완료)
- [x] 사용자 컨펌 미해결 §1/§3/§4/§5 fix (2026-05-14)

#### 4.1 Done
- [-] 정보형 5종 토스피드 reference 비교 사용자 OK → **4.2 Done 통합 e2e (5페이지 분량) 로 close 위임** (2026-05-15 사용자 결정, Path B 단독 비교 e2e 보류)
- [x] `styles/ehyun_default.yaml` + `templates/_base.css` 토큰 동기 (831abd0 / c6f3cec / 78d9745 / aa69eb2)
- [x] 회귀 검증 0 (사실 데이터 SHA / OCR diff) — chart baseline SHA lock 재기록 (8ce7b74)
- [x] mobile 40px+ 유지 — Phase 4.1 변경은 token (background/padding) 만, font-size 0 변경

#### 4.2 진입 prerequisite
- [-] 4.1 Done — #1 은 4.2 통합 e2e 로 위임 (위 [-] 항목), #2-4 [x] 통과
- [x] `docs/visual_styles_library_v1.md` 5종 스타일 frontmatter draft 사용자 OK (2026-05-15)

#### 4.2 Done
- [x] `skills/visual_styles/` 5개 + `reference_library/visual_styles/` 5개 폴더 (6dc69f7)
- [x] `ai_visual` 카드 e2e — trigger 시도 4건 (3 dispose @ review_input + 1 완주 ai_render→Notion, $0.063 medium), 5종 distinct 미달은 4.3 운영 자연 cover (사용자 컨펌 2026-05-15)
- [x] `illustration` skill `[deprecated]` 표시 (5a8c59a, 즉시 삭제 X)
- [x] 슬롯 3 cap 적용 (efafa1a spec + 관찰 — e2e 5페이지 모두 3 슬롯 결정)
- [~] `quality=high` 실비 측정 → cinematic_three_frame LLM 매칭 0건 발생 → **4.3 운영 cover 의존**
- [x] 사용자 스타일 추가 dry-run — 2026-05-15 sentinel 6번째 스타일 추가 → `list_visual_styles()` + analyze 표 자동 인식 확인, 즉시 삭제. 코드 변경 0.
- [x] sweep 폐기 (5ce3ca1, list / page-id 만)
- [x] **Gap A — `skills/image_types/ai_visual.md` 신설** (12df132, review_input loader 정합 — Page 4 재실행 시 ai_visual 1건 완주 검증)

#### 4.3 진입 prerequisite
- [-] 4.2 Done — 7/8 [x], #5 (cinematic 실비) 만 [~] 4.3 운영 cover 의존. 4.3 진입은 #5와 직교 (vision spike 별도). 사용자 결정 사유 — Phase 4.3 Design 첫 작업은 vision spike, cinematic 실비는 운영 5건 누적 추적.
- [x] vision 모델 spike 1페이지 (Sonnet 4.6 vision via anthropic SDK 0.102, 2026-05-18, spike commit 38d66e9) → cost $0.0065 / latency 2.883s / accuracy text_detected=false (text_rule=zero 정합, page_id 35543f95d72a811cb5ddf87e3c3c1d49 사용자 ground truth 컨펌 2026-05-18). PER_SLOT_VISION_COST_USD cap $0.10 결정 (사용자 컨펌 2026-05-18 — retry 1회 + 대형 이미지 cover 사유).

#### 4.3 Done
- [x] `tools/render/vision_review.py` 신설 + 슬롯 폐기 분기 (2026-05-18 commit dbf674a vision_review.py + a1cc037 image_review.py + c30df46 orchestrator 통합, retry 1회 hard cap)
- [x] text_rule=zero 텍스트 환각 단일 분기 동작 (격리 검증 2026-05-18 — `scripts/_check_vision_dispose.py` chart_bar.png 33KB → text_pixels_pct=18.5 / ocr_tokens=28 / verdict.passed=False / reason 한글·영문 OCR 정확. cost $0.007716. §23 키워드 keywords.py + review.py 본문 1차 pass / kakao OCR trigger 0건 paper-only 유지)
- [~] `PER_SLOT_VISION_COST_USD` 5건 실측 평균 < $0.10 — **운영 자연 cover 의존** (자동 sourcing 후보 0건, 4.2 Done [~] cinematic 실비와 동일 path). 현재 2건 누적 ($0.0065 spike 38d66e9 + $0.007716 chart_bar 격리) 평균 $0.0071 / cap $0.10. 다음 운영 세션 3건 trigger 후 close.
- [ ] §19.16/§19.17 plan_history 상 paper-only → implemented 격상 (위 [~] 5건 누적 cover 후 commit, e2e 실측 데이터 포함)
- [ ] 페이지 cap $1.20 복귀 검토 (§10 미결정, 운영 5건 누적 후 결정)

### 14.7 비용 시뮬레이션 — 페이지당 슬롯 3 cap 가정

**기준 단가** (실측 + `tools/limits.py:GPT_IMAGE_PRICE_USD` + OpenAI 공식 docs):

| 항목 | medium 시나리오 | high 시나리오 | 출처 |
|---|---|---|---|
| analyze_content | $0.35 | $0.35 | 5/12 실측 cache hit 평균 ($0.26 mean, $0.34 max — `tools/limits.py:ANALYZE_BUDGET_USD=$0.80` cap 안전) |
| review_input × 3 슬롯 | $0.15 | $0.15 | 슬롯당 $0.05, REVIEW_BUDGET_USD=$0.30 cap |
| gpt-image 1536×1024 medium × 1-2 슬롯 | $0.063-$0.126 | — | `GPT_IMAGE_PRICE_USD[("1536x1024","medium")] = $0.063` |
| gpt-image 1024×1536 high × 1 슬롯 (cinematic) | — | $0.25 | `GPT_IMAGE_PRICE_USD[("1024x1536","high")] = $0.25` |
| vision_review × 3 슬롯 (Phase 4.3) | $0.020 (실측) | $0.020 (실측) | 슬롯당 cap **$0.10** (사용자 컨펌 2026-05-18 — retry 1회 + 대형 이미지 cover) / **실측 $0.0065** (2026-05-18 spike 38d66e9, Sonnet 4.6 anthropic SDK 0.102, image 1.478 MB webp, 1859 in / 62 out tokens). 추가 5건 누적은 4.3 Do 단계 자연 cover. |

**페이지 총 비용 — 슬롯 3 cap (정보형 1-2 + 감성형 1-2 mix)**:

| 시나리오 | 구성 | 총 비용 | PER_PAGE_CAP $2.50 안전 마진 |
|---|---|---|---|
| **medium 전형** | analyze + review×3 + gpt-image medium×2 + vision×3 | $0.35 + $0.15 + $0.126 + $0.15 = **$0.78** | $1.72 |
| **medium + cinematic 1** | analyze + review×3 + gpt-image medium×1 + gpt-image high×1 + vision×3 | $0.35 + $0.15 + $0.063 + $0.25 + $0.15 = **$0.96** | $1.54 |
| **high 풀** (cinematic + thinking 2개) | analyze + review×3 + gpt-image high×2 + vision×3 | $0.35 + $0.15 + $0.50 + $0.15 = **$1.15** | $1.35 |
| **edge case** (analyze 폭주 $0.80 + high 풀) | analyze + review×3 + gpt-image high×2 + vision×3 | $0.80 + $0.15 + $0.50 + $0.15 = **$1.60** | $0.90 |

**월 비용 (40편 기준, medium 전형 가정)**: 40 × $0.78 = **~$31**. 페이지 cap $1.20 복귀 시 $48 cap 내. 현재 $2.50 cap 은 edge case 안전 마진 + 5/12 실측 $0.96 (illustration 포함) 대응.

**상수 갱신 후보 (Phase 4.3 Done 후 결정)**:
- `PER_SLOT_VISION_COST_USD = 0.10` **확정** (사용자 컨펌 2026-05-18, spike 실측 $0.0065 + 안전 마진 15x). 4.3 Do 단계 `tools/limits.py` 신설 commit 별도.
- `PER_PAGE_CAP_USD` $2.50 유지 또는 $1.50 으로 단계 하향 (slot 3 cap + vision 인프라 안정화 후)

### 14.8 영향 받는 코드 영역 (Phase 4.1/4.2/4.3 Do 단계 작업, 본 Plan 세션 = 변경 0)

| 영역 | 단계 | 파일 | 변경 종류 |
|---|---|---|---|
| 디자인 토큰 | 4.1 | `styles/ehyun_default.yaml` | background / padding / sp-3xl 활용 |
| CSS | 4.1 | `templates/_base.css` | `.card { background, padding }` |
| HTML 정보형 5종 | 4.1 | `templates/{simple_table,master_chart,comparison_table,key_points_card,timeline}.html` | layout 미세 조정 |
| chart axis | 4.1 | `templates/master_chart.html` Chart.js config | x-axis grid hidden, y-axis `neutral-200` |
| reference meta | 4.1 | `reference_library/_meta.yaml` (옵션) | 신설 또는 yaml 토큰 갱신으로 대체 |
| AI prompt builder | 4.2 | `tools/render/ai_render.py` | `_build_illustration_prompt` deprecate → `_build_ai_visual_prompt` 신설 |
| analyze 매칭 | 4.2 | `tools/llm/analyze_content.py` | 감성형 슬롯 trigger 시 `skills/visual_styles/*.md` 디렉터리 scan + LLM 매칭 prompt |
| orchestrator | 4.2 | `orchestrator.py` | `SUPPORTED_TYPES` + `AI_CARD_TYPES` + `_render_slot` 분기, **sweep 모드 폐기** (argparse 분기 단순화) |
| skill | 4.2 | `skills/image_types/illustration.md` | deprecate 표시 |
| skill | 4.2 | `skills/image_types/ai_visual.md` | **신설** — review_input loader 정합 (Gap A, 2026-05-15 발견). `tools/llm/review.py` 가 `load_skill(f"image_types/{slot_type}.md")` 호출 시 파일 부재면 슬롯 폐기 → ai_visual 모든 슬롯 review 단계 dispose. visual_styles_library 참조 + scene/mood/visual_style/accent_target 검증 룰 |
| 신규 디렉터리 | 4.2 | `skills/visual_styles/` + `reference_library/visual_styles/` | 5종 스타일 md + reference 폴더 |
| slot_selection | 4.2 | `skills/meta/slot_selection.md` | mix 룰 갱신 (슬롯 3 cap, ai_visual 통합) |
| vision review | 4.3 | `tools/render/vision_review.py` (신규) | **anthropic SDK 별 path** (claude-agent-sdk ContentBlock ImageBlock 부재 — types.py:992-999 확인, 2026-05-18 사용자 컨펌). multimodal content (image base64) + Sonnet 4.6 vision + JSON 반환 + anthropic.Usage → token-ledger 환산 |
| §19 격상 | 4.3 | `plan_history.md` §19.16/§19.17 | paper-only → implemented 격상 |
| 비용 상수 | 4.3 | `tools/limits.py` | `PER_SLOT_VISION_COST_USD` 신설 + 페이지 cap 재검토 |
| CLAUDE.md 동기 | 4.1-4.3 각 단계 | `CLAUDE.md` | 절대 룰 #5 (카드 라인업) + 운영 가드 §19.16/17 격상 명시 |

### 14.9 미해결 (Plan 작성 중 컨펌받은 결과 + 향후 결정)

**해소 (사용자 컨펌 2026-05-14)**:

| # | 항목 | 결정 |
|---|---|---|
| §1 | cinematic 비율 vs 3:2 default 충돌 | A안 — 스타일별 `aspect_ratio` 자유. cinematic 만 2:3, 나머지 3:2. |
| §3 | vision review 모델 | Claude Sonnet 4.6 vision (SDK 인프라 재사용). Phase 4.3 Design 첫 작업 1페이지 spike. |
| §4 | 스타일 라이브러리 frontmatter | 필수 6 (`name`/`tone`/`use_when`/`prompt_template`/`aspect_ratio`/`text_rule`) + 선택 3 (`reference_dir`/`quality`/`accent_target_default`). |
| §5 | sweep 모드 폐기 여부 | Phase 4 진입 시 sweep 폐기, fan-out only. orchestrator.main() argparse 분기 단순화. |

**해소 (사용자 컨펌 2026-05-18)**:

| # | 항목 | 결정 |
|---|---|---|
| §14.4 | vision input path | anthropic SDK 별 path 신설. claude-agent-sdk 0.1.77 ContentBlock 에 ImageBlock 정의 부재 (`types.py:992-999`) 사유. plan §12 SDK 통일 결정과 직교. token-ledger 환산 path 신설 사유. |

**Phase 4 진입 후 미해결** → §10 `v1.8 신규` 4개 row 참조 (high quality 실비 / reference 매칭 영향 / 같은 visual_style 연속 / vision 모델 spike).

---

## Changelog

- **v1.8.0-plan** (2026-05-14): Phase 4 (감성형 카드 사상 재설계 + 토스피드 톤 정합) plan 신설. **plan only — 코드 변경 0**.
  - **배경**: (a) 카드 배경 `#ffffff` 강제가 토스피드 톤("소프트 에디토리얼 미니멀리즘")과 불일치 (drift 3곳: `styles/ehyun_default.yaml:87` + `templates/_base.css:147` + `tools/render/ai_render.py:58`). (b) gpt-image-2-2026-04-21 한글 정확도 ↑ → AI 활용 비율 상향 정당화. (c) illustration 단일 스타일 한계 → 콘텐츠 톤 다양성 부족. (d) §19.16 vision OCR 텍스트 환각 검증이 paper-only 인 상태로 ai_visual ship 시 §23 / 사실 정확성 위반 리스크.
  - **해결**: 3단계 ship — **4.1 정보형 톤 fix** (1-2일, light gray 배경 + padding/typography 정합) → **4.2 `ai_visual` 카드 + 스타일 라이브러리 5종 신설** (4-7일, LLM 본문 보고 best fit 선택, 사용자가 md + reference 폴더 추가하면 자동 인식) → **4.3 vision OCR 검증** (3-5일, Claude Sonnet 4.6 vision, §19.16/§19.17 paper → implemented 격상).
  - **갱신 위치**:
    - §4 카드 카탈로그 — `illustration` deprecated 표시 + `ai_visual` 신설 row 추가
    - §3 진입점 — sweep 모드 폐기 명시 (Phase 4.1 Do)
    - §10 미결정 — `v1.8 신규` 4개 row 추가 (vision spike / high quality 실비 / reference 영향 / 같은 visual_style 연속)
    - **새 §14** "Phase 4 — 감성형 카드 사상 재설계 + 토스피드 톤 정합" 섹션 (4.1/4.2/4.3 spec + 진입 체크리스트 + 비용 시뮬레이션 + 영향 코드 enumerate)
    - 새 [docs/visual_styles_library_v1.md](docs/visual_styles_library_v1.md) — 5종 스타일 상세 정의 (frontmatter sample + 자연어 prompt + cinematic 사용자 원문 인용)
    - plan_history.md §19.16/§19.17 — Phase 4.3 진입 트리거 + 슬롯 3 cap 명시 갱신
  - **사용자 컨펌 (2026-05-14, §14.9)**: ①시네마틱 비율 → A안 스타일별 자유 (cinematic 만 2:3, 나머지 3:2). ③vision 모델 → Claude Sonnet 4.6 vision. ④frontmatter → 필수 6 + 선택 3. ⑤sweep → 폐기, fan-out only.
  - **코드 변경 영역 (Phase 4 Do 단계, 본 세션 = 0)**: §14.8 표 참조. 신규: `skills/visual_styles/`, `reference_library/visual_styles/`, `tools/render/vision_review.py`. 갱신: `styles/ehyun_default.yaml`, `templates/_base.css`, `templates/*.html`, `tools/render/ai_render.py`, `tools/llm/analyze_content.py`, `orchestrator.py`, `skills/meta/slot_selection.md`, `skills/image_types/illustration.md`, `tools/limits.py`, `CLAUDE.md`.
  - **비용 영향**: PER_PAGE_CAP_USD $2.50 유지 (medium 전형 페이지 $0.78, edge case $1.60). vision_review 슬롯당 $0.10 추정. 슬롯 3 cap 하향으로 페이지 비용 ceiling 안정.
  - **branch**: `feat/phase4-visual-styles` (main 분기). Plan PR → 머지 후 Phase 4.1 Design 별 세션 진입.

- **v1.7.5-plan** (2026-05-14): `.github/workflows/cron.yml` **2-step matrix fan-out** 갱신. 배경: 직전 cron run 실측 — 블로그 1건(7:15) + 웹 1건(7:28) 완료, 웹 2번째 페이지 처리 중 `timeout-minutes: 20` 도달해 cancel. 페이지당 7-8분 × 페이지 N → 단일 job 구조는 N ≥ 3 부터 timeout 노출. **해결**: page 단위 fan-out — fetch job (5분) 이 "이미지 필요" 페이지 목록 JSON 출력 → process job matrix (cell 별 15분, fail-fast: false, max-parallel: 5) 가 페이지 1개씩 병렬 처리. 총 wall-clock = max(페이지 처리 시간), 페이지 수 N 무관. **갱신 위치**: §3 진입점 (list 모드 / page-id 모드 / cron 2-step 설명 추가) + §10 cron schedule row (fan-out 작성 완료 명시) + §12.8.3 (matrix 구조 명시). **코드 변경**: `orchestrator.py` argparse 분기 (`--mode list` / `--page-id+--source` / 인자 없음 sweep) 추가, `process_database` / `run_for_page` 본체 보존. **PER_RUN_CAP_USD 의미 변화**: 기존 sweep 누적 cap → matrix cell 당 cap (cell 이 별 process). 총 spend = pages × PER_PAGE_CAP_USD worst case, max-parallel 5 + per-DB limit 5 로 자연 제한.

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
