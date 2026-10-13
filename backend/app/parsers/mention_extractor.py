# -*- coding: utf-8 -*-
"""
backend/app/parsers/mention_extractor.py
========================================
IS-mention and International Standards extraction pipeline.
Pattern A (IS-family) + Pattern B (non-IS international families) + structured parser.
"""
from __future__ import annotations
import re
import sys
import os
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

from app.db import get_db_cursor

# ── DB presence cache (loaded once at import or on demand) ─────────────────────
_DB_EXACT: set[str]    = set()   # full base_key: IS694, IS7098(PART1), ...
_DB_FAM_NUM: set[str]  = set()   # family+number only: IS694, IS7098, IS/IEC60947, ...

def load_db_sets():
    """Populate _DB_EXACT and _DB_FAM_NUM from the live standards DB."""
    global _DB_EXACT, _DB_FAM_NUM
    if _DB_EXACT and _DB_FAM_NUM:
        return
    with get_db_cursor() as cur:
        cur.execute("SELECT base_number FROM standards WHERE base_number IS NOT NULL;")
        for (bn,) in cur.fetchall():
            _DB_EXACT.add(bn)
            fn = re.sub(r'\(.*', '', bn)   # strip (PARTn...) suffix
            _DB_FAM_NUM.add(fn)
    print(f"[DB] {len(_DB_EXACT)} exact keys, {len(_DB_FAM_NUM)} family+num keys loaded.",
          file=sys.stderr)

# ── Citation-cue look-behind pattern ─────────────────────────────────────────
_CITATION_CUE_RE = re.compile(
    r'(?:conforming\s+to|as\s+per|marked\s+to|per\s+IS|to\s+IS|IS\s*:|per\s+BIS'
    r'|tested\s+(?:as\s+)?per)',
    re.IGNORECASE
)

# Copula words: precede 'IS' in a predicate sentence, not a standard reference
_COPULA_RE = re.compile(
    r'\b(?:RATE|COST|PRICE|QTY|QUANTITY|TOTAL|AMOUNT|PERIOD|DELIVERY|DIAMETER|LENGTH|WIDTH|HEIGHT|THICKNESS|DEPTH|SIZE|WEIGHT|CODE|ITEM|PART|SERIAL|SR)\s+$',
    re.IGNORECASE
)

_UNIT_TOKEN = r'(?:m|mm|cm|km|kg|nos?|sq|pcs?|ltr?|mtr?|lm|ml|g)(?:\b|$)'

# ── Pattern A ─────────────────────────────────────────────────────────────────
# IS-family (case-SENSITIVE — compiled WITHOUT re.IGNORECASE).
# Named groups: prefix intl num paren part_n sec_n hyph yr_c yr_s
IS_FAMILY_RE = re.compile(r"""
    (?<![a-z])                      # not preceded by lowercase
    (?P<prefix>[A-Z]*)              # optional UPPERCASE prefix glued to IS: GRADE→GRADEIS
    IS                              # literal IS — case-sensitive
    (?P<intl>(?:/(?:IEC|ISO|IEEE|TR))+)?  # /IEC /ISO /IEEE /TR (repeatable)
    [ \t]*[:/.\-]?[ \t]*            # flexible separator
    (?P<num>\d+)                    # main IS number (mandatory)
    (?:[ \t]*\(\s*(?P<paren>[^)\n]+?)\s*\))?   # optional paren block
    (?:(?:[ \t]*[,:][ \t]*|[ \t]+)  # Part/Sec with colon or space separator
       (?:Part|Pt|Section|Sec)\.?[ \t]*
       (?P<part_n>\d+)
       (?:[ \t]*/[ \t]*(?:Sec(?:tion)?|S)\.?[ \t]*(?P<sec_n>\d+))?
    )?
    (?:-(?P<hyph>\d{1,2})(?!\d))?   # hyphenated part: 1-2 digits NOT followed by another digit
    (?:                             # year: colon (never filtered) or space/dash (unit-filtered)
        [ \t]*:[ \t]*(?P<yr_c>(?:19|20)\d{2})
        |
        (?:[ \t]|\-)+(?P<yr_s>(?:19|20)\d{2})
        (?![ \t]*(?:m\b|mm\b|cm\b|km\b|kg\b|nos?\b|sq\b|pcs?\b|ltr?\b|mtr?\b|lm\b|ml\b|g\b))
    )?
""", re.VERBOSE)

# ── Pattern B ─────────────────────────────────────────────────────────────────
# Non-IS international families (case-sensitive; \b word boundaries required).
NON_IS_RE = re.compile(
    r'\b(IEC|ISO|BS|EN|ASTM|DIN|IEEE|UL)[ \t/\-]?[A-Z]?\d+(?:[:\-]\d+)*\b'
)

# ── Paren content parser ──────────────────────────────────────────────────────
def _parse_paren(paren_text: Optional[str]):
    """Return (part, sec, year) from parenthesized content."""
    if not paren_text:
        return None, None, None
    t = paren_text.strip()
    if re.match(r'^(?:19|20)\d{2}$', t):
        return None, None, int(t)
    m = re.match(r'^(?:Part|Pt|P)\.?[ \t]*(\d+)(?:[ \t]*/[ \t]*(?:Sec(?:tion)?|S)\.?[ \t]*(\d+))?$', t, re.I)
    if m:
        return m.group(1), m.group(2), None
    return None, None, None

# ── base_key builder ──────────────────────────────────────────────────────────
def _build_base_key(family: str, num: str, part: Optional[str], sec: Optional[str]) -> str:
    b = family + num
    if part:
        b += f"(PART{part}"
        if sec:
            b += f"/SEC{sec}"
        b += ")"
    return b.upper()

