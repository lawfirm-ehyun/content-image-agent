# illustration (v1.6.2) **[deprecated v1.8 Phase 4.2]**

> **v1.8 Phase 4.2 (2026-05-15) 부터 deprecated.** `ai_visual` + `skills/visual_styles/point_color_line.md` 가 동일 라인 일러스트 톤 + 추가 4종 스타일 (`miniature_stock` / `korean_court_scene` / `blueprint_poster` / `cinematic_three_frame`) 을 제공. 신규 trigger 는 `ai_visual` 로 라우팅 권장. 본 스킬은 backwards compat 유지 — 즉시 삭제 X, 운영 누적 0건 1주 후 삭제 검토.
> - **신 스킬 매칭**: 본 illustration 의 라인 일러스트 톤 = `ai_visual.visual_style = point_color_line` (frontmatter `use_when` 동일).
> - **이관 경로**: analyze_content 가 본문 보고 `ai_visual` 결정 → `visual_style=point_color_line` 매칭 시 동일 결과. illustration 직접 trigger 는 LLM이 본 스킬 보고 결정한 legacy path.

페이지 도입부 H2 첫 단락 또는 콘텐츠 전환부에 **분위기·감정 전달용 라인 일러스트**.

## When to use
- 페이지 **도입부 H2 첫 단락** — 사용자 상황 환기 (예: "음주운전 적발된 직장인", "상속 분쟁 가족")
- 콘텐츠 **전환부** — 단조로운 정보 흐름 끊기, 감정 분기점
- 본문에 사용자 인용/사연/장면 묘사가 있을 때 가장 적합
- **금지**: 텍스트 다수 필요한 경우 (그건 정보형 카드), 사실 인용 필요한 경우 (그건 kakao_dialogue)

## Generation method
AI (gpt-image instant, quality=medium) — ~$0.042/장 @ 1024x1024.

## Style (v1.6.1 fix — 라인 일러스트 단일)
- 자연어 키워드: **Korean editorial line illustration**, minimalist outline drawing, single-weight black outlines on white background, wine-magenta accent on 1-2 elements only, side/back view or silhouette, no text.
- 한국 웹툰형은 Phase 4 `webtoon`로 분리.

## Variables
- `scene` (str, 필수): 장면 묘사 자연어. 본문에서 추출 또는 본문 사실 안에서 합성.
  - 예: "야간 공원에서 음주측정 받는 30대 직장인", "거실에서 형제 둘이 유산 서류 보며 다투는 모습"
- `mood` (str, 필수): 분위기 키워드. "당혹스러움" / "고민" / "안도" / "긴장" 등.
- `accent_target` (str, 옵션): wine-magenta로 강조할 1-2 요소. 예: "셔츠 칼라", "서류 표지".
- `alt_text` (str, 필수): 노션 image caption 으로 박혀 인간 검수자가 발행 시 alt 시드로 사용. **한국어 80자 이하** (v1.9 plan §13). 룰은 `skills/meta/slot_selection.md` "alt_text 룰" 섹션 참조.
- `footnote` (str, 옵션)

## Data validation (사실 정확성 절대 룰 #1 — 카테고리 차등)
- **scene / mood는 본문에서 합성 OK** (라벨링·재표현 허용) — 본문에 없는 사람/숫자/사실 X.
- **이미지 안 텍스트 0 강제** — gpt-image가 임의로 한글/영문 박을 가능성 → vision으로 텍스트 감지 시 retry 1회 + 슬롯 폐기 (§19.16).
- alt_text는 본문 사실 안에서 합성. 환각 인물·장소·시간 X.
- 인물 정면 X — 옆모습/뒷모습/실루엣 (특정인 환각 차단).

## Reference images
- `reference_library/illustration/ehyun_v1_line_*.png` — Phase 3 진입 전 사용자 시드 1-2장 (라인 일러스트 단일 톤).

## Quality criteria
- [ ] scene이 본문 도입 사연/상황과 일치
- [ ] 스타일이 line drawing — fill·그라데이션·그림자·텍스처 0
- [ ] brand 톤 accent 1-2 포인트 (3+ 시 단조로움 깨짐)
- [ ] 인물 정면 묘사 X (특정인 환각 차단)
- [ ] 이미지 안 텍스트 0 (vision 검증)
- [ ] 한국 맥락 (서양 법정/외국 거리 X)
- [ ] alt_text 한글 자연스럽고 본문 사연 반영
