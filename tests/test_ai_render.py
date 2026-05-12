"""ai_render prompt builder + 분기 단위 테스트.

v1.6.1 신설 (plan §12 P3.2). 실제 OpenAI 호출은 mock.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from tools.image.gpt_image_2 import ImageResult
from tools.render.ai_render import (
    _build_illustration_prompt,
    _build_kakao_prompt,
    render_ai_card,
)


# ============================================================================
# illustration prompt
# ============================================================================


def test_illustration_prompt_basic():
    data = {
        "scene": "야간 공원에서 음주측정 받는 30대 직장인",
        "mood": "당혹스러움",
    }
    prompt = _build_illustration_prompt(data)
    assert "Korean editorial line illustration" in prompt
    assert "야간 공원에서 음주측정 받는 30대 직장인" in prompt
    assert "당혹스러움" in prompt
    # accent_target 없으면 default 문구
    assert "wine-magenta accent on a key element" in prompt
    # 텍스트 환각 차단 명시
    assert "No text" in prompt


def test_illustration_prompt_with_accent_target():
    data = {
        "scene": "거실에서 형제 둘이 유산 서류 보며 다투는 모습",
        "mood": "긴장",
        "accent_target": "서류 표지",
    }
    prompt = _build_illustration_prompt(data)
    assert "서류 표지 highlighted in wine-magenta" in prompt
    # default 문구는 안 나옴
    assert "wine-magenta accent on a key element" not in prompt


def test_illustration_prompt_missing_scene_raises():
    with pytest.raises(ValueError, match="scene/mood 필수"):
        _build_illustration_prompt({"mood": "당혹스러움"})


def test_illustration_prompt_missing_mood_raises():
    with pytest.raises(ValueError, match="scene/mood 필수"):
        _build_illustration_prompt({"scene": "장면"})


def test_illustration_prompt_blank_scene_raises():
    with pytest.raises(ValueError, match="scene/mood 필수"):
        _build_illustration_prompt({"scene": "   ", "mood": "당혹스러움"})


# ============================================================================
# kakao_dialogue prompt
# ============================================================================


def test_kakao_prompt_basic():
    data = {
        "title": "의뢰인의 첫 질문",
        "messages": [
            {"sender_label": "의뢰인", "text": "변호사님, 어떻게 해야 하나요?", "time": "오전 9:10"},
            {"sender_label": "변호사", "text": "우선 상담부터 받으시는 게 좋습니다.", "time": "오전 9:12"},
        ],
    }
    prompt = _build_kakao_prompt(data)
    assert "Korean KakaoTalk chat screenshot" in prompt
    assert "의뢰인의 첫 질문" in prompt
    # 메시지 텍스트 literal 인용 (OCR 정확성 확보)
    assert "변호사님, 어떻게 해야 하나요?" in prompt
    assert "우선 상담부터 받으시는 게 좋습니다." in prompt
    # sender label literal
    assert '"의뢰인"' in prompt
    assert '"변호사"' in prompt
    # 시각 literal
    assert "오전 9:10" in prompt


def test_kakao_prompt_title_optional():
    data = {
        "messages": [{"sender_label": "의뢰인", "text": "테스트"}],
    }
    prompt = _build_kakao_prompt(data)
    assert "Korean KakaoTalk chat screenshot" in prompt
    # title 없으면 default 문구
    assert "a short chat title" in prompt


def test_kakao_prompt_empty_messages_raises():
    with pytest.raises(ValueError, match="messages 필수"):
        _build_kakao_prompt({"title": "t", "messages": []})


def test_kakao_prompt_missing_messages_raises():
    with pytest.raises(ValueError, match="messages 필수"):
        _build_kakao_prompt({"title": "t"})


def test_kakao_prompt_message_without_time():
    data = {
        "messages": [{"sender_label": "의뢰인", "text": "시각 없음 메시지"}],
    }
    prompt = _build_kakao_prompt(data)
    assert "시각 없음 메시지" in prompt
    # time이 없으면 ' at "..."' 절 없음
    assert "시각 없음 메시지" in prompt


# ============================================================================
# render_ai_card 분기 + 파일 저장
# ============================================================================


@pytest.mark.asyncio
async def test_render_ai_card_illustration(tmp_path):
    out = tmp_path / "test_illu.png"
    mock_result = ImageResult(
        png_bytes=b"\x89PNG\r\n\x1a\nfake",
        cost_usd=0.042,
        model_id="gpt-image-1",
        size="1024x1024",
        quality="medium",
    )
    with patch(
        "tools.render.ai_render.generate_instant",
        new=AsyncMock(return_value=mock_result),
    ) as mock_gen:
        result = await render_ai_card(
            "illustration",
            {"scene": "장면", "mood": "분위기"},
            out,
        )
    assert result is mock_result
    assert out.exists()
    assert out.read_bytes() == b"\x89PNG\r\n\x1a\nfake"
    # generate_instant이 medium quality로 호출됐는지
    call_kwargs = mock_gen.call_args.kwargs
    assert call_kwargs["quality"] == "medium"
    assert call_kwargs["size"] == "1024x1024"


@pytest.mark.asyncio
async def test_render_ai_card_kakao(tmp_path):
    out = tmp_path / "test_kakao.png"
    mock_result = ImageResult(
        png_bytes=b"kakao_png_bytes",
        cost_usd=0.25,
        model_id="gpt-image-1",
        size="1024x1536",
        quality="high",
    )
    with patch(
        "tools.render.ai_render.generate_thinking",
        new=AsyncMock(return_value=mock_result),
    ) as mock_gen:
        await render_ai_card(
            "kakao_dialogue",
            {"messages": [{"sender_label": "의뢰인", "text": "테스트"}]},
            out,
        )
    assert out.exists()
    call_kwargs = mock_gen.call_args.kwargs
    assert call_kwargs["quality"] == "high"
    assert call_kwargs["size"] == "1024x1536"


@pytest.mark.asyncio
async def test_render_ai_card_unsupported_raises(tmp_path):
    out = tmp_path / "test.png"
    with pytest.raises(ValueError, match="미지원 card_type"):
        await render_ai_card("nonexistent", {}, out)
