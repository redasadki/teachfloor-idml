#!/usr/bin/env python3
"""
idml_to_teachfloor_md.py
========================
Converts an unpacked IDML folder to a single Teachfloor-writer Markdown file.

Usage
-----
  python3 idml_to_teachfloor_md.py <idml_folder> [output.md] [options]
  python3 idml_to_teachfloor_md.py <idml_folder> --init [--config my.toml] [--force]

Options
-------
  --init          Scan IDML, generate/merge styles.toml.  Does NOT convert.
  --force         With --init: regenerate TOML from scratch.
  --config FILE   Explicit TOML path.

Config search order (without --config)
  1. <idml_folder>/styles.toml
  2. <script_dir>/styles.toml
  3. Built-in defaults

Changes in v1.3.5
-----------------
  * Fix 1: parse_hyperlink_map() now percent-decodes URLs (InDesign stores
    them as e.g. https%3a//...), strips InDesign duplicate-name suffixes
    (" 1", " 2" etc.), and falls back to the Hyperlink Name attribute for
    destinations of type="list" (used for simple URL/email hyperlinks that
    have no shared URL-destination element). This covers the majority of
    hyperlinks in practice.
  * Fix 2: parse_story() collapses runs of 2+ consecutive hard-break
    sequences ("  \\n") down to a single one, removing the spurious blank
    lines that InDesign inserts around every hyperlink via extra <Br/> nodes.
  * Fix 3: _merge_stray_fragments() joins any hard-break line consisting
    solely of digits/punctuation onto the preceding content line, preventing
    lone "." or DOI suffix fragments from appearing as separate lines.

Changes in v1.3.4
-----------------
  * parse_hyperlink_map() introduced: reads <Hyperlink> entries from
    designmap.xml and builds a {source_id -> url} lookup.
  * _run_text() wraps <HyperlinkTextSource> content as [display](url).
  * to_teachfloor_md() joins consecutive same-style body paragraphs that
    end without sentence-closing punctuation (InDesign PSR splits at links).
"""

__version__ = "1.3.5"

import sys
import re
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import date
try:
    from urllib.parse import unquote as url_unquote
except ImportError:
    def url_unquote(s): return s

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None


VALID_ROLES = frozenset({
    "lesson_title", "element_title", "h2",
    "quote", "citation_name", "citation_role",
    "ul", "ol", "body", "skip",
})

IDML_NS = "http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"

_DEFAULT_SETTINGS = {
    "default_role":    "body",
    "bold_keywords":   ["bold", "semibold", "extrabold", "black"],
    "italic_keywords": ["italic", "oblique"],
}

_DEFAULT_STYLE_MAP = {
    "title 1": "lesson_title", "title 1 blue": "lesson_title",
    "title 1 grey": "lesson_title", "title white large": "lesson_title",
    "title 1 purple": "lesson_title", "title 1 brown": "lesson_title",
    "title 1 orange": "lesson_title", "title 1 green": "lesson_title",
    "cover": "lesson_title",
    "title 2 blue": "element_title", "title 2 white": "element_title",
    "title 2 brown": "element_title", "title 2 orange": "element_title",
    "title box": "element_title", "annex hpv": "element_title",
    "annex measles": "element_title",
    "title 3": "h2", "title 3 blue": "h2", "boxes title": "h2",
    "talking points 1": "h2", "conclusions title": "h2",
    "action plan title": "h2", "kf country blue": "h2",
    "kf country orange": "h2", "kf country green": "h2",
    "kf country purple": "h2", "kf country brown": "h2",
    "country contr": "h2",
    "citations": "quote", "citations orange": "quote",
    "comment02": "quote", "kf normal": "quote",
    "executive quotes": "body", "chapo": "body",
    "citation 2": "citation_name", "citation 2 orange": "citation_name",
    "kf first": "citation_name", "kf first green": "citation_name",
    "kfa name": "citation_name", "kfa name2": "citation_name",
    "kf ref blue": "citation_role", "kf ref orange": "citation_role",
    "kf ref green": "citation_role", "kf ref purple": "citation_role",
    "citations 3": "citation_role", "citations 3 orange": "citation_role",
    "bullet blue": "ul", "bullet brown": "ul", "bullet grey": "ul",
    "bullet brown 2": "ul", "bullet grey 2": "ul",
    "bullet blue ital bullet": "ul", "bullet white text 2": "ul",
    "bullet whte text": "ul", "boxes bullet": "ul",
    "talking points 2": "ul", "talking points 3": "ul",
    "votes bullets": "ul", "kf bullets blue": "ul",
    "kf bullets orange": "ul", "kf bullets green": "ul",
    "kf bullets purple": "ul", "citation bullet": "ul",
    "num": "ol",
    "normal": "body", "normal shared": "body",
    "normal shared white": "body", "questions": "body",
    "big story txt": "body", "bigstory end": "body",
    "blue centered": "body", "contributors": "body",
    "boxes": "body", "bo bolder": "body", "notes": "body",
    "action plans": "body", "conclusions": "body", "big story": "body",
    "copyright": "skip", "margin1": "skip", "margin2": "skip",
    "tdm 1": "skip", "tdm 2": "skip", "header": "skip",
}

