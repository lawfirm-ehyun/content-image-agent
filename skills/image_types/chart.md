# chart

## When to use
본문에 시계열 추이, 분포, 비율, 카테고리 비교 데이터.

## Generation method
Template (HTML + Chart.js + Playwright) — `tools/render/chart_render.py`.
Week 3a (plan §12.2 v1.7.3) 통합: 4 sub-type → `templates/master_chart.html` 단일 + `ChartSpec` 단일 스키마 + `render_chart` 단일 함수.

## Sub-types (`ChartSpec.sub_type`)
- `line` : 시계열 추이.
- `bar`  : 카테고리 비교 (연도별 건수, 지역별 유형 등).
- `donut`: 분포/구성비 (전체 합에서 각 slice 비율, 중앙 hole 55%).
- `pie`  : 분포/구성비 (donut과 동일, 중앙 채움 = cutout 0).

## Card size (plan §4 v1.2)
default — `width: 1200px` 고정, `height: auto`.
- Chart.js canvas 자체는 약 480px (시각 비율 일관성 — best practice)
- 카드 전체는 제목+canvas+출처 합산해 700~800px 범위에 수렴
- min_height: 700px / max_height: 800px (image_review가 자동 검증)
- 다른 카드(simple_table 등)와 달리 차트는 사실상 거의 fixed — 차트 비율 일관성 유지가 표보다 더 중요.

## Variables (line/bar — `ChartSpec(sub_type='line' | 'bar', ...)`)
- `title` : str — **필수**. 본문 인접 H2/H3 그대로. (절대 룰 #1)
- `labels` : list[str]
- `values` : list[float]
- `point_labels` : list[str] (각 포인트/막대 위 표시. 단위 포함 권장)
- `sub_labels` : list[str] | None (x축 2행 라벨 — 긴 라벨 줄바꿈)
- `y_unit` : str | None ("(%)", "(억 원)" 등)
- `source` : str | None (통계는 표기 권장)
- `y_min` / `y_max` : float | None
- `orientation` : `'vertical'`(default) | `'horizontal'` — Week 3b parametric.
- `emphasis_index` : int | None (default None) — 강조할 포인트/막대 인덱스. None이면 강조 X.
- `alt_text` : str — **필수**. 노션 image caption SEO 추천문. 한국어 80자 이하. line/bar 패턴: "[주제] [기간] 추이 — [시작값]에서 [끝값]로 [방향]". donut/pie 패턴: "[주제] [N]개 [축] 구성비 — [핵심 slice] 최대". 룰은 `skills/meta/slot_selection.md` "alt_text 룰" 참조. (v1.9 plan §13)

### line vs bar 선택
- **line**: 본문에 연속된 시계열 (연도/월/분기 → 값). x축이 순서 의미 있음.
- **bar**: 카테고리 비교 (지역/유형/연도 카테고리 → 값). 순서 의미 없거나 약함.
- 같은 데이터를 둘 다 표현 가능하면 — 연속 추이는 line, 이산 비교는 bar.

## Variables (donut/pie — `ChartSpec(sub_type='donut' | 'pie', ...)`)
- `title` : str — **필수**.
- `labels` : list[str] — slice 이름 (2-6개).
- `values` : list[float] — slice 값 (Chart.js가 자동 % 환산). 음수/합 0 X.
- `point_labels` : list[str] | None — slice 표시 텍스트 (예: "1,240건"). None이면 raw value 표시.
- `source` : str | None.
- `emphasis_index` : int | None (default None) — 강조할 slice 인덱스. None이면 강조 X.
- (donut/pie 분기에선 `sub_labels` / `y_unit` / `y_min` / `y_max` / `orientation` 사용 X — None/default 둘 것. orientation은 원형 DOM이라 무의미.)

### donut vs pie 선택
- **donut**: 중앙 hole 있음 — 더 현대적 톤. 기본 권장.
- **pie**: 중앙 채움 — 전통적, 슬라이스 비교 더 명확.
- 본문이 "구성비" 강조 → donut. "비율 자체"가 중요 → pie. 보통 donut으로 가도 OK.

### orientation 선택 (line/bar만 — Week 3b)
- `vertical`(default): 거의 모든 경우. 시계열(연도/월) line·bar 표준.
- `horizontal`: 라벨이 길거나(긴 카테고리명) 6+개 카테고리로 vertical에서 라벨 잘림 시.

### emphasis_index 선택 (4 sub_type 공통 — Week 3b)
- 본문이 특정 시점/카테고리/슬라이스를 명시 강조 (예: "최근 1년", "가장 큰 비중")할 때 그 인덱스.
- 본문에 강조 신호 없으면 **None 유지** (모든 포인트 동등). 임의 강조 X (절대 룰 #1).

### 분포 vs 비교 선택 (donut/pie vs bar)
- **donut/pie**: 전체 합 = 100% (구성비 시각화). 카테고리 5-6개 이하.
- **bar**: 카테고리 간 절대값 비교 (서로 합산 의미 없음).
- 같은 데이터를 둘 다 표현 가능 — "이게 전체의 %냐"가 핵심이면 donut/pie, "어디가 큰가"가 핵심이면 bar.

## Style (donut/pie — `templates/master_chart.html` donut/pie 분기)
- 좌측 chart canvas 480x480 + 우측 범례 list 좌우 분할.
- 컬러: `chart-mono-1~5` (brand wine-magenta monochromatic) + `chart-mono-other` (기타 카테고리는 neutral).
- 범례: 28px swatch + 40px label + 40px value (neutral.500).
- '기타'/'그 외'/'etc' label은 자동으로 neutral 톤 (brand 톤 강조 X).

## Style (line/bar — `templates/master_chart.html` line/bar 분기)
- 카드 배경 neutral.100, 라인 brand.primary 4px, 포인트 8px
- 포인트 라벨 28px bold neutral.900
- x/y 축 라벨 24px neutral.500
- 출처 20px neutral.400 bottom-left

## Reference
- `reference_library/chart/infographic.jpg`
- `reference_library/chart/tmp_kor_03.png`

## Data validation (CRITICAL — `chart_render.py`가 강제)
- 본문 명시 숫자 1:1 매칭 (slot_selection 단)
- 최소 2 포인트 (1개면 stat_highlight 폴백 — Phase 1 미완)
- labels/values/point_labels 길이 일치
- labels 12자 초과 + sub_labels 미지정 → 자동 줄바꿈

## Quality criteria
- [ ] 데이터 라벨 본문과 1:1
- [ ] 출처 표기됨
- [ ] brand.primary는 메인 라인에만
- [ ] 변호사법 §23 금지 표현 없음
