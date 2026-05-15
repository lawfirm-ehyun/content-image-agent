"""skills/visual_styles/<name>.md 디렉터리 scan + frontmatter/prompt_template 로드.

Phase 4.2 (plan §14.2/§14.6) 신설. ai_render._build_ai_visual_prompt 와
analyze_content (감성형 매칭 prompt 합성) 양쪽에서 공유.

Frontmatter 스키마 (필수 6 + 선택 3, docs/visual_styles_library_v1.md §1.1-1.2):
  필수: name / tone / use_when / aspect_ratio / text_rule / quality
  선택: reference_dir / accent_target_default

본문 구조:
  - YAML frontmatter (--- 로 감싸짐)
  - `## prompt_template` 섹션의 첫 fenced ``` block 내용 = prompt_template

설계:
  - **runtime SOT는 skill md** — docs/visual_styles_library_v1.md는 Plan-phase 인덱스.
    drift 시 skill md 우선 (CLAUDE.md drift 룰 #7).
  - **strict 검증** — 필수 필드 누락 / aspect_ratio enum 위반 / fenced block 부재 시
    즉시 ValueError. silent skip 금지 (환각 방지).
  - **list_visual_styles 단건 파싱 실패는 warning + skip** — 다른 스타일 작동 보장.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import yaml

logger = logging.getLogger(__name__)

REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
VISUAL_STYLES_DIR: Final[Path] = REPO_ROOT / "skills" / "visual_styles"

REQUIRED_FRONTMATTER_FIELDS: Final[frozenset[str]] = frozenset({
    "name", "tone", "use_when", "aspect_ratio", "text_rule", "quality",
})
ALLOWED_ASPECT_RATIOS: Final[frozenset[str]] = frozenset({
    "1024x1024", "1024x1536", "1536x1024",
})
ALLOWED_TEXT_RULES: Final[frozenset[str]] = frozenset({"zero", "factual"})
ALLOWED_QUALITIES: Final[frozenset[str]] = frozenset({"medium", "high"})


@dataclass(frozen=True)
class VisualStyle:
    """skills/visual_styles/<name>.md 로드 결과."""

    name: str
    tone: str
    use_when: str
    aspect_ratio: str  # "1024x1024" / "1024x1536" / "1536x1024"
    text_rule: str  # "zero" / "factual"
    quality: str  # "medium" / "high"
    prompt_template: str
    reference_dir: str | None = None
    accent_target_default: str | None = None


_FRONTMATTER_RE: Final = re.compile(r"^---\s*\r?\n(.+?)\r?\n---\s*\r?\n(.*)$", re.DOTALL)
_PROMPT_TEMPLATE_RE: Final = re.compile(
    r"##\s*prompt_template\s*\r?\n.*?\r?\n```(?:[a-zA-Z0-9_-]+)?\s*\r?\n(.+?)\r?\n```",
    re.DOTALL,
)


def _parse_markdown(md_path: Path) -> VisualStyle:
    """Markdown 파일 파싱 → VisualStyle. 스키마 검증 포함."""
    content = md_path.read_text(encoding="utf-8")
    fm_match = _FRONTMATTER_RE.match(content)
    if not fm_match:
        raise ValueError(
            f"visual_style {md_path.name}: YAML frontmatter (---) 없음"
        )
    fm_text, body = fm_match.groups()
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError as e:
        raise ValueError(
            f"visual_style {md_path.name}: frontmatter YAML 파싱 실패 — {e}"
        ) from e
    if not isinstance(fm, dict):
        raise ValueError(
            f"visual_style {md_path.name}: frontmatter는 dict 여야 함 (받은 타입: {type(fm).__name__})"
        )

    missing = REQUIRED_FRONTMATTER_FIELDS - set(fm.keys())
    if missing:
        raise ValueError(
            f"visual_style {md_path.name}: 필수 필드 누락 — {sorted(missing)}"
        )

    if fm["aspect_ratio"] not in ALLOWED_ASPECT_RATIOS:
        raise ValueError(
            f"visual_style {md_path.name}: aspect_ratio={fm['aspect_ratio']!r} — "
            f"허용: {sorted(ALLOWED_ASPECT_RATIOS)}"
        )
    if fm["text_rule"] not in ALLOWED_TEXT_RULES:
        raise ValueError(
            f"visual_style {md_path.name}: text_rule={fm['text_rule']!r} — "
            f"허용: {sorted(ALLOWED_TEXT_RULES)}"
        )
    if fm["quality"] not in ALLOWED_QUALITIES:
        raise ValueError(
            f"visual_style {md_path.name}: quality={fm['quality']!r} — "
            f"허용: {sorted(ALLOWED_QUALITIES)}"
        )

    pt_match = _PROMPT_TEMPLATE_RE.search(body)
    if not pt_match:
        raise ValueError(
            f"visual_style {md_path.name}: '## prompt_template' 섹션의 "
            f"fenced ``` block 없음"
        )
    prompt_template = pt_match.group(1).strip()

    return VisualStyle(
        name=str(fm["name"]),
        tone=str(fm["tone"]),
        use_when=str(fm["use_when"]),
        aspect_ratio=str(fm["aspect_ratio"]),
        text_rule=str(fm["text_rule"]),
        quality=str(fm["quality"]),
        prompt_template=prompt_template,
        reference_dir=(str(fm["reference_dir"]) if fm.get("reference_dir") else None),
        accent_target_default=(
            str(fm["accent_target_default"]) if fm.get("accent_target_default") else None
        ),
    )


def load_visual_style(name: str, base_dir: Path = VISUAL_STYLES_DIR) -> VisualStyle:
    """단일 스타일 로드. 매칭 실패 시 ValueError (환각 방지 — silent fallback 금지)."""
    md_path = base_dir / f"{name}.md"
    if not md_path.is_file():
        raise ValueError(
            f"visual_style {name!r} 없음 — {md_path} 존재하지 않음"
        )
    style = _parse_markdown(md_path)
    if style.name != name:
        raise ValueError(
            f"visual_style {md_path.name}: frontmatter name={style.name!r} "
            f"파일명과 불일치"
        )
    return style


def list_visual_styles(base_dir: Path = VISUAL_STYLES_DIR) -> list[VisualStyle]:
    """디렉터리 scan → 정상 파싱되는 스타일만 리스트 반환.

    파싱 실패 1건은 warning 로그 + skip — 다른 스타일 작동 보장.
    """
    if not base_dir.is_dir():
        logger.warning("visual_styles dir 없음: %s", base_dir)
        return []
    styles: list[VisualStyle] = []
    for md_path in sorted(base_dir.glob("*.md")):
        try:
            style = _parse_markdown(md_path)
        except ValueError as e:
            logger.warning("visual_style 로드 실패 (skip): %s — %s", md_path.name, e)
            continue
        styles.append(style)
    return styles
