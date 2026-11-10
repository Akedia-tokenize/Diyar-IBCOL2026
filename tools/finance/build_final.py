"""Combine untouched DIYAR v2.7 pages with an in-place Annex D financial extension.

The addendum is placed after original page 24, before Annex E.
No page of the original is redrawn, deleted or rewritten.
"""
from __future__ import annotations

import hashlib
import re
from io import BytesIO
from pathlib import Path

import fitz
from openpyxl import load_workbook
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, PageBreak, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"paper"/"DIYAR whitepaper v2.7.pdf"
FIN=ROOT/"reference-and-tests"/"DIYAR_cost_model.xlsx"
OUT=ROOT/"paper"/"DIYAR_Whitepaper_v2.7_Financial_Annex_D1_Complete.pdf"
ANN=ROOT/"paper"/"DIYAR_Annexes_A-H_with_D1.pdf"

doc=fitz.open(SOURCE)
assert len(doc)==42, f"Expected v2.7 42-page archival PDF, found {len(doc)}"
original_digest=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
base=load_workbook(FIN,data_only=True,read_only=True)
annual=float(base["Annual cost"]["B11"].value)
assert abs(annual-1785795.123092998)<0.03, f"Source cost model changed: {annual}"
base.close()
sizes=[100,1000,10000]
# The exact base-case model's cost functions are preserved:
# annual= (29.3061283125+7064.16+1766.04+180000)
#        + N*(0.03932145883008+9.65424023763847+50+100).
fixed=29.3061283125+7064.16+1766.04+180000.0
unit=0.03932145883008+9.65424023763847+50+100
assert abs(fixed+10000*unit-annual)<0.03
def norm(n,fte=3,besu=4):
    return fixed+unit*n-(3-fte)*60000-(4-besu)*147.17*12
def cash(n,fte=3,besu=4):
    return norm(n,fte,besu)+900*n
def usd(v):
    return f"\${v:,.0f}"
assert abs(norm(100)-204828.86229795936)<0.03
assert abs(cash(100)-294828.86229795936)<0.03
assert abs(norm(100,1,0)-77764.70229795936)<0.03
assert abs(cash(100,1,0)-167764.70229795936)<0.03

# Confirm the pre-existing Annex boundary directly from original pages.
firstlines=lambda i: doc[i].get_text(sort=True)[:300].upper()
covers={"A":6,"B":10,"C":15,"D":20,"E":24,"F":29,"G":34,"H":38}
for key,i in covers.items():
    assert f"ANNEX {key}" in firstlines(i), f"Incorrect Annex {key} cover at source page {i+1}"
existing=" ".join(doc[i].get_text(sort=True) for i in range(20,24))
indices=[int(x) for x in re.findall(r"\bD\.(\d+)\s+[A-Za-z]",existing)]
assert indices and min(indices)==1, f"Could not determine section numbering: {indices}"
next_section=max(indices)+1
section=f"D.{next_section}"
print("Original Annex D section numbers",sorted(set(indices)),"=> new section",section,flush=True)
print("Original SHA256",original_digest,flush=True)

# Two-page editorial style, consistent with separately reviewed finance supplement.
fdir=Path("/usr/share/fonts/truetype/dejavu")
if (fdir/"DejaVuSans.ttf").exists():
    pdfmetrics.registerFont(TTFont("DV",(fdir/"DejaVuSans.ttf").as_posix()))
    pdfmetrics.registerFont(TTFont("DV-B",(fdir/"DejaVuSans-Bold.ttf").as_posix()))
    font,bold="DV","DV-B"
else:
    font,bold="Helvetica","Helvetica-Bold"

