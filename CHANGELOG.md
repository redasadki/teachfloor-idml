# Changelog

All notable changes to this project are documented here.
This project follows [Semantic Versioning](https://semver.org/).

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
