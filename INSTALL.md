# Installation & Usage Guide

> **No coding experience required.** Follow these steps from top to bottom.

---

## What this script does

It converts an Adobe InDesign publication file (`.idml`) into a Markdown file you can paste directly into [Teachfloor](https://www.teachfloor.com/)'s course writer — preserving lessons, headings, body text, quotes, bullet lists, and contributor attributions.

---

## Step 1 — Install Python

The script runs on **Python 3.9 or later**.

1. Open **Terminal** (macOS / Linux) or **Command Prompt** (Windows)
2. Type and press Enter:
   ```
   python --version
   ```
3. If you see `Python 3.9` or higher, skip to Step 2.
4. If you see an error or a version below 3.9, download from [python.org/downloads](https://www.python.org/downloads/).
   - Windows: tick **"Add Python to PATH"** before clicking Install.

**Python 3.9 or 3.10 only** — run this once:
```
pip install tomli
```
Python 3.11+ includes TOML support automatically.

---

## Step 2 — Download the script

1. Go to: https://github.com/redasadki/teachfloor-idml
2. Click the green **Code** button → **Download ZIP**.
3. Extract the ZIP. You need both files:
   - `idml_to_teachfloor_md.py`
   - `styles.toml`
4. Put both in the same folder (e.g. your Desktop or `idml-converter/`).

---

## Step 3 — Unpack your IDML file

**macOS / Linux:**
```bash
unzip "MyReport.idml" -d MyReport-IDML
```

**Windows (PowerShell):**
```powershell
Expand-Archive -Path "MyReport.idml" -DestinationPath "MyReport-IDML"
```

**File manager:** rename `.idml` → `.zip`, extract, rename the folder.

---

## Step 4 — Bootstrap your style map

Run `--init` once to auto-generate a `styles.toml` for your document:

```bash
python3 idml_to_teachfloor_md.py MyReport-IDML/ --init
```

This creates `MyReport-IDML/styles.toml`. Open it in any text editor and correct lines marked `# TODO: verify`. The available roles are listed in comments at the top.

> **Working with multiple templates?** Use a named config per template:
> ```bash
> python3 idml_to_teachfloor_md.py MyReport-IDML/ --init --config my-template.toml
> ```

---

## Step 5 — Convert

```bash
python3 idml_to_teachfloor_md.py MyReport-IDML/ course-content.md
```

You will see:
```
  Config     : styles.toml (87 mappings, default_role='body')
  Designmap  : designmap.xml
  StoryList  : 210 story IDs
  Story files: 47 found
  Parsed     : 43 stories with content (4 skipped as empty)
  Paragraphs : 2847
  Output     : course-content.md  (214,879 chars)
  Lessons    : ~11    Elements: ~27
```

---

## Step 6 — Iterate

If the output needs corrections:

1. Open `MyReport-IDML/styles.toml`, fix the wrong role
2. Re-run Step 5

To add newly found styles without losing edits:
```bash
python3 idml_to_teachfloor_md.py MyReport-IDML/ --init
```
(This **merges** — existing mappings are untouched.)

---

## Step 7 — Import into Teachfloor

1. Open your course in the Teachfloor editor
2. Use **Import** / **Paste Markdown**
3. Upload or paste `course-content.md`

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `python: command not found` | Try `python3` |
| `No module named tomli` | `pip install tomli` (Python 3.9/3.10 only) |
| `ERROR: No designmap*.xml found` | IDML not fully unpacked, or wrong folder |
| All styles map to `body` | Run `--init` first |
| `# TODO: verify` entries | Open `styles.toml` and set the correct role |

---

## Getting the latest version

Check your version:
```python
__version__ = "1.3.0"
```

To update: download the ZIP again and replace `idml_to_teachfloor_md.py`. Your `styles.toml` is not affected.

---

## Reporting a problem

[Open an issue](https://github.com/redasadki/teachfloor-idml/issues) with:
- The error message
- Your OS and Python version (`python --version`)
- The name/version of your `.idml` file
