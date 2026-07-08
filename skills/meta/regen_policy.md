# Regeneration Policy

## 슬롯 단위 재시도 룰
1. 첫 시도 실패 시 같은 입력으로 1회 재생성
2. 그래도 실패: 입력 수정 후 1회 재시도 (prompt_review가 자동 수정 시도한 결과로)
3. 그래도 실패: 슬롯을 `failed`로 마킹, 다음 슬롯 진행
4. 슬롯당 최대 시도 = 3 (첫 시도 + 재시도 2회) — `tools/limits.py:PER_SLOT_ATTEMPTS` 단일 source (Phase 2 진입 전 신설)
5. AI 카드 vision 검수 fail/예외는 **retry 1회 hard cap** (plan §14.4, `orchestrator.py` `vision_retry_used`) — 소진 후에도 fail이면 슬롯 폐기
6. 데이터 결함성 예외 (`ChartDataError`/`ValueError`/`JinjaUndefinedError`/`KeyError`/`BlockNotFoundError`/`AncestorMismatchError`)는 같은 입력 재시도가 무의미 → **즉시 폐기** (재시도 X, §19.18)

## 페이지 status 룰 (운영 컨벤션)
- 모든 슬롯 성공 (또는 슬롯 0개) → `발행 필요`
- 1개 이상 슬롯 `failed` → `이미지 작업 중`
- `이미지 작업 중` 페이지는 cron이 자동으로 다시 처리하지 않음. **재처리는 운영자가
  상태값을 `이미지 필요`로 되돌리면 트리거** (v1.8.4 — 전부 실패 페이지 한정, 아래 멱등성 룰).

## 멱등성 룰 (§19.1) — v1.8.4 성공-행-only 로 좁힘
- 가드의 목적: **이미 이미지가 삽입된 페이지의 중복 삽입 방지** (0장 페이지 차단이 아님).
- `get_logged_page_ids` 가 로그 DB 최근 100건에서 **셀프 리뷰=True(삽입 성공) 행이 있는**
  page_id 만 skip set 에 담음.
- **전부 실패 페이지** (이미지 0장): 성공 행 없음 → skip 제외 → 운영자가 상태값만
  `이미지 필요`로 되돌리면 **자동 재처리** (로그 수동 삭제 불필요).
- **일부 성공 페이지** (1장+ 삽입): 성공 행 있음 → 여전히 skip (중복 방지). 통째 재처리
  대신 "골라서 다시 그리기" 별도 트랙 필요 (통째 재생성은 취향 판단 이미지에 부적합 —
  2026-07-07 사용자 논의).

## 비용 가드 (plan §6)
- **상수값 SSOT는 `tools/limits.py`** — `PER_PAGE_CAP_USD` / `PER_PAGE_TARGET_USD` / `PER_RUN_CAP_USD` / `PER_SLOT_COST_CAP_USD`. 본 문서에 숫자 복사 X (drift 방지 — 2026-07-06 구식 값 $1.00/$3.00 방치 사례로 원칙 확정).
- 안정화 목표(`PER_PAGE_TARGET_USD`) 복귀 시점/조건은 plan §10 미결정 참조.
- 초과 시 즉시 `stop_and_log` — 진행 중 슬롯 폐기, 페이지 `이미지 작업 중`으로 마킹.

## 로그 기록 룰 (plan §19.5 강화)
**모든 시도(성공/실패 무관)는 `tools/notion/log_metadata.py`로 로그 DB에 1행씩 기록**:
- 렌더/업로드 시도 → `시도 횟수 = N` (1+)
- review_input 단계 폐기 → `시도 횟수 = 0`, `셀프 리뷰 = False`, issues 포함
- 슬롯 0개 페이지도 1행 (`타입 = 없음`, `시도 횟수 = 0`, plan §19.6) — `타입` select에 "없음" 옵션 추가 필요
- 누락 금지: review_input 실패 / 렌더 실패 / 업로드 실패 / 비용 cap 초과 모두 1행씩.
