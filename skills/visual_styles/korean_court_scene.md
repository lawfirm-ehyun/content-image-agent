---
name: korean_court_scene
tone: 한국 법원 외관·복도·법정 풍경 사진 / 차분한 다큐멘터리 톤
use_when: 본문이 법원 외관·복도·법정 풍경을 명시적으로 묘사할 때 한정 (예 — "OO법원에 출석", "법정에서 다투다", "판사가 법정에서 선고", "법원 앞에서 만나"). 단순 법적 무게감 환기·소송 절차 일반은 miniature_stock 디오라마 메타포가 우선 후보.
aspect_ratio: 1536x1024
text_rule: zero
quality: medium
reference_dir: reference_library/visual_styles/korean_court_scene/
---

# korean_court_scene — 한국 법원 실제 풍경

> Phase 4.2 신설, v1.8 Phase 4.3 (2026-05-18) use_when 좁힘 — 사용자 컨펌으로 법률 도메인 default 지위 박탈, 본문이 법원 풍경을 명시적으로 묘사할 때만 trigger. 상세 spec: [docs/visual_styles_library_v1.md §2.3](../../docs/visual_styles_library_v1.md). 망치/저울/외국 법정 클리셰 회피 (ehyun_visual_guide.md "금지" §).

## prompt_template

```
Documentary photograph of {scene} in a Korean courthouse setting.
Wide or medium shot — court building exterior, hallway, courtroom interior,
or judicial garden as fits the scene. Mood: {mood}.
Soft overcast daylight or warm interior light, desaturated palette,
restrained wine-magenta accent only on {accent_target} (a tie, a folder spine,
a small detail). Avoid courtroom Western iconography
(gavels, scales, blindfolded justice statues, foreign judge robes).
No close-up faces, no readable text or signs, no English signage.
Style reference: Korean editorial photography, calm Toss-feed tone, slight film grain.
```

## Why this style?

망치/저울/외국 법정 클리셰 회피. 한국 법원 맥락이 콘텐츠 사실과 정합.
