# comparison_table

## When to use
옵션 A vs B (또는 N) 항목별 비교. 협의/재판 이혼, 일반/간이 절차, 가/나 유형 등.

**§23 경계**: 다른 법무법인과의 비교 광고 X. 비교 대상은 **법적 절차/유형/조건** 등 추상 개념이어야 함.
"이현 vs 경쟁사" 식 표현은 절대 X — `tools/compliance/keywords.py`의 비교 광고 카테고리(`타 로펌`, `다른 법무법인`, `경쟁사`)가 1차 regex pass로 차단.

## Generation method
Template (HTML + Playwright) — `tools/render/template_render.py("comparison_table", ...)`

## Card size
default — width 1200px 고정, height auto. 행 4-6개 기준 ~700-900px.
- min_height: 480px / max_height: 1200px
- 행 7개+면 슬롯 분할 권장 (한 화면에 비교 항목 너무 많으면 인지 부담)

## Variables (v1.4 — highlight 제거)
- `title` : str | None — 본문 인접 H2/H3 그대로 (있으면). 표 위 h2.
- `column_headers` : list[str] — **첫 항목은 label 컬럼명** (보통 "항목"/"구분"), 그 뒤 비교 대상 N개. 길이 2-4 권장 (label + 비교 1-3).
- `rows` : list[{label: str, values: list[str]}] — `values` 길이 = `len(column_headers) - 1`.
- `footnote` : str | None — 출처 또는 보충 설명.
- `alt_text` : str — **필수**. 노션 image caption SEO 추천문. 한국어 80자 이하. 패턴: "[비교 주제 A·B] [N]가지 [축] 비교". 룰은 `skills/meta/slot_selection.md` "alt_text 룰" 참조. (v1.9 plan §13)

> **highlight_column_index 제거 (v1.4)**: 한 컬럼을 시각적으로 띄우면 "이게 더 좋다"는 광고성 신호로 읽혀 §23 위반 경계. 모든 비교 컬럼은 동등 표시. 구조적 명료성(외곽 보더 + 세로 보더 + 헤더 톤 차별화)로 가독성 확보.

## Style (`templates/comparison_table.html` v1.4)
- 카드 배경 white. 표 외곽 1px neutral.300 보더.
- 헤더: neutral.200 배경 + neutral.800 bold (본문과 명확 구분).
- 비교 컬럼 사이 세로 1px 보더 — 파티션 명확.
- label 컬럼 (1열): neutral.50 옅은 배경, 좌측정렬, 36px (7자 한글 라벨 한 줄 수용).
- 본문 셀: 모든 비교 컬럼 동등 (neutral.800 regular 40px).
- footnote 32px neutral.500.

## Quality criteria
- [ ] `title` 채워짐 + 본문 인접 H2/H3 일치
- [ ] **column_headers에 다른 법무법인/로펌 명시 X** — `이현 vs OO법무법인` 식 X. review.py의 check_keywords 1차 pass가 자동 차단.
- [ ] 본문 명시 정보만 사용 (절대 룰 #1)
- [ ] 비교 컬럼 시각 동등 (광고성 강조 없음)
- [ ] 비교 컬럼 본문 셀 40px / label 셀 36px (모바일 가독성)
- [ ] 비교 항목 4-6행 권장 (7행 이상이면 슬롯 분할)

## 슬롯 결정 (slot_selection 참조)
본문에 다음 패턴이 줄글로 있으면 comparison_table 후보:
- "A는 X이고 B는 Y" 식 대조 (3개 이상 비교 항목)
- "협의/재판" "일반/간이" 같은 절차 비교
- "이런 경우 / 저런 경우" 조건별 결과 비교 (단 2-3 옵션만)

단순 enumeration ("3가지 핵심") 은 simple_table. 비교 구조가 명확할 때만 comparison_table.
