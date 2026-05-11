# 이현 비주얼 가이드 v1

## 톤
- 차분함과 친근함 사이 (8:2)
- 신뢰감 있되 위압적이지 않음
- "보통의 사람을 위한 로펌" 포지셔닝
- 토스피드 본문 자료의 미니멀 톤 차용

## 컬러 룰

### 기본 원칙
- 흑백(neutral) + `brand.primary` (#a91c51) 조합으로 90% 커버
- **monochromatic 원칙**: 차트 multi-series는 같은 plum 계열의 채도 변형으로만 구성. 이질적 색(파랑/초록/노랑 등) 추가 X. 토스피드의 "navy → light blue" 패턴을 plum으로 차용.
- neutral은 Tailwind Zinc (true neutral) — brand wine-magenta와 언더톤 충돌 없게
- **금지**: 다채로운 컬러 팔레트, 레인보우 톤, 그라데이션

### `brand.primary` (#a91c51) 사용처 — 강조 포인트로만
- 표의 한 컬럼/행 (key column, 강조 row)
- 차트의 메인 라인 또는 첫 번째 항목
- 강조 텍스트 (핵심 수치, 키워드)

### 차트 multi-series 컬러 매핑
- 1계열: `chart.primary` (#a91c51)
- 2계열: `chart.secondary` (#c98497) — primary의 desaturated 톤
- 3계열 이상 fallback: `chart.tertiary` (#a1a1aa) — mid-gray
- `chart.accent_warm` (#d97706): 한 차트에 **강조선 1개**까지만. multi-series 컬러로는 사용 금지.

### 면적 큰 강조
- stacked bar 한 칸, 큰 박스 강조 영역 등 면적이 클 때는 `brand.primary_dark` (#7d1239) 사용. primary 그대로 면적에 깔면 채도(71%)가 시각 부담.
- 강조 영역 배경: `brand.primary_soft` (#fdf2f5)

### 거의 안 쓰는 컬러
- `accent.success` / `accent.warning` — 체크 표시 등 한정

## 타이포 룰
- Pretendard 단일 폰트
- **모바일 가독성 절대 룰: 모든 본문 최소 28px** (1200px wide 카드 기준)
- 출처/메타는 20px까지 OK
- 줄 간격 본문 1.5, 제목 1.3

## 레이아웃 룰
- 여백 충분히 (카드 padding 최소 64px)
- 텍스트 정렬: 좌측 정렬 기본 (제목/본문)
- 데이터 (숫자, 비용): 우측 정렬 또는 중앙 정렬

## 금지사항
- 망치/저울/정의의 여신상 클리셰 (법조 일반 묘사)
- 외국 법정 묘사
- 시간 압박/공포 마케팅 카피 ("당신만을 위한", "지금 아니면", "골든타임")
- 클립아트 풍 일러스트
- 부정확한 데이터 (본문 숫자 다른 값으로 변형)
- 가짜 출처

## 권장사항
- 한국 맥락 (필요시)
- 차분한 색감 우선
- 출처 표기 (차트, 통계는 반드시)
- 텍스트는 본문 그대로 (의역 X)

## 변호사법 §23 컴플라이언스 (이미지 안 텍스트도 적용)

> 키워드 master는 **`tools/compliance/keywords.py`** (plan §19.7, §20.1).
> 본 가이드는 LLM/사람 검토 reasoning만 담당. 키워드 신설/수정은 코드 master에서.

이미지 텍스트(인포그래픽/차트/표/카드)도 본문과 동일하게 §23 4 카테고리로 검사:

- **절대성 표현** — "최고", "유일", "100% 승소" 같은 superlative 클레임.
- **마케팅 과장** — "당신만을 위한", "특별 혜택" 같은 희귀성/배타성.
- **시간 압박** — "지금 아니면", "마지막 기회" 같은 긴급성 유도.
- **비교 광고** — "타 로펌", "다른 법무법인" 명시 비교.

### 검사 시점
- prompt_review (생성 전): `tools/llm/review.py`가 1차 regex pass로 즉시 폐기, 그 외는 LLM 맥락 판단.
- image_review (생성 후, Phase 2 §20.4): vision OCR로 이미지 텍스트 추출 후 동일 `check_keywords` 호출.
