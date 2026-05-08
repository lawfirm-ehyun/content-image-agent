# Slot Selection

본문 블록을 분석해서 각 H2 섹션마다 어떤 image_type 슬롯을 넣을지 결정한다.
0개도 OK이지만 이현 콘텐츠는 보통 2000자+이라 0개 결정은 거의 없을 것.

## 결정 룰 (Phase 1)

본문에 다음 패턴이 있으면 해당 카드 후보:
- **표 형식 데이터** (구분/항목/값) → `simple_table` ← **Phase 1 활성**
- **시계열 추이** (연도별 변화, 2개 이상 포인트) → `chart` sub_type=`line` ← **Phase 1 활성**

> 다른 패턴 (카테고리 비교 / 분포 / 이현 vs 경쟁사 / 핵심 N가지 / 단일 숫자 강조 / 판례 인용)은 **Phase 1엔 슬롯 결정 X** — 카드 미구현. Phase 2/3에서 점진 활성화.

## Phase 1 폴백
- chart line인데 데이터 포인트 1개 → 슬롯 결정 X (stat_highlight Phase 3)
- 통계 다수면 chart line 우선

## 위치 결정
- 해당 정보가 등장하는 H2 섹션의 **첫 단락 직후**
- 첫 단락이 50자 미만이면 다음 단락 후

## 슬롯 개수
- 페이지당 1~3개 권장. 4개 초과는 본문 매우 길거나 데이터 다수일 때만.
- 슬롯 0개도 OK (콘텐츠 짧거나 시각화할 데이터 없을 때). 단 추적 위해 로그 DB에 1행 기록 필수 (plan §19.6 — `타입=없음` select 옵션 사용).

## 출력 형식 (orchestrator가 파싱)

### 카드 제목(`title`) 룰 — **필수**
모든 슬롯의 `extracted_data.title`은 **반드시** 채울 것. 비우지 말 것.
- 우선순위 1: 슬롯이 속한 H2/H3 본문 헤딩 그대로 (예: "정보통신망법 제70조 처벌 기준")
- 우선순위 2: 직전 단락의 핵심 명사구 (한 줄 요약, 명사 마침)
- 의역·추측 금지. 본문에 없는 단어 X.

### 출력 예시
```yaml
image_slots:
  - type: chart
    sub_type: line
    position_after_block_id: <block_uuid>
    extracted_data:
      title: "마스터스 우승 상금 추이"          # 본문 H2 그대로
      labels: ["1985", "1990", "..."]
      values: [19, 34, 60]
      point_labels: ["19억 원", "34억 원", "60억 원"]
      source: "출처: Golf Digest, 2025"
  - type: simple_table
    position_after_block_id: <block_uuid>
    extracted_data:
      title: "정보통신망법 제70조 처벌 기준"     # 본문 H2 그대로 — 절대 비우지 말 것
      headers: ["구분", "내용"]
      rows: [["트랙 I", "1인당 최대 800만 원"]]
      highlight_first_col: true
```

## 데이터 정확성 (절대 룰 #1)
본문에 명시된 숫자/텍스트만 사용. 1자도 추측·의역 X. 본문에 없는 출처 만들지 마라.