navy=colors.HexColor("#192B46")
ink=colors.HexColor("#24344F")
violet=colors.HexColor("#6854AD")
gray=colors.HexColor("#63748A")
grid=colors.HexColor("#DCE3EC")
pale=colors.HexColor("#F0ECFA")
styles={
"title":ParagraphStyle("title",fontName=bold,fontSize=16.6,leading=21.5,textColor=navy,spaceAfter=9),
"sub":ParagraphStyle("sub",fontName=font,fontSize=8.5,leading=11.8,textColor=gray,spaceAfter=9),
"head":ParagraphStyle("head",fontName=bold,fontSize=10.2,leading=13.2,textColor=navy,spaceBefore=9,spaceAfter=4),
"body":ParagraphStyle("body",fontName=font,fontSize=7.9,leading=11.5,textColor=ink,spaceAfter=7),
"small":ParagraphStyle("small",fontName=font,fontSize=6.9,leading=9.4,textColor=gray,spaceAfter=7),
"th":ParagraphStyle("th",fontName=bold,fontSize=6.8,leading=9,textColor=colors.white),
"cell":ParagraphStyle("cell",fontName=font,fontSize=6.85,leading=9.4,textColor=ink),
}
def P(txt,style="body"):return Paragraph(txt,styles[style])
def T(rows,widths):
    cells=[[P(str(x),"th" if ri==0 else "cell") for x in row] for ri,row in enumerate(rows)]
    out=Table(cells,colWidths=widths,repeatRows=1,hAlign="LEFT")
    out.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),navy),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LEFTPADDING",(0,0),(-1,-1),6),
        ("RIGHTPADDING",(0,0),(-1,-1),6),
        ("TOPPADDING",(0,0),(-1,-1),4.6),
        ("BOTTOMPADDING",(0,0),(-1,-1),4.6),
        ("LINEBELOW",(0,0),(-1,-1),.25,grid),
    ]))
    return out

pagewidth,pageheight=doc[20].rect.width,doc[20].rect.height
packet=BytesIO()
margin=17*mm
width=pagewidth-2*margin
def footer(c,document):
    c.saveState()
    c.setStrokeColor(grid);c.setLineWidth(.55)
    c.line(margin,16*mm,pagewidth-margin,16*mm)
    c.setFont(font,7);c.setFillColor(gray)
    c.drawString(margin,11.6*mm,"DIYAR / IBCOL 2026 / FINANCIAL EXTENSION / 10 NOV 2026")
    c.drawRightString(pagewidth-margin,11.6*mm,f"ANNEX D / {document.page} OF 2")
    c.restoreState()

pdf=SimpleDocTemplate(packet,pagesize=(pagewidth,pageheight),leftMargin=margin,rightMargin=margin,
    topMargin=17*mm,bottomMargin=19*mm,title=f"DIYAR Annex D Financial Extension {section}",
    author="DIYAR / Team Akedia",subject="Pilot-to-scale and year-one cash bridge")
