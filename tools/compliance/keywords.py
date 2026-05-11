"""변호사법 §23 키워드 master + 1차 regex pass (plan §19.7, §20.1).

설계:
  - 4 카테고리 (절대성 / 마케팅 과장 / 시간 압박 / 비교 광고).
  - 한글 단어 경계는 `\\b` 미지원 → `(?<![가-힣])` lookbehind / `(?![가-힣])` lookahead 사용.
  - 모호한 일반 한국어("절대로", "반드시")는 outcome verb와 함께일 때만 매치.
    → false positive 최소화. 광고 맥락 최종 판단은 LLM 2차 pass에 위임.
  - check_keywords()는 후보 위반을 반환. 즉시 슬롯 폐기가 아니라 LLM이 맥락 판단.
"""
from __future__ import annotations

import re
from enum import StrEnum


class Category(StrEnum):
    ABSOLUTE = "절대성 표현"
    EXAGGERATION = "마케팅 과장"
    TIME_PRESSURE = "시간 압박"
    COMPARATIVE = "비교 광고"


# 한글 단어 경계 helpers.
_BEFORE = r"(?<![가-힣])"
_AFTER = r"(?![가-힣])"


_PATTERNS: dict[Category, list[re.Pattern[str]]] = {
    Category.ABSOLUTE: [
        # "100% 승소", "100%승소", "100 % 승소"
        re.compile(r"\d{2,3}\s?%\s?(승소|성공|해결)"),
        re.compile(_BEFORE + r"최저가" + _AFTER),
        # "최고"는 lookahead 없이 — "최고의 변호사" superlative 잡기 위함.
        # "최고급" 같은 합성어 false positive는 LLM 2차 pass가 맥락 판단.
        re.compile(_BEFORE + r"최고"),
        re.compile(_BEFORE + r"유일(한)?" + _AFTER),
        re.compile(_BEFORE + r"완벽(한)?" + _AFTER),
        # "모든 사건 해결", "모든사건해결"
        re.compile(_BEFORE + r"모든\s*사건\s*해결"),
        # "반드시" + outcome verb. "반드시 확인하세요"는 제외.
        re.compile(_BEFORE + r"반드시\s*(이깁|이긴|승소|해결|성공)"),
        # "절대로" + outcome verb. "절대로 안전한"은 제외.
        re.compile(_BEFORE + r"절대로\s*(보장|이깁|이긴|승소|성공|해결|약속)"),
    ],
    Category.EXAGGERATION: [
        re.compile(_BEFORE + r"당신만(을|의)?\s*위한"),
        re.compile(_BEFORE + r"특별\s*혜택"),
        re.compile(_BEFORE + r"한정\s*기회"),
        re.compile(_BEFORE + r"단\s*한\s*번"),
        re.compile(_BEFORE + r"놓치면\s*안\s*되"),
    ],
    Category.TIME_PRESSURE: [
        re.compile(_BEFORE + r"지금\s*아니면"),
        re.compile(_BEFORE + r"골든타임"),
        re.compile(_BEFORE + r"마지막\s*기회"),
        re.compile(_BEFORE + r"시간이\s*없"),
        re.compile(_BEFORE + r"오늘\s*안에"),
    ],
    Category.COMPARATIVE: [
        re.compile(_BEFORE + r"타\s*로펌"),
        re.compile(_BEFORE + r"다른\s*법무법인"),
        re.compile(_BEFORE + r"경쟁사"),
    ],
}


KEYWORD_DESCRIPTIONS: dict[Category, str] = {
    Category.ABSOLUTE: "절대성/우월성 클레임 — 객관적 입증 불가 표현.",
    Category.EXAGGERATION: "희귀성/배타성 강조 — '당신만을 위한' 등 마케팅 과장.",
    Category.TIME_PRESSURE: "긴급성/FOMO 유도 — '지금 아니면', '마지막 기회' 등.",
    Category.COMPARATIVE: "다른 법무법인/로펌 명시 비교.",
}


def check_keywords(text: str) -> dict[Category, list[str]]:
    """본문 1차 regex pass. 위반 후보 반환.

    빈 dict면 통과 (1차 pass 안 LLM 호출 정상 진행).
    위반 발견 시 호출자는 LLM 호출 생략하고 슬롯 폐기 가능 (비용 절약).
    """
    out: dict[Category, list[str]] = {}
    for cat, patterns in _PATTERNS.items():
        hits: list[str] = []
        for pat in patterns:
            for m in pat.finditer(text):
                hits.append(m.group(0))
        if hits:
            out[cat] = hits
    return out


def format_violations(violations: dict[Category, list[str]]) -> str:
    """위반 메시지를 사람·LLM 모두 읽을 수 있는 한 줄 형식으로 직렬화."""
    if not violations:
        return ""
    parts: list[str] = []
    for cat, hits in violations.items():
        unique = sorted(set(hits))
        parts.append(f"[{cat.value}] {', '.join(unique)}")
    return "변호사법 §23 후보 위반: " + " / ".join(parts)
