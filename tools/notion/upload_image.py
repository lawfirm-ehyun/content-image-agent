"""Notion File Upload API로 이미지 업로드. file_upload_id 리턴.

Notion 정책 (2026-05 기준):
  - 단일 이미지 ≤ 20MB: single_part 모드 (create + send 한 번).
  - 1시간 안에 page/block에 attach 안 하면 archive됨. 우리 흐름은 즉시 attach (insert_image_block).

content_type 자동 추론: 확장자 → MIME. 미지원 확장자면 호출자가 명시 필요.

retry 정책 (plan §20.1):
  - file_uploads.create는 notion_call (idempotent — 같은 metadata로 재시도해도 새 id 발급).
  - file_uploads.send는 notion_call 제외 — multipart 부분 재업로드 안전 X.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from tools.notion import get_client
from tools.notion._retry import notion_call

_MIME_BY_EXT: dict[str, str] = {
    ".webp": "image/webp",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
}


async def upload_image(file_path: str | Path, *, content_type: str | None = None) -> str:
    """이미지를 Notion에 업로드하고 file_upload_id 리턴.

    file_path    : 업로드할 로컬 파일 경로.
    content_type : MIME. None이면 확장자로 추론. 미지원 확장자면 ValueError.
    """
    path = Path(file_path)

    # content_type 검증 먼저 — 미지원 확장자면 파일 존재 여부와 무관하게 호출자 잘못.
    if content_type is None:
        ext = path.suffix.lower()
        if ext not in _MIME_BY_EXT:
            raise ValueError(
                f"확장자 {ext!r}의 content_type을 자동 추론 못함. 호출 시 명시 필요."
            )
        content_type = _MIME_BY_EXT[ext]

    if not path.exists():
        raise FileNotFoundError(path)

    client = get_client()
    # 1) create — single_part 모드 (≤ 20MB). filename은 노션 UI에 표시되는 이름.
    created = await notion_call(
        client.file_uploads.create,
        mode="single_part",
        filename=path.name,
        content_type=content_type,
    )
    file_upload_id: str = created["id"]

    # 2) send — multipart form. SDK가 (filename, fobj, mime) 튜플을 files 필드로 처리.
    # retry 제외 — multipart 부분 재업로드 안전 X.
    def _send_sync() -> None:
        with path.open("rb") as fobj:
            client.file_uploads.send(
                file_upload_id=file_upload_id,
                file=(path.name, fobj, content_type),
            )

    await asyncio.to_thread(_send_sync)
    # single_part 모드는 complete 호출 불필요 — send 1회로 status="uploaded".
    return file_upload_id
