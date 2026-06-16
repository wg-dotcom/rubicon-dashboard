#!/usr/bin/env python3
"""Build rubicon-data.json from the two Google Sheets CSV exports.

Usage: build_data.py <candidates.csv> <core_member_hr.csv> <out.json>

Keeps ONLY Rubicon rows and customer-safe columns. The tracker's internal
margin columns (Budget, %WG, Deal Value) and link columns are never read.
"""
import csv, json, sys, datetime

CUSTOMER = "rubicon"

def rows_of(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def col(row, *names):
    keys = list(row.keys())
    # exact (case-insensitive, trimmed) first, then substring
    for n in names:
        for k in keys:
            if k and k.strip().lower() == n:
                return (row[k] or "").strip()
    for n in names:
        for k in keys:
            if k and n in k.strip().lower():
                return (row[k] or "").strip()
    return ""

def is_rubicon(row):
    return col(row, "company name").lower().startswith(CUSTOMER)

def build_candidates(path):
    out, contact, advisor = [], "", ""
    for r in rows_of(path):
        if not is_rubicon(r):
            continue
        name = col(r, "candidates name", "candidate name")
        if not name:
            continue
        contact = contact or col(r, "customers name", "customer name")
        advisor = advisor or col(r, "talent advisor", "taent advisor", "advisor")
        out.append({
            "batch": col(r, "batch #", "batch"),
            "role": col(r, "title/role", "title", "role"),
            "name": name,
            "email": col(r, "candidates email", "candidate email", "email"),
            "location": col(r, "candidates location", "location"),
            "salary": col(r, "salary expectations", "salary").replace("$", "").strip(),
            "status": col(r, "status"),
            "resume": col(r, "resume link", "resume"),
            "video": col(r, "video link", "video"),
            "notes": col(r, "notes"),
        })
    return out, contact, advisor

def build_requests(path):
    by_key, order = {}, []
    for r in rows_of(path):
        if not is_rubicon(r):
            continue
        role = col(r, "role")
        hr = col(r, "hiring request")
        if not role and not hr:
            continue
        key = hr if (hr and hr != "N/A") else role.lower()
        note = col(r, "notes")
        if key in by_key:
            if note and note not in by_key[key]["notes"]:
                by_key[key]["notes"] += (" · " if by_key[key]["notes"] else "") + note
            continue
        by_key[key] = {
            "hr": hr,
            "role": role,
            "status": col(r, "status"),
            "advisor": col(r, "advisor", "talent advisor"),
            "kickoff": col(r, "alignment date/ kickoff meeting", "alignment date / kickoff meeting", "kickoff meeting", "kickoff"),
            "datePlaced": col(r, "date placed"),
            "notes": note,
        }
        order.append(key)
    return [by_key[k] for k in order]

def main():
    cand_path, trk_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    rows, contact, advisor = build_candidates(cand_path)
    requests = build_requests(trk_path)
    payload = {"customer": "Rubicon", "contact": contact, "advisor": advisor or "Vicky",
               "requests": requests, "rows": rows}

    # Skip rewrite if nothing but the timestamp would change → no noisy commits.
    try:
        old = json.load(open(out_path, encoding="utf-8"))
        if {k: old.get(k) for k in payload} == payload:
            print("no data change; leaving file untouched")
            return
    except Exception:
        pass

    data = {"updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"), **payload}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"wrote {out_path}: {len(rows)} candidates, {len(requests)} requisitions")

if __name__ == "__main__":
    main()
