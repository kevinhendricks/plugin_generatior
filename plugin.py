#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sigil Plugin – RemoveInlineScripts
===================================
Prompts the user (via a PySide6 QFileDialog) to select any number of HTML /
XHTML files from the local filesystem.  For every selected file the plugin:

  1. Reads the raw file content.
  2. Uses a regular expression to remove every ``<script>`` tag that does
     **not** carry a ``src`` attribute (i.e. inline scripts).
  3. Adds the cleaned file to the currently open epub via the Sigil
     BookContainer API.

Entry point
-----------
Sigil calls ``run(bk)`` where *bk* is the BookContainer wrapper object
described in *Sigil_Plugin_Framework_rev15.epub*.
"""

import os
import re
import sys


# ---------------------------------------------------------------------------
# Regex used to strip inline <script> blocks
# ---------------------------------------------------------------------------
# Matches:
#   <script …>…</script>     – when the opening tag has NO src= attribute
#   <script …/>              – self-closing variant without src=
#
# The negative look-ahead  (?![^>]*\bsrc\s*=)  ensures that any <script>
# element that already references an external file is left untouched.
# re.DOTALL lets '.' match newlines so multi-line script blocks are handled.
# ---------------------------------------------------------------------------
_INLINE_SCRIPT_RE = re.compile(
    r"<script\b(?![^>]*\bsrc\s*=)[^>]*>.*?</script[^>]*>"
    r"|"
    r"<script\b(?![^>]*\bsrc\s*=)[^>]*/\s*>",
    re.DOTALL | re.IGNORECASE,
)

# MIME types keyed by (lower-cased) file extension
_MIME_MAP = {
    ".xhtml": "application/xhtml+xml",
    ".html": "text/html",
    ".htm": "text/html",
}


def _remove_inline_scripts(html_text: str) -> str:
    """Return *html_text* with all inline ``<script>`` tags removed."""
    return _INLINE_SCRIPT_RE.sub("", html_text)


def _select_files_via_dialog() -> list[str]:
    """
    Open a PySide6 QFileDialog and return the list of file paths chosen by
    the user.  Returns an empty list when the dialog is cancelled or when
    PySide6 is unavailable.
    """
    try:
        from PySide6.QtWidgets import QApplication, QFileDialog
    except ImportError:
        print(
            "ERROR: PySide6 is not installed.  "
            "Install it with:  pip install PySide6"
        )
        return []

    # Reuse an existing QApplication if Sigil already created one.
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    file_paths, _ = QFileDialog.getOpenFileNames(
        None,
        "Select HTML files to import into the epub",
        "",
        "HTML / XHTML Files (*.html *.htm *.xhtml);;All Files (*)",
    )
    return file_paths


def run(bk) -> int:
    """
    Plugin entry point called by Sigil.

    Parameters
    ----------
    bk:
        The Sigil BookContainer wrapper (see Sigil_Plugin_Framework_rev15.epub).

    Returns
    -------
    int
        0 on success, 1 on fatal error.
    """
    # ------------------------------------------------------------------
    # 1. Let the user pick one or more HTML files via a GUI dialog.
    # ------------------------------------------------------------------
    selected_paths = _select_files_via_dialog()

    if not selected_paths:
        print("No files selected – plugin cancelled without changes.")
        return 0

    # ------------------------------------------------------------------
    # 2. Process every selected file.
    # ------------------------------------------------------------------
    added = 0
    errors = 0

    for file_path in selected_paths:
        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower()
        mime = _MIME_MAP.get(ext, "text/html")

        # Build the in-epub href.  Sigil conventionally stores HTML under
        # "Text/"; adjust if your epub uses a different OPS structure.
        book_href = "Text/" + filename

        # Derive a manifest ID that is safe to use as an XML id attribute.
        # Replace any character that is not alphanumeric or a hyphen/
        # underscore with an underscore.
        manifest_id = re.sub(r"[^A-Za-z0-9_-]", "_", os.path.splitext(filename)[0])

        try:
            # Read the source file from the local filesystem.
            with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                raw_content = fh.read()

            # Strip inline script tags and record how many were removed.
            matches = _INLINE_SCRIPT_RE.findall(raw_content)
            removed_count = len(matches)
            cleaned_content = _INLINE_SCRIPT_RE.sub("", raw_content)
            print(
                f"  {filename}: removed {removed_count} inline script block(s)."
            )

            # ----------------------------------------------------------
            # Add (or overwrite) the file in the epub.
            #
            # BookContainer.addfile(uniqueid, href, data, mime_or_type)
            #   uniqueid    – manifest id for the new item
            #   href        – OPS href relative to the OPS directory
            #   data        – file content (str or bytes)
            #   mime_or_type – MIME type string
            #
            # If an item with the same href already exists Sigil will raise
            # an exception; in that case we fall back to writefile().
            # ----------------------------------------------------------
            try:
                bk.addfile(manifest_id, book_href, cleaned_content, mime)
                print(f"  {filename}: added to epub as '{book_href}'.")
            except Exception:
                # The file already exists in the manifest – overwrite it.
                # Retrieve the manifest id for the existing item.
                existing_id = None
                for mid, href, mime_type in bk.manifest_iter():
                    if href == book_href:
                        existing_id = mid
                        break
                if existing_id is not None:
                    bk.writefile(existing_id, cleaned_content)
                    print(
                        f"  {filename}: file already in epub – content updated."
                    )
                else:
                    raise

            added += 1

        except Exception as exc:
            print(f"ERROR processing '{file_path}': {exc}")
            errors += 1

    # ------------------------------------------------------------------
    # 3. Report summary.
    # ------------------------------------------------------------------
    print(
        f"\nDone – {added} file(s) successfully imported"
        + (f", {errors} error(s) encountered." if errors else ".")
    )
    return 0 if errors == 0 else 1
