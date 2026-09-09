# Florida marine business list

Two ways to build a list of Florida boat sales companies, marinas and marine
service businesses — company name, address, phone, website.

Both use licensed data sources with a proper API. Neither scrapes anyone's
website, and neither collects individual employees' names or direct numbers.

---

## 1. The starter list — already built, nothing to run

`data/florida-marine-businesses.xlsx`

213 companies pulled from OpenStreetMap: 49 boat sales / builders and 159
marinas and dock operators. Every row has a name, most have an address and a
map link.

**Be aware of the catch:** OpenStreetMap is excellent at *where things are* and
poor at *how to phone them*, at least in the US. Only 39 of the 213 have a phone
number and only 9 have an email. It is a good map of who exists and where; it is
not a finished call list.

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

---

## Rebuilding the OpenStreetMap starter list

Only needed if you want to refresh it. `osm/` holds the query and the build
script.

```sh
cd osm
sh fetch_osm.sh          # queries the public Overpass API
python3 build_osm.py     # writes the spreadsheet
```

The public Overpass servers are frequently busy and return 504s; the script
tries three different mirrors before giving up. Just run it again if it fails.

---

## What this deliberately does not do

No email harvesting off company websites, and no individual employees — no
service managers by name, no direct extensions. Business contact details are
fair game; compiling named people and their numbers into a marketing list is a
different thing, and it is not something I build.

For the service manager, calling the main number and asking for them by role
gets you a warmer contact than a scraped name would anyway.
