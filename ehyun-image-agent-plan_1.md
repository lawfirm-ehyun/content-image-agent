# 이현 블로그 이미지 에이전트 — 빌드 계획서 (v1.1)

> 법무법인 이현의 블로그 + 웹 콘텐츠용 이미지를 자율 생성·배치하는 에이전트.
> Notion 워크플로 안에서 동작하며, OpenMontage의 agent-first / pipeline-driven 패턴을 차용한다.
>
> **이 문서는 다른 Claude Code 세션이 그대로 받아서 빌드를 시작할 수 있도록 작성된 단일 계획서다.**

---

## 다음 세션 시작 instruction (Claude Code에게)

이 계획서를 컨텍스트로 받았다면:

1. 이 문서 전체를 먼저 읽어라
2. 섹션 14의 **사용자 사전 작업 체크리스트**를 사용자에게 확인 요청
3. 모든 사전 작업 완료 확인 후 → 섹션 12의 **Phase 0**부터 시작
4. 각 Phase 완료 시 사용자 검증 요청
5. 절대 Phase 점프 금지. **Phase 1은 카드 2개만 (simple_table, chart_line)**. 더 만들지 마라
6. 산출물(skill, template, tool)은 매 Phase마다 README 인덱스에 추가

**핵심 원칙 (절대):**
- **Template-first** — AI 카드는 P1 이후. P0은 코드 템플릿만
- **데이터 정확성 절대 우선** — 차트/표는 본문 명시 숫자 외 절대 사용 금지
- **모바일 가독성 우선** — 모든 텍스트 최소 28px (1200px wide 카드 기준)
- **변호사법 §23 컴플라이언스** — 모든 이미지 텍스트는 광고규제 검사 대상
- **검증 게이트 통과 못한 단계 → 다음 단계 X**
- **MVP 사이즈 지키기** — Phase 1은 카드 2개만

---

## 0. 컨텍스트

**무엇을 만드는가**
Notion 콘텐츠 DB(블로그 + 웹)의 `status="이미지필요"` 페이지를 자동 처리해서, 본문 분석 → 이미지 슬롯 결정 → 이미지 생성/렌더링 → Notion에 업로드 + 적절한 위치 배치 → 결과에 따라 status 변경하는 에이전트.

**왜 만드는가**
1. SEO 콘텐츠 생산 속도 향상 (이미지 제작 병목 해소)
2. 비주얼 일관성 확보 (디자인 시스템 자동 적용)
3. 운영 데이터 축적 (어떤 이미지 타입이 효과적인지 학습)

**비주얼 추구미**
토스피드의 본문 자료 톤 — **미니멀한 데이터 시각화, 깔끔한 표, 텍스트 카드**. 캐릭터 일러스트나 화려한 그래픽이 아님. 가독성과 데이터 정확성 우선.

- 표 (회색 헤더 + 흰 셀, 가독성 우선)
- 차트 (단색 강조, 정확한 라벨, 출처 표기) ← **자주 사용됨**
- 비교 표 (한쪽 컬럼 강조)
- 텍스트 카드 (핵심 포인트, 체크리스트)
- 가끔: 판례/법조문 발췌, 카톡 대화

**누가 쓰는가**
법무법인 이현 마케팅팀. 검수자는 노션에서 결과 확인하고 status를 다음 단계로 변경.

**처리 대상 콘텐츠 DB (2개)**
- **블로그 콘텐츠 DB** (인블로그)
- **웹 콘텐츠 DB** (ehyun.ai.kr)

본문 구조는 동일. 속성에만 일부 차이. 같은 분석/생성 룰 적용. `출처` select로 분기.

**핵심 사상**
- **Agent IS the orchestrator** — 별도 백엔드 없이 Claude Agent SDK가 자율 실행
- **Pipeline-driven** — YAML 매니페스트 + Markdown skill로 모든 의사결정 외부화
- **Template-first** — 코어는 HTML+Playwright 템플릿. AI(gpt-image-2)는 P1+ 보조
- **figma는 디자인 ground truth** — 자동화 런타임 X. 디자이너 의사결정 도구 + 시드 레퍼런스 추출 도구
- **Self-review gates** — 입력/이미지 두 단계 자동 검증
- **Notion 단일 데이터 소스** — 메타 로그도 Notion DB에 저장
- **Page mention via rich_text** — relation 대신 mention. 콘텐츠 DB 스키마 무영향

---

## 1. 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────┐
│                  GitHub Actions Cron (1h)                    │
│                            │                                  │
│                            ▼                                  │
│                    orchestrator.py                            │
│                            │                                  │
│                            ▼                                  │
│              Claude Agent SDK (Sonnet 4.7)                    │
│              ↕ reads skills/, pipeline_defs/                  │
│              ↕ calls tools/                                   │
└────────┬───────────────────────────────────────────┬─────────┘
         │                                            │
    ┌────▼─────┐                              ┌──────▼──────┐
    │  Notion  │  fetch / upload / status     │  Template   │
    │   API    │                              │  Renderer   │  ← 코어
    └──────────┘                              │ (Playwright │
                                              │  + Chart.js)│
                                              └──────┬──────┘
                                                     │
                                              ┌──────▼──────┐
                                              │  GPT-Image-2│  ← 보조
                                              │ (P1+ 카드)   │
                                              └─────────────┘

[figma]
└── 디자인 ground truth (자동화 파이프라인 외부)
    - 카드 시안 결정
    - 시드 레퍼런스 추출 (수동, 1회성)
    - 디자인 변경 시 코드 동기화 트리거
