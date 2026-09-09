#!/bin/sh
# Query the public Overpass API for Florida marine businesses.
# The public mirrors are often busy and answer 504; we try three.
cd "$(dirname "$0")"
for ep in https://overpass.private.coffee/api/interpreter \
          https://overpass-api.de/api/interpreter \
          https://overpass.kumi.systems/api/interpreter; do
  echo "trying $ep"
  code=$(curl -s -X POST -d @q.overpass "$ep" -o fl.json --max-time 300 -w "%{http_code}")
  if [ "$code" = "200" ]; then echo "got $(wc -c < fl.json) bytes from $ep"; exit 0; fi
  echo "  http=$code, next mirror"
done
echo "All Overpass mirrors were busy. Try again in a few minutes."
exit 1
