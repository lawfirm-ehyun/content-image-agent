# PROJECT_CONTEXT

> 빌드/운영 시 참조하는 아키텍처 레퍼런스. 이 문서는 사실(spec)만 담는다. 운영 계약은 [AGENT_GUIDE.md](AGENT_GUIDE.md), 큰 그림은 [ehyun-image-agent-plan_1.md](ehyun-image-agent-plan_1.md).

## 1. 정체

법무법인 이현 블로그/웹 콘텐츠용 이미지 자동 생성 에이전트.
- Notion 콘텐츠 DB(블로그 + 웹) → `status="이미지필요"` 페이지 처리
- 본문 분석 → 시각화 슬롯 판별 → 토스피드 톤 인포그래픽 렌더 → Notion 업로드 → status 변경
- 레포: `lawfirm-ehyun/content-image-agent`
- 레퍼런스 패턴: [OpenMontage](https://github.com/calesthio/OpenMontage) — agent-first / pipeline-driven

## 2. 기술 스택 (확정)

- Python 3.12
- 패키지 관리: `uv` 0.11+
- 의존성: `claude-agent-sdk` 0.1.74, `notion-client` 3.0, `playwright` 1.59, `pillow` 12, `pydantic` 2.13, `pyyaml` 6, `httpx` 0.28, `openai` 2.34
- 렌더링: Playwright (Chromium headless) + Chart.js + Pretendard
- 폰트: Pretendard 1.3.9 (Regular/Medium/SemiBold/Bold) — `scripts/download_fonts.sh`로 자동 다운로드

## 3. claude-agent-sdk — 공식 API (Phase 0 확인)

### 3.1 import / 진입점
```python
from claude_agent_sdk import query, ClaudeAgentOptions

async for message in query(
    prompt="...",
    options=ClaudeAgentOptions(
        allowed_tools=["Read", "Edit", "Bash"],
        # model="claude-opus-4-7",  # 또는 claude-sonnet-4-6
    ),
):
    ...
```

### 3.2 모델 ID
- Opus 4.7: `claude-opus-4-7` (SDK ≥ 0.2.111 필요. 우리는 0.1.74라서 **Sonnet 4.6 또는 Sonnet 4.5** 우선 사용 권장)
- Sonnet 4.6: `claude-sonnet-4-6`
- 비용 vs 품질 — Sonnet으로 시작, 분석/판별 품질이 부족하면 Opus 검토

> ⚠️ **결정 보류**: SDK 0.1.74로 어떤 모델을 안정적으로 호출할 수 있는지 Phase 1 첫 호출 시 검증.

### 3.3 Skills 시스템 (중요 — 위치 충돌)

SDK는 **`.claude/skills/{name}/SKILL.md`** 위치의 markdown을 자동으로 skill로 로드함.
- 계획서는 `skills/image_types/{name}.md` 위치를 가정 (OpenMontage 패턴)
- **결정 보류 (Phase 1 진입 시)**:
  - **옵션 A (계획서 유지)**: `skills/` 디렉터리 사용, SDK 자동 로드 X. `system_prompt`로 수동 로드 또는 직접 읽어서 prompt에 inject.
  - **옵션 B (SDK 활용)**: `.claude/skills/{name}/SKILL.md`로 이동, SDK 자동 로드 활용.
- 기록: 옵션 A가 OpenMontage "운영 일관성" 의도에 더 부합 (디렉터리 구조 통제권). 단 옵션 B는 코드량 적음.

### 3.4 Custom tools
- in-process Python 함수를 tool로 등록 가능
- 정확한 등록 방법은 Phase 1 orchestrator 작성 시 [공식 docs custom-tools 페이지](https://code.claude.com/docs/en/agent-sdk) 재확인

### 3.5 그 외 기능
- **Hooks**: `PreToolUse`, `PostToolUse`, `Stop`, `SessionStart`, `SessionEnd`, `UserPromptSubmit` (변호사법 §23 검사 게이트로 활용 가능)
- **Subagents**: `AgentDefinition`으로 정의, `Agent` tool로 호출
- **Sessions**: `resume` 옵션으로 컨텍스트 이어가기
- **Memory**: `CLAUDE.md` 또는 `.claude/CLAUDE.md` 자동 로드
- **MCP servers**: `mcp_servers` 옵션 (외부 시스템 연동)

## 4. 디렉터리 구조 (현재)

```
content-image-agent/
├── pipeline_defs/          # YAML 파이프라인 정의 (Phase 1)
├── skills/                 # 카드 타입 + meta skill (위치 결정 보류)
│   ├── image_types/
│   ├── meta/
│   └── style/
├── styles/                 # 디자인 토큰 yaml (Phase 1)
├── tools/
│   ├── notion/             # Notion API 도구
│   ├── render/             # Playwright + Chart.js
│   ├── image/              # WebP 변환, P3+ AI
│   └── llm/                # 본문 분석, 검토
├── templates/              # HTML 템플릿
├── reference_library/      # 시드 레퍼런스 (figma + 토스피드)
├── assets/
│   ├── fonts/              # Pretendard (download_fonts.sh)
│   └── logo/               # 이현 로고 (옵션)
├── scripts/                # 운영 스크립트
├── tests/                  # pytest
├── .github/workflows/      # cron (Phase 3)
├── pyproject.toml
├── .env.example
├── .gitignore
├── README.md
├── PROJECT_CONTEXT.md      ← 이 문서
├── AGENT_GUIDE.md
└── ehyun-image-agent-plan_1.md  # 큰 그림 (v1.1)
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

### Phase 0 (현재 진행 중)
- ✅ `.gitignore`, `pyproject.toml`, `uv.lock`
- ✅ 의존성 + chromium
- ✅ 디렉터리 골격
- ✅ `.env.example`
- ✅ `scripts/download_fonts.sh` + Pretendard 4 weights
- ✅ `PROJECT_CONTEXT.md`, `AGENT_GUIDE.md`, `README.md` (초안)
- ⏳ `scripts/check_notion.py` (토큰 받은 후)
- ⏳ Phase 0 게이트 검증

### Phase 1 (예정 — 한 사이클 자율 실행, 카드 2종)
대기 중. 게이트 통과 후 시작.

## 7. 외부 참조

- [Anthropic Claude Agent SDK docs](https://code.claude.com/docs/en/agent-sdk)
- [claude-agent-sdk-python GitHub](https://github.com/anthropics/claude-agent-sdk-python)
- [Notion API: File Upload](https://developers.notion.com/docs/working-with-files-and-media)
- [Notion API: Mention objects](https://developers.notion.com/reference/rich-text#mention)
- [Playwright Python](https://playwright.dev/python/)
- [Chart.js](https://www.chartjs.org/)
- [Pretendard 1.3.9](https://github.com/orioncactus/pretendard)
- [OpenMontage](https://github.com/calesthio/OpenMontage)
