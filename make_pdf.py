#!/usr/bin/env python3
"""
Turn the marine-business CSV into a printable PDF directory.

    python3 make_pdf.py data/florida-marine-businesses.csv

Works with either CSV layout — the OpenStreetMap one (has an Email column) or
the Google Places one (has County/Rating instead). It picks columns based on
what the file actually contains.
"""
import csv
import os
import sys
from collections import defaultdict

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (BaseDocTemplate, Frame, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

NAVY = colors.HexColor('#11314F')
SLATE = colors.HexColor('#4A5A6A')
RULE = colors.HexColor('#C9D3DC')
BAND = colors.HexColor('#F2F5F8')

argv = [a for a in sys.argv[1:] if a != '--calls-only']
calls_only = '--calls-only' in sys.argv

src = argv[0] if argv else 'data/florida-marine-businesses.csv'
out = argv[1] if len(argv) > 1 else os.path.splitext(src)[0] + '.pdf'

rows = list(csv.DictReader(open(src, encoding='utf-8')))
if not rows:
    raise SystemExit(f'{src} has no rows')

total_in = len(rows)
if calls_only:
    # A call sheet with nothing to call is worse than no row at all.
    rows = [r for r in rows if r.get('Phone')]
    if not rows:
        raise SystemExit(f'{src} has no rows with a phone number')
have = set(rows[0].keys())

# The two builders emit different columns, and the provenance note on page one
# has to match whichever one produced this file — printing "compiled from
# OpenStreetMap" on top of Google data would be a lie on a document that gets
# passed on to someone else.
SOURCE = 'places' if 'Rating' in have or 'County' in have else 'osm'

# Column plan: (heading, csv field, width in inches)
plan = [('Company', 'Company', 2.35)]
if 'Phone' in have:
    plan.append(('Phone', 'Phone', 1.02))
if 'Email' in have:
    plan.append(('Email', 'Email', 1.85))
if 'Website' in have:
    plan.append(('Website', 'Website', 2.15))
if 'Address' in have:
    plan.append(('Address', 'Address', 2.55))
if 'County' in have:
    plan.append(('County', 'County', 0.95))
elif 'City' in have:
    plan.append(('City', 'City', 1.15))

styles = getSampleStyleSheet()
cell = ParagraphStyle('cell', parent=styles['BodyText'], fontName='Helvetica',
                      fontSize=7.4, leading=9.2, textColor=colors.HexColor('#1B2733'),
                      spaceBefore=0, spaceAfter=0)
cell_b = ParagraphStyle('cellb', parent=cell, fontName='Helvetica-Bold')
head = ParagraphStyle('head', parent=cell, fontName='Helvetica-Bold', fontSize=7.6,
                      textColor=colors.white)
h1 = ParagraphStyle('h1', parent=styles['Title'], fontName='Helvetica-Bold',
                    fontSize=19, leading=23, textColor=NAVY, alignment=0, spaceAfter=2)
sub = ParagraphStyle('sub', parent=styles['BodyText'], fontName='Helvetica',
                     fontSize=9.5, leading=13, textColor=SLATE)
sect = ParagraphStyle('sect', parent=styles['BodyText'], fontName='Helvetica-Bold',
                      fontSize=11.5, leading=14, textColor=NAVY,
                      spaceBefore=13, spaceAfter=5)
note = ParagraphStyle('note', parent=styles['BodyText'], fontName='Helvetica',
                      fontSize=8.2, leading=11, textColor=SLATE)


def shorten_url(u, n=42):
    u = u.replace('https://', '').replace('http://', '').rstrip('/')
    if u.startswith('www.'):
        u = u[4:]
    return u if len(u) <= n else u[:n - 1] + '…'


def para(text, field, bold=False):
    if not text:
        return Paragraph('<font color="#9AA7B4">—</font>', cell)
    if field == 'Website':
        text = shorten_url(text)
    return Paragraph(text.replace('&', '&amp;').replace('<', '&lt;'),
                     cell_b if bold else cell)


PAGE = landscape(letter)
LM = RM = 0.42 * inch
TM = 0.52 * inch
BM = 0.6 * inch


def decorate(canvas, doc):
    canvas.saveState()
    w, h = PAGE
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.6)
    canvas.line(LM, BM - 9, w - RM, BM - 9)
    canvas.setFont('Helvetica', 7.4)
    canvas.setFillColor(SLATE)
    canvas.drawString(LM, BM - 20, 'Florida Marine Businesses')
    canvas.drawRightString(w - RM, BM - 20, f'Page {doc.page}')
    canvas.restoreState()


