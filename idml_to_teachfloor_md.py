#!/usr/bin/env python3
"""
idml_to_teachfloor_md.py
========================
Converts an unpacked IDML folder to a single Teachfloor-writer Markdown file.

Usage
-----
  # Normal conversion (reads styles.toml from the IDML folder, then next to
  # this script, then falls back to built-in defaults):
  python3 idml_to_teachfloor_md.py <idml_folder> [output.md] [options]

  # Bootstrap: scan the IDML and generate / merge a styles.toml:
  python3 idml_to_teachfloor_md.py <idml_folder> --init [--config my.toml] [--force]

Options
-------
  --init          Scan the IDML folder and generate/merge a styles.toml.
                  Does NOT produce a Markdown file.
  --force         Used with --init: regenerate the TOML from scratch,
                  overwriting any existing file.
  --config FILE   Explicit TOML file path (overrides auto-search).

Config search order (without --config)
---------------------------------------
  1. <idml_folder>/styles.toml    per-project config
  2. <script_dir>/styles.toml     shipped default / GLF-T2R reference
  3. Built-in defaults            (no file; warning printed)

See styles.toml for documentation of all settings and roles.

Changes in v1.3.3
-----------------
  * Fix 1: _has_font_keyword now descends into wrapper sub-elements
    (HyperlinkTextSource etc.) so bold/italic on hyperlinked text is
    detected correctly.
  * Fix 2: Removed the dead/dangerous substring fallback in get_role;
    after the primary exact-match dict lookup, unknown styles now fall
    straight to default_role with a logged warning.
  * Fix 3: flush_quotes preserves Markdown hard-break trailing spaces
    instead of rstrip()ing them away.
  * Fix 4: citation_name / citation_role no longer strip literal asterisks
    from content; double-wrapping is prevented by a starts/endswith check.
  * Fix 5: _walk() now appends element.tail so text after inline wrapper
    closing tags is no longer silently dropped.
  * Fix 6: get_story_order() emits a [WARN] when the StoryList attribute
    is absent and order is therefore approximate.
"""

__version__ = "1.3.3"

import sys
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import date

# ---------------------------------------------------------------------------
# TOML - stdlib tomllib (Python 3.11+) or tomli backport (3.9 / 3.10)
# ---------------------------------------------------------------------------
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib   # pip install tomli
    except ImportError:
        tomllib = None


# ============================================================
# CONSTANTS
# ============================================================

VALID_ROLES = frozenset({
    "lesson_title", "element_title", "h2",
    "quote", "citation_name", "citation_role",
    "ul", "ol", "body", "skip",
})

IDML_NS = "http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"


# ============================================================
# BUILT-IN DEFAULTS  (used only when no styles.toml is found)
# ============================================================

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


# ============================================================
# HEURISTIC ROLE GUESSER
# ============================================================

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


# ============================================================
# CONFIG LOADER
# ============================================================

def resolve_config_path(idml_folder, explicit):
    if explicit:
        return Path(explicit)
    per_project = idml_folder.resolve() / "styles.toml"
    if per_project.exists():
        return per_project
    return Path(__file__).parent / "styles.toml"


def load_config(config_path):
    """Load TOML config; return (settings, style_map)."""
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
          f"({len(style_map)} mappings, default_role='{settings['default_role']}')"
    )
    return settings, style_map


# ============================================================
# INIT: discover styles & generate / merge styles.toml
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
        # FIX 2: exact-match only; the old substring fallback was dead code
        # that could silently mis-role paragraphs (e.g. "num" matching
        # "document number"). Unknown styles now fall to default_role with
        # an [INFO] log so problems are visible.
        role = style_map.get(norm)
        if role is not None:
            return role
        print(f"  [INFO] Unknown style '{norm}' - using default role '{default_role}'.",
              file=sys.stderr)
        return default_role
    return get_role