```

---

## 2. 레포 구조

```
ehyun-image-agent/
├── pipeline_defs/
│   └── blog_image.yaml
├── skills/
│   ├── image_types/
│   │   ├── simple_table.md          # P0
│   │   ├── chart.md                 # P0 (line부터, sub-type 점진 확장)
│   │   ├── comparison_table.md      # P0
│   │   ├── key_points_card.md       # P0
│   │   ├── stat_highlight.md        # P1
│   │   ├── document_excerpt.md      # P1 (AI)
│   │   ├── kakao_dialogue.md        # P2 (AI)
│   │   └── app_ui_mockup.md         # P2 (AI)
│   ├── meta/
│   │   ├── slot_selection.md
│   │   ├── prompt_review.md
│   │   ├── image_review.md          # 변호사법 §23 컴플라이언스 포함
│   │   ├── regen_policy.md
│   │   └── notion_placement.md
│   └── style/
│       └── ehyun_visual_guide.md
├── styles/
│   └── ehyun_default.yaml           # 디자인 토큰
├── tools/
│   ├── notion/
│   │   ├── fetch_pages.py
│   │   ├── get_page_content.py
│   │   ├── upload_image.py
│   │   ├── insert_image_block.py
│   │   ├── update_status.py
│   │   └── log_metadata.py          # mention 변환 로직 포함
│   ├── render/
│   │   ├── template_render.py       # Playwright 코어, WebP 후처리
│   │   └── chart_render.py
│   ├── image/
│   │   ├── gpt_image_2.py           # P1+
│   │   └── webp_converter.py        # PNG → WebP 변환 (pillow)
│   └── llm/
│       ├── analyze_content.py
│       └── review.py
├── templates/                        # ← 코어 자산 (HTML/CSS)
│   ├── _base.css                    # 공통 스타일 (폰트, 토큰)
│   ├── simple_table.html
│   ├── chart.html                   # 모든 차트 sub-type 통합
│   ├── comparison_table.html
│   ├── key_points_card.html
│   └── stat_highlight.html          # P1
├── reference_library/
│   ├── simple_table/
│   ├── chart/                       # 토스피드 캡처 포함
│   ├── comparison_table/
│   ├── key_points_card/
│   ├── stat_highlight/
│   ├── document_excerpt/
│   └── _meta.yaml
├── assets/
│   ├── fonts/                       # Pretendard (자동 다운로드 스크립트로)
│   └── logo/                        # 이현 로고 (옵션)
├── scripts/
│   └── download_fonts.sh            # Pretendard 다운로드 자동화
├── .github/workflows/
│   └── cron.yml
├── orchestrator.py
├── pyproject.toml
├── .env.example
├── README.md                        # 프로젝트 개요 + 산출물 인덱스
├── AGENT_GUIDE.md                   # 에이전트 운영 계약
└── PROJECT_CONTEXT.md               # 아키텍처 레퍼런스
```

---

## 3. 기술 스택

**언어/런타임**
- Python 3.12 (메인)

**Python 의존성**
- `claude-agent-sdk` — Anthropic Agent SDK (※ 정확한 import/모델명은 Phase 0에서 SDK 문서 확인)
- `openai` — P1+ (gpt-image-2)
- `notion-client` — Notion 공식 SDK
- `pillow` — 이미지 후처리 (WebP 변환, 사이즈 조정)
- `pydantic` v2 — 스키마 검증
- `pyyaml` — 파이프라인/스타일 정의 로드
- `httpx` — 비동기 HTTP
- `playwright` — HTML → PNG 렌더링

**렌더링 스택**
- Playwright Python + Chromium headless
- Chart.js (HTML 안에서 CDN 또는 로컬 import)
- Pretendard (assets/fonts/, scripts/download_fonts.sh로 자동 다운로드)

**개발 도구**
- `uv` — 패키지 관리
- `ruff` — 린트/포맷
- `pytest` — 테스트

---

## 4. 디자인 토큰 (`styles/ehyun_default.yaml`)

**핵심 원칙: 모바일 가독성 우선. 1200px wide 카드 기준 모든 텍스트 최소 28px.**

```yaml
# styles/ehyun_default.yaml

colors:
  brand:
    primary: '#a91c51'        # 강조 - 표 한 컬럼/행, 차트 메인 라인, 강조 텍스트
    primary_soft: '#fdf2f5'   # 연한 배경 (강조 영역 배경 톤)

  neutral:
    900: '#0f172a'   # 가장 진한 글자, 다크 카드 배경
    800: '#1e293b'   # 큰 제목
    700: '#334155'   # 본문 글자 (기본)
    600: '#475569'   # 보조 글자
    500: '#64748b'   # 캡션
    400: '#94a3b8'   # 출처/메타
    300: '#cbd5e1'   # 보더 (연한)
    200: '#e2e8f0'   # 보더 (더 연한)
    100: '#f1f5f9'   # 셀 배경 (회색 헤더)
    50:  '#f8fafc'   # 카드 배경 (옵션)
    0:   '#ffffff'   # 기본 배경

  accent:  # 거의 안 씀. 90%는 흑백 + brand.primary
    success: '#16a34a'  # ✓ 표시 등 (key_points_card checked variant)
    warning: '#f59e0b'  # 주의 표시

typography:
  font_family: 'Pretendard, -apple-system, BlinkMacSystemFont, sans-serif'
  weights: { regular: 400, medium: 500, semibold: 600, bold: 700 }

  # 1200px wide 카드 기준 모바일 가독성 우선
  # 모든 본문 텍스트 최소 28px (production 검증 기준)
  sizes:
    display: 96px       # stat_highlight 메가 숫자 ("638억")
    h1: 52px            # 카드 메인 제목
    h2: 38px            # 부제 / 차트 제목
    body_large: 34px    # key_points_card 항목 등 본문 큰 글씨
    body: 30px          # 표 헤더, 일반 본문
    body_sm: 28px       # 표 본문 셀 (절대 minimum)
    caption: 24px       # 차트 축 라벨, 캡션
    small: 20px         # 출처/메타 (출처는 가독성 양보 OK)

  line_heights: { tight: 1.15, snug: 1.3, normal: 1.5 }

spacing:  # px
  xs: 4
  sm: 8
  md: 16
  lg: 24
  xl: 32
  '2xl': 48
  '3xl': 64

radius:  # px
  sm: 4
  md: 8
  lg: 12
  xl: 20

# 카드 사이즈 프리셋 (비율별)
card_sizes:
  default: { width: 1200, height: 675, ratio: '16:9' }   # 본문 inline
  square:  { width: 1080, height: 1080, ratio: '1:1' }
  vertical:{ width: 1080, height: 1350, ratio: '4:5' }

# 카드 공통 룰
card_defaults:
  padding: 64px
  background: '#ffffff'
  text_color: '#1e293b'    # neutral.800
```

`templates/_base.css`로 위 토큰을 CSS 변수로 export해서 모든 카드 템플릿에서 공유:

```css
/* templates/_base.css (예시) */
:root {
  --brand-primary: #a91c51;
  --brand-primary-soft: #fdf2f5;
  --neutral-900: #0f172a;
  /* ... */

  --font-display: 96px;
  --font-h1: 52px;
  --font-body: 30px;
  --font-body-sm: 28px;
  /* ... */
}

@font-face {
  font-family: 'Pretendard';
  src: url('../assets/fonts/Pretendard-Regular.otf') format('opentype');
  font-weight: 400;
}
/* ... 500, 600, 700 */

