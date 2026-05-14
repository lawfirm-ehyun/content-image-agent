# Plan History — Archive (v1.6.4 다이어트, 2026-05-12)

> 본 파일은 plan의 archive. 현 운영에 영향 없는 항목 보존.
> 활성 plan → [`ehyun-image-agent-plan_1.md`](ehyun-image-agent-plan_1.md)

본 archive에 들어가는 것:
- Changelog v0.1 ~ v1.6.3 (현재 v1.6.4만 plan 본문에 유지)
- Phase 4 검토 카드 v1.5 정의 (stat_highlight, document_excerpt) — Phase 4 진입 시 복원 가능
- Paper-only 운영 가드 (§19.10/14/16/17 풀 spec) — cron 무인 가동 가정용, 운영자 검수 단계엔 paper
- Phase 2 (§20) / Phase 3 (§21) 진입 체크리스트 — 이미 통과된 게이트

---

## 1. Archive 카드 spec (Phase 4 진입 시 복원)

### 1.1 stat_highlight (v1.5 정식 정의, v1.6.1 폐기)

본문에 단일 숫자가 핵심 인사이트로 등장하는 경우 메가 디스플레이로 강조. chart 데이터 1개 폴백 path도 담당.

**폐기 사유 (v1.6.1)**:
- 단일 숫자 메가 디스플레이가 시각적으로 강압적
- Phase 3는 감성형 카드 도입에 집중 (정보형 신설 X)
- chart 1개 폴백은 simple_table 2행 또는 슬롯 결정 X로 운영

```markdown
# stat_highlight

## When to use
- 본문에 **단일 숫자** 인사이트 ("10명 중 7명", "638억 원", "최근 5년 3.2배 증가")
- chart 후보 데이터 포인트 1개뿐 (시계열·비교 1개) — 폴백 진입

## Generation method
Template (HTML + Playwright)

## Variables
- title: string (옵션) — 카드 상단 작은 라벨
- big_number: string — 메가 디스플레이 ("638억", "7명", "3.2배")
- unit: string (옵션) — 단위 ("원", "/10명")
- description: string — 숫자 의미 한 줄. 본문 그대로.
- source: string (옵션) — footnote
- footnote: string (옵션)

## Data validation (CRITICAL — 절대 룰 #1)
- big_number는 본문 명시 숫자 1자도 변경 X
- unit은 본문 표기 그대로
- description은 본문 사실 안에서 직관 합성 OK (라벨링)
- 변호사법 §23 검사
```

Phase 4 복원 시: `templates/stat_highlight.html` + `skills/image_types/stat_highlight.md` + render 분기 + slot_selection trigger.

### 1.2 document_excerpt (v1.5 정식 정의, v1.6 Phase 4 검토 이관)

본문에 판례/법조문 인용이 등장하는 경우 인용 카드로 시각화. AI gpt-image thinking으로 시각 구성만, 본문 텍스트는 1자도 변경 X.

**Phase 4로 이동 사유 (v1.6)**:
- illustration이 도입부 분위기 카드 역할 흡수
- 판례 인용은 본문 텍스트로 박는 빈도가 더 높음

```markdown
# document_excerpt

## When to use
- 본문에 판례 인용 ("대법원 2023다12345 판결: ...")
- 본문에 법조문 인용 ("민법 제839조의2: ...")
- 본문 자체에 따옴표/괄호로 인용된 법률 텍스트 3-10줄

## Generation method
AI (gpt-image thinking) — Image 6 톤 (warm off-white 종이, serif 본문, brand.primary vertical accent bar).

## Variables
- court: string — 법원/근거명
- case_title: string (옵션)
- excerpt: string — 인용 본문 그대로. 줄바꿈 보존.
- emphasis: list[string] (옵션) — excerpt 안 substring 정확 일치 검증
- source: string

## Data validation (CRITICAL)
- excerpt / court / case_title / source는 본문 1자도 변경 X
- emphasis는 excerpt substring 정확 일치 — match 안 되면 폐기
- 본문에 인용 표시 없는 텍스트를 판례인 양 박지 X
- image_review vision OCR로 Levenshtein ≤ 2 검증
```

### 1.3 Phase 4 검토 신설 카드

- **webtoon**: 한국 웹툰 다컷 (2-4컷) 내러티브. 텔링 강. AI gpt-image thinking. 텍스트 정확성 검증 복잡.
- **app_ui_mockup**: 앱 UI mockup. use case 좁음. 법률 앱·서비스 콘텐츠 한정.