def _has_font_keyword(cr, keywords):
    # FIX 1: descend into wrapper sub-elements (HyperlinkTextSource etc.)
    # so bold/italic character styles on hyperlinked text are detected.
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


def _run_text(cr):
    """Collect text from a CharacterStyleRange in document order.

    Handles:
      <Content>   - literal text, appended directly.
      <Br/>       - InDesign forced line break, converted to newline.
      wrappers    - e.g. <HyperlinkTextSource>, <CrossReferenceSource>:
                    descended recursively; element.tail appended after
                    descent (FIX 5) so text after closing tags is kept.

    A nested <CharacterStyleRange> is NOT descended into to avoid
    double-emission (the outer loop visits every CSR independently).
    """
    parts = []

    def _walk(node):
        for child in node:
            if child.tag == "Content":
                if child.text:
                    parts.append(child.text)
                if child.tail:          # FIX 5
                    parts.append(child.tail)
            elif child.tag == "Br":
                parts.append("\n")
                if child.tail:          # FIX 5
                    parts.append(child.tail)
            elif child.tag != "CharacterStyleRange":
                _walk(child)
                if child.tail:          # FIX 5: text after wrapper closing tag
                    parts.append(child.tail)

    _walk(cr)
    return "".join(parts)


def make_inline_extractor(bold_keywords, italic_keywords):
    """Return an inline-text extractor closed over font keyword lists."""
    def extract_inline(para):
        pieces = []
        for cr in para:
            if cr.tag != "CharacterStyleRange":
                continue
            bold   = _has_font_keyword(cr, bold_keywords)
            italic = _has_font_keyword(cr, italic_keywords)
            run = _run_text(cr)
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
        if text and role != "skip":
            result.append((role, normalize_style(raw), text))
    return result


# ============================================================
# MARKDOWN RENDERER
# ============================================================

def to_teachfloor_md(paragraphs):
    lines      = []
    ol_n       = 0
    prev_role  = None
    in_lesson  = False
    quote_buf  = []

    def flush_quotes():
        for q in quote_buf:
            for ln in q.split("\n"):
                # FIX 3: preserve Markdown hard-break trailing spaces ("  ")
                # instead of rstrip()ing them away, which collapsed line
                # breaks inside blockquotes into merged paragraphs.
                suffix = "  " if ln.endswith("  ") else ""
                lines.append(f"> {ln.strip()}{suffix}")
        quote_buf.clear()

    for role, _style, text in paragraphs:
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
            prev_role = role
            continue

        if not in_lesson:
            lines.append("---")
            lines.append(f"# {text}")
            in_lesson = True
            prev_role = role
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
            # FIX 4: don't strip all asterisks (destroys literal * in content);
            # instead avoid double-wrapping by checking existing markers.
            t = text.strip()
            line = t if (t.startswith("**") and t.endswith("**")) else f"**{t}**"
            lines.append(line)
        elif role == "citation_role":
            flush_quotes()
            # FIX 4: same - only wrap if not already wrapped.
            t = text.strip()
            line = t if (t.startswith("*") and t.endswith("*")) else f"*{t}*"
            lines.append(line)
        elif role == "ul":
            lines.append(f"- {text.replace(chr(10), chr(10) + '  ')}")
        elif role == "ol":
            ol_n += 1
            lines.append(f"{ol_n}. {text.replace(chr(10), chr(10) + '   ')}")
        else:  # body
            if prev_role == "body":
                lines.append("")
            lines.append(text)

        prev_role = role

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
    # FIX 6: emit a warning so the user knows order is approximate.
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
    get_role       = make_get_role(style_map, settings["default_role"])
    extract_inline = make_inline_extractor(
        settings["bold_keywords"], settings["italic_keywords"]
    )

    designmap = find_designmap(folder)
    if not designmap:
        sys.exit(f"ERROR: No designmap*.xml found in {folder}")
    print(f"  Designmap  : {designmap.name}")

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

    # Output path: bare filename -> anchored to IDML folder (not CWD).
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
