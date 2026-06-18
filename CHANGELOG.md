# Changelog

All notable changes to this project are documented here.
This project follows [Semantic Versioning](https://semver.org/).

---

## [1.4.0] — 2026-06-18

### Added
- **Font-size heuristic** (`headline_point_size` setting) — body paragraphs
  whose largest `PointSize` attribute meets or exceeds the configured threshold
  are automatically promoted to `element_title`, starting a new Teachfloor
  content element. This solves the problem of special pages (coloured
  backgrounds, large display headlines) that were not being recognised as
  separate elements because the layout artist sized up body text directly
  instead of applying a heading paragraph style.
- **`_paragraph_point_size()` helper** — scans all `CharacterStyleRange`
  children of a paragraph for `PointSize` attributes (inline and inside
  `<Properties>`), returns the maximum value found, or `0.0` if absent.
- **`headline_point_size` key in `_DEFAULT_SETTINGS`** — default value `40.0`
  pt. Set to `0` to disable the heuristic entirely.
- **`headline_point_size` documented in `styles.toml`** — configuration
  template updated with the new key and its rationale.
- **`parse_story()` signature extended** — accepts `headline_point_size: float
  = 0.0`; `convert_folder()` passes `settings.get("headline_point_size", 0.0)`
  through to it on every story.

### How it works

For each `ParagraphStyleRange` in a story:
1. The paragraph style name is resolved to a role via `styles.toml`.
2. If the resolved role is `body` **and** `headline_point_size > 0`, the
   paragraph's maximum point size is checked.
3. If the point size is >= `headline_point_size`, the role is overridden to
   `element_title`.
4. All other paragraphs are unaffected.

The heuristic fires only when the style map has already classified a paragraph
as `body` (no heading style was applied). Paragraphs matched explicitly by
a style-map rule are never touched.

---

## [1.3.0] — 2026-06-18

### Added
- **`--init` flag** — scans the IDML folder and generates (or merges into) a
  `styles.toml` with every paragraph style found in the document, implementing
  the "scaffold then edit" pattern used by tools such as `eslint --init` and
  `black`
- **Heuristic role guesser** (`_guess_role`) — maps style names to roles using
  keyword rules (`"title 1"` → `lesson_title`, `"bullet"` → `ul`,
  `"copyright"` → `skip`, etc.). Uncertain guesses flagged with
  `# TODO: verify`. Expected accuracy ~70–80% on first run
- **`--force` flag** — used with `--init`; regenerates the TOML completely
  instead of merging
- **Merge behaviour** — `--init` without `--force` preserves all existing
  entries and appends only new styles, protecting prior human edits
- **Three-tier config search** (`resolve_config_path`) — checks
  `<idml_folder>/styles.toml` first, then `<script_dir>/styles.toml`, then
  built-in defaults. `--config` flag still takes absolute priority
- `discover_all_styles()` helper scans all Story XML files for unique styles

### Fixed
- Python 3.9/3.10 type-hint compatibility: `Path | None` union syntax replaced
  with untyped signatures to avoid `TypeError` at import time
- `flush_quotes()` no longer uses `nonlocal` unnecessarily
- README version badge corrected (`1.1.0` → `1.3.0`)
- INSTALL.md download link updated to `redasadki/teachfloor-idml`

---

## [1.2.0] — 2026-06-17

### Added
- Style mappings extracted from script into `styles.toml`
- `[style_map]` and `[settings]` TOML sections
- `--config FILE` CLI flag for per-project configs
- Three-layer config fallback with warning
- TOML loading via `tomllib` / `tomli` backport
- Role validation with `[WARN]` on unknown roles

---

## [1.1.0] — 2026-06-17

### Fixed
- Whitespace inside bold/italic markers trimmed correctly
- Stories sorted by `StoryList` canonical order

---

## [1.0.0] — 2026-06-17

### Added
- Initial release
- Reads IDML unpacked folder (flat and `Stories/` layouts)
- Reading order from `StoryList` in `designmap.xml`
- Style map → Teachfloor Markdown roles
- Inline bold / italic / bold-italic from `CharacterStyleRange`
- Multi-story collation to single output file
- CLI: `python idml_to_teachfloor_md.py <folder> [output.md]`
