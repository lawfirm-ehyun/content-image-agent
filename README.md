# content-image-agent

> 법무법인 이현 블로그/웹 콘텐츠용 이미지 자동 생성 에이전트.

Notion 콘텐츠 DB에서 `상태="이미지 필요"` 페이지를 가져와 본문을 분석한 뒤, 토스피드 톤 인포그래픽(차트/표/카드)을 자동 생성·배치한다. [OpenMontage](https://github.com/calesthio/OpenMontage)의 agent-first / pipeline-driven 패턴 차용.

## 문서

- **빌드 큰 그림 (SOT)**: [`ehyun-image-agent-plan_1.md`](ehyun-image-agent-plan_1.md) (v1.2 — 20 섹션, §19 운영 가드 + §20 Phase 2 진입 체크리스트 신설)
- **프로젝트 메모리**: [`CLAUDE.md`](CLAUDE.md) — 절대 룰 + 자주 쓰는 운영 사실 (자동 로드)
- **운영 계약**: [`AGENT_GUIDE.md`](AGENT_GUIDE.md) — 이 레포에서 작업하는 에이전트 룰
- **아키텍처/스펙**: [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) — 기술 스택, LLM 호출 패턴, DB 스키마

## 개발 환경

```bash
# 1. 의존성 설치
uv sync

# 2. Playwright Chromium 설치
uv run playwright install chromium

# 3. 폰트 다운로드 (Pretendard 4 weights)
bash scripts/download_fonts.sh

# 4. 환경변수 세팅
cp .env.example .env
# .env에 NOTION_TOKEN, NOTION_DB_*, ANTHROPIC_API_KEY 입력
```

## Phase 진행 상황

| Phase | 상태 | 산출물 |
|--|--|--|
| Phase 0 — Setup | ✅ 완료 | 레포 골격, 의존성, 폰트, Notion 연결 검증 |
| Phase 1 — 한 사이클 자율 실행 | 진행 중 | 카드 2종(`simple_table` + `chart` line), 수동 trigger, plan §19 즉시 가드 |
| Phase 2 — 카드 4종 + 멱등성 + rate limit + image_review OCR | 대기 | plan §20 체크리스트 충족 후 |
| Phase 3 — Cron + AI 카드 | 대기 | stat_highlight, document_excerpt, GitHub Actions |
| Phase 4 — 학습 루프 | 대기 | 운영 데이터 분석, 프롬프트/템플릿 개선 |

## 산출물 인덱스

### Phase 0 (완료)
- [`pyproject.toml`](pyproject.toml) — Python 3.12 + 의존성 정의
- [`.env.example`](.env.example) — 환경변수 템플릿
- [`scripts/download_fonts.sh`](scripts/download_fonts.sh) — Pretendard 다운로드
- [`scripts/check_notion.py`](scripts/check_notion.py) — Notion DB 식별/검증

### Phase 1 (진행 중)
- [`styles/ehyun_default.yaml`](styles/ehyun_default.yaml) — 디자인 토큰
- [`templates/`](templates/) — `_base.css`, `simple_table.html`, `chart_line.html`
- [`tools/render/`](tools/render/) — Playwright + Chart.js 렌더, 데이터 검증
- [`tools/notion/`](tools/notion/) — 6개 모듈
- [`tools/llm/`](tools/llm/) — bundled CLI subprocess 패턴
- [`skills/`](skills/) — 옵션 A (system_prompt 직접 inject)
- [`pipeline_defs/blog_image.yaml`](pipeline_defs/blog_image.yaml)
- [`orchestrator.py`](orchestrator.py) — `run_for_page()` (Phase 2에서 `main()` 추가 예정)
- [`scripts/test_phase1.py`](scripts/test_phase1.py) — 수동 trigger

## 라이선스

Proprietary. 법무법인 이현 내부 사용.
