#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Erzeugt eine fuer den Google Ads Editor importfaehige CSV aus dem Workflow-Output."""
import json, csv, re, sys

SRC = "/private/tmp/claude-501/-Users-dominiktheis-Claude-Pavodens/55d2d902-a189-4731-beb4-9601b31c52c6/tasks/w605dkawn.output"
OUT = "/Users/dominiktheis/Claude/Pavodens/pavodens-google-ads-import.csv"

with open(SRC, encoding="utf-8") as f:
    data = json.load(f)
res = data["result"]
ad_groups = res["adGroups"]

# ---- Kampagnen-Konfiguration -------------------------------------------------
CAMP = {
    "Pavodens | ZFA":          {"budget": "20.00", "status": "Enabled", "maxcpc": "1.50", "slug": "zfa"},
    "Pavodens | ZMP":          {"budget": "15.00", "status": "Enabled", "maxcpc": "1.50", "slug": "zmp"},
    "Pavodens | Zahntechniker":{"budget": "5.00",  "status": "Paused",  "maxcpc": "1.20", "slug": "zahntechniker"},
}
NETWORKS    = "Google search;Search partners"
BID         = "Manual CPC"
URL_BASE    = "https://pavodens.onepage.me/bewerbung"

def slug(s):
    s = s.lower()
    s = (s.replace("ä","ae").replace("ö","oe").replace("ü","ue").replace("ß","ss"))
    s = re.sub(r"[^a-z0-9]+","-", s).strip("-")
    return s

def final_url(camp, ag):
    return (f"{URL_BASE}?utm_source=google&utm_medium=cpc"
            f"&utm_campaign={CAMP[camp]['slug']}&utm_content={slug(ag)}")

# ---- Spalten -----------------------------------------------------------------
COLS = ["Campaign","Campaign Type","Campaign Status","Campaign Daily Budget","Networks",
        "Bid Strategy Type","Ad Group","Ad Group Status","Max CPC","Keyword","Criterion Type",
        "Final URL"] \
       + [f"Headline {i}" for i in range(1,16)] \
       + [f"Description {i}" for i in range(1,5)] \
       + ["Path 1","Path 2"]

def blank():
    return {c: "" for c in COLS}

rows = []

# Reihenfolge der Kampagnen
camp_order = ["Pavodens | ZFA","Pavodens | ZMP","Pavodens | Zahntechniker"]
# Negatives je Kampagne sammeln (dedupe, Reihenfolge erhalten)
camp_negs = {c: [] for c in camp_order}
for ag in ad_groups:
    c = ag["spec"]["campaign"]
    for n in ag["kw"]["negatives"]:
        n = n.strip().lower()
        if n and n not in camp_negs[c]:
            camp_negs[c].append(n)

stats = {"campaigns":0,"adgroups":0,"keywords":0,"negatives":0,"ads":0}

for camp in camp_order:
    cfg = CAMP[camp]
    # 1) Kampagnenzeile
    r = blank()
    r.update({"Campaign":camp,"Campaign Type":"Search","Campaign Status":cfg["status"],
              "Campaign Daily Budget":cfg["budget"],"Networks":NETWORKS,"Bid Strategy Type":BID})
    rows.append(r); stats["campaigns"] += 1

    # 2) Kampagnen-Negative (Ad Group leer, Criterion Type = Campaign negative)
    for n in camp_negs[camp]:
        r = blank()
        r.update({"Campaign":camp,"Keyword":n,"Criterion Type":"Campaign negative"})
        rows.append(r); stats["negatives"] += 1

    # 3) Anzeigengruppen dieser Kampagne
    for ag in [a for a in ad_groups if a["spec"]["campaign"] == camp]:
        agname = ag["spec"]["name"]
        # Ad-Group-Zeile
        r = blank()
        r.update({"Campaign":camp,"Ad Group":agname,"Ad Group Status":"Enabled","Max CPC":cfg["maxcpc"]})
        rows.append(r); stats["adgroups"] += 1

        # Keyword-Zeilen (dedupe text+matchtype)
        seen = set()
        for kw in ag["kw"]["keywords"]:
            key = (kw["text"].strip().lower(), kw["matchType"])
            if key in seen: continue
            seen.add(key)
            r = blank()
            r.update({"Campaign":camp,"Ad Group":agname,"Keyword":kw["text"].strip(),
                      "Criterion Type":kw["matchType"]})
            rows.append(r); stats["keywords"] += 1

        # RSA-Zeile
        rsa = ag["rsa"]
        r = blank()
        r.update({"Campaign":camp,"Ad Group":agname,"Final URL":final_url(camp,agname),
                  "Path 1":rsa.get("path1",""),"Path 2":rsa.get("path2","")})
        for i,h in enumerate(rsa["headlines"][:15], start=1):
            r[f"Headline {i}"] = h
        for i,d in enumerate(rsa["descriptions"][:4], start=1):
            r[f"Description {i}"] = d
        rows.append(r); stats["ads"] += 1

# ---- Schreiben (UTF-8 mit BOM, damit Editor/Excel Umlaute sauber liest) ------
with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=COLS, quoting=csv.QUOTE_MINIMAL)
    w.writeheader()
    w.writerows(rows)

# ---- Validierung der Zeichenlimits (Sicherheitsnetz) -------------------------
viol = []
for ag in ad_groups:
    for i,h in enumerate(ag["rsa"]["headlines"]):
        if len(h) > 30: viol.append(("H",ag["spec"]["name"],i,len(h),h))
    for i,d in enumerate(ag["rsa"]["descriptions"]):
        if len(d) > 90: viol.append(("D",ag["spec"]["name"],i,len(d),d))

print(f"CSV geschrieben: {OUT}")
print(f"Zeilen gesamt (ohne Header): {len(rows)}")
print("Statistik:", stats)
print(f"Zeichenlimit-Verstoesse: {len(viol)}")
for v in viol: print("  !", v)