---

## 2. Paper-only 운영 가드 풀 spec

활성 가드는 plan §5 참조. 아래는 cron 무인 가동 가정용 미래 가드. 운영자 검수 단계에선 paper-only.

### §19.10 file_upload 고아 (낮음, 인지만)
- upload 성공 → insert_image_block 실패 N회 → file_upload_id가 1시간 뒤 자동 archive (Notion 정책). 비용 누수 없음.
- 단 슬롯 시도 N회 = upload N회. 첫 upload만 보존하고 retry는 insert만 재시도하면 효율적.

### §19.11 AI 카드 OCR 사실 검증 (kakao_dialogue 부분 미구현)
- **카드 종류별 분기 (v1.6)**:
  - **kakao_dialogue / document_excerpt** (텍스트 사실 카드):
    - vision OCR로 결과 이미지 한국어 텍스트 추출
    - extracted_data.messages[i].text / excerpt / court 등 "사실 그 자체" 필드와 Levenshtein distance 계산 (`rapidfuzz`)
    - 거리 ≤ 2자: 통과. > 2자: retry 1회 → 슬롯 폐기 + 로그.
  - **illustration**: OCR 검증 면제 (텍스트 0이 정상). 대신 §19.16 텍스트 감지 검증.
- **현재 상태**: rapidfuzz 의존성 추가됨, kakao_dialogue OCR 검증 코드 미구현. kakao trigger 시 추가.

### §19.14 cron 연속 실패 누적 알림 (paper, Phase 3 cron 가동 후 권장)
- **위험**: cron 가동 중 N일 연속 1건도 처리 안 됨 → 운영자 인지 지연.
- **룰**:
  - cron 실행 후 처리 페이지 0건이면 stdout warning + log row 1행
  - 3일 연속 처리 0건이면 GitHub Actions failure exit code 1 → 기본 이메일 알림
  - 1회 실행 안에서 페이지 처리 시도 + 실패 비율 ≥ 50%이면 즉시 exit code 1
- **현재 상태**: cron schedule 미가동 (workflow_dispatch만). 운영 진입 시 추가.

### §19.16 AI 카드 텍스트 환각 차단 (Phase 4.3 진입 트리거 — plan v1.8.0)
- **위험**: gpt-image 가 AI 카드 prompt 에 "텍스트 금지" 명시해도 임의로 한글·영문 박을 수 있음 (특히 간판/포스터/책 표지/법원 표지 장면). 환각 텍스트 → 한국 맥락 위반 / §23 위반 / 사실 정확성 위반. v1.8 `ai_visual` 5종 스타일 모두 `text_rule=zero` 로 출범 → 본 가드 implementation 이 ai_visual ship 의 prerequisite.
- **룰**:
  - vision_review (Claude Sonnet 4.6 vision, 사용자 컨펌 2026-05-14) 로 이미지 안 텍스트 영역 감지
  - 텍스트 픽셀 비율 > 1% 또는 OCR token ≥ 3개 또는 한글/영문 단어 detect: 환각 의심
  - retry 1회 (gpt-image 다른 seed + prompt 에 "no text" 강조)
  - 그래도 텍스트 있으면 슬롯 폐기 + 로그 DB row 폐기 reason 기록
- **§23 키워드 이미지 텍스트 검사 동반**: vision OCR 추출 텍스트 → `tools/compliance/keywords.py:check_keywords` 호출 (4 카테고리 regex). hit 시 즉시 폐기.
- **현재 상태**: 5/12 e2e 에서 gpt-image-2 자체 텍스트 환각 0건이지만, ai_visual 5종 + cinematic high quality 도입으로 환각 확률 ↑ 예상. **Phase 4.3 진입 트리거 — paper-only → implemented 격상 (plan §14.4)**. 신규 파일 `tools/render/vision_review.py`, 비용 상수 `PER_SLOT_VISION_COST_USD` (예상 $0.05-$0.10/슬롯, Phase 4.3 Design spike 후 확정).

