#!/bin/sh
# Pull Florida marine businesses from the public Overpass API into fl.json.
#
# The obvious approach — one big union query — fails. Every public mirror
# answers 504 on it, because the name-regex sweep across all of Florida is too
# heavy for a shared server. So each selector is fetched as its own lighter
# query into parts/, and the parts are merged at the end.
#
# Parts are cached. If a run dies halfway, or a mirror throws 429 at you, just
# run it again: whatever already succeeded is skipped.

cd "$(dirname "$0")" || exit 1
mkdir -p parts

MIRRORS='https://overpass-api.de/api/interpreter
https://overpass.private.coffee/api/interpreter
https://overpass.kumi.systems/api/interpreter'

# Businesses whose NAME says marine even when their category does not.
N='marine|boat|yacht|marina|outboard|nautic|sail|watersport|kayak|paddle|pontoon|catamaran|trawler|jet ski|jetski|waverunner|propeller|rigging|chandler|dockside|boatyard|shipyard'

run() {
  name=$1
  sel=$2
  if [ -s "parts/$name.json" ] && head -c 1 "parts/$name.json" | grep -q '{'; then
    echo "  $name — cached"
    return
  fi
  printf '[out:json][timeout:200];\narea["ISO3166-2"="US-FL"][admin_level=4]->.fl;\nnwr%s(area.fl);\nout center tags;\n' "$sel" > "parts/$name.ql"
  for ep in $MIRRORS; do
    code=$(curl -s -X POST -d "@parts/$name.ql" "$ep" -o "parts/$name.json" --max-time 220 -w '%{http_code}')
    if [ "$code" = "200" ] && head -c 1 "parts/$name.json" | grep -q '{'; then
      echo "  $name — ok, $(wc -c < "parts/$name.json") bytes"
      return
    fi
    echo "  $name — http=$code, next mirror"
    sleep 4
  done
  rm -f "parts/$name.json"   # never leave an error page looking like a cache hit
  echo "  $name — FAILED on every mirror; re-run to retry just this part"
}

echo "Fetching by selector (mirrors are busy at peak US hours; retries are normal)"
run t_shop    '["shop"~"^(boat|yachts|watercraft|boat_parts|boat_repair|marine|chandlery|outboard|sails|fishing|scuba_diving)$"]'
run t_craft   '["craft"~"^(boatbuilder|shipwright|sailmaker)$"]'
run t_leisure '["leisure"~"^(marina|sailing_club)$"]'
run t_club    '["club"~"^(yacht|sailing|boat)$"]'
run t_amenity '["amenity"~"^(boat_rental|boat_storage|boat_sharing|dive_centre)$"]'
run t_indus   '["industrial"~"^(shipyard|boatyard)$"]'
run t_manmade '["man_made"="shipyard"]'
run t_office  '["office"="yacht_broker"]'
run n_shop    "[\"shop\"][\"name\"~\"$N\",i]"
run n_craft   "[\"craft\"][\"name\"~\"$N\",i]"
run n_office  "[\"office\"][\"name\"~\"$N\",i]"
run n_indus   "[\"industrial\"][\"name\"~\"$N\",i]"
run n_tourism "[\"tourism\"][\"name\"~\"$N\",i]"
run n_amenity "[\"amenity\"][\"name\"~\"$N\",i]"

python3 - <<'PY'
import glob, json, sys

seen = {}
for fn in sorted(glob.glob('parts/*.json')):
    try:
        d = json.load(open(fn))
    except Exception as e:
        print(f'  skipping {fn}: {e}', file=sys.stderr)
        continue
    for el in d.get('elements', []):
        seen[(el['type'], el['id'])] = el

if not seen:
    raise SystemExit('No parts fetched. Every mirror was busy — try again shortly.')

json.dump({'elements': list(seen.values())}, open('fl.json', 'w'))
named = sum(1 for e in seen.values() if e.get('tags', {}).get('name'))
print(f'fl.json — {len(seen)} unique elements, {named} with a name')
PY