story=[]
story += [
P(f"ANNEX D / {section} | PILOT-TO-SCALE COST AND FUNDING REQUIREMENTS","title"),
P("Integrated supplement to the 10 November 2026 DIYAR whitepaper v2.7 and original Annex D. The original model, E1-E4 outcomes and 112-value reconciliation are preserved. All monetary figures are USD.","sub"),
P(f"{section}.1  What the original USD 178.58 measures","head"),
P("The existing six-tab cost model reports <b>$1,785,795.12 per year for 10,000 buildings ($178.58/building-year)</b>, under a full operating-stack scenario with three staff FTE, four Besu validators, one compute VM and 0 notary nodes. It is a <b>normalized annual economic cost</b>, not the cash required to onboard a complete portfolio in its first year."),
P("Its assumed <b>$1,000 one-time onboarding cost per building</b> is annualized over ten years ($100 per building-year). When all buildings enter in Year 1, the modeled cash requirement must replace that $100 fraction with the full $1,000. Therefore, for N newly onboarded buildings: <b>Year-1 priced cash subtotal = normalized annual economic cost + $900 × N</b>. This is an accounting bridge, not an externally validated new price."),
P(f"{section}.2  Mechanical scale comparison","head"),
]
table=[
["Same full stack","Annual economic cost","Year-1 priced cash subtotal","Year-1 cash per building"],
*[[f"{n:,} buildings",usd(norm(n)),usd(cash(n)),usd(cash(n)/n)] for n in sizes],
]
story += [T(table,[width*.22,width*.245,width*.295,width*.24]),
P("The 100- and 1,000-building rows retain the full reference configuration and are deliberately <b>not optimized pilot budgets</b>. The 10,000-building annual amount agrees with the unchanged source cost workbook to the cent; values in the table are rounded.","small"),
P(f"{section}.3  Lean pilot illustration, not a commitment","head"),
T([
["100-building scenario","Original full stack","Lean phase-1 hypothesis"],
["Staff FTE","3","1 (not workload-validated)"],
["Besu validators","4","0 (Besu deferred)"],
["Compute / notary nodes","1 / 0","1 / 0"],
["Annual economic cost",usd(norm(100)),usd(norm(100,1,0))],
["Year-1 priced cash subtotal",usd(cash(100)),usd(cash(100,1,0))],
],[width*.36,width*.30,width*.34]),
P("A phase-1 witnessed transparency log and public-chain anchoring design is consistent with Annex F, which defers Besu. <b>However witness cost is not included, and one FTE has not been validated as sufficient.</b> The USD 167,765 lean figure is only a partial priced cash subtotal, <b>not a complete funded pilot budget</b>.","small"),
P(f"{section}.4  Human operations at scale","head"),
P("At 5% random annual physical inspections and 0.189 quarterly review cases per building-year, 100 buildings imply approximately <b>5 inspections, 18.9 review cases and 100 initial onboarding events</b> if the cohort joins in Year 1. The 10,000-building scale implies 500 inspections, 1,890 cases and 10,000 onboarding events. Inspection capacity, contractor availability and consent lead times are not established by the current FTE assumptions."),
PageBreak(),
P(f"ANNEX D / {section} | FUNDING, PROCUREMENT AND ASSURANCE","title"),
P("The finance test for implementation is not just average annual cost. It is which cash obligations arise in the first year, who funds them, and what evidence makes the pilot financeable.","sub"),
P(f"{section}.5  Unpriced prerequisites","head"),
T([
["Dependency","Evidence required before a defensible funding request"],
["Data rights and access","Named utility/operator integration path, building permissions, consent, API entitlement and access SLA."],
["Integration and deployment","Scoped quote for source ingestion, registry mapping, error handling, hosting and acceptance testing."],
["Physical binding and inspections","Qualified installation-verification quotation; reconcile scope against the assumed $1,000 onboarding and $1,000 inspection charges without double-counting."],
["Witnesses, HSM and keys","Independent witness operations, PKI/HSM procurement, issuance, recovery, rotation and breach response."],
["Procurement and law","Contracting, privacy, insurance, liability, supervision and explicitly priced contingency."]
],[width*.31,width*.69]),
P("The two large field-cost assumptions ($1,000 onboarding and $1,000 inspection) are <b>not verified Dubai meter-binding supplier quotes</b>. A generic energy-audit or building-inspection advertisement has materially different scope and cannot silently validate them.","small"),
P(f"{section}.6  Funding and verifier independence","head"),
P("Potential pilot sponsors include an asset owner, lender, valuer, or public innovation program. The source model <b>does not establish a signed buyer or sponsor</b>. Any verifier fee should be fixed or based on work performed, and contractually independent of whether an evidence claim passes, fails or receives a lower grade. Outcome-linked fees could undermine neutrality."),
P(f"{section}.7  Four financing decision gates","head"),
T([
["Gate","Deliverable","Decision"],
["1. Eligibility","100-building cohort, consent and metering access","Confirm scope"],
["2. Delivery capacity","Staffing, witness model, inspection and integration plan","Approve design"],
["3. Procurement","Third-party RFQs for integration, fieldwork, HSM, legal and contingency","Approve cash envelope"],
["4. Assurance","Independent replay and fail-closed test evidence, milestones and acceptance criteria","Authorize pilot"]
],[width*.21,width*.58,width*.21]),
P(f"{section}.8  Evidence basis and boundary","head"),
P("The figures above derive only from <b>DIYAR_cost_model.xlsx</b> (Inputs, Annual cost, Custody deposit and Review vs alpha) and the separate formula-driven pilot-to-scale financial supplement. They do not modify the original six-sheet model, the USD 178.58 baseline or its E1-E4 scientific claims. They do not prove a Dubai utility deployment, site access, regulatory approval, staffed operational sufficiency, or mainnet anchoring. The costs omitted above must be quoted before a full cash funding request can be represented as complete."),
P("<b>Available supporting package:</b> https://github.com/Akedia-tokenize/Diyar-IBCOL2026 · original workbook under Reference & Tests · scenario register under Results / pilot-to-scale. The original whitepaper's Section V financial claims are unchanged; this annex provides their pilot-stage accounting qualification.","small"),
]
pdf.build(story,onFirstPage=footer,onLaterPages=footer)
packet.seek(0)
additional=fitz.open(stream=packet.read(),filetype="pdf")
assert len(additional)==2, f"Financial extension overflowed to {len(additional)} pages"
# Assemble final full whitepaper and separate A-H annex package.
combined=fitz.open()
combined.insert_pdf(doc,from_page=0,to_page=23)
combined.insert_pdf(additional)
combined.insert_pdf(doc,from_page=24,to_page=len(doc)-1)
annexes=fitz.open()
annexes.insert_pdf(doc,from_page=6,to_page=23)
annexes.insert_pdf(additional)
annexes.insert_pdf(doc,from_page=24,to_page=len(doc)-1)
assert len(combined)==44 and len(annexes)==38
for i in range(len(doc)):
    new_i = i if i<24 else i+2
    assert doc[i].get_text() == combined[new_i].get_text(),f"Source text changed on original page {i+1}"
