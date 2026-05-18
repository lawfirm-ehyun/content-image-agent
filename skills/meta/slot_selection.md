# Slot Selection (v1.8 Phase 4.2)

본문 블록을 분석해서 페이지 전체에 어떤 image_type 슬롯을 어디에 넣을지 결정한다.
0개도 OK이지만 이현 콘텐츠는 보통 2000자+이라 0개 결정은 거의 없을 것.

## v1.8 사상 — 정보형 + 감성형 mix, 슬롯 3 cap

**페이지당 슬롯 합계 3 cap (hard, v1.8 Phase 4.2 §14.5)**. 권장 mix: 정보형 1-2 + 감성형 1-2, **합 ≤ 3**. 정보형은 사실 시각화, 감성형은 도입부 분위기/내러티브 전달. 콘텐츠 종속 — 강제 X.

| 카테고리 | 카드 | 생성 | 트리거 |
|---|---|---|---|
| **정보형** | `simple_table` / `chart`(line·bar·donut·pie) / `comparison_table` / `key_points_card` / `timeline` | template | 본문 사실 시각화 |
| **감성형 (텍스트 0)** | `ai_visual` (5 visual_style: point_color_line / miniature_stock / korean_court_scene / blueprint_poster / cinematic_three_frame) | AI (gpt-image) | 도입부 분위기 / 사용자 사연 / 한국 법원 풍경 / 추상 구조 환기 |
| **감성형 (텍스트 사실)** | `kakao_dialogue` | AI (gpt-image thinking) | 본문 대화 시나리오 텔링 |
| **감성형 [deprecated]** | `illustration` (단일 라인 스타일, v1.8 Phase 4.2 에서 ai_visual + point_color_line 으로 흡수) | AI (gpt-image instant) | legacy path만 — 신규 trigger 는 ai_visual 권장 |

### 사실 정확성 절대 룰 #1 — 카테고리 차등
- **정보형 + kakao_dialogue**: 본문 그대로 (숫자/values/labels/messages 1자 변경 X)
- **ai_visual + illustration**: scene/mood/accent_target은 본문 사실 안에서 합성 OK (라벨링·재표현). 이미지 안 텍스트 0 강제 (`text_rule=zero`, vision 검증).

---

## 정보형 결정 사상 (v1.3) — 줄글 시각화가 1순위 목적

**원칙**: 카드는 본문에 **줄글로 풀려있는 구조적 정보를 시각화**하는 게 1순위 목적.
본문에 이미 table block으로 정리된 데이터는 우선순위 낮음.

### 정보형 슬롯 결정 우선순위 (높은 순)
1. **줄글로 풀려있는 구조 발굴** (enumeration / 비교 / 절차 / 조건→결과) → simple_table
2. **본문 표 → chart 형식 전환** (시계열 데이터일 때만) → chart line
3. **본문 표 → 다른 의미 있는 재구성** (드물게. 컬럼 발췌·관점 변경) → simple_table
4. **본문 표 그대로 복제** → ❌ 슬롯 X (카드 목적과 다름)

### 정보형 좋은 슬롯 후보

본문에 다음 패턴이 줄글로 있으면 카드 후보:

- **N가지 enumeration — 핵심 정리 / 체크리스트 / 주의사항** ("핵심 3가지", "주의사항 5가지", "준비 서류") → `key_points_card`
  - extracted_data: `title` (str), `items: [{label (str), description? (str scalar)}]`, `footnote?` (3-5개)
  - **`description` 은 string scalar 필수** — dict 산출 시 슬롯 폐기 (Gap B, 2026-05-15). description은 옵션 — label만으로 충분하면 description 생략 가능.
- **N가지 enumeration — 표 형식 데이터 (2-3 컬럼)** ("권리/내용", "조건/결과") → `simple_table`
- **비교 구조 (2-3 옵션 × 항목별 차이)** ("협의 vs 재판 이혼", "일반 vs 간이 절차") → `comparison_table`
  - **§23 경계**: 다른 법무법인과 비교 X. 비교 대상은 법적 절차/유형/조건 등 추상 개념이어야 함.
  - 모든 비교 컬럼 시각 동등 (highlight 없음 — v1.4 §23 안전 재설계).
  - extracted_data: `title`, `column_headers` (label컬럼 포함), `rows: [{label, values}]`, `footnote?`
