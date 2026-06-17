# Changelog

All notable changes to this project are documented here.
This project follows [Semantic Versioning](https://semver.org/).

---

## [1.0.0] — 2026-06-17

### Added
- Initial release
- Reads full IDML unpacked folder; discovers Story XML files in both flat and `Stories/` subdirectory layouts
- Determines canonical reading order from `StoryList` attribute in `designmap.xml`
- Configurable `STYLE_MAP` mapping InDesign paragraph styles to Teachfloor Markdown roles
- Supported roles: `lesson_title`, `element_title`, `h2`, `quote`, `citation_name`, `citation_role`, `ul`, `ol`, `body`, `skip`
- Inline formatting: **bold**, *italic*, ***bold-italic*** extracted from `CharacterStyleRange` font attributes
- Whitespace trimmed from inside bold/italic markers (e.g. `**word: **` → `**word:**`)
- Multi-story collation into a single `output.md` file
- Stories with no content after filtering are silently skipped
- CLI: `python idml_to_teachfloor_md.py <folder> [output.md]`

### Style map covers
- T2R (Teach to Reach) report template styles validated against:
  - `citations` / `citations orange` — direct quotes
  - `executive quotes` / `chapo` — editorial body (not quotes)
  - `citation 2` / `citation 2 orange` — speaker name
  - `citations 3` / `citations 3 orange` — speaker role
  - `title 1` variants — lesson titles
  - `title 2` variants — element titles
  - `bullet *` variants — bullet lists
