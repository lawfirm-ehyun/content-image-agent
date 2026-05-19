# Prompt/Input Review

생성 단계 직전, 입력(template variables)을 셀프 리뷰한다.
**형식 검증은 코드(`chart_render.validate_chart`)가 담당**, 본 스킬은 사실 정확성 + 본문 중복 + §23 검사.

## 사실 정확성 검증 (CRITICAL — 절대 룰 #1) — v1.3 분리

### 사실 그 자체 (절대 일치 — 1자도 변경 X)
- [ ] 모든 **숫자 / values / labels / point_labels** 가 본문에 등장 (1:1, 0% 관용)
- [ ] **source(출처)** 가 본문에 명시된 것과 동일 (가짜 출처 X)
- [ ] 차트 labels 순서가 본문 순서와 일치

### title / headers / cells 검증 (v1.3 — 직관 합성 허용, 사실 일탈 X)
- [ ] `title`, 모든 `headers`, 모든 `cell` 텍스트가 표현하는 **사실(숫자/주체/내용)이 본문 안에 있는가**
      (본문에 없는 사실/주체/숫자를 만들었으면 fail. 예: 본문 4가지인데 5가지 표현)
- [ ] `title` 필드가 채워져 있는가
- [ ] `title`이 인접 H2/H3 본문 헤딩과 **완전히 동일하지** 않은가
      (통째 복붙이면 issues에 "title을 직관적으로 합성하라" 추가)
- [ ] cell이 본문 사실에 충실한 라벨링/축약인가
      (본문 한 문장을 그대로 박은 게 아니라, 짧고 직관적으로 재표현했으면 OK.
       본문에 없는 새 사실을 추가했으면 fail.)

### 본문 중복 검증 (v1.3 신설) — 같은 형식 복제만 폐기
- [ ] 본문에 `[table]` 마커가 있는 영역인데 같은 데이터를 같은 형식(`simple_table`)으로 그대로 옮긴 게 아닌가
- [ ] (같은 형식+같은 데이터면 폐기. revised_data로 수정 X — 슬롯 자체가 가치 없음.)
- [ ] chart로 형식 전환했거나, 컬럼 재구성/일부 발췌로 가치 추가한 경우는 통과.

## alt_text 검증 (v1.9 plan §13 — SEO + a11y caption)

`extracted_data.alt_text` 가 있으면 (7종 카드 모두 필수) 다음 검사. 룰 상세는 `skills/meta/slot_selection.md` "alt_text 룰" 섹션.

- [ ] **80자 이하** (`ALT_TEXT_MAX_CHARS`). 초과 시 issues 에 `"alt_text 80자 초과"` 추가 — orchestrator 가 caption 생략 분기 처리 (슬롯은 살림).
- [ ] **target keyword 1회 포함** — `PAGE TITLE` 핵심 명사가 alt_text 에 1회 자연스럽게 들어갔는지. 2회+ stuffing 도 fail. 0회면 issues 에 `"alt_text 에 페이지 target keyword 없음"`.
- [ ] **자기지시 단어 X** — "이미지" / "그림" / "사진" / "차트" / "표" 같은 메타 단어 사용 X. 발견 시 `revised_data` 로 자동 수정 시도 1회 (의미 보존 가능한 대체어).
- [ ] **본문 통째 복붙 X** — 본문 문장이 alt 안에 5자 차이 이내로 그대로 들어가 있으면 fail (관계/추이/패턴 묘사로 재작성 권장). Levenshtein 정확 측정은 코드 단 추가 검토 — LLM 단에선 "본문 한 문장이 거의 그대로 들어갔는가" 직관 판단.
- [ ] **사실 정확성** — alt 가 표현하는 내용이 카드 데이터/본문 안 사실로 합성된 것인가. 본문에 없는 인물/숫자/시간/장소 삽입 시 즉시 폐기.
- [ ] **front-load 권장** — 핵심 명사가 앞쪽에 있는가. 서술문 prefix("다음 표는~", "본 차트는~")는 자동 `revised_data` 수정 시도.
- [ ] **ASCII 기호만** — em dash (—), en dash (–), 화살표 (→ ← ↔), bullet (· •), 줄임표 (…), smart quotes 사용 X. 발견 시 `revised_data` 로 자동 수정 시도 (em dash → 쉼표, 화살표 → 공백/단어). 검수자가 caption 을 다른 CMS 로 옮길 때 깨짐 방지 + Google word separator 정상 분해.

## 변호사법 §23 컴플라이언스
입력 데이터의 모든 문자열 필드(title, headers, rows, point_labels, footnote, source)에서 검사.

> 키워드 master는 **`tools/compliance/keywords.py`** (plan §19.7, §20.1).
> 1차 regex pass는 코드가 처리 (`tools/llm/review.py`가 LLM 호출 전 자동 검사), LLM은 맥락 판단.
> 본 markdown은 검사 의도 + 카테고리만 안내. 키워드 신설/수정은 코드 master에서.

### 검사 4 카테고리
- **절대성 표현** — "최고", "유일", "100% 승소" 등 객관적 입증 불가 superlative.
- **마케팅 과장** — "당신만을 위한", "특별 혜택" 등 희귀성/배타성 강조.
- **시간 압박** — "지금 아니면", "마지막 기회" 등 긴급성/FOMO 유도.
- **비교 광고** — "타 로펌", "다른 법무법인" 명시 비교.

LLM 검토 기준: 위 카테고리에 해당하는 표현이 데이터에 등장하면 광고 맥락 안 위반인지 판단.
일반 한국어 의미("절대로 안전한 운전" 같은 비-광고 사용)는 통과 가능.

## 위반 시 처리
1. **사실 일탈 위반 (본문에 없는 사실 삽입 / 숫자 변경 / 가짜 출처)** → 즉시 슬롯 폐기 (`failed`). 추측 금지. log_metadata는 호출 (plan §19.5).
2. **본문 중복 (같은 형식 복제)** → 즉시 슬롯 폐기. revised_data로 수정 X — 슬롯 자체가 가치 없음.
3. **§23 위반** → 표현 제거/순화 1회 시도 (`revised_data` 채워서 반환) → 그래도 위반이면 폐기.
4. **title 통째 복붙** → `revised_data`에 직관 합성된 title 채워서 반환 (자동 수정).

## 출력
```yaml
passed: bool
issues: list[str]   # 위반 사유 목록 (한국어)
revised_data: dict | null   # 자동 수정 시도 결과 (§23만)
```
