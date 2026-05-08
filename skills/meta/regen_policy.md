# Regeneration Policy

## 슬롯 단위 재시도 룰
1. 첫 시도 실패 시 같은 입력으로 1회 재생성
2. 그래도 실패: 입력 수정 후 1회 재시도 (prompt_review가 자동 수정 시도한 결과로)
3. 그래도 실패: 슬롯을 `failed`로 마킹, 다음 슬롯 진행
4. 슬롯당 최대 시도 = 3 (첫 시도 + 재시도 2회) — `tools/limits.py:PER_SLOT_ATTEMPTS` 단일 source (Phase 2 진입 전 신설)

## 페이지 status 룰 (운영 컨벤션)
- 모든 슬롯 성공 (또는 슬롯 0개) → `발행 필요`
- 1개 이상 슬롯 `failed` → `이미지 작업 중`
- `이미지 작업 중` 페이지는 cron이 다시 처리하지 않음 (사람 개입 대기)

## 멱등성 룰 (plan §19.1 — Phase 2 진입 전 필수)
- 동일 page_id가 두 번 처리되면 image block 중복 삽입 위험.
- `run_for_page` 시작 시 로그 DB에서 `관련 페이지 = mention(page_id)` row 검색:
  - 이력 있으면 Phase 1엔 skip + warning 로그
  - Phase 3+에서 운영자 의도 재처리 가드 강화 (기존 image block 제거 후 진행)

## 비용 가드 (plan §13 v1.2)
- **페이지당 cap (Phase 1 임시)**: `$1.00` — 실측 ~$0.70 반영
- **페이지당 목표 (Phase 2 안정화 후)**: `$0.30` — page_text 압축 + auto-mode 끄기로 달성
- **런당 cap**: `$3.00` — Phase 2 batch 진입 시 누적 추적 (`RunBudget`)
- 초과 시 즉시 `stop_and_log` — 진행 중 슬롯 폐기, 페이지 `이미지 작업 중`으로 마킹.

## 로그 기록 룰 (plan §19.5 강화)
**모든 시도(성공/실패 무관)는 `tools/notion/log_metadata.py`로 로그 DB에 1행씩 기록**:
- 렌더/업로드 시도 → `시도 횟수 = N` (1+)
- review_input 단계 폐기 → `시도 횟수 = 0`, `셀프 리뷰 = False`, issues 포함
- 슬롯 0개 페이지도 1행 (`타입 = 없음`, `시도 횟수 = 0`, plan §19.6) — `타입` select에 "없음" 옵션 추가 필요
- 누락 금지: review_input 실패 / 렌더 실패 / 업로드 실패 / 비용 cap 초과 모두 1행씩.