# Deep links (PDF TOC) keep the eight existing annex entrances obvious.
items=[("A",6),("B",10),("C",15),("D",20),("E",24),("F",29),("G",34),("H",38)]
toc=[[1,"Whitepaper (original six pages)",1]]
toc_a=[]
for letter,idx in items:
    new_idx=idx if idx<24 else idx+2
    toc.append([1,f"Annex {letter}",new_idx+1])
    toc_a.append([1,f"Annex {letter}",new_idx-6+1])
    if letter=="D":
        toc.append([2,f"Annex D / {section} Pilot-to-scale financial extension",25])
        toc_a.append([2,f"Annex D / {section} Pilot-to-scale financial extension",19])
combined.set_toc(toc)
annexes.set_toc(toc_a)
combined.set_metadata({"title":"DIYAR Whitepaper v2.7 and Annexes A-H with Integrated Financial Extension",
"author":"Fatemeh Zahra Bazrgar / Team Akedia",
"subject":"Original 2026-11-10 v2.7 preserved; additional D-section pilot-to-scale analysis 2026-11-10",
"keywords":"DIYAR, IBCOL 2026, provenance, sustainability, pilot cost, financial annex"})
annexes.set_metadata({"title":"DIYAR Annexes A-H with Pilot-to-Scale Financial Extension",
"author":"Team Akedia","subject":"Original annexes A-H preserved with two inserted Annex D financial pages"})
combined.save(OUT,garbage=3,deflate=True)
annexes.save(ANN,garbage=3,deflate=True)
print("READY",OUT,OUT.stat().st_size,len(combined),"pages")
print("READY",ANN,ANN.stat().st_size,len(annexes),"pages")
print("Original pages and text verified preserved: 42/42")
print("Financial extension located at combined pages 25-26; annex-only pages 19-20")
print("The original submitted v2.7 PDF remains untouched.")