_HEURISTIC_RULES = [
    ("copyright",   "skip",          True),
    ("margin",      "skip",          True),
    ("header",      "skip",          True),
    ("footer",      "skip",          True),
    ("toc",         "skip",          True),
    ("tdm",         "skip",          True),
    ("cover",       "lesson_title",  True),
    ("title 1",     "lesson_title",  True),
    ("title 2",     "element_title", True),
    ("title 3",     "h2",            True),
    ("title box",   "element_title", True),
    ("bullet",      "ul",            True),
    ("num",         "ol",            True),
    ("citation 2",  "citation_name", True),
    ("citation 3",  "citation_role", True),
    ("citations 3", "citation_role", True),
    ("citations",   "quote",         True),
    ("citation",    "citation_name", False),
    ("title",       "lesson_title",  False),
    ("heading",     "h2",            False),
    ("subhead",     "h2",            False),
    ("quote",       "quote",         False),
    ("normal",      "body",          True),
    ("body",        "body",          True),
    ("paragraph",   "body",          False),
    ("text",        "body",          False),
    ("annex",       "element_title", False),
]


def _guess_role(style_name):
    s = style_name.lower()
    for fragment, role, confident in _HEURISTIC_RULES:
        if fragment in s:
            return role, confident
    return "body", False


def resolve_config_path(idml_folder, explicit):
    if explicit:
        return Path(explicit)
    per_project = idml_folder.resolve() / "styles.toml"
    if per_project.exists():
        return per_project
    return Path(__file__).parent / "styles.toml"


def load_config(config_path):
    if not config_path.exists():
        print(f"  [INFO] No config at {config_path} - using built-in defaults.",
              file=sys.stderr)
        return _DEFAULT_SETTINGS.copy(), _DEFAULT_STYLE_MAP.copy()
    if tomllib is None:
        print(
            "  [WARN] TOML support unavailable.\n"
            "         Python 3.11+ includes it automatically.\n"
            "         For Python 3.9/3.10: pip install tomli\n"
            "         Falling back to built-in defaults.",
            file=sys.stderr,
        )
        return _DEFAULT_SETTINGS.copy(), _DEFAULT_STYLE_MAP.copy()
    try:
        with open(config_path, "rb") as fh:
            data = tomllib.load(fh)
    except Exception as exc:
        sys.exit(f"ERROR: Cannot read {config_path}: {exc}")
    settings  = {**_DEFAULT_SETTINGS, **data.get("settings", {})}
    raw_map   = data.get("style_map", {})
    style_map = {}
    for style, role in raw_map.items():
        sl = style.lower().strip()
        rl = role.lower().strip()
        if rl not in VALID_ROLES:
            print(f"  [WARN] Unknown role '{role}' for style '{style}' - skipping.",
                  file=sys.stderr)
            continue
        style_map[sl] = rl
    print(f"  Config     : {config_path.name} "
          f"({len(style_map)} mappings, default_role='{settings['default_role']}')")
    return settings, style_map


