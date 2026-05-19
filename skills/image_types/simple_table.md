# simple_table

## When to use
본문에 단순 표 형식의 정보 (구분/대상/금액 같은 행 단위 데이터). 2~3 컬럼, 5~10 행 적합.

## Generation method
Template (HTML + Playwright) — `tools/render/template_render.py("simple_table", ...)`

## Card size (plan §4 v1.2)
default — `width: 1200px` 고정, `height: auto`.
- min_height: 480px (호흡감 확보, 너무 납작한 카드 방지)
- max_height: 1400px (행 ~12개 기준. 초과 시 슬롯 두 개로 분할 권장)
- image_review가 위 범위 자동 검증 (plan §19 + image_review.md).
인스타용 fixed-aspect(square/vertical)는 Phase 2+에서 modifier로 분리.

## Variables
- `title` : str — **필수**. 본문 인접 H2/H3 그대로. (절대 룰 #1)
- `headers` : list[str] (2~3개)
- `rows` : list[list[str]]
- `footnote` : str | None
- `highlight_first_col` : bool (기본 False, 좌측 키 컬럼 회색 강조 시 True)
- `alt_text` : str — **필수**. 노션 image caption SEO 추천문. 한국어 80자 이하. 패턴: "[주제] [N]가지 [축]". 룰은 `skills/meta/slot_selection.md` "alt_text 룰" 참조. (v1.9 plan §13)

## Style (`templates/simple_table.html` 참조)
- 헤더: neutral.100 배경 + neutral.500 텍스트, 30px medium
- 본문: white 배경 + neutral.800 텍스트, 28px regular
- 행 보더: neutral.200, 1px
- 정렬: 시드(토스피드) 기준 center-center

## Reference
- `reference_library/simple_table/tmp_kor_02.png` (단순 2열)
- `reference_library/simple_table/tmp_kor_05.png` (좌측 키 컬럼)

## Quality criteria
- [ ] **`title` 채워짐 + 본문 인접 H2/H3 일치**
- [ ] 본문 명시 텍스트만 셀에 (1자도 변형 X)
- [ ] 헤더 명확히 구분
- [ ] 모든 셀 텍스트 최소 28px
- [ ] 변호사법 §23 금지 표현 없음
