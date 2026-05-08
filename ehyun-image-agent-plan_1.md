# 이현 블로그 이미지 에이전트 — 빌드 계획서 (v1.2)

> 법무법인 이현의 블로그 + 웹 콘텐츠용 이미지를 자율 생성·배치하는 에이전트.
> Notion 워크플로 안에서 동작하며, OpenMontage의 agent-first / pipeline-driven 패턴을 차용한다.
>
> **이 문서는 다른 Claude Code 세션이 그대로 받아서 빌드를 시작할 수 있도록 작성된 단일 계획서다.**

---

## 다음 세션 시작 instruction (Claude Code에게)

이 계획서를 컨텍스트로 받았다면:

1. 이 문서 전체를 먼저 읽어라 (특히 v1.2 추가분: §4 카드 사이즈 정책, §19 운영 가드, §20 Phase 2 진입 체크리스트)
2. 섹션 14의 **사용자 사전 작업 체크리스트**를 사용자에게 확인 요청
3. 모든 사전 작업 완료 확인 후 → 섹션 12의 **Phase 0**부터 시작 (Phase 0/1은 이미 진행 중일 수 있음 — `PROJECT_CONTEXT §6 Phase별 산출물 인덱스` 확인)
4. 각 Phase 완료 시 사용자 검증 요청
5. 절대 Phase 점프 금지. **Phase 1은 카드 2개만 (simple_table, chart sub_type=line)**. 더 만들지 마라
6. 산출물(skill, template, tool)은 매 Phase마다 README 인덱스에 추가
7. **v1.2부터: drift 발견 시 본 계획서를 먼저 갱신**한 뒤 코드 동기화. `CLAUDE.md`는 압축 룰, 본 계획서는 사실 정의.

**핵심 원칙 (절대):**
- **Template-first** — AI 카드는 P1 이후. P0은 코드 템플릿만
- **데이터 정확성 절대 우선** — 차트/표는 본문 명시 숫자 외 절대 사용 금지
- **모바일 가독성 우선** — 모든 텍스트 최소 28px (1200px wide 카드 기준)
- **변호사법 §23 컴플라이언스** — 모든 이미지 텍스트는 광고규제 검사 대상
- **검증 게이트 통과 못한 단계 → 다음 단계 X**
- **MVP 사이즈 지키기** — Phase 1은 카드 2개만
- **width-fixed + content-fit 카드 정책** — 노션 inline은 너비만 고정(1200px), 세로는 콘텐츠 fit. fixed-aspect는 인스타 등 채널용 modifier (Phase 2+). 일관성은 토큰·패딩·min-height 공유로 확보 (§4)
- **운영 결정 SOT** — 본 계획서가 단일 진실원칙. 코드/스킬과 drift 발생 시 본 계획서를 먼저 갱신한 뒤 코드 동기화 (`CLAUDE.md`는 압축 룰, 본 계획서는 사실 정의)

---

## 0. 컨텍스트

