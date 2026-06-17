#!/usr/bin/env python3
"""Incrementally anonymize NEW candidates' CVs into branded, PII-safe pages.

Usage: anonymize_cvs.py <candidates.csv> <cvs_dir> <cv_map.json>

For each Rubicon candidate with a résumé URL that is NOT already in cv_map.json:
  1. download the résumé PDF (Fillout / Google Drive / Docs)
  2. extract text (pypdf)
  3. ask Claude (structured output) to return ONLY anonymized fields — first name,
     profile, experience, skills, education; never surnames/email/phone/address/URLs
  4. render cvs/<slug>.html from a fixed template (the model never emits HTML)
  5. PII-audit the rendered page; only add to cv_map if it passes (fail-safe: a CV
     that can't be verified clean is left hidden, never published)

Requires ANTHROPIC_API_KEY in the environment. Idempotent: already-mapped
candidates are skipped, so it only ever processes the latest additions.
"""
import csv, json, os, re, subprocess, sys

MODEL = "claude-opus-4-8"   # change to claude-sonnet-4-6 / claude-haiku-4-5 to cut cost
CUSTOMER = "rubicon"

SYSTEM = (
    "You anonymize candidate résumés for a customer-facing hiring dashboard. "
    "Candidate identity MUST be protected. From the résumé text, extract a clean, "
    "truthful professional profile, but REMOVE every piece of personally identifying "
    "information: full/last names (keep ONLY the first name), email addresses, phone "
    "numbers, home/street addresses, LinkedIn or any personal/social URLs, links, "
    "national ID numbers, and date of birth. Keep employers, job titles, dates, "
    "achievements, skills, and education (degree/field/institution/year). Do not invent "
    "facts. Repair broken word-wrapping from the extracted text into clean prose. "
    "Return only the requested structured fields."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "first_name": {"type": "string"},
        "profile": {"type": "string"},
        "experience": {"type": "array", "items": {"type": "object", "properties": {
            "title": {"type": "string"}, "company": {"type": "string"},
            "dates": {"type": "string"},
            "bullets": {"type": "array", "items": {"type": "string"}},
        }, "required": ["title", "company", "dates", "bullets"], "additionalProperties": False}},
        "skills": {"type": "array", "items": {"type": "string"}},
        "education": {"type": "array", "items": {"type": "object", "properties": {
            "credential": {"type": "string"}, "institution": {"type": "string"},
            "year": {"type": "string"},
        }, "required": ["credential", "institution", "year"], "additionalProperties": False}},
    },
    "required": ["first_name", "profile", "experience", "skills", "education"],
    "additionalProperties": False,
}

def slugify(n): return re.sub(r"[^a-z0-9]+", "-", n.strip().lower()).strip("-")

def download_url(u):
    u = u.strip()
    m = re.search(r"/file/d/([A-Za-z0-9_-]+)", u)
    if "drive.google" in u and m: return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    m2 = re.search(r"/document/d/([A-Za-z0-9_-]+)", u)
    if "docs.google.com/document" in u and m2: return f"https://docs.google.com/document/d/{m2.group(1)}/export?format=pdf"
    return u

def extract_text(url, tmp):
    import pypdf
    if subprocess.run(["curl", "-fsSL", download_url(url), "-o", tmp], capture_output=True).returncode != 0:
        return ""
    try:
        txt = "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(tmp).pages)
    except Exception:
        return ""
    txt = re.sub(r"[ \t]+", " ", txt); txt = re.sub(r"\n(?=[a-z0-9,(])", "", txt)
    return re.sub(r"\n{2,}", "\n", txt).strip()