# ============================================================
# HYPERLINK MAP
# ============================================================

def parse_hyperlink_map(designmap_path):
    """Return {source_id: url} from <Hyperlink> elements in designmap.xml.

    Handles two destination patterns InDesign uses:

    1. type="object" — the URL is stored as the element text, prefixed with
       "HyperlinkURLDestination/".  InDesign percent-encodes the URL
       (e.g. https%3a// instead of https://) so we URL-decode it.

    2. type="list" (or absent) — no URL destination element; the URL is the
       Hyperlink Name attribute itself (InDesign uses this for simple URL /
       email hyperlinks that don't share a named URL destination).  We accept
       Names that look like a URL (http/https prefix) or an email address.

    In both cases we strip InDesign's duplicate-name numeric suffixes
    (" 1", " 2" … appended when the same URL appears more than once).
    """
    hmap = {}
    try:
        root = ET.fromstring(designmap_path.read_bytes())
    except ET.ParseError:
        return hmap

    for hyperlink in root.iter("Hyperlink"):
        source = hyperlink.get("Source", "").strip()
        if not source:
            continue

        url = ""

        # Pattern 1: explicit URL destination element
        for dest in hyperlink.iter("Destination"):
            if dest.get("type", "") == "object":
                raw = (dest.text or "").strip()
                candidate = re.sub(r"^HyperlinkURLDestination/?", "", raw).strip()
                candidate = re.sub(r"\s+\d+$", "", candidate).strip()
                if candidate:
                    url = url_unquote(candidate)
                    break

        # Pattern 2: fallback to Hyperlink Name attribute
        if not url:
            name = re.sub(r"\s+\d+$", "", hyperlink.get("Name", "").strip()).strip()
            if name.startswith(("http://", "https://", "mailto:")):
                url = name
            elif "@" in name and "." in name and " " not in name:
                url = "mailto:" + name

        if url:
            hmap[source] = url

    return hmap


# ============================================================
# INIT
# ============================================================

def discover_all_styles(folder):
    styles = set()
    for search_dir in [folder, folder / "Stories"]:
        if not search_dir.is_dir():
            continue
        for fpath in search_dir.glob("Story_*.xml"):
            try:
                root = ET.fromstring(fpath.read_bytes())
            except ET.ParseError:
                continue
            for para in root.iter("ParagraphStyleRange"):
                raw = para.get("AppliedParagraphStyle", "")
                if raw:
                    styles.add(normalize_style(raw))
    return sorted(styles)


def _load_existing_toml_map(path):
    if not path.exists() or tomllib is None:
        return {}
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
        return {k.lower().strip(): v for k, v in data.get("style_map", {}).items()}
    except Exception:
        return {}