**무엇을 만드는가**
Notion 콘텐츠 DB(블로그 + 웹)의 `상태="이미지 필요"` 페이지를 자동 처리해서, 본문 분석 → 이미지 슬롯 결정 → 이미지 생성/렌더링 → Notion에 업로드 + 적절한 위치 배치 → 결과에 따라 `상태` 변경하는 에이전트.

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
│                  GitHub Actions Cron (Phase 3+)              │
│                            │                                  │
│                            ▼                                  │
│                    orchestrator.py                            │
│              (page 단위 try/except, run-level 비용 누적)      │
│                            │                                  │
│                            ▼                                  │
│            tools/llm/_common.py — Claude CLI subprocess        │
│            (bundled claude.exe -p ... --system-prompt ...)     │
│            ↕ skills/*.md 본문을 system_prompt에 직접 inject   │
│            ↕ JSON 응답 파싱 → tools/* in-process 호출         │
└────────┬───────────────────────────────────────────┬─────────┘
         │                                            │
    ┌────▼─────┐                              ┌──────▼──────┐
    │  Notion  │  fetch / upload / status     │  Template   │
    │   API    │  (notion-client 3.0)         │  Renderer   │  ← 코어
    └──────────┘                              │ (Playwright │
                                              │  + Chart.js)│
                                              └──────┬──────┘
                                                     │
                                              ┌──────▼──────┐
                                              │  GPT-Image-2│  ← 보조
                                              │ (P3+ 카드)   │
                                              └─────────────┘

[figma]
└── 디자인 ground truth (자동화 파이프라인 외부)
    - 카드 시안 결정
    - 시드 레퍼런스 추출 (수동, 1회성)
    - 디자인 변경 시 코드 동기화 트리거
```

**중요한 아키텍처 결정 (v1.2)**:
- claude-agent-sdk 0.1.x는 우리 use case(단일 LLM 1회 호출 + 외부 in-process tools)에 비효율
  → SDK 우회. 단 **bundled claude.exe는 그대로 사용** (인증/모델 path는 SDK와 동일).
- skills 자동 로드 X. `tools/llm/_common.load_skill()`로 markdown 본문 읽어 system_prompt에 inject (옵션 A).
- Phase 2/3에 hooks·subagents 필요해지면 SDK 부분 재도입 검토.

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
- `claude-agent-sdk` 0.1.74 — **bundled `claude.exe`만 사용** (SDK 자체 API는 우회. 의존성/인증 path는 SDK가 제공).
- `openai` — P3+ (gpt-image-2)
- `notion-client` 3.0 — Notion 공식 SDK (file_uploads / data_sources 풀 지원, multi-source DB 자동 처리)
- `pillow` 12 — 이미지 후처리 (WebP 변환)
- `pydantic` 2.13 — 스키마 검증 (제한적 — 대부분 dataclass로 충분)
- `pyyaml` 6 — 파이프라인 정의 로드
- `httpx` 0.28 — multi-source DB의 data_source detail retrieve 등 SDK 미커버 endpoint
- `playwright` 1.59 — HTML → PNG 렌더링 (Chromium headless)
- `jinja2` — HTML 템플릿 (StrictUndefined로 누락 변수 즉시 raise)

**LLM 호출 모델** (Phase 1 실측 후 확정):
- `claude-sonnet-4-6` — analyze_content / review_input 양쪽 default. SDK 0.1.74로 안정 호출 검증됨.
- Opus 4.7 (`claude-opus-4-7`)은 SDK ≥ 0.2.111 필요 — Phase 4 학습 루프 진입 시 분석 품질 부족하면 SDK 업그레이드 + Opus 재검토.

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

# 카드 사이즈 정책 (v1.2 — width-fixed + content-fit + 타입별 min-height)
#
# 사상:
#   - 노션 inline 이미지는 너비만 고정, 세로는 콘텐츠 fit (height: auto).
#   - 일관성은 width/padding/min-height 토큰 공유로 확보.
#   - 차트는 시각 비율 일관성 위해 차트 영역 자체를 거의 fixed (Chart.js canvas).
#   - fixed-aspect 카드(square/vertical)는 인스타그램 등 채널용 modifier — Phase 2+.
card_sizes:
  default:                                  # 노션 inline (본문)
    width: 1200
    height: auto
    min_height: 480                         # 너무 납작한 카드 방지 (호흡감)
  # Phase 2+ modifier (인스타용)
  square:   { width: 1080, height: 1080, ratio: '1:1' }
  vertical: { width: 1080, height: 1350, ratio: '4:5' }

# 카드 타입별 권장 높이 범위 (시각 일관성 가이드 — Phase 1)
card_type_sizes:
  simple_table:
    width: 1200
    min_height: 480
    max_height: 1400                        # 행 ~12개. 초과 시 슬롯을 두 개로 분할 권장
  chart_line:
    width: 1200
    canvas_height: 480                      # Chart.js canvas 자체는 거의 고정
    min_height: 700                         # 제목+canvas+출처 합산 안정
    max_height: 800                         # 차트 영역 비율 일관성

# 카드 공통 룰
card_defaults:
  padding: 64px                             # spacing.3xl
  background: '#ffffff'
  text_color: '#1e293b'                     # neutral.800
```

**카드 사이즈 정책 결정 노트 (v1.2)**:
- **What**: 노션 inline용 default 카드는 `width: 1200px` 고정 + `height: auto`. 카드 타입별 `min_height` 토큰으로 호흡감 확보. fixed-aspect 비율은 Phase 2+ modifier(`.card--square`, `.card--vertical`).
- **Why**: 1200×675 fixed는 표 행 수에 따라 잘림/빈 여백 발생, 노션 inline 표시에 부자연스러움. 그렇다고 height 완전 free는 시각 일관성 약화. 타입별 min/max로 절충.
- **차트 예외**: Chart.js는 canvas에 명시적 height가 필요. 차트 카드는 canvas 480px + 제목 + 출처로 사실상 700~800px 범위에 수렴 — 차트 시각 비율 일관성을 유지.
- **검증 룰**: `image_review`의 사이즈 체크는 (1200, 675) fixed가 아니라 **width == 1200 + min_height ≤ 실제 ≤ max_height** 범위 검증으로 갱신 (Phase 2 vision OCR 진입 전 코드 측 보조).

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

/* default: 노션 inline용 — width 고정, height auto, min-height로 호흡감. */
.card {
  width: 1200px;
  min-height: 480px;
  padding: 64px;
  box-sizing: border-box;
  background: #fff;
}
/* 차트 카드는 canvas 영역이 큰 비중 — min-height을 더 높게 잡아 시각 일관성 확보. */
.card--chart { min-height: 700px; }
/* Phase 2+ — 인스타용 fixed-aspect modifier */
.card--square   { width: 1080px; height: 1080px; }
.card--vertical { width: 1080px; height: 1350px; }
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
  page_source: enum [블로그, 웹]            # v1.2: 영문 → 한글. 로그 DB select 옵션과 1:1 매칭.
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
      처리 결과에 따라 페이지 `상태` 결정 (운영 표기 — 띄어쓰기 그대로):
        - 모든 슬롯 성공 (또는 슬롯 0개) → "발행 필요"
        - 일부 또는 전부 슬롯 실패 → "이미지 작업 중"
      참고: 슬롯 0개 케이스는 사실상 거의 발생 안 함 (콘텐츠 보통 2000자+).
            발생 시에도 "발행 필요"로 진행 (LLM 판단 신뢰).
            단 슬롯 0개 페이지 추적 위해 §19 운영 가드 B7 룰에 따라 로그 DB에 1행 기록.
    tool: tools/notion/update_status.py