- **단순 차이 비교 (한 축만)** ("전과 후", "X와 Y") → `simple_table` (3열 비교 형식)
- **법률 절차/소송 흐름 (4-6 단계)** ("소장 접수 → 답변서 → 변론 → 조정 → 판결") → `timeline`
  - extracted_data: `title` (str), `steps: [{label (str), description? (str scalar), duration? (str scalar), icon? (str)}]`, `footnote?`
  - **`description` / `duration` 은 string scalar 필수** — dict (`{value, unit}` 등 구조화) 산출 시 슬롯 폐기 (Gap B, 2026-05-15). 단위 포함은 단일 문자열 ("30일", "1-3개월", "약 2주").
  - `icon`은 Lucide 이름 (`file-text`, `gavel`, `scale`, `handshake`, `mail`, `clock`, `check-circle` 등)
  - 단순 enumeration (3가지)은 simple_table 우선. 순차 단계가 명확할 때만 timeline.
- **절차/순서 (단순 3-4 항목, 시간/소요 정보 없음)** → `simple_table`
- **조건→결과 매핑** ("~한 경우에는", "다음 요건을 갖추면 ~한 권리") → `simple_table`
- **시계열 추이** (연도별/시점별 숫자 변화, 2개 이상 포인트) → `chart` sub_type=`line`
  - **엄격 조건**: x축이 시점(연도/월/분기), y축이 숫자 추이. 절차/단계/분류/카테고리 비교는 chart 절대 X — simple_table로.
  - **chart line은 single series만.** 본문에 multi-column 시계열 표가 있으면 가장 의미 있는 1개 컬럼만 골라 `values`로 쓰고, 나머지 컬럼은 폐기.
  - **chart 슬롯 extracted_data 필수 필드 (누락 = 폐기)**:
    - `title` (str): 직관 합성 OK
    - `labels` (list[str]): x축 라벨 — 시점 ("2021", "2022", ...)
    - `values` (list[number]): y값 — 숫자 추이. **list[float] 또는 list[int]. 빈 list X.**
    - `point_labels` (list[str]): 포인트 위 표시 — "28,988건" 형태 (단위 포함 라벨)
    - `y_unit` (str, 옵션): "(건)" "(%)" 등
    - `source` (str, 옵션): 본문 출처 그대로
    - `orientation` (str, 옵션, line/bar만): `"vertical"`(default) | `"horizontal"`. 카테고리 라벨이 길거나 6+개면 horizontal.
    - `emphasis_index` (int, 옵션, 4 sub_type 공통): 본문이 강조하는 포인트/막대/slice 인덱스. 강조 신호 없으면 생략(None) — 임의 강조 X.
  - **values 못 채우면 chart 슬롯 결정 X.** 본문에 시계열 숫자 명시 안 됐으면 simple_table 또는 슬롯 X.
- **카테고리 비교 (지역별/유형별 절대값)** ("지역별 건수", "사건 유형별 처리") → `chart` sub_type=`bar`
  - 데이터 shape는 line과 동일 (title, labels, values, point_labels). x축이 카테고리(순서 의미 약함).
- **분포/구성비 (전체 합 = 100%)** ("사건 유형별 비율", "연령대별 분포") → `chart` sub_type=`donut` 또는 `pie`
  - extracted_data: `title`, `labels`, `values` (음수/합 0 X), `point_labels?`, `source?`. 2-6 slice.
  - 카테고리 7개+면 작은 비중을 '기타'로 합산하거나 슬롯 분할.
  - donut(중앙 hole, 현대 톤) 기본 권장 / pie(전통)는 비율 강조 시.

**chart 슬롯 변환 예시 (multi-column 시계열 표 → single series chart)**:
```
본문 표:
| 연도   | 발생 건수 | 검거 건수 | 검거율 | 특징 |
| 2021년 | 28,988건  | 22,299건  | 76.9%  | ... |
| 2022년 | 29,258건  | 18,242건  | 62.3%  | ... |
| 2023년 | 24,252건  | 20,390건  | 84.1%  | ... |
| 2024년 | 33,581건  | 26,529건  | 79.0%  | ... |

→ chart 슬롯 (1 series 선택, 예: 발생 건수):
extracted_data:
  title: "사이버명예훼손 발생 추이"
  labels: ["2021", "2022", "2023", "2024"]
  values: [28988, 29258, 24252, 33581]
  point_labels: ["28,988건", "29,258건", "24,252건", "33,581건"]
  y_unit: "(건)"
  source: "출처: 경찰청 ..."
```

### 본문 table block 처리 (v1.3)
- **시계열 데이터**가 표 안에 있음 → `chart` line으로 형식 전환 → 슬롯 OK
- **컬럼 재구성 / 일부 발췌**로 가치 추가 → `simple_table` OK
- **본문 표 그대로 simple_table 복제** → ❌ 슬롯 X

