# Egypt Trains — Complete Data Kit for Simulation

Everything you need to simulate the **Egyptian National Railways (ENR)** network: stations,
full-day timetable, track geometry, level crossings — plus the API reference to refresh it all.

Built from: the **Egypt Trains Android app v3.1.1** (`com.dynamo.egypt_trains`, the backup you
provided) and the **official ENR ticketing API** (`obs.enr.gov.eg`, no authentication required).

---

## 1. What's in this folder

| File | What it is | Rows / size |
|---|---|---|
| `stations_enr.csv` / `.json` | **All ENR stations** from the official API — ID, name (EN + AR), station code, type, flags (`used_in_obs`, `has_gates`…). `type=0` rows are the 903 physical stations; other types are windows/groups/agent points. | 4,017 records |
| `timetable_2026-11-11.csv` | **Full national timetable for one day** — flat table: train number, origin/terminus, every stop with km-from-origin, arrival/departure (minutes + clock time), dwell. | 798 trains, 14,694 stop events |
| `timetable_2026-11-11.json` | Same timetable, structured per train (incl. class info, days-of-week, coach count). | 798 trains |
| `rail_network.geojson` | **Track geometry** decoded from the app's `rail_lines.bin` — 1,790 LineStrings, 25,188 vertices, 8,320 km. | GeoJSON (WGS84) |
| `rail_lines.csv` | Raw vertex dump of the same file (`segment_id`, `point_seq`, lon, lat). | 25,188 points |
| `level_crossings_osm_way_ids.json` / `rail_road_risk.csv` | 6,805 **OpenStreetMap way IDs of rail-road level crossings** (the app's crossing-alert list). | 6,805 IDs |
| `rail_network_map.png` | Rendered map of the whole network. | — |
| `example_ticket_search_cairo_alexandria_2026-11-11.json` | Raw response of a live ticket search (35 journeys Cairo→Alexandria with fares, seat maps). | — |
| `enr_obs_openapi_spec.json` | The **complete OpenAPI spec** of the ENR API (1,451 endpoints). | — |
| `tools/fetch_enr_data.py` | Script to refresh stations / timetable / searches for any date. | — |
| `tools/geocode_stations_from_osm.py` | Adds lat/lon to stations by matching names against OpenStreetMap. | — |
| `docs/` | Full data-extraction report (APK reverse engineering + ENR API discovery, methodology & validation). | PDF + Word |

### Timetable time semantics (validated against the live API)
For each train: `dep_min = Σ(leg times t) + Σ(dwells st)` measured from `origin_time`;
`arr_min = dep_min − dwell` at that stop. `km` is cumulative metres from the origin.
Example (train 163, Aswan 12:30 → Alexandria): Cairo arrival = 930 min elapsed = 04:00 next day,
Alexandria = 1160 min = 07:50 — matches the live ticket search exactly.

---

## 2. Where each kind of data comes from

### A. Stations — official ENR API (free, no auth)
```
GET https://obs.enr.gov.eg/api/v1/serviceTripPoints/stations?page=0&page_size=10000&locale=en
```
Returns every station with its numeric/string **station ID** (needed for all trip queries),
English + Arabic names, and the legacy **station_code** (e.g. Cairo = 108, Alexandria = 5818).

### B. Schedules — three options
1. **Whole-network timetable for any date** (best for simulation):
   ```
   GET https://obs.enr.gov.eg/api/v1/trainWorkOrders/timeTable?from=2026-11-11&to=2026-11-11
   ```
   → every train that day: number, origin time, stop-by-stop cumulative distance/time/dwell,
   coaches, supported classes, day-of-week pattern (`days` param), repeat rules (e.g. `no_friday`).
2. **Ticket search between two stations** (what the app uses):
   ```
   GET https://obs.enr.gov.eg/api/v1/tickets/search?from=<stationId>&to=<stationId>&departureDate=YYYY-MM-DD
   ```
   → journeys with fares (EGP), available seats, per-coach seat maps, and the stop sequence.
   Optional: `fareKind=one_way`, `transfers=true`.
3. **Single-train whole route**: `/api/v1/tickets/trainInformationWholeRoute?from=<id>&trainName=<nr>&departureDate=<date>&request=<token>`
   (the `request` token comes from a prior search response — `ticketBuyRequestTemplate`).

### C. Track geometry / map data — inside the APK (already extracted here)
- `assets/flutter_assets/assets/rail_lines.bin` — custom `RAIL` format:
  `magic "RAIL" + version(u32) + count(u32) + count×point-count(u32) + float32 (lon,lat) pairs`.
  → decoded to `rail_network.geojson`.
- `assets/flutter_assets/assets/rail_road_risk.bin` — `count(u32) + sorted OSM way IDs (u32)`
  → level crossings.
- `assets/map/native/` — MapLibre style JSONs (EN/AR, light/dark) + sprite/font bundle.

### D. Station coordinates — OpenStreetMap (run the geocoder on your own machine)
The ENR API does **not** expose coordinates, and the app's own tile/station server
(`tiles.egypttrains.com`) is behind Cloudflare. Easiest path: Overpass API.
```
[out:json][timeout:300];
node["railway"="station"](21.8,24.6,31.8,34.5);
out body;
```
Then run `tools/geocode_stations_from_osm.py` to fuzzy-match OSM names to `stations_enr.csv`
(names mostly match: "CAIRO" ↔ "Cairo", "EL-MINIA" ↔ "Minya"; Arabic names included on both sides).

### E. Live train positions (the app's realtime features)
The app polls `https://egypttrains.com/api/train-live/...` and `wss://egypttrains.com/chat/api/train/...`,
plus `https://egypttrains.com/api/route?from=...` for journey planning. **These are Cloudflare-protected**
and expect the app's client — not usable from scripts without mimicking the app. For a simulation,
the ENR timetable (B1) is the authoritative schedule anyway; delay/realtime data is not public.

---

## 3. Quick start for your simulation

```python
import csv, json

# 1. stations
stations = list(csv.DictReader(open('stations_enr.csv', encoding='utf-8-sig')))
physical = [s for s in stations if s['type'] == '0']          # 903 real stations

# 2. timetable
tt = json.load(open('timetable_2026-11-11.json', encoding='utf-8'))
for train in tt['trains']:
    for stop in train['stops']:        # seq, station_id, name_en/ar, km,
        ...                            # arr_min, dep_min, arr_time, dep_time, dwell_min

# 3. network
geo = json.load(open('rail_network.geojson', encoding='utf-8'))
```

## 4. Refreshing data for another day / route

```bash
python3 tools/fetch_enr_data.py timetable --date 2026-12-01 --out timetable_dec.json
python3 tools/fetch_enr_data.py search --from-name CAIRO --to-name ASWAN --date 2026-12-01
python3 tools/fetch_enr_data.py stations --out stations.json
```

Notes
- Timetables differ by weekday (`days` / `repeat_kind` in each entry — e.g. `no_friday` trains
  skip Fridays); to build a generic week, pull `timeTable` for 7 consecutive dates and merge.
- The OpenAPI spec (`enr_obs_openapi_spec.json`) documents 1,451 endpoints (fares, quotas,
  work orders…) — most require staff auth, but the station/trip endpoints used here are open.