quality_gates:
  - id: input_review_passes
    when: after each prepare_data
  - id: image_review_passes
    when: after each generate_image
    note: Phase 1엔 형식 검증만 (파일 존재, width=1200, min_height 충족). vision OCR은 Phase 2.

budget:
  # Phase 1 검증 단계 임시값. 실측 ~$0.70/페이지 (analyze 1회 + slot당 review 1회).
  # Phase 2 비용 최적화 후 0.30 복귀 목표 (CLI auto-mode Haiku 동시 호출 끄기, page_text 압축).
  per_page_cap_usd: 1.00       # Phase 1 임시 상한
  per_page_target_usd: 0.30    # Phase 2 안정화 목표
  per_run_cap_usd: 3.00        # batch (Phase 2 cron) 진입점에서 누적 추적 필수
  on_exceed: stop_and_log

# 모든 비용 상수는 단일 source — `tools/limits.py` (Phase 2 진입 전 신설). 본 yaml과 1:1 매칭.
```

---

## 7. 카드 타입 가이드 (Skills)

### 7.0 Phase별 카드 활성화 (v1.2 명시)

| Phase | 활성 카드 | 비고 |
|---|---|---|
| **Phase 1 (현재)** | `simple_table`, `chart` (sub_type=line) | MVP 룰 — 다른 카드 만들지 마라 |
| Phase 2 | + `comparison_table`, `key_points_card` | + chart sub_type bar/donut/pie 점진 추가 |
| Phase 3 | + `stat_highlight` (template), `document_excerpt` (AI) | gpt-image-2 도입 |
| Phase 4 | (검토) `kakao_dialogue`, `app_ui_mockup` | 운영 데이터 기반 |

> 이전 v1.1까지 P0 카드 4종 표시 부분(7.4, 7.5)은 **Phase 2 섹션**으로 의미상 이동 — Phase 1엔 정의만 남기고 구현 X.

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

## Card size (v1.2)
default — width 1200px 고정, height auto (min 480 / max 1400). 행 ~12개 기준.
초과 시 슬롯을 두 개로 분할 권장 (slot_selection 단). 인스타용 vertical은 Phase 2+ modifier.

## Variables
- title: string (**필수** — slot_selection.md title 룰)
- headers: list[string] (2-3개)
- rows: list[list[string]]
- footnote: string (옵션)
- highlight_first_col: bool (좌측 키 컬럼 강조)

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

## Card size (v1.2)
default — width 1200px 고정. Chart.js canvas 자체는 약 480px (시각 비율 일관성).
카드 전체는 제목+canvas+출처 합산해 ~700~800px 범위에 수렴 (min_height 700 / max_height 800).

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

### 7.4 Phase 2 카드: comparison_table

```markdown
# comparison_table

