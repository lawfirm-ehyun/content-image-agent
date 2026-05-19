# key_points_card

## When to use
본문에 "핵심 N가지", "준비 서류", "주의사항 5가지" 등 **동등한 핵심 정리 패턴**.

**적합한 패턴**:
- 핵심 3가지 ("계약 시 반드시 확인할 3가지")
- 체크리스트 ("이혼 소장 작성 시 필수 기재 항목")
- 주의사항 N가지 ("부동산 계약 주의사항 5가지")
- 권리 / 의무 정리 ("임차인의 3대 권리")

**부적합한 패턴**:
- 순차 단계 (시간 흐름) → `timeline`
- 동등 비교 (A vs B) → `comparison_table`
- 시계열 추이 → `chart` line/bar
- 표 형식 데이터 (2-3 컬럼) → `simple_table`

## Generation method
Template (HTML + Playwright) — `tools/render/template_render.py("key_points_card", ...)`

## Card size
default — width 1200px, height auto. 항목 3-5개 기준 ~600-900px.
- 항목 6개+면 슬롯 분할 권장 (한 카드에 너무 많은 핵심 = 인지 분산).
- 항목 2개 이하면 simple_table 또는 stat_highlight가 더 적합.

## Variables (v1.4 — 단일 variant)
- `title` : str | None — 본문 인접 H2/H3 그대로 (있으면).
- `items` : list[item] — 최소 3개, 최대 5개 권장.
  - `label` : str — **필수**. 핵심 포인트 제목 (한 줄, 짧게).
  - `description` : str | None — 한 줄 설명 (옵션).
- `footnote` : str | None — 출처/주석.
- `alt_text` : str — **필수**. 노션 image caption SEO 추천문. 한국어 80자 이하. 패턴: "[주제] 핵심 [N]가지". 룰은 `skills/meta/slot_selection.md` "alt_text 룰" 참조. (v1.9 plan §13)

> plan §7.5 v1.0의 `variant: numbered | checked | bulleted` 3종은 v1.4에서 단일 패턴(numbered)으로 통일.
> 이유: (1) checked variant는 accent.success 색이 brand 외 컬러 추가 → 토스피드 단색 강조 톤 위반.
> (2) bulleted는 numbered와 시각 차별성 약함. 단일 numbered가 가장 명확.

## Style (`templates/key_points_card.html`)
- marker: 64px 원, brand.primary_soft 배경 + brand.primary 32px bold 숫자 (timeline marker와 시각 일관).
- label: 42px bold neutral.900.
- description: 40px regular neutral.700.
- items 사이 gap sp-xl(40px) — timeline(sp-2xl)보다 좁게 (item 독립성, 카드 컴팩트).
- 단계 사이 line 없음 (timeline과 차별 — item들은 동등/독립).
- footnote: 32px neutral.500.

## Quality criteria
- [ ] `title` 채워짐 + 본문 인접 H2/H3 일치
- [ ] items 3-5개 (2개 이하 / 6개 이상 X)
- [ ] 본문에 명시된 항목만 사용 (절대 룰 #1 — 환각 항목 X)
- [ ] label은 짧고 직관적 (긴 문장 X — description으로)
- [ ] 모든 텍스트 최소 40px (모바일 가독성)
- [ ] 변호사법 §23 금지 표현 없음 (자동 1차 regex pass)
