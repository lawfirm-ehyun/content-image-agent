# PROJECT_CONTEXT

> 빌드/운영 시 참조하는 아키텍처 레퍼런스. 이 문서는 사실(spec)만 담는다. 운영 계약은 [AGENT_GUIDE.md](AGENT_GUIDE.md), 큰 그림은 [ehyun-image-agent-plan_1.md](ehyun-image-agent-plan_1.md).

## 1. 정체

법무법인 이현 블로그/웹 콘텐츠용 이미지 자동 생성 에이전트.
- Notion 콘텐츠 DB(블로그 + 웹) → `상태 = "이미지 필요"` 페이지 처리
- 본문 분석 → 시각화 슬롯 판별 → 토스피드 톤 인포그래픽 렌더 → Notion 업로드 → status 변경
- 레포: `lawfirm-ehyun/content-image-agent`
- 레퍼런스 패턴: [OpenMontage](https://github.com/calesthio/OpenMontage) — agent-first / pipeline-driven

## 2. 기술 스택 (확정)

- Python 3.12
- 패키지 관리: `uv` 0.11+
- 의존성: `claude-agent-sdk` 0.1.74, `notion-client` 3.0, `playwright` 1.59, `pillow` 12, `pydantic` 2.13, `pyyaml` 6, `httpx` 0.28, `openai` 2.34
- 렌더링: Playwright (Chromium headless) + Chart.js + Pretendard
- 폰트: Pretendard 1.3.9 (Regular/Medium/SemiBold/Bold) — `scripts/download_fonts.sh`로 자동 다운로드

## 3. LLM 호출 — claude-agent-sdk **우회** + bundled CLI subprocess (v1.2 확정)

### 3.1 현재 패턴 (Phase 1)

claude-agent-sdk 0.1.x는 우리 use case(단일 LLM 1회 호출 + in-process tools)에 비효율 — default Claude Code agent system prompt 추가 inject + max_turns 무시 등으로 토큰 비용 3배 초과. 같은 prompt를 CLI 직접(`claude.exe -p ... --system-prompt ...`)으로 부르면 정상 응답.

→ **SDK API는 우회**. 단 bundled `claude.exe`는 그대로 사용 (의존성/인증 path는 SDK가 제공).

```python
# tools/llm/_common.py 요지
CLAUDE_EXE = ROOT / ".venv" / "Lib" / "site-packages" / "claude_agent_sdk" / "_bundled" / "claude.exe"

cmd = [str(CLAUDE_EXE), "-p",
       "--model", "claude-sonnet-4-6",
       "--output-format", "json",
       "--max-budget-usd", f"{cap}",
       "--system-prompt", system_prompt_with_skills_inlined,
       user_prompt]
```

### 3.2 모델 ID (확정 v1.2)

- **default**: `claude-sonnet-4-6` — SDK 0.1.74로 안정 호출 검증됨 (`tools/llm/_common.py:25`).
- Opus 4.7 (`claude-opus-4-7`)은 SDK ≥ 0.2.111 필요 — Phase 4 학습 루프 진입 시 분석 품질 부족하면 SDK 업그레이드 + Opus 검토.

### 3.3 Skills 로드 — 옵션 A 확정 (v1.2)

SDK 자동 로드(`.claude/skills/{name}/SKILL.md`)는 **사용 안 함**. `tools/llm/_common.load_skill()`로 `skills/image_types/{name}.md` 본문을 직접 읽어 system_prompt에 inject.

근거: OpenMontage "운영 일관성" 의도 + 디렉터리 구조 통제권 + skill 로드 시점/방식 명시적 제어.

### 3.4 Phase 2/3 SDK 재도입 검토 시점

다음 기능이 필요해지면 SDK 부분 재도입 검토:
- **Hooks**: `PreToolUse`, `PostToolUse`, `UserPromptSubmit` (변호사법 §23 검사 게이트로 활용 가능)
- **Subagents**: 카드 타입별 specialized agent
- **MCP servers**: 외부 시스템 연동
현재(Phase 1)는 모두 미사용.

### 3.5 비용 상수 (`tools/limits.py` 신설 예정)

Phase 2 진입 전 단일 source 신설:
- `PER_PAGE_CAP_USD = 1.00` (Phase 1 임시 — 실측 ~$0.70)
- `PER_PAGE_TARGET_USD = 0.30` (Phase 2 안정화 목표)
- `PER_RUN_CAP_USD = 3.00` (batch 누적)
- `PER_SLOT_ATTEMPTS = 3`
- `MAX_USER_PROMPT_CHARS = 20_000`

## 4. 디렉터리 구조 (현재)

```
content-image-agent/
├── pipeline_defs/          # YAML 파이프라인 정의 (Phase 1)
├── skills/                 # 옵션 A 확정 — system_prompt에 직접 inject
│   ├── image_types/        # simple_table.md, chart.md (Phase 1 활성)
│   ├── meta/               # slot_selection / prompt_review / image_review / regen_policy / notion_placement
│   └── style/              # ehyun_visual_guide
├── styles/                 # 디자인 토큰 yaml (Phase 1)
├── tools/
│   ├── notion/             # Notion API 도구 (notion-client 3.0)
│   ├── render/             # Playwright + Chart.js + chart_render 검증 게이트
│   ├── image/              # WebP 변환, P3+ AI
│   └── llm/                # _common.py (CLI subprocess), analyze_content, review
├── templates/              # HTML 템플릿 + _base.css
├── reference_library/      # 시드 레퍼런스 (figma + 토스피드)
├── assets/
│   ├── fonts/              # Pretendard (download_fonts.sh)
│   └── logo/               # 이현 로고 (옵션)
├── scripts/                # 운영 스크립트 (check_notion, test_phase1)
├── tests/                  # pytest
├── .github/workflows/      # cron (Phase 3)
├── orchestrator.py         # run_for_page() (Phase 1) / main() (Phase 2 신설 예정)
├── pyproject.toml
├── .env.example
├── .gitignore
├── README.md
├── CLAUDE.md               # 프로젝트 메모리 (자동 로드)
├── PROJECT_CONTEXT.md      ← 이 문서
├── AGENT_GUIDE.md
└── ehyun-image-agent-plan_1.md  # SOT (v1.2 — 20 섹션)

# Phase 2 진입 전 신설 예정
tools/
├── limits.py               # 비용 cap / 시도 횟수 / prompt 한계 단일 source
├── notion/_retry.py        # 429/5xx exponential backoff
└── compliance/keywords.py  # 변호사법 §23 키워드 코드 상수
```

## 5. Notion DB 구조

### 5.1 입력 DB (사용자가 받은 ID 3개)
URL fragments:
- `7feddd17f8574707ab9807d15a0e0298`
- `21443f95d72a80098c9cd4ce6ab264d2`
- `35843f95d72a80688d56dd6ba60cc3ce`

어느 게 블로그/웹/로그인지는 `scripts/check_notion.py`(P0-11)로 자동 식별.

### 5.2 콘텐츠 DB의 `상태` 속성 (한글 + 띄어쓰기)
운영 컨벤션에 align됨. 속성명 **`상태`**, 옵션은 띄어쓰기 포함:
- 입력: `이미지 필요`
- 출력 1: `발행 필요` (모든 슬롯 성공 또는 슬롯 0개)
- 출력 2: `이미지 작업 중` (1개 이상 슬롯 실패)
- "이미지 작업 중" 페이지는 cron이 다시 처리하지 않음 (사람 개입 대기)

### 5.3 `이미지 작업 로그` DB 스키마 (계획서 §10.2 — align됨)

#### 필수 (Phase 1부터)
| 속성 | 타입 |
|--|--|
| 작업 ID | title |
| 출처 | select (블로그/웹) |
| 관련 페이지 | rich_text (mention 객체로 페이지 연결) |
| 타입 | select |
| 차트 타입 | select |
| 생성 방식 | select |
| 입력(JSON) | rich_text (공백 없음 주의) |
| 비용 USD | number |
| 시도 횟수 | number |
| 셀프 리뷰 | checkbox |
| 생성 일시 | created_time |

#### 권장 (Phase 4 학습 루프 진입 전까지)
| 속성 | 타입 |
|--|--|
| 사람이 교체함 | checkbox |
| 결과 이미지 | files |

> relation 속성 없음. `관련 페이지`는 rich_text + mention.
> 컨벤션 노트: 공백/단어 일치 중요 — 코드 키와 1:1 매칭. `scripts/check_notion.py`의 `LOG_DB_REQUIRED_SCHEMA`가 단일 출처(single source of truth).

## 6. Phase별 산출물 인덱스

### Phase 0 (✅ 완료)
- ✅ `.gitignore`, `pyproject.toml`, `uv.lock`
- ✅ 의존성 + chromium
- ✅ 디렉터리 골격
- ✅ `.env.example`
- ✅ `scripts/download_fonts.sh` + Pretendard 4 weights
- ✅ `PROJECT_CONTEXT.md`, `AGENT_GUIDE.md`, `README.md`, `CLAUDE.md`
- ✅ `scripts/check_notion.py` 통과
- ✅ Phase 0 게이트 검증

### Phase 1 (현재 진행 중 — 한 사이클 자율 실행, 카드 2종)
- ✅ `styles/ehyun_default.yaml` — 디자인 토큰
- ✅ `templates/_base.css` + `simple_table.html` + `chart_line.html`
- ✅ `tools/render/{template_render, chart_render}.py`
- ✅ `tools/image/webp_converter.py` (lossless 기본)
- ✅ `tools/notion/` 6개 모듈
- ✅ `tools/llm/{_common, analyze_content, review}.py` — CLI subprocess
- ✅ `skills/{image_types, meta, style}/` — 옵션 A 직접 inject
- ✅ `pipeline_defs/blog_image.yaml`
- ✅ `orchestrator.run_for_page()` + `scripts/test_phase1.py`
- ⏳ Phase 1 즉시 가드 (plan §19): block_id ancestor / Chart.js·폰트 검증 / review_input 로그 / 슬롯 0개 추적 / 본문 길이 fallback / page-level try/except
- ⏳ image_review.md 사이즈 검증 룰 갱신 (1200×675 fixed → width=1200 + min_height)
- ⏳ Phase 1 종료 게이트 사용자 검증

### Phase 2 (대기 — plan §20 체크리스트 충족 후)
대기 중.

## 7. 외부 참조

- [Anthropic Claude Agent SDK docs](https://code.claude.com/docs/en/agent-sdk)
- [claude-agent-sdk-python GitHub](https://github.com/anthropics/claude-agent-sdk-python)
- [Notion API: File Upload](https://developers.notion.com/docs/working-with-files-and-media)
- [Notion API: Mention objects](https://developers.notion.com/reference/rich-text#mention)
- [Playwright Python](https://playwright.dev/python/)
- [Chart.js](https://www.chartjs.org/)
- [Pretendard 1.3.9](https://github.com/orioncactus/pretendard)
- [OpenMontage](https://github.com/calesthio/OpenMontage)
