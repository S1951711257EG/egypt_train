#!/usr/bin/env python3
"""Add lat/lon to ENR stations by matching names against OpenStreetMap (Overpass API).

Run this on a machine with normal internet access (the Overpass API was unreachable
from the extraction sandbox, but works from ordinary networks).

  python3 geocode_stations_from_osm.py \
      --stations ../stations_enr.csv --out stations_with_coords.csv

Strategy:
  1. Download all railway=station / halt / tram_stop nodes inside Egypt from Overpass.
  2. Normalise names on both sides (case, punctuation, common ENR prefixes/suffixes
     like EL-/AL-, stations named after towns).
  3. Exact normalised match first, then difflib fuzzy match (cut-off 0.62).
  4. Arabic names are used as a second key (OSM often has name:ar).
  5. Unmatched stations keep empty coords — you can fill those few by hand.
"""
import argparse, csv, json, re, unicodedata, urllib.request, urllib.parse, difflib

OVERPASS = "https://overpass-api.de/api/interpreter"   # try mirrors if slow:
MIRRORS = ["https://overpass.private.coffee/api/interpreter",
           "https://overpass.kumi.systems/api/interpreter"]

QUERY = """
[out:json][timeout:300];
(
  node["railway"~"^(station|halt)$"](21.8,24.6,31.8,34.5);
);
out body;
"""


def fetch_osm():
    last = None
    for url in [OVERPASS] + MIRRORS:
        try:
            data = urllib.parse.urlencode({"data": QUERY}).encode()
            req = urllib.request.Request(url, data=data,
                                         headers={"User-Agent": "EgyptTrainsGeocode/1.0"})
            with urllib.request.urlopen(req, timeout=360) as r:
                return json.load(r)
        except Exception as e:
            last = e
            print(f"mirror failed: {url} ({e})")
    raise SystemExit(f"all Overpass mirrors failed: {last}")


def norm(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"\b( el | al | el-|al-)", " ", " " + s + " ")
    s = re.sub(r"[^a-z\u0600-\u06ff ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stations", default="../stations_enr.csv")
    ap.add_argument("--out", default="stations_with_coords.csv")
    args = ap.parse_args()

    print("fetching OSM stations...")
    osm = fetch_osm()
    els = osm.get("elements", [])
    print(f"OSM returned {len(els)} nodes")

    by_en, by_ar = {}, {}
    for e in els:
        t = e.get("tags", {})
        for key, idx in (("name", by_en), ("name:en", by_en)):
            n = norm(t.get(key, ""))
            if n:
                by_en.setdefault(n, []).append(e)
        n_ar = norm(t.get("name:ar", ""))
        if n_ar:
            by_ar.setdefault(n_ar, []).append(e)
    osm_keys = list(by_en.keys())

    rows = list(csv.DictReader(open(args.stations, encoding="utf-8-sig")))
    out, matched = [], 0
    for r in rows:
        if r.get("type") != "0":
            out.append({**r, "lat": "", "lon": "", "match": ""})
            continue
        en, ar = norm(r.get("name_en", "")), norm(r.get("name_ar", ""))
        cand = by_en.get(en) or by_ar.get(ar)
        how = "exact"
        if not cand:
            close = difflib.get_close_matches(en, osm_keys, n=1, cutoff=0.62) if en else []
            if close:
                cand, how = by_en[close[0]], f"fuzzy:{close[0]}"
        if cand:
            best = cand[0]
            out.append({**r, "lat": best["lat"], "lon": best["lon"],
                        "match": f"{how} osm{best['id']}"})
            matched += 1
        else:
            out.append({**r, "lat": "", "lon": "", "match": "unmatched"})
    with open(args.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader(); w.writerows(out)
    print(f"matched {matched}/{sum(1 for r in rows if r.get('type') == '0')} physical stations -> {args.out}")


if __name__ == "__main__":
    main()