### simple_table 컬럼 수 룰 (v1.3)
- **2컬럼 (default)** — enumeration / 절차 / 조건→결과 / 단순 비교. 줄글 시각화의 90%는 2컬럼.
- **3컬럼** — A vs B 비교 또는 분류+설명+특징 같은 특수 케이스.
- **4컬럼 이상** — ❌ 줄글 시각화 부적합. 핵심 2-3컬럼만 발췌, 슬롯 분할, 또는 슬롯 X.

---

## 감성형 결정 룰 (v1.8 갱신)

### `ai_visual` — 5 visual_style 라이브러리 (v1.8 Phase 4.2 신설)

`skills/visual_styles/*.md` frontmatter (analyze prompt에 슬림 표로 inject) 의 `use_when` 패턴과 본문이 명확히 매칭될 때 후보. 매칭 안 되면 슬롯 폐기 (임의 default 금지).

**visual_style 선택 룰**:
- 본문 H2 첫 단락 + 도입부 톤 분석 → 표의 `use_when` 패턴 중 best fit 1개 결정
- `point_color_line`: 도입부 사용자 사연 / 콘텐츠 전환부 (기존 illustration 흡수, default)
- `miniature_stock`: 추상 개념 사물 비유 가능 (계약/합의/분쟁) / 얼굴 노출 회피
- `korean_court_scene`: 소송·재판 절차 / 법원 출석·변호사 등장 / 법적 무게감 환기
- `blueprint_poster`: 추상 구조·시스템·관계도 환기 (정보형 timeline/simple_table 부적합)
- `cinematic_three_frame`: 인물 사연이 짧은 시퀀스 (시간 흐름·감정 변화) 로 풀리는 경우 — 2:3 portrait, quality=high (실비 ↑)

**금지 케이스**:
- 본문에 사연/장면/구조/대화·인물 시퀀스 묘사 없음 → ai_visual trigger X (환각 방지)
- 텍스트 다수 필요 → 정보형 카드 (template)
- 사실 인용 필요 → kakao_dialogue 또는 정보형 simple_table
- 같은 페이지 ai_visual 2개+ 시 visual_style 연속 동일 → 톤 단조 (별 visual_style 또는 슬롯 분할)

**extracted_data** (analyze prompt 응답):
- `visual_style` (str, 필수): 위 5개 name 중 1. 빈 값 / 미정의 값 → 슬롯 폐기.
- `scene` (str, 필수): 장면 묘사 자연어. 본문 사실 안에서 합성.
- `mood` (str, 필수): 분위기 키워드. "당혹스러움" / "긴장" / "고민" / "체계적" 등.
- `accent_target` (str, 옵션): wine-magenta 강조 자연어. 비우면 frontmatter `accent_target_default` 또는 "a key element" fallback.
- `alt_text` (str): 노션 이미지 alt. 한국어 1-2줄. 본문에서 합성.
- `footnote` (str, 옵션)

### `illustration` [deprecated v1.8 Phase 4.2] — legacy path만

> ai_visual + visual_style=point_color_line 으로 흡수. 신규 trigger 는 ai_visual 권장. backwards compat 유지 (legacy path 진입은 LLM이 본 항목 보고 결정한 경우만).

본문에 도입부 사용자 사연 패턴이 있어도 ai_visual 우선. ai_visual 매칭 실패 시 fallback illustration trigger 도 금지 — 환각 방지 (slot 폐기).

### `kakao_dialogue` — 의뢰인-변호사 카톡 대화

본문에 다음 패턴이 있으면 후보:

- **본문 안 의뢰인-변호사 채팅 시나리오**
  - "Q: ~ A: ~" 형식, "의뢰인이 물어봅니다", 따옴표 + 인용된 대화
  - 4-8 메시지 분량 (왕복 2-4회). 더 길면 글로 풀어쓰기 권장.
- **금지 케이스**:
  - 본문에 대화 시나리오 없는데 카톡으로 만들기 X (환각)
  - 절차/체크리스트 → timeline / key_points_card
  - 한 페이지에 kakao_dialogue 2개+ → 톤 과잉, 1개만

**extracted_data**:
- `title` (str, 옵션): 카드 상단 라벨. 예: "의뢰인의 첫 질문, 변호사의 답변"
- `messages` (list): `[{sender_label, text, time?}, ...]` — **본문 대화 1자 변경 X** (OCR Levenshtein ≤ 2 검증)
  - `sender_label`: "의뢰인" / "변호사" / "상담사" 등 본문 인용대로
  - `text`: 메시지 본문 그대로
  - `time` (옵션): "오전 9:10" 형식