body { font-family: 'Pretendard', -apple-system, sans-serif; }
.card { width: 1200px; height: 675px; padding: 64px; box-sizing: border-box; background: #fff; }
```

---

## 5. 비주얼 가이드 (`skills/style/ehyun_visual_guide.md`)

```markdown
# 이현 비주얼 가이드 v1

## 톤
- 차분함과 친근함 사이 (8:2)
- 신뢰감 있되 위압적이지 않음
- "보통의 사람을 위한 로펌" 포지셔닝
- 토스피드 본문 자료의 미니멀 톤

## 컬러 룰
- 흑백(neutral) + brand.primary(#a91c51) 조합으로 90% 커버
- brand.primary는 **강조 포인트로만**:
  - 표의 한 컬럼/행
  - 차트의 메인 라인 또는 첫 번째 항목
  - 강조 텍스트 (수치, 핵심 키워드)
- accent.success/warning은 거의 안 씀 (체크 표시 등 한정)
- **금지**: 다채로운 컬러 팔레트, 레인보우 톤, 그라데이션

## 타이포 룰
- Pretendard 단일 폰트
- **모바일 가독성 절대 룰: 모든 본문 최소 28px** (1200px wide 카드 기준)
- 출처/메타는 20px까지 OK
- 줄 간격 본문 1.5, 제목 1.3

## 레이아웃 룰
- 여백 충분히 (카드 padding 최소 64px)
- 텍스트 정렬: 좌측 정렬 기본 (제목/본문)
- 데이터 (숫자, 비용): 우측 정렬 또는 중앙 정렬

## 금지사항
- 망치/저울/정의의 여신상 클리셰 (법조 일반 묘사)
- 외국 법정 묘사
- 시간 압박/공포 마케팅 카피 ("당신만을 위한", "지금 아니면", "골든타임")
- 클립아트 풍 일러스트
- 부정확한 데이터 (본문 숫자 다른 값으로 변형)
- 가짜 출처

## 권장사항
- 한국 맥락 (필요시)
- 차분한 색감 우선
- 출처 표기 (차트, 통계는 반드시)
- 텍스트는 본문 그대로 (의역 X)

## 변호사법 §23 컴플라이언스 (이미지 안 텍스트도 적용)

다음 표현은 **이미지 텍스트로도 사용 금지** (인포그래픽/차트/표/카드 모두):

### 절대성 표현 (금지)
- "최저가", "최고", "유일한", "100% 승소", "반드시 이긴다"
- "모든 사건 해결", "절대로", "완벽한 해결"

### 마케팅 과장 (금지)
- "당신만을 위한", "특별 혜택", "한정 기회"
- "단 한 번의", "놓치면 안 되는"

### 시간 압박 (금지)
- "지금 아니면 늦는다", "골든타임", "마지막 기회"
- "시간이 없습니다", "오늘 안에"

### 비교 광고 (금지)
- "타 로펌과 달리", "경쟁사 대비"
- 다른 법무법인 명시 비교

### 검사 시점
- prompt_review (생성 전): 입력 데이터/프롬프트에 위 표현 포함 여부
- image_review (생성 후): 결과 이미지의 텍스트(OCR 또는 LLM vision)에서 검사
```

---

## 6. 파이프라인 정의

`pipeline_defs/blog_image.yaml`:

```yaml
name: blog_image
version: 1.1.0
description: 블로그/웹 페이지 한 건의 이미지를 생성·배치한다

input_schema:
  page_id: string
  page_source: enum [blog, web]
  notion_page_blocks: array

stages:
  - name: analyze_content
    skill: meta/slot_selection.md
    output: { image_slots: array }
    description: |
      본문 블록을 읽고 image_slots 결정 (0개도 가능, 보통 1-4개).
      각 슬롯: { type, sub_type?, position_after_block_id, extracted_data }

  - name: generate_per_slot
    foreach: image_slots
    sub_stages:
      - name: read_skill
        action: load_skill
        path: image_types/{slot.type}.md

      - name: prepare_data
        skill: image_types/{slot.type}.md
        output: { data: object } | { prompt: string, references: array }

      - name: review_input
        skill: meta/prompt_review.md
        output: { passed: boolean, issues: array }
        on_fail: revise (max 1 회)

      - name: generate_image
        tool: |
          if slot.type in [simple_table, chart, comparison_table,
                           key_points_card, stat_highlight]:
            tools/render/template_render.py (chart는 chart_render.py)
          else:
            tools/image/gpt_image_2.py
        output: { image_path: string, cost_usd: float }

      - name: review_image
        skill: meta/image_review.md
        output: { passed: boolean, issues: array }
        on_fail:
          - regenerate (max 1 회) per regen_policy.md
          - if still fail: mark slot as `failed`, continue

      - name: upload_to_notion
        tool: tools/notion/upload_image.py + insert_image_block.py
        output: { notion_block_id: string }

      - name: log_metadata
        tool: tools/notion/log_metadata.py

  - name: update_status
    description: |
      처리 결과에 따라 페이지 status 결정:
        - 모든 슬롯 성공 (또는 슬롯 0개) → "발행필요"
        - 일부 또는 전부 슬롯 실패 → "이미지 작업 중"
      참고: 슬롯 0개 케이스는 사실상 거의 발생 안 함 (콘텐츠가 보통 2000자+).
            발생 시에도 발행필요로 진행 (LLM 판단 신뢰).
    tool: tools/notion/update_status.py

quality_gates:
  - id: input_review_passes
    when: after each prepare_data
  - id: image_review_passes
    when: after each generate_image

budget:
  per_page_cap_usd: 0.30
  per_run_cap_usd: 3.00
  on_exceed: stop_and_log
```

---

## 7. 카드 타입 가이드 (Skills)

### 7.1 공통 skill 구조

각 `skills/image_types/{name}.md`의 표준 구조:

```markdown
# {카드 타입명}

## When to use
[본문 패턴]

## Generation method
- Template (HTML + Playwright) | AI (gpt-image-2)

## Card size
default | square | vertical (styles/ehyun_default.yaml 참조)

## Variables to extract (template) | Prompt template (AI)
[구체적 정의]

## Reference images
- reference_library/{category}/...

## Quality criteria (셀프 리뷰)
- [ ] ...
```

### 7.2 P0 카드: simple_table

```markdown
# simple_table

## When to use
본문에 단순 표 형식의 정보 (구분/대상/금액 같은 행 단위 데이터).
2~3 컬럼, 5~10 행 정도가 적합.

## Generation method
Template (HTML + Playwright)

## Card size
default (1200x675) — 행이 많으면 vertical (1080x1350)

## Variables
- title: string (옵션)
- headers: list[string] (2-3개)
- rows: list[list[string]]
- footnote: string (옵션)

## Style
- 헤더 행: neutral.100 배경 + neutral.800 텍스트, body 30px, semibold
- 본문 행: white 배경 + neutral.700 텍스트, body_sm 28px, regular
- 행 구분선: neutral.200, 1px
- 정렬: 첫 컬럼 좌측, 나머지 우측 (숫자 위주)

## Reference images
- reference_library/simple_table/scholarship_table.png
- reference_library/simple_table/region_deposit_table.png

## Quality criteria
- [ ] 본문에 명시된 텍스트만 셀에 사용
- [ ] 헤더 명확히 구분
- [ ] 모든 셀 텍스트 최소 28px
- [ ] 행 5개 이하면 default, 6+ 면 vertical
- [ ] 변호사법 §23 금지 표현 없음
```

### 7.3 P0 카드: chart (코어 — 가장 자주 사용)

```markdown
# chart

## When to use
본문에 시계열 추이, 분포, 비율, 카테고리 비교 데이터가 있을 때.
이현 콘텐츠에서 가장 자주 사용되는 카드.

## Generation method
Template (HTML + Chart.js + Playwright)

## Card size
default (1200x675)

## Sub-types (점진 확장)
- `line`: 시계열 추이 ← **Phase 1 시작점**
- `bar`: 카테고리 비교 ← Phase 2에서 추가
- `donut`: 분포 (3-5개 항목) ← Phase 2에서 추가
- `pie`: 분포 (다수 항목) ← Phase 2에서 추가

각 sub-type은 Phase 1 line 검증 후 점진적으로 추가. 모든 sub-type을 한 번에 만들지 마라.

## Variables (공통)
- title: string (h2 38px)
- chart_type: line | bar | donut | pie
- data: ChartData (sub-type별 스키마)
- source: string ("출처: <기관명>, <연도>")

## Variables (sub-type별)
### line
- data.labels: list[string]
- data.values: list[number]
- data.point_labels: list[string] (각 포인트 위 라벨)

### bar
- data.labels: list[string]
- data.values: list[number]
- data.bar_labels: list[string]
- data.series_name: string (옵션, 범례)

### donut / pie
- data.labels: list[string]
- data.values: list[number]
- data.center_text: string (옵션, donut)

## Style (공통)
- 카드 padding: 64px
- 제목: top-left, h2 38px, neutral.800, bold
- 차트 영역: 카드 중앙
- 출처: bottom-left, small 20px, neutral.400, "출처: <X>, <Y>"

## Style (sub-type별 디테일)

### line
- line_color: brand.primary 또는 neutral.800
- line_width: 4px
- point: filled circle, 12px diameter
- point_label: above_point, 28-32px, bold, neutral.900
- gridlines: horizontal only, 4-5개, neutral.200
- x_axis_labels: 24px, neutral.500
- y_axis: 숨김

### bar
- bar_color: brand.primary 또는 neutral.800 (단색)
- bar_radius: 4px (top-only)
- bar_label: above_bar, 28-32px, bold
- gridlines: horizontal only
- legend: top-right (시리즈 2+ 일 때만, 28px)

### donut
- colors: [brand.primary, neutral.700, neutral.400, neutral.300, neutral.200]
- 첫 번째(가장 큰 비중) = brand.primary
- thickness: 80px
- center_text: 큰 숫자 또는 비워둠
- label_position: outside_with_line
- label_size: 24px
- legend: right, 28px

### pie
- colors: [brand.primary, neutral.tones...]
- labels: percent only, inside slice, 24px
- legend: right, 28px

## Reference images
- reference_library/chart/toss_*.png  (토스피드 캡처, 시드 레퍼런스)
- reference_library/chart/ehyun_*.png  (회사 자산)

## Data validation (CRITICAL)
- 본문에 명시된 숫자 외 절대 사용 금지
- donut/pie: 합계 100% 검증, 아니면 경고 + 진행
- 최소 데이터 포인트 2개 (1개면 stat_highlight로 폴백 — P1 대기)
- 라벨 길이 최대 12자, 초과 시 줄바꿈

## Quality criteria
- [ ] 차트 제목 명확
- [ ] 모든 라벨 최소 24px
- [ ] 데이터 라벨 정확 (본문과 1:1)
- [ ] 출처 표기됨
- [ ] brand.primary - 메인 데이터에만
- [ ] 변호사법 §23 금지 표현 없음
```

### 7.4 P0 카드: comparison_table

```markdown
# comparison_table

## When to use
이현 vs 경쟁사, 옵션 A vs B 등 두 개 이상의 옵션을 항목별 비교.

## Generation method
Template (HTML + Playwright)

## Card size
default (1200x675) — 항목 많으면 vertical

## Variables
- title: string (옵션)
- column_headers: list[string]
- highlight_column_index: int (보통 0 = 이현)
- rows: list[{label: string, values: list[string]}]
- footnote: string (옵션)

## Style
- 카드 배경: neutral.50 또는 brand.primary_soft
- 제목: h1 52px, top-center
- 컬럼 헤더: body_large 34px, semibold
  - highlight_column: brand.primary 텍스트 + brand.primary_soft 배경
  - 다른 컬럼: neutral.500 텍스트
- row label: body 30px, neutral.700, 좌측
- row values: body_sm 28px
  - highlight_column: brand.primary 텍스트, semibold
  - 다른 컬럼: neutral.700, regular

## Reference images
- reference_library/comparison_table/*.png

## Quality criteria
- [ ] highlight_column 시각적 구분 명확
- [ ] 본문 명시 텍스트만 사용
- [ ] 모든 셀 최소 28px
- [ ] 비교 광고 표현 없음 (변호사법 §23) — 다른 법무법인 명시 X
```

### 7.5 P0 카드: key_points_card

```markdown
# key_points_card

## When to use
본문에 "핵심 3가지", "준비 서류", "체크리스트", "요약" 패턴.

## Generation method
Template (HTML + Playwright)

## Card size
default (1200x675)

## Variables
- title: string
- variant: numbered | checked | bulleted
- items: list[{label: string, description: string?}]  (3-5개)

## Style
- 카드 배경: white 또는 neutral.50
- 제목: h1 52px, semibold, neutral.800
- items 사이 간격: spacing.xl 32px

### variant별
- numbered: 큰 숫자 (h2 38px, brand.primary, bold) + label
- checked: ✓ 아이콘 (accent.success 24px) + label
- bulleted: • (neutral.500) + label

- item label: body_large 34px, semibold, neutral.800
- item description: body_sm 28px, neutral.600

## Quality criteria
- [ ] 항목 3-5개
- [ ] 모든 텍스트 최소 28px
- [ ] variant 일관성
- [ ] 변호사법 §23 금지 표현 없음
```

### 7.6 P1+ 카드들 (Phase 3 이후)

각 카드 정의는 Phase 3 진입 시점에 정교화. P1+ 카드 라인업:

- `stat_highlight`: 단일 숫자 메가 강조 (display 96px). chart 데이터 1개 폴백 처리도 담당
- `document_excerpt`: 판례/법조문 (AI gpt-image-2 thinking)

**제외**: `lawyer_profile` (운영 결정으로 설계에서 제거)

### 7.7 P2 카드 (Phase 4 이후 검토)

- `kakao_dialogue`: 카톡 대화 (AI)
- `app_ui_mockup`: 앱 UI mockup (AI, use case 좁음)

---

## 8. Meta Skills

### 8.1 `skills/meta/slot_selection.md`

```markdown
# Slot Selection

본문 블록을 분석해서 각 H2 섹션마다 어떤 image_type 슬롯이 들어가면 좋을지 결정한다.
0개도 OK이지만, 이현 콘텐츠는 보통 2000자+이라 0개 결정은 거의 없을 것.

## 결정 룰

본문에 다음 패턴이 있으면 해당 카드 후보:

- **표 형식 데이터** (구분/항목/값) → simple_table
- **시계열 추이** (연도별 변화) → chart (line) ← P0
- **카테고리 비교** (X / Y / Z 비율) → chart (bar) ← P2 활성화
- **분포** (전체 중 비율, 3-5개) → chart (donut) ← P2
- **분포** (다수 항목, 6+) → chart (pie) ← P2
- **이현 vs 경쟁사**, "X는 A, Y는 B" → comparison_table
- **핵심 N가지**, "준비 서류", 체크리스트 → key_points_card
- **단일 숫자 강조** ("10명 중 7명") → stat_highlight (P1+)
- **판례/법조문 인용** → document_excerpt (P1+)

## P1 미완 카드 폴백
- chart의 데이터 포인트 1개만 있는 경우 → P1까지 stat_highlight 카드 미완이므로 슬롯 결정 X
- 통계가 다수 있으면 chart로

## 위치 결정
- 해당 정보가 등장하는 H2 섹션의 **첫 단락 직후**
- 단, 섹션 첫 단락이 너무 짧으면 (50자 미만) 다음 단락 후

## 슬롯 개수
- 페이지당 평균 1-3개 권장
- 4개 초과는 본문이 매우 길거나 데이터가 많을 때만
- 0개는 예외적 (콘텐츠 길이상 거의 안 발생)

## 출력 형식
```yaml
image_slots:
  - type: chart
    sub_type: line
    position_after_block_id: <block_uuid>
    extracted_data:
      title: "마스터스 우승 상금 추이"
      labels: ["1985", "1990", ...]
      values: [19, 34, 60, ...]
      point_labels: ["19억 원", "34억 원", ...]
      source: "Golf Digest, GolfWRX"
  - type: simple_table
    position_after_block_id: <block_uuid>
    extracted_data:
      headers: ["구분", "대상", "연간지원금액"]
      rows: [["국가장학금", "기초·차상위", "등록금 전액"], ...]
```
```

### 8.2 `skills/meta/prompt_review.md`

```markdown
# Prompt/Input Review

생성 단계 직전, 입력(template variables 또는 AI prompt)을 셀프 리뷰한다.

## 템플릿 카드 검증
- [ ] 본문에서 추출한 데이터가 정확한가 (숫자, 텍스트)
- [ ] 차트의 경우: 본문 명시 숫자와 1:1 매칭
- [ ] 라벨 길이가 카드 영역에 들어가는가
- [ ] highlight_column 의도 일치
- [ ] 모든 텍스트 최소 28px 룰 violate 안 함

## AI 카드 검증
- [ ] 한국어 문구 명확히 명시 (`exact_korean_strings`)
- [ ] 법률 오류 가능성 (서양 법정, 정의의 여신상 등)
- [ ] 비주얼 가이드 위반 없음

## 변호사법 §23 컴플라이언스
입력 데이터/프롬프트에 다음 표현 검사:
- 절대성 표현 ("최고", "유일한", "100% 승소" 등)
- 마케팅 과장 ("당신만을 위한", "특별 혜택" 등)
- 시간 압박 ("지금 아니면", "골든타임" 등)
- 비교 광고 ("타 로펌과 달리" 등)

위반 발견 시 → 표현 제거 또는 대체. 자동 수정 후 1회 재시도.

## 실패 시
- 1회 자동 수정 시도
- 실패 시: 슬롯을 `failed`로 마킹, 다음 슬롯 진행
```

### 8.3 `skills/meta/image_review.md`

```markdown
# Image Review

이미지 생성 후 결과물을 셀프 리뷰한다.

## 검증 항목
- [ ] 텍스트 정확성 (한국어 오타, 누락)
- [ ] 컬러 팔레트 일치 (brand.primary, neutral 톤)
- [ ] 의도한 콘텐츠 표현
- [ ] 출처 표기 (차트만)
- [ ] 모바일 가독성 (텍스트 충분히 큰가, 28px+)
- [ ] 비주얼 가이드 위반 없음

## 변호사법 §23 컴플라이언스 (이미지 텍스트)
LLM vision으로 이미지 텍스트 추출 후 다음 검사:
- 절대성 표현 검출
- 마케팅 과장 검출
- 시간 압박 검출
- 비교 광고 검출

위반 발견 시 → regenerate (입력 정정 후)

## 실패 시
- regen_policy.md 따라 처리
```

### 8.4 `skills/meta/regen_policy.md`

```markdown
# Regeneration Policy

## 룰
1. 같은 입력으로 1회 재생성
2. 실패 시: 입력 수정 후 1회 재시도
3. 그래도 실패: 슬롯을 `failed`로 마킹, 계속 진행

## 페이지 status 룰
- 모든 슬롯 성공 (또는 슬롯 0개) → "발행필요"
- 1개 이상 슬롯 `failed` → "이미지 작업 중"
- "이미지 작업 중" 페이지는 cron이 다시 처리하지 않음 (사람 개입 대기)

## 비용 가드
- 페이지당 재생성 총 시도 cap: 4회
- 초과 시 강제 종료, 페이지를 "이미지 작업 중"으로 마킹
```

### 8.5 `skills/meta/notion_placement.md`

```markdown
# Notion Placement

## 룰
- 슬롯 결정 시 `position_after_block_id` 함께 결정
- Notion API의 `append_block_children` 사용해 해당 block 다음에 image block 삽입
- 캡션은 옵션 (차트의 source는 카드 안에 이미 있음)

## image block 삽입 방식
1. `tools/notion/upload_image.py` → file_upload_id 획득
2. `tools/notion/insert_image_block.py` → after_block_id 다음에 새 image block
3. block_id는 작업 로그의 `입력 (JSON)` 안에 포함시켜 저장
```

---

## 9. 도구 (Tools)

### 9.1 Notion

```python
# tools/notion/fetch_pages.py
async def fetch_pages_by_status(
    database_id: str,
    status: str,
    limit: int = 5,
) -> list[Page]:
    """status가 일치하는 페이지 N개를 fetch."""

# tools/notion/get_page_content.py
async def get_page_blocks(page_id: str) -> list[Block]:
    """페이지 본문의 모든 블록을 재귀적으로 가져옴."""

# tools/notion/upload_image.py
async def upload_image(file_path: str) -> str:
    """File Upload API로 업로드, file_upload_id 리턴.
    
    20MB 이하: 단일 요청.
    1시간 안에 page/block에 attach 안 하면 archived됨.
    Attach되면 영구 보존.
    """

# tools/notion/insert_image_block.py
async def insert_image_block(
    parent_id: str,
    after_block_id: str,
    file_upload_id: str,
    caption: str = "",
) -> str:
    """본문 특정 위치 다음에 image block 삽입, 새 block_id 리턴."""

# tools/notion/update_status.py
async def update_page_status(page_id: str, status: str) -> None:
    """페이지 status select 속성 변경.
    
    유효 값은 Phase 0에서 fetch한 옵션 목록에서.
    """

# tools/notion/log_metadata.py
async def log_metadata(
    log_db_id: str,
    page_id: str,
    page_source: Literal["blog", "web"],
    slot_type: str,
    slot_sub_type: str | None,
    generation_method: str,
    input_data: dict,           # template vars or AI prompt + block_id 등
    cost_usd: float,
    attempts: int,
    review_passed: bool,
    image_path: str | None,
) -> None:
    """작업 로그 DB에 row 추가.
    
    내부 처리:
    - page_id를 노션 mention 객체로 변환해서 '관련 페이지' rich_text 속성에 박음:
      {"type": "mention", "mention": {"type": "page", "page": {"id": page_id}}}
    - input_data는 JSON 문자열화해서 '입력 (JSON)' 속성에 저장 (block_id 포함)
    - page_source는 '출처' select 속성에 (블로그/웹)
    """
```

### 9.2 렌더링 (코어)

```python
# tools/render/template_render.py
async def render_template(
    template_name: str,
    variables: dict,
    output_format: Literal["webp", "png"] = "webp",
    card_size: str = "default",
) -> str:
    """templates/{name}.html을 Playwright로 렌더링.
    
    내부 처리:
    1. HTML 템플릿 + variables 주입 → 임시 HTML 파일
    2. Playwright Chromium headless로 PNG screenshot (Playwright는 PNG/JPEG만 직접 지원)
    3. output_format="webp"면 webp_converter.py로 변환
    4. file_path 리턴
    """

# tools/render/chart_render.py
async def render_chart(
    chart_type: Literal["line", "bar", "donut", "pie"],
    data: ChartData,              # pydantic, 데이터 검증
    title: str,
    source: str | None = None,
    output_format: Literal["webp", "png"] = "webp",
) -> str:
    """templates/chart.html + Chart.js 옵션 + Playwright 렌더 + WebP 변환."""
```

### 9.3 이미지 후처리

```python
# tools/image/webp_converter.py
async def png_to_webp(
    png_path: str,
    quality: int = 90,
    output_path: str | None = None,
) -> str:
    """PNG → WebP 변환 (pillow 사용).
    
    Playwright 출력은 PNG라서 후처리 필요.
    quality 90이 사이즈/품질 균형점.
    """
```

### 9.4 AI (P1+)

```python
# tools/image/gpt_image_2.py
async def generate_image(
    prompt: str,
    mode: Literal["instant", "thinking"] = "instant",
    reference_images: list[str] = [],
    aspect_ratio: str = "16:9",
    output_format: Literal["webp", "png"] = "webp",
) -> tuple[str, float]:
    """gpt-image-2 호출, (file_path, cost_usd) 리턴.
    
    Phase 3에서 구현.
    """
```

### 9.5 LLM

```python
# tools/llm/analyze_content.py
async def analyze_blocks(blocks: list[Block]) -> ContentAnalysis: ...

# tools/llm/review.py
async def review_input(input_data: dict, slot: SlotSpec) -> ReviewResult: ...
async def review_image(image_path: str, slot: SlotSpec) -> ReviewResult:
    """LLM vision으로 이미지 검사.
    
    텍스트 정확성 + 변호사법 §23 컴플라이언스 검사.
    """
```

---

## 10. Notion DB 스키마

### 10.1 입력 DB (2개)
- **블로그 콘텐츠 DB** (인블로그) — 실제 title: `[MST] 블로그`
- **웹 콘텐츠 DB** (ehyun.ai.kr) — 실제 title: `[MST] 웹 콘텐츠`

본문 구조 동일. 속성 일부 차이. 같은 처리 룰 적용.

**상태 속성** (이름: `상태`, 한글, 띄어쓰기 포함): Phase 0에서 Notion API로 자동 fetch. 시스템이 사용하는 옵션 값:
- 입력: `이미지 필요`
- 출력 1: `발행 필요` (모든 슬롯 성공 또는 슬롯 0개)
- 출력 2: `이미지 작업 중` (1개 이상 슬롯 실패)

### 10.2 신규: `이미지 작업 로그` DB

> **align 노트 (2026-05-06)**: 운영팀이 노션에서 만든 실제 DB의 한국어 컨벤션에 맞춰 갱신. 코드/문서가 운영 현실에 align되어야 한다는 원칙. 콘텐츠 DB의 `상태` 속성도 한글.

#### 필수 속성 (Phase 1부터 사용)

| 속성명 | 타입 | 비고 |
|--|--|--|
| 작업 ID | title | UUID 또는 timestamp |
| 출처 | select | `블로그` / `웹` |
| 관련 페이지 | rich_text | 노션 mention 객체로 페이지 연결 (≈ `[[페이지 제목]]`) |
| 타입 | select | simple_table / chart / comparison_table / key_points_card / stat_highlight / document_excerpt |
| 차트 타입 | select | line / bar / donut / pie (slot=chart일 때만) |
| 생성 방식 | select | template / gpt-image-2-instant / gpt-image-2-thinking |
| 입력(JSON) | rich_text | template 변수 또는 AI 프롬프트 + notion_block_id 포함. 공백 없음 주의 |
| 비용 USD | number | 0.000 |
| 시도 횟수 | number | |
| 셀프 리뷰 | checkbox | |
| 생성 일시 | created_time | |

#### 권장 속성 (Phase 4 학습 루프 진입 전까지 추가)

| 속성명 | 타입 | 비고 |
|--|--|--|
| 사람이 교체함 | checkbox | 검수자가 결과 이미지 교체 시 마킹. **Phase 4 학습 시그널의 핵심** |
| 결과 이미지 | files | 이미지 사본 (옵션) |

**relation 속성 없음** — `관련 페이지`를 rich_text + mention으로 처리. 콘텐츠 DB 스키마 무영향.

---

## 11. 레퍼런스 라이브러리

### 11.1 시드 절차
1. **figma 회사 자산 export**:
   - simple_table: 4-5장
   - chart: 1-2장 (회사 자산)
   - comparison_table: 4-5장
   - key_points_card: 3-5장

2. **토스피드 캡처** (chart 부족분):
   - reference_library/chart/toss_line_*.png (2-3장)
   - reference_library/chart/toss_bar_*.png (2장)
   - reference_library/chart/toss_donut_*.png (2장)
   - reference_library/chart/toss_pie_*.png (1-2장)
   - **저작권 주의**: 시드 prompt input 용도만, 외부 노출 X

3. `reference_library/_meta.yaml` 작성

### 11.2 `_meta.yaml` 구조

```yaml
simple_table:
  - file: scholarship_table.png
    style: { background: white, header: gray, accent: navy }
    use_when: "단순 정보 표"
    text_density: medium

chart:
  - file: toss_line_consumption_trend.png
    style: { color: navy, type: line }
    use_when: "시계열 추이"
    source: "토스피드 (시드 레퍼런스, 외부 노출 금지)"
  - file: ehyun_masters_prize_line.png
    style: { color: navy, type: line }
    use_when: "시계열 추이, 큰 변동"
  # ...

comparison_table:
  - file: ehyun_debt_collection_v1.png
    style: { background: beige, accent: burgundy, layout: 2-column }
```

### 11.3 활용 방식
- **AI 카드** (document_excerpt 등): 카테고리에서 1-2장을 image input
- **템플릿 카드**: CSS 스타일 가이드로 참조 (hex/사이즈 추출), Phase 1 코드 작성 시 1:1 재현 목표

---

## 12. 구현 단계 (Phases)

### Phase 0: Setup (1-2일)

**목표**: 빈 레포 + 의존성 설치 + Notion 연결 + status 옵션 확인

- [ ] 레포 생성: `lawfirm-ehyun/ehyun-image-agent`
- [ ] Python 3.12 + `uv init`
- [ ] 의존성 설치: `uv add claude-agent-sdk notion-client pillow pydantic pyyaml httpx playwright`
- [ ] `playwright install chromium`
- [ ] **claude-agent-sdk 정확한 import / 모델 ID 확인** (SDK 문서 참조하여 v1.1 patch)
- [ ] Notion integration 토큰 발급 (https://www.notion.so/profile/integrations)
- [ ] **`이미지 작업 로그` DB 생성** (섹션 10.2 스키마 그대로)
- [ ] **3개 DB에 integration 권한 부여** (read + write 모두):
  - 블로그 콘텐츠 DB
  - 웹 콘텐츠 DB
  - 이미지 작업 로그 DB
- [ ] **Notion API로 콘텐츠 DB의 status 옵션 목록 fetch + 검증** (`이미지 필요`, `발행 필요`, `이미지 작업 중` 존재 확인)
- [ ] `.env.example` 작성, `.env`로 복사
- [ ] GitHub Actions secrets 등록 (NOTION_TOKEN, NOTION_DB_BLOG, NOTION_DB_WEB, NOTION_DB_LOG, ANTHROPIC_API_KEY)
- [ ] `pyproject.toml` 정리 (ruff, pytest)
- [ ] `scripts/download_fonts.sh` 작성 + 실행 (Pretendard 4 weights → assets/fonts/)

**검증**: 
- `python -c "from notion_client import Client; print(Client(auth=os.environ['NOTION_TOKEN']).databases.retrieve(os.environ['NOTION_DB_BLOG']))"` 성공
- 콘텐츠 DB의 status 옵션에 `이미지 필요`, `발행 필요`, `이미지 작업 중` 모두 존재 확인

### Phase 1: 디자인 시스템 + 카드 2개 (3-5일)

**목표**: simple_table + chart_line 카드를 코드로 렌더링 가능

- [ ] **시드 레퍼런스 라이브러리 구축**
  - figma 회사 자산 export → reference_library/{category}/
  - 토스피드 차트 캡처 5-7장 → reference_library/chart/toss_*.png
  - reference_library/_meta.yaml 작성
- [ ] **디자인 토큰 작성**: `styles/ehyun_default.yaml` (섹션 4 그대로)
- [ ] **비주얼 가이드 작성**: `skills/style/ehyun_visual_guide.md` (섹션 5 그대로)
- [ ] **`templates/_base.css`** 작성 (CSS 변수 + Pretendard @font-face)
- [ ] **`templates/simple_table.html`** 작성 (회사 자산 1:1 재현)
- [ ] **`templates/chart.html`** 작성 (Chart.js + 토스피드 톤 line)
- [ ] **`tools/render/template_render.py`** (Playwright)
- [ ] **`tools/render/chart_render.py`** (Chart.js + 데이터 검증)
- [ ] **`tools/image/webp_converter.py`** (PNG → WebP, pillow)
- [ ] **`tools/notion/`** 6개 파일 모두 구현
- [ ] **수동 호출 스크립트** (`scripts/test_phase1.py`): 1개 페이지에 simple_table + chart_line 1장씩 생성/업로드 검증
- [ ] **사용자 검증**: 결과 이미지 톤 OK?

**Phase 1 종료 게이트**: 사용자 "이 정도면 OK" 승인.

### Phase 2: 카드 추가 + 파이프라인 + chart sub-type 확장 (5-7일)

**목표**: 카드 4종 완성 + 자동 파이프라인 가동 (수동 trigger)

- [ ] **`templates/comparison_table.html`** (회사 자산 1:1 재현)
- [ ] **`templates/key_points_card.html`** (3 variants)
- [ ] **chart sub-type 확장**: bar → donut → pie 순서로 검증하며 추가
  - 각 sub-type 추가 후 사용자 톤 검증 게이트
- [ ] **`skills/image_types/{simple_table,chart,comparison_table,key_points_card}.md`** (섹션 7 참조)
- [ ] **`skills/meta/{slot_selection,prompt_review,image_review,regen_policy,notion_placement}.md`** (섹션 8 참조)
- [ ] **`pipeline_defs/blog_image.yaml`** (섹션 6)
- [ ] **`tools/llm/{analyze_content,review}.py`**
- [ ] **`orchestrator.py`** (Claude Agent SDK)
- [ ] **`.github/workflows/cron.yml`** 작성하되 **`workflow_dispatch`만 활성화** (cron schedule은 Phase 3에서)
- [ ] **수동 trigger** (workflow_dispatch)로 5개 페이지 처리 + 검수
- [ ] **사용자 검증**: 5건 모두 통과 가능?

### Phase 3: Cron 가동 + P1 카드 (5-7일)

**목표**: 무인 cron 가동 + stat_highlight + document_excerpt 추가

- [ ] **`cron.yml`의 schedule 활성화** (1일 1회로 시작)
- [ ] **`templates/stat_highlight.html`**
- [ ] **`skills/image_types/{stat_highlight,document_excerpt}.md`** 작성
- [ ] **`tools/image/gpt_image_2.py`** 구현 (Instant + Thinking)
- [ ] **document_excerpt** AI 생성 검증 (Image 6 톤)
- [ ] **slot_selection.md 갱신**: stat_highlight 활성화, chart 1개 폴백 룰 갱신
- [ ] **1주일 cron 운영** + 매일 검수
- [ ] **사용자 검증**: 운영 안정성 + 품질

### Phase 4: 학습 루프 + P2 (2주차+, 지속적)

- [ ] `이미지 작업 로그` DB의 "사람이 교체함" 마킹 패턴 분석
- [ ] 자주 교체되는 슬롯/sub-type 식별
- [ ] 프롬프트/템플릿 개선
- [ ] (검토) `kakao_dialogue` 추가
- [ ] (검토) `app_ui_mockup` 추가
- [ ] cron 주기 30분으로 단축 (안정화 후)

---

## 13. 비용 / 예산

### 13.1 단가 (26년 5월)
| 항목 | 단가 |
|--|--|
| Template 렌더링 | $0 |
| gpt-image-2 medium | ~$0.053 / 장 |
| gpt-image-2 thinking | ~$0.10-0.15 / 장 |
| Claude Sonnet (분석/리뷰) | ~$0.005 / 페이지 |
| Claude vision (image_review) | ~$0.005 / 이미지 |

### 13.2 페이지당 평균
- **P0 (템플릿만)**: ~$0.02
- **P1 (AI 일부)**: ~$0.10
- **P2 (AI 다수)**: ~$0.20

### 13.3 월 비용 (블로그 + 웹 합쳐서 주 10편 × 4주 = 40편)
- P0: ~$0.8/월
- P1: ~$4/월
- P2: ~$8/월

**Cap**: $20/월 (오류/재생성 버퍼).

---

## 14. 사용자 사전 작업 체크리스트

빌드 시작 전 사용자가 해놔야 할 것들:

### 디자인 자산
- [ ] **figma 디자인 시스템 정돈**: 흩어진 카드 시안들을 한 페이지에 "이현 디자인 시스템 v1"으로 정리. Claude Code가 정확히 재현 가능하도록
- [ ] (선택) 이현 로고 svg/png

### Notion 환경
- [ ] Notion integration 발급
- [ ] 블로그 콘텐츠 DB ID 확보
- [ ] 웹 콘텐츠 DB ID 확보
- [ ] **`이미지 작업 로그` DB 생성** (섹션 10.2 스키마)
- [ ] 3개 DB 모두 **read + write** integration 권한 부여
- [ ] **콘텐츠 DB의 status 옵션 확인**: `이미지 필요`, `발행 필요`, `이미지 작업 중` 모두 존재해야 함. 없으면 추가

### API 계정
- [ ] Anthropic API key (Phase 0부터 필요)
- [ ] OpenAI API key (Phase 3에서 필요)

### GitHub
- [ ] `lawfirm-ehyun` 조직에 새 레포 생성 권한 확인
- [ ] GitHub Actions secrets 등록 준비

### 시드 자산
- [ ] **figma export 가능한 카드 시안 인벤토리** (어떤 카드들이 회사 자산으로 있는지 목록)

---

## 15. orchestrator.py (참조 구현)

```python
"""orchestrator.py — GitHub Actions cron 진입점"""
import asyncio
import os
from claude_agent_sdk import Agent  # ※ 정확한 import는 Phase 0에서 확인
from tools.notion.fetch_pages import fetch_pages_by_status
from tools.notion.get_page_content import get_page_blocks
# ... 다른 tools import

async def process_database(agent, db_id: str, source: str) -> None:
    """한 DB의 처리 대상 페이지들 처리."""
    pages = await fetch_pages_by_status(
        database_id=db_id,
        status="이미지필요",
        limit=5,
    )
    if not pages:
        return

    for page in pages:
        try:
            blocks = await get_page_blocks(page.id)
            await agent.run(
                input={
                    "page_id": page.id,
                    "page_source": source,    # "blog" or "web"
                    "blocks": blocks,
                },
                pipeline="blog_image",
            )
        except Exception as e:
            print(f"[{source}] 페이지 {page.id} 처리 실패: {e}")
            # 다음 페이지로 계속

async def main() -> None:
    agent = Agent(
        model="<phase-0-에서-확정>",      # ※ Phase 0에서 SDK 문서 참조하여 확정
        skills_dir="./skills",
        pipeline_path="./pipeline_defs/blog_image.yaml",
        tools=[
            # notion
            fetch_pages_by_status,
            get_page_blocks,
            upload_image,
            insert_image_block,
            update_page_status,
            log_metadata,
            # render
            render_template,
            render_chart,
            png_to_webp,
            # llm
            analyze_blocks,
            review_input,
            review_image,
            # image (P3+)
            # generate_image,
        ],
        budget_cap_usd=3.00,
    )

    # 두 콘텐츠 DB 처리
    await process_database(agent, os.environ["NOTION_DB_BLOG"], "blog")
    await process_database(agent, os.environ["NOTION_DB_WEB"], "web")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 16. GitHub Actions Cron

`.github/workflows/cron.yml`:

```yaml
name: blog-image-agent
on:
  # Phase 2까지: workflow_dispatch만
  # Phase 3+: schedule 활성화
  schedule:
    - cron: '0 */1 * * *'   # 1시간마다 (안정화 후 30분으로 단축)
  workflow_dispatch:

jobs:
  run:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install uv
      - run: uv sync
      - run: uv run playwright install chromium
      - run: bash scripts/download_fonts.sh
      - run: uv run python orchestrator.py
        env:
          NOTION_TOKEN: ${{ secrets.NOTION_TOKEN }}
          NOTION_DB_BLOG: ${{ secrets.NOTION_DB_BLOG }}
          NOTION_DB_WEB: ${{ secrets.NOTION_DB_WEB }}
          NOTION_DB_LOG: ${{ secrets.NOTION_DB_LOG }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}  # P3+
```

---

## 17. 미결정 사항 (Phase별 결정)

| 항목 | 결정 시점 |
|--|--|
| 인블로그 권장 사이즈가 default 3종으로 충분한지 | Phase 1 검증 시점 |
| claude-agent-sdk 정확한 API/모델 ID | Phase 0 setup |
| 변호사법 차단 표현 추가/조정 | Phase 3 운영 후 |

---

## 18. 참고 자료

- [OpenMontage](https://github.com/calesthio/OpenMontage) — agent-first 패턴 원본
- [Anthropic Agent SDK](https://docs.claude.com/en/api/agent-sdk)
- [Playwright Python](https://playwright.dev/python/)
- [Chart.js](https://www.chartjs.org/)
- [Pretendard](https://github.com/orioncactus/pretendard)
- [GPT-Image-2](https://developers.openai.com/api/docs/models/gpt-image-2) — P3+
- [Notion File Upload API](https://developers.notion.com/docs/working-with-files-and-media)
- [Notion API: Mention objects](https://developers.notion.com/reference/rich-text#mention)
- [Figma REST API](https://www.figma.com/developers/api) — 시드 추출용

---

## Changelog

- **v1.1** (2026-05-04):
  - 콘텐츠 DB 권한: read **+ write** 명시
  - WebP 후처리 도구 (webp_converter.py) 추가
  - status 흐름 확정: 부분 성공 → "이미지 작업 중", 모든 성공/0개 → "발행필요"
  - "이미지 작업 중" cron 재시도 X (사람 개입 대기)
  - 0개 슬롯 케이스 → 사실상 발생 안 함 (콘텐츠 2000자+), 발행필요로 진행 (LLM 신뢰)
  - Phase 1 → 2 → 3 chart sub-type 점진 확장 룰 명시
  - Phase 2 trigger: workflow_dispatch만, Phase 3에서 cron schedule 활성화
  - log_metadata: page_id를 노션 mention 객체로 변환 (relation 미사용)
  - lawyer_profile 카드 **설계에서 제거**
  - 작업 로그 DB 스키마: relation → rich_text(mention), `Notion block ID` 속성 제거 (입력 JSON에 통합), `출처` (블로그/웹) select 추가
  - 변호사법 §23 컴플라이언스 룰 정식 추가 (prompt_review + image_review)
  - 두 콘텐츠 DB (블로그 + 웹) 통합 처리 흐름
  - Pretendard 자동 다운로드 스크립트 (scripts/download_fonts.sh)
  - chart 데이터 1개 폴백 → P1까지 슬롯 결정 X
  - chart 카드 sub-type 우선순위: line(P1) → bar/donut/pie(P2)
- v1.0: 첫 finalize. 디자인 토큰 + 모바일 가독성 룰 + 차트 정교화.
- v0.2: 카드 라인업 재정리. Template-first 사상 강조.
- v0.1: 초안.

---

**Version**: 1.1.0
**Maintainer**: 수연 / 마케팅팀
**Status**: ✅ 빌드 시작 가능 (사용자 사전 작업 완료 후)
