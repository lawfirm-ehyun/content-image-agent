# CLAUDE.md

> Claude Code / Claude Agent SDK가 자동 로드하는 프로젝트 메모리. 절대 룰과 반복 사고 패턴을 영구화한다. 이 파일은 매 세션 컨텍스트에 들어가니 짧고 압축적으로.
>
> 사실/스펙 → [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)
> 운영 계약 / Phase 게이트 → [AGENT_GUIDE.md](AGENT_GUIDE.md)
> 큰 그림 / 로드맵 → [ehyun-image-agent-plan_1.md](ehyun-image-agent-plan_1.md)

## 절대 룰

1. **사실 정확성** — 본문에 없는 사실/숫자/출처/주체 X. 추측·환각·가짜 출처 X.
   - **숫자/values/labels/point_labels/source (사실 그 자체)**: 1자도 변경 X. 본문 그대로.
   - **title/headers/cells (라벨링·재표현)**: 본문 사실 안에서 직관 합성 OK. 본문에 없는 사실 삽입은 금지.
2. **변호사법 §23** — 절대성/마케팅 과장/시간 압박/비교 광고 표현 검출 시 슬롯 폐기. 상세는 `skills/style/ehyun_visual_guide.md`. **키워드 master는 `tools/compliance/keywords.py`** (v1.4 완료 — `tools/llm/review.py`의 1차 regex pass가 LLM 호출 전 자동 검사).
3. **모바일 가독성 40px+** (v1.3 / v1.4 통일) — 카드 본문 텍스트 최소 40px (1200px 캔버스 기준). 1200px가 노션 모바일에서 30% 축소되어 표시 ~12px 보장. **출처/메타(footnote)는 모두 32px caption + neutral-500 통일** (v1.4 — 26px는 모바일 ~8px 가독 한계). plan §13 D안 참조.
4. **Phase 점프 금지** — 게이트 통과 못한 단계 작업 X.
5. **카드 라인업 — 정보/감성 mix (v1.8.1, 활성 6종)** — 페이지당 정보형(template) 1-2 + 감성형(AI) 1-2 mix 권장, 슬롯 3 cap hard.
   - **정보형 (사실 엄격, Phase 2 v1.4 5종)**: `simple_table`, `chart`(line/bar/donut/pie), `comparison_table`, `key_points_card`, `timeline`. **정보형 신설 X**.
   - **감성형 (활성 1종)**: `ai_visual`(v1.8 Phase 4.2 — `skills/visual_styles/` 5 스타일에서 LLM best fit, 텍스트 0 강제 `text_rule=zero`, vision 검증).
   - **deprecated**: `illustration`(v1.8 — ai_visual + point_color_line 흡수) / `kakao_dialogue`(**v1.8.1 은퇴, 2026-07-06** — 채팅 스크린샷 텍스트 과다 = "환기하되 몰입 안 깨기" 방향 불일치 + vision `text_rule=zero` 모순으로 100% 폐기·thinking $0.25 비용만 소모. 정의 보존 → plan_history §1.4). 둘 다 코드 backwards compat 유지, 신규 trigger 는 slot_selection 단 차단.
   - **Phase 4 검토 archive**: `stat_highlight`(v1.6.1 폐기, v1.5 정의 보존), `document_excerpt`(v1.5 정의 보존), `webtoon`(한국 웹툰 다컷), `app_ui_mockup`.
   - **mix 룰** (`skills/meta/slot_selection.md`): 정보형만/감성형만 X. 같은 카드 3연속 X. 콘텐츠 종속, 강제 X.
6. **에러 만나면 우회 X — 근본 원인 진단 → 기능 살리며 해결.**
7. **drift 처리 룰** — 코드/스킬과 plan(SOT) 간 불일치 발견 시 **plan을 먼저 갱신**한 뒤 코드 동기화. CLAUDE.md는 압축 룰, plan(`ehyun-image-agent-plan_1.md`)은 사실 정의.
8. **AI prompt 자연어 룰 (v1.6.2)** — gpt-image-2 등 최신 이미지 모델 prompt는 **자연어 키워드**로만 작성. 픽셀(`stroke 2px`)·hex(`#a91c51`)·CSS 토큰·"절대 금지" 같은 over-constraint 금지. 시각 톤은 (a) 자연어 스타일 키워드, (b) `reference_library/{card_type}/*` reference image input, (c) image_review 사후 검수로 보장. 단 **텍스트 사실 필드는 exact_korean_strings로 엄격 명시** — messages/excerpt/title 1자도 변경 X. 상세 plan §7.0 v1.6.2 사상.

## 카드 디자인 정책 (**노션 inline 이미지 = 콘텐츠 fit**)

토스피드 시드는 인스타그램 정사각형/4:5 비율의 fixed-aspect 카드. 우리 출력은 **노션 inline 이미지** — 다른 정책:

