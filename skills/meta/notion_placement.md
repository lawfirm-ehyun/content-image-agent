# Notion Placement

## 룰
- 슬롯 결정 시 LLM 은 `position_after_block_index` (BLOCKS 순번 idx, 정수) 결정 (slot_selection 단, v1.8.2 — LLM 에 block UUID 미노출)
- `tools/llm/analyze_content.py` 가 idx→block_id 변환해 `position_after_block_id` 로 전달 (orchestrator 인터페이스 불변)
- `tools/notion/insert_image_block.py`로 해당 block 다음에 image block 삽입
- 캡션은 옵션 (차트의 source는 카드 안에 이미 있음, 표는 footnote 안에 있음 → 캡션 빈 문자열로)

## 삽입 플로우
1. `tools/notion/upload_image.py(webp_path)` → `file_upload_id`
2. `tools/notion/insert_image_block.py(parent_id=page_id, after_block_id, file_upload_id)` → 새 block_id
3. `block_id`는 작업 로그의 `입력(JSON)` 안에 포함 (`"notion_block_id": "..."`)

## block_id ancestor 검증 (plan §19.2 — Phase 1 즉시 적용)

**위험**: LLM 이 위치를 환각하거나 다른 페이지 block 을 가리킬 수 있음. v1.8.2 인덱스 전환으로 UUID 환각은 원천 차단됐지만, legacy 출력 수용 path + 코드 버그 가능성이 남으므로 **사후 ancestor 검증은 안전망으로 유지**. `insert_image_block.py`는 `target.parent`로 real_parent 동적 resolve하는데, **다른 페이지의 block parent**일 경우 다른 페이지에 이미지가 박힐 수 있음 (재앙).

**룰**: insert 직전 검증 필수
1. `client.blocks.retrieve(after_block_id)` → target
2. target.parent를 따라 ancestor traversal → page parent 도달까지
3. **그 page_id가 처리 중인 page_id와 일치**해야 함
4. 불일치 시 슬롯 폐기 + issues에 "block_id가 처리 페이지에 없음 (parent={실제_page_id})" 기록 + log_metadata 호출

## 주의
- File Upload는 1시간 안에 attach 안 하면 archive됨 → 업로드 직후 즉시 insert.
- 페이지 자체가 parent. 컬럼/토글 안 위치는 nested block. `insert_image_block.py`가 real_parent 동적 resolve 처리.
- file_upload 고아 (plan §19.10): upload N회 + insert 실패 N회면 file_upload_id가 1시간 뒤 자동 archive (Notion 정책). 비용 누수 X. Phase 2 최적화로 첫 upload만 보존하고 retry는 insert만 재시도.
