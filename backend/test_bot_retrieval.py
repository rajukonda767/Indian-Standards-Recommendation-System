"""
test_bot_retrieval.py
=====================
Pytest suite for MiniBot Phase 2:
- IS number extraction (extract_is_numbers)
- Canonical IS normalization (normalize_is)
- Streaming-safe <think> tag filter (ThinkTagFilter)
"""

import pytest
from app.services.bot_retrieval import extract_is_numbers, normalize_is, NormalizedIS
from app.routers.bot import ThinkTagFilter


# ── IS Number Extraction Tests (extract_is_numbers) ──────────────────────────

def test_extract_basic_is():
    res = extract_is_numbers("Check IS 7098 please")
    assert res == ["IS 7098"]


def test_extract_unspaced_is():
    res = extract_is_numbers("Specification refers to IS7098")
    assert res == ["IS7098"]


def test_extract_lowercase_is_with_year():
    res = extract_is_numbers("Standard is 694:2010 for copper cables")
    assert res == ["is 694:2010"]


def test_extract_part_and_year():
    res = extract_is_numbers("Conforming to IS 7098 (Part 1):2025 with amendments")
    assert res == ["IS 7098 (Part 1):2025"]


def test_extract_hyphenated_part():
    res = extract_is_numbers("Heavy duty cable IS 1554-1 required")
    assert res == ["IS 1554-1"]


def test_extract_spaced_part():
    res = extract_is_numbers("Refer to IS 1554 (Part 1) specifications")
    assert res == ["IS 1554 (Part 1)"]


def test_extract_iec_joint_standard():
    res = extract_is_numbers("International standard IS/IEC 60502 for power distribution")
    assert res == ["IS/IEC 60502"]


def test_extract_colon_year():
    res = extract_is_numbers("Aerial bunched cable per IS 14255:1995")
    assert res == ["IS 14255:1995"]


def test_extract_in_hindi_sentence():
    text = "क्या IS 7098 (Part 1):2025 वर्तमान में सक्रिय मानक है?"
    res = extract_is_numbers(text)
    assert res == ["IS 7098 (Part 1):2025"]


def test_extract_in_telugu_sentence():
    text = "IS 694 మరియు IS 7098 ప్రమాణాల గురించి వివరాలు తెలపండి"
    res = extract_is_numbers(text)
    assert res == ["IS 694", "IS 7098"]


def test_extract_multiple_and_deduplicate():
    text = "Compare IS 694 with IS 7098, and also check IS 694 again"
    res = extract_is_numbers(text)
    assert res == ["IS 694", "IS 7098"]


def test_ignore_unrelated_numbers_and_years():
    text = "In 2024 we procured 500 units of 4C x 2.5 sq mm cable under clause 5.2"
    res = extract_is_numbers(text)
    assert res == []


def test_ignore_copula_is():
    text = "What is 2024? This is 100% compliant with the tender terms."
    res = extract_is_numbers(text)
    assert res == []


def test_extract_with_punctuation():
    text = "Please verify IS 7098:2025. Is IS 694 active? Check (IS 1554-1)!"
    res = extract_is_numbers(text)
    assert "IS 7098:2025" in res
    assert "IS 694" in res
    assert "IS 1554-1" in res


# ── IS Normalization Tests (normalize_is) ───────────────────────────────────

def test_normalize_basic():
    norm = normalize_is("IS 7098")
    assert isinstance(norm, str)
    assert norm == "IS7098"
    assert norm.base == "IS7098"
    assert norm.part is None
    assert norm.year is None
    assert norm.base_key == "IS7098"


def test_normalize_unspaced():
    norm = normalize_is("IS7098")
    assert norm == "IS7098"
    assert norm.base == "IS7098"


def test_normalize_lowercase_colon_year():
    norm = normalize_is("is 694:2010")
    assert norm == "IS694:2010"
    assert norm.base == "IS694"
    assert norm.year == 2010
    assert norm.part is None
    assert norm.base_key == "IS694"


def test_normalize_part_and_year():
    norm = normalize_is("IS 7098 (Part 1):2025")
    assert norm == "IS7098:PART1:2025"
    assert norm.base == "IS7098"
    assert norm.part == "PART1"
    assert norm.year == 2025
    assert norm.base_key == "IS7098(PART1)"


def test_normalize_hyphenated_part():
    norm = normalize_is("IS 1554-1")
    assert norm == "IS1554:PART1"
    assert norm.base == "IS1554"
    assert norm.part == "PART1"
    assert norm.year is None
    assert norm.base_key == "IS1554(PART1)"


def test_normalize_paren_part():
    norm = normalize_is("IS 1554 (Part 1)")
    assert norm == "IS1554:PART1"
    assert norm.base == "IS1554"
    assert norm.part == "PART1"


def test_normalize_iec_standard():
    norm = normalize_is("IS/IEC 60502")
    assert norm == "ISIEC60502"
    assert norm.base == "ISIEC60502"
    assert norm.base_key == "IS/IEC60502"


def test_normalize_colon_year_standard():
    norm = normalize_is("IS 14255:1995")
    assert norm == "IS14255:1995"
    assert norm.base == "IS14255"
    assert norm.year == 1995


# ── Streaming-Safe ThinkTagFilter Tests ──────────────────────────────────────

def test_think_filter_split_tags():
    filter_inst = ThinkTagFilter()
    chunks = [
        "The standard is ",
        "<th",
        "ink>I am reasoning about the standard",
        " internally here</th",
        "ink>Current and active in BIS catalog."
    ]
    result = "".join(filter_inst.process_chunk(c) for c in chunks) + filter_inst.flush()
    assert result == "The standard is Current and active in BIS catalog."
    assert "<think>" not in result
    assert "</think>" not in result
    assert "reasoning" not in result


def test_think_filter_multiple_blocks():
    filter_inst = ThinkTagFilter()
    chunks = [
        "Prefix text. ",
        "<think>thought 1</think>",
        "Middle text. ",
        "<think>thought 2</think>",
        "Suffix text."
    ]
    result = "".join(filter_inst.process_chunk(c) for c in chunks) + filter_inst.flush()
    assert result == "Prefix text. Middle text. Suffix text."


def test_think_filter_clean_text_with_less_than():
    filter_inst = ThinkTagFilter()
    chunks = [
        "Price is <",
        "500 rupees and compliance is <100%."
    ]
    result = "".join(filter_inst.process_chunk(c) for c in chunks) + filter_inst.flush()
    assert result == "Price is <500 rupees and compliance is <100%."
