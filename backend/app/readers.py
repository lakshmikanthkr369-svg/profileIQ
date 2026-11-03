"""Resume file readers: PDF, .docx (tables, text boxes, headers) and legacy .doc.
Ported unchanged from the Streamlit app; only extract_text() now takes bytes."""
import io
import re
import pdfplumber
from docx import Document as DocxDocument

# ── Legacy Word (.doc, Word 97-2003) text extraction ──
# python-docx only understands .docx (a zip of XML). The old .doc format is a different,
# binary "OLE" container, so it needs its own reader. Pure Python (needs only `olefile`),
# nothing to install on the server besides that one small package.
#
# Everything that can go wrong with a damaged / unusual file is turned into ONE exception
# type (LegacyDocError) with a short code, so the app can show a friendly message.
_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

class LegacyDocError(ValueError):
    """Message is a short code: NOT_WORD | ENCRYPTED_DOC | BAD_DOC | DOC_LIB_MISSING"""

def _clean_word_text(s):
    """Word stores text with control characters: paragraph/cell/field marks etc. Make it plain text."""
    out, stack, hidden = [], [], 0            # field states: "code" (hidden) or "result" (shown); hidden = how many enclosing codes
    for c in s:
        if c == "\x13":                       # field begin  (e.g. HYPERLINK "mailto:..." <code> ... )
            stack.append("code"); hidden += 1
        elif c == "\x14":                     # field separator: what follows is the visible result
            if stack and stack[-1] == "code":
                stack[-1] = "result"; hidden -= 1
        elif c == "\x15":                     # field end
            if stack and stack.pop() == "code":
                hidden -= 1
        elif hidden == 0:                     # visible only if NO enclosing field is still in its hidden code part
            out.append(c)
    t = "".join(out)
    t = t.replace("\x07\x07", "\n").replace("\x07", "\t")      # table: end-of-row -> newline, end-of-cell -> tab
    t = (t.replace("\r", "\n").replace("\x0b", "\n").replace("\x0c", "\n")
          .replace("\x1e", "-").replace("\x1f", "").replace("\xa0", " ")
          .replace("\uf0b7", "•").replace("\uf0a7", "▪").replace("\uf0d8", "➢").replace("\uf0fc", "✓"))
    t = "".join(ch for ch in t if ch in "\n\t" or ord(ch) >= 0x20)
    t = "\n".join(line.rstrip() for line in t.split("\n"))
    while "\n\n\n" in t:
        t = t.replace("\n\n\n", "\n\n")
    return t.strip()

_PAGE_NUMBER_LINE = __import__("re").compile(r"^(page\s*)?\d{1,4}(\s*(of|/)\s*\d{1,4})?$", __import__("re").I)

def _unique_lines(chunks):
    """Lines from several header/footer stories: de-duplicated (the same header repeats in every section),
    without bare page numbers, in order."""
    seen, out = set(), []
    for chunk in chunks:
        for ln in _clean_word_text(chunk).split("\n"):
            key = ln.strip()
            if key and key not in seen and not _PAGE_NUMBER_LINE.match(key):
                seen.add(key); out.append(ln.strip())
    return out

