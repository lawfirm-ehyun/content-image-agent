# Visual Styles Library v1 (Phase 4.2)

> [ehyun-image-agent-plan_1.md §14](../ehyun-image-agent-plan_1.md) 본문 §14.2 "스타일 라이브러리 메타 구조" 의 상세 정의.
> Phase 4.2 진입 시 `skills/visual_styles/<name>.md` + `reference_library/visual_styles/<name>/` 로 ship.
> 본 문서는 5종 스타일 spec + frontmatter sample. plan 본문에는 요약만.

---

## 1. 메타 구조 — frontmatter 스키마 (필수 6 + 선택 3, 사용자 컨펌 2026-05-14)

5종 모두 동일 스키마. 새 스타일 추가 시 동일 필드 박아야 LLM 자동 매칭 작동.

### 1.1 필수 (6)

| 필드 | 타입 | 의미 | 예시 |
|---|---|---|---|
| `name` | str | 스타일 식별자 (snake_case, ai_render.py 분기 키) | `point_color_line` |
| `tone` | str | 한 문장 톤 요약 (LLM 매칭 reasoning 입력) | "단색 라인 + wine-magenta accent 1포인트" |
| `use_when` | str | 본문 패턴 매칭 룰 (LLM 본문 보고 best fit 결정) | "도입부 사용자 사연·상황 묘사 / H2 첫 단락 인물 등장" |
| `prompt_template` | str (multiline) | gpt-image 자연어 prompt 본문. `{scene}` / `{mood}` / `{accent_target}` placeholder 허용 | (§2.x 참조) |
| `aspect_ratio` | enum | `1024x1024` / `1024x1536` / `1536x1024` 중 1 (= 1:1 / 2:3 / 3:2) | `1536x1024` |
| `text_rule` | enum | `zero` (텍스트 0 강제, vision 텍스트 픽셀 ≥ 1% 폐기) / `factual` (본문 사실 인용 OK, OCR Levenshtein ≤ 2) | `zero` |

### 1.2 선택 (3)

| 필드 | 타입 | 의미 | default |
|---|---|---|---|
| `reference_dir` | str | `reference_library/visual_styles/<name>/` 경로 (LLM이 reference image input 활용) | `reference_library/visual_styles/<name>/` (자동 추정) |
| `quality` | enum | `medium` / `high` (gpt-image quality) — high 는 thinking, medium 은 instant | `medium` |
| `accent_target_default` | str | `accent_target` 미지정 시 fallback (라인 일러스트류만 의미 있음) | null |

### 1.3 frontmatter 본문 구조

```markdown
---
name: <snake_case>
tone: <한 문장>
use_when: <본문 패턴>
aspect_ratio: <1024x1024 | 1024x1536 | 1536x1024>
text_rule: <zero | factual>
quality: <medium | high>             # 선택, default medium
reference_dir: <경로>                 # 선택
accent_target_default: <자연어 키워드> # 선택
---

prompt_template: |
  <gpt-image 자연어 prompt 본문.
   {scene} / {mood} / {accent_target} placeholder 허용.>

# Why this style?
<운영 노트 — 어느 페이지에서 잘 통했는지, 회피 케이스 등.>
```

> `prompt_template` 은 frontmatter 가 아니라 본문 fenced 영역에 둠 (multiline + Korean 자연어 가독성).

### 1.4 LLM 매칭 룰 (Phase 4.2 Do 단계 코드 작업, v1.8.5 갱신 — 조건부 default 사상)

`tools/llm/analyze_content.py` 가 감성형 슬롯 trigger 시:
1. `skills/visual_styles/*.md` 모두 load → frontmatter `name` / `tone` / `use_when` 만 추출해 슬림 표 합성
2. analyze_content prompt 에 inject — LLM 이 본문 H2/H3 + 첫 단락 보고 best fit 결정
3. 결과: `extracted_data.visual_style = <name>` + `scene` / `mood` / `accent_target` 합성
4. `ai_render.render_ai_card` 가 `card_type="ai_visual"` 분기 → `visual_style` 보고 `skills/visual_styles/<name>.md` load → `prompt_template` placeholder 치환 → gpt-image 호출

**매칭 결정 사상 (v1.8.5, 2026-05-19 사용자 컨펌 — plan §14.3 visual_style 매칭 사상 갱신)**:

- **specific trigger 우선**: `point_color_line` (구체 인물 묘사 명시) / `korean_court_scene` (법원 풍경 명시) / `cinematic_three_frame` (시간 흐름 시퀀스 명시) / `blueprint_poster` (추상 구조 환기) — use_when 패턴과 본문 명확 매칭 시 우선 채택
- **조건부 default — `miniature_stock`**: 본문이 추상 법률 개념(계약·분쟁·합의·절차·파산·소송·채권·증거) 서술 또는 의뢰인 사연이지만 인물 구체 묘사 약함 → default 채택
- **조건도 안 맞고 다른 specific 도 안 맞음 → 슬롯 폐기** (환각 가드 유지). 무조건 default X — "추상 법률 개념 / 약한 사연" 게이트가 부적합 본문(순수 통계·정보) 강제 진입 차단.

이전 v1.8 사상 "매칭 실패 → 슬롯 폐기, 임의 default fallback X" → v1.8.5 에서 `miniature_stock` 만 조건부 default 로 격상. 환각 가드는 추상 법률 개념 게이트로 대체.

---

## 2. 초기 5종 스타일 (사용자 확정 2026-05-14)

### 2.1 `point_color_line` — 포인트 컬러 라인 일러스트 (기존 illustration 톤 보존)

```markdown
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
```

> v1.8.5 (2026-05-19) — use_when 좁힘: 구체적 인물 묘사 명시 필요. 약한 사연·추상 법률 개념은 `miniature_stock` 조건부 default 로 흐르도록 가드.

**prompt_template**:
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

**Why this style?**
v1.6.4 운영에서 토스피드 톤과 가장 잘 어울리던 라인. 정보형 카드 사이 호흡 분기 + 도입부 사연 시각화에 default.

---

### 2.2 `miniature_stock` — 미니어처 스톡 이미지

```markdown
---
name: miniature_stock
tone: 작은 미니어처 figure + 일상 사물 메타포 디오라마 / tilt-shift 매크로 photo
use_when: 법률 추상 개념(계약·분쟁·합의·절차·파산·소송·채권·증거)을 일상 사물 메타포(서류·도장·동전·계약서·열쇠·균열 등)로 시각화 가능한 본문 — 인물 얼굴 환각 회피 + 무거운 법률 톤을 디오라마로 완화. 본문이 법원 외관·법정 풍경을 명시적으로 묘사하지 않는 한 korean_court_scene 보다 우선 검토. **ai_visual 조건부 default — 다른 specific trigger (point_color_line 의 구체 인물 / korean_court_scene 의 법원 풍경 / cinematic_three_frame 의 시퀀스 / blueprint_poster 의 추상 구조) 안 걸리고 본문이 추상 법률 개념 서술 또는 인물 묘사 약한 사연이면 우선 채택.**
aspect_ratio: 1536x1024
text_rule: zero
quality: medium
reference_dir: reference_library/visual_styles/miniature_stock/
---
```

> v1.8 Phase 4.3 (2026-05-18) — 사용자 reference 기반 재정의 (tilt-shift 사진 → 메타포 사물 디오라마). v1.8.5 (2026-05-19) — ai_visual 조건부 default 격상 (§1.4 매칭 룰 참조).

**prompt_template**:
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

**Why this style?**
얼굴 환각 / 한국 외 맥락 환각을 사물 스케일로 회피. 계약·분쟁 같은 추상 법률 개념을 일상 사물 메타포로 풀기 좋음. 법률 도메인 1차 감성형 (default).

---

### 2.3 `korean_court_scene` — 한국 법원 실제 풍경

```markdown
---
name: korean_court_scene
tone: 한국 법원 외관·복도·법정 풍경 사진 / 차분한 다큐멘터리 톤
use_when: 본문이 법원 외관·복도·법정 풍경을 명시적으로 묘사할 때 한정 (예 — "OO법원에 출석", "법정에서 다투다", "판사가 법정에서 선고", "법원 앞에서 만나"). 단순 법적 무게감 환기·소송 절차 일반은 miniature_stock 디오라마 메타포가 우선 후보.
aspect_ratio: 1536x1024
text_rule: zero
quality: medium
reference_dir: reference_library/visual_styles/korean_court_scene/
---
```

> v1.8 Phase 4.3 (2026-05-18) — use_when 좁힘: 법률 도메인 default 지위 박탈, 본문이 법원 풍경을 명시적으로 묘사할 때만 trigger.

**prompt_template**:
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

**Why this style?**
망치/저울/외국 법정 클리셰 회피 (ehyun_visual_guide.md "금지" §). 한국 법원 맥락이 콘텐츠 사실과 정합.

---

### 2.4 `blueprint_poster` — 블루프린트 포스터

```markdown
---
name: blueprint_poster
tone: 청사진(blueprint) 라인 + 구조도 / 절차·시스템·관계도 시각화
use_when: 절차/시스템 다이어그램이 본문에 등장하나 정보형 timeline·simple_table 로 풀기 부적합 (추상도 높음) / 도입부 "이 글에서 다루는 구조" 시각 환기
aspect_ratio: 1536x1024
text_rule: zero
quality: medium
reference_dir: reference_library/visual_styles/blueprint_poster/
---
```

