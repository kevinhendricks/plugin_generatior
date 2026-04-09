#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PrettyPrinter – Python conversion of the Qt C++ PrettyPrinter class.

Given the raw XHTML source and an XhtmlFormatParser instance (which carries
the parsed prettyprinter.pcss settings), produces a reformatted XHTML string
with the indentation, line-breaks, and text-condensation rules the user has
specified.

All four public methods are implemented as static methods so they can be
called without instantiating the class, exactly as in the original C++:

    result = PrettyPrinter.PrettifyXhtml(source, xfparser)

CSS reformatting of <style> tag content relies on an optional CSSInfo module.
If that module is not available the CSS text is left as-is (still correct;
only the internal CSS formatting differs).

Original C++ classes: PrettyPrinter.h / PrettyPrinter.cpp (Qt)
"""

import re

from TagLister import TagLister
from XhtmlFormatParser import XhtmlFormatParser, SortMode, Properties, UNDEFINED_PROP

# Optional CSS reformatting support (Sigil's CSSInfo Python binding).
try:
    from CSSInfo import CSSInfo as _CSSInfo
    _HAVE_CSSINFO = True
except ImportError:
    _HAVE_CSSINFO = False


# ---------------------------------------------------------------------------
# PrettyPrinter
# ---------------------------------------------------------------------------

class PrettyPrinter:
    """
    Static-method collection that mirrors the Qt C++ PrettyPrinter class.

    Methods
    -------
    PrettifyXhtml(source, xfparser)  – reformat a raw XHTML string.
    trimmed(text, chars)             – strip leading/trailing chars.
    condenseText(text)               – collapse whitespace runs to one space.
    RegexSub(regexp, alt, text, n)   – regex substitution with \\N back-refs.
    """

    # ------------------------------------------------------------------
    # RegexSub
    # ------------------------------------------------------------------

    @staticmethod
    def RegexSub(regexp: str, alt_pattern: str, text: str,
                 max_count: int = 0) -> str:
        """Replace occurrences of *regexp* in *text* using *alt_pattern*.

        *alt_pattern* supports ``\\N`` (backslash + single ASCII digit)
        back-references to captured groups, exactly as the C++ version does.
        Group 0 is the full match; groups 1-9 address capturing parentheses.

        When *max_count* > 0, at most that many substitutions are performed.
        """
        compiled = re.compile(regexp)
        parts = []
        offset = 0
        count = 0

        for m in compiled.finditer(text):
            if max_count > 0 and count == max_count:
                break
            count += 1

            # Append verbatim text before this match.
            parts.append(text[offset:m.start()])

            # Expand alt_pattern: handle \N back-references.
            alt_parts = []
            backslash = False
            for ch in alt_pattern:
                if ch == '\\':
                    backslash = True
                    continue
                if backslash:
                    backslash = False
                    if ch.isdigit():
                        group_num = int(ch)
                        try:
                            captured = m.group(group_num)
                            alt_parts.append(captured if captured is not None else '')
                            continue
                        except IndexError:
                            pass
                    alt_parts.append('\\')
                alt_parts.append(ch)

            parts.append(''.join(alt_parts))
            offset = m.end()

        parts.append(text[offset:])
        return ''.join(parts)

    # ------------------------------------------------------------------
    # condenseText
    # ------------------------------------------------------------------

    @staticmethod
    def condenseText(text: str) -> str:
        """Replace all newline variants with a space, then collapse runs of
        whitespace to a single space."""
        segment = re.sub(r'(\r\n)|\n|\r', ' ', text)
        segment = re.sub(r'\s{2,}', ' ', segment)
        return segment

    # ------------------------------------------------------------------
    # trimmed
    # ------------------------------------------------------------------

    @staticmethod
    def trimmed(text: str, chars: str) -> str:
        """Return *text* with leading and trailing characters found in *chars*
        removed.  Mirrors the custom C++ trimmed() rather than Python's
        str.strip() (which only handles whitespace)."""
        i = 0
        while i < len(text) and text[i] in chars:
            i += 1
        j = len(text)
        while j > i and text[j - 1] in chars:
            j -= 1
        return text[i:j]

    # ------------------------------------------------------------------
    # PrettifyXhtml
    # ------------------------------------------------------------------

    @staticmethod
    def PrettifyXhtml(source: str, xfparser: XhtmlFormatParser) -> str:
        """Reformat *source* (raw XHTML text) according to the formatting
        settings held by *xfparser* (a parsed prettyprinter.pcss instance).

        Returns the reformatted XHTML string.
        """

        # ---- helpers (closures over locals) ---------------------------

        ascend_selectors = xfparser.getAllSelectors(SortMode.ASCEND)
        node_path = []          # mutable stack of tag names currently open

        def is_selector_match_node(sel: str) -> bool:
            """Return True when the space-separated selector *sel* matches the
            tail of the current *node_path*."""
            segments = sel.split(' ')
            if len(segments) > len(node_path):
                return False
            for k in range(1, len(segments) + 1):
                seg  = segments[len(segments) - k]
                seg2 = node_path[len(node_path) - k]
                if seg == '*':
                    continue
                if seg != seg2:
                    return False
            return True

        # Clamp global settings.
        raw_indent  = xfparser.global_props.indent
        indent_para = 2 if (raw_indent > 4 or raw_indent < 0) else raw_indent

        raw_cssfold = xfparser.global_props.cssfold
        cssfold     = 0 if (raw_cssfold > 1 or raw_cssfold < 0) else raw_cssfold

        def calc_final_props() -> Properties:
            """Merge all matching selector rules for the current *node_path*
            in ascending-specificity order and return the resolved Properties.
            Results are cached on *xfparser.path_props_cache*."""
            feature_path = ' '.join(node_path)
            if feature_path in xfparser.path_props_cache:
                return xfparser.path_props_cache[feature_path]

            fp = Properties()   # final (merged) properties
            for sel in ascend_selectors:
                if is_selector_match_node(sel):
                    p = xfparser.getSelectorProperties(sel)
                    if p.open_pre_br   != UNDEFINED_PROP: fp.open_pre_br   = p.open_pre_br
                    if p.open_post_br  != UNDEFINED_PROP: fp.open_post_br  = p.open_post_br
                    if p.close_pre_br  != UNDEFINED_PROP: fp.close_pre_br  = p.close_pre_br
                    if p.close_post_br != UNDEFINED_PROP: fp.close_post_br = p.close_post_br
                    if p.ind_adj       != UNDEFINED_PROP: fp.ind_adj       = p.ind_adj
                    if p.inner_ind_adj != UNDEFINED_PROP: fp.inner_ind_adj = p.inner_ind_adj
                    if p.attr_fm_resv  != UNDEFINED_PROP: fp.attr_fm_resv  = p.attr_fm_resv
                    if p.text_fm_resv  != UNDEFINED_PROP: fp.text_fm_resv  = p.text_fm_resv

            # Clamp each field to its valid range; UNDEFINED_PROP (-100)
            # falls below every lower bound and is therefore mapped to 0.
            fp.open_pre_br   = 0 if fp.open_pre_br   > 9 or fp.open_pre_br   < 0 else fp.open_pre_br
            fp.open_post_br  = 0 if fp.open_post_br  > 9 or fp.open_post_br  < 0 else fp.open_post_br
            fp.close_pre_br  = 0 if fp.close_pre_br  > 9 or fp.close_pre_br  < 0 else fp.close_pre_br
            fp.close_post_br = 0 if fp.close_post_br > 9 or fp.close_post_br < 0 else fp.close_post_br
            fp.ind_adj       = 0 if fp.ind_adj       > 9 or fp.ind_adj       < -9 else fp.ind_adj
            fp.inner_ind_adj = 0 if fp.inner_ind_adj > 9 or fp.inner_ind_adj < -9 else fp.inner_ind_adj
            fp.attr_fm_resv  = 0 if fp.attr_fm_resv  > 1 or fp.attr_fm_resv  < 0 else fp.attr_fm_resv
            fp.text_fm_resv  = 0 if fp.text_fm_resv  > 1 or fp.text_fm_resv  < 0 else fp.text_fm_resv

            xfparser.path_props_cache[feature_path] = fp
            return fp

        def clean_open_tag_text(opentag: str) -> str:
            """Strip redundant whitespace from within an opening tag while
            preserving required spacing around attribute punctuation."""
            blank = set('\n\t ')
            tight = set('=;')
            parts = []
            for idx in range(len(opentag) - 1):
                ch      = opentag[idx]
                next_ch = opentag[idx + 1]
                if ch in blank:
                    if next_ch in blank:
                        continue
                    last = parts[-1] if parts else ''
                    if next_ch in tight or (last and last in tight):
                        continue
                parts.append(ch)
            parts.append(opentag[-1])
            return ''.join(parts)

        # ---- main loop ------------------------------------------------

        out = []            # collected output fragments
        lvl              = -1
        last_post_br     = 0
        last_tag_end_pos = 0

        taglist  = TagLister(source)
        ti_count = taglist.size() - 1  # last entry is a dummy — skip it

        i = 0
        while i < ti_count:
            ti = taglist.at(i)

            # Text between the previous tag's end and this tag's start.
            if ti.pos > last_tag_end_pos:
                previous_text = PrettyPrinter.trimmed(
                    source[last_tag_end_pos:ti.pos], ' \n\t'
                )
            else:
                previous_text = ''

            # ---- opening tag -----------------------------------------
            if ti.ttype == 'begin':
                node_path.append(ti.tname)
                props = calc_final_props()
                lvl += 1 + props.ind_adj

                if previous_text:
                    pre_br = '\n' * props.open_pre_br
                elif props.open_pre_br > last_post_br:
                    pre_br = '\n' * (props.open_pre_br - last_post_br)
                else:
                    pre_br = ''

                post_br = '\n' * props.open_post_br if props.open_post_br > 0 else ''

                if props.open_pre_br + last_post_br == 0:
                    indent = ''
                elif indent_para * lvl > 0:
                    indent = ' ' * (indent_para * lvl)
                else:
                    indent = ''

                tag = source[ti.pos:ti.pos + ti.len]
                if not props.attr_fm_resv:
                    tag = clean_open_tag_text(tag)

                if props.text_fm_resv:
                    # Jump directly to the closing tag; preserve inner text.
                    post_br = ''
                    i = taglist.findCloseTagForOpen(i) - 1
                else:
                    previous_text = PrettyPrinter.condenseText(previous_text)

                out.append(previous_text + pre_br + indent + tag + post_br)
                last_post_br = len(post_br)
                lvl += props.inner_ind_adj

            # ---- closing tag -----------------------------------------
            elif ti.ttype == 'end':
                props = calc_final_props()

                if previous_text:
                    pre_br = '\n' * props.close_pre_br
                elif props.close_pre_br > last_post_br:
                    pre_br = '\n' * (props.close_pre_br - last_post_br)
                else:
                    pre_br = ''

                post_br = '\n' * props.close_post_br if props.close_post_br > 0 else ''
                tag     = source[ti.pos:ti.pos + ti.len]

                lvl -= props.inner_ind_adj

                if props.close_pre_br + last_post_br == 0:
                    indent = ''
                elif indent_para * lvl > 0:
                    indent = ' ' * (indent_para * lvl)
                else:
                    indent = ''

                # Special handling for <style> element content.
                # The "\v" character is an invisible marker inserted by Emmet's
                # code-generation to indicate the cursor position; do not remove it.
                if ti.tname == 'style':
                    if previous_text == '\v':
                        previous_text = '\n\v\n'
                    elif PrettyPrinter.trimmed(previous_text, '\n\t ') != '':
                        css_indent = ' ' * (indent_para * lvl) if indent_para * lvl > 0 else ''
                        if _HAVE_CSSINFO:
                            cp = _CSSInfo(previous_text)
                            reformat_css = '\n' + cp.getReformattedCSSText(not bool(cssfold)) + '\n'
                            previous_text = PrettyPrinter.RegexSub('\n', '\n' + css_indent, reformat_css)
                        # If CSSInfo is not available, leave the CSS text as-is.

                previous_text = source[last_tag_end_pos:ti.pos]
                if props.text_fm_resv:
                    pre_br = ''
                else:
                    previous_text = PrettyPrinter.condenseText(previous_text)

                out.append(previous_text + pre_br + indent + tag + post_br)

                if node_path:
                    node_path.pop()
                last_post_br = len(post_br)
                lvl -= 1 + props.ind_adj

            # ---- single / xmlheader / doctype / comment --------------
            else:
                node_path.append(ti.tname)
                props = calc_final_props()
                lvl += 1 + props.ind_adj

                combined_pre  = props.open_pre_br  + props.close_pre_br
                combined_post = props.open_post_br + props.close_post_br

                if previous_text:
                    pre_br = '\n' * combined_pre
                elif combined_pre > last_post_br:
                    pre_br = '\n' * (combined_pre - last_post_br)
                else:
                    pre_br = ''

                post_br = '\n' * combined_post if combined_post > 0 else ''

                if props.open_pre_br + last_post_br == 0:
                    indent = ''
                elif indent_para * lvl > 0:
                    indent = ' ' * (indent_para * lvl)
                else:
                    indent = ''

                tag = source[ti.pos:ti.pos + ti.len]
                if not props.attr_fm_resv:
                    tag = clean_open_tag_text(tag)

                out.append(previous_text + pre_br + indent + tag + post_br)

                node_path.pop()
                last_post_br = len(post_br)
                lvl -= 1 + props.ind_adj

            last_tag_end_pos = ti.pos + ti.len
            i += 1

        return ''.join(out)
