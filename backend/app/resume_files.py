"""Resume templates, DOCX/PDF generation and HTML preview. Ported from the Streamlit app."""
from io import BytesIO
from docx import Document as DocxDocument
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ══════════════════════════════════════
# RESUME TEMPLATES — same data, different look. Switching format re-renders
# instantly from the stored resume data (no extra AI call, no extra cost).
# ══════════════════════════════════════
RESUME_TEMPLATES = {
    "Bold": {
        "label": "Bold — dark header, amber accents",
        "font_docx": "Calibri", "pdf_font": "Helvetica", "pdf_font_bold": "Helvetica-Bold",
        "banner": True, "banner_fill": "1a1a1a",
        "name_color": "FFFFFF", "title_color": "F59E0B", "contact_color": "BBBBBB",
        "name_size": 20, "align": "center",
        "text_color": "1a1a1a", "muted_color": "555555", "company_color": "2E5FA3",
        "sec_color": "1a1a1a", "sec_rule": "F59E0B", "sec_rule_sz": 6, "sec_rule_pdf": 1.5,
        "bullet": "▸", "bullet_color": "F59E0B",
    },
    "Classic": {
        "label": "Classic — serif, traditional black & white",
        "font_docx": "Times New Roman", "pdf_font": "Times-Roman", "pdf_font_bold": "Times-Bold",
        "banner": False, "banner_fill": None,
        "name_color": "000000", "title_color": "333333", "contact_color": "444444",
        "name_size": 22, "align": "center",
        "text_color": "000000", "muted_color": "333333", "company_color": "000000",
        "sec_color": "000000", "sec_rule": "000000", "sec_rule_sz": 6, "sec_rule_pdf": 0.75,
        "bullet": "•", "bullet_color": "000000",
    },
    "Modern": {
        "label": "Modern — navy & blue accents, clean sans-serif",
        "font_docx": "Calibri", "pdf_font": "Helvetica", "pdf_font_bold": "Helvetica-Bold",
        "banner": False, "banner_fill": None,
        "name_color": "1F3A5F", "title_color": "2E5FA3", "contact_color": "555555",
        "name_size": 24, "align": "left",
        "text_color": "222222", "muted_color": "555555", "company_color": "2E5FA3",
        "sec_color": "2E5FA3", "sec_rule": "2E5FA3", "sec_rule_sz": 8, "sec_rule_pdf": 1.5,
        "bullet": "•", "bullet_color": "2E5FA3",
    },
    "Minimal": {
        "label": "Minimal ATS — plain and simple, max compatibility",
        "font_docx": "Arial", "pdf_font": "Helvetica", "pdf_font_bold": "Helvetica-Bold",
        "banner": False, "banner_fill": None,
        "name_color": "000000", "title_color": "000000", "contact_color": "333333",
        "name_size": 18, "align": "left",
        "text_color": "000000", "muted_color": "333333", "company_color": "000000",
        "sec_color": "000000", "sec_rule": None, "sec_rule_sz": 0, "sec_rule_pdf": 0,
        "bullet": "•", "bullet_color": "000000",
    },
}

def _rgb(hexstr):
    return RGBColor(int(hexstr[0:2], 16), int(hexstr[2:4], 16), int(hexstr[4:6], 16))

