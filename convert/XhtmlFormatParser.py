#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XhtmlFormatParser – Python conversion of the Qt C++ XhtmlFormatParser class.

When pretty-printing XHTML the user would like control over the format chosen.
This module parses the user's prettyprinter.pcss file to determine where and
when to inject new lines, add indentation, and condense text.

The prettyprinter.pcss is a pseudo-CSS structure whose selectors may only
include element (tag) names and immediate child-descendant combinators that
are also element names.

There are 2 global parameters that must appear at the top of the file before
any selectors.  They are *not* used inside braces '{'.

  @css-fold: true|false;     # specifies whether the CSS of the style node
                             # is collapsed.  Default: false.

  @indent: int1;             # number of spaces per indentation level.
                             # Range 0–4, default 2.

There are 6 possible per-selector properties:

  opentag-br: int1 int2;    # new lines *before* (int1) and *after* (int2)
                             # an opening tag.  Each 0–9, default 0.

  closetag-br: int1 int2;   # new lines *before* (int1) and *after* (int2)
                             # a closing tag.  Each 0–9, default 0.

  ind-adj: int1;             # adjusts the indent level of the node.
                             # Range -9 to 9.

  inner-ind-adj: int1;       # adjusts the indentation level *within* a node
                             # but excluding the node itself.  Range -9 to 9.

  attr-fm-resv: true|false;  # preserve spaces/newlines inside the opening
                             # tag.  Default false.

  text-fm-resv: true|false;  # preserve spaces/newlines in the node's text.
                             # Default false.

