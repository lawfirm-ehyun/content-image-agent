# 이현 블로그 이미지 에이전트 — Plan (v1.6.4 다이어트)

> 노션 콘텐츠에 자동으로 이미지 카드 박는 에이전트.
>
> 압축 룰 / 절대 룰 → [CLAUDE.md](CLAUDE.md)
> 운영 계약 / Phase 게이트 → [AGENT_GUIDE.md](AGENT_GUIDE.md)
> 사실/스펙 디테일 → [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)
> Changelog v0.1~v1.6.3 / archive 카드 / paper-only 가드 → [plan_history.md](plan_history.md)

---

## 1. 한 줄 정의

노션 콘텐츠 DB `이미지 필요` 페이지 → LLM이 슬롯 결정 → 카드 자동 생성 + 노션 inline 삽입 + status 변경.

진화 축은 **카드 종류 하나만**. 나머지 (가드, cap, 인프라, 메서드)는 stable.

## 2. 절대 룰

1. **사실 정확성 #1** — 본문에 없는 사실/숫자/주체 X. 추측·환각·가짜 출처 X.
   - **사실 그 자체** (숫자 / values / labels / point_labels / source / messages.text / excerpt): 1자도 변경 X.
   - **라벨링·재표현** (title / headers / cells / scene / mood): 본문 사실 안에서 직관 합성 OK.
2. **변호사법 §23** — 절대성/마케팅 과장/시간 압박/비교 광고 표현 검출 시 슬롯 폐기. 키워드 master는 `tools/compliance/keywords.py`.
3. **모바일 가독성 40px+** — 카드 본문 텍스트 최소 40px (1200px 캔버스, 노션 모바일 30% 축소 시 ~12px 보장). 출처/메타는 32px.
4. **AI prompt = 자연어** (v1.6.2) — 픽셀/hex/CSS 토큰 over-constraint 금지. 텍스트 사실 필드만 `exact_korean_strings`로 엄격 명시.

## 3. MVP 흐름

```
[fetch "이미지 필요" 페이지]
        ↓
[LLM analyze: 슬롯 결정 — slot_selection.md 룰 기반]
        ↓
[for each slot]
        ↓
  ┌──── [review_input: 본문 일치 + §23 검사] ────┐
  │                                              │
  │   template path                AI path       │
  │   (chart / table /             (illustration /
  │    timeline / key_points)       kakao_dialogue)
  │        ↓                            ↓        │
  │   Playwright render          gpt-image API   │
  │        ↓                            ↓        │
  │      PNG → WebP                     ↓        │
  └─────────────┬────────────────────────────────┘
                ↓
[Notion file_upload → image block 삽입]
                ↓
[로그 DB row 기록]
                ↓
[status: "이미지 필요" → "발행 필요"]
```

진입점:
- 수동: `uv run python orchestrator.py` (`orchestrator.main()` → `process_database()` 블로그 + 웹 순차)
- 단건: `uv run python scripts/test_phase1.py <page_id> --source <블로그|웹>`
- cron: `.github/workflows/cron.yml` (현재 workflow_dispatch만, schedule 미가동)

## 4. 카드 카탈로그 (활성 7종)

| 카드 | 종류 | When | 상세 |
|---|---|---|---|
| `simple_table` | 정보형 template | 줄글 enumeration, 2-3 컬럼 표 데이터, 조건→결과 매핑 | [skill](skills/image_types/simple_table.md) |
| `chart` (line/bar/donut/pie) | 정보형 template | 시계열 추이(line) / 카테고리 비교(bar) / 분포(donut·pie) | [skill](skills/image_types/chart.md) |
| `comparison_table` | 정보형 template | 법적 절차/유형 비교 (협의 vs 재판). 다른 법무법인 비교 X (§23) | [skill](skills/image_types/comparison_table.md) |
| `key_points_card` | 정보형 template | 핵심 N가지 / 준비 서류 / 체크리스트 (3-5개) | [skill](skills/image_types/key_points_card.md) |
| `timeline` | 정보형 template | 4-6 순차 단계 (법률 절차 / 소송 흐름) | [skill](skills/image_types/timeline.md) |
| `illustration` | 감성형 AI instant | 도입부 사연/분위기 (라인 일러스트 단일 스타일) | [skill](skills/image_types/illustration.md) |
| `kakao_dialogue` | 감성형 AI thinking | 본문 카톡 대화 시나리오 재현 | [skill](skills/image_types/kakao_dialogue.md) |

**페이지당 mix**: 정보형 1-2 + 감성형 1-2 권장. 콘텐츠 종속 (강제 X). 금지 — 감성형만 / 같은 카드 3연속 / kakao 2개+.

