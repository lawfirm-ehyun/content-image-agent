# ai_visual (v1.8 Phase 4.2)

본문 톤·구조에 맞는 **5종 visual_style 라이브러리 중 best fit 스타일** 로 감성형 카드 생성. analyze_content가 LLM 매칭, ai_render가 `skills/visual_styles/<name>.md` frontmatter + prompt_template 로드 → gpt-image 호출.

## When to use
- 본문에 **사연/장면/구조/한국 법원 풍경/짧은 인물 시퀀스** 묘사가 있어 5종 visual_style `use_when` 패턴 중 1개와 명확히 매칭
- 도입부 H2 첫 단락 / 콘텐츠 전환부 호흡 분기 / 정보형 사이 mix
- **금지**: 본문 톤이 5종 `use_when` 패턴 어디에도 부합 안 됨 → ai_visual trigger X (환각 방지, 슬롯 폐기). 임의 default visual_style 합성 절대 X.

## Generation method
AI (gpt-image instant or thinking, quality=medium 또는 high — frontmatter `quality` 종속).
- `point_color_line` / `miniature_stock` / `korean_court_scene` / `blueprint_poster`: instant medium @ 1536x1024 ≈ $0.063
- `cinematic_three_frame`: thinking high @ 1024x1536 ≈ $0.25

## Style (5종, 자세한 spec: docs/visual_styles_library_v1.md)
runtime SOT는 `skills/visual_styles/<name>.md` frontmatter + body `prompt_template`. analyze_content가 `name`/`tone`/`use_when` 만 보고 매칭, ai_render가 prompt_template 치환 후 gpt-image 호출.

| name | aspect_ratio | quality | use_when (요약) |
|---|---|---|---|
| point_color_line | 1536x1024 | medium | 도입부 사연 / 전환부 (default) |
| miniature_stock | 1536x1024 | medium | 추상 비유 / 얼굴 회피 |
| korean_court_scene | 1536x1024 | medium | 소송·재판 풍경 |
| blueprint_poster | 1536x1024 | medium | 추상 구조·시스템 환기 |
| cinematic_three_frame | 1024x1536 | high | 짧은 인물 시퀀스 |

## Variables
- `visual_style` (str, 필수): 위 5 name 중 1. 빈 값 / 미정의 → 슬롯 폐기.
- `scene` (str, 필수): 장면 묘사 자연어. 본문 사실 안에서 합성 (라벨링·재표현 OK, 환각 X).
- `mood` (str, 필수): 분위기 키워드. "당혹스러움" / "긴장" / "고민" / "체계적" 등.
- `accent_target` (str, 옵션): wine-magenta 강조 요소 자연어. 비우면 frontmatter `accent_target_default` 또는 fallback.
- `alt_text` (str, 필수): 노션 image caption 으로 박혀 인간 검수자가 발행 시 alt 시드로 사용. **한국어 80자 이하** (v1.9 plan §13). SEO 룰 6개 + 카드별 패턴은 `skills/meta/slot_selection.md` "alt_text 룰" 섹션 참조. ai_visual 패턴: scene 본문 합성 + target keyword 1회.
- `footnote` (str, 옵션)

## Data validation (사실 정확성 절대 룰 #1 — 카테고리 차등)
- **visual_style 매칭**: 5종 name 중 정확히 1개. 본문 톤 + use_when 명확 매칭만. 매칭 불확실 시 폐기.
- **scene / mood / accent_target**: 본문 사실 안에서 합성 OK (라벨링·재표현). 본문에 없는 사람/숫자/사실 X. 인물 정면 X (특정인 환각 차단 — prompt_template 가 side/back/silhouette 강제).
- **이미지 안 텍스트 0 강제** (`text_rule=zero`, 전 5종): gpt-image 가 임의 한글/영문 박을 가능성 → Phase 4.3 vision (`tools/render/vision_review.py`, §19.16) 검출 시 retry 1회 + 폐기. Phase 4.2 까지는 paper-only 가드, prompt_template 의 "No text/signs/letters" 강제로 1차 차단.
- **변호사법 §23**: 1차 regex pass (`tools/compliance/keywords.py`) 가 scene/mood/accent_target/alt_text/footnote 모두 검사. 위반 발견 시 즉시 폐기.
- alt_text는 본문 사실 안에서 합성. 환각 인물·장소·시간 X.

## Reference images
- `reference_library/visual_styles/<name>/` — 사용자 시드 (1-3장, 옵션). `.gitignore` 적용 (저작권/로컬 한정). 없어도 작동, 있으면 LLM 매칭 품질 ↑.

## Quality criteria
- [ ] visual_style 이 5종 정확히 1개 (오타·미정의 X)
- [ ] scene 이 본문 사연/구조/풍경과 일치 (환각 X)
- [ ] mood 가 본문 톤 반영 (감정·분위기 한 단어 또는 짧은 구)
- [ ] aspect_ratio 가 frontmatter 와 일치 (runtime ai_render 자동 결정)
- [ ] 인물 정면 클로즈업 X
- [ ] 이미지 안 텍스트 0 (vision 검증은 Phase 4.3)
- [ ] alt_text 본문 사연 반영, 자연스러운 한국어
- [ ] 변호사법 §23 표현 0
