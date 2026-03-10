# RemoveInlineScripts – Sigil Plugin

A Python plugin for [Sigil](https://sigil-ebook.com/) that lets you import
HTML files from your filesystem into the currently open epub while
automatically stripping all **inline** `<script>` tags (those without a
`src` attribute).

---

## What it does

1. Opens a **PySide6 QFileDialog** so you can choose any number of `.html`,
   `.htm`, or `.xhtml` files from your local filesystem.
2. For each selected file it uses a **regular expression** to remove every
   `<script>` tag that does **not** carry a `src` attribute (inline scripts).
   External script references (`<script src="…">`) are left untouched.
3. Adds the cleaned file to the current epub via the **Sigil BookContainer
   API** (`bk.addfile()`).  If the file already exists in the manifest its
   content is overwritten with `bk.writefile()`.

---

## Files

| File | Purpose |
|------|---------|
| `plugin.xml` | Plugin metadata consumed by Sigil |
| `plugin.py`  | Plugin implementation (entry point: `run(bk)`) |

---

## Requirements

* **Sigil ≥ 1.0.0** with the Python 3 plugin engine enabled.
* **PySide6** available to Sigil's Python interpreter:

  ```bash
  pip install PySide6
  ```

---

## Installation

1. Zip the two plugin files together (the zip must contain `plugin.xml` at
   its root):

   ```bash
   zip RemoveInlineScripts.zip plugin.xml plugin.py
   ```

2. In Sigil: **Plugins → Manage Plugins → Add Plugin** and select
   `RemoveInlineScripts.zip`.

---

## Usage

Open an epub in Sigil, then run the plugin from the **Plugins** menu (it will
appear under the *Edit* category).  A file picker dialog will open; select
the HTML / XHTML files you want to import and click **Open**.  The plugin
will process each file and print a summary to the Sigil plugin output window.

---

## How the inline-script regex works

```python
_INLINE_SCRIPT_RE = re.compile(
    r"<script\b(?![^>]*\bsrc\s*=)[^>]*>.*?</script[^>]*>"
    r"|"
    r"<script\b(?![^>]*\bsrc\s*=)[^>]*/\s*>",
    re.DOTALL | re.IGNORECASE,
)
```

* `<script\b` – matches the start of a `<script>` tag.
* `(?![^>]*\bsrc\s*=)` – **negative look-ahead**: skips the tag if `src=`
  appears anywhere before the closing `>`.
* `[^>]*>.*?</script[^>]*>` – consumes the tag body (lazy, so it stops at
  the first `</script>`); `[^>]*>` at the end tolerates malformed closing
  tags such as `</script   bar>`.
* `re.DOTALL` – allows `.` to match newlines, handling multi-line scripts.
* A second alternative handles the rare self-closing `<script … />` form.
