# kakao_dialogue (v1.6.2)

본문에 **의뢰인-변호사 카톡 대화 시나리오**가 있을 때 대화 재현 카드.

## When to use
- 본문에 **의뢰인-변호사 채팅 시나리오**가 직간접 형태로 있음 ("Q: ~ A: ~", "의뢰인이 물어봅니다: ~")
- 본문 톤이 "친구 같은 상담" / "쉬운 진입" / "익숙한 매체" 강조할 때
- 4-8 메시지 분량 (왕복 2-4회). 더 길면 글로 풀어쓰기 권장.
- **금지**: 본문에 대화 시나리오가 없는데 카톡으로 만들어내기 (환각). 절차/체크리스트는 timeline/key_points_card.

## Generation method
AI (gpt-image thinking, quality=high) — ~$0.25/장 @ 1024x1536. 텍스트 정확성 필수라 thinking 모드.

## Style (v1.6.1 reference 기반)
- 자연어 키워드: **Korean KakaoTalk chat screenshot, Samsung Android style**. Chat area only (no status bar, no keyboard). Header at top with back arrow, title, search/menu icons. Yellow self-bubbles aligned right (no avatar). White other-bubbles aligned left with pastel circular avatars. Light blue chat background, Korean Pretendard font feel.
- reference: `reference_library/kakao_dialogue/` (`kakao talk.webp` 기반 시드)

## Variables
- `title` (str, 옵션): 카드 상단 라벨. 예: "의뢰인의 첫 질문, 변호사의 답변"
- `messages` (list, 필수): `[{sender_label, text, time?}, ...]` — **본문 대화 1자 변경 X**
  - `sender_label`: "의뢰인" / "변호사" / "상담사" 등 본문 인용대로
  - `text`: 메시지 본문 그대로
  - `time` (옵션): "오전 9:10" 형식
- `source` (str, 옵션): "본 사연은 실제 의뢰인 사연을 각색했습니다" 등
- `footnote` (str, 옵션)

## Data validation (CRITICAL — 사실 정확성 절대 룰 #1)
- **messages[i].text는 본문 1자도 변경 X** — AI 환각 절대 금지.
- title은 본문 사실 안에서 합성 OK.
- source는 본문 표기 그대로 또는 운영 기본 문구.
- image_review vision OCR로 카톡 버블 텍스트 추출 → messages[i].text와 Levenshtein distance ≤ 2 검증. 초과 시 retry 1회 → 그래도 초과면 슬롯 폐기 (§19.11).
- 변호사법 §23 검사 — "100% 승소" / "유일한" 같은 표현이 메시지 안에 있으면 슬롯 폐기 (`tools/compliance/keywords.py` 1차 regex pass).

## Reference images
- `reference_library/kakao_dialogue/` — `kakao talk.webp` 기반 사용자 시드 1-2장 (카톡 UI 톤 합의).

## Quality criteria
- [ ] messages OCR이 본문과 1:1 (≤ 2자 편집 거리)
- [ ] sender 좌우 정렬 정확 (의뢰인=우측 yellow, 변호사·상대=좌측 white)
- [ ] 카톡 UI 톤 (특히 메시지 버블 모서리·색·아바타)
- [ ] 채팅 영역만 (status bar/키보드 X)
- [ ] 변호사법 §23 표현 0
- [ ] 가독성 36px+ (메시지)