def generate_toml(folder, output_path, force=False):
    folder = folder.resolve()
    print(f"\n  Scanning IDML stories in {folder} ...")
    all_styles = discover_all_styles(folder)
    if not all_styles:
        sys.exit("ERROR: No paragraph styles found - is this a valid unpacked IDML folder?")
    print(f"  Found {len(all_styles)} unique paragraph styles.")
    existing    = {} if force else _load_existing_toml_map(output_path)
    new_styles  = [s for s in all_styles if s not in existing]
    kept_styles = [s for s in all_styles if s in existing]
    print(f"  Already mapped : {len(kept_styles)}")
    print(f"  New styles     : {len(new_styles)}")
    grouped   = {}
    uncertain = []
    for style in new_styles:
        role, confident = _guess_role(style)
        grouped.setdefault(role, []).append((style, confident))
        if not confident:
            uncertain.append(style)
    confident_count = len(new_styles) - len(uncertain)
    pct = int(100 * confident_count / len(new_styles)) if new_styles else 100
    role_order = [
        "lesson_title", "element_title", "h2",
        "quote", "citation_name", "citation_role",
        "ul", "ol", "body", "skip",
    ]
    role_labels = {
        "lesson_title":   "Lesson titles (--- + # Title)",
        "element_title":  "Element titles (# Title)",
        "h2":             "Sub-headings (## Heading)",
        "quote":          "Verbatim direct quotes (> blockquote)",
        "citation_name":  "Citation name (**bold**)",
        "citation_role":  "Citation role (*italic*)",
        "ul":             "Bullet lists",
        "ol":             "Numbered lists",
        "body":           "Body / editorial text",
        "skip":           "Skip entirely (page furniture, TOC, copyright)",
    }
    lines = []
    if force or not output_path.exists():
        lines += [
            "# =============================================================================",
            "# styles.toml - idml-to-teachfloor configuration",
            "# =============================================================================",
            f"# Generated by idml_to_teachfloor_md.py v{__version__}",
            f"# Date        : {date.today().isoformat()}",
            f"# Styles      : {len(all_styles)} total",
            f"# Auto-mapped : {confident_count} / {len(new_styles)} new styles ({pct}% confident)",
        ]
        if uncertain:
            lines.append(f"# Review      : {len(uncertain)} entries marked '# TODO: verify'")
        lines += [
            "#",
            "# Edit this file to correct any mappings, then re-run the converter.",
            "# =============================================================================",
            "", "",
            "[settings]", "",
            "# Role for any style NOT in [style_map]: \"body\" (safe) or \"skip\" (discard)",
            'default_role = "body"', "",
            'bold_keywords   = ["bold", "semibold", "extrabold", "black"]',
            'italic_keywords = ["italic", "oblique"]',
            "", "",
            "# -----------------------------------------------------------------------------",
            "# [style_map]  InDesign paragraph style -> Teachfloor role",
            "# -----------------------------------------------------------------------------",
            "# Roles: lesson_title  element_title  h2  quote  citation_name",
            "#        citation_role  ul  ol  body  skip",
            "# -----------------------------------------------------------------------------",
            "[style_map]", "",
        ]
        for role in role_order:
            entries = grouped.get(role, [])
            if not entries:
                continue
            label = role_labels[role]
            lines.append(f"# -- {label} " + "-" * max(0, 60 - len(label)))
            for style, confident in sorted(entries):
                todo = "" if confident else "  # TODO: verify"
                lines.append(f'"{style}" = "{role}"{todo}')
            lines.append("")
    else:
        existing_text = output_path.read_text(encoding="utf-8").rstrip()
        lines.append(existing_text)
        lines += [
            "", "",
            "# " + "-" * 78,
            f"# NEW STYLES discovered on {date.today().isoformat()}",
            f"# {len(new_styles)} new style(s) added  ({pct}% auto-mapped with confidence)",
        ]
        if uncertain:
            lines.append("# Review lines marked '# TODO: verify'.")
        lines.append("# " + "-" * 78)
        lines.append("")
        for role in role_order:
            entries = grouped.get(role, [])
            if not entries:
                continue
            lines.append(f"# -- {role} (new)")
            for style, confident in sorted(entries):
                todo = "" if confident else "  # TODO: verify"
                lines.append(f'"{style}" = "{role}"{todo}')
            lines.append("")
    toml_text = "\n".join(lines).rstrip() + "\n"
    output_path.write_text(toml_text, encoding="utf-8")
    print(f"\n  -> {output_path}")
    print(f"  {len(new_styles)} new style(s) written. {len(uncertain)} marked TODO: verify.\n")
    print("  Next steps:")
    print(f"  1. Open {output_path.name} and review lines marked 'TODO: verify'")
    print(f"  2. python3 idml_to_teachfloor_md.py {folder.name}/ output.md --config {output_path}")


# ============================================================
# XML PARSING
# ============================================================

def normalize_style(raw):
    return raw.split("/")[-1].replace("$ID/", "").strip().lower()


def make_get_role(style_map, default_role):
    def get_role(raw):
        norm = normalize_style(raw)
        role = style_map.get(norm)
        if role is not None:
            return role
        print(f"  [INFO] Unknown style '{norm}' - using default role '{default_role}'.",
              file=sys.stderr)
        return default_role
    return get_role


