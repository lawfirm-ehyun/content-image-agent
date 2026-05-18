---
name: miniature_stock
tone: 작은 미니어처 figure + 일상 사물 메타포 디오라마 / tilt-shift 매크로 photo
use_when: 법률 추상 개념(계약·분쟁·합의·절차·파산·소송·채권·증거)을 일상 사물 메타포(서류·도장·동전·계약서·열쇠·균열 등)로 시각화 가능한 본문 — 인물 얼굴 환각 회피 + 무거운 법률 톤을 디오라마로 완화. 본문이 법원 외관·법정 풍경을 명시적으로 묘사하지 않는 한 korean_court_scene 보다 우선 검토.
aspect_ratio: 1536x1024
text_rule: zero
quality: medium
reference_dir: reference_library/visual_styles/miniature_stock/
---

# miniature_stock — 미니어처 디오라마 (메타포 사물)

> Phase 4.2 신설, v1.8 Phase 4.3 (2026-05-18) 사용자 reference 기반 재정의 — tilt-shift 사진이 아닌 **메타포 사물 디오라마** 사상. 상세 spec: [docs/visual_styles_library_v1.md §2.2](../../docs/visual_styles_library_v1.md).
>
> 핵심 사상: 작은 미니어처 figure 가 **추상 법률 개념을 비유하는 일상 사물 위에서 활동**.
> 예) 비스킷 위 인부들 (사회 시스템·재건), 갈라진 콘크리트 위 작업자 (분쟁·균열), 거대 계약서 위 인물 (계약 협상).

## prompt_template

```
Tilt-shift macro photography of small miniature figures (about 1:64 to 1:87 scale)
acting out {scene} on top of everyday objects rescaled as the landscape.
Choose an object that metaphorically represents the abstract legal concept in {scene}
(documents, contracts, coins, biscuits, cracked concrete, folders, keys, stamps —
whichever fits the scene's metaphor).
Shallow depth of field, soft natural lighting, light gray or out-of-focus neutral background.
Mood: {mood}.
Natural figure colors are allowed (helmets, vests, clothing), with a single
wine-magenta accent on {accent_target} as the focal element.
No human faces in close-up. No visible text, signs, letters, numbers, or readable labels.
Editorial documentary photo, Toss-feed soft minimalism, slightly cinematic light.
```

## Why this style?

- **얼굴 환각 회피**: 작은 figure 스케일로 인물 얼굴 디테일 자연 흐림
- **한국 외 맥락 환각 회피**: 사물 메타포라 도시·인물 풍경에 의존 X
- **법률 톤 완화**: 무거운 법조 콘텐츠를 디오라마 비유로 시각적 호흡
- **법률 도메인 1차 감성형**: 본문이 법원 풍경 명시 X 한 경우 korean_court_scene 보다 자연 정합도 높음 (대부분의 절차·분쟁·계약 콘텐츠)

## reference

운영 reference image (사용자 컨펌, 2026-05-18):
- 도시 tilt-shift (레고/장난감 도시 풍경) — 큰 풍경을 미니어처로
- 비스킷 위 미니어처 작업자 — 일상 사물 메타포
- 갈라진 콘크리트 위 작업자 — 추상 개념(균열·분쟁) 메타포

[reference_library/visual_styles/miniature_stock/](../../reference_library/visual_styles/miniature_stock/) 에 저장 권장 (운영 spec SOT).
