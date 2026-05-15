---
name: miniature_stock
tone: 작은 인물·소품 미니어처 사진 톤 / 한국 일상 맥락
use_when: 추상 개념을 사물·소품으로 비유 가능한 본문 (계약 / 합의 / 분쟁 등) / 사람 얼굴 직접 노출 회피하고 싶은 사연
aspect_ratio: 1536x1024
text_rule: zero
quality: medium
reference_dir: reference_library/visual_styles/miniature_stock/
---

# miniature_stock — 미니어처 스톡 이미지

> Phase 4.2 신설. 상세 spec: [docs/visual_styles_library_v1.md §2.2](../../docs/visual_styles_library_v1.md). 얼굴 환각 / 한국 외 맥락 환각을 사물 스케일로 회피.

## prompt_template

```
Tilt-shift miniature photography of {scene}.
Small figures (under 5 cm scale feel), shallow depth of field, soft natural lighting,
warm neutral light gray background or out-of-focus Korean urban setting.
Mood: {mood}.
Restrained color palette — desaturated tones with a single wine-magenta accent
on {accent_target} (a hat / a folder / a small object).
No human faces in close-up. No visible text, signs, letters, numbers, or readable labels.
Editorial calm, Toss-feed soft minimalism, slightly cinematic light.
```

## Why this style?

얼굴 환각 / 한국 외 맥락 환각을 사물 스케일로 회피. 계약·분쟁 같은 추상 개념을 비유로 풀기 좋음.