### §19.17 mix 정책 위반 검증 (Phase 4.2 진입 트리거 — plan v1.8.0)
- **위험**: slot_selection 이 감성형만 trigger / 같은 카드 3개+ 연속 / kakao 2개+ in 페이지 / **페이지당 슬롯 4개+ (v1.8 슬롯 3 cap 위반)** → 콘텐츠 가치 결여, 시각 단조로움, 비용 폭주.
- **룰** (slot_selection 결과 검증, v1.8 갱신):
  - **페이지당 슬롯 3 cap (v1.8 hard cap, 이전 2-4 권장 → 3 hard)**: 4개+ trigger 시 우선순위 낮은 1개 폐기 + warning 로그.
  - 슬롯 N개 중 정보형 0 + 감성형 N개: warning + slot_selection 재호출 1회
  - 같은 카드 타입 3개+ 연속: warning + 운영자 검수 권장 표시
  - **같은 `visual_style` 2개+ 연속 (v1.8 신규)**: ai_visual 슬롯 2개가 동일 visual_style 일 때 허용 여부 Phase 4.2 Do 결정
  - kakao_dialogue 2개+: 1개만 남기고 폐기
- **현재 상태**: LLM 이 슬롯 결정 시 mix 룰 markdown 으로 안내됨. 코드 가드 미구현. **Phase 4.2 진입 트리거 — `skills/meta/slot_selection.md` mix 룰 갱신 + orchestrator 슬롯 3 cap 가드 추가 (plan §14.5)**.

---

## 3. 통과된 게이트 체크리스트

### Phase 2 진입 체크리스트 (§20, v1.2 신설, v1.4 모두 통과)
- [x] tools/limits.py — 비용 상수 단일 source
- [x] tools/notion/_retry.py — 429/5xx backoff (tenacity)
- [x] tools/compliance/keywords.py — 변호사법 §23 키워드 master
- [x] orchestrator.main() + process_database() + RunBudget
- [x] cron.yml workflow_dispatch 활성화
- [x] §19.1 멱등성, §19.2 block ancestor, §19.3 rate limit, §19.5 review 폐기 로그, §19.6 슬롯 0개 추적
- [x] Phase 2 카드 5종 (simple_table, chart 4 sub_type, comparison_table, key_points_card, timeline)
- [x] image_review 단계 (Phase 1 형식 검증만 — vision OCR은 Phase 3)
- [x] 비용 최적화 — page_text 압축, auto-mode 끄기, prompt 슬림화

### Phase 3 진입 체크리스트 (§21, v1.5 신설, v1.6 P3.0 통과 / v1.6.4 P3.3/P3.4 통합 완료)
- [x] Phase 2 종료 게이트: e2e ≥ 5건, 카드 4/5 trigger (5/12 e2e), 멱등성·§19 가드 작동, 사용자 승인
- [x] 코드 신설: tools/image/gpt_image_2.py, tools/render/ai_render.py, tools/limits.py Phase 3 상수, tools/budget.py 분리, openai + rapidfuzz 의존성, 단위 테스트
- [x] 운영 가드: §19.12 OpenAI backoff (tenacity), §19.13 OpenAI 비용 cap, §19.15 OpenAI key fail-fast
- [x] 카드 추가: illustration (v1.6.1), kakao_dialogue (v1.6.1) — kakao 실제 trigger 0회
- [x] slot_selection.md v1.6.2 갱신
- [x] reference_library 시드 (kakao_dialogue reference webp 1장 — illustration 사용자 시드 미추가)
- [ ] cron schedule 활성화 — 운영자 결정 (현재 수동 trigger)
- [ ] kakao_dialogue OCR Levenshtein 검증 — kakao 실제 trigger 시 추가
- [x] 사용자 사전 작업: OpenAI API key, GitHub secret, 로그 DB 옵션 (자동 생성 검증됨)

---

## 4. Changelog Archive (v0.1 ~ v1.6.3)

> v1.6.4 이후만 plan 본문에 유지. 이전 변경 내역은 본 archive 참조.

- **v1.6.3** (2026-05-12): 5/12 e2e 후속 — analyze cap 상향 + 페이지 cap 재상향
  - 실측 trigger: P3.3+P3.4 통합 후 e2e 1건에서 analyze_content가 ANALYZE_BUDGET_USD($0.50) 초과 ($0.5197). cache_creation 47K → 54K (slot_selection v1.6.2 mix 룰), output_tokens 21K (4 카드 mix 결정 분량).
  - 상수 갱신: ANALYZE_BUDGET_USD 0.50 → 0.80, PER_PAGE_CAP_USD 1.20 → 2.50, PER_RUN_CAP_USD 5.00 → 8.00
  - Phase 4 안정화 목표: PER_PAGE_CAP_USD $1.20 복귀 (analyze prompt 슬림 + slot_selection 다이어트 후)
  - 운영 가드 §19.9 page-level try/except 작동 확인

