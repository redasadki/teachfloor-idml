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
    python3 idml_to_teachfloor_md.py <idml_folder> [output.md] [--config styles.toml]

    <idml_folder>   Directory containing Story XML files and a designmap*.xml
    [output.md]     Output path (default: <idml_folder>/output.md)
    --config FILE   Path to a TOML config file (default: styles.toml next to script)

Configuration:
    All style mappings and conversion settings live in styles.toml.
    The script reads styles.toml from the same directory as itself by default.
    Use --config to point at a different file (e.g. per-project configs).
    If no config file is found, built-in defaults are used with a warning.

    See styles.toml for full documentation of all settings.
"""

__version__ = "1.2.0"

import sys
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

# ---------------------------------------------------------------------------
# TOML loading — stdlib tomllib (Python 3.11+) or tomli backport (3.9/3.10)
# ---------------------------------------------------------------------------
try:
    import tomllib          # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # pip install tomli
    except ImportError:
        tomllib = None


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

VALID_ROLES = frozenset({
    "lesson_title", "element_title", "h2",
    "quote", "citation_name", "citation_role",
    "ul", "ol", "body", "skip",
})


# ============================================================
# CONFIG LOADER
# ============================================================

def load_config(config_path: Path) -> tuple[dict, dict]:
    """
    Load styles.toml and return (settings, style_map).
    Falls back to built-in defaults if the file is missing or TOML unavailable.
    Validates roles and warns on unknown values.
    """
    if not config_path.exists():
        print(f"  [INFO] No config file at {config_path} — using built-in defaults.",
              file=sys.stderr)
        return _DEFAULT_SETTINGS.copy(), _DEFAULT_STYLE_MAP.copy()

    if tomllib is None:
        print(
            "  [WARN] TOML support unavailable.\n"
            "         Python 3.11+ includes tomllib automatically.\n"
            "         For Python 3.9/3.10: pip install tomli\n"
            "         Falling back to built-in defaults.",
            file=sys.stderr,
        )
        return _DEFAULT_SETTINGS.copy(), _DEFAULT_STYLE_MAP.copy()

    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        sys.exit(f"ERROR: Could not read config file {config_path}: {e}")

    settings = {**_DEFAULT_SETTINGS, **data.get("settings", {})}

    raw_map   = data.get("style_map", {})
    style_map = {}
    for style, role in raw_map.items():
        style_lower = style.lower().strip()
        role_lower  = role.lower().strip()
        if role_lower not in VALID_ROLES:
            print(f"  [WARN] Unknown role '{role}' for style '{style}' — skipping.",
                  file=sys.stderr)
            continue
        style_map[style_lower] = role_lower

    print(f"  Config     : {config_path.name} "
          f"({len(style_map)} style mappings, "
          f"default_role='{settings['default_role']}')")
    return settings, style_map


# ============================================================
# XML PARSING
# ============================================================

def normalize_style(raw: str) -> str:
    """Strip IDML path prefix and normalize to lowercase."""
    return raw.split("/")[-1].replace("$ID/", "").strip().lower()


def make_get_role(style_map: dict, default_role: str):
    """Return a role-resolver closed over the loaded style_map."""
    def get_role(raw: str) -> str:
        norm = normalize_style(raw)
        if norm in style_map:
            return style_map[norm]
        for key, role in style_map.items():
            if key and key in norm:
                return role
        return default_role
    return get_role


def _has_font_keyword(cr, keywords: list) -> bool:
    for attr in ("FontStyle", "AppliedCharacterStyle"):
        if any(k in cr.get(attr, "").lower() for k in keywords):
            return True
    for prop in cr.iter("Properties"):
        for e in prop.iter("FontStyle"):
            if e.text and any(k in e.text.lower() for k in keywords):
                return True
    return False


def make_inline_extractor(bold_keywords: list, italic_keywords: list):
    """Return an inline-text extractor closed over font keyword lists."""
    def extract_inline(para) -> str:
        pieces = []
        for cr in para:
            if cr.tag != "CharacterStyleRange":
                continue
            bold   = _has_font_keyword(cr, bold_keywords)
            italic = _has_font_keyword(cr, italic_keywords)
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
    return extract_inline


def parse_story(xml_bytes: bytes, get_role, extract_inline) -> list:
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
# MARKDOWN RENDERER
# ============================================================

def to_teachfloor_md(paragraphs: list) -> str:
    """
    Render (role, style, text) tuples → Teachfloor-writer Markdown.
    """
    lines      = []
    ol_n       = 0
    prev_role  = None
    in_lesson  = False
    quote_buf  = []

    def flush_quotes():
        nonlocal quote_buf
        for q in quote_buf:
            lines.append(f"> {q}")
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
            lines.append(f"**{text.replace('**', '').strip()}**")
        elif role == "citation_role":
            flush_quotes()
            lines.append(f"*{text.replace('*', '').strip()}*")
        elif role == "ul":
            lines.append(f"- {text}")
        elif role == "ol":
            ol_n += 1
            lines.append(f"{ol_n}. {text}")
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

IDML_NS = "http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"


def find_designmap(folder: Path) -> Path | None:
    for candidate in sorted(folder.glob("designmap*.xml")):
        return candidate
    return None


def get_story_order(designmap_path: Path) -> list[str]:
    root = ET.fromstring(designmap_path.read_bytes())
    story_list_str = root.attrib.get("StoryList", "")
    if story_list_str:
        return story_list_str.split()
    ids = [
        elem.get("src", "").split("/")[-1].replace("Story_", "").replace(".xml", "")
        for elem in root.iter(f"{{{IDML_NS}}}Story")
    ]
    return list(reversed([i for i in ids if i]))


def discover_stories(folder: Path) -> dict[str, Path]:
    stories: dict[str, Path] = {}
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


def convert_folder(folder: Path, output_path: Path | None, config_path: Path) -> str:
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

    if output_path is None:
        output_path = folder / "output.md"
    output_path.write_text(md, encoding="utf-8")

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
  python3 idml_to_teachfloor_md.py MyReport-IDML/
  python3 idml_to_teachfloor_md.py MyReport-IDML/ course.md
  python3 idml_to_teachfloor_md.py MyReport-IDML/ course.md --config t2r11.toml
""",
    )
    parser.add_argument("idml_folder", help="Path to the unpacked IDML folder")
    parser.add_argument("output", nargs="?", default=None,
                        help="Output Markdown file (default: <idml_folder>/output.md)")
    parser.add_argument("--config", default=None,
                        help="Path to TOML config file "
                             "(default: styles.toml next to this script)")
    args = parser.parse_args()

    folder = Path(args.idml_folder)
    if not folder.is_dir():
        sys.exit(f"ERROR: Not a directory: {folder}")

    output      = Path(args.output) if args.output else None
    config_path = Path(args.config) if args.config else Path(__file__).parent / "styles.toml"

    convert_folder(folder, output, config_path)


if __name__ == "__main__":
    main()
