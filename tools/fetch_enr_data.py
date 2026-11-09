#!/usr/bin/env python3
"""Fetch fresh ENR data (stations / whole-day timetable / ticket search).

Examples:
  python3 fetch_enr_data.py stations --out stations.json
  python3 fetch_enr_data.py timetable --date 2026-12-01 --out timetable_dec.json
  python3 fetch_enr_data.py search --from-name CAIRO --to-name ASWAN --date 2026-12-01 --out search.json

Requires only `requests` (pip install requests). No authentication needed.
"""
import argparse, csv, json, sys, time
from datetime import datetime

try:
    import requests
except ImportError:
    sys.exit("pip install requests first")

BASE = "https://obs.enr.gov.eg"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) EgyptTrainsData/1.0", "Accept": "application/json"}


def get(path, params=None, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(BASE + path, params=params or {}, headers=HEADERS, timeout=90)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == retries - 1:
                raise
            print(f"  retry {attempt + 1}: {e}", file=sys.stderr)
            time.sleep(3)


def cmd_stations(args):
    data = get("/api/v1/serviceTripPoints/stations",
               {"page": 0, "page_size": 10000, "locale": "en"})
    json.dump(data, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    phys = [s for s in data if s.get("type") == 0]
    print(f"{len(data)} records ({len(phys)} physical stations) -> {args.out}")
    csv_out = args.out[:-5] + ".csv" if args.out.endswith(".json") else args.out + ".csv"
    with open(csv_out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["id", "name_en", "name_ar", "type", "active", "station_code", "short_name"])
        for s in data:
            lm = s.get("localizationMap") or {}
            w.writerow([s["id"], s.get("name", ""), lm.get("ar", ""), s.get("type"),
                        s.get("active"), (s.get("params") or {}).get("station_code", ""),
                        s.get("shortName", "")])
    print(f"csv -> {csv_out}")


def cmd_timetable(args):
    data = get("/api/v1/trainWorkOrders/timeTable", {"from": args.date, "to": args.date})
    json.dump({"date": args.date, "n_trains": len(data), "trains": data},
              open(args.out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{len(data)} trains on {args.date} -> {args.out}")
    print("NOTE: entries contain cumulative t/st/dist per stop; see README for semantics.")


_STATIONS_CACHE = []


def _all_stations():
    if not _STATIONS_CACHE:
        _STATIONS_CACHE.extend(
            get("/api/v1/serviceTripPoints/stations",
                {"page": 0, "page_size": 10000, "locale": "en"}))
    return _STATIONS_CACHE


def _resolve_station(name):
    pool = [s for s in _all_stations() if s.get("type") == 0] or _all_stations()
    want = name.strip().lower()
    exact = [s for s in pool if s.get("name", "").lower() == want]
    subs = [s for s in pool if want in s.get("name", "").lower()] if not exact else []
    arabic = [s for s in pool
              if want in ((s.get("localizationMap") or {}).get("ar") or "")] \
        if not (exact or subs) else []
    cands = exact or subs or arabic
    if not cands:
        sys.exit(f"no station matching '{name}' ({len(pool)} known)")
    best = cands[0]
    if len(cands) > 1:
        print(f"  note: {len(cands)} matches for '{name}', using the first", file=sys.stderr)
    lm = best.get("localizationMap") or {}
    print(f"  '{name}' -> {best['id']} ({best.get('name')} / {lm.get('ar', '')})")
    return best["id"]


def cmd_search(args):
    fid = _resolve_station(args.from_name)
    tid = _resolve_station(args.to_name)
    data = get("/api/v1/tickets/search",
               {"from": fid, "to": tid, "departureDate": args.date,
                "fareKind": "one_way", "skip_places_information": "true"})
    json.dump(data, open(args.out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{len(data)} journeys -> {args.out}")
    for j in data[:5]:
        st = j["steps"][0]
        tr = st.get("train") or {}
        print(f"  train {tr.get('name')}: {st['fromDate'][11:16]} -> {st['finishDate'][11:16]}"
              f"  seats={st.get('availableSeats')}  from {j.get('startingPrice', '?')} {j.get('currency', 'EGP')}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("stations"); ps.add_argument("--out", default="stations_enr.json")
    ps.set_defaults(fn=cmd_stations)

    pt = sub.add_parser("timetable"); pt.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    pt.add_argument("--out", default="timetable.json"); pt.set_defaults(fn=cmd_timetable)

    pq = sub.add_parser("search")
    pq.add_argument("--from-name", required=True); pq.add_argument("--to-name", required=True)
    pq.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    pq.add_argument("--out", default="search.json"); pq.set_defaults(fn=cmd_search)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
