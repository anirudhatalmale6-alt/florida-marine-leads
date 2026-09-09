#!/usr/bin/env python3
"""Turn the Overpass result into a spreadsheet Jet can actually work from."""
import json, re, sys
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

# Tags that say "this is a marine business" on their own.
CATEGORY = {
    ('shop', 'boat'): 'Boat sales',
    ('shop', 'yachts'): 'Boat sales',
    ('shop', 'watercraft'): 'Boat sales',
    ('shop', 'marine'): 'Boat sales',
    ('shop', 'outboard'): 'Boat sales',
    ('office', 'yacht_broker'): 'Boat sales',
    ('shop', 'boat_parts'): 'Parts & chandlery',
    ('shop', 'chandlery'): 'Parts & chandlery',
    ('shop', 'boat_repair'): 'Repair / service',
    ('craft', 'shipwright'): 'Repair / service',
    ('craft', 'boatbuilder'): 'Boat builder',
    ('industrial', 'shipyard'): 'Boat builder',
    ('industrial', 'boatyard'): 'Boat builder',
    ('man_made', 'shipyard'): 'Boat builder',
    ('leisure', 'marina'): 'Marina / docks',
    ('amenity', 'boat_rental'): 'Rental / storage',
    ('amenity', 'boat_storage'): 'Rental / storage',
}

# The query also sweeps anything with marine/boat/yacht/marina in its NAME that
# carries a shop, craft, office or industrial tag. That widens the net a long
# way, and it also drags in "Marina Gift Shop", "Boat House Convenience" and the
# county's Marine Patrol office. A name match only counts when the business
# category is generic enough that it could plausibly be a marine trader.
NAME_OK = {
    ('shop', 'yes'), ('shop', 'trade'), ('shop', 'hardware'),
    ('shop', 'car_repair'), ('shop', 'motorcycle'), ('shop', 'fishing'),
    ('shop', 'sports'), ('shop', 'rental'), ('shop', 'storage_rental'),
    ('office', 'yes'), ('office', 'company'), ('office', 'estate_agent'),
    ('craft', 'yes'), ('craft', 'metal_construction'), ('craft', 'painter'),
    ('craft', 'carpenter'), ('craft', 'electrician'), ('craft', 'sailmaker'),
    ('industrial', 'yes'), ('industrial', 'factory'), ('industrial', 'warehouse'),
}

MARINE_NAME = re.compile(r'(?i)\b(marine|marina|boat|boats|yacht|yachts|'
                         r'outboard|nautic\w*|marittim\w*|ship\w*)\b')


def category(tags):
    """Return a category, or None if this is not a marine business."""
    for (k, v), label in CATEGORY.items():
        if tags.get(k) == v:
            return label
    # No marine tag — this row is here purely because its name matched.
    name = tags.get('name') or ''
    if not MARINE_NAME.search(name):
        return None
    for k in ('shop', 'craft', 'office', 'industrial'):
        if tags.get(k) and (k, tags[k]) in NAME_OK:
            return 'Other marine'
    return None

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
    cat = category(t)
    if cat is None:
        continue  # matched the name sweep but is not a marine business
    lat = el.get('lat') or (el.get('center') or {}).get('lat')
    lon = el.get('lon') or (el.get('center') or {}).get('lon')
    rows.append({
        'Company': name,
        'Category': cat,
        'Phone': phone(t),
        'Email': first(t, 'email', 'contact:email'),
        'Website': first(t, 'website', 'contact:website', 'url'),
        'Address': address(t),
        'City': t.get('addr:city', ''),
        'Map': f'https://www.google.com/maps/search/?api=1&query={lat},{lon}' if lat and lon else '',
        'OSM': f"https://www.openstreetmap.org/{el['type']}/{el['id']}",
    })

# The same yard is routinely mapped twice — once as a node, once as the building
# outline — and the two copies rarely carry the same tags. Collapse them.
#
# Match on name, but only merge across a city difference when one side has no
# city at all. "MarineMax" with no city and "MarineMax" in Naples are the same
# record split in two; "MarineMax Fort Myers" and "MarineMax Naples" are two
# real branches and must both survive.
def norm(name):
    return re.sub(r'[^a-z0-9]+', ' ', name.lower()).strip()

buckets = {}
for r in rows:
    buckets.setdefault(norm(r['Company']), []).append(r)

uniq = []
for group in buckets.values():
    # Richest record first so it becomes the one we merge into.
    group.sort(key=lambda r: -sum(bool(r[f]) for f in ('Phone', 'Email', 'Website', 'Address', 'City')))
    kept = []
    for r in group:
        target = None
        for k in kept:
            if not r['City'] or not k['City'] or r['City'].lower() == k['City'].lower():
                target = k
                break
        if target is None:
            kept.append(r)
            continue
        for f in ('Phone', 'Email', 'Website', 'Address', 'City'):
            if not target[f] and r[f]:
                target[f] = r[f]
    uniq.extend(kept)

# Rows carrying a way to make contact come first — a name-only row is a lead to
# research, not a lead to call, and it should not sit at the top of the page.
def contactable(r):
    return bool(r['Phone'] or r['Email'] or r['Website'])

uniq.sort(key=lambda r: (r['Category'], not contactable(r), r['Company'].lower()))

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