**prompt_template**:
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

**Why this style?**
정보형 카드는 사실 시각화. 본문이 추상 구조(시스템·관계·흐름) 환기만 필요한 경우 blueprint 톤이 정보형 트리거 없이 메시지 전달.

---

### 2.5 `cinematic_three_frame` — 시네마틱 3-프레임 필름

> **aspect_ratio fix (사용자 컨펌 2026-05-14, plan §14.4 A안)**: 사용자 prompt 원문이 "가로 프레임을 세로로 쌓은 형태" 명시 → **2:3 portrait (1024×1536)** 단일. 스타일별 비율 자유 채택으로 충돌 해소.

```markdown
---
name: cinematic_three_frame
tone: 시네마틱한 3프레임 연속 필름 스틸 / 가공되지 않은 아날로그 필름 톤
use_when: 도입부에 동일 인물·장면의 짧은 스토리텔링 (시간 흐름·감정 변화) / 인물 사연이 한 순간이 아니라 짧은 시퀀스로 풀리는 경우
aspect_ratio: 1024x1536
text_rule: zero
quality: high
reference_dir: reference_library/visual_styles/cinematic_three_frame/
---
```

**prompt_template** (사용자 원문 자연어 prompt 그대로 + brand 톤 정합 minor adjust):

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

**Why this style?**
사용자 직접 제공 prompt. 도입부 사연이 시퀀스(시간 흐름)로 풀릴 때 라인 일러스트 1컷보다 더 강한 스토리텔링. 2:3 portrait 노션 inline 에서 세로 길이가 크지만 도입부 헤더 다음 임팩트 포지션.

---

## 3. 스타일 추가 절차 (운영자용, 30분 가이드)

새 스타일 1종 추가:

1. **`skills/visual_styles/<new_name>.md` 작성**
   - frontmatter 필수 6 + 필요시 선택 3
   - 본문 `prompt_template` (자연어, {placeholder} 활용)
   - "Why this style?" 짧게

2. **`reference_library/visual_styles/<new_name>/` 폴더 생성**
   - reference image 1-3 장 (webp/png/jpg). 없어도 작동하지만 LLM 매칭 품질 ↑
   - `.gitignore` 적용 — local 시드만, repo 미커밋 (현재 정책 유지)

3. **첫 운영 trigger 후 1주 모니터링**
   - 노션 로그 DB `타입=ai_visual`, `extracted_data.visual_style=<new_name>` row 누적 확인
   - vision review 폐기율, OCR 텍스트 환각 검출 빈도 체크
   - 적합도 낮으면 frontmatter `use_when` / `prompt_template` 정밀화

**LLM 코드 변경 없이 새 스타일 자동 인식**. analyze_content 가 `skills/visual_styles/` 디렉터리 scan → frontmatter load.

---

## 4. 비율·텍스트 룰 매트릭스

| name | aspect_ratio | text_rule | quality |
|---|---|---|---|
| point_color_line | 1536x1024 (3:2) | zero | medium |
| miniature_stock | 1536x1024 (3:2) | zero | medium |
| korean_court_scene | 1536x1024 (3:2) | zero | medium |
| blueprint_poster | 1536x1024 (3:2) | zero | medium |
| cinematic_three_frame | 1024x1536 (2:3) | zero | high |

전 5종 `text_rule=zero` — 첫 출범. 향후 `factual` 스타일(예: 신문 헤드라인 카드, 법조 명언 포스터)은 vision OCR Levenshtein 검증 인프라(§19.16 갱신 + plan §19.11 카드별 분기) 완비 후 추가.

`kakao_dialogue` (= 기존 활성 카드, `factual` 룰) 는 Phase 4 에서도 별도 카드로 유지 — `ai_visual` 신설과 무관.

---

## 5. 미해결 (Design/Do 단계에서 fix)

| 항목 | 결정 시점 |
|---|---|
| `quality=high` (cinematic_three_frame) 의 실제 비용 / latency / 한글 정확도 | Phase 4.2 Do 첫 5건 e2e 후 |
| reference image 가 LLM 매칭 품질에 미치는 영향 측정 | Phase 4.2 Do 1주 운영 후 (reference 있는 스타일 vs 없는 스타일 폐기율 비교) |
| `accent_target_default` 자동 추정 룰 (스타일 정의에 없으면 LLM 가 합성 가능 여부) | Phase 4.2 Do |
| 동일 페이지 `ai_visual` 슬롯 2개 trigger 시 같은 visual_style 연속 허용 여부 | Phase 4.2 Do (slot_selection mix 룰 §19.17 갱신과 연동) |