def make_docx(data, template="Bold"):
    cfg = RESUME_TEMPLATES.get(template) or RESUME_TEMPLATES["Bold"]
    F = cfg["font_docx"]
    doc = DocxDocument()
    for sc in doc.sections:
        sc.top_margin = Inches(0.6); sc.bottom_margin = Inches(0.6)
        sc.left_margin = Inches(0.7); sc.right_margin = Inches(0.7)
    TXT = _rgb(cfg["text_color"]); MUT = _rgb(cfg["muted_color"]); LGR = _rgb("BBBBBB")
    COMPANY = _rgb(cfg["company_color"])
    from docx.oxml.ns import qn; from docx.oxml import OxmlElement
    def shade(p, fill):
        pPr = p._p.get_or_add_pPr(); shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear'); shd.set(qn('w:color'), 'auto'); shd.set(qn('w:fill'), fill); pPr.append(shd)
    def bdr(p, color, sz):
        pPr = p._p.get_or_add_pPr(); pBdr = OxmlElement('w:pBdr')
        b = OxmlElement('w:bottom'); b.set(qn('w:val'), 'single'); b.set(qn('w:sz'), str(sz))
        b.set(qn('w:space'), '1'); b.set(qn('w:color'), color); pBdr.append(b); pPr.append(pBdr)
    def hp(txt, sz, col, bold=False, align=WD_ALIGN_PARAGRAPH.LEFT, before=0, after=4, sh=None):
        p = doc.add_paragraph(); p.alignment = align
        p.paragraph_format.space_before = Pt(before); p.paragraph_format.space_after = Pt(after)
        r = p.add_run(str(txt or "")); r.bold = bold; r.font.size = Pt(sz); r.font.color.rgb = col; r.font.name = F
        if sh: shade(p, sh)
    def sec(t):
        p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(10); p.paragraph_format.space_after = Pt(4)
        r = p.add_run(str(t)); r.bold = True; r.font.size = Pt(11); r.font.color.rgb = _rgb(cfg["sec_color"]); r.font.name = F
        if cfg["sec_rule"]: bdr(p, cfg["sec_rule"], cfg["sec_rule_sz"])
    def comp(lbl, val):
        p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(2); p.paragraph_format.space_after = Pt(2)
        r1 = p.add_run(str(lbl) + "  "); r1.bold = True; r1.font.color.rgb = TXT; r1.font.size = Pt(10); r1.font.name = F
        r2 = p.add_run(str(val)); r2.font.color.rgb = MUT; r2.font.size = Pt(10); r2.font.name = F
    def bul(txt):
        p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(2); p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.left_indent = Inches(0.2)
        r1 = p.add_run(cfg["bullet"] + "  "); r1.bold = True; r1.font.color.rgb = _rgb(cfg["bullet_color"]); r1.font.size = Pt(10); r1.font.name = F
        r2 = p.add_run(str(txt)); r2.font.size = Pt(10); r2.font.name = F; r2.font.color.rgb = TXT
    al = WD_ALIGN_PARAGRAPH.CENTER if cfg["align"] == "center" else WD_ALIGN_PARAGRAPH.LEFT
    sh = cfg["banner_fill"] if cfg["banner"] else None
    hp(data.get("name"), cfg["name_size"], _rgb(cfg["name_color"]), bold=True, align=al, after=3, sh=sh)
    hp(data.get("title"), 11, _rgb(cfg["title_color"]), bold=True, align=al, after=3, sh=sh)
    hp(data.get("contact"), 9, _rgb(cfg["contact_color"]), align=al, after=8, sh=sh)
    sec("PROFESSIONAL SUMMARY")
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(4)
    r = p.add_run(str(data.get("summary", ""))); r.font.size = Pt(10); r.font.name = F; r.font.color.rgb = TXT
    if data.get("competencies"):
        sec("CORE COMPETENCIES")
        for c in data["competencies"]: comp(c["label"], c["value"])
    sec(data.get("experience_heading", "WORK EXPERIENCE"))
    for job in data.get("experience", []):
        p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(8); p.paragraph_format.space_after = Pt(2)
        r1 = p.add_run(str(job.get("title", ""))); r1.bold = True; r1.font.color.rgb = TXT; r1.font.size = Pt(11); r1.font.name = F
        r2 = p.add_run("  |  "); r2.font.color.rgb = LGR; r2.font.size = Pt(11); r2.font.name = F
        r3 = p.add_run(str(job.get("company", ""))); r3.bold = True; r3.font.color.rgb = COMPANY; r3.font.size = Pt(11); r3.font.name = F
        if job.get("dates"):
            r4 = p.add_run("    " + str(job["dates"])); r4.italic = True; r4.font.color.rgb = MUT; r4.font.size = Pt(10); r4.font.name = F
        for b in job.get("bullets", []): bul(b)
    if data.get("skills"):
        sec("TECHNICAL SKILLS")
        for s in data["skills"]: comp(s["label"], s["value"])
    if data.get("achievements"):
        sec("KEY ACHIEVEMENTS")
        for a in data["achievements"]: bul(a)
    sec("EDUCATION")
    p = doc.add_paragraph(); r = p.add_run(str(data.get("education", ""))); r.font.size = Pt(10); r.font.name = F; r.font.color.rgb = TXT
    if data.get("certifications"):
        sec("CERTIFICATIONS & LANGUAGES")
        p = doc.add_paragraph(); r = p.add_run(str(data["certifications"])); r.font.size = Pt(10); r.font.name = F; r.font.color.rgb = TXT
    buf = BytesIO(); doc.save(buf); buf.seek(0); return buf.read()