def _has_font_keyword(cr, keywords):
    def _check(node):
        for attr in ("FontStyle", "AppliedCharacterStyle"):
            if any(k in node.get(attr, "").lower() for k in keywords):
                return True
        for prop in node.iter("Properties"):
            for e in prop.iter("FontStyle"):
                if e.text and any(k in e.text.lower() for k in keywords):
                    return True
        for child in node:
            if child.tag != "CharacterStyleRange" and _check(child):
                return True
        return False
    return _check(cr)


def _run_text(cr, hyperlink_map):
    """Collect text from a CharacterStyleRange in document order.

    <HyperlinkTextSource> nodes are wrapped as [display](url) using the
    hyperlink_map.  If the source ID is not in the map (internal anchor,
    cross-reference, etc.) the display text is emitted as plain text.
    <Content> and <Br/> are handled as before; element.tail is always
    appended after wrapper closing tags (v1.3.3 Fix 5).
    """
    parts = []

    def _walk(node):
        for child in node:
            if child.tag == "Content":
                if child.text:
                    parts.append(child.text)
                if child.tail:
                    parts.append(child.tail)
            elif child.tag == "Br":
                parts.append("\n")
                if child.tail:
                    parts.append(child.tail)
            elif child.tag == "HyperlinkTextSource":
                link_parts = []
                def _collect(n):
                    for c in n:
                        if c.tag == "Content":
                            if c.text:
                                link_parts.append(c.text)
                            if c.tail:
                                link_parts.append(c.tail)
                        elif c.tag == "Br":
                            link_parts.append("\n")
                            if c.tail:
                                link_parts.append(c.tail)
                        elif c.tag != "CharacterStyleRange":
                            _collect(c)
                            if c.tail:
                                link_parts.append(c.tail)
                _collect(child)
                display = "".join(link_parts).strip()
                source_id = child.get("Self", "").strip()
                url = hyperlink_map.get(source_id, "")
                if display and url:
                    parts.append(f"[{display}]({url})")
                elif display:
                    parts.append(display)
                if child.tail:
                    parts.append(child.tail)
            elif child.tag != "CharacterStyleRange":
                _walk(child)
                if child.tail:
                    parts.append(child.tail)

    _walk(cr)
    return "".join(parts)


def make_inline_extractor(bold_keywords, italic_keywords, hyperlink_map):
    """Return inline-text extractor closed over font keywords and hyperlink map."""
    def extract_inline(para):
        pieces = []
        for cr in para:
            if cr.tag != "CharacterStyleRange":
                continue
            bold   = _has_font_keyword(cr, bold_keywords)
            italic = _has_font_keyword(cr, italic_keywords)
            run = _run_text(cr, hyperlink_map)
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
    return extract_inline


# Lines consisting only of digits and/or punctuation — these are stray
# fragments that InDesign placed after a hyperlink in a separate run
# (e.g. a DOI suffix "15126588" or a sentence-ending ".").
_STRAY_FRAGMENT = re.compile(r'^[\d\s.,;:!?\u2019\u201c\u201d\u2014\u2013()\[\]]+$')


def _merge_stray_fragments(text):
    """Join bare punctuation/digit lines onto the preceding content line.

    Input/output use "  \\n" as the hard-break separator (as produced by
    parse_story after the newline-to-hard-break conversion).
    """
    raw_lines = text.split("  \n")
    merged = []
    for line in raw_lines:
        stripped = line.strip()
        if stripped and _STRAY_FRAGMENT.match(stripped) and merged:
            merged[-1] = merged[-1].rstrip() + stripped
        else:
            merged.append(line)
    return "  \n".join(merged)


def parse_story(xml_bytes, get_role, extract_inline):
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        print(f"  [WARN] XML parse error: {exc}", file=sys.stderr)
        return []
    result = []
    for para in root.iter("ParagraphStyleRange"):
        raw  = para.get("AppliedParagraphStyle", "")
        role = get_role(raw)
        text = extract_inline(para)
        text = text.replace("\u2028", "\n").replace("\u2029", "\n")
        text = "\n".join(seg.strip() for seg in text.split("\n")).strip()
        text = text.replace("\n", "  \n")
        # Collapse 2+ consecutive hard-breaks to one: InDesign wraps every
        # hyperlink with extra <Br/> nodes that produce spurious blank lines.
        text = re.sub(r"(  \n){2,}", "  \n", text).strip()
        # Merge lone punctuation/digit fragments onto the preceding line.
        text = _merge_stray_fragments(text)
        if text and role != "skip":
            result.append((role, normalize_style(raw), text))
    return result


