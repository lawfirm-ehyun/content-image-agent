# timeline

## When to use
법률 절차/소송 진행 흐름 등 **순차 단계가 명확한 본문**. 단계 4-6개 적합.

**적합한 패턴**:
- 이혼 소송 절차 단계 ("소장 접수 → 답변서 → 변론 → 조정 → 판결")
- 상속 분쟁 흐름 ("협의 → 조정 신청 → 심판")
- 형사 절차 ("수사 → 기소 → 재판 → 선고")
- 행정 처리 단계

**부적합한 패턴**:
- 단순 enumeration ("3가지 핵심") → `simple_table` 또는 `key_points_card`
- 동등 비교 (A vs B) → `comparison_table`
- 시계열 숫자 추이 → `chart` line/bar

## Generation method
Template (HTML + Lucide icons + Playwright) — `tools/render/template_render.py("timeline", ...)`

## Card size
default — width 1200px, height auto. 단계 4-6개 기준 ~900-1300px.
- 단계 7개+면 슬롯 분할 권장 (한 화면에 너무 많은 단계 = 인지 부담).
- 단계 3개 이하면 simple_table이 더 적합한 경우 많음.

## Variables
- `title` : str | None — 본문 인접 H2/H3 그대로 (있으면).
- `steps` : list[step] — 단계 객체 배열. 최소 3개, 최대 7개 권장.
  - `label` : str — **필수**. 단계 이름 ("소장 접수", "변론 기일" 등).
  - `description` : str | None — 한 줄 설명 (옵션). 본문 명시 정보만.
  - `duration` : str | None — 소요 기간 ("1-2주", "30일 이내", "약 2개월"). label 옆 inline 표시.
  - `icon` : str | None — Lucide icon 이름 (예: "file-text", "gavel"). None이면 단계 번호 표시.
- `footnote` : str | None — 출처/주석.
- `alt_text` : str — **필수**. 노션 image caption SEO 추천문. 한국어 80자 이하. 패턴: "[주제] [N]단계 절차". 룰은 `skills/meta/slot_selection.md` "alt_text 룰" 참조. (v1.9 plan §13)

## Lucide icon 추천 (법률 절차)
- 서류/제출: `file-text`, `file-pen-line`, `file-search`, `file-check`, `send`, `mail`
- 절차/판결: `gavel`, `scale`, `landmark`
- 당사자/합의: `users`, `handshake`, `user-check`
- 시간/일정: `clock`, `calendar`, `calendar-days`
- 완료/확정: `check-circle`, `shield-check`, `award`

> icon 이름 정확성 확인: https://lucide.dev/icons/ 검색. 없는 이름이면 SVG 미렌더 (마커가 공백) → 단계 번호로 폴백 권장.

## Style (`templates/timeline.html`)
- 단계 marker: 80px 원, brand.primary 배경, white 아이콘 (38px stroke-2.25).
- 단계 사이 세로 line: 2px brand.primary 25% opacity.
- 단계 label: 42px bold neutral.900.
- duration: 32px brand.primary medium, label 옆 inline (`· 1-2주` 패턴).
- description: 40px neutral.700 regular.
- footnote: 32px neutral.500.

## Quality criteria
- [ ] `title` 채워짐 + 본문 인접 H2/H3 일치
- [ ] 본문에 명시된 단계만 사용 (절대 룰 #1 — 환각 단계 X)
- [ ] 단계 4-6개 (3개면 simple_table 검토, 7개+면 분할)
- [ ] duration은 본문 명시 그대로 (추측 X)
- [ ] icon은 단계 내용과 의미적으로 매칭 (예: "판결 선고" → gavel)
- [ ] 변호사법 §23 금지 표현 없음 (label/description 모두 자동 1차 regex pass)
