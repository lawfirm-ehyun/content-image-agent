# content-image-agent

> 법무법인 이현 블로그/웹 콘텐츠용 이미지 자동 생성 에이전트.

Notion 콘텐츠 DB에서 `status="이미지필요"` 페이지를 가져와 본문을 분석한 뒤, 토스피드 톤 인포그래픽(차트/표/카드)을 자동 생성·배치한다. [OpenMontage](https://github.com/calesthio/OpenMontage)의 agent-first / pipeline-driven 패턴 차용.

## 문서

- **빌드 큰 그림**: [`ehyun-image-agent-plan_1.md`](ehyun-image-agent-plan_1.md) (v1.1, 18 섹션)
- **운영 계약**: [`AGENT_GUIDE.md`](AGENT_GUIDE.md) — 이 레포에서 작업하는 에이전트 룰
- **아키텍처/스펙**: [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) — 기술 스택, SDK API, DB 스키마

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
| Phase 0 — Setup | 진행 중 | 레포 골격, 의존성, 폰트, Notion 연결 검증 |
| Phase 1 — 한 사이클 자율 실행 | 대기 | 카드 2종(simple_table + chart_line), 수동 trigger |
| Phase 2 — 카드 4종 + 통합 | 대기 | comparison_table, key_points_card, image_review |
| Phase 3 — Cron + AI 카드 | 대기 | stat_highlight, document_excerpt, GitHub Actions |
| Phase 4 — 학습 루프 | 대기 | 운영 데이터 분석, 프롬프트/템플릿 개선 |

## 산출물 인덱스

Phase 진행하면서 추가됩니다.

### Phase 0
- [`pyproject.toml`](pyproject.toml) — Python 3.12 + 의존성 정의
- [`.env.example`](.env.example) — 환경변수 템플릿
- [`scripts/download_fonts.sh`](scripts/download_fonts.sh) — Pretendard 다운로드
- (예정) `scripts/check_notion.py` — Notion DB 식별/검증

### Phase 1+
대기 중.

## 라이선스

Proprietary. 법무법인 이현 내부 사용.