## When to use
이현 vs 경쟁사, 옵션 A vs B 등 두 개 이상의 옵션을 항목별 비교.

## Generation method
Template (HTML + Playwright)

## Card size (v1.2)
default — width 1200px 고정, height auto. 행 많으면 자연 가변 (min 480 / max ~1000 권장).

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

### 7.5 Phase 2 카드: key_points_card

```markdown
# key_points_card

## When to use
본문에 "핵심 3가지", "준비 서류", "체크리스트", "요약" 패턴.

## Generation method
Template (HTML + Playwright)

## Card size (v1.2)
default — width 1200px 고정, height auto. 항목 3-5개 기준 ~600~900px 범위.

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

## 페이지 status 룰 (운영 표기 — 띄어쓰기 그대로)
- 모든 슬롯 성공 (또는 슬롯 0개) → `발행 필요`
- 1개 이상 슬롯 `failed` → `이미지 작업 중`
- `이미지 작업 중` 페이지는 cron이 다시 처리하지 않음 (사람 개입 대기)

## 비용 가드 (v1.2 두 단계)
- 페이지당 cap: $1.00 (Phase 1 임시, 실측 ~$0.70) → $0.30 (Phase 2 안정화 목표)
- 런당 cap: $3.00 (Phase 2 batch 누적)
- 슬롯당 시도 cap: 3회 (첫 시도 + 재시도 2회)
- 초과 시 강제 종료, 페이지를 `이미지 작업 중`으로 마킹
```

> 실제 skill 파일은 `skills/meta/regen_policy.md`. 본 인용 블록은 plan SOT 참조용 — drift 발생 시 plan 먼저 갱신.

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

**상태 속성** — 이름 `상태` (한글), 옵션 값은 모두 **공백 포함** (운영 컨벤션 v1.1 align). 시스템이 사용하는 옵션:
- 입력: `이미지 필요` (공백 O)
- 출력 1: `발행 필요` (모든 슬롯 성공 또는 슬롯 0개)
- 출력 2: `이미지 작업 중` (1개 이상 슬롯 실패)

> ※ 본 계획서 안 모든 코드 예시·설명에서 `이미지필요`(공백 X) 같은 표기 발견 시 운영 표기로 수정. `tools/notion/get_status_property_type()`이 select/status 타입 자동 감지 후 페이로드 분기.

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

### 13.2 페이지당 평균 (Phase 1 실측 기반 v1.2)
- **Phase 1 (템플릿만, 실측)**: ~$0.70 — analyze_content 1회 + slot당 review_input 1회 + CLI auto-mode Haiku 부수 호출
- Phase 2 최적화 후 목표: ~$0.30 (page_text 압축, auto-mode 끄기, prompt 슬림화)
- Phase 3 (AI 일부 카드 추가): ~$0.40
- Phase 4 (AI 다수 카드): ~$0.60