- **v1.6.2** (2026-05-12): AI prompt 자연어 전환 — over-constraint 제거
  - 사상 추가: 최신 이미지 모델은 자연어 묘사를 잘 따라옴. 픽셀·hex·CSS 토큰 명시는 부자연스러운 결과로 이어지므로 자연어 키워드로만 fix.
  - AI prompt 작성 룰:
    - ❌ 금지: `stroke 1.5-2px`, `#a91c51`, `var(--brand-primary)`, "절대 금지" 같은 부정 명령 다수
    - ✅ 권장: 자연어 스타일 키워드, 장면·톤 묘사
    - ✅ 엄격 명시 = 텍스트 사실 필드만 (exact_korean_strings)
    - ✅ reference image input 활용
    - ✅ 품질 검수는 사후로 (image_review 단계)
  - §7.8 illustration / §7.9 kakao_dialogue prompt 재작성 (픽셀/hex 제거)
  - CLAUDE.md 절대 룰 #8 신설

- **v1.6.1** (2026-05-12): stat_highlight 폐기 + illustration 라인 단일 스타일 fix + kakao reference 기반 spec
  - stat_highlight Phase 3 폐기 — v1.5 정의는 archive 보존
  - illustration 스타일 = 라인 일러스트 단일 fix (line drawing + brand.primary accent 1-2 포인트)
  - 한국 웹툰형은 Phase 4 webtoon 카드로 분리
  - kakao_dialogue spec reference 기반 갱신 (`kakao talk.webp` 톤)
  - §8.1 slot_selection 갱신 — stat_highlight trigger 룰 제거
  - §12 Phase 3 트랙 번호 재정리

- **v1.6** (2026-05-12): 사상 재정의 — 정보형 + 감성형 mix + P3.0 게이트 통과
  - §7.0 카드 라인업 사상 재정의: 페이지당 정보형(template) 1-2 + 감성형(AI) 1-2 mix
  - §7.8 illustration 정식 정의 (AI gpt-image instant)
  - §7.9 kakao_dialogue 정식 정의 (AI gpt-image thinking, OCR Levenshtein 검증)
  - document_excerpt → Phase 4 검토로 이동
  - §8.1 slot_selection 사상 갱신: 정보형/감성형 분리, mix 권장 룰, 금지 조합
  - §12 Phase 3 트랙 재정의: P3.4 document_excerpt → illustration, P3.5 kakao_dialogue 신설
  - §13 비용 cap 단계 갱신: PER_PAGE 0.50 폐기 → 1.20, PER_RUN 3.00 → 5.00, PER_SLOT 0.20 → 0.30
  - §19 운영 가드 갱신 + 신설: §19.11 카드별 분기, §19.16 illustration 텍스트 환각 차단, §19.17 mix 정책 위반 검증
  - §21 P3.0 게이트 통과 기록 (5/12 e2e 결과)
  - 5/12 운영 데이터 통합: 1 페이지 3 슬롯 $0.7723, 노션 select 옵션 자동 생성 검증

- **v1.5** (2026-05-12): Phase 3 detailed plan — cron 무인 가동 + AI 카드 (stat_highlight + document_excerpt) 진입 정교화
  - §7.7 stat_highlight 정식 정의 (P1+ stub → 정식, 추후 v1.6.1에서 폐기)
  - §7.8 document_excerpt 정식 정의 (AI gpt-image thinking, 추후 v1.6에서 Phase 4 이관)
  - §12.Phase 3 expanded form: P3.0~P3.6 트랙
  - §13 비용 cap 단계 갱신
  - §16 cron schedule 활성화 시점 명시
  - §17 미결정 항목 갱신
  - §19 Phase 3 운영 가드 5건 신설 (§19.11~15)
  - §21 Phase 3 진입 체크리스트 신설

