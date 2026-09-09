#!/usr/bin/env python3
"""
Fill in missing phone numbers from each company's own website.

Scope, deliberately narrow: it only visits companies that are ALREADY in the
list and that published a website address, and it only reads the main business
phone number those companies put on their own page for customers to call. It
does not crawl, does not follow links beyond a known contact page, does not
collect email addresses, and does not touch anything about individual people.

It checks robots.txt before each site and skips any that disallows it.

    python3 find_phones.py data/florida-marine-businesses.csv

Rewrites the CSV in place, adding a "Phone source" column so it is always clear
which numbers came from the original dataset and which were looked up.
"""
import csv
import re
import sys
import time
import urllib.parse
import urllib.robotparser

import requests

UA = ('Mozilla/5.0 (compatible; business-directory-builder/1.0; '
      'contact via freelancer.com)')
CONTACT_PATHS = ['', '/contact', '/contact-us', '/contact.html', '/about/contact']

# tel: links are unambiguous, so they are tried first and trusted most.
TEL_RE = re.compile(r'href=["\']tel:([+0-9().\-\s]{7,})["\']', re.I)
TEXT_RE = re.compile(
    r'(?<![\d-])(?:\+?1[\s.\-]?)?\(?([2-9]\d{2})\)?[\s.\-]?([2-9]\d{2})[\s.\-]?(\d{4})(?![\d-])')

# Numbers that appear on marine sites but are not the business: the Coast Guard,
# emergency services, and the toll-free ranges used by manufacturers.
BLOCK_PREFIX = {'911', '988', '800', '833', '844', '855', '866', '877', '888'}

# Every area code Florida actually uses. A "starts with 2-9" check is far too
# loose for the text fallback: the first pass through these pages produced
# (749), (200) and (399), none of which are assignable, plus one number that
# turned up for two unrelated marinas — all of them digit runs that merely
# looked like phone numbers. A Florida marine business answers a Florida line,
# so that is what we require.
FL_AREA = {'239', '305', '321', '352', '386', '407', '448', '561', '656',
           '689', '727', '754', '772', '786', '813', '850', '863', '904',
           '941', '954'}


def dialable(d):
    if len(d) != 10:
        return False
    if d[0] in '01' or d[3] in '01':
        return False
    if d[3:6] == '555' and d[6] == '0':
        return False
    if len(set(d)) == 1:
        return False
    return True


def digits(raw):
    d = re.sub(r'\D', '', raw)
    if len(d) == 11 and d[0] == '1':
        d = d[1:]
    return d


def fmt(d):
    return f'({d[0:3]}) {d[3:6]}-{d[6:]}'


def allowed(session, base):
    """Honour robots.txt. If we cannot read it, assume not allowed."""
    rp = urllib.robotparser.RobotFileParser()
    try:
        r = session.get(urllib.parse.urljoin(base, '/robots.txt'), timeout=10)
        if r.status_code >= 400:
            return True          # no robots file published = no restriction
        rp.parse(r.text.splitlines())
        return rp.can_fetch(UA, base)
    except requests.RequestException:
        return False


def phone_from(html):
    """The company's own Florida phone number, or None.

    Taking the first tel: link on the page is not good enough. Rickenbacker
    Marina's contact page carries both `tel:+1 212 425 8617` and
    `tel:+1 305 361 1900`; the New York one appears first in the markup, so
    first-match handed back a number in the wrong state for a Miami marina.
    Every candidate is collected and a Florida area code is required — for a
    directory of Florida businesses, an out-of-state number is much more likely
    to be a web vendor, a parent company or a mis-parse than the line a customer
    should ring. Blank beats wrong on a call sheet.
    """
    candidates = [digits(m.group(1)) for m in TEL_RE.finditer(html)]
    # Plain text is guesswork — nothing says these digits are a phone number at
    # all — so it is only consulted after the marked-up links, and only near the
    # top of the page, where a business puts its own number.
    candidates += [''.join(m.groups()) for m in TEXT_RE.finditer(html[:60000])]
    for d in candidates:
        if dialable(d) and d[:3] in FL_AREA and d[:3] not in BLOCK_PREFIX:
            return d
    return None


def look_up(session, website):
    if not website.startswith(('http://', 'https://')):
        website = 'https://' + website
    base = f'{urllib.parse.urlsplit(website).scheme}://{urllib.parse.urlsplit(website).netloc}'
    if not allowed(session, base):
        return None, 'robots.txt'
    for path in CONTACT_PATHS:
        url = urllib.parse.urljoin(base, path) if path else website
        try:
            r = session.get(url, timeout=15)
        except requests.RequestException:
            continue
        if r.status_code != 200 or 'html' not in r.headers.get('Content-Type', ''):
            continue
        d = phone_from(r.text)
        if d:
            return fmt(d), url
        time.sleep(0.6)
    return None, 'not found'


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'data/florida-marine-businesses.csv'
    rows = list(csv.DictReader(open(path, encoding='utf-8')))
    cols = list(rows[0].keys())
    if 'Phone source' not in cols:
        cols.insert(cols.index('Phone') + 1, 'Phone source')

    todo = [r for r in rows if r.get('Website') and not r.get('Phone')]
    print(f'{len(rows)} companies, {len(todo)} have a website but no phone number\n')

    session = requests.Session()
    session.headers['User-Agent'] = UA
    found = skipped = 0

    for i, r in enumerate(todo, 1):
        phone, where = look_up(session, r['Website'])
        if phone:
            r['Phone'] = phone
            r['Phone source'] = 'company website'
            found += 1
            print(f'[{i:3}/{len(todo)}] {r["Company"][:38]:38} {phone}')
        else:
            if where == 'robots.txt':
                skipped += 1
            print(f'[{i:3}/{len(todo)}] {r["Company"][:38]:38} — ({where})')
        time.sleep(1.0)  # one site per second, no faster

    # If the same number came back for two different companies, it is not
    # either company's line — it is a shared template, a web designer's footer,
    # or a digit run that was never a phone number. Throw both away.
    from collections import Counter
    tally = Counter(r['Phone'] for r in todo if r.get('Phone source') == 'company website')
    shared = {p for p, n in tally.items() if n > 1}
    for r in todo:
        if r.get('Phone source') == 'company website' and r['Phone'] in shared:
            print(f'  dropped {r["Phone"]} — found on {tally[r["Phone"]]} different companies')
            r['Phone'], r['Phone source'] = '', ''
            found -= 1

    for r in rows:
        r.setdefault('Phone source', '')
        if r.get('Phone') and not r['Phone source']:
            r['Phone source'] = 'OpenStreetMap'

    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    total = sum(1 for r in rows if r['Phone'])
    print(f'\nfound {found} new numbers, {skipped} sites declined by robots.txt')
    print(f'phone coverage now {total}/{len(rows)}')


if __name__ == '__main__':
    main()
