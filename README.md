# content-image-agent

> 법무법인 이현 블로그/웹 콘텐츠용 이미지 자동 생성 에이전트.

Notion 콘텐츠 DB에서 `상태="이미지 필요"` 페이지를 가져와 본문을 분석한 뒤, 토스피드 톤 인포그래픽(차트/표/카드)을 자동 생성·배치한다. agent-first / pipeline-driven 설계 — [OpenMontage](https://github.com/calesthio/OpenMontage) 참고.

## 문서

- **빌드 큰 그림 (SOT)**: [`ehyun-image-agent-plan_1.md`](ehyun-image-agent-plan_1.md)
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
# .env에 NOTION_TOKEN, NOTION_DB_*, ANTHROPIC_API_KEY, OPENAI_API_KEY 입력
```

## 라이선스

Proprietary. 법무법인 이현 내부 사용.