### 13.3 월 비용 (블로그 + 웹 합쳐서 주 10편 × 4주 = 40편)
- Phase 1 임시: ~$28/월 (40편 × $0.70)
- Phase 2 안정화 후: ~$12/월
- Phase 3+: ~$16~24/월

**Cap (코드 강제)**:
- 페이지당 `per_page_cap_usd = 1.00` (Phase 1 임시) → 안정화 후 0.30
- 런당 `per_run_cap_usd = 3.00` (Phase 2 cron 진입 전 batch 누적 추적 신설)
- 월 총량 cap 별도 없음 — 페이지/런 cap으로 자연 제한.

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

## 15. orchestrator.py (참조 구현 — v1.2 CLI subprocess 패턴)

> v1.1까지의 `claude_agent_sdk.Agent(...)` 패턴은 폐기됨. SDK 0.1.x가 우리 use case에 비효율 — `tools/llm/_common.py`가 bundled `claude.exe` subprocess로 직접 LLM 호출. orchestrator는 일반 async Python 함수.

### 15.1 페이지 단위 처리 (Phase 1, 구현됨)

`orchestrator.run_for_page(page_id, page_source, log_db_id) -> PageResult` — `scripts/test_phase1.py`가 호출하는 단일 페이지 진입점:

```python
# orchestrator.py (요지)
async def run_for_page(
    page_id: str,
    page_source: Literal["블로그", "웹"],
    log_db_id: str,
) -> PageResult:
    page = await asyncio.to_thread(lambda: get_client().pages.retrieve(page_id))
    content_db_id = (page.get("parent") or {}).get("database_id")
    blocks = await get_page_blocks(page_id)
    page_text = _blocks_to_text(blocks)             # compact_blocks와 단일 source

    slots, analyze_cost = await analyze_content(blocks)
    page_cost = analyze_cost
    results: list[SlotResult] = []

    with tempfile.TemporaryDirectory() as tmp:
        for slot in slots:
            r = await _process_slot(slot, page_id, page_source, page_text,
                                     log_db_id, Path(tmp), page_cost)
            results.append(r)
            page_cost += r.cost_usd
            if page_cost > PER_PAGE_CAP_USD:
                break                                # 남은 슬롯 폐기

    failed = sum(1 for r in results if not r.passed)
    final_status = "이미지 작업 중" if failed > 0 else "발행 필요"
    await update_page_status(page_id, final_status, database_id=content_db_id)
    return PageResult(...)
```

### 15.2 batch 진입점 (Phase 2 진입 시 신설)

```python
# orchestrator.py main() — Phase 2 cron 진입점
async def process_database(db_id: str, source: Literal["블로그", "웹"], log_db_id: str,
                            run_budget: RunBudget) -> list[PageResult]:
    """한 DB의 '이미지 필요' 페이지들 처리. 페이지 단위 try/except + run-level 비용 cap."""
    pages = await fetch_pages_by_status(db_id, status="이미지 필요", limit=5)
    out: list[PageResult] = []
    for page in pages:
        if run_budget.exceeded():
            logger.warning("run-level 비용 cap 도달 — 남은 페이지 폐기")
            break
        try:
            r = await run_for_page(page["id"], source, log_db_id)
            run_budget.add(r.cost_usd)
            out.append(r)
        except Exception:
            logger.exception("[%s] 페이지 %s 처리 실패 — 다음 페이지", source, page["id"])
        await asyncio.sleep(0.5)                    # Notion rate limit 보호
    return out


async def main() -> None:
    log_db_id = os.environ["NOTION_DB_LOG"]
    budget = RunBudget(cap_usd=PER_RUN_CAP_USD)     # tools/limits.py에서 가져옴
    await process_database(os.environ["NOTION_DB_BLOG"], "블로그", log_db_id, budget)
    await process_database(os.environ["NOTION_DB_WEB"],  "웹",     log_db_id, budget)


if __name__ == "__main__":
    asyncio.run(main())
```