# ============================================================
# MARKDOWN RENDERER
# ============================================================

# Sentence-ending punctuation: a body paragraph that ends with one of these
# is treated as a complete thought — the next same-style paragraph gets a
# blank-line separator. Without these, InDesign likely split a single visual
# line at a hyperlink boundary, so we join the fragments inline.
_SENTENCE_END = re.compile(r'[.!?:)\]"\'\u00bb\u2014\u2013]\s*$')


def to_teachfloor_md(paragraphs):
    lines      = []
    ol_n       = 0
    prev_role  = None
    prev_style = None
    in_lesson  = False
    quote_buf  = []

    def flush_quotes():
        for q in quote_buf:
            for ln in q.split("\n"):
                suffix = "  " if ln.endswith("  ") else ""
                lines.append(f"> {ln.strip()}{suffix}")
        quote_buf.clear()

    for role, style, text in paragraphs:
        if role != "ol":
            ol_n = 0
        if role not in ("quote", "citation_name", "citation_role"):
            flush_quotes()

        if role == "lesson_title":
            if in_lesson:
                lines.append("")
            lines.append("---")
            lines.append(f"# {text}")
            in_lesson = True
            prev_role  = role
            prev_style = style
            continue

        if not in_lesson:
            lines.append("---")
            lines.append(f"# {text}")
            in_lesson = True
            prev_role  = role
            prev_style = style
            continue

        if role == "element_title":
            lines.append("")
            lines.append(f"# {text}")
        elif role == "h2":
            lines.append("")
            lines.append(f"## {text}")
        elif role == "quote":
            quote_buf.append(text)
        elif role == "citation_name":
            flush_quotes()
            t = text.strip()
            line = t if (t.startswith("**") and t.endswith("**")) else f"**{t}**"
            lines.append(line)
        elif role == "citation_role":
            flush_quotes()
            t = text.strip()
            line = t if (t.startswith("*") and t.endswith("*")) else f"*{t}*"
            lines.append(line)
        elif role == "ul":
            lines.append(f"- {text.replace(chr(10), chr(10) + '  ')}")
        elif role == "ol":
            ol_n += 1
            lines.append(f"{ol_n}. {text.replace(chr(10), chr(10) + '   ')}")
        else:  # body
            # InDesign splits a single visual paragraph into multiple
            # ParagraphStyleRanges at hyperlink boundaries. Detect this by
            # checking whether the previous body paragraph ended without
            # sentence-closing punctuation AND shares the same style.
            # If so, join inline with a space rather than a blank-line gap.
            if (prev_role == "body"
                    and prev_style == style
                    and lines
                    and lines[-1]
                    and not _SENTENCE_END.search(lines[-1])):
                lines[-1] = lines[-1].rstrip() + " " + text
            else:
                if prev_role == "body":
                    lines.append("")
                lines.append(text)

        prev_role  = role
        prev_style = style

    flush_quotes()
    return "\n".join(lines).strip()


# ============================================================
# IDML FOLDER READER
# ============================================================

def find_designmap(folder):
    for candidate in sorted(folder.glob("designmap*.xml")):
        return candidate
    return None


def get_story_order(designmap_path):
    root = ET.fromstring(designmap_path.read_bytes())
    story_list_str = root.attrib.get("StoryList", "")
    if story_list_str:
        return story_list_str.split()
    print(
        "  [WARN] StoryList attribute missing in designmap - "
        "story order may be approximate. Verify the output.",
        file=sys.stderr,
    )
    ids = [
        elem.get("src", "").split("/")[-1].replace("Story_", "").replace(".xml", "")
        for elem in root.iter(f"{{{IDML_NS}}}Story")
    ]
    return list(reversed([i for i in ids if i]))


