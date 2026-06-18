# Changelog

All notable changes to this project are documented here.
This project follows [Semantic Versioning](https://semver.org/).

---

## [1.3.7] — 2026-06-18

### Fixed
- **Spurious line breaks before hyperlinks** — `_run_text` and
  `_collect_hls_text` were appending `child.tail` (the XML whitespace
  between elements used for indentation) as if it were document content.
  In IDML story XML every element tail is purely formatting whitespace
  (`\n\t\t\t`); the only genuine in-paragraph line separators are `<Br/>`
  elements and `\u2028` (LINE SEPARATOR) characters inside `<Content>`
  nodes. Dropping all tail appends removes the unwanted hard-break that
  appeared before every hyperlink (e.g. the line break before the email
  address in the Contact paragraph).

---

## [1.3.6] — 2026-06-18

### Fixed
- **Truncated URL display text** — InDesign sometimes wraps only part of a
  URL inside the `<HyperlinkTextSource>` element (e.g.
  `https://doi.org/10.5281/zenodo.`) and places the remainder (`15126588`)
  as a plain `<Content>` sibling in the same `CharacterStyleRange`. The
  old recursive `_walk` had no ability to look ahead.

  `_run_text` now iterates CSR children by index. When a
  `HyperlinkTextSource` display text ends with `.` or `/` (a truncated
  URL), the immediately following sibling is checked: if it is a bare
  `<Content>` node with no whitespace in its text, that text is appended
  to the display and the sibling index is advanced so the fragment is not
  emitted again as plain text.

  Result: `[https://doi.org/10.5281/zenodo.15126588](url)` instead of
  `[https://doi.org/10.5281/zenodo.](url)15126588`.

---

## [1.3.5] — 2026-06-18

### Fixed
- `parse_hyperlink_map()` now percent-decodes URLs (InDesign stores them
  as e.g. `https%3a//...`), strips InDesign duplicate-name suffixes
  (` 1`, ` 2` etc.), and falls back to the Hyperlink `Name` attribute for
  destinations of type `list` (used for simple URL/email hyperlinks that
  have no shared URL-destination element).
- `parse_story()` collapses runs of 2+ consecutive hard-break sequences
  (`  \n`) down to a single one, removing spurious blank lines that
  InDesign inserts around every hyperlink via extra `<Br/>` nodes.
- `_merge_stray_fragments()` joins any hard-break line consisting solely
  of digits/punctuation onto the preceding content line, preventing lone
  `.` or DOI suffix fragments from appearing as separate lines.

---

## [1.3.4] — 2026-06-18

### Added
- `parse_hyperlink_map()` — reads `<Hyperlink>` entries from
  `designmap.xml` and builds a `{source_id -> url}` lookup.
- `_run_text()` — wraps `<HyperlinkTextSource>` content as
  `[display](url)` Markdown links.
- `to_teachfloor_md()` — joins consecutive same-style body paragraphs
  that end without sentence-closing punctuation (InDesign splits single
  visual lines at hyperlink boundaries into multiple PSRs).

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
- `_paragraph_point_size()` helper — scans all `CharacterStyleRange`
  children of a paragraph for `PointSize` attributes (inline and inside
  `<Properties>`), returns the maximum value found, or `0.0` if absent.
- `headline_point_size` key in `_DEFAULT_SETTINGS` — default value `40.0` pt.
  Set to `0` to disable the heuristic entirely.
- `headline_point_size` documented in `styles.toml`.
- `parse_story()` signature extended — accepts `headline_point_size: float
  = 0.0`; `convert_folder()` passes the setting through on every story.

---

## [1.3.0] — 2026-06-18

### Added
- **`--init` flag** — scans the IDML folder and generates (or merges into) a
  `styles.toml` with every paragraph style found in the document.
- **Heuristic role guesser** (`_guess_role`) — maps style names to roles using
  keyword rules. Uncertain guesses flagged with `# TODO: verify`.
- **`--force` flag** — used with `--init`; regenerates the TOML completely.
- **Merge behaviour** — `--init` without `--force` preserves all existing
  entries and appends only new styles.
- **Three-tier config search** (`resolve_config_path`).
- `discover_all_styles()` helper.

### Fixed
- Python 3.9/3.10 type-hint compatibility.
- `flush_quotes()` closure fix.
- README version badge corrected.
- INSTALL.md download link updated.

---

## [1.2.0] — 2026-06-17

### Added
- Style mappings extracted from script into `styles.toml`.
- `[style_map]` and `[settings]` TOML sections.
- `--config FILE` CLI flag for per-project configs.
- Three-layer config fallback with warning.
- TOML loading via `tomllib` / `tomli` backport.
- Role validation with `[WARN]` on unknown roles.

---

## [1.1.0] — 2026-06-17

### Fixed
- Whitespace inside bold/italic markers trimmed correctly.
- Stories sorted by `StoryList` canonical order.

---

## [1.0.0] — 2026-06-17

### Added
- Initial release.
- Reads IDML unpacked folder (flat and `Stories/` layouts).
- Reading order from `StoryList` in `designmap.xml`.
- Style map → Teachfloor Markdown roles.
- Inline bold / italic / bold-italic from `CharacterStyleRange`.
- Multi-story collation to single output file.
- CLI: `python idml_to_teachfloor_md.py <folder> [output.md]`.