- `source` (str, 옵션): "본 사연은 실제 의뢰인 사연을 각색했습니다" 등
- `footnote` (str, 옵션)

---

## Page-level mix 권장 룰 (v1.8 갱신 — 슬롯 3 cap hard)

- **페이지당 슬롯 합계 3 cap (hard, v1.8 Phase 4.2 §14.5)**. 이전 2-4 권장 → 3 hard cap. ai_visual `quality=high` 변동성 + vision review 슬롯당 cost 마진 반영.
- **권장 mix**: 정보형 1-2 + 감성형 1-2, **합 ≤ 3**.
- **4개+ trigger 시**: 우선순위 낮은 1개 폐기. 우선순위 룰:
  - (a) 정보형 0 시 정보형 1개 보장 (감성형 1-2 + 정보형 1 = 3 우선)
  - (b) 정보형 ≥ 2 + 감성형 0 → ai_visual 1개 추가 trigger 후보 (감성 mix 권장)
  - (c) kakao_dialogue 우선, ai_visual 차순, 정보형 동등 — 4번째 슬롯은 데이터 신호 약한 카드부터 폐기
- **콘텐츠 종속 — 강제 X**:
  - 도입 사연이 약한 페이지 → 감성형 생략 OK (정보형만 2-3개)
  - 데이터 풍부 페이지 → 정보형 3개도 허용 (단 3 cap 안에서)
  - 짧은 본문 (1500자 미만) → 슬롯 1-2개로 압축
- **금지 조합**:
  - 감성형만 (정보형 0): 정보 콘텐츠로서 가치 결여
  - 정보형만 (감성형 0) 강제: 콘텐츠가 정보 위주면 OK, 강제 추가 X
  - 같은 카드 타입 3개 연속 (예: simple_table 3개): 시각 단조로움
  - kakao_dialogue 2개+ in 한 페이지: 톤 과잉
  - ai_visual 2개 + 동일 visual_style: 톤 단조 (별 visual_style 또는 슬롯 분할)

---

## 폐기 후보

- 같은 표현 형식(table → simple_table)으로 같은 데이터 그대로 옮긴 카드
- 50자 미만 단순 정의 한 문장
- **(`chart`) 데이터 포인트 1개** — v1.6.1 `stat_highlight` 폐기로 폴백 없음. 슬롯 결정 X (본문 텍스트로 강조 유지).
- **단일 숫자 강조** ("10명 중 7명", "638억") — v1.6.1 `stat_highlight` 폐기. 슬롯 결정 X.
- 본문에 대화/사연 없는데 만들어내는 감성형 카드 (환각)
- **ai_visual visual_style 매칭 실패** — 5 visual_style use_when 패턴 중 명확히 매칭되는 것 없으면 슬롯 폐기 (임의 default 금지, plan §14.2 §1.4)
- **4번째+ 슬롯** — 3 cap 초과분은 우선순위 룰로 폐기 (위 Page-level mix)

> v1.6.2: AI prompt는 자연어 묘사로 작성 (픽셀/hex/CSS 토큰 over-constraint X). 텍스트 사실 필드만 `exact_korean_strings`로 엄격 분리.

---

## 위치 결정

- **정보형 카드**: 해당 데이터가 등장하는 H2 섹션의 **첫 단락 직후**. 첫 단락이 50자 미만이면 다음 단락 후.
- **ai_visual**: 페이지 도입부 H2 섹션 첫 단락 직후 (도입 사연·구조·법원 풍경 등 환기) — 또는 콘텐츠 전환부 H2 헤딩 직후. `visual_style=cinematic_three_frame` 은 2:3 portrait 라 도입부 헤더 직후 임팩트 포지션 권장.
- **illustration** [deprecated]: ai_visual + point_color_line 으로 라우팅 권장. legacy path 진입 시 위치는 ai_visual 과 동일.
- **kakao_dialogue**: 본문 대화 인용 직후.

## 슬롯 개수

- **페이지당 3 cap hard (v1.8 Phase 4.2 §14.5)**. 4개+ 결정 X — 우선순위 룰 (위 Page-level mix) 적용해 1개 폐기.
- 슬롯 0개도 OK (콘텐츠 짧거나 시각화할 줄글 구조가 없을 때). 단 추적 위해 로그 DB에 1행 기록 필수 (plan §19.6 — `타입=없음` select 옵션 사용).

---

## 출력 형식 (orchestrator가 파싱)

### title / headers / cells 룰 — v1.3 (직관 합성 허용)