def make_pdf(data, template="Bold"):
    from xml.sax.saxutils import escape as _x
    cfg = RESUME_TEMPLATES.get(template) or RESUME_TEMPLATES["Bold"]
    C = lambda h: colors.HexColor("#" + h)
    F, FB = cfg["pdf_font"], cfg["pdf_font_bold"]
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=14*mm, bottomMargin=14*mm, leftMargin=18*mm, rightMargin=18*mm)
    back = C(cfg["banner_fill"]) if cfg["banner"] else None
    align = 1 if cfg["align"] == "center" else 0
    TX, MU, CO = cfg["text_color"], cfg["muted_color"], cfg["company_color"]
    s = getSampleStyleSheet()
    ns = ParagraphStyle("N", parent=s["Normal"], fontSize=cfg["name_size"], textColor=C(cfg["name_color"]), fontName=FB, alignment=align, backColor=back, spaceAfter=2, leading=cfg["name_size"] * 1.3)
    ts = ParagraphStyle("T", parent=s["Normal"], fontSize=11, textColor=C(cfg["title_color"]), fontName=FB, alignment=align, backColor=back, spaceAfter=2, leading=16)
    cs = ParagraphStyle("C", parent=s["Normal"], fontSize=9, textColor=C(cfg["contact_color"]), fontName=F, alignment=align, backColor=back, spaceAfter=10, leading=14)
    ss = ParagraphStyle("S", parent=s["Normal"], fontSize=10, textColor=C(cfg["sec_color"]), fontName=FB, spaceBefore=10, spaceAfter=3, leading=15)
    bs = ParagraphStyle("B", parent=s["Normal"], fontSize=9, textColor=C(MU), fontName=F, spaceBefore=2, spaceAfter=2, leading=13)
    bus = ParagraphStyle("BU", parent=s["Normal"], fontSize=9, textColor=C(TX), fontName=F, spaceBefore=2, spaceAfter=2, leading=13, leftIndent=10)
    bos = ParagraphStyle("BO", parent=s["Normal"], fontSize=9, fontName=F, spaceBefore=2, spaceAfter=2, leading=13)
    story = []
    story.extend([Paragraph(_x(str(data.get("name", ""))), ns), Paragraph(_x(str(data.get("title", ""))), ts), Paragraph(_x(str(data.get("contact", ""))), cs)])
    def sec(t):
        story.append(Paragraph(_x(t), ss))
        if cfg["sec_rule"]: story.append(HRFlowable(width="100%", thickness=cfg["sec_rule_pdf"], color=C(cfg["sec_rule"]), spaceAfter=4))
        else: story.append(Spacer(1, 2))
    def bul(t): story.append(Paragraph(f'<font color="#{cfg["bullet_color"]}"><b>{cfg["bullet"]}</b></font>  {_x(t)}', bus))
    def comp(l, v): story.append(Paragraph(f'<font color="#{TX}"><b>{_x(l)}</b></font>  <font color="#{MU}">{_x(v)}</font>', bos))
    sec("PROFESSIONAL SUMMARY"); story.append(Paragraph(_x(str(data.get("summary", ""))), bs))
    if data.get("competencies"):
        sec("CORE COMPETENCIES")
        for c in data["competencies"]: comp(str(c["label"]), str(c["value"]))
    sec(data.get("experience_heading", "WORK EXPERIENCE"))
    for job in data.get("experience", []):
        story.append(Spacer(1, 4))
        dates = f'<font color="#{MU}"><i>    {_x(str(job["dates"]))}</i></font>' if job.get("dates") else ""
        story.append(Paragraph(
            f'<font color="#{TX}"><b>{_x(str(job.get("title", "")))}</b></font>'
            f'<font color="#bbbbbb">  |  </font>'
            f'<font color="#{CO}"><b>{_x(str(job.get("company", "")))}</b></font>' + dates, bos))
        for b in job.get("bullets", []): bul(str(b))
    if data.get("skills"):
        sec("TECHNICAL SKILLS")
        for sk in data["skills"]: comp(str(sk["label"]), str(sk["value"]))
    if data.get("achievements"):
        sec("KEY ACHIEVEMENTS")
        for a in data["achievements"]: bul(str(a))
    sec("EDUCATION"); story.append(Paragraph(_x(str(data.get("education", ""))), bs))
    if data.get("certifications"):
        sec("CERTIFICATIONS & LANGUAGES"); story.append(Paragraph(_x(str(data["certifications"])), bs))
    doc.build(story); buf.seek(0); return buf.read()

