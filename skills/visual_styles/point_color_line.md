---
name: point_color_line
tone: 단색 검정 라인 + wine-magenta accent 1포인트
use_when: 본문에 구체적 인물 묘사 (이름·직업·상황 명시, 예 "30대 직장인 A씨가 야간 도로에서 음주측정") 가 있는 도입부 사연 / 콘텐츠 전환부 호흡 분기. 인물 묘사 약한 추상 법률 개념은 miniature_stock 조건부 default 로.
aspect_ratio: 1536x1024
text_rule: zero
quality: medium
reference_dir: reference_library/visual_styles/point_color_line/
accent_target_default: 인물 의류 또는 손에 든 서류
---

# point_color_line — 포인트 컬러 라인 일러스트

> Phase 4.2 신설. 상세 spec: [docs/visual_styles_library_v1.md §2.1](../../docs/visual_styles_library_v1.md). 기존 `illustration` (v1.6.2 단일 라인 스타일) 의 톤을 보존한 default 스타일.

## prompt_template

```
Korean editorial line illustration, minimalist outline drawing.
Scene: {scene}.
Mood: {mood}.
Single weight black outlines on soft light gray background (warm neutral, not pure white),
with restrained wine-magenta color accent on {accent_target}.
Side view, back view, or silhouette — avoid direct front portraits with detailed faces.
No text, signs, letters, numbers, or labels anywhere inside the image.
Modern Korean urban context (Korean offices, streets, courtrooms, or homes as fits the scene).
Style reference: editorial minimalism, single-line drawing, restrained color use,
calm Toss-feed editorial tone.
```

## Why this style?

v1.6.4 운영에서 토스피드 톤과 가장 잘 어울리던 라인. 정보형 카드 사이 호흡 분기 + 도입부 사연 시각화에 default. 기존 `illustration` 스킬과 동일 톤 — Phase 4.2 진입 후 `illustration` 은 `[deprecated]` 표시.