- **v1.4** (2026-05-11): Phase 2 인프라 (§20.1) + 운영 가드 (§19.1) + 카드 라인업 5종 완성
  - tools/limits.py — 비용/타임아웃/한계 상수 18개 단일 source
  - tools/budget.py — RunBudget mutable 상태
  - tools/notion/_retry.py — async tenacity wrapper (429/5xx)
  - tools/compliance/keywords.py — 변호사법 §23 키워드 regex master (4 카테고리)
  - tenacity>=9.0.0,<11.0.0 의존성 추가
  - 단위 테스트 38건 신설
  - orchestrator.main + process_database 구현 (cron 진입점)
  - §19.1 멱등성 가드 (get_logged_page_ids + process_database skip)
  - 카드 5종 완성: comparison_table v1.4 §23 안전 재설계, key_points_card v1.4 단일 variant, timeline 신설, chart bar/donut/pie 정식 활성

- **v1.3** (2026-05-11): 슬롯 선택 사상 전환 + 사실/라벨링 룰 분리
  - 슬롯 선택 사상: "본문에 정리된 데이터를 카드화" → "본문에 줄글로 풀려있는 구조를 발굴해 시각화"
  - 본문 table 처리 룰 신설: chart 형식 전환 또는 컬럼 재구성 OK, 단순 복제 ❌
  - 절대 룰 #1 재정의: 사실 그 자체 vs 라벨링·재표현 분리
  - 모바일 가독성 D안: 폰트·spacing 1.4x + 정보 밀도 낮춤. 본문 표시 ~12px 보장.
  - 한글 가독성 토큰: word-break keep-all + letter-spacing -0.01em + line-height 1.5
  - 정보 밀도 가이드: cell 한 줄 18자 안 권장, 카드 3-5행 권장
  - simple_table 컬럼 수 룰: 2 default / 3 특수 / 4+ 슬롯 X
  - chart 카드 재설계: yUnit canvas 외 HTML 분리, scales.x.offset, 폰트 위계 재조정
  - §19 Phase 1 즉시 적용 7항 코드 동기화

- **v1.2** (2026-05-08): drift 제거 + edge case 정책 신설
  - 카드 사이즈 정책 확정: width-fixed (1200px) + content-fit + 타입별 min-height
  - claude-agent-sdk 사용 폐기 명시: bundled claude.exe만 subprocess
  - skills 자동 로드 옵션 A 확정: system_prompt에 직접 inject
  - page_source/status 영문 → 한글 통일
  - 카드 라인업 P0 4종 → Phase 1 = 2종
  - 비용 cap 두 단계: Phase 1 임시 $1.00 → Phase 2 안정화 후 $0.30 목표
  - §15 orchestrator 재작성: CLI subprocess 패턴
  - §19 운영 가드 신설 (10항목)
  - §20 Phase 2 진입 체크리스트 신설

- **v1.1** (2026-05-04):
  - 콘텐츠 DB 권한: read + write 명시
  - WebP 후처리 도구 (webp_converter.py)
  - status 흐름 확정
  - "이미지 작업 중" cron 재시도 X
  - 0개 슬롯 케이스 처리
  - Phase 1 → 2 → 3 chart sub-type 점진 확장
  - Phase 2 trigger: workflow_dispatch만
  - log_metadata: page_id를 노션 mention 객체로 변환
  - lawyer_profile 카드 설계에서 제거
  - 작업 로그 DB 스키마 정리
  - 변호사법 §23 컴플라이언스 룰 정식 추가
  - 두 콘텐츠 DB (블로그 + 웹) 통합 처리 흐름
  - Pretendard 자동 다운로드 스크립트
  - chart 데이터 1개 폴백 → P1까지 슬롯 결정 X
  - chart 카드 sub-type 우선순위

- **v1.0**: 첫 finalize. 디자인 토큰 + 모바일 가독성 룰 + 차트 정교화.
- **v0.2**: 카드 라인업 재정리. Template-first 사상 강조.
- **v0.1**: 초안.

---

## 5. 사후 점검 사항 (운영 데이터 쌓이면 결정)

- chatgpt-image-latest 조직 verification 후 비교 시도 (ChatGPT 웹 톤 재현 가장 직접적)
- gpt-image-1.5를 라인 일러스트 콘텐츠 한정 옵션으로 두는 게 더 나은지 (콘텐츠 타입별 모델 라우팅)
- Phase 4 안정화 시: ANALYZE prompt 슬림 + slot_selection 다이어트 → PER_PAGE_CAP_USD $2.50 → $1.20 복귀 시도
- cron 주기 단축 (1일 1회 → 30분/1시간) — 안정성 데이터 기반
- 실패 알림 채널 (이메일 → Slack/Discord) — Phase 4
