"""Lexical adaptation helpers shared across STT backends."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from dictate.stt import SpeechToText

LexiconMode = Literal["native", "prompt", "post", "hybrid"]
LEXICON_MODES: tuple[LexiconMode, ...] = ("native", "prompt", "post", "hybrid")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")


@dataclass(frozen=True, slots=True)
class LexiconPlan:
    decode_hotwords: str | None
    prompt_context: str | None
    post_hotwords: tuple[str, ...]
    post_replacements: dict[str, str]


def normalize_lexicon_mode(value: str | None) -> LexiconMode:
    if value in LEXICON_MODES:
        return value  # type: ignore[return-value]
    return "native"


def parse_hotwords(hotwords: str | None) -> tuple[str, ...]:
    if not hotwords:
        return ()
    words = [word.strip() for word in hotwords.split() if word.strip()]
    return tuple(_dedupe(words))


def build_lexicon_plan(
    *,
    stt: SpeechToText,
    hotwords: str | None,
    lexicon_mode: LexiconMode,
    replacements: dict[str, str] | None = None,
) -> LexiconPlan:
    terms = parse_hotwords(hotwords)
    normalized_replacements = _normalize_replacements(replacements)

    decode_hotwords = None
    if lexicon_mode in {"native", "hybrid"} and stt.capabilities.supports_hotwords:
        decode_hotwords = hotwords

    prompt_context = None
    if lexicon_mode in {"prompt", "hybrid"} and stt.capabilities.supports_prompt_bias:
        prompt_context = _build_prompt_context(terms)

    post_hotwords: tuple[str, ...] = ()
    post_replacements: dict[str, str] = {}
    if lexicon_mode in {"post", "hybrid"}:
        post_hotwords = terms
        post_replacements = normalized_replacements

    return LexiconPlan(
        decode_hotwords=decode_hotwords,
        prompt_context=prompt_context,
        post_hotwords=post_hotwords,
        post_replacements=post_replacements,
    )


def apply_post_corrections(
    text: str,
    *,
    hotwords: tuple[str, ...],
    replacements: dict[str, str],
) -> str:
    if not text:
        return text
    if not hotwords and not replacements:
        return text

    hotword_map = {word.lower(): word for word in hotwords}

    def replace_token(match: re.Match[str]) -> str:
        token = match.group(0)
        lowered = token.lower()

        if lowered in replacements:
            return replacements[lowered]
        if lowered in hotword_map:
            return hotword_map[lowered]

        # Conservative fallback: allow one-edit typo repair against configured hotwords.
        # This fixes common near-misses (for example "canery" -> "canary") without
        # aggressively rewriting unrelated words.
        if len(token) < 4:
            return token
        candidate = _nearest_hotword(lowered, hotword_map)
        return candidate if candidate is not None else token

    return _WORD_RE.sub(replace_token, text)


def _nearest_hotword(token: str, hotword_map: dict[str, str]) -> str | None:
    best: str | None = None
    best_distance = 2
    for lowered, canonical in hotword_map.items():
        if abs(len(lowered) - len(token)) > 1:
            continue
        distance = _levenshtein_distance(token, lowered, max_distance=1)
        if distance is None:
            continue
        if distance < best_distance:
            best_distance = distance
            best = canonical
    return best


def _levenshtein_distance(a: str, b: str, *, max_distance: int) -> int | None:
    if a == b:
        return 0
    if abs(len(a) - len(b)) > max_distance:
        return None

    prev = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        row = [i]
        min_in_row = i
        for j, char_b in enumerate(b, start=1):
            cost = 0 if char_a == char_b else 1
            value = min(
                prev[j] + 1,
                row[j - 1] + 1,
                prev[j - 1] + cost,
            )
            row.append(value)
            if value < min_in_row:
                min_in_row = value
        if min_in_row > max_distance:
            return None
        prev = row

    distance = prev[-1]
    return distance if distance <= max_distance else None


def _build_prompt_context(terms: tuple[str, ...]) -> str | None:
    if not terms:
        return None
    shortlist = ", ".join(terms[:32])
    return (
        "Prefer these domain terms when acoustically plausible, preserving their exact spelling: "
        f"{shortlist}."
    )


def _normalize_replacements(replacements: dict[str, str] | None) -> dict[str, str]:
    if not replacements:
        return {}
    normalized: dict[str, str] = {}
    for wrong, right in replacements.items():
        wrong_clean = wrong.strip().lower()
        right_clean = right.strip()
        if wrong_clean and right_clean:
            normalized[wrong_clean] = right_clean
    return normalized


def _dedupe(words: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for word in words:
        key = word.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(word)
    return ordered