> Phase 2 진입 전 신설할 의존:
> - `tools/limits.py` — 비용 cap / 시도 횟수 / prompt 한계 등 단일 source 상수
> - `tools/notion/_retry.py` — 429/5xx exponential backoff (notion-client 3.0은 자체 backoff 없음)
> - `RunBudget` — run 누적 비용 추적

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

| 항목 | 결정 시점 | 상태 |
|--|--|--|
| 인블로그 권장 사이즈가 default(width 1200) 단일로 충분한지 | Phase 1 검증 끝 | 진행중 |
| claude-agent-sdk 정확한 API/모델 ID | Phase 0 setup | ✅ 결정 (v1.2: SDK 우회 + bundled CLI subprocess + Sonnet 4.6) |
| skills 자동 로드 옵션 A vs B | Phase 1 진입 | ✅ 결정 (v1.2: 옵션 A — system_prompt에 직접 inject) |
| 변호사법 차단 표현 추가/조정 | Phase 3 운영 후 | 보류 |
| `tools/limits.py` 단일 source 상수 위치 | Phase 2 cron 진입 전 | 보류 (Phase 2 작업) |
| Phase 1 → Phase 2 비용 cap 복귀 ($1.00 → $0.30) | Phase 2 비용 최적화 후 | 보류 |

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

## 19. 운영 가드 (Edge case 정책 — v1.2 신설)

> 코드 구현은 Phase 1 안에서 즉시 가능한 것 / Phase 2 cron 진입 전 필수인 것으로 분류. 본 섹션이 단일 source — 새 edge case 발견 시 본 섹션을 먼저 갱신한 뒤 코드 동기화.

### 19.1 멱등성 (idempotency) — Phase 2 진입 전 필수
- **위험**: 동일 page_id가 두 번 처리되면 image block이 **중복 삽입**됨. 운영팀이 한 페이지를 `이미지 필요`로 되돌렸을 때, 또는 cron 재시도 시 즉시 발생.
- **룰**: `run_for_page` 시작 시 로그 DB에서 `관련 페이지 = mention(page_id)` row 검색. 이력 있으면:
  1. 운영자가 의도적으로 재처리 원하면 기존 image block을 본문에서 제거 후 진행 (Phase 3에서 가드 강화)
  2. Phase 1엔 단순히 skip + warning 로그 + page status 그대로 두기

### 19.2 block_id ancestor 검증 — Phase 1 즉시 적용
- **위험**: LLM이 `position_after_block_id`를 환각하거나 다른 페이지 block UUID를 던질 수 있음. `insert_image_block`이 real_parent 동적 resolve로 일부 완화하지만, **다른 페이지의 block parent**일 경우 다른 페이지에 이미지가 박힐 수 있음.
- **룰**: insert 직전 `target.parent` 또는 ancestor traversal로 `page_id == 처리 중인 page_id` 검증 필수. 실패 시 슬롯 폐기 + issues에 "block_id가 처리 페이지에 없음" 기록.

### 19.3 Notion API rate limit (3 req/s) — Phase 2 진입 전 필수
- **위험**: 페이지당 6~20 호출 (page retrieve / blocks list / upload create+send / insert / log row / status update). 슬롯 3개면 한꺼번에 쏠림.
- **룰**:
  - notion-client 호출 wrapper에 `tenacity` 기반 exponential backoff (429/5xx, 최대 5회 retry).
  - batch 진입점에서 페이지 사이 `await asyncio.sleep(0.5)`.

### 19.4 Chart.js / Pretendard 로드 실패 시 silent corruption — Phase 1 즉시 적용
- **위험**:
  - 폰트 미로드 → fallback sans-serif → 28px+ 가독성 룰 시각적 위반.
  - Chart.js CDN 로드 실패 → 빈 캔버스 캡처. 파일 크기 검증(>1KB)은 통과 가능.
- **룰**: `template_render` 캡처 직전:
  ```python
  await page.wait_for_function(
      "window.Chart != null && document.fonts.check('700 30px Pretendard')",
      timeout=5000,
  )
  ```
  실패 시 슬롯 폐기 + issues에 "폰트/Chart.js 로드 실패" 기록.

