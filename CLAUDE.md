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
2. **변호사법 §23** — 절대성/마케팅 과장/시간 압박/비교 광고 표현 검출 시 슬롯 폐기. 상세는 `skills/style/ehyun_visual_guide.md`. 키워드 코드 상수화는 `tools/compliance/keywords.py` (Phase 2 진입 전 신설).
3. **모바일 가독성 40px+** (v1.3) — 카드 본문 텍스트 최소 40px (1200px 캔버스 기준). 1200px가 노션 모바일에서 30% 축소되어 표시 ~12px 보장. 출처/메타만 26px까지. plan §13 D안 참조.
4. **Phase 점프 금지** — 게이트 통과 못한 단계 작업 X.
5. **MVP 사이즈** — Phase 1은 카드 2종(`simple_table` + `chart` sub_type=`line`)만.
6. **에러 만나면 우회 X — 근본 원인 진단 → 기능 살리며 해결.**
7. **drift 처리 룰** — 코드/스킬과 plan(SOT) 간 불일치 발견 시 **plan을 먼저 갱신**한 뒤 코드 동기화. CLAUDE.md는 압축 룰, plan(`ehyun-image-agent-plan_1.md`)은 사실 정의.

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

Python 3.12 / uv / Playwright(Chromium-headless-shell) / Chart.js CDN / Pretendard 1.3.9 / notion-client 3.0 (multi-source DB 자동 처리) / Claude Sonnet 4.6 (LLM은 bundled `claude.exe` 직접 호출 — claude-agent-sdk 0.1.x는 우리 use case에 비효율).

## 컬러 시스템

- brand wine-magenta `#a91c51` monochromatic, 차트 secondary는 desaturated 변형 (토스피드 navy→light blue 패턴 차용)
- neutral은 Tailwind Zinc (true neutral, brand 언더톤 충돌 X)
- 차트 multi-series 멀티 컬러 X — 같은 plum 계열 채도 변형으로만
- brand.primary는 강조 포인트로만 (표 키 컬럼, 차트 메인 라인, 강조 텍스트). 표 본문 셀에는 X.

## 알아두면 좋을 운영 사실

- Notion 콘텐츠 DB의 `상태` 속성은 **`status` 타입** (select 아님). `tools/notion/__init__.py:get_status_property_type()`이 자동 감지 후 페이로드 분기.
- multi-source DB이면 `data_sources[0]`에서 properties 가져옴. `resolve_data_source_id()`로 일관 처리.
- 콘텐츠 페이지의 raw blocks JSON은 80KB+ 가능 → LLM에 보내기 전 `compact_blocks()`로 id/type/text만 추출 (5~15KB). **모든 본문 구조의 text를 빠짐없이 추출해야 함** — table_row.cells, callout, quote 등 rich_text 외 구조도 포함. 데이터 손실 = 절대 룰 #1 위반.
- **데이터 추출은 단일 source**: analyze_content의 LLM 입력과 review_input의 page_text는 **반드시 같은 추출 함수**(`compact_blocks`)를 통과해야 함. 두 path가 갈라지면 "analyze는 보고 review는 못 봐서" false-positive 위반 보고 발생.
- LLM user_prompt 한계 ~20KB (Windows argv). 초과 시 `analyze_content`가 압축 모드 fallback 적용 (heading + 첫 paragraph + table_row만 유지, `_compress_for_analyze`). 그래도 초과면 RuntimeError raise.
- WebP 변환은 lossless가 lossy q=92보다 작음 (텍스트+단색 콘텐츠 특성). default lossless=True.
- **page_source / status 한글 통일**: `Literal["블로그", "웹"]`, `이미지 필요` / `발행 필요` / `이미지 작업 중` (모두 공백 포함). 영문/공백 없는 표기는 폐기됨.
- **claude-agent-sdk는 우회**, bundled `claude.exe`만 subprocess로 직접 호출 (`tools/llm/_common.py`). skills 자동 로드 X — markdown을 system_prompt에 직접 inject (옵션 A).
- **비용 cap 두 단계 (v1.3 상향)**: Phase 1 `PER_PAGE_CAP_USD = 1.50` (실측 ~$0.60-0.70/페이지, 4건 평균). analyze max_budget 0.50, review_input 0.30. run-level cap 3.00은 batch 진입점에서 누적 추적 (Phase 2). Phase 2 안정화 후 0.30 복귀 목표.

## 운영 가드 (plan §19 reference — Phase 1 즉시 / Phase 2 진입 전 분류)

**Phase 1 즉시 적용 (코드 수정 — v1.3 완료) ✅**:
- §19.2 block ancestor 검증 (`_verify_ancestor`, `insert_image_block`) + table_row anchor 격상 보강
- §19.4 Chart.js / Pretendard 로드 검증 — `wait_for_function("window.Chart != null && document.fonts.check(...)")`
- §19.5 review_input 실패도 log_metadata 호출 (`_log_review_dispose`)
- §19.6 슬롯 0개도 로그 1행 (`타입=없음`, 노션 select 옵션 운영팀 추가 필요)
- §19.8 본문 길이 압축 fallback (`_compress_for_analyze`)
- §19.9 page-level try/except (`scripts/test_phase1.py`)

**Phase 2 진입 전 필수**:
- §19.1 멱등성 — 동일 page_id 이력 검색 후 skip
- §19.3 rate limit backoff — `tools/notion/_retry.py`
- §19.7 §23 키워드 코드 상수화 — `tools/compliance/keywords.py`
- 비용 단일 source — `tools/limits.py`
