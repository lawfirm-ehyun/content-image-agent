"""변호사법 §23 키워드 1차 regex pass 단위 테스트 (plan §19.7)."""
from __future__ import annotations

from tools.compliance.keywords import Category, check_keywords, format_violations

# --- 절대성 ---

def test_absolute_percent_win_rate():
    v = check_keywords("저희는 100% 승소를 보장합니다")
    assert Category.ABSOLUTE in v
    assert any("100" in h for h in v[Category.ABSOLUTE])


def test_absolute_choeigo():
    v = check_keywords("업계 최고의 변호사")
    assert Category.ABSOLUTE in v


def test_absolute_perfect_resolution():
    v = check_keywords("모든 사건 해결을 약속합니다")
    assert Category.ABSOLUTE in v


def test_absolute_jeoldaero_with_outcome_verb_hits():
    v = check_keywords("절대로 보장합니다")
    assert Category.ABSOLUTE in v


def test_absolute_jeoldaero_safe_context_no_hit():
    """'절대로 안전한 운전' — outcome 동사 없으면 false positive 회피."""
    v = check_keywords("절대로 안전한 운전 습관")
    assert Category.ABSOLUTE not in v


def test_absolute_bandeusi_safe_context_no_hit():
    """'반드시 확인하세요' 같은 일반 안내는 false positive 회피."""
    v = check_keywords("계약서를 반드시 확인하세요")
    assert Category.ABSOLUTE not in v


def test_absolute_choeigo_followed_by_eui():
    """'최고의'도 superlative claim — 광고 맥락에서 위반."""
    v = check_keywords("업계 최고의 법무법인")
    assert Category.ABSOLUTE in v


# --- 마케팅 과장 ---

def test_exaggeration_dangsinmaneul():
    v = check_keywords("당신만을 위한 특별한 서비스")
    assert Category.EXAGGERATION in v


def test_exaggeration_special_offer():
    v = check_keywords("이번 주 한정 기회입니다")
    assert Category.EXAGGERATION in v


# --- 시간 압박 ---

def test_time_pressure_now_or_never():
    v = check_keywords("지금 아니면 늦습니다")
    assert Category.TIME_PRESSURE in v


def test_time_pressure_today_no_hit():
    """'오늘 만나요' — 압박 문구 아님."""
    v = check_keywords("오늘 만나요")
    assert Category.TIME_PRESSURE not in v


def test_time_pressure_today_inside():
    """'오늘 안에'는 시간 압박."""
    v = check_keywords("오늘 안에 결정해 주세요")
    assert Category.TIME_PRESSURE in v


# --- 비교 광고 ---

def test_comparative_other_lawfirm():
    v = check_keywords("타 로펌과 달리 저희는 다릅니다")
    assert Category.COMPARATIVE in v


def test_comparative_other_legal_corp():
    v = check_keywords("다른 법무법인보다 빠릅니다")
    assert Category.COMPARATIVE in v


def test_comparative_no_competitor_mention():
    v = check_keywords("저희 사무소의 강점은 신속함입니다")
    assert Category.COMPARATIVE not in v


# --- 통합 ---

def test_clean_text_returns_empty():
    v = check_keywords("이번 사건은 형사 절차에 따라 진행됩니다")
    assert v == {}


def test_multi_category_hits():
    v = check_keywords("100% 승소 보장 — 지금 아니면 늦습니다")
    assert Category.ABSOLUTE in v
    assert Category.TIME_PRESSURE in v


def test_format_violations_empty():
    assert format_violations({}) == ""


def test_format_violations_message_includes_section_23():
    v = check_keywords("100% 승소 보장합니다")
    msg = format_violations(v)
    assert "§23" in msg
    assert "절대성" in msg