def _header_footer_stories(word, table, blob, cc, full, u32):
    """(header_chunks, footer_chunks). Word keeps every header and footer in ONE text story and lists where
    each starts in PlcfHdd: 6 footnote/endnote separator stories first, then per section six stories
    [even header, odd header, even footer, odd footer, first-page header, first-page footer]."""
    start, length = cc[0] + cc[1], cc[2]
    if length <= 0:
        return [], []
    hdd = full[start:start + length]
    try:
        fc, lcb = u32(word, blob + 11 * 8), u32(word, blob + 11 * 8 + 4)
        raw = table[fc:fc + lcb]
        cps = [u32(raw, 4 * k) for k in range(len(raw) // 4)]
        if len(cps) < 8:
            return [], [hdd]
        fc_dop, lcb_dop = u32(word, blob + 31 * 8), u32(word, blob + 31 * 8 + 4)
        facing = bool(lcb_dop >= 1 and table[fc_dop] & 0x01)                  # different even/odd pages turned on?
        heads, foots = [], []
        for i in range(6, len(cps) - 1):
            kind = (i - 6) % 6
            if kind in (0, 2) and not facing:                                  # even-page stories unused
                continue
            seg = hdd[cps[i]:cps[i + 1]]
            (heads if kind in (0, 1, 4) else foots).append(seg)
        return heads, foots
    except Exception:
        return [], [hdd]                                                       # couldn't split them: still keep the text

def _old_word_text(word, flags, u16, u32):
    """Word 6 / Word 95 (1993-1996). Text is 8-bit; 'complex' (fast-saved) files keep a piece table inside
    the WordDocument stream itself."""
    if flags & 0x0004:                                                # fComplex: text is split into pieces
        try:
            fc_clx, lcb_clx = u32(word, 0x160), u32(word, 0x164)
            clx = word[fc_clx:fc_clx + lcb_clx]
            i = 0
            while i < len(clx) and clx[i] == 0x01:
                i += 3 + u16(clx, i + 1)
            if i < len(clx) and clx[i] == 0x02:
                lcb = u32(clx, i + 1); plc = clx[i + 5:i + 5 + lcb]; n = (len(plc) - 4) // 12
                cps = [u32(plc, 4 * k) for k in range(n + 1)]; pcd = 4 * (n + 1)
                parts = []
                for k in range(n):
                    count = cps[k + 1] - cps[k]
                    if count > 0:
                        fc = u32(plc, pcd + 8 * k + 2) & 0x3FFFFFFF
                        parts.append(word[fc:fc + count].decode("cp1252", "replace"))
                if parts:
                    return _checked_old_text("".join(parts))
        except Exception:
            pass                                                      # fall through to the plain run
    fc_min, fc_mac = u32(word, 0x18), u32(word, 0x1C)
    if not (0 < fc_min <= fc_mac <= len(word)):
        raise LegacyDocError("BAD_DOC")
    return _checked_old_text(word[fc_min:fc_mac].decode("cp1252", "replace"))

def _checked_old_text(raw):
    """Word 6/95 stored text in the author's local codepage (e.g. Cyrillic), which we cannot know.
    If it clearly is not Western European text, refuse instead of returning garbled characters."""
    text = _clean_word_text(raw)
    letters = [c for c in text if c.isalpha()]
    if letters and sum(1 for c in letters if 0xC0 <= ord(c) <= 0xFF) / len(letters) > 0.30:
        raise LegacyDocError("BAD_DOC")
    return text

def _extract_legacy_doc_text(data):
    import io, struct
    try:
        import olefile
    except ImportError:
        raise LegacyDocError("DOC_LIB_MISSING")
    u16 = lambda b, o: struct.unpack_from("<H", b, o)[0]
    u32 = lambda b, o: struct.unpack_from("<I", b, o)[0]
    if data[:8] != _OLE_MAGIC:
        raise LegacyDocError("NOT_WORD")
    ole = olefile.OleFileIO(io.BytesIO(data))
    try:
        if not ole.exists("WordDocument"):
            raise LegacyDocError("NOT_WORD")                          # an OLE file, but not Word (e.g. an old Excel)
        word = ole.openstream("WordDocument").read()
        if len(word) < 0x40:
            raise LegacyDocError("NOT_WORD")
        wident, nfib, flags = u16(word, 0), u16(word, 2), u16(word, 0x0A)
        if wident not in (0xA5EC, 0xA5DC) and nfib not in (0x0065, 0x0068):   # 0xA5EC = Word 97+, 0xA5DC = Word 6/95
            raise LegacyDocError("NOT_WORD")
        if flags & 0x0100:
            raise LegacyDocError("ENCRYPTED_DOC")                     # password-protected
        if nfib < 0x00C1:                                             # Word 6 / Word 95
            return _old_word_text(word, flags, u16, u32)
        if len(word) < 0x200:
            raise LegacyDocError("BAD_DOC")

        table_name = "1Table" if flags & 0x0200 else "0Table"
        if not ole.exists(table_name):
            raise LegacyDocError("BAD_DOC")
        table = ole.openstream(table_name).read()

        # --- the File Information Block: where the text lives and how long each story is
        pos = 0x20
        csw = u16(word, pos); pos += 2 + csw * 2                      # fibRgW
        cslw = u16(word, pos); lw = pos + 2                           # fibRgLw97
        if cslw < 11:
            raise LegacyDocError("BAD_DOC")
        cc = [u32(word, lw + 12 + 4 * i) for i in range(8)]           # ccpText, Ftn, Hdd, (Mcr), Atn, Edn, Txbx, HdrTxbx
        ccp_text, ccp_txbx = cc[0], cc[6]
        pos = lw + cslw * 4
        cb_fclcb = u16(word, pos); blob = pos + 2                     # fibRgFcLcb97
        if cb_fclcb <= 33:
            raise LegacyDocError("BAD_DOC")
        fc_clx, lcb_clx = u32(word, blob + 33 * 8), u32(word, blob + 33 * 8 + 4)
        clx = table[fc_clx:fc_clx + lcb_clx]

        # --- the piece table (CLX): the text is stored in "pieces", each 8-bit or UTF-16
        i = 0
        while i < len(clx) and clx[i] == 0x01:                        # skip property-modifier entries
            i += 3 + u16(clx, i + 1)
        if i >= len(clx) or clx[i] != 0x02:
            raise LegacyDocError("BAD_DOC")
        lcb = u32(clx, i + 1)
        plc = clx[i + 5:i + 5 + lcb]
        n = (len(plc) - 4) // 12
        if n <= 0 or n > 200000:
            raise LegacyDocError("BAD_DOC")
        cps = [u32(plc, 4 * k) for k in range(n + 1)]
        pcd = 4 * (n + 1)
        parts, total, cap = [], 0, 20_000_000
        for k in range(n):
            count = cps[k + 1] - cps[k]
            if count <= 0:
                continue
            fc_raw = u32(plc, pcd + 8 * k + 2)
            if fc_raw & 0x40000000:                                   # compressed: 1 byte per character (Windows-1252)
                start = (fc_raw & 0x3FFFFFFF) // 2
                chunk = word[start:start + count].decode("cp1252", "replace")
            else:                                                     # otherwise UTF-16
                start = fc_raw
                chunk = word[start:start + count * 2].decode("utf-16-le", "replace")
            parts.append(chunk); total += len(chunk)
            if total > cap:
                break
        full = "".join(parts)
        main = full[:ccp_text]
        # text boxes (many résumé templates put names / contact details / skills in them)
        txbx_start = sum(cc[:6])
        txbx = full[txbx_start:txbx_start + ccp_txbx] if ccp_txbx else ""
        body_text = _clean_word_text(main + ("\r" + txbx if txbx.strip("\r\x07 ") else ""))
        # page headers / footers (name + contact details often live here)
        heads, foots = _header_footer_stories(word, table, blob, cc, full, u32)
        hdr_box_start = sum(cc[:7])
        hdr_box = full[hdr_box_start:hdr_box_start + cc[7]] if cc[7] else ""
        head_lines = _unique_lines(heads + ([hdr_box] if hdr_box.strip("\r\x07 ") else []))
        foot_lines = _unique_lines(foots)
        return "\n".join(head_lines + ([body_text] if body_text else []) + foot_lines)
    finally:
        ole.close()

def extract_legacy_doc_text(data):
    """Plain text of a legacy .doc file given as bytes. Raises LegacyDocError (a ValueError) on any problem."""
    try:
        return _extract_legacy_doc_text(data)
    except LegacyDocError:
        raise
    except Exception as e:                                            # truncated / corrupt / hostile files
        raise LegacyDocError("BAD_DOC") from e

# ── Modern Word (.docx) text extraction ──
# python-docx's `doc.paragraphs` only returns top-level paragraphs, so everything inside a TABLE
# (very common in résumé templates), a TEXT BOX, a content control, or the page HEADER / FOOTER
# (where many templates keep the name and phone number) was silently missed.
# This walks the real document structure instead, in reading order. It never raises on odd
# content: the caller falls back to the basic paragraph reader if anything unexpected happens.
import re as _re

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
_PAGE_NUMBER_LINE = _re.compile(r"^(page\s*)?\d{1,4}(\s*(of|/)\s*\d{1,4})?$", _re.I)

def _para_text(p):
    """Text of one paragraph, including hyperlinks, tracked insertions, tabs and line breaks.
    Skips text boxes (read separately), tracked deletions, and Word's duplicate 'fallback' drawings."""
    out = []
    skip = (_W + "txbxContent", _MC + "Fallback", _W + "instrText", _W + "delText", _W + "del", _W + "moveFrom")
    def walk(el):
        for ch in el:
            tag = ch.tag
            if tag == _W + "t":
                out.append(ch.text or "")
            elif tag == _W + "tab" and el.tag == _W + "r":
                out.append("\t")
            elif tag in (_W + "br", _W + "cr"):
                out.append("\n")
            elif tag == _W + "noBreakHyphen":
                out.append("-")
            elif tag in skip or not isinstance(tag, str):
                continue
            else:
                walk(ch)
    walk(p)
    return "".join(out)

def _block_children(parent):
    """Paragraphs and tables directly inside `parent`, looking through content controls (w:sdt)."""
    for ch in parent:
        tag = ch.tag
        if tag == _W + "p" or tag == _W + "tbl":
            yield ch
        elif tag in (_W + "sdt", _W + "customXml", _W + "ins", _W + "moveTo"):
            inner = ch.find(_W + "sdtContent") if tag == _W + "sdt" else ch
            if inner is not None:
                yield from _block_children(inner)

def _kids(parent, tag):
    """Direct children with the given tag, looking THROUGH content controls (w:sdt) - Word's built-in
    templates wrap whole table rows and cells in them."""
    for ch in parent:
        if ch.tag == tag:
            yield ch
        elif ch.tag in (_W + "sdt", _W + "customXml", _W + "ins", _W + "moveTo"):
            inner = ch.find(_W + "sdtContent") if ch.tag == _W + "sdt" else ch
            if inner is not None:
                yield from _kids(inner, tag)

def _table_lines(tbl, depth):
    lines = []
    for tr in _kids(tbl, _W + "tr"):
        cells = [_blocks_to_lines(tc, depth + 1) for tc in _kids(tr, _W + "tc")]
        if not any(cells):
            continue
        if all(len(c) <= 1 for c in cells):                 # a data row: "Label<TAB>Value"
            line = "\t".join(c[0] if c else "" for c in cells).rstrip("\t")
            if line.strip():
                lines.append(line)
        else:                                               # a layout cell with several lines: keep them in order
            for c in cells:
                lines.extend(c)
    return lines

def _blocks_to_lines(parent, depth=0):
    if depth > 12:                                          # absurdly nested tables: stop, don't recurse forever
        return []
    lines = []
    for b in _block_children(parent):
        if b.tag == _W + "p":
            for part in _para_text(b).split("\n"):
                if part.strip():
                    lines.append(part)
        else:
            lines.extend(_table_lines(b, depth))
    return lines

def _textbox_lines(root):
    """Text inside text boxes / shapes (name banners, skills sidebars...). Word stores each box twice
    (a modern copy and a legacy fallback copy): read only the modern one."""
    lines = []
    for box in root.iter(_W + "txbxContent"):
        if any(a.tag in (_MC + "Fallback", _W + "txbxContent") for a in box.iterancestors()):
            continue
        lines.extend(_blocks_to_lines(box))
    return lines

def _clean_group(lines):
    """Remove duplicates (same header repeated on every section) and bare page numbers, keeping order."""
    seen, out = set(), []
    for ln in lines:
        key = ln.strip()
        if not key or key in seen or _PAGE_NUMBER_LINE.match(key):
            continue
        seen.add(key); out.append(ln)
    return out

def _header_footer_lines(doc):
    heads, foots = [], []
    try:
        odd_even = bool(doc.settings.odd_and_even_pages_header_footer)
    except Exception:
        odd_even = False
    for sec in doc.sections:
        variants = [("header", sec.header, "footer", sec.footer)]
        if getattr(sec, "different_first_page_header_footer", False):
            variants.append(("header", sec.first_page_header, "footer", sec.first_page_footer))
        if odd_even:
            variants.append(("header", sec.even_page_header, "footer", sec.even_page_footer))
        for _, h, _, f in variants:
            for part, bucket in ((h, heads), (f, foots)):
                try:
                    if part.is_linked_to_previous:            # inherits the previous section's: already counted
                        continue
                    el = part._element
                    bucket.extend(_blocks_to_lines(el)); bucket.extend(_textbox_lines(el))
                except Exception:
                    continue
    return _clean_group(heads), _clean_group(foots)

def extract_docx_text(doc):
    """Full résumé text from an already-opened python-docx Document: header, body (paragraphs AND
    tables, in order), text boxes, footer."""
    body = doc.element.body
    head, foot = _header_footer_lines(doc)
    main = _blocks_to_lines(body)
    boxes = _textbox_lines(body)
    return "\n".join(head + main + boxes + foot)

def _check_docx_zip(data, max_bytes=150 * 1024 * 1024, max_files=20000):
    """A .docx is a zip. Refuse one that would expand to an absurd size (a 'zip bomb') before opening it."""
    import zipfile
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            infos = z.infolist()
            if len(infos) > max_files or sum(i.file_size for i in infos) > max_bytes:
                raise LegacyDocError("BAD_DOC")
    except LegacyDocError:
        raise
    except Exception as e:                           # bad zip, corrupt file names, anything else: unreadable
        raise LegacyDocError("BAD_DOC") from e

def extract_text(data: bytes, filename: str) -> str:
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return "\n".join(p.extract_text() for p in pdf.pages if p.extract_text())
    elif name.endswith((".docx", ".doc")):
        # Decide by what the file REALLY is (its first bytes), not by its name.
        if data[:4] == b"PK\x03\x04":                 # modern Word (.docx is a zip of XML)
            _check_docx_zip(data)
            try:
                doc = DocxDocument(io.BytesIO(data))
            except Exception as e:
                raise LegacyDocError("BAD_DOC") from e
            try:
                text = extract_docx_text(doc)
                if text.strip():
                    return text
            except Exception as e:
                print(f"[docx] full reader failed ({type(e).__name__}); using the basic paragraph reader")
            try:
                return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            except Exception as e:
                raise LegacyDocError("BAD_DOC") from e
        if data[:8] == _OLE_MAGIC:                    # classic Word 97-2003 (.doc)
            return extract_legacy_doc_text(data)
        raise LegacyDocError("NOT_WORD")
    return ""
