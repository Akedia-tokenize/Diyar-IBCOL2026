from pathlib import Path
import fitz, re
f=Path("paper/DIYAR whitepaper v2.7.pdf")
d=fitz.open(f)
print("PAGE MAP: total",len(d),"file bytes",f.stat().st_size,flush=True)
for i,page in enumerate(d):
    text=page.get_text(sort=True)
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    cand=[s[:110] for s in lines if re.search(r"annex|appendix|financial|cost model|sensitivity|table of contents|references",s,re.I)]
    print("PAGE",i+1,"FIRST",repr(" / ".join(lines[:4])[:180]),"KEYWORDS",repr(cand[:12]),flush=True)
