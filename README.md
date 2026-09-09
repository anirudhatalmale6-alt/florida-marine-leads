# Florida marine business list

Two ways to build a list of Florida boat sales companies, marinas and marine
service businesses — company name, address, phone, website.

Built from licensed data sources with a proper API, plus one narrow step that
reads a company's own published phone number off its own contact page. Nothing
here collects email addresses in bulk, and nothing here collects individual
employees' names or direct numbers.

---

## 1. The starter list — already built, nothing to run

Each list comes as `.xlsx`, `.csv` and a printable `.pdf`, plus a
`-call-sheet.pdf` holding only the entries that have a phone number.

`data/florida-boat-dealers.*` — **boat sellers only**: 102 companies, 46 with a
phone. This is the one the client asked for; no marinas, rentals, tackle or dive
shops. Built with `python3 build_osm.py fl.json --sales-only`.

`data/florida-marine-businesses.*` — everything marine: 639 companies, 245 with
a phone. 91 boat sales, 11 builders, 303 marinas and dock operators, 122
rental/storage, 53 tackle, 39 dive shops, 4 clubs.

The query casts a wide net — the explicit marine tags, plus anything with
marine, boat, yacht, marina, outboard or nautic in its name that is tagged as a
shop, trade, office or industrial site. That last part is what takes it from
209 entries to 639: plenty of businesses are filed under a generic category and
are invisible to a tag-only search. Name matches are filtered so that the
county Marine Patrol office and "Marina Gift Shop" do not come along with them.

**Phone coverage: 245 of the 639**, of which 59 came from `find_phones.py`
reading the number a company publishes on its own site (see below).

**The ceiling on boat dealers is about 100, and it is not worth attacking
again.** Widening the sweep as far as it goes — sailing, watersports, dive,
tackle, clubs, riggers, sailmakers, every generic-tagged business whose name
mentions boats — moved the overall total from 519 to 639 but moved boat dealers
from 89 to 90. OpenStreetMap simply does not hold Florida's dealer network.
Industry listings suggest 300–400 dealer locations statewide, so a complete
list is 3–4x this. That needs the Places run.

It is also crowd-sourced, so the odd entry is junk — this pull contained one
business with `941-555-0198`, which is the number range reserved for use in
fiction. The build script now checks numbers against the US dialling rules and
blanks anything that cannot ring, rather than handing you a dead number to call.

That is what the second tool is for.

## 2. The Google Places tool — complete phone coverage

`fetch_places.py` walks all 67 Florida counties, runs six search terms in each
("boat dealer", "boat sales", "yacht sales", "marine dealer", "boat repair",
"marina"), de-duplicates, and writes a spreadsheet. Google has a phone number
for essentially every listed business, so this is the one that produces a list
you can actually work from.

It needs a Google Maps API key on your own account. Takes about ten minutes to
set up, one time.

### Getting the key

1. Go to <https://console.cloud.google.com/projectcreate> and create a project.
   Call it anything.
2. Enable billing on it: <https://console.cloud.google.com/billing> → *Link a
   billing account*. A card is required, but see the cost note below — this
   stays inside the free allowance.
3. Enable the API: <https://console.cloud.google.com/apis/library/places.googleapis.com>
   → **Enable**. Make sure it is the one called **Places API (New)**, not the
   older "Places API".
4. Create the key: <https://console.cloud.google.com/apis/credentials> →
   *Create credentials* → *API key*. Copy it.
5. Optional but sensible: click the key, and under *API restrictions* choose
   *Restrict key* → **Places API (New)**. That way the key cannot be used for
   anything else if it leaks.

### Running it

```sh
pip install requests openpyxl

export GOOGLE_MAPS_API_KEY=AIza...your key...
python3 fetch_places.py
```

Writes `florida-marine-businesses.xlsx` and `.csv` in the current folder.
The whole state takes roughly 15–25 minutes to run.

Useful flags:

```sh
# See the plan and the cost estimate without calling anything
python3 fetch_places.py --dry-run

# Just the counties you care about
python3 fetch_places.py --counties "Broward,Miami-Dade,Palm Beach,Monroe"

# Just boat sales, skip marinas and repair yards
python3 fetch_places.py --terms "boat dealer,boat sales,yacht sales"

# Name the output
python3 fetch_places.py --out southeast-florida
```

### What it costs

67 counties × 6 terms ≈ 400 searches, up to ~1,200 API requests. At Google's
Text Search rate that is about $38 of usage — but Google includes **$200 of free
Maps usage every month**, so a full run of the state normally bills you nothing.
Running it repeatedly in one month is what would eventually cost money.

`--dry-run` prints the estimate for whatever slice you have chosen before you
commit to it.

### Columns

Company · Category · Phone · Website · Address · County · Rating · Reviews ·
Status · Map link

Category is one of Boat sales, Repair / service, Marina / docks, Rental, or
whatever Google's own primary type says. `Status` flags anything Google has
marked as temporarily closed so you do not waste a call on it.

**No email column, and that is not a choice I made.** The Google Places API has
no email field — it returns phone, website, address and ratings, and that is
all. Nobody can pull emails out of it. The website column is the way in: the
contact form or the published `info@` address is one click from there.
Bulk email lists come from paid B2B providers (Data Axle, Apollo and similar),
not from Google.

---

## Rebuilding the OpenStreetMap starter list

Only needed if you want to refresh it. `osm/` holds the query and the build
script.

```sh
cd osm
sh fetch_osm.sh                        # queries the public Overpass API
python3 build_osm.py fl.json           # every marine business
python3 build_osm.py fl.json --sales-only   # boat sellers only
```

The public Overpass servers are frequently busy and return 504s. The full union
query fails on all of them, so `fetch_osm.sh` pulls one lighter query per
selector and caches each part — an interrupted run picks up where it stopped.
Just run it again if a part fails.

## Filling in missing phone numbers

```sh
python3 find_phones.py data/florida-marine-businesses.csv
```

For companies already in the list that published a website but no phone number,
this opens that company's own site and reads the number they put there for
customers to ring. It checks `robots.txt` first and skips any site that
disallows it, waits a second between sites, tries the home page and then the
usual contact paths, and stops at the first number it finds. It adds a
**Phone source** column so it is always visible which numbers came from
OpenStreetMap and which were looked up. On the full marine list it added 59
numbers across 116 candidate sites, with 12 declining via robots.txt.

It is deliberately fussy about what counts as a phone number, because the first
version was not and produced rubbish:

- The area code must be one Florida actually uses. A "first digit 2–9" check
  let through `(749)`, `(200)` and `(399)`, none of which are assignable.
- Taking the first `tel:` link on the page is not enough. Rickenbacker Marina's
  contact page carries both `tel:+1 212 425 8617` and `tel:+1 305 361 1900`,
  New York first — first-match gave a Miami marina a New York number. Every
  candidate on the page is collected and a Florida number is preferred.
- If the same number comes back for two different companies it belongs to
  neither, and both are dropped. That caught two shared template numbers.

Blank beats wrong on a call sheet.

## Making the PDF

```sh
python3 make_pdf.py data/florida-marine-businesses.csv data/florida-marine-businesses.pdf
```

Landscape directory grouped by category, contactable entries first in each
section, with the coverage caveat printed on page one so nobody downstream
mistakes it for a complete register. It adapts to whichever CSV you give it —
the OpenStreetMap one or the Google Places one.

---

## What this deliberately does not do

No bulk email harvesting, and no individual employees — no service managers by
name, no direct extensions. A company's own switchboard number, published on
its own site so that customers will call it, is business contact information
and fair game. Compiling named people and their direct numbers into a marketing
list is a different thing, and it is not something I build.

For the service manager, calling the main number and asking for them by role
gets you a warmer contact than a scraped name would anyway.