def resume_preview_html(data, tpl):
    """Built-in preview of the chosen format as a white 'paper' card. Needs no
    extra libraries, so a preview is always visible; it mirrors each format's
    fonts, colours and layout (the download uses the exact layout)."""
    from html import escape as _e
    cfg = RESUME_TEMPLATES.get(tpl) or RESUME_TEMPLATES["Bold"]
    fam = cfg["font_docx"]
    # NB: no quote characters here - this value sits inside a single-quoted
    # style='...' attribute, and a stray ' would cut the whole style off.
    ff = ("Times New Roman,Times,serif" if fam == "Times New Roman"
          else "Arial,Helvetica,sans-serif" if fam == "Arial"
          else "Calibri,Carlito,Segoe UI,Helvetica,Arial,sans-serif")
    H = lambda h: "#" + h
    ta = "center" if cfg["align"] == "center" else "left"
    TX, MU, CO = H(cfg["text_color"]), H(cfg["muted_color"]), H(cfg["company_color"])
    P = []
    banner = f"background:{H(cfg['banner_fill'])};padding:10px 8px;" if cfg["banner"] else ""
    P.append(
        f"<div style='{banner}text-align:{ta};margin-bottom:6px'>"
        f"<div style='font-size:{cfg['name_size'] * 0.85:.0f}px;font-weight:800;color:{H(cfg['name_color'])};line-height:1.2'>{_e(str(data.get('name','')))}</div>"
        f"<div style='font-size:10.5px;font-weight:700;color:{H(cfg['title_color'])};margin-top:2px'>{_e(str(data.get('title','')))}</div>"
        f"<div style='font-size:8.5px;color:{H(cfg['contact_color'])};margin-top:2px'>{_e(str(data.get('contact','')))}</div></div>")
    def sec(t):
        rule = f"border-bottom:{cfg['sec_rule_pdf']}px solid {H(cfg['sec_rule'])};" if cfg["sec_rule"] else ""
        P.append(f"<div style='font-size:10px;font-weight:800;color:{H(cfg['sec_color'])};margin:11px 0 5px;padding-bottom:2px;{rule}'>{_e(t)}</div>")
    def line(lbl, val):
        P.append(f"<div style='margin:2px 0'><b style='color:{TX}'>{_e(str(lbl))}</b>&nbsp; <span style='color:{MU}'>{_e(str(val))}</span></div>")
    def bul(t):
        P.append(f"<div style='margin:2px 0 2px 10px;color:{TX}'><span style='color:{H(cfg['bullet_color'])};font-weight:700'>{cfg['bullet']}</span>&nbsp; {_e(str(t))}</div>")
    sec("PROFESSIONAL SUMMARY"); P.append(f"<div style='color:{MU}'>{_e(str(data.get('summary','')))}</div>")
    if data.get("competencies"):
        sec("CORE COMPETENCIES")
        for c in data["competencies"]: line(c.get("label", ""), c.get("value", ""))
    sec(data.get("experience_heading", "WORK EXPERIENCE"))
    for job in data.get("experience", []):
        dates = f" <i style='color:{MU}'>&nbsp;{_e(str(job['dates']))}</i>" if job.get("dates") else ""
        P.append(f"<div style='margin-top:7px'><b style='color:{TX}'>{_e(str(job.get('title','')))}</b>"
                 f"<span style='color:#bbb'> &nbsp;|&nbsp; </span><b style='color:{CO}'>{_e(str(job.get('company','')))}</b>{dates}</div>")
        for b in job.get("bullets", []): bul(b)
    if data.get("skills"):
        sec("TECHNICAL SKILLS")
        for s in data["skills"]: line(s.get("label", ""), s.get("value", ""))
    if data.get("achievements"):
        sec("KEY ACHIEVEMENTS")
        for a in data["achievements"]: bul(a)
    sec("EDUCATION"); P.append(f"<div style='color:{MU}'>{_e(str(data.get('education','')))}</div>")
    if data.get("certifications"):
        sec("CERTIFICATIONS & LANGUAGES"); P.append(f"<div style='color:{MU}'>{_e(str(data['certifications']))}</div>")
    # single line on purpose: blank/indented lines would be parsed as markdown code
    return (f"<div style='background:#fff;color:{TX};font-family:{ff};font-size:10px;line-height:1.5;"
            f"padding:24px 28px;border-radius:6px;box-shadow:0 2px 14px rgba(0,0,0,.5);max-width:560px;margin:2px 0 10px'>"
            + "".join(P) + "</div>")

