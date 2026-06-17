# idml-to-teachfloor

![Version](https://img.shields.io/badge/version-1.1.0-blue)
![Python](https://img.shields.io/badge/python-3.9%2B-brightgreen)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

Convert an Adobe InDesign IDML file into Teachfloor-writer Markdown, ready for direct import into a Teachfloor course.

## What it does

Reads all `Story_*.xml` files from an unpacked IDML folder, orders them using the `StoryList` attribute in `designmap.xml` (InDesign's canonical page order), maps paragraph styles to semantic roles (lesson title, element title, quote, bullet, etc.), and writes a single collated Markdown file structured for the Teachfloor course writer.

## Quick start

```bash
# 1. Unpack the IDML (it is a ZIP archive)
unzip "MyReport.idml" -d MyReport-IDML/

# 2. Run the converter
python idml_to_teachfloor_md.py MyReport-IDML/ course-content.md

# 3. Import course-content.md into Teachfloor
```

**New to scripting?** See [INSTALL.md](INSTALL.md) for step-by-step instructions (no coding experience required).

## Requirements

- Python 3.9+
- No third-party dependencies (stdlib only: `xml.etree.ElementTree`, `re`, `pathlib`, `sys`)

## Output format

The script produces Markdown structured for the Teachfloor writer:

| Markdown | Teachfloor concept |
|---|---|
| `---` + `# Title` | New **Lesson** (module separator) |
| `# Title` | New **Content Element** |
| `## Heading` | Sub-heading inside an element |
| `> Quote text` | Verbatim direct quote / testimonial |
| `**Name**` | Citation name (bold attribution) |
| `*Role, Org, Country*` | Citation role (italic attribution) |
| `- item` | Bullet list |
| `1. item` | Numbered list |
| Plain paragraph | Body / editorial text |

## IDML folder layouts supported

Both flat and standard IDML layouts are detected automatically:

```
Flat (some export tools):        Standard (unzip of .idml):
  MyReport-IDML/                   MyReport-IDML/
    Story_u145de.xml                 Stories/
    Story_u175f9.xml                   Story_u145de.xml
    designmap.xml                      Story_u175f9.xml
                                     designmap.xml
                                     Resources/
                                     Spreads/
```

## Style map

Paragraph styles are mapped to roles in the `STYLE_MAP` dictionary at the top of the script. To adapt it for a different InDesign template:

1. Run the script once — unmapped styles fall back to `body`
2. Open the output, identify any mis-rendered paragraphs
3. Add or adjust entries in `STYLE_MAP`

Common roles:

| Role | Description |
|---|---|
| `lesson_title` | Starts a new Teachfloor lesson (`---` separator) |
| `element_title` | Starts a new content element within a lesson |
| `h2` | Sub-heading |
| `quote` | Rendered as `> blockquote` |
| `citation_name` | Bold attribution line after a quote |
| `citation_role` | Italic role/org/location line |
| `ul` | Unordered list item |
| `ol` | Ordered list item |
| `body` | Plain paragraph text |
| `skip` | Omitted entirely (headers, margins, TOC, copyright) |

## Known limitations

- **Inline images and graphics** are not extracted (text-only conversion)
- **Tables** are not supported
- **Footnotes** are dropped
- Multi-sentence runs joined by InDesign layout returns may produce missing spaces between sentences — check output for `word.NextWord` patterns

## Acknowledgements

The IDML XML structure documentation used to build this script draws on:

- [Adobe IDML Specification](https://www.adobe.com/devnet/indesign/idml.html) — Adobe Systems (public developer documentation)
- [idml-cookbook](https://github.com/Vinge1718/idml-cookbook) — community reference for IDML story and spread structure
- Developed with AI pair-programming assistance (Perplexity / Claude) for the [Geneva Learning Foundation](https://www.genevalearningfoundation.org/) Teach to Reach programme

## Tested on

Teach to Reach 11 report (*T2R-EN Malaria Turning the tide*, Geneva Learning Foundation / Roll Back Malaria, December 2024) — [`zenodo.15126588`](https://zenodo.org/record/15126588)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## License

MIT — see repository root for details.