# ── Result dataclass ──────────────────────────────────────────────────────────
@dataclass
class Mention:
    raw_text:    str
    start:       int
    end:         int
    pattern:     str           # 'A' or 'B'
    family:      str
    number:      str
    part:        Optional[str]
    sec:         Optional[str]
    year:        Optional[int]
    base_key:    str
    in_db:       bool
    part_only_in_db: bool
    disposition: str           # KEEP | DROP | NEEDS_REVIEW
    copula_flag: bool = False
    context_before: str = ""   # 40 chars before match
    context_after:  str = ""   # 40 chars after match

# ── Main extractor ────────────────────────────────────────────────────
def extract_mentions(text: str, source_block_tier: str = "AUTHORITATIVE") -> list[Mention]:
    """
    Run Pattern A and Pattern B over text, apply all disposition rules,
    return Mention objects with KEEP/DROP/NEEDS_REVIEW dispositions.
    """
    if not _DB_EXACT:
        load_db_sets()

    mentions: list[Mention] = []

    # ── Pattern A ──
    for m in IS_FAMILY_RE.finditer(text):
        prefix = m.group('prefix') or ''
        intl   = m.group('intl') or ''
        num    = m.group('num')
        paren_t = m.group('paren')
        part_n  = m.group('part_n')
        sec_n   = m.group('sec_n')
        hyph    = m.group('hyph')
        yr_c    = m.group('yr_c')
        yr_s    = m.group('yr_s')

        p_part, p_sec, p_year = _parse_paren(paren_t)

        part = part_n or p_part or hyph
        sec  = sec_n  or p_sec
        year = int(yr_c) if yr_c else (int(yr_s) if yr_s else p_year)

        family  = 'IS' + intl
        base_key = _build_base_key(family, num, part, sec)
        fam_num_key = (family + num).upper()

        exact_match   = base_key in _DB_EXACT
        fam_num_match = fam_num_key in _DB_FAM_NUM
        in_db         = exact_match or fam_num_match
        part_only     = (not exact_match) and fam_num_match

        raw           = m.group(0).strip()
        has_colon_sep = bool(re.search(r'IS\s*:', raw))
        has_part_or_year = (part is not None or year is not None)

        # Text windows
        before60 = text[max(0, m.start()-60): m.start()]
        after15  = text[m.end(): m.end()+15]

        has_citation_cue   = bool(_CITATION_CUE_RE.search(before60))
        has_trailing_unit  = bool(re.match(r'^[ \t]*' + _UNIT_TOKEN, after15, re.I))

        # Copula guard: word immediately preceding IS
        before_is_word = re.search(r'(\w+)\s+$', before60)
        copula_flag = bool(before_is_word and _COPULA_RE.search(before_is_word.group(1) + ' '))

        # ── Disposition ──
        if has_trailing_unit and not (has_part_or_year or has_colon_sep or has_citation_cue):
            # Universal trailing-unit suppressor: physical measurement, not a standard
            disposition = 'DROP'
        elif prefix:
            # Glued prefix (GRADEIS, THIS, ANALYSIS, BASIS, etc.):
            if fam_num_match and (has_colon_sep or has_part_or_year or has_citation_cue) and not has_trailing_unit:
                disposition = 'KEEP'
            else:
                disposition = 'DROP'
        else:
            # Standalone IS
            if copula_flag and not (has_part_or_year or has_colon_sep):
                disposition = 'DROP'
            elif in_db:
                if part_only:
                    if has_colon_sep or has_part_or_year or has_citation_cue:
                        disposition = 'KEEP'
                    else:
                        disposition = 'DROP'
                else:
                    disposition = 'KEEP'
            else:
                if has_citation_cue or has_colon_sep or has_part_or_year:
                    disposition = 'NEEDS_REVIEW'
                else:
                    disposition = 'DROP'

        mentions.append(Mention(
            raw_text    = raw,
            start       = m.start(),
            end         = m.end(),
            pattern     = 'A',
            family      = family,
            number      = num,
            part        = part,
            sec         = sec,
            year        = year,
            base_key    = base_key + (' +NO_PART' if part_only else ''),
            in_db       = in_db,
            part_only_in_db = part_only,
            disposition = disposition,
            copula_flag = copula_flag,
            context_before = text[max(0, m.start()-40): m.start()],
            context_after  = text[m.end(): m.end()+40],
        ))

    # ── Pattern B (deduplicate overlapping A spans) ──
    a_spans = [(mn.start, mn.end) for mn in mentions]
    for m in NON_IS_RE.finditer(text):
        if any(not (m.end() <= a_s or m.start() >= a_e) for a_s, a_e in a_spans):
            continue  # overlaps Pattern A match — deduped
        fam = m.group(1)
        raw = m.group(0)
        mentions.append(Mention(
            raw_text    = raw,
            start       = m.start(),
            end         = m.end(),
            pattern     = 'B',
            family      = fam,
            number      = re.sub(r'^[A-Z]+', '', raw),
            part        = None,
            sec         = None,
            year        = None,
            base_key    = fam + re.sub(r'[^A-Z0-9/]', '', raw[len(fam):].upper()),
            in_db       = False,
            part_only_in_db = False,
            disposition = 'KEEP',   # all non-IS families are NON_BIS_STANDARD
            copula_flag = False,
            context_before = text[max(0, m.start()-40): m.start()],
            context_after  = text[m.end(): m.end()+40],
        ))

    mentions.sort(key=lambda mn: mn.start)
    return mentions
