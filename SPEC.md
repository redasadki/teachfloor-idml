# IDML Package Structure — Developer Specification

> ⚠️ **STATUS: DEVELOPER WORKING NOTE — NOT NORMATIVE**
>
> This document is an internal working note compiled to help a senior developer
> continue this project. It has **not** been validated against the formal Adobe
> IDML File Format Specification. Some details are drawn from Adobe-format
> structure references and community documentation, cross-checked where
> possible but **not** authoritatively confirmed.
>
> **Before treating any statement here as normative**, obtain the official
> *Adobe InDesign IDML File Format Specification* (distributed via the InDesign
> Plugin SDK / Adobe developer documentation) and verify all element names,
> attribute names, and structural claims against it.

---

> **Purpose**: Reference for developers maintaining `idml_to_teachfloor_md.py`.
> Describes the structure, file nomenclature, and XML elements of Adobe IDML
> packages that this converter reads.
>
> **Scope**: This document covers only the parts of the IDML format that the
> converter touches (text content and reading order). It is not a complete
> IDML reference. For the full format, consult the primary sources listed at
> the end.

---

## 1. What IDML is

IDML (InDesign Markup Language) is Adobe InDesign's XML-based interchange
format, introduced with InDesign CS4. It is the backward-compatible,
inspectable alternative to the binary `.indd` format. An IDML file represents
the objects and properties of an InDesign document as XML elements and
attributes.

A `.idml` file is a **ZIP archive**. It can be unpacked with any ZIP tool
(`unzip`, Expand-Archive, etc.) and read without launching InDesign.

The XML namespace used by package-level wrapper elements is:

```
http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging
```

This is the canonical Adobe packaging namespace and is referenced in the
converter as `IDML_NS`.

---

## 2. Package layout

When unpacked, an IDML package contains the following top-level parts. The
converter only reads `designmap.xml` and the `Stories/` directory; the rest is
listed for context.

```
MyDocument-IDML/
├── mimetype                 First entry; contains the IDML MIME type string
├── META-INF/
│   ├── container.xml        Identifies the root content file (designmap.xml)
│   └── manifest.xml         Lists all parts in the package
├── designmap.xml            Master manifest — lists every component + reading order
├── Resources/
│   ├── Fonts.xml
│   ├── Graphic.xml
│   ├── Preferences.xml
│   └── Styles.xml           Global paragraph/character/object/table style defs
├── Styles/                  (style definition parts, when present)
├── Stories/
│   ├── Story_<id>.xml       One file per story (text flow) — THE TEXT CONTENT
│   └── ...
├── Spreads/
│   ├── Spread_<id>.xml      Page/spread layout: text frames, image frames, geometry
│   └── ...
├── MasterSpreads/
│   └── MasterSpread_<id>.xml Master page definitions (headers, footers, grids)
└── XML/
    ├── BackingStory.xml     Top-level content↔structure associations
    ├── Tags.xml
    └── Mapping.xml
```

> **Note on layouts**: Some export tools produce a *flat* layout where
> `Story_*.xml` files sit in the package root rather than inside `Stories/`.
> The converter's `discover_stories()` checks both the root and `Stories/`.

---

## 3. File nomenclature

| Part | Filename pattern | Notes |
|---|---|---|
| Master manifest | `designmap.xml` | Always present at package root. The converter globs `designmap*.xml`. |
| Story | `Story_<Self>.xml` | `<Self>` is the story's `Self` identifier (e.g. `Story_u145de.xml`). |
| Spread | `Spread_<Self>.xml` | One per spread. |
| Master spread | `MasterSpread_<Self>.xml` | One per master page. |

The `<id>` / `<Self>` portion is an opaque InDesign object identifier, usually
prefixed with `u` followed by a base-36-like string (e.g. `u145de`). It is
**not** a sequential page number and carries no inherent ordering — ordering
comes from `designmap.xml` (see §5).

---

## 4. designmap.xml

`designmap.xml` is the master manifest. It contains a single `<Document>`
element that references every other part of the package via `idPkg:`-namespaced
child elements.

Minimal example (from the IDML cookbook):

```xml
<?xml version="1.0" encoding="utf-8"?>
<?aid style="50" type="document" readerVersion="6.0" featureSet="257"?>
<Document
  xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"
  DOMVersion="7.0" Self="d">
  <idPkg:Spread src="Spreads/Spread_spread1.xml"/>
  <idPkg:Story src="Stories/Story_story1.xml"/>
</Document>
```

Key attributes the converter uses:

- **`StoryList`** (on `<Document>`): a space-separated list of story `Self`
  identifiers in InDesign's canonical reading order. This is the primary
  signal the converter uses to order stories. See `get_story_order()`.
- **`idPkg:Story/@src`**: relative path to each story XML file. Used as a
  fallback ordering source when `StoryList` is absent.

---

## 5. Determining reading order

Stories in `Stories/` are stored without inherent order; a story is text
content abstracted from its placement. To reconstruct document reading order:

1. **Primary method (converter default)**: read the `StoryList` attribute on
   the `<Document>` element in `designmap.xml`. It enumerates story `Self` IDs
   in page order.
