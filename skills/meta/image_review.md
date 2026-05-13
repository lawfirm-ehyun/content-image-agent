# Image Review

이미지 생성 후 결과물을 셀프 리뷰한다.

## Phase 1 스코프
- 텍스트 렌더링 정확성은 **prompt_review가 끝낸 input**에서 보장 → Phase 1엔 image_review 단계 코드 기반 형식 검증만.
- 다음은 **렌더 산출물에서만 확인 가능**:
  1. WebP 산출물이 실제로 생성되었는가 (파일 존재, 크기 > 1KB)
  2. 카드 사이즈가 정책 범위 안인가 (v1.2 갱신 — 아래 룰 참조)
- vision OCR 기반 검사는 **Phase 2**에서 도입.

## 카드 사이즈 검증 룰 (v1.2 — width-fixed + content-fit)

plan §4 카드 사이즈 정책에 따라 **1200×675 fixed 검증 폐기**. width 고정 + 타입별 min/max 범위 검증으로 갱신:

| 카드 타입 | width | min_height | max_height |
|---|---|---|---|
| `simple_table` | 1200 | 480 | 1400 |
| `chart` (`line`) | 1200 | 700 | 800 |
| (Phase 2) `comparison_table` | 1200 | 480 | 1000 |
| (Phase 2) `key_points_card` | 1200 | 600 | 900 |

검증 식: `width == 1200 AND min_height ≤ 실제_height ≤ max_height`. 실패 시 슬롯 폐기 + issues에 "사이즈 정책 위반: {타입} {wxh}" 기록.

## Phase 1 검증 항목 (자동, 코드 기반)
- [ ] 산출 WebP 존재 + ≥ 1KB
- [ ] 카드 사이즈 정책 충족 (위 표)
- [ ] 차트 슬롯이면 `chart_render.validate_chart` 통과한 input이었나 (renderer side에서 보장)

## Phase 2 검증 (vision OCR — Phase 1엔 미구현)
- 이미지 텍스트 추출 → 변호사법 §23 키워드 재검사 (`tools/compliance/keywords.py` 단일 source 사용)
- 텍스트 정확성 (한국어 오타, 누락)
- 컬러 팔레트 일치 (brand.primary, neutral — `ehyun_visual_guide` monochromatic 룰)
- 모바일 가독성 (28px+ 추정)

## 실패 시
- regen_policy.md 따름. 슬롯 폐기 시에도 `log_metadata` 호출 (plan §19.5).
