---
name: blueprint_poster
tone: 청사진(blueprint) 라인 + 구조도 / 절차·시스템·관계도 시각화
use_when: 절차/시스템 다이어그램이 본문에 등장하나 정보형 timeline·simple_table 로 풀기 부적합 (추상도 높음) / 도입부 "이 글에서 다루는 구조" 시각 환기
aspect_ratio: 1536x1024
text_rule: zero
quality: medium
reference_dir: reference_library/visual_styles/blueprint_poster/
---

# blueprint_poster — 블루프린트 포스터

> Phase 4.2 신설. 상세 spec: [docs/visual_styles_library_v1.md §2.4](../../docs/visual_styles_library_v1.md). 정보형 트리거 없이 추상 구조 환기.

## prompt_template

```
Korean editorial blueprint-style illustration.
Subject: {scene}.
Mood: {mood}.
Light gray background with thin dark navy or charcoal line drawings,
geometric structure, schematic feel, no realistic shading.
Restrained wine-magenta accent on {accent_target} (one key node, one connecting line,
or one highlighted box).
No text, no labels, no numbers, no measurement marks, no readable letters anywhere.
Style reference: minimalist blueprint poster, editorial infographic mood,
calm Toss-feed restraint.
```

## Why this style?

정보형 카드는 사실 시각화. 본문이 추상 구조(시스템·관계·흐름) 환기만 필요한 경우 blueprint 톤이 정보형 트리거 없이 메시지 전달.