모든 슬롯의 `extracted_data.title`은 **반드시** 채울 것 (illustration·kakao_dialogue는 `title` optional). 비우지 말 것.

**공통 룰 (title / headers / cells)**:
- 본문 사실 안에서 직관 합성 OK — 축약·재표현·라벨링 허용
- 본문에 없는 사실/숫자/주체 삽입 X (환각 방지)
- 가독성 권장: 짧고 직관적. 길이 강제 한도 없음

**title 추가 룰**:
- 본문 H2/H3 문자열과 완전히 동일하면 X (통째 복붙만 X, 부분 겹침은 OK)

**headers / cells 추가 룰**:
- 본문 한 문장을 그대로 박지 말고, 핵심을 짧게 재표현
- **한 줄 18자 안 권장 (v1.3 모바일 가독성).** 초과 시 두 줄 또는 키워드형으로 분할.
- **한 카드 행 수 3-5행 권장.** 6행 이상이면 슬롯을 두 개로 분할하거나 핵심만 추려라.
- **본문에 없는 사실/숫자는 절대 추가 X.**
- **쉼표/짧은 절 분할** 활용 — 한 cell 안에서 콤마로 두 호흡 (각 7-9자) 권장

### 출력 예시

```yaml
image_slots:
  # ai_visual (감성형, 도입부 — v1.8 Phase 4.2 신설)
  - type: ai_visual
    position_after_block_id: <block_uuid>
    extracted_data:
      visual_style: "point_color_line"
      scene: "야간 공원에서 음주측정 받는 30대 직장인"
      mood: "당혹스러움"
      accent_target: "직장인의 셔츠 칼라"
      alt_text: "음주운전 적발 후 망연자실한 모습"

  # chart (정보형, 시계열)
  - type: chart
    sub_type: line
    position_after_block_id: <block_uuid>
    extracted_data:
      title: "사이버명예훼손 발생 추이"
      labels: ["2021", "2022", "2023", "2024"]
      values: [28988, 29258, 24252, 33581]
      point_labels: ["28,988건", "29,258건", "24,252건", "33,581건"]
      y_unit: "(건)"
      source: "출처: 경찰청"

  # simple_table (정보형)
  - type: simple_table
    position_after_block_id: <block_uuid>
    extracted_data:
      title: "세입자의 4가지 권리"
      headers: ["권리", "핵심 내용"]
      rows:
        - ["대항력", "집이 팔려도 쫓겨나지 않을 권리"]
        - ["우선변제권", "경매에서 다른 채권자보다 먼저 보증금 회수"]
      highlight_first_col: true

  # kakao_dialogue (감성형, 대화)
  - type: kakao_dialogue
    position_after_block_id: <block_uuid>
    extracted_data:
      title: "의뢰인의 첫 질문"
      messages:
        - sender_label: "의뢰인"
          text: "변호사님, 음주측정 결과가 0.08이 나왔어요. 어떻게 해야 하나요?"
          time: "오전 9:10"
        - sender_label: "변호사"
          text: "0.08은 면허 정지 구간입니다. 우선 진술서 작성 전에 상담부터 받으시는 게 좋습니다."
          time: "오전 9:12"
      source: "본 사연은 실제 의뢰인 사연을 각색했습니다"
```

---

## 사실 정확성 (절대 룰 #1) — v1.8 카테고리 차등

- **사실 그 자체 (정보형 + kakao_dialogue 텍스트 필드)**: 1자도 변경 X. 본문에 명시된 값/대화 그대로. 가짜 출처 X.
  - 정보형: 숫자 / values / labels / point_labels / source
  - kakao_dialogue: messages[i].text, sender_label
  - kakao_dialogue OCR 검증: `tools/llm/image_review.py` vision으로 messages OCR 추출 → Levenshtein distance ≤ 2 검증. 초과 시 retry 1회 → 슬롯 폐기.
- **라벨링·재표현 (정보형 title/headers/cells, ai_visual + illustration scene/mood/accent_target)**: 본문 사실 안에서 직관 합성 OK. 본문에 없는 사실/주체 삽입 X. title은 본문 H2/H3와 완전 동일만 X.
- **ai_visual visual_style 매칭**: 본문 톤 + use_when 패턴 명확 매칭만. 매칭 불확실 시 슬롯 폐기 (임의 default 금지).
- **ai_visual + illustration 이미지 안 텍스트**: 0 강제 (`text_rule=zero`). Phase 4.3 vision 인프라 (§19.16, `tools/render/vision_review.py`) 완성 후 픽셀 ≥ 1% 또는 OCR token ≥ 3개 → retry 1회 → 슬롯 폐기.
