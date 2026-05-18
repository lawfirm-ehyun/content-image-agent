---
name: cinematic_three_frame
tone: 시네마틱한 3프레임 연속 필름 스틸 / 가공되지 않은 아날로그 필름 톤
use_when: 도입부에 동일 인물·장면의 짧은 스토리텔링 (시간 흐름·감정 변화) / 인물 사연이 한 순간이 아니라 짧은 시퀀스로 풀리는 경우
aspect_ratio: 1024x1536
text_rule: zero
quality: high
reference_dir: reference_library/visual_styles/cinematic_three_frame/
---

# cinematic_three_frame — 시네마틱 3-프레임 필름

> Phase 4.2 신설. 상세 spec: [docs/visual_styles_library_v1.md §2.5](../../docs/visual_styles_library_v1.md). 사용자 컨펌 2026-05-14 — A안 (스타일별 aspect_ratio 자유). 2:3 portrait 단일.

## prompt_template

사용자 원문 자연어 prompt 그대로 + brand 톤 정합 minor adjust.

```
시네마틱한 3프레임 연속 필름 스틸(가로 프레임을 세로로 쌓은 형태)로 {scene} 을(를)
표현해줘.

가장자리는 여백 없이 꽉 채우는 풀 블리드로 처리해줘. 각 프레임은 같은 장면의 서로 다른
순간을 명확한 흐름으로 보여줘야 해. 구도, 카메라 앵글, 촬영 거리에 변화를 주어 움직임과
스토리텔링이 느껴지게 해줘.

시네마틱하고 쿨톤이며 고대비에 깊고 진한 블랙이 표현되는 필름을 사용하고, 자연스러운
컬러 그레이드를 적용해줘. 은은한 필름 그레인, 약간의 모션 블러, 자연스러운 불완전함을
더해 아날로그 사진을 재현해줘.

꾸밈없는 구도와 진솔한 감정을 유지하면서, 움직임과 잔잔한 스토리텔링이 느껴지도록 해줘.
전체적인 분위기는 가공되지 않은 필름 스틸처럼 시네마틱하고, 향수를 불러일으키며,
인위적이지 않은 느낌이어야 해.

분위기 키워드: {mood}.
한국 도시·실내 맥락. 사람 얼굴은 정면 클로즈업 회피, 옆모습·뒷모습·실루엣 우선.
이미지 안에 텍스트·간판·문자·숫자·라벨 절대 X.
브랜드 톤: 차분한 신뢰감, 토스피드 에디토리얼 미니멀리즘, wine-magenta 색감은 {accent_target}
에 은은하게만 (포스터 색감 아님).
```

## Why this style?

사용자 직접 제공 prompt. 도입부 사연이 시퀀스(시간 흐름)로 풀릴 때 라인 일러스트 1컷보다 더 강한 스토리텔링. 2:3 portrait 노션 inline 에서 세로 길이가 크지만 도입부 헤더 다음 임팩트 포지션. `quality=high` (thinking) — 실비/한글 정확도 4.2 Do 첫 5건 e2e 후 측정.