def discover_stories(folder):
    stories = {}
    for search_dir in [folder, folder / "Stories"]:
        if not search_dir.is_dir():
            continue
        for fpath in search_dir.glob("Story_*.xml"):
            stem   = fpath.stem
            raw_id = stem.split("_", 1)[1]
            sid    = raw_id.split("-")[0]
            if sid not in stories or "-" not in stem:
                stories[sid] = fpath
    return stories


def convert_folder(folder, output_path, config_path):
    folder = folder.resolve()

    settings, style_map = load_config(config_path)
    get_role = make_get_role(style_map, settings["default_role"])

    designmap = find_designmap(folder)
    if not designmap:
        sys.exit(f"ERROR: No designmap*.xml found in {folder}")
    print(f"  Designmap  : {designmap.name}")

    hyperlink_map = parse_hyperlink_map(designmap)
    print(f"  Hyperlinks : {len(hyperlink_map)} destinations indexed")

    extract_inline = make_inline_extractor(
        settings["bold_keywords"], settings["italic_keywords"], hyperlink_map
    )

    story_order = get_story_order(designmap)
    print(f"  StoryList  : {len(story_order)} story IDs")

    available = discover_stories(folder)
    print(f"  Story files: {len(available)} found")

    def sort_key(sid):
        try:
            return story_order.index(sid)
        except ValueError:
            return len(story_order)

    ordered   = sorted(available.items(), key=lambda kv: sort_key(kv[0]))
    all_paras = []
    n_skipped = 0

    for sid, fpath in ordered:
        paras = parse_story(fpath.read_bytes(), get_role, extract_inline)
        if not paras:
            n_skipped += 1
            continue
        all_paras.extend(paras)

    print(f"  Parsed     : {len(ordered) - n_skipped} stories with content "
          f"({n_skipped} skipped as empty)")
    print(f"  Paragraphs : {len(all_paras)}")

    md = to_teachfloor_md(all_paras)

    if output_path is None:
        output_path = folder / "output.md"
    else:
        output_path = Path(output_path)
        if not output_path.parent.parts:
            output_path = folder / output_path

    Path(output_path).write_text(md, encoding="utf-8")

    lessons  = md.count("\n---\n") + (1 if md.startswith("---") else 0)
    elements = md.count("\n# ")    + (1 if md.startswith("# ")  else 0)
    print(f"  Output     : {output_path}  ({len(md):,} chars)")
    print(f"  Lessons    : ~{lessons}    Elements: ~{elements}")
    return md


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Convert an unpacked IDML folder to Teachfloor Markdown.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 idml_to_teachfloor_md.py MyReport-IDML/ --init
  python3 idml_to_teachfloor_md.py MyReport-IDML/ --init --config t2r12.toml
  python3 idml_to_teachfloor_md.py MyReport-IDML/ --init --force
  python3 idml_to_teachfloor_md.py MyReport-IDML/ course.md
  python3 idml_to_teachfloor_md.py MyReport-IDML/ course.md --config t2r12.toml
""",
    )
    parser.add_argument("idml_folder", help="Path to the unpacked IDML folder")
    parser.add_argument("output", nargs="?", default=None,
                        help="Output Markdown file. Ignored when --init is used.")
    parser.add_argument("--init", action="store_true",
                        help="Generate/merge styles.toml. Does not convert.")
    parser.add_argument("--force", action="store_true",
                        help="With --init: overwrite existing styles.toml completely.")
    parser.add_argument("--config", default=None,
                        help="Explicit TOML path. With --init: write generated TOML here.")
    args = parser.parse_args()

    folder = Path(args.idml_folder)
    if not folder.is_dir():
        sys.exit(f"ERROR: Not a directory: {folder}")

    if args.init:
        toml_out = Path(args.config) if args.config else folder.resolve() / "styles.toml"
        generate_toml(folder, toml_out, force=args.force)
    else:
        config_path = resolve_config_path(folder, args.config)
        output      = args.output
        convert_folder(folder, output, config_path)


if __name__ == "__main__":
    main()
