#!/usr/bin/env python3
"""
idml_to_teachfloor_md.py
========================
Converts an unpacked IDML folder to a single Teachfloor-writer Markdown file.

Story reading order is determined by the `StoryList` attribute in the
designmap XML (the InDesign canonical page order). Stories not present
as files, or yielding no content after style filtering, are skipped.

IDML folders are typically laid out as either:
  <folder>/Story_*.xml          (flat, as exported by some tools)
  <folder>/Stories/Story_*.xml  (standard IDML zip layout)
Both layouts are supported.

Usage:
    python idml_to_teachfloor_md.py <idml_folder> [output.md]

    <idml_folder>   Directory containing Story XML files and a designmap*.xml
    [output.md]     Output path (default: <idml_folder>/output.md)
"""

__version__ = "1.1.0"

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


# ============================================================
# CONFIGURABLE STYLE MAP
# ============================================================
# Keys  : IDML paragraph style names, lowercased, path-stripped.
# Values: semantic role consumed by the Markdown renderer.
#
# Roles:
#   lesson_title   → ---\n# <text>    New Teachfloor Lesson (module separator)
#   element_title  → # <text>          New Teachfloor Content Element
#   h2             → ## <text>         Sub-heading inside an element
#   quote          → > <text>          Verbatim direct quote / testimonial
#   citation_name  → **<text>**        Speaker name after a quote
#   citation_role  → *<text>*          Speaker role / org after name
#   ul             → - <text>          Bullet list item
#   ol             → 1. <text>         Ordered list item (auto-counter)
#   body           → plain paragraph   Body / editorial / summary text
#   skip           → (omitted)         Headers, margins, TOC, copyright

STYLE_MAP = {
    # ── Lesson titles ────────────────────────────────────────────────────────────
    "title 1":                  "lesson_title",
    "title 1 blue":             "lesson_title",
    "title 1 grey":             "lesson_title",
    "title white large":        "lesson_title",
    "title 1 purple":           "lesson_title",
    "title 1 brown":            "lesson_title",
    "title 1 orange":           "lesson_title",
    "title 1 green":            "lesson_title",
    "cover":                    "lesson_title",

    # ── Element titles ───────────────────────────────────────────────────────────
    "title 2 blue":             "element_title",
    "title 2 white":            "element_title",
    "title 2 brown":            "element_title",
    "title 2 orange":           "element_title",
    "title box":                "element_title",
    "annex hpv":                "element_title",
    "annex measles":            "element_title",

    # ── Sub-headings ─────────────────────────────────────────────────────────────
    "title 3":                  "h2",
    "title 3 blue":             "h2",
    "boxes title":              "h2",
    "talking points 1":         "h2",
    "conclusions title":        "h2",
    "action plan title":        "h2",
    "kf country blue":          "h2",
    "kf country orange":        "h2",
    "kf country green":         "h2",
    "kf country purple":        "h2",
    "kf country brown":         "h2",
    "country contr":            "h2",

    # ── ACTUAL direct quotes (verbatim first-person speech) ──────────────────────
    "citations":                "quote",
    "citations orange":         "quote",
    "comment02":                "quote",
    "kf normal":                "quote",

    # ── NOT quotes: editorial summary / intro paragraphs ─────────────────────────
    "executive quotes":         "body",
    "chapo":                    "body",

    # ── Citation name (bold attribution after a quote) ───────────────────────────
    "citation 2":               "citation_name",
    "citation 2 orange":        "citation_name",
    "kf first":                 "citation_name",
    "kf first green":           "citation_name",
    "kfa name":                 "citation_name",
    "kfa name2":                "citation_name",

    # ── Citation role (italic attribution after name) ────────────────────────────
    "kf ref blue":              "citation_role",
    "kf ref orange":            "citation_role",
    "kf ref green":             "citation_role",
    "kf ref purple":            "citation_role",
    "citations 3":              "citation_role",
    "citations 3 orange":       "citation_role",

    # ── Bullet lists ─────────────────────────────────────────────────────────────
    "bullet blue":              "ul",
    "bullet brown":             "ul",
    "bullet grey":              "ul",
    "bullet brown 2":           "ul",
    "bullet grey 2":            "ul",
    "bullet blue ital bullet":  "ul",
    "bullet white text 2":      "ul",
    "bullet whte text":         "ul",
    "boxes bullet":             "ul",
    "talking points 2":         "ul",
    "talking points 3":         "ul",
    "votes bullets":            "ul",
    "kf bullets blue":          "ul",
    "kf bullets orange":        "ul",
    "kf bullets green":         "ul",
    "kf bullets purple":        "ul",
    "citation bullet":          "ul",

    # ── Numbered lists ───────────────────────────────────────────────────────────
    "num":                      "ol",

    # ── Body text ────────────────────────────────────────────────────────────────
    "normal":                   "body",
    "normal shared":            "body",
    "normal shared white":      "body",
    "questions":                "body",
    "big story txt":            "body",
    "bigstory end":             "body",
    "blue centered":            "body",
    "contributors":             "body",
    "boxes":                    "body",
    "bo bolder":                "body",
    "notes":                    "body",
    "action plans":             "body",
    "conclusions":              "body",
    "big story":                "body",

    # ── Skip entirely ────────────────────────────────────────────────────────────
    "copyright":                "skip",
    "margin1":                  "skip",
    "margin2":                  "skip",
    "tdm 1":                    "skip",
    "tdm 2":                    "skip",
    "header":                   "skip",
}