Original C++ classes: XhtmlFormatParser.h / XhtmlFormatParser.cpp (Qt)
"""

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

UNDEFINED_PROP = -100

DEFAULT_CONF = (
    "/* global settings */\n"
    "  @indent 2;\n"
    "  @css-fold false;\n"
    "\n"
    "  /* block-level elements */\n"
    "  html, body, p, div, h1, h2, h3, h4, h5, h6, ol, ul, li, address, blockquote,"
    " dd, dl, fieldset, form, hr, nav, menu, pre, table, tr, td, th, article {\n"
    "      opentag-br : 1 0;\n"
    "      closetag-br: 0 1;\n"
    "  }\n"
    "  p, div {\n"
    "      opentag-br : 1 0;\n"
    "      closetag-br: 0 2;\n"
    "  }\n"
    "\n"
    "  /* head elements */\n"
    "  head, meta, link, title, style, script {\n"
    "      opentag-br : 1 0;\n"
    "      closetag-br: 0 1;\n"
    "  }\n"
    "\n"
    "  /* xml header */\n"
    "  ?xml {\n"
    "      opentag-br: 0 1;\n"
    "  }\n"
    "\n"
    "  /* doctype */\n"
    "  !DOCTYPE {\n"
    "      opentag-br  : 1 2;\n"
    "      attr-fm-resv: true;\n"
    "  }\n"
    "\n"
    "  /* xhtml element */\n"
    "  html {\n"
    "    inner-ind-adj:-1;\n"
    "  }\n"
    "\n"
    "  /* comment */\n"
    "  !-- {\n"
    "      attr-fm-resv: true;\n"
    "  }\n"
    "\n"
    "  /* main */\n"
    "  body {\n"
    "      opentag-br : 2 1;\n"
    "      closetag-br: 1 1;\n"
    "  }\n"
    "\n"
    "  h1,h2,h3,h4,h5,h6 {\n"
    "      opentag-br : 2 0;\n"
    "      closetag-br: 0 2;\n"
    "  }\n"
    "\n"
    "  pre {\n"
    "    text-fm-resv: true;\n"
    "  }\n"
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class SortMode(Enum):
    """Controls the ordering of selectors returned by getAllSelectors()."""
    ORI     = auto()   # original (insertion) order
    ASCEND  = auto()   # ascending specificity weight
    DESCEND = auto()   # descending specificity weight


@dataclass
class GlobalProps:
    """Container for the two file-level (@) directives."""
    indent:  int = UNDEFINED_PROP   # number of spaces per indent level
    cssfold: int = UNDEFINED_PROP   # 1 = fold CSS, 0 = don't fold, UNDEFINED_PROP = not set


@dataclass
class Properties:
    """Per-selector formatting properties."""
    open_pre_br:   int = UNDEFINED_PROP  # new lines before the opening tag
    open_post_br:  int = UNDEFINED_PROP  # new lines after the opening tag
    close_pre_br:  int = UNDEFINED_PROP  # new lines before the closing tag
    close_post_br: int = UNDEFINED_PROP  # new lines after the closing tag
    ind_adj:       int = UNDEFINED_PROP  # indent-level adjustment for the node
    inner_ind_adj: int = UNDEFINED_PROP  # indent-level adjustment inside the node
    attr_fm_resv:  int = UNDEFINED_PROP  # 1 = preserve attr whitespace, 0 = don't
    text_fm_resv:  int = UNDEFINED_PROP  # 1 = preserve text whitespace, 0 = don't


# ---------------------------------------------------------------------------
# Pre-compiled regular expressions (module level for performance)
# ---------------------------------------------------------------------------

_RE_INT         = re.compile(r'^-?\d+$')
_RE_INT_INT     = re.compile(r'^\d+ \d+$')
_RE_BOOL        = re.compile(r'true|false')
_RE_WILDCARD    = re.compile(r'[^ ]\*|\*[^ :]')
_RE_INDENT      = re.compile(r'@indent (\d+);')
_RE_CSSFOLD     = re.compile(r'@css-fold (true|false);')
_RE_RULE        = re.compile(r'([a-zA-Z?!_\-\*][a-zA-Z\d_,\- \*]*?)\{(.*?)\}', re.DOTALL)

_BLANK_CHARS    = set(' \n\t')
_PUNCT_CHARS    = set('{};:,')


# ---------------------------------------------------------------------------
# XhtmlFormatParser class
# ---------------------------------------------------------------------------

class XhtmlFormatParser:
    """
    Parses a pseudo-CSS file (prettyprinter.pcss) that controls how XHTML
    source files are pretty-printed.

    Usage
    -----
    parser = XhtmlFormatParser()                  # use built-in defaults
    parser = XhtmlFormatParser(open(...).read())  # use a custom .pcss file

    # Retrieve global settings
    indent_spaces = parser.global_props.indent    # -100 means "not set"

    # Retrieve per-selector properties
    props = parser.getSelectorProperties("body")  # returns a Properties object

    # Iterate selectors in descending-specificity order
    for sel in parser.getAllSelectors(SortMode.DESCEND):
        ...
    """

    def __init__(self, conf_text: str = "") -> None:
        self.global_props: GlobalProps = GlobalProps()
        # Cache: selector path -> resolved Properties (avoids re-computation)
        self.path_props_cache: Dict[str, Properties] = {}

        self._selectors: List[str] = []
        self._properties_map: Dict[str, Properties] = {}
        self._ori_conf_text: str = conf_text if conf_text else self.getDefaultConfigure()

        self._parse()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def getAllSelectors(self, mode: SortMode = SortMode.ORI) -> List[str]:
        """Return the list of all parsed selectors in the requested order."""
        if mode == SortMode.ORI:
            return list(self._selectors)
        elif mode == SortMode.ASCEND:
            return self._orderingSelectors(descending=False)
        elif mode == SortMode.DESCEND:
            return self._orderingSelectors(descending=True)
        return list(self._selectors)

    def getSelectorProperties(self, selector: str) -> Properties:
        """Return the Properties recorded for *selector*, or a default (all
        UNDEFINED_PROP) instance when the selector was not found."""
        return self._properties_map.get(selector, Properties())

    def getCleanConfText(self) -> str:
        """Strip C-style block comments (``/* … */``) and normalise
        consecutive whitespace from the raw configuration text, then return
        the cleaned string.  The logic mirrors the C++ implementation."""
        text = self._ori_conf_text
        new_text: List[str] = []
        annotation = False
        index = -1
        length = len(text)

        while index < length - 2:
            index += 1
            ch      = text[index]
            next_ch = text[index + 1]

            if annotation:
                if ch == '*' and next_ch == '/':
                    annotation = False
                    index += 1
                continue

            if ch in _BLANK_CHARS:
                if not new_text:
                    continue
                if next_ch in _BLANK_CHARS:
                    continue
                last = new_text[-1]
                if last in _PUNCT_CHARS:
                    continue
                if next_ch in _PUNCT_CHARS:
                    continue

            if ch == '/' and next_ch == '*':
                annotation = True
                index += 1
                continue

            new_text.append(' ' if ch in _BLANK_CHARS else ch)

        # Handle the very last character (the C++ loop stops at length-2)
        if index == length - 2 and text[-1] != ' ':
            new_text.append(text[-1])

        return ''.join(new_text)

    def getConfText(self) -> str:
        """Return the original (unmodified) configuration text."""
        return self._ori_conf_text

    @staticmethod
    def getDefaultConfigure() -> str:
        """Return the built-in default prettyprinter configuration."""
        return DEFAULT_CONF

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse(self) -> None:
        """Parse the configuration text and populate internal data structures."""
        clean_text = self.getCleanConfText()

        # ---- global directives ----------------------------------------
        m = _RE_INDENT.search(clean_text)
        if m:
            self.global_props.indent = int(m.group(1))

        m = _RE_CSSFOLD.search(clean_text)
        if m:
            self.global_props.cssfold = 1 if m.group(1) == 'true' else 0

        # ---- per-selector rules ---------------------------------------
        for m in _RE_RULE.finditer(clean_text):
            selectors_str = m.group(1)
            properties_str = m.group(2)

            for sel in selectors_str.split(','):
                sel = sel.strip()
                if not sel:
                    continue
                if _RE_WILDCARD.search(sel):
                    continue

                # Later declarations override earlier ones for the same selector
                if sel in self._selectors:
                    self._selectors.remove(sel)
                self._selectors.append(sel)

                for prop in properties_str.split(';'):
                    parts = prop.split(':', 1)
                    if len(parts) != 2:
                        continue
                    key   = parts[0].strip()
                    value = parts[1].strip()

                    if key == 'opentag-br':
                        if not _RE_INT_INT.match(value):
                            continue
                        v0, v1 = value.split()
                        if sel not in self._properties_map:
                            self._properties_map[sel] = Properties()
                        self._properties_map[sel].open_pre_br  = int(v0)
                        self._properties_map[sel].open_post_br = int(v1)

                    elif key == 'closetag-br':
                        if not _RE_INT_INT.match(value):
                            continue
                        v0, v1 = value.split()
                        if sel not in self._properties_map:
                            self._properties_map[sel] = Properties()
                        self._properties_map[sel].close_pre_br  = int(v0)
                        self._properties_map[sel].close_post_br = int(v1)

                    elif key == 'ind-adj':
                        if not _RE_INT.match(value):
                            continue
                        if sel not in self._properties_map:
                            self._properties_map[sel] = Properties()
                        self._properties_map[sel].ind_adj = int(value)

                    elif key == 'inner-ind-adj':
                        if not _RE_INT.match(value):
                            continue
                        if sel not in self._properties_map:
                            self._properties_map[sel] = Properties()
                        self._properties_map[sel].inner_ind_adj = int(value)

                    elif key == 'attr-fm-resv':
                        if not _RE_BOOL.search(value):
                            continue
                        if sel not in self._properties_map:
                            self._properties_map[sel] = Properties()
                        self._properties_map[sel].attr_fm_resv = 1 if value == 'true' else 0

                    elif key == 'text-fm-resv':
                        if not _RE_BOOL.search(value):
                            continue
                        if sel not in self._properties_map:
                            self._properties_map[sel] = Properties()
                        self._properties_map[sel].text_fm_resv = 1 if value == 'true' else 0

    def _calcWeightForSelector(self, selector: str) -> int:
        """Compute a numeric specificity weight for *selector*.

        Each path segment (space-separated token) contributes:
          - 1    if the segment is the universal selector ``*``
          - 1000 for any named element

        The C++ implementation accumulated these into an ``unsigned long``;
        Python ints are unbounded so no overflow is possible.
        """
        weight = 0
        for seg in selector.split():
            weight += 1 if seg == '*' else 1000
        return weight

    def _orderingSelectors(self, descending: bool = False) -> List[str]:
        """Return a copy of the selector list sorted by specificity weight.

        When two selectors have the same weight their original (insertion)
        order is preserved (stable sort via the order tiebreaker).
        """
        weighted = [
            (sel, self._calcWeightForSelector(sel) * 1000 + order)
            for order, sel in enumerate(self._selectors)
        ]
        weighted.sort(key=lambda x: x[1], reverse=descending)
        return [sel for sel, _ in weighted]
