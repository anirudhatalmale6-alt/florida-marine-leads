#!/usr/bin/env python3
"""Turn the Overpass result into a spreadsheet Jet can actually work from."""
import json, re, sys
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

CATEGORY = {
    ('shop', 'boat'): 'Boat sales',
    ('shop', 'yachts'): 'Yacht sales',
    ('shop', 'watercraft'): 'Watercraft sales',
    ('shop', 'boat_parts'): 'Parts & chandlery',
    ('shop', 'boat_repair'): 'Repair / service',
    ('craft', 'boatbuilder'): 'Boat builder',
    ('leisure', 'marina'): 'Marina / docks',
}

def category(tags):
    for (k, v), label in CATEGORY.items():
        if tags.get(k) == v:
            return label
    return 'Other marine'

def dialable(d):
    """d is 10 digits. Reject anything that cannot be a real US number.

    OSM is crowd-sourced and does contain placeholders — this dataset had
    'Allwater Marine +1-941-555-0198' in it, which is the 555-01XX range
    reserved for fiction. A number that rings nowhere is worse than a blank
    cell in a call list, so these get dropped rather than passed on.
    """
    if len(d) != 10:
        return False
    if d[0] in '01' or d[3] in '01':          # NANP: area/exchange start 2-9
        return False
    if d[3:6] == '555' and d[6] == '0':       # 555-0100..555-0199, fictional
        return False
    if len(set(d)) == 1:                      # 0000000000 and friends
        return False
    return True


def phone(tags):
    for k in ('phone', 'contact:phone', 'phone:mobile', 'contact:mobile'):
        if tags.get(k):
            raw = tags[k].split(';')[0].strip()
            d = re.sub(r'\D', '', raw)
            if len(d) == 11 and d[0] == '1':
                d = d[1:]
            if not dialable(d):
                continue
            return f'({d[0:3]}) {d[3:6]}-{d[6:]}'
    return ''

def first(tags, *keys):
    for k in keys:
        if tags.get(k):
            return tags[k].split(';')[0].strip()
    return ''

def address(t):
    parts = [' '.join(x for x in (t.get('addr:housenumber'), t.get('addr:street')) if x)]
    parts += [t.get('addr:city', ''), t.get('addr:state', ''), t.get('addr:postcode', '')]
    return ', '.join(p for p in parts if p).replace(', FL,', ', FL')

data = json.load(open(sys.argv[1] if len(sys.argv) > 1 else 'fl.json'))
rows = []
for el in data['elements']:
    t = el.get('tags', {})
    name = t.get('name') or t.get('operator') or ''
    if not name:
        continue  # an unnamed dock is no use as a lead
    lat = el.get('lat') or (el.get('center') or {}).get('lat')
    lon = el.get('lon') or (el.get('center') or {}).get('lon')
    rows.append({
        'Company': name,
        'Category': category(t),
        'Phone': phone(t),
        'Email': first(t, 'email', 'contact:email'),
        'Website': first(t, 'website', 'contact:website', 'url'),
        'Address': address(t),
        'City': t.get('addr:city', ''),
        'Map': f'https://www.google.com/maps/search/?api=1&query={lat},{lon}' if lat and lon else '',
        'OSM': f"https://www.openstreetmap.org/{el['type']}/{el['id']}",
    })

# Same company mapped as both a node and an area is common; collapse on name+city.
seen, uniq = {}, []
for r in rows:
    key = (r['Company'].lower().strip(), r['City'].lower().strip())
    if key in seen:
        keep = seen[key]
        for f in ('Phone', 'Email', 'Website', 'Address'):
            if not keep[f] and r[f]:
                keep[f] = r[f]
        continue
    seen[key] = r
    uniq.append(r)

# Anything with a phone or an email first, then alphabetical.
uniq.sort(key=lambda r: (not (r['Phone'] or r['Email']), r['Category'], r['Company'].lower()))

cols = ['Company', 'Category', 'Phone', 'Email', 'Website', 'Address', 'City', 'Map', 'OSM']
wb = Workbook()
ws = wb.active
ws.title = 'FL Marine Businesses'
ws.append(cols)
head = Font(bold=True, color='FFFFFF')
fill = PatternFill('solid', fgColor='11314F')
for c in ws[1]:
    c.font, c.fill, c.alignment = head, fill, Alignment(vertical='center')
ws.freeze_panes = 'A2'
for r in uniq:
    ws.append([r[c] for c in cols])
widths = {'Company': 42, 'Category': 18, 'Phone': 16, 'Email': 32, 'Website': 40, 'Address': 46, 'City': 20, 'Map': 30, 'OSM': 30}
for i, c in enumerate(cols, 1):
    ws.column_dimensions[get_column_letter(i)].width = widths[c]
ws.auto_filter.ref = f'A1:{get_column_letter(len(cols))}{len(uniq)+1}'
wb.save('florida-marine-businesses.xlsx')

with open('florida-marine-businesses.csv', 'w', encoding='utf-8') as f:
    import csv
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(uniq)

from collections import Counter
print(f'{len(uniq)} companies')
print(f"  with phone   : {sum(1 for r in uniq if r['Phone'])}")
print(f"  with email   : {sum(1 for r in uniq if r['Email'])}")
print(f"  with website : {sum(1 for r in uniq if r['Website'])}")
for cat, n in Counter(r['Category'] for r in uniq).most_common():
    ph = sum(1 for r in uniq if r['Category'] == cat and r['Phone'])
    print(f'  {cat:22} {n:5}   ({ph} with phone)')