2. **Fallback method**: if `StoryList` is absent, the converter collects
   `idPkg:Story/@src` references in document order.

> **Authoritative cross-check (per Adobe/community reference)**: the fully
> rigorous method walks the layout — read spread order from `designmap.xml`,
> then within each `Spread_*.xml` read `<TextFrame>` order and follow each
> frame's `ParentStory` reference to the matching `Story_*.xml`. The converter
> uses the simpler `StoryList` approach, which is sufficient for
> single-frame-per-story documents. **A senior developer extending this tool
> for complex multi-frame threaded layouts should implement the
> spread→TextFrame→ParentStory walk.**

---

## 6. Story XML structure

Each `Story_*.xml` file is wrapped in an `idPkg:Story` packaging element and
contains a `<Story>` element. Text is organised as a hierarchy:

```
<idPkg:Story>
  <Story Self="...">
    <ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/...">
      <CharacterStyleRange AppliedCharacterStyle="CharacterStyle/...">
        <Content>The actual text</Content>
      </CharacterStyleRange>
    </ParagraphStyleRange>
  </Story>
</idPkg:Story>
```

### Element reference

| Element | Meaning | Converter usage |
|---|---|---|
| `<Story>` | The text flow container | Root iterated via `root.iter("ParagraphStyleRange")` |
| `<ParagraphStyleRange>` | A run of text sharing one paragraph style | One paragraph; mapped to a semantic role |
| `<CharacterStyleRange>` | A run within a paragraph sharing one character style | Inline bold/italic detection |
| `<Content>` | The literal text string | Concatenated to build paragraph text |
| `<Br/>` | Forced line/paragraph break | (Not currently handled specially) |

### Key attributes

| Attribute | On element | Meaning |
|---|---|---|
| `AppliedParagraphStyle` | `ParagraphStyleRange` | The paragraph style, e.g. `ParagraphStyle/$ID/Title 1`. The converter strips the `ParagraphStyle/` / `$ID/` prefix and lowercases it (`normalize_style()`), then maps it via `styles.toml`. |
| `AppliedCharacterStyle` | `CharacterStyleRange` | The character style, e.g. `CharacterStyle/$ID/[No character style]`. Inspected for bold/italic keywords. |
| `FontStyle` | `CharacterStyleRange` / `Properties` | Font weight/style name (e.g. `Bold`, `Italic`, `Semibold`). The converter scans this for bold/italic keywords defined in `styles.toml`. |

> **Style name nomenclature**: paragraph/character style references take the
> form `<Type>/<group?>/$ID/<name>` or `<Type>/<name>`. The `$ID/` segment
> denotes an application-default (untranslated) style name. `normalize_style()`
> handles both by taking the final path segment.

### Special characters

InDesign encodes certain non-text markers as processing instructions inside
`<Content>`, e.g. an auto page-number marker:

```xml
<Content><?ACE 18?></Content>
```

These are not plain text and may require special handling if encountered.

---

## 7. Styles: local vs. global

- **Global styles** are defined once in `Resources/Styles.xml` (and the
  `Styles/` parts): the catalogue of all paragraph, character, object, and
  table styles, with their full formatting properties.
- **Local styles / overrides** are expressed inline within story files on the
  `ParagraphStyleRange` / `CharacterStyleRange` elements.

The converter relies on the **style name reference** (the `AppliedParagraphStyle`
attribute), not on resolving the full style definition from `Resources/`. This
is why the `styles.toml` mapping is keyed by style *name*, not by resolved
visual formatting.

---

## 8. What the converter deliberately ignores

| IDML feature | Location | Why ignored |
|---|---|---|
| Images / graphics | `Spreads/`, `Resources/` | Text-only conversion |
| Tables | `<Table>` in stories | Not supported |
| Footnotes | `<Footnote>` in stories | Dropped |
| Layout geometry | `Spreads/`, `MasterSpreads/` | Reading order taken from `StoryList` instead |
| Style definitions | `Resources/Styles.xml` | Mapping is by style name, not resolved formatting |
| Hyperlinks | story / `designmap.xml` | Not extracted |

---

## 9. Primary sources

This document is built only from official and authoritative references:

- **Adobe InDesign IDML File Format Specification** — Adobe Systems. The formal
  specification, distributed with the InDesign Plugin SDK / InDesign developer
  documentation (CS5 edition). This is the canonical source of record.
- **Adobe IDML packaging namespace** — `http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging`,
  as declared in `designmap.xml`.
- **Adobe InDesign developer documentation** — https://www.adobe.com/devnet/indesign/idml.html

Community/reference material consulted for the reading-order walk (cross-checked
against, not substituted for, Adobe sources): the IDML cookbook and
long-standing developer Q&A describing the `designmap → Spread → TextFrame →
ParentStory` resolution.

> **For maintainers**: when extending the converter (tables, footnotes,
> threaded multi-frame stories, page-number markers), obtain the formal Adobe
> IDML File Format Specification from the InDesign SDK and verify element and
> attribute names against it before implementing. Do not infer schema details
> from sample files alone.