- **너비만 고정** (1200px). 세로는 **콘텐츠 fit (height auto)**.
- 1200×675 같은 16:9 fixed 비율은 **폐기** — 표 행 수, 차트 데이터 분량에 따라 시각 균형 깨짐 (하단 여백 과다 등).
- 외부 여백은 `.card` padding `var(--sp-2xl) = 60px` (v1.3 — 콘텐츠 가용 폭 확보 위해 80→60 축소). chart 카드만 `.card--chart { min-height: 900px }` modifier로 보장. **콘텐츠가 짧으면 카드도 짧게, 콘텐츠가 길면 카드도 길게.**
- fixed-aspect 카드(`.card--vertical`, `.card--square`)는 인스타그램 등 채널용으로 modifier로 별도 (Phase 2+).
- 권장 원칙 한 줄: **"웹 UI처럼 너비만 고정, 세로는 자연스럽게."**

이 정책은 `templates/_base.css` `.card` + `styles/ehyun_default.yaml` `card_sizes`에 반영. 두 파일은 단일 진실원칙으로 동기화.

## 슬롯 데이터 룰 (v1.3) — 사실/라벨링 분리

`extracted_data.title` **필수** + 데이터 종류별 룰 다름 (절대 룰 #1과 동기):

- **title / headers / cells (라벨링·재표현)**: 본문 사실 안에서 직관 합성 OK. 본문에 없는 사실/숫자/주체 삽입은 X. title은 H2/H3와 완전 동일만 X (부분 겹침 OK).
- **values / labels / point_labels / source (사실 그 자체)**: 1자도 의역·추측 X. 본문 그대로.

**슬롯 선택 우선순위**: ① 줄글 발굴 → simple_table  ② 본문 표 → chart 형식 전환 (시계열만)  ③ 본문 표 재구성 (드물게)  ④ 본문 표 그대로 복제 = ❌. **simple_table 컬럼 수: 2 default / 3 특수 / 4+ 슬롯 X.**

상세 룰: `skills/meta/slot_selection.md`, `skills/meta/prompt_review.md`.

## 기술 스택 한 줄

Python 3.12 / uv / Playwright(Chromium-headless-shell) / Chart.js CDN / Pretendard 1.3.9 / notion-client 3.0 (multi-source DB 자동 처리) / Claude Sonnet 4.6 (LLM은 **anthropic SDK 직접 호출 default** — v1.8.3 transport 전환, ENV `LLM_TRANSPORT=sdk` 롤백 시 claude-agent-sdk 0.1.77 query() subprocess 경로) / **OpenAI `gpt-image-2-2026-04-21`** (v1.6.4 default — ENV `OPENAI_IMAGE_MODEL_INSTANT/THINKING`로 override 가능. Phase 4 검토: `chatgpt-image-latest` (org verification 후), `gpt-image-1.5` (라인 일러스트 톤 최고)).

## 컬러 시스템

- brand wine-magenta `#a91c51` monochromatic, 차트 secondary는 desaturated 변형 (토스피드 navy→light blue 패턴 차용)
- neutral은 Tailwind Zinc (true neutral, brand 언더톤 충돌 X)
- **카드 배경은 예외** — Phase 4.1 (2026-05-15 결정) `--card-bg: #f5f5f5` warm light gray 도입. Zinc cool 톤 외 유일 예외. 토스피드 "소프트 에디토리얼 미니멀리즘" 톤 정합 위해. 적용 위치: `_base.css` `.card { background }` + `master_chart.html` `.card` override. 다른 컴포넌트(셀/헤더/legend swatch 등)는 Zinc 그대로.
- 차트 multi-series 멀티 컬러 X — 같은 plum 계열 채도 변형으로만
- brand.primary는 강조 포인트로만 (표 키 컬럼, 차트 메인 라인, 강조 텍스트). 표 본문 셀에는 X.

## 알아두면 좋을 운영 사실

- Notion 콘텐츠 DB의 `상태` 속성은 **`status` 타입** (select 아님). `tools/notion/__init__.py:get_status_property_type()`이 자동 감지 후 페이로드 분기.
- multi-source DB이면 `data_sources[0]`에서 properties 가져옴. `resolve_data_source_id()`로 일관 처리.
- 콘텐츠 페이지의 raw blocks JSON은 80KB+ 가능 → LLM에 보내기 전 `compact_blocks()`로 id/type/text만 추출 (5~15KB). **모든 본문 구조의 text를 빠짐없이 추출해야 함** — table_row.cells, callout, quote 등 rich_text 외 구조도 포함. 데이터 손실 = 절대 룰 #1 위반.
- **데이터 추출은 단일 source**: analyze_content의 LLM 입력과 review_input의 page_text는 **반드시 같은 추출 함수**(`compact_blocks`)를 통과해야 함. 두 path가 갈라지면 "analyze는 보고 review는 못 봐서" false-positive 위반 보고 발생.
- LLM user_prompt 한계 ~20KB 는 **sdk transport 한정** (claude.exe subprocess 전달 통로 제약). v1.8.3 default 인 api transport 는 한계 없음 — §19.8 압축은 150K ceiling(`MAX_BLOCKS_PROMPT_CHARS_API`) 초과 초장문만 진입, 일반 긴 글 무손실. sdk 롤백 시에만 기존 18K/20K 압축·RuntimeError 동작.
- WebP 변환은 lossless가 lossy q=92보다 작음 (텍스트+단색 콘텐츠 특성). default lossless=True.
- **page_source / status 한글 통일**: `Literal["블로그", "웹"]`, `이미지 필요` / `발행 필요` / `이미지 작업 중` (모두 공백 포함). 영문/공백 없는 표기는 폐기됨.
- **LLM transport 이중화** (`tools/llm/_common.py`, v1.8.3): default **api** (anthropic SDK `messages.stream()` + system cache_control 캐싱 — §12.9 spike: 캐싱 영수증 OK, 252블록 페이지 비용 0.23x, 슬롯 동등). 롤백: ENV `LLM_TRANSPORT=sdk` → claude-agent-sdk 0.1.77 query() (max_turns=1 + setting_sources=[] 가드, b7fe789 spike 채택 경로) — 전달 통로 ~20KB 한계 있음. 어느 쪽이든 skills 자동 로드 X — markdown을 system_prompt에 직접 inject.
- **비용 cap 단계 (v1.6.3 갱신)**: `PER_PAGE_CAP_USD = 2.50` / `PER_RUN_CAP_USD = 8.00` / `PER_SLOT_COST_CAP_USD = 0.30` / `ANALYZE_BUDGET_USD = 0.80` / `REVIEW_BUDGET_USD = 0.30`. AI mix 4슬롯 + slot_selection v1.6.2 두꺼움 반영. Phase 4 안정화 후 페이지 cap $1.20 복귀 목표 (analyze prompt 슬림 + slot_selection 다이어트).
- **5/12 e2e 실측**: ① 1페이지 3슬롯 (comparison_table + key_points_card×2) = $0.7723 / 5분 / 3/3 통과. ② P3.3+P3.4 통합 후 후속 e2e — analyze cap 초과 → §19.9 page try/except가 graceful 흡수. cap 상향 후 재시도. **노션 select 옵션 자동 생성 검증 OK**.

## 운영 가드 (plan §19 reference — Phase 1 즉시 / Phase 2 진입 전 분류)

**Phase 1 즉시 적용 (코드 수정 — v1.3 완료) ✅**:
- §19.2 block ancestor 검증 (`_verify_ancestor`, `insert_image_block`) + table_row anchor 격상 보강
- §19.4 Chart.js / Pretendard 로드 검증 — `wait_for_function("window.Chart != null && document.fonts.check(...)")`
- §19.5 review_input 실패도 log_metadata 호출 (`_log_review_dispose`)
- §19.6 슬롯 0개도 로그 1행 (`타입=없음`, 노션 select 옵션 운영팀 추가 필요)
- §19.8 본문 길이 압축 fallback (`_compress_for_analyze`)
- §19.9 page-level try/except (`scripts/test_phase1.py`)

**Phase 2 진입 전 — v1.4 완료 ✅**:
- §19.1 멱등성 — `get_logged_page_ids()` + `process_database` skip 가드
- §19.3 rate limit backoff — `tools/notion/_retry.py`의 `notion_call` (tenacity 5회 지수 백오프, 429/5xx)
- §19.7 §23 키워드 코드 상수화 — `tools/compliance/keywords.py` (4 카테고리 regex master)
- 비용 단일 source — `tools/limits.py` (18개 Final 상수) + `tools/budget.py` (`RunBudget`)
- §3 cron 진입점 — `orchestrator.main()` argparse 분기 (인자 없음 sweep / `--mode list` / `--page-id+--source`) + `.github/workflows/cron.yml` 2-step matrix fan-out (v1.7.5-plan)

**Phase 4 보강 — 2026-05-20 운영 1건 반영 ✅**:
- §19.18 block 위치 환각 원천 차단 (v1.8.2, 2026-07-06) — `analyze_content.py`가 LLM에 blocks를 UUID 없이 순번 `idx`로 제시, LLM은 `position_after_block_index`(정수)만 출력 → 코드가 block_id 변환 (범위 밖/비정수 drop, legacy UUID 출력은 known-id 게이트로 수용)
- §19.18 retry whitelist 확장 — `insert_image_block`에 `BlockNotFoundError` / `AncestorMismatchError` dedicated exception 신설, `orchestrator.py:531` except 화이트리스트에 추가 → retrieve 404 / ancestor 불일치 시 헛재시도 (3회 × webp/upload) 즉시 차단

**Phase 3 진입 전 — v1.6 정의, 코드 작업 예정**:
- ~~§19.11 AI 카드 OCR 사실 검증 (kakao Levenshtein)~~ — **obsolete (v1.8.1, 2026-07-06 kakao_dialogue 은퇴)**. text-fact AI 카드 (document_excerpt 등) 활성화 시에만 부활 검토 (plan_history §19.11)
- §19.12 OpenAI rate limit / 429 backoff
- §19.13 OpenAI 비용 cap (`PER_SLOT_COST_CAP_USD = 0.30`, anthropic/openai 분리)
- §19.14 cron 연속 실패 누적 알림
- §19.15 OpenAI key fail-fast + 에러 sanitize
- §19.16 illustration 텍스트 환각 차단 (vision)
- §19.17 mix 정책 위반 검증 (감성만/3연속)