### 19.5 review_input 실패 시 로그 누락 — Phase 1 즉시 적용
- **위험**: review_input fail + revised_data None 케이스에서 `log_metadata` 호출 안 됨 → regen_policy.md "모든 시도 1행 기록" 룰 위반. 운영팀 추적 불가.
- **룰**: review_input 단계에서 슬롯 폐기 시에도 `log_metadata` 호출 (`attempts=0`, `review_passed=False`, `notion_block_id=None`, issues 포함). `시도 횟수 = 0`의 의미를 "review_input에서 폐기"로 정의.

### 19.6 슬롯 0개 페이지 추적 — Phase 1 즉시 적용
- **위험**: LLM이 빈 `image_slots: []` 반환 → status="발행 필요"로 통과 + 로그 DB row 0개. 운영팀이 "왜 이미지가 안 들어갔지?" 확인 불가.
- **룰**: 로그 DB `타입` select에 `없음` 옵션 추가. analyze 단에서 슬롯 0개면 1행 기록 (`타입=없음`, `생성 방식=template`, `비용=analyze_cost`, `시도 횟수=0`).

### 19.7 변호사법 §23 키워드 코드 상수화 — Phase 2 진입 전 권장
- **위험**: prompt_review.md의 키워드 리스트가 markdown으로만 존재 → LLM이 매번 재해석. 새 키워드 추가 누락 + 테스트 불가.
- **룰**: `tools/compliance/keywords.py` 단일 source 상수. analyze_content / review_input / image_review 모두 동일 source 참조. 1차 regex 패스(빠른 차단) + 2차 LLM 패스(맥락 위반).

### 19.8 본문 길이 한계 fallback — Phase 1 즉시 적용
- **위험**: `MAX_USER_PROMPT_CHARS = 20_000` 초과 시 RuntimeError raise → 페이지 fail. 압축/청크 fallback 없음.
- **룰**: 본문 > 18K이면 H2 단위로 청크 분할해 슬롯 분석 2-pass. 또는 본문을 H2 헤딩 + 첫 단락만 유지하는 압축 모드 fallback.

### 19.9 페이지 처리 중 unhandled exception — Phase 1 즉시 적용
- **위험**: `run_for_page`의 `get_page_blocks` / `get_client().pages.retrieve` 등 시작 단계 예외가 그대로 위로 전파. test_phase1.py도 catch 안 함.
- **룰**: page-level try/except (Phase 2 batch에선 process_database가 담당, Phase 1엔 test_phase1.py가 stack trace 대신 사용자 친화 메시지 출력).

### 19.10 file_upload 고아 (낮음, 인지만)
- upload 성공 → insert_image_block 실패 N회 → file_upload_id가 1시간 뒤 자동 archive (Notion 정책). 비용 누수 없음.
- 단 슬롯 시도 N회 = upload N회. 첫 upload만 보존하고 retry는 insert만 재시도하면 효율적 (Phase 2 최적화 항목).

---

## 20. Phase 2 진입 체크리스트 (cron 활성화 전제 — v1.2 신설)

> Phase 1 게이트 통과 후 Phase 2 시작 시 **모두 충족 필요**. 빠진 항목 있으면 cron 활성화 X.

### 20.1 코드 신설
- [ ] `tools/limits.py` — `PER_PAGE_CAP_USD`, `PER_PAGE_TARGET_USD`, `PER_RUN_CAP_USD`, `PER_SLOT_ATTEMPTS`, `MAX_USER_PROMPT_CHARS` 단일 source.
- [ ] `tools/notion/_retry.py` — 429/5xx exponential backoff wrapper (tenacity).
- [ ] `tools/compliance/keywords.py` — 변호사법 §23 키워드 상수.
- [ ] `orchestrator.main()` + `process_database()` + `RunBudget` (§15.2 참조).
- [ ] `.github/workflows/cron.yml` — `workflow_dispatch` 우선 활성화, `schedule`은 dry-run 5건 통과 후 활성화.