**카드 카테고리별 사실 정확성**:
- 정보형 + kakao_dialogue: 본문 1자 변경 X (절대 룰 #1 엄격)
- illustration: scene/mood는 합성 OK. 이미지 안 텍스트 0 강제.

**Phase 4 검토 archive** (운영 데이터로 결정): `stat_highlight` (v1.5 정의 보존), `document_excerpt` (v1.5 정의 보존), `webtoon`, `app_ui_mockup`. spec → [plan_history.md](plan_history.md).

## 5. 활성 운영 가드 (5개 카테고리)

| 가드 | 코드 위치 | 사상 |
|---|---|---|
| **멱등성 + page try/except** | `orchestrator.py` (`get_logged_page_ids`, `process_database` try/except) | 동일 page_id 재처리 자동 skip + page-level 실패는 다음 페이지 진행 |
| **block UUID 검증** | `tools/notion/insert_image_block.py:_verify_ancestor` | LLM 환각으로 다른 페이지에 이미지 박힘 차단 |
| **API rate limit backoff** | `tools/notion/_retry.py` (Notion) + `tools/image/gpt_image_2.py` (OpenAI, tenacity) | 429/5xx 자동 지수 재시도 + 페이지 사이 0.5s sleep |
| **비용 cap (페이지/런/슬롯/analyze/review)** | `tools/limits.py` + `tools/budget.py` | RunBudget 누적, cap 초과 시 즉시 break + 슬롯 폐기 |
| **§23 컴플라이언스** | `tools/compliance/keywords.py` (1차 regex) + `tools/llm/review.py` (2차 LLM) | LLM 호출 전 키워드 차단 (호출당 $0.30 절약) + 본문 일치 + §23 LLM 재검토 |
| (보조) 렌더 안전 검증 | `tools/render/template_render.py` `wait_for_function` + `tools/llm/analyze_content.py:_compress_for_analyze` + 슬롯 0개/review 폐기 로그 | Chart.js·Pretendard 로드 검증, 본문 길이 초과 시 압축 fallback, 폐기 케이스 로그 기록 |

미구현 paper-only 가드 (cron 무인 가동 시 추가 검토) → [plan_history.md](plan_history.md) §2.

## 6. 비용 cap (v1.6.3 기준)

| 상수 (`tools/limits.py`) | 값 | 의미 |
|---|---|---|
| `PER_PAGE_CAP_USD` | $2.50 | 한 페이지 처리 총 비용 한도. 초과 시 페이지 break. |
| `PER_RUN_CAP_USD` | $8.00 | 한 cron 실행 누적 한도. 5건 × 평균 $1.20-1.60. |
| `PER_SLOT_COST_CAP_USD` | $0.30 | 슬롯 1개 누적 비용 한도 (gpt-image thinking 변동성 대비). |
| `ANALYZE_BUDGET_USD` | $0.80 | analyze_content LLM 호출 한도. cache 47K-54K + output 21K 반영. |
| `REVIEW_BUDGET_USD` | $0.30 | 슬롯별 review_input 호출 한도. |

**Phase 4 안정화 목표**: PER_PAGE $1.20 복귀 (analyze prompt 슬림 + slot_selection 다이어트 후).

**페이지당 평균 비용** (실측 + 예측):
- Phase 2 (정보형만): ~$0.40-0.80
- Phase 3 (정보 + 감성 mix): ~$0.70-1.00 (5/12 e2e 1페이지 4슬롯 $0.96 — illustration 포함)
- 월 비용 (40편 기준): ~$28-40

**비용 분리 추적**: `RunBudget.anthropic_usd` / `openai_usd` 별도 (gpt-image 단가 변동성 대비).

## 7. 카드 추가 절차 (30분 가이드)

진화 축. 새 카드 1종 추가 시 다음 4단계로 끝남:

1. **`skills/image_types/<name>.md` 작성** — When / Generation method / Variables / Style / Quality criteria. 자연어로.
2. **렌더 path 추가**:
   - **template**: `templates/<name>.html` 작성 + `tools/render/template_render.py` 분기 1개 (이미 generic하면 추가 불필요)
   - **AI**: `tools/render/ai_render.py`에 `_build_<name>_prompt()` 함수 1개 추가 + `render_ai_card` 분기 1개
3. **`orchestrator.SUPPORTED_TYPES`에 `<name>` 추가** (line 50). AI면 `AI_CARD_TYPES`에도.
4. **`orchestrator._render_slot`에 분기 1개 추가** (필요시 schema 검증 포함).

추가 작업 (선택):
- `reference_library/<name>/` 시드 1-2장 (AI 카드 톤 합의용)
- 로그 DB `타입` select 옵션은 첫 trigger 시 자동 생성 (5/12 검증됨)

**LLM은 자동으로 새 카드 trigger** — `slot_selection.md` 룰만 작성하면 됨. 별도 코드 등록 없음.

## 8. 기술 스택

Python 3.12 / uv / Playwright (Chromium-headless-shell) / Chart.js CDN / Pretendard 1.3.9 / notion-client 3.0 (multi-source DB 자동) / Claude Sonnet 4.6 (bundled `claude.exe` subprocess 호출, claude-agent-sdk 우회) / **OpenAI `gpt-image-2-2026-04-21`** (ENV `OPENAI_IMAGE_MODEL_INSTANT/THINKING`로 override) / WebP 후처리 (Pillow lossless).

## 9. 인프라

| 파일 | 역할 |
|---|---|
| `orchestrator.py` | cron 진입점 + page/slot 처리 흐름 + try/except |
| `tools/llm/analyze_content.py` | LLM 슬롯 결정 (slot_selection.md inject) |
| `tools/llm/review.py` | 슬롯 input 본문 일치 + §23 검사 |
| `tools/render/template_render.py` | HTML + Playwright 렌더 |
| `tools/render/chart_render.py` | Chart.js sub_type 4종 분기 |
| `tools/render/ai_render.py` | gpt-image 호출 wrapper (illustration / kakao) |
| `tools/image/gpt_image_2.py` | OpenAI client + tenacity backoff + 에러 sanitize |
| `tools/image/webp_converter.py` | PNG → WebP (lossless) |
| `tools/notion/*` | fetch / upload / insert / status / log + retry wrapper |
| `tools/compliance/keywords.py` | §23 키워드 regex master |
| `tools/limits.py` | 비용/타임아웃/모델 상수 단일 source |
| `tools/budget.py` | RunBudget (anthropic/openai 분리 누적) |

## 10. 미결정 사항

| 항목 | 결정 시점 |
|---|---|
| cron schedule 활성화 (workflow_dispatch → schedule) | 운영자 검수 부담 결정 후 |
| chatgpt-image-latest 비교 | OpenAI organization verification 완료 후 (15분 propagate) |
| gpt-image-1.5 콘텐츠별 라우팅 | 5/12 비교에서 라인 일러스트 톤 최고였음. 운영 데이터로 결정. |
| kakao_dialogue OCR Levenshtein 검증 | kakao 실제 trigger 시 추가 (현재 0건) |
| Phase 4 검토 카드 (stat_highlight / document_excerpt / webtoon / app_ui_mockup) 활성화 | 운영 데이터 + 콘텐츠 적합도 |
| 페이지 cap $1.20 복귀 (Phase 4) | analyze prompt 슬림 + slot_selection 다이어트 후 |
| 실패 알림 채널 (이메일 → Slack/Discord) | Phase 4 |

## 11. 사용자 사전 작업 체크리스트

### 디자인 자산
- [x] figma 디자인 시스템 정돈
- [ ] 이현 로고 svg/png (선택)

### Notion 환경
- [x] Notion integration 발급
- [x] 블로그 / 웹 / 로그 DB ID 확보 (`.env`)
- [x] 3개 DB read + write integration 권한
- [x] 콘텐츠 DB status 옵션: `이미지 필요`, `발행 필요`, `이미지 작업 중`

### API 계정
- [x] Anthropic API key
- [x] OpenAI API key + 사용 한도 알림 ($40/월 권장)
- [x] GitHub secret 등록

### 시드 자산
- [x] `reference_library/kakao_dialogue/` 시드 (kakao talk.webp)
- [ ] `reference_library/illustration/` 라인 일러스트 시드 (운영하면서 좋은 결과물 1-2장 저장 권장)

### 추가 옵션
- [ ] OpenAI organization verification (`chatgpt-image-latest` 사용)
- [ ] 노션 로그 DB legacy select 옵션 정리 (`table_simple` / `table_comparison` 제거, `출처` 영문 `web`/`blog` 제거 — 한글 통일)

---

## Changelog

- **v1.6.4** (2026-05-12): 이미지 모델 5종 비교 + default `gpt-image-2-2026-04-21` 채택
  - **OpenAI 가용 모델 9종 발견**: `chatgpt-image-latest` (org verification 필요), `gpt-image-1`, `gpt-image-1-mini`, `gpt-image-1.5`, `gpt-image-2`, `gpt-image-2-2026-04-21`, `sora-2`, `sora-2-pro`, `dall-e-2/3`.
  - **5종 라인 일러스트 비교** (동일 prompt, 1024x1024 medium):
    - `gpt-image-1`: ❌ 한글 텍스트 환각 (§19.16 위반)
    - `gpt-image-1.5`: ★★★★★ 라인 톤·accent·일관성 최고 (Phase 4 검토)
    - `gpt-image-2-2026-04-21`: ★★★ 안정적 (default 채택)
    - `chatgpt-image-latest`: ❌ org verification 필요
  - **default 결정**: `gpt-image-2-2026-04-21` (최신 + 안정). `gpt-image-1.5`는 Phase 4 콘텐츠별 라우팅 검토.
  - **`.env` ENV**: `OPENAI_IMAGE_MODEL_INSTANT` / `OPENAI_IMAGE_MODEL_THINKING` = `gpt-image-2-2026-04-21`
  - **plan v1.6.4 다이어트**: 본 파일 2372줄 → 약 300줄. Changelog v0.1~v1.6.3, archive 카드 spec (stat_highlight v1.5, document_excerpt v1.5), paper-only 가드 (§19.10/14/16/17), Phase 2/3 통과 체크리스트 모두 [plan_history.md](plan_history.md)로 이관. 활성 plan은 사상·원칙·MVP 흐름·카드 카탈로그·활성 가드·비용 cap·카드 추가 절차만 유지.

이전 changelog (v0.1 ~ v1.6.3) → [plan_history.md](plan_history.md) §4