# ============================================================
# XML PARSING
# ============================================================

def normalize_style(raw: str) -> str:
    """Strip IDML path prefix and normalize to lowercase."""
    return raw.split("/")[-1].replace("$ID/", "").strip().lower()


def get_role(raw: str) -> str:
    """Resolve a paragraph style name to its semantic role."""
    norm = normalize_style(raw)
    if norm in STYLE_MAP:
        return STYLE_MAP[norm]
    for key, role in STYLE_MAP.items():
        if key and key in norm:
            return role
    return "body"


def _has_font_keyword(cr, keywords: tuple) -> bool:
    for attr in ("FontStyle", "AppliedCharacterStyle"):
        if any(k in cr.get(attr, "").lower() for k in keywords):
            return True
    for prop in cr.iter("Properties"):
        for e in prop.iter("FontStyle"):
            if e.text and any(k in e.text.lower() for k in keywords):
                return True
    return False


def char_is_bold(cr) -> bool:
    return _has_font_keyword(cr, ("bold", "semibold", "extrabold", "black"))


def char_is_italic(cr) -> bool:
    return _has_font_keyword(cr, ("italic", "oblique"))


def extract_inline(para) -> str:
    """
    Extract text from a ParagraphStyleRange, applying bold/italic markers.

    Whitespace is trimmed from each run BEFORE markers are applied so it
    sits outside them:  "**word:**  rest"  not  "**word: ** rest"
    """
    pieces = []
    for cr in para:
        if cr.tag != "CharacterStyleRange":
            continue

        bold   = char_is_bold(cr)
        italic = char_is_italic(cr)

        run = "".join(
            child.text for child in cr
            if child.tag == "Content" and child.text
        )
        if not run:
            continue

        core   = run.strip()
        lspace = run[: len(run) - len(run.lstrip())]
        rspace = run[len(run.rstrip()):]

        if core:
            if bold and italic:
                core = f"***{core}***"
            elif bold:
                core = f"**{core}**"
            elif italic:
                core = f"*{core}*"
            pieces.append(lspace + core + rspace)
        else:
            pieces.append(run)

    return "".join(pieces)


def parse_story(xml_bytes: bytes) -> list:
    """Parse an IDML Story XML → list of (role, style_name, text)."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        print(f"  [WARN] XML parse error: {e}", file=sys.stderr)
        return []
    result = []
    for para in root.iter("ParagraphStyleRange"):
        raw  = para.get("AppliedParagraphStyle", "")
        role = get_role(raw)
        text = extract_inline(para).strip()
        if text and role != "skip":
            result.append((role, normalize_style(raw), text))
    return result


# ============================================================
# MARKDOWN RENDERER  (Teachfloor-writer format)
# ============================================================

def to_teachfloor_md(paragraphs: list) -> str:
    """
    Render (role, style, text) tuples → Teachfloor-writer Markdown.

    Format recap:
        ---
        # Lesson title

        # Element title
        Body text...

        > "Verbatim direct quote."

        **Citation Name**
        *Role, Organisation, Location*

        ## Sub-heading
        - Bullet item
        1. Numbered item
    """
    lines: list[str] = []
    ol_n      = 0
    prev_role = None
    in_lesson = False
    quote_buf: list[str] = []

    def flush_quotes():
        nonlocal quote_buf
        for q in quote_buf:
            lines.append(f": 