# The per-column widths above are a wish list; which columns exist depends on
# the source file. Left unchecked the OpenStreetMap layout overflows the page
# and silently clips the last column mid-word ("Port Charlott"), so scale the
# whole set to fit whatever width is actually available.
AVAIL = PAGE[0] - LM - RM
_want = sum(w for _, _, w in plan) * inch
_scale = min(1.0, AVAIL / _want)
COL_W = [w * inch * _scale for _, _, w in plan]

doc = BaseDocTemplate(out, pagesize=PAGE, leftMargin=LM, rightMargin=RM,
                      topMargin=TM, bottomMargin=BM,
                      title='Florida Marine Businesses',
                      author='Anirudha Talmale')
frame = Frame(LM, BM, PAGE[0] - LM - RM, PAGE[1] - TM - BM, id='f',
              leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
doc.addPageTemplates([PageTemplate(id='all', frames=[frame], onPage=decorate)])

story = []
n_phone = sum(1 for r in rows if r.get('Phone'))
n_email = sum(1 for r in rows if r.get('Email'))
n_site = sum(1 for r in rows if r.get('Website'))

story.append(Paragraph(
    'Florida Marine Businesses &mdash; Call Sheet' if calls_only
    else 'Florida Marine Businesses', h1))
story.append(Paragraph(
    f'{len(rows)} companies &nbsp;·&nbsp; {n_phone} with a phone number'
    + (f' &nbsp;·&nbsp; {n_email} with an email' if 'Email' in have else '')
    + f' &nbsp;·&nbsp; {n_site} with a website', sub))
story.append(Spacer(1, 7))
n_contact = sum(1 for r in rows if r.get('Phone') or r.get('Email') or r.get('Website'))
if calls_only:
    story.append(Paragraph(
        f'<b>Every company on this sheet has a phone number.</b> These are the '
        f'{len(rows)} of {total_in} entries in the source list that publish one. '
        f'The other {total_in - len(rows)} are omitted here on purpose &mdash; '
        'they are in the full directory, but there is nothing on them to dial. '
        'Numbers have been checked against the North American dialling rules, so '
        'nothing on this page is a placeholder or a malformed entry.', note))
else:
    if SOURCE == 'places':
        story.append(Paragraph(
            '<b>About this list.</b> Built from the Google Places API, which is '
            'licensed business data rather than anything scraped off a website. '
            f'{n_contact} of the {len(rows)} entries carry a phone number or a '
            'website. There is no email column because the Places API has no '
            'email field &mdash; the website is the route to a contact address. '
            'A dash means the detail is not published, not that it does not '
            'exist.', note))
    else:
        story.append(Paragraph(
            '<b>About this list.</b> Compiled from OpenStreetMap, an open '
            'licensed business dataset. It covers the whole state, but it is '
            'not a complete register of every marine business in Florida '
            '&mdash; it contains what has been mapped, which is strong on '
            'locations and thin on contact details. '
            f'<b>{n_contact} of the {len(rows)} entries carry a phone, email or '
            f'website; the remaining {len(rows) - n_contact} are a name and a '
            'location only</b> and are listed after the contactable ones in each '
            'section. Phone numbers have been checked against the North American '
            'dialling rules; anything that could not be a working number has been '
            'left blank rather than printed. A dash means the detail is not '
            'published in this source, not that it does not exist.', note))
story.append(Spacer(1, 4))

groups = defaultdict(list)
for r in rows:
    groups[r.get('Category', 'Other')].append(r)

order = ['Boat sales', 'Boat builder', 'Repair / service', 'Marina / docks', 'Rental']
cats = [c for c in order if c in groups] + sorted(c for c in groups if c not in order)

for cat in cats:
    # Contactable first, as the note on page 1 promises, then alphabetical.
    items = sorted(groups[cat], key=lambda r: (
        not (r.get('Phone') or r.get('Email') or r.get('Website')),
        r['Company'].lower()))
    story.append(Paragraph(f'{cat} &nbsp;<font size="9" color="#7C8B9A">'
                           f'({len(items)})</font>', sect))
    data = [[Paragraph(h, head) for h, _, _ in plan]]
    for r in items:
        data.append([para(r.get(f, ''), f, bold=(f == 'Company')) for _, f, _ in plan])
    t = Table(data, colWidths=COL_W, repeatRows=1, hAlign='LEFT')
    style = [
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3.2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.2),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('LINEBELOW', (0, 1), (-1, -1), 0.35, RULE),
    ]
    for i in range(2, len(data), 2):
        style.append(('BACKGROUND', (0, i), (-1, i), BAND))
    t.setStyle(TableStyle(style))
    story.append(t)

doc.build(story)
print(f'{out}  ({len(rows)} companies, {len(cats)} sections)')
