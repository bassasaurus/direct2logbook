import hashlib
import inspect
import platform
import sys
import botocore
import boto3
import os
from logbook.celery import app
from io import BytesIO
from reportlab.lib.pagesizes import legal, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    Paragraph,
    Table,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
    PageBreak,
    LongTable,
    Image as RLImage,
)
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader

from django.core.mail import EmailMessage
from django.contrib.auth.models import User
from django.core.files.storage import default_storage
from django.conf import settings
from django.contrib.staticfiles import finders

import datetime

from urllib.parse import urlparse, unquote

from .models import Signature
from flights.models import Flight, Total, Stat, Regs, Power, Weight, Endorsement

import logging
logger = logging.getLogger(__name__)


def _func_fingerprint(func):
    try:
        src = inspect.getsource(func)
    except Exception:
        src = repr(func)
    h = hashlib.sha256(src.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return h


def _celery_env_report():
    from django.conf import settings as dj
    try:
        boto_ver = boto3.__version__
        botocore_ver = botocore.__version__
    except Exception:
        boto_ver = botocore_ver = "?"
    try:
        from django.core.files.storage import default_storage as ds
        storage_cls = f"{ds.__class__.__module__}.{ds.__class__.__name__}"
    except Exception:
        storage_cls = "<unknown>"
    return {
        "py": sys.version.split()[0],
        "platform": platform.platform(),
        "cwd": os.getcwd(),
        "DJANGO_SETTINGS_MODULE": os.environ.get("DJANGO_SETTINGS_MODULE"),
        "AWS_BUCKET": getattr(dj, "AWS_STORAGE_BUCKET_NAME", None),
        "AWS_REGION": getattr(dj, "AWS_S3_REGION_NAME", None),
        "AWS_SIG": getattr(dj, "AWS_S3_SIGNATURE_VERSION", None),
        "DEBUG": getattr(dj, "DEBUG", None),
        "boto3": boto_ver,
        "botocore": botocore_ver,
        "storage": storage_cls,
    }


# --- helpers ---------------------------------------------------------------

def _entry(value, flight):
    """Render a cell value according to original logic."""
    if not value or value is False:
        return '-'
    if value is True:
        return str(flight.duration)
    return str(value)


def _image_reader_from_storage(name: str):
    """Return a ReportLab ImageReader from a storage key (S3/local).

    Uses default_storage so it works under django-storages S3 as well as local FS.
    """
    with default_storage.open(name, "rb") as fh:
        return ImageReader(BytesIO(fh.read()))


def _static_image_reader(static_path: str):
    """Try to load an image from staticfiles, else return None."""
    abs_path = finders.find(static_path)
    if not abs_path:
        return None
    try:
        return ImageReader(abs_path)
    except Exception:
        return None


def _derive_storage_key_from_signature(sig):
    """Derive storage key from Signature instance regardless of field type."""
    sig_name = getattr(sig.signature, 'name', None)
    if sig_name:
        return sig_name
    field = getattr(sig, 'signature', None)
    if isinstance(field, str) and field.startswith(('http://', 'https://')):
        parsed = urlparse(field)
        key = unquote(parsed.path.lstrip('/'))
        if key:
            return key
    return None


# --- main task -------------------------------------------------------------

@app.task
def pdf_generate(user_pk):
    # setup
    user = User.objects.get(pk=user_pk)

    logger.info("pdf_generate: START user=%s env=%s fp=%s",
                user_pk, _celery_env_report(), _func_fingerprint(pdf_generate))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(legal),
        leftMargin=0.25 * inch,
        rightMargin=0.25 * inch,
        topMargin=0.5 * inch,
        bottomMargin=1.25 * inch,
    )
    styles = getSampleStyleSheet()

    story = []

    try:
        if Signature.objects.filter(user=user).exists():
            sig = Signature.objects.get(user=user)
            raw = getattr(sig, 'signature', None)
            sig_key_dbg = _derive_storage_key_from_signature(sig)
            logger.info(
                "pdf_generate: signature raw=%r derived_key=%r", raw, sig_key_dbg)
    except Exception as e:
        logger.warning("pdf_generate: signature precheck failed: %s", e)

    # cover page starts here
    def title_page(canvas, doc_):
        canvas.saveState()

        # Draw header wings image if available from static
        wings = _static_image_reader('pdf_output/wings.png')
        if wings is not None:
            canvas.drawImage(wings, 103, 205, width=800,
                             height=229, mask='auto')

        canvas.setFont('Helvetica-Oblique', 7)
        canvas.drawString(
            800, 30, "Powered by Direct2Logbook.com and ReportLab")

        canvas.setFont('Helvetica', 10)
        page_number_text = f"{doc_.page}"
        canvas.drawCentredString(14 * inch / 2, 30, page_number_text)
        canvas.restoreState()

    def add_later_page_number(canvas, doc_):
        canvas.saveState()

        canvas.setFont('Helvetica-Oblique', 7)
        canvas.drawString(
            800, 30, "Powered by Direct2Logbook.com and ReportLab")

        # Draw signature from storage if exists (use storage name, not URL)
        try:
            logger.debug("PDF sig: checking signature for user=%s", user.pk)
            if Signature.objects.filter(user=user).exists():
                sig = Signature.objects.get(user=user)
                logger.debug("PDF sig: raw field repr=%r",
                             getattr(sig, 'signature', None))
                sig_key = _derive_storage_key_from_signature(sig)
                logger.debug("PDF sig: derived storage key=%r", sig_key)
                if sig_key:
                    reader = _image_reader_from_storage(sig_key)
                    canvas.drawImage(reader, 240, 50, width=100,
                                     height=40, mask='auto')
        except Exception as e:
            logger.warning("PDF sig: failed to embed signature: %s", e)
            # Non-fatal if signature cannot be loaded
            pass

        canvas.setFont('Helvetica', 10)
        canvas.drawString(
            30, 50, "I certify that the entries in this logbook are true.")

        canvas.setStrokeColorRGB(0, 0, 0)
        canvas.setLineWidth(0.5)
        canvas.line(240, 50, 480, 50)

        canvas.setFont('Helvetica', 10)
        page_number_text = f"{doc_.page}"
        canvas.drawCentredString(14 * inch / 2, 30, page_number_text)
        canvas.restoreState()

    spacer15 = Spacer(1, 1.5 * inch)
    spacer025 = Spacer(1, 0.25 * inch)

    story.append(spacer15)
    story.append(spacer025)
    text = f"<para size=50 align=center>Logbook for {user.first_name} {user.last_name}</para>"
    title = Paragraph(text, style=styles["Normal"])
    story.append(title)
    story.append(spacer15)
    story.append(spacer15)

    text = f"<para size=15 align=center>Data current as of {datetime.date.today().strftime('%m/%d/%Y')}</para>"
    story.append(Paragraph(text, style=styles["Normal"]))
    story.append(PageBreak())

    # summary page starts here
    spacer = Spacer(1, 0.25 * inch)
    text = "<para size=15 align=left><u><b>Category and Class Summary</b></u></para>"
    story.append(Paragraph(text, style=styles["Normal"]))
    story.append(spacer)

    # total table
    total_objects = Total.objects.filter(user=user)
    totals_that_exist = [str(t.total)
                         for t in total_objects if t.total_time > 0.0]

    total_data = []
    for total in totals_that_exist:
        t = Total.objects.filter(user=user).get(total=total)
        row = [
            str(t.total), str(t.total_time), str(t.pilot_in_command), str(
                t.second_in_command), str(t.cross_country),
            str(t.instructor), str(t.dual), str(t.solo), str(
                t.instrument), str(t.night), str(t.simulated_instrument),
            str(t.simulator), str(t.landings_day), str(
                t.landings_night), str(t.landings_day + t.landings_night),
            str(t.last_flown.strftime("%m/%d/%Y")
                ), str(t.last_30), str(t.last_60), str(t.last_90), str(t.last_180),
            str(t.last_yr), str(t.last_2yr), str(t.ytd),
        ]
        total_data.append(row)

    total_header = [
        "Cat/Class", "Time", "PIC", "SIC", "XC", "CFI", "Dual", "Solo",
        "IFR", "Night", "Hood", "Sim", "D Ldg", "N Ldg", "Total Ldg",
        "Last Flown", "30", "60", "90", "6mo", "1yr", "2yr", "Ytd",
    ]

    total_data.insert(0, total_header)
    total_table = Table(total_data, hAlign='LEFT')
    total_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 10),
        ('LINEBELOW', (0, 0), (-1, 0), 1.0, colors.black),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('LINEBELOW', (0, 0), (-1, -1), .25, colors.black),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
    ]))

    story.append(total_table)
    story.append(spacer)

    # role_table
    role_objects = Power.objects.filter(user=user)
    role_data = [[str(r.role), str(r.turbine), str(r.piston)]
                 for r in role_objects]
    role_header = ["Role", "Turbine", "Piston"]
    role_data.insert(0, role_header)
    role_table = Table(role_data, hAlign="LEFT")
    role_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 10),
        ('LINEBELOW', (0, 0), (-1, 0), 1.0, colors.black),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('LINEBELOW', (0, 0), (-1, -1), .25, colors.black),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
    ]))

    # regs_table
    regs_objects = Regs.objects.filter(user=user)
    regs_data = [[str(r.reg_type), str(r.pilot_in_command),
                  str(r.second_in_command)] for r in regs_objects]
    regs_header = ["FAR", "PIC", "SIC"]
    regs_data.insert(0, regs_header)
    regs_table = Table(regs_data, hAlign='LEFT')
    regs_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 10),
        ('LINEBELOW', (0, 0), (-1, 0), 1.0, colors.black),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('LINEBELOW', (0, 0), (-1, -1), .25, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
    ]))

    # weight_table
    weight_objects = Weight.objects.filter(user=user)
    weights_that_exist = [w for w in weight_objects if w.total > 0.0]
    weight_data = [[str(w.weight), str(w.total)] for w in weights_that_exist]
    weight_header = ['Weight', 'Total']
    weight_data.insert(0, weight_header)
    weight_table = Table(weight_data, hAlign='LEFT')
    weight_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 10),
        ('LINEBELOW', (0, 0), (-1, 0), 1.0, colors.black),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('LINEBELOW', (0, 0), (-1, -1), .25, colors.black),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
    ]))

    # endorsement_table
    endorsement_objects = Endorsement.objects.filter(user=user)
    endorsements_that_exist = [e for e in endorsement_objects if e.total > 0.0]
    endorsement_data = [[str(e.endorsement), str(e.total)]
                        for e in endorsements_that_exist]
    endorsement_header = ['Endorsement', 'Total']
    endorsement_data.insert(0, endorsement_header)
    endorsement_table = Table(endorsement_data, hAlign='LEFT')
    endorsement_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 10),
        ('LINEBELOW', (0, 0), (-1, 0), 1.0, colors.black),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('LINEBELOW', (0, 0), (-1, -1), .25, colors.black),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
    ]))

    # misc_table
    story.append(Paragraph(
        "<para size=15 align=left><u><b>Misc Summary</b></u></para>", style=styles["Normal"]))
    story.append(spacer)
    misc_data = [[role_table, regs_table, weight_table, endorsement_table]]
    story.append(Table(misc_data, hAlign="LEFT"))
    story.append(spacer)

    # aircraft stats table
    story.append(Paragraph(
        "<para size=15 align=left><u><b>Aircraft Summary</b></u></para>", style=styles["Normal"]))
    story.append(spacer)

    stat_objects = Stat.objects.filter(user=user)
    stat_data = []
    for s in stat_objects:
        # Skip rows if any required date fields are None
        if None in [s.last_flown, s.last_30, s.last_60, s.last_90, s.last_180, s.last_yr, s.last_2yr, s.ytd]:
            continue
        row = [
            str(s.aircraft_type), str(s.total_time), str(s.pilot_in_command), str(
                s.second_in_command), str(s.cross_country),
            str(s.instructor), str(s.dual), str(s.solo), str(
                s.instrument), str(s.night), str(s.simulated_instrument),
            str(s.simulator), str(s.landings_day), str(s.landings_night),
            str(s.last_flown.strftime("%m/%d/%Y")
                ), str(s.last_30), str(s.last_60), str(s.last_90), str(s.last_180),
            str(s.last_yr), str(s.last_2yr), str(s.ytd),
        ]
        stat_data.append(row)

    stat_header = [
        "Type", "Time", "PIC", "SIC", "XC", "CFI", "Dual", "Solo",
        "IFR", "Night", "Hood", "Sim", "D Ldg", "N Ldg",
        "Last Flown", "30", "60", "90", "6mo", "1yr", "2yr", "Ytd",
    ]
    stat_data.insert(0, stat_header)

    stat_table = Table(stat_data, repeatRows=1, hAlign='LEFT')
    stat_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 10),
        ('LINEBELOW', (0, 0), (-1, 0), 1.0, colors.black),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('LINEBELOW', (0, 0), (-1, -1), .25, colors.black),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
    ]))

    story.append(stat_table)
    story.append(spacer)

    # logbook section (page-level subtotals)
    # ---------------------------------------------------------------------
    # Start the logbook on a new page so we can accurately size per-page chunks.
    story.append(PageBreak())

    logbook_header = [
        'Date', 'Type', 'Reg', 'Route', 'Block', 'PIC', 'SIC', 'XC', 'Night',
        'IFR', 'Appr', 'Hold', 'D Ldg', 'N Ldg', 'Hood', 'CFI', 'Dual', 'Solo', 'Sim'
    ]

    # if settings.DEBUG:
    #     flight_objects = Flight.objects.filter(
    #         user=user).order_by('-date')[:100]
    # else:
    flight_objects = Flight.objects.filter(user=user).order_by('-date')

    # Build raw rows
    logbook_rows = []
    for f in flight_objects:
        date_str = f.date.strftime("%m/%d/%Y")
        appr = ''
        for approach in f.approach_set.all():
            appr += f"{approach.approach_type}-{approach.number} "
        hold = 'Yes' if any(h.hold for h in f.holding_set.all()) else '-'
        row = [
            date_str, str(f.aircraft_type), str(
                f.registration), str(f.route), str(f.duration),
            _entry(f.pilot_in_command, f), _entry(
                f.second_in_command, f), _entry(f.cross_country, f),
            _entry(f.night, f), _entry(f.instrument, f), appr, hold,
            _entry(f.landings_day, f), _entry(
                f.landings_night, f), _entry(f.simulated_instrument, f),
            _entry(f.instructor, f), _entry(f.dual, f), _entry(
                f.solo, f), _entry(f.simulator, f),
        ]
        logbook_rows.append(row)

    # Build a prototype LongTable to get column widths and perform splitting
    all_data = [logbook_header] + logbook_rows
    proto_table = LongTable(all_data, repeatRows=1, hAlign='LEFT')
    proto_style = TableStyle([
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 10),
        ('LINEBELOW', (0, 0), (-1, 0), 1.0, colors.black),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('LINEBELOW', (0, 0), (-1, -1), .25, colors.black),
        ('ALIGN', (4, 0), (-1, -1), 'RIGHT'),
    ])
    proto_table.setStyle(proto_style)

    # Wrap once to compute column widths
    # (use a minimal fake canvas via doc.width/height)
    proto_table.wrapOn(None, doc.width, doc.height)
    col_widths = getattr(proto_table, '_colWidths', None)

    # Numeric columns (0-based indices) for logbook
    numeric_cols = [4, 5, 6, 7, 8, 9, 12, 13, 14, 15, 16, 17, 18]

    def _make_footer_row(values):
        """Build a one-row Table for the page footer, styled appropriately."""
        tbl = Table([values], colWidths=col_widths, hAlign='LEFT')
        style = TableStyle([
            ('FONT', (0, 0), (0, 0), 'Helvetica-Bold', 10),
            ('FONT', (1, 0), (-1, 0), 'Helvetica', 10),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ])
        # Right-align numeric columns
        for c in numeric_cols:
            style.add('ALIGN', (c, 0), (c, 0), 'RIGHT')
        style.add('LINEBELOW', (0, 0), (-1, 0), 1.0, colors.black)
        tbl.setStyle(style)
        return tbl

    # Measure first-page header + spacer so we can subtract their height
    header_para = Paragraph(
        "<para size=15 align=left><u><b>Logbook</b></u></para>", style=styles["Normal"])
    _, header_h = header_para.wrap(doc.width, doc.height)
    first_spacer_h = 0.25 * inch
    safety_margin = 6  # points to account for stroke widths/rounding
    # Available space on first page and other pages
    avail_first = max(36, doc.height - header_h -
                      first_spacer_h - safety_margin)
    avail_other = doc.height

    # Refactored: First pass, split into page_chunks, compute page_rows and page_sums for each page
    page_chunks = []
    rows_consumed = 0
    page_index = 0
    remaining_table = LongTable(
        all_data, repeatRows=1, hAlign='LEFT', colWidths=col_widths)
    remaining_table.setStyle(proto_style)
    # Precompute a blank footer row height for space reservation
    _, footer_h = _make_footer_row(
        [''] * len(logbook_header)).wrap(doc.width, doc.height)

    while True:
        page_index += 1
        avail = avail_first if page_index == 1 else avail_other
        # Reserve space for footer rows: last page = 1 row, others = 2 rows (but we don't know last page yet)
        # For first pass, always reserve 2 rows except possibly last page
        # We'll handle this correctly in second pass
        # For now, always reserve 2 rows except for first page (if only one page, okay)
        # To be safe, always reserve 2 rows except for the last page (which we only know when split_parts has length 1)
        # Try with 2 rows reserved, then adjust for last page
        is_first_page = (page_index == 1)
        # For first pass, always reserve 2*footer_h except possibly last page
        avail_for_split = avail - 2 * footer_h
        chunk_height = max(36, avail_for_split - safety_margin)
        attempt = 0
        while True:
            split_parts = remaining_table.split(doc.width, chunk_height)
            if not split_parts:
                break
            this_page_table = split_parts[0]
            _, h_tbl = this_page_table.wrap(doc.width, avail_for_split)
            if h_tbl + safety_margin <= avail_for_split:
                break
            attempt += 1
            overflow = (h_tbl + safety_margin) - avail_for_split
            chunk_height = max(36, chunk_height - overflow - 4)
            if attempt > 5:
                break
        if not split_parts:
            break
        this_page_table = split_parts[0]
        this_rows = len(getattr(this_page_table, '_cellvalues', [])) - 1
        page_rows = logbook_rows[rows_consumed:rows_consumed + this_rows]
        # Compute page sums for numeric columns
        page_sums = {col: 0.0 for col in numeric_cols}
        for row in page_rows:
            for col in numeric_cols:
                val = row[col] if col < len(row) else ''
                if col in (12, 13):
                    try:
                        n = int(val) if val not in ('-', '', None) else 0
                    except Exception:
                        n = 0
                    page_sums[col] += n
                else:
                    try:
                        n = float(val) if val not in ('-', '', None) else 0.0
                    except Exception:
                        n = 0.0
                    page_sums[col] += n
        page_chunks.append((this_page_table, page_rows, page_sums))
        rows_consumed += this_rows
        if len(split_parts) == 1:
            break
        else:
            remaining_table = split_parts[1]

    # Second pass: render each page, append footers, reserve correct space
    num_pages = len(page_chunks)
    for i, (this_page_table, page_rows, page_sums) in enumerate(page_chunks, start=1):
        is_first = (i == 1)
        is_last = (i == num_pages)
        # Reserve correct space for footers
        # On last page: 1 row, others: 2 rows
        # (Handled by split above, so here we just render)
        if is_first:
            story.append(header_para)
            story.append(Spacer(1, first_spacer_h))
        story.append(this_page_table)
        # Build Current Page footer
        values = [''] * len(logbook_header)
        values[0] = 'Current Page'
        for col in numeric_cols:
            s = page_sums[col]
            if col in (12, 13):
                values[col] = str(int(round(s)))
            else:
                values[col] = f"{s:.1f}"
        story.append(_make_footer_row(values))
        # If not last page, also build Previous Page footer using next page's sums
        if not is_last:
            # i is 1-based, so i==current, i+1==next; page_chunks is 0-based
            next_page_sums = page_chunks[i][2]
            prev_values = [''] * len(logbook_header)
            prev_values[0] = 'Previous Page'
            for col in numeric_cols:
                s = next_page_sums[col]
                if col in (12, 13):
                    prev_values[col] = str(int(round(s)))
                else:
                    prev_values[col] = f"{s:.1f}"
            story.append(_make_footer_row(prev_values))
        # PageBreak if not last page
        if not is_last:
            story.append(PageBreak())

    # build pdf
    doc.multiBuild(story, onFirstPage=title_page,
                   onLaterPages=add_later_page_number)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    # email the generated PDF (no need to persist unless you want to)
    subject = f"Logbook for {user.first_name} {user.last_name}"
    email = EmailMessage(
        subject,
        'Good luck on your interview!',
        'noreply@direct2logbook.com',
        [user.email],
        reply_to=['noreply@direct2logbook.com'],
        headers={'Message-ID': 'logbook'},
    )
    email.attach('Logbook.pdf', pdf_bytes, 'application/pdf')
    email.send()

    return None


@app.task
def celery_debug_probe(user_pk):
    # Light-weight probe to ensure the worker has the same env and can open the signature via storage
    info = _celery_env_report()
    details = {"env": info, "user": user_pk}
    try:
        user = User.objects.get(pk=user_pk)
        if Signature.objects.filter(user=user).exists():
            sig = Signature.objects.get(user=user)
            key = _derive_storage_key_from_signature(sig)
            details["sig_key"] = key
            if key:
                with default_storage.open(key, "rb") as fh:
                    chunk = fh.read(16)
                    details["sig_first_bytes_hex"] = chunk.hex()
    except Exception as e:
        details["error"] = str(e)
    logger.info("celery_debug_probe: %s", details)
    return details