def esc(s): return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def render(d, role, location):
    jobs = "".join(
        f'<div class="job"><div class="job-h"><span class="job-t">{esc(j["title"])}'
        + (f' — {esc(j["company"])}' if j.get("company") else "")
        + f'</span><span class="job-d">{esc(j.get("dates",""))}</span></div>'
        + ("<ul>" + "".join(f"<li>{esc(b)}</li>" for b in j.get("bullets", [])) + "</ul>" if j.get("bullets") else "")
        + "</div>"
        for j in d.get("experience", []))
    chips = "".join(f'<span class="chip">{esc(s)}</span>' for s in d.get("skills", []))
    edu = "".join(
        f'<div class="job"><div class="job-h"><span class="job-t">{esc(e.get("credential",""))}</span>'
        f'<span class="job-d">{esc(e.get("year",""))}</span></div>'
        + (f'<div style="font-size:13px;color:var(--mut)">{esc(e["institution"])}</div>' if e.get("institution") else "")
        + "</div>"
        for e in d.get("education", []))
    edu_section = f'<section><h2>Education</h2>{edu}</section>' if edu else ""
    first = esc(d.get("first_name", "Candidate"))
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{first} — Anonymized CV · Rubicon × Sagan</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;500;600;700&family=Playfair+Display:wght@500;600;700&family=Poppins:wght@500;600&display=swap" rel="stylesheet"/>
<style>
  :root{{--green:#00835a;--green-dark:#006344;--ink:#0a1a14;--ink-2:#374151;--mut:#6b7280;--line:#e5e7eb;--light:#f4f8f6;--paper:#fff;--accent-light:#34d399;}}
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{font-family:'Open Sans',sans-serif;color:var(--ink);background:#eef3f0;line-height:1.55;-webkit-font-smoothing:antialiased;}}
  .sheet{{max-width:820px;margin:30px auto;background:var(--paper);border-radius:18px;overflow:hidden;box-shadow:0 16px 44px rgba(10,26,20,.12);}}
  .top{{background:linear-gradient(160deg,#0d2119,#061210 75%);color:#fff;padding:34px 40px 28px;position:relative;overflow:hidden;border-top:3px solid var(--green);}}
  .top::after{{content:'';position:absolute;inset:0;background:radial-gradient(420px 240px at 85% 0%, rgba(0,131,90,.28), transparent 65%);}}
  .top>*{{position:relative;}}
  .brandrow{{display:flex;align-items:center;gap:12px;margin-bottom:22px;}}
  .brandrow img{{height:20px;filter:brightness(0) invert(1);}}
  .sep{{width:1px;height:20px;background:rgba(255,255,255,.25);}}
  .brandrow span{{font-family:'Poppins',sans-serif;font-size:10px;letter-spacing:1.6px;text-transform:uppercase;color:rgba(255,255,255,.6);}}
  .top h1{{font-family:'Playfair Display',serif;font-weight:600;font-size:40px;line-height:1;}}
  .top .role{{font-family:'Poppins',sans-serif;color:var(--accent-light);font-size:13px;letter-spacing:.5px;margin-top:8px;text-transform:uppercase;}}
  .anon{{display:inline-flex;align-items:center;gap:7px;margin-top:18px;font-family:'Poppins',sans-serif;font-size:11px;color:rgba(255,255,255,.7);background:rgba(0,131,90,.2);border:1px solid rgba(0,131,90,.45);padding:6px 12px;border-radius:30px;}}
  .anon::before{{content:'';width:7px;height:7px;border-radius:50%;background:var(--accent-light);}}
  .body{{padding:34px 40px 40px;}}
  .body section{{margin-bottom:28px;}}
  h2{{font-family:'Poppins',sans-serif;font-size:12px;letter-spacing:1.8px;text-transform:uppercase;color:var(--green-dark);margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid var(--line);}}
  .lead{{font-size:15px;color:var(--ink-2);}}
  .job{{margin-bottom:18px;}}
  .job-h{{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;}}
  .job-t{{font-family:'Playfair Display',serif;font-weight:600;font-size:17px;}}
  .job-d{{font-family:'Poppins',sans-serif;font-size:11px;color:var(--mut);white-space:nowrap;}}
  ul{{list-style:none;margin-top:9px;}}
  li{{position:relative;padding-left:18px;margin-bottom:7px;font-size:13.5px;color:var(--ink-2);}}
  li::before{{content:'';position:absolute;left:0;top:8px;width:6px;height:6px;border-radius:2px;background:var(--green);}}
  .chips{{display:flex;flex-wrap:wrap;gap:8px;}}
  .chip{{font-family:'Poppins',sans-serif;font-size:12px;color:var(--green-dark);background:var(--light);border:1px solid var(--line);padding:5px 12px;border-radius:30px;}}
  .foot{{padding:18px 40px;background:var(--light);border-top:1px solid var(--line);font-family:'Poppins',sans-serif;font-size:11px;color:var(--mut);text-align:center;}}
</style></head>
<body><div class="sheet">
  <div class="top">
    <div class="brandrow"><img src="https://www.rubicon.com/wp-content/uploads/2021/05/logo-brand.svg" alt="Rubicon"/><div class="sep"></div><span>Talent Selection</span></div>
    <h1>{first}</h1>
    <div class="role">{esc(role)} · {esc(location)}</div>
    <div class="anon">Anonymized profile — contact details removed</div>
  </div>
  <div class="body">
    <section><h2>Profile</h2><p class="lead">{esc(d.get("profile",""))}</p></section>
    <section><h2>Work Experience</h2>{jobs}</section>
    {f'<section><h2>Core Skills</h2><div class="chips">{chips}</div></section>' if chips else ''}
    {edu_section}
  </div>
  <div class="foot">Anonymized by Sagan · Personal contact information, full name, and address removed to protect candidate privacy.</div>
</div></body></html>"""

def pii_clean(html, source_text, first=""):
    """Return True if no PII detected. Fail closed."""
    body = re.sub(r"<style.*?</style>", "", html, flags=re.S)
    EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
    if EMAIL.search(body): return False
    # real phone numbers (>=9 digits), ignoring 4-digit year ranges
    for m in re.finditer(r"\+?\d[\d\-\s().]{7,}\d", body):
        if re.fullmatch(r"\d{4}\s*[-–]\s*\d{4}", m.group().strip()): continue
        if len(re.sub(r"\D", "", m.group())) >= 9: return False
    # external links beyond the template's font + logo
    for u in re.findall(r"https?://[^\s\"'<>]+", html):
        if not any(d in u for d in ("fonts.googleapis", "fonts.gstatic", "rubicon.com/wp-content")):
            return False
    # surnames: any email-local-part name token (len>=4) from source appearing in body
    # (the first name is allowed — it's the one identifier we intentionally keep)
    fl = (first or "").strip().lower()
    for e in EMAIL.findall(source_text):
        for tok in re.split(r"[._\-0-9]+", e.split("@")[0]):
            t = tok.lower()
            if len(t) >= 4 and t != fl and re.search(r"\b" + re.escape(t) + r"\b", body.lower()):
                return False
    return True

def col(row, *names):
    for n in names:
        for k in row:
            if k and k.strip().lower() == n: return (row[k] or "").strip()
    for n in names:
        for k in row:
            if k and n in k.strip().lower(): return (row[k] or "").strip()
    return ""

def main():
    cand_csv, cvs_dir, map_path = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(cvs_dir, exist_ok=True)
    cv_map = {}
    if os.path.exists(map_path):
        try: cv_map = json.load(open(map_path, encoding="utf-8"))
        except Exception: cv_map = {}

    import anthropic
    client = anthropic.Anthropic()

    rows = list(csv.DictReader(open(cand_csv, newline="", encoding="utf-8")))
    rub = [r for r in rows if col(r, "company name").lower().startswith(CUSTOMER)]
    added = 0
    for r in rub:
        name = col(r, "candidates name", "candidate name")
        url = col(r, "resume link", "resume")
        if not name or name in cv_map or not url:
            continue
        text = extract_text(url, f"/tmp/_cv_{slugify(name)}.pdf")
        if len(text) < 200:
            print(f"skip {name}: low/no extractable text"); continue
        try:
            resp = client.messages.create(
                model=MODEL, max_tokens=4096, system=SYSTEM,
                output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
                messages=[{"role": "user", "content": "Anonymize this résumé:\n\n" + text[:24000]}],
            )
            data = json.loads(next(b.text for b in resp.content if b.type == "text"))
        except Exception as e:
            print(f"skip {name}: model error {e}"); continue
        if not data.get("first_name"):
            data["first_name"] = name.split()[0]
        slug = slugify(name)
        html = render(data, col(r, "title/role", "title", "role"), col(r, "candidates location", "location"))
        if not pii_clean(html, text, data["first_name"]):
            print(f"HOLD {name}: PII audit failed — CV left hidden"); continue
        open(os.path.join(cvs_dir, f"{slug}.html"), "w", encoding="utf-8").write(html)
        cv_map[name] = f"{cvs_dir}/{slug}.html"
        added += 1
        print(f"anonymized {name} -> {cvs_dir}/{slug}.html")

    json.dump(cv_map, open(map_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"done: {added} new CV(s) anonymized; {len(cv_map)} total mapped")

if __name__ == "__main__":
    main()
