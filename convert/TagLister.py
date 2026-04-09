#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TagLister – Python conversion of the Qt C++ TagLister class.

Given the raw text of an XHTML file, TagLister scans through it in document
order and builds a flat list of TagInfo structures — one entry per tag.
Each TagInfo records:

  * The tag's byte position and length in the source string.
  * The tag's name (e.g. ``"div"``, ``"img"``, ``"?xml"``, ``"!--"``).
  * The tag's type: ``xmlheader``, ``pi``, ``comment``, ``doctype``,
    ``cdata``, ``begin``, ``single``, or ``end``.
  * The tag's child-number within its parent and the full dot-style
    ancestor path (e.g. ``"html -1,body 0,div 2"``).
  * For ``end`` tags: the position and length of the matching ``begin`` tag.

The companion AttInfo structure describes the position and value of a
single attribute within a tag string.

Once built, the list can be queried with helpers such as
``findCloseTagForOpen``, ``isPositionInBody``, ``GeneratePathToTag``, etc.

Original C++ classes: TagLister.h / TagLister.cpp (Qt)
"""

import sys
from dataclasses import dataclass, field
from typing import Optional

# Characters treated as whitespace in XML/HTML markup
WHITESPACE_CHARS = " \t\n\r\f"


# ---------------------------------------------------------------------------
# Data structures (replaces the nested C++ structs)
# ---------------------------------------------------------------------------

@dataclass
class TagInfo:
    """Describes a single tag (or non-tag chunk) found in the source."""
    pos: int = -1       # position of tag in source
    len: int = -1       # length of tag in source
    child: int = -1     # child number of this tag within its parent
    tpath: str = ""     # comma-joined path of "tagname childindex" entries
    tname: str = ""     # tag name, e.g. "?xml", "?", "!--", "!DOCTYPE", "![CDATA[", "div"
    ttype: str = ""     # one of: xmlheader, pi, comment, doctype, cdata, begin, single, end
    open_pos: int = -1  # for end tags: position of the corresponding begin tag
    open_len: int = -1  # for end tags: length of the corresponding begin tag


@dataclass
class AttInfo:
    """Describes a single attribute found inside a tag string."""
    pos: int = -1       # position of attribute relative to tag start
    len: int = -1       # length of the full attribute (name=value) in the tag
    vpos: int = -1      # position of attribute value relative to tag start
    vlen: int = -1      # length of attribute value
    aname: str = ""     # attribute name
    avalue: str = ""    # attribute value (without surrounding quotes)


# ---------------------------------------------------------------------------
# TagLister class
# ---------------------------------------------------------------------------

class TagLister:
    """
    Scans the raw text of an XHTML file and builds an ordered flat list of
    TagInfo records — one entry per tag, in document order.

    Each record captures the tag's position and length in the source, its
    name and type (begin / end / single / comment / …), its child-number
    within its parent, and a hierarchical path string.  End tags also store
    a back-reference (position + length) to their matching begin tag.

    Usage
    -----
    lister = TagLister(xhtml_source_string)
    for i in range(lister.size()):
        ti = lister.at(i)   # TagInfo
        print(ti.tname, ti.ttype, ti.pos)
    """

    def __init__(self, source: str = "") -> None:
        self.m_source: str = source
        self.m_pos: int = 0
        self.m_next: int = 0
        self.m_child: int = -1
        # Parallel stacks tracking the currently open tag hierarchy.
        # Index 0 is always the synthetic "root" entry.
        self.m_TagPath: list = ["root"]
        self.m_TagPos: list = [-1]
        self.m_TagLen: list = [0]
        self.m_TagChild: list = [-1]
        self.m_Tags: list = []
        self.m_bodyStartPos: int = -1
        self.m_bodyEndPos: int = -1
        self.m_bodyOpenTag: int = -1
        self.m_bodyCloseTag: int = -1
        if source:
            self._buildTagList()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def reloadLister(self, source: str) -> None:
        """Reinitialise the lister with a new source string."""
        self.m_source = source
        self.m_pos = 0
        self.m_next = 0
        self.m_child = -1
        self.m_TagPath = ["root"]
        self.m_TagPos = [-1]
        self.m_TagLen = [0]
        self.m_TagChild = [-1]
        self._buildTagList()

    def at(self, i: int) -> TagInfo:
        """Return the TagInfo at index *i*.  Out-of-range returns the last (dummy) entry."""
        if i < 0 or i >= len(self.m_Tags):
            i = len(self.m_Tags) - 1  # last entry is a dummy stop record
        return self.m_Tags[i]

    def size(self) -> int:
        """Number of entries in the tag list (including the trailing dummy)."""
        return len(self.m_Tags)

    def getSource(self) -> str:
        return self.m_source

    def isPositionInBody(self, pos: int) -> bool:
        if pos < self.m_bodyStartPos or pos > self.m_bodyEndPos:
            return False
        return True

    def isPositionInTag(self, pos: int) -> bool:
        i = self.findFirstTagOnOrAfter(pos)
        ti = self.m_Tags[i]
        return ti.pos <= pos < ti.pos + ti.len

    def isPositionInOpenTag(self, pos: int) -> bool:
        i = self.findFirstTagOnOrAfter(pos)
        ti = self.m_Tags[i]
        if ti.pos <= pos < ti.pos + ti.len:
            if ti.ttype in ("begin", "single"):
                return True
        return False

    def isPositionInCloseTag(self, pos: int) -> bool:
        i = self.findFirstTagOnOrAfter(pos)
        ti = self.m_Tags[i]
        if ti.pos <= pos < ti.pos + ti.len:
            if ti.ttype == "end":
                return True
        return False

    def findLastTagOnOrBefore(self, pos: int) -> int:
        """
        Return the index of the tag whose start position is <= *pos*.
        Returns -1 if no such tag exists (the front of m_Tags is not padded).
        """
        # Walk forward to the first tag that starts *after* pos, then step back.
        i = 0
        ti = self.m_Tags[i]
        while ti.pos <= pos and ti.len != -1:
            i += 1
            ti = self.m_Tags[i]
        i -= 1
        return i

    def findFirstTagOnOrAfter(self, pos: int) -> int:
        """
        Return the index of the first tag whose end position is > *pos*.
        Always succeeds because m_Tags is padded with a trailing dummy entry.
        """
        i = 0
        ti = self.m_Tags[i]
        while (ti.pos + ti.len <= pos) and ti.len != -1:
            i += 1
            ti = self.m_Tags[i]
        return i

    def findOpenTagForClose(self, i: int) -> int:
        """Return the index of the begin tag corresponding to the end tag at *i*."""
        if i < 0 or i >= len(self.m_Tags):
            return -1
        ti = self.m_Tags[i]
        if ti.ttype != "end":
            return -1
        open_pos = ti.open_pos
        for j in range(i - 1, -1, -1):
            if self.m_Tags[j].pos == open_pos:
                return j
        return -1

    def findCloseTagForOpen(self, i: int) -> int:
        """Return the index of the end tag corresponding to the begin tag at *i*."""
        if i < 0 or i >= len(self.m_Tags):
            return -1
        ti = self.m_Tags[i]
        if ti.ttype != "begin":
            return -1
        open_pos = ti.pos
        for j in range(i + 1, len(self.m_Tags)):
            if self.m_Tags[j].open_pos == open_pos:
                return j
        return -1

    def findLastOpenOrSingleTagThatContainsYou(self, pos: int) -> int:
        """
        Return the index of the innermost open/single tag that contains *pos*.
        The search is clamped to the body region.  Returns -1 if none found.
        """
        bpos = max(self.m_bodyStartPos, min(pos, self.m_bodyEndPos))

        k = self.findLastTagOnOrBefore(bpos)
        ti = self.m_Tags[k]

        # If bpos is inside a single tag, use it.
        if ti.ttype == "single":
            if ti.pos <= bpos < ti.pos + ti.len:
                return k

        # If bpos is inside the span of a begin tag (up to its close), use it.
        if ti.ttype == "begin":
            ci = self.findCloseTagForOpen(k)
            if ci != -1:
                cls = self.m_Tags[ci]
                if ti.pos <= bpos < cls.pos + cls.len:
                    return k

        # Scan backwards for the closest single or begin tag.
        i = k
        found = False
        while i >= 0 and not found:
            if self.m_Tags[i].ttype in ("single", "begin"):
                found = True
            if not found:
                i -= 1
        return i if found else -1

    def findLastOpenTagOnOrBefore(self, pos: int) -> int:
        """
        Return the index of the last begin tag at or before *pos*,
        clamped to the body region.  Returns -1 if none found.
        """
        bpos = pos
        if bpos >= self.m_bodyEndPos:
            bpos = self.m_bodyEndPos
        if bpos <= self.m_bodyStartPos:
            bpos = self.m_bodyStartPos

        i = self.findLastTagOnOrBefore(bpos)
        found = False
        while i >= 0 and not found:
            if self.m_Tags[i].ttype == "begin":
                found = True
            if not found:
                i -= 1
        return i if found else -1

    def findBodyOpenTag(self) -> int:
        return self.m_bodyOpenTag

    def findBodyCloseTag(self) -> int:
        return self.m_bodyCloseTag

    def GeneratePathToTag(self, pos: int) -> str:
        i = self.findLastOpenOrSingleTagThatContainsYou(pos)
        if i < 0:
            return "html -1"
        return self.m_Tags[i].tpath

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def serializeAttribute(aname: str, avalue: str) -> str:
        """Return ``name="value"`` (or single-quoted when value contains ``"``).``"""
        qc = '"'
        if '"' in avalue:
            qc = "'"
        return aname + "=" + qc + avalue + qc

    @staticmethod
    def parseAttribute(tagstring: str, attribute_name: str) -> AttInfo:
        """
        Locate *attribute_name* inside *tagstring* and return an AttInfo
        describing its position and value.

        Note: the C++ version modified an AttInfo passed by reference;
        the Python version returns a new AttInfo instead.
        """
        ainfo = AttInfo()
        if len(tagstring) < 2:
            return ainfo
        c = tagstring[1]
        p = 0

        # Ignore comments, doctypes, CDATA sections, PIs and XML headers.
        if c in ("?", "!"):
            return ainfo

        # Normal tag: skip over the tag name.
        p = TagLister._skipAnyBlanks(tagstring, 1)
        if tagstring[p] == "/":
            return ainfo  # end tag has no attributes
        p = TagLister._stopWhenContains(tagstring, ">/ \f\t\r\n", p)

        # Iterate over attributes (begin or single tag type).
        while tagstring.find("=", p) != -1:
            p = TagLister._skipAnyBlanks(tagstring, p)
            s = p
            p = TagLister._stopWhenContains(tagstring, "=", p)
            aname = tagstring[s:p].strip()
            if aname == attribute_name:
                ainfo.pos = s
                ainfo.aname = aname
            p += 1  # skip the '='
            p = TagLister._skipAnyBlanks(tagstring, p)
            if p < len(tagstring) and tagstring[p] in ("'", '"'):
                qc = tagstring[p]
                p += 1
                b = p
                p = TagLister._stopWhenContains(tagstring, qc, p)
                avalue = tagstring[b:p]
                if aname == attribute_name:
                    ainfo.avalue = avalue
                    ainfo.len = p - s + 1
                    ainfo.vpos = b
                    ainfo.vlen = p - b
                p += 1  # skip closing quote
            else:
                b = p
                p = TagLister._stopWhenContains(tagstring, ">/ ", p)
                avalue = tagstring[b:p]
                if aname == attribute_name:
                    ainfo.avalue = avalue
                    ainfo.len = p - s
                    ainfo.vpos = b
                    ainfo.vlen = p - b
        return ainfo

    @staticmethod
    def extractAllAttributes(tagstring: str) -> str:
        """
        Return a copy of the attribute substring from *tagstring*, or an
        empty string if the tag carries no attributes.
        """
        taglen = len(tagstring)
        if taglen < 2:
            return ""
        c = tagstring[1]
        p = 0

        # Ignore comments, doctypes, CDATA sections, PIs and XML headers.
        if c in ("?", "!"):
            return ""

        p = TagLister._skipAnyBlanks(tagstring, 1)
        if tagstring[p] == "/":
            return ""  # end tag has no attributes

        # Skip over the tag name.
        p = TagLister._stopWhenContains(tagstring, ">/ \f\t\r\n", p)
        # Skip blanks before first attribute or the tag end.
        p = TagLister._skipAnyBlanks(tagstring, p)

        # XML/XHTML does not support boolean attributes without '='.
        if tagstring.find("=", p) == -1:
            return ""

        # Extract everything up to (but not including) the closing '>'.
        res = tagstring[p:taglen - 1].strip()
        if res.endswith("/"):
            res = res[:-1].strip()
        return res

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _makePathToTag(self) -> str:
        """
        Build a comma-joined path string like ``"html -1,body 0,div 2"``
        from the current tag-path stacks.
        """
        tagpath = []
        i = 1  # skip the synthetic "root" entry at index 0
        while i < len(self.m_TagPath):
            child_index = -1
            if i + 1 < len(self.m_TagPath):
                child_index = self.m_TagChild[i + 1]
            tagpath.append(self.m_TagPath[i] + " " + str(child_index))
            i += 1
        return ",".join(tagpath)

    def _getNext(self) -> TagInfo:
        """
        Advance through the source and return the next TagInfo for a tag.
        Non-tag text is silently skipped.  Returns a dummy TagInfo (len==-1)
        when the source is exhausted.
        """
        mi = TagInfo()
        markup = self._parseML()
        while markup is not None:
            if len(markup) >= 2 and markup[0] == "<" and markup[-1] == ">":
                mi.pos = self.m_pos
                self._parseTag(markup, mi)

                if mi.ttype == "begin":
                    self.m_TagPos.append(mi.pos)
                    self.m_TagLen.append(mi.len)
                    self.m_child += 1
                    mi.child = self.m_child
                    self.m_TagChild.append(mi.child)
                    self.m_child = -1
                    self.m_TagPath.append(mi.tname)
                    mi.tpath = self._makePathToTag()

                elif mi.ttype == "single":
                    # Temporarily treat as an open tag to compute the path …
                    self.m_child += 1
                    mi.child = self.m_child
                    self.m_TagChild.append(mi.child)
                    self.m_TagPath.append(mi.tname)
                    mi.tpath = self._makePathToTag()
                    # … then remove it since a single tag has no children.
                    self.m_TagPath.pop()
                    self.m_TagChild.pop()

                elif mi.ttype == "end":
                    pathnode = self.m_TagPath[-1]
                    if pathnode.startswith(mi.tname):
                        self.m_TagPath.pop()
                        mi.open_pos = self.m_TagPos.pop()
                        mi.open_len = self.m_TagLen.pop()
                        mi.child = self.m_TagChild.pop()
                        self.m_child = mi.child
                    else:
                        print(
                            "TagLister Error: Not well formed – open/close mismatch:\n"
                            f"   open Tag:  {pathnode} at position: {self.m_TagPos[-1]}\n"
                            f"   close Tag: {mi.tname} at position: {mi.pos}",
                            file=sys.stderr,
                        )
                        mi.open_pos = -1
                        mi.open_len = -1
                        mi.child = -1
                    mi.tpath = self._makePathToTag()

                return mi

            # Skip non-tag text and try again.
            markup = self._parseML()

        return mi  # exhausted – dummy TagInfo with len == -1

    def _parseML(self) -> Optional[str]:
        """
        Return the next chunk of source as a string, advancing *m_next*.
        Returns ``None`` when the source is exhausted.
        """
        p = self.m_next
        self.m_pos = p
        if p >= len(self.m_source):
            return None

        if self.m_source[p] != "<":
            # Plain text up to the next tag start.
            self.m_next = self._findTarget("<", p + 1)
            return self.m_source[self.m_pos:self.m_next]

        # Tag or special construct – handle special cases first.
        tstart = self.m_source[p:p + 9]
        if tstart.startswith("<!--"):
            self.m_next = self._findTarget("-->", p + 4, after=True)
            return self.m_source[self.m_pos:self.m_next]
        if tstart.startswith("<![CDATA["):
            self.m_next = self._findTarget("]]>", p + 9, after=True)
            return self.m_source[self.m_pos:self.m_next]

        # Normal tag: advance to the closing '>'.
        self.m_next = self._findTarget(">", p + 1, after=True)
        # If another '<' appears before '>', the markup is malformed; use the '<'.
        ntb = self._findTarget("<", p + 1)
        if ntb < self.m_next:
            self.m_next = ntb
        return self.m_source[self.m_pos:self.m_next]

    def _parseTag(self, tagstring: str, mi: TagInfo) -> None:
        """Classify *tagstring* and fill in *mi.tname*, *mi.ttype*, and *mi.len*."""
        mi.len = len(tagstring)
        if len(tagstring) < 2:
            return
        c = tagstring[1]

        # Processing instruction or XML declaration
        if c == "?":
            if tagstring.startswith("<?xml"):
                mi.tname = "?xml"
                mi.ttype = "xmlheader"
            else:
                mi.tname = "?"
                mi.ttype = "pi"
            return

        # Comment, DOCTYPE or CDATA
        if c == "!":
            if tagstring.startswith("<!--"):
                mi.tname = "!--"
                mi.ttype = "comment"
            elif tagstring.startswith("<!DOCTYPE") or tagstring.startswith("<!doctype"):
                mi.tname = "!DOCTYPE"
                mi.ttype = "doctype"
            elif tagstring.startswith("<![CDATA[") or tagstring.startswith("<![cdata["):
                mi.tname = "![CDATA["
                mi.ttype = "cdata"
            return

        # Normal element tag – extract the tag name.
        p = TagLister._skipAnyBlanks(tagstring, 1)
        if tagstring[p] == "/":
            mi.ttype = "end"
            p += 1
            p = TagLister._skipAnyBlanks(tagstring, p)
        b = p
        p = TagLister._stopWhenContains(tagstring, ">/ \f\t\r\n", p)
        mi.tname = tagstring[b:p]

        # Determine begin vs. single if not already set to "end".
        if not mi.ttype:
            if tagstring.endswith("/>") or tagstring.endswith("/ >"):
                mi.ttype = "single"
            else:
                mi.ttype = "begin"

    def _findTarget(self, tgt: str, p: int, after: bool = False) -> int:
        """
        Return the position immediately *before* (or *after* when
        ``after=True``) the first occurrence of *tgt* in the source at or
        after *p*.  Returns ``len(source)`` when *tgt* is not found.
        """
        nxt = self.m_source.find(tgt, p)
        if nxt == -1:
            return len(self.m_source)
        nxt = nxt + len(tgt) - 1
        if after:
            nxt += 1
        return nxt

    def _buildTagList(self) -> None:
        """Populate ``m_Tags`` by consuming the entire source."""
        self.m_Tags = []
        self.m_bodyStartPos = -1
        self.m_bodyEndPos = -1
        self.m_bodyOpenTag = -1
        self.m_bodyCloseTag = -1
        i = 0
        ti = self._getNext()
        while ti.len != -1:
            if ti.tname == "body" and ti.ttype == "begin":
                self.m_bodyStartPos = ti.pos + ti.len
                self.m_bodyOpenTag = i
            if ti.tname == "body" and ti.ttype == "end":
                self.m_bodyEndPos = ti.pos - 1
                self.m_bodyCloseTag = i
            self.m_Tags.append(ti)
            i += 1
            ti = self._getNext()
        # Append a dummy stop record so forward searches always terminate.
        self.m_Tags.append(TagInfo())

    @staticmethod
    def _skipAnyBlanks(tgt: str, p: int) -> int:
        """Advance *p* past any whitespace characters in *tgt*."""
        while p < len(tgt) and tgt[p] in WHITESPACE_CHARS:
            p += 1
        return p

    @staticmethod
    def _stopWhenContains(tgt: str, stopchars: str, p: int) -> int:
        """Advance *p* until a character in *stopchars* is reached."""
        while p < len(tgt) and tgt[p] not in stopchars:
            p += 1
        return p
