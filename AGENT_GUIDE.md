# AGENT_GUIDE

> 이 레포에서 작업하는 Claude Code(또는 다른 AI 에이전트)가 따르는 운영 계약. 사실/스펙은 [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md), 큰 그림은 [ehyun-image-agent-plan_1.md](ehyun-image-agent-plan_1.md).

## 1. 절대 룰 (위반 시 작업 중단)

1. **데이터 정확성 절대 우선** — 본문에 명시된 숫자/텍스트 외 절대 사용 금지. 차트 라벨 1자도 추측 X.
2. **변호사법 §23 컴플라이언스** — 절대성/마케팅 과장/시간 압박/비교 광고 표현 검출 시 입력 정정 또는 슬롯 폐기. 상세는 [ehyun-image-agent-plan_1.md §5](ehyun-image-agent-plan_1.md).
3. **모바일 가독성 28px+** — 카드 본문 텍스트 최소 28px (1200px wide 기준). 출처/메타만 20px까지.
4. **Phase 점프 금지** — 게이트 통과 못한 단계의 다음 Phase 작업 X.
5. **MVP 사이즈 지키기** — Phase 1은 카드 2종(simple_table + chart_line)만. 다른 카드 만들지 마라.

## 2. Phase별 스코프 (현재 위치 표시)

### Phase 0 — Setup (현재 위치)
레포 골격 + 의존성 + 폰트 + Notion 연결 검증.

**완료 게이트:**
- `uv sync` + `playwright install chromium` + 폰트 4개 ✅
- `scripts/check_notion.py` 통과 (3개 DB read/write OK, status 옵션 OK, 로그 DB 스키마 OK)
- 사용자 "Phase 1 진입 OK" 승인

### Phase 1 — 한 사이클 자율 실행 (다음)
카드 2종(`simple_table` + `chart_line`)으로 한 사이클 자동 실행:
```
노션 fetch → LLM 본문 분석 → 슬롯 판별 → 데이터 추출
         → 변호사법 §23 최소 검사 → 렌더 → 노션 업로드 → status 변경 → 로그
```
- 수동 trigger (`scripts/run_one_page.py page_id`)
- pipeline_defs/, skills/, orchestrator.py 도입

**완료 게이트:**
- 한 사이클 자동으로 돌아감 (사람 개입 0)
- 토스피드 톤 OK
- 본문 데이터 1:1 일치
- 28px+ 가독성 OK
- brand.primary 강조 포인트로만
- 변호사법 §23 검사 작동

### Phase 2+ (추후)
- Phase 2: 카드 4종 + image_review vision OCR + 두 콘텐츠 DB 통합
- Phase 3: cron 자동화 + AI 카드(stat_highlight, document_excerpt)
- Phase 4: 학습 루프 + P2 카드 검토

## 3. 의사결정 가이드

### 3.1 작업하기 전 항상
- [ ] 큰 그림 의문이면 [ehyun-image-agent-plan_1.md](ehyun-image-agent-plan_1.md) 먼저 확인
- [ ] 사실/스펙 의문이면 [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) 확인
- [ ] 메모리 (`~/.claude/projects/.../memory/`) 관련 항목 확인
- [ ] 현재 Phase 스코프 밖이면 작업 X, 사용자에게 확인 요청

### 3.2 무엇을 빌드할 때
- **Template-first**. AI(gpt-image-2)는 P3 이후. 그 전엔 HTML+Playwright 템플릿만.
- **데이터 정확성 게이트** 빠뜨리지 말 것 (prepare_data → prompt_review → render).
- **변호사법 §23 검사** prompt_review와 image_review 양쪽에 (Phase 1엔 prompt_review만, image_review vision OCR은 Phase 2).
- **카드 새로 추가하지 마** — Phase 스코프에 명시된 카드만.

### 3.3 사용자에게 검증 요청해야 할 시점
- Phase 게이트 (각 Phase 종료)
- 디자인 토큰 변경 (색/타이포)
- 변호사법 차단 표현 추가/조정
- claude-agent-sdk 호출 패턴 변경 (모델 ID, 옵션 구조)
- Notion DB 스키마 변경

## 4. 코드 컨벤션

- Python 3.12, type hints 필수
- async 우선 (Notion API, Playwright, Anthropic SDK 모두 async)
- 함수 도큐멘트 1줄 (인풋/리턴만)
- 에러 핸들링: 페이지 단위로 try/except. 한 페이지 실패해도 다음 페이지 진행.
- 비용 가드: 페이지당 $0.30, 런당 $3.00 cap. 초과 시 stop_and_log.

## 5. 외부 의존 / 사용자 액션 필요

- Notion integration token + 3개 DB connect (사용자 .env)
- Anthropic API key (사용자 .env)
- OpenAI API key (Phase 3)
- figma 회사 자산 export (Phase 1 시드)
- 토스피드 차트 캡처 (Phase 1 시드)
- 변호사법 차단 표현 검토 승인 (변경 시)

## 6. 무엇을 만들지 말 것 (의도된 부재)

- 별도 백엔드/큐 (Notion이 단일 데이터 소스)
- relation 속성 (page mention via rich_text)
- `lawyer_profile` 카드 (운영 결정으로 제거)
- 캐릭터 일러스트 / 다채로운 컬러 (토스피드 톤 X)
- README.md, docs 자동 생성 (사용자 명시 요청 시만)
