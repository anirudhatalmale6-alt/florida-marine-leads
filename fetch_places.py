#!/usr/bin/env python3
"""
Build a Florida marine-business list from the Google Places API.

Licensed data straight from Google, not scraped off anyone's website. It walks
every Florida county, runs a handful of search terms in each, and writes what it
finds to a spreadsheet.

    pip install requests openpyxl
    export GOOGLE_MAPS_API_KEY=AIza...
    python3 fetch_places.py

Options:
    --counties "Broward,Miami-Dade"   only these counties (default: all 67)
    --terms    "boat dealer,marina"   only these search terms
    --out      leads                  output basename
    --dry-run                         print the plan and cost estimate, call nothing
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from collections import Counter

import requests
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ENDPOINT = 'https://places.googleapis.com/v1/places:searchText'

# Only what we actually put in the sheet. The field mask is what Google bills
# on, so asking for less genuinely costs less.
FIELD_MASK = ','.join([
    'places.id',
    'places.displayName',
    'places.formattedAddress',
    'places.nationalPhoneNumber',
    'places.websiteUri',
    'places.primaryTypeDisplayName',
    'places.types',
    'places.rating',
    'places.userRatingCount',
    'places.businessStatus',
    'places.googleMapsUri',
    'nextPageToken',
])

TERMS = [
    'boat dealer',
    'boat sales',
    'yacht sales',
    'marine dealer',
    'boat repair',
    'marina',
]

COUNTIES = [
    'Alachua', 'Baker', 'Bay', 'Bradford', 'Brevard', 'Broward', 'Calhoun',
    'Charlotte', 'Citrus', 'Clay', 'Collier', 'Columbia', 'DeSoto', 'Dixie',
    'Duval', 'Escambia', 'Flagler', 'Franklin', 'Gadsden', 'Gilchrist',
    'Glades', 'Gulf', 'Hamilton', 'Hardee', 'Hendry', 'Hernando', 'Highlands',
    'Hillsborough', 'Holmes', 'Indian River', 'Jackson', 'Jefferson',
    'Lafayette', 'Lake', 'Lee', 'Leon', 'Levy', 'Liberty', 'Madison',
    'Manatee', 'Marion', 'Martin', 'Miami-Dade', 'Monroe', 'Nassau',
    'Okaloosa', 'Okeechobee', 'Orange', 'Osceola', 'Palm Beach', 'Pasco',
    'Pinellas', 'Polk', 'Putnam', 'St. Johns', 'St. Lucie', 'Santa Rosa',
    'Sarasota', 'Seminole', 'Sumter', 'Suwannee', 'Taylor', 'Union',
    'Volusia', 'Wakulla', 'Walton', 'Washington',
]

# Places tags a lot of loosely-related things when you search "boat". Keep the
# ones that are actually marine businesses.
KEEP_TYPES = {
    'boat_dealer', 'boat_repair_shop', 'marina', 'boat_rental_service',
    'boat_ramp', 'store', 'car_dealer', 'point_of_interest', 'establishment',
}
DROP_NAME = re.compile(
    r'\b(storage|self storage|u-haul|apartment|condo|hotel|motel|resort|'
    r'restaurant|bar & grill|park|boat ramp|county park|state park)\b',
    re.I,
)


def category(place):
    types = set(place.get('types') or [])
    if 'boat_dealer' in types:
        return 'Boat sales'
    if 'boat_repair_shop' in types:
        return 'Repair / service'
    if 'marina' in types:
        return 'Marina / docks'
    if 'boat_rental_service' in types:
        return 'Rental'
    return place.get('primaryTypeDisplayName', {}).get('text', 'Other marine')


def search(session, key, query, budget):
    """One text search, following pagination. Returns a list of places."""
    out, token, page = [], None, 0
    while page < 3:  # Google caps text search at 3 pages / 60 results
        body = {'textQuery': query, 'pageSize': 20}
        if token:
            body['pageToken'] = token
        for attempt in range(4):
            r = session.post(
                ENDPOINT,
                headers={
                    'Content-Type': 'application/json',
                    'X-Goog-Api-Key': key,
                    'X-Goog-FieldMask': FIELD_MASK,
                },
                json=body,
                timeout=30,
            )
            budget['requests'] += 1
            if r.status_code == 200:
                break
            if r.status_code in (429, 500, 502, 503):
                time.sleep(2 ** attempt)
                continue
            # 400/403 means the key or the request is wrong — say so loudly
            # rather than quietly returning an empty list.
            raise SystemExit(
                f'\nPlaces API returned {r.status_code} for "{query}":\n'
                f'{r.text[:500]}\n\n'
                'A 403 usually means the Places API (New) is not enabled on the '
                'project, or the key is restricted. See the README.'
            )
        else:
            print(f'   ! gave up on "{query}" after repeated errors', file=sys.stderr)
            return out

        data = r.json()
        out.extend(data.get('places', []))
        token = data.get('nextPageToken')
        page += 1
        if not token:
            break
        time.sleep(1.5)  # the page token needs a moment before it is valid
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--counties', default='')
    ap.add_argument('--terms', default='')
    ap.add_argument('--out', default='florida-marine-businesses')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    counties = [c.strip() for c in args.counties.split(',') if c.strip()] or COUNTIES
    terms = [t.strip() for t in args.terms.split(',') if t.strip()] or TERMS

    planned = len(counties) * len(terms)
    print(f'{len(counties)} counties x {len(terms)} terms = {planned} searches')
    print(f'up to ~{planned * 3} API requests, roughly ${planned * 3 * 0.032:.2f} '
          f'at the Text Search Pro rate')
    print('Google gives $200 of free Maps usage a month, so this normally costs nothing.\n')
    if args.dry_run:
        print('Dry run — nothing called.')
        return

    key = os.environ.get('GOOGLE_MAPS_API_KEY')
    if not key:
        raise SystemExit('Set GOOGLE_MAPS_API_KEY first. See the README.')

    session = requests.Session()
    budget = {'requests': 0}
    found = {}  # place id -> row, so the same yard found by 3 terms lands once

    for i, county in enumerate(counties, 1):
        before = len(found)
        for term in terms:
            query = f'{term} in {county} County, Florida'
            for p in search(session, key, query, budget):
                pid = p.get('id')
                if not pid or pid in found:
                    continue
                name = p.get('displayName', {}).get('text', '')
                if not name or DROP_NAME.search(name):
                    continue
                if p.get('businessStatus') == 'CLOSED_PERMANENTLY':
                    continue
                found[pid] = {
                    'Company': name,
                    'Category': category(p),
                    'Phone': p.get('nationalPhoneNumber', ''),
                    'Website': p.get('websiteUri', ''),
                    'Address': p.get('formattedAddress', ''),
                    'County': county,
                    'Rating': p.get('rating', ''),
                    'Reviews': p.get('userRatingCount', ''),
                    'Status': p.get('businessStatus', ''),
                    'Map': p.get('googleMapsUri', ''),
                }
        print(f'[{i:2}/{len(counties)}] {county:14} +{len(found)-before:3}  '
              f'total {len(found)}')

    rows = sorted(found.values(), key=lambda r: (r['County'], r['Category'], r['Company'].lower()))
    if not rows:
        raise SystemExit('No results — check the API key and that Places API (New) is enabled.')

    cols = ['Company', 'Category', 'Phone', 'Website', 'Address', 'County',
            'Rating', 'Reviews', 'Status', 'Map']

    wb = Workbook()
    ws = wb.active
    ws.title = 'FL Marine Businesses'
    ws.append(cols)
    for c in ws[1]:
        c.font = Font(bold=True, color='FFFFFF')
        c.fill = PatternFill('solid', fgColor='11314F')
        c.alignment = Alignment(vertical='center')
    ws.freeze_panes = 'A2'
    for r in rows:
        ws.append([r[c] for c in cols])
    widths = {'Company': 42, 'Category': 18, 'Phone': 16, 'Website': 40,
              'Address': 50, 'County': 16, 'Rating': 8, 'Reviews': 9,
              'Status': 18, 'Map': 34}
    for i, c in enumerate(cols, 1):
        ws.column_dimensions[get_column_letter(i)].width = widths[c]
    ws.auto_filter.ref = f'A1:{get_column_letter(len(cols))}{len(rows)+1}'
    wb.save(f'{args.out}.xlsx')

    with open(f'{args.out}.csv', 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    print(f'\n{len(rows)} companies -> {args.out}.xlsx / {args.out}.csv')
    print(f'  with phone   : {sum(1 for r in rows if r["Phone"])}')
    print(f'  with website : {sum(1 for r in rows if r["Website"])}')
    print(f'  API requests : {budget["requests"]}')
    for cat, n in Counter(r['Category'] for r in rows).most_common():
        print(f'  {cat:22} {n}')


if __name__ == '__main__':
    main()