### 20.2 운영 가드 적용 (§19 항목)
- [ ] 19.1 멱등성 — 로그 DB 이력 검색 후 skip
- [ ] 19.2 block_id ancestor 검증
- [ ] 19.3 rate limit backoff
- [ ] 19.5 review_input 실패도 로그 1행
- [ ] 19.6 슬롯 0개 로그 1행 + `타입=없음` 옵션 추가

### 20.3 카드 추가 (Phase 2 스코프)
- [ ] `comparison_table` (§7.4) — 이현 vs 경쟁사 비교광고 §23 위반 검증 강화
- [ ] `key_points_card` (§7.5)
- [ ] chart sub_type `bar` / `donut` / `pie` (각 sub-type 추가 후 사용자 톤 게이트)

### 20.4 image_review 단계
- [ ] vision OCR로 이미지 텍스트 추출 → §23 키워드 재검사
- [ ] 사이즈 검증 룰 갱신 (v1.2 §4): width=1200 + min_height ≤ 실제 ≤ max_height
- [ ] 색상 팔레트 검증 (brand.primary 외 색 사용 시 경고)

### 20.5 비용 최적화 (Phase 1 → Phase 2)
- [ ] page_text 압축 (analyze_content / review_input의 본문 inject 슬림)
- [ ] CLI auto-mode 동시 Haiku 호출 끄기 또는 모델 강제
- [ ] 페이지당 비용 $0.30 이하 안정적 달성 검증

---

## Changelog

- **v1.2** (2026-05-08): drift 제거 + edge case 정책 신설
  - **카드 사이즈 정책 확정**: width-fixed (1200px) + content-fit + 타입별 min-height 토큰. 1200×675 fixed 폐기. 차트는 canvas 480px로 시각 비율 일관성 유지. fixed-aspect는 Phase 2+ modifier (`.card--square`, `.card--vertical`).
  - **claude-agent-sdk 사용 폐기 명시**: bundled `claude.exe`만 subprocess로 직접 호출. SDK API는 우회. 모델 ID `claude-sonnet-4-6` 확정 (§1, §3, §15).
  - **skills 자동 로드 옵션 A 확정**: `tools/llm/_common.load_skill()`로 markdown을 system_prompt에 직접 inject (§1, §17).
  - **page_source 영문 → 한글 통일**: `[blog, web]` → `[블로그, 웹]`. 로그 DB select 옵션과 1:1 매칭 (§6, §15).
  - **status 표기 띄어쓰기 통일**: 본 계획서 안 모든 표기 `이미지 필요` / `발행 필요` / `이미지 작업 중` 공백 포함으로 통일 (§10.1).
  - **카드 라인업 P0 4종 → Phase 1 = 2종**: §7.0 Phase별 활성화 표 신설. comparison_table / key_points_card는 §7.4·§7.5에 정의만 남기고 Phase 2 카드로 표시.
  - **비용 cap 두 단계**: Phase 1 임시 $1.00 → Phase 2 안정화 후 $0.30 목표. 실측 ~$0.70 반영 (§6, §13).
  - **§15 orchestrator 재작성**: SDK 패턴 폐기 → CLI subprocess 패턴. Phase 2 batch 진입점 (process_database / RunBudget) 의사 코드 추가.
  - **§19 운영 가드 신설** (10항목): 멱등성, block_id ancestor 검증, rate limit, Chart.js/폰트 로드 검증, review_input 로그 누락, 슬롯 0개 추적, §23 키워드 상수화, 본문 길이 fallback 등.
  - **§20 Phase 2 진입 체크리스트 신설**: 코드 신설 / 운영 가드 적용 / 카드 추가 / image_review / 비용 최적화 5축.
  - **§17 미결정 사항 갱신**: SDK·skills·status 결정 완료 표시.

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

**Version**: 1.2.0
**Maintainer**: 수연 / 마케팅팀
**Status**: Phase 1 진행 중 (v1.2 = drift 제거 + edge case 정책 신설). Phase 2 진입은 §20 체크리스트 충족 후.
