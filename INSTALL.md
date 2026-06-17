# Installation & Usage Guide

> **No coding experience required.** Follow these steps from top to bottom.

---

## What this script does

It converts an Adobe InDesign publication file (`.idml`) into a Markdown file you can paste directly into [Teachfloor](https://www.teachfloor.com/)'s course writer — preserving lessons, headings, body text, quotes, bullet lists, and contributor attributions.

---

## Step 1 — Install Python

The script runs on **Python 3.9 or later**. To check if you already have it:

1. Open **Terminal** (macOS / Linux) or **Command Prompt** (Windows)
2. Type this and press Enter:
   ```
   python --version
   ```
3. If you see `Python 3.9` or higher, skip to Step 2.
4. If you see an error or a version below 3.9, download Python from [python.org/downloads](https://www.python.org/downloads/) and run the installer.
   - On the Windows installer, tick **"Add Python to PATH"** before clicking Install.

> **No other packages are needed.** The script uses only Python's built-in libraries.

---

## Step 2 — Download the script

You do not need a GitHub account to download the file.

1. Go to the script page:  
   https://github.com/redasadki/openclaw-workspace/blob/main/scripts/idml-to-teachfloor/idml_to_teachfloor_md.py
2. Click the **Download raw file** button (↓ icon, top right of the code panel).
3. Save the file somewhere easy to find, for example your **Desktop** or a folder called `idml-converter`.

---

## Step 3 — Unpack your IDML file

An `.idml` file is a compressed archive (like a ZIP). You need to unpack it first.

**macOS / Linux:**
```bash
unzip "MyReport.idml" -d MyReport-IDML
```

**Windows (PowerShell):**
```powershell
Expand-Archive -Path "MyReport.idml" -DestinationPath "MyReport-IDML"
```

**Using a file manager (any OS):**
1. Rename the file extension from `.idml` to `.zip`
2. Double-click it to extract
3. Rename the resulting folder to something recognisable, e.g. `MyReport-IDML`

After unpacking you should see a folder containing files like `designmap.xml`, a `Stories/` subfolder with many `Story_*.xml` files, and `Resources/`.

---

## Step 4 — Run the script

1. Open **Terminal** (macOS / Linux) or **Command Prompt** / **PowerShell** (Windows).

2. Navigate to the folder where you saved the script.  
   Example on macOS:
   ```bash
   cd ~/Desktop/idml-converter
   ```
   Example on Windows:
   ```powershell
   cd C:\Users\YourName\Desktop\idml-converter
   ```

3. Run the script, pointing it at your unpacked IDML folder:
   ```bash
   python idml_to_teachfloor_md.py MyReport-IDML course-content.md
   ```
   Replace `MyReport-IDML` with the actual name of your unpacked folder,  
   and `course-content.md` with whatever you want to call the output file.

4. You will see output like:
   ```
     Designmap  : designmap.xml
     StoryList  : 210 story IDs
     Story files: 47 found
     Parsed     : 43 stories with content (4 skipped as empty)
     Paragraphs : 2847
     Output     : course-content.md  (214,879 chars)
     Lessons    : ~11    Elements: ~27
   ```

5. The file `course-content.md` is now ready to import into Teachfloor.

---

## Step 5 — Import into Teachfloor

1. Open your Teachfloor course in the course editor.
2. Use the **Import** or **Paste Markdown** option in the course writer.
3. Paste or upload the contents of `course-content.md`.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `python: command not found` | Try `python3` instead of `python` |
| `No module named ...` | You are running Python 2 — install Python 3.9+ |
| `ERROR: No designmap*.xml found` | The IDML was not fully unpacked, or you pointed at the wrong folder |
| Output is missing chapters | Not all Story XML files were extracted — re-unpack the full `.idml` |
| Bold text shows `**word: **` | Update to the latest version of the script (v1.1.0+) |

---

## Getting the latest version

To check your script version, open the file in a text editor and look for the line:
```python
__version__ = "1.1.0"
```
Or compare with the [CHANGELOG](CHANGELOG.md).

To update: simply re-download `idml_to_teachfloor_md.py` from Step 2 and replace your old copy.

---

## Reporting a problem

If something goes wrong, [open an issue](https://github.com/redasadki/openclaw-workspace/issues) on GitHub and include:
- The error message from your terminal
- The name and version of your `.idml` file
- Your operating system and Python version (`python --version`)
