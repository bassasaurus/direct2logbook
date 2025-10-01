from decimal import ROUND_HALF_UP
import logging
from flights.models import Flight, Total, Stat, Regs, Power, Weight, Endorsement
from urllib.parse import urlparse, unquote
from decimal import Decimal
import datetime
from django.contrib.staticfiles import finders
from django.conf import settings
from django.core.files.storage import default_storage
from django.contrib.auth.models import User
from django.core.mail import EmailMessage
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import inch
from reportlab.lib import colors
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
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import legal, landscape
from io import BytesIO
from logbook.celery import app
import os
import boto3
import botocore
import sys
import platform
import inspect
import hashlib


def _to_decimal_safe(val):
    try:
        return Decimal(str(val))
    except Exception:
        return Decimal("0.0")


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


# --- Numeric formatting helper ---


def _dec_str(val):
    """Convert a numeric field to a clean string with one decimal place using Decimal."""
    if val in (None, '', '-'):
        return '-'
    try:
        d = Decimal(str(val)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        return str(d)
    except Exception:
        return str(val)


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

    # try:
    #     if Signature.objects.filter(user=user).exists():
    #         sig = Signature.objects.get(user=user)
    #         raw = getattr(sig, 'signature', None)
    #         sig_key_dbg = _derive_storage_key_from_signature(sig)
    #         logger.info(
    #             "pdf_generate: signature raw=%r derived_key=%r", raw, sig_key_dbg)
    # except Exception as e:
    #     logger.warning("pdf_generate: signature precheck failed: %s", e)

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
            800, 30, "Powered by Direct2Logbook.com")

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
    flight_objects = Flight.objects.filter(user=user).order_by('date')

    # Build raw rows with Decimals for numeric fields
    logbook_rows = []
    for f in flight_objects:
        date_str = f.date.strftime("%m/%d/%Y")
        appr = ''
        for approach in f.approach_set.all():
            appr += f"{approach.approach_type}-{approach.number} "
        hold = 'Yes' if any(h.hold for h in f.holding_set.all()) else '-'

        def dec_or_zero(val):
            # For numeric fields: if not null/empty, wrap in Decimal(str(val)), else Decimal("0.0")
            if val not in (None, '', '-'):
                try:
                    return Decimal(str(val))
                except Exception:
                    return Decimal("0.0")
            return Decimal("0.0")
        # Ensure PIC, SIC, XC, Night, IFR, CFI, Dual, Solo go through dec_or_zero
        row = [
            date_str,
            str(f.aircraft_type),
            str(f.registration),
            str(f.route),
            dec_or_zero(f.duration),           # Block
            dec_or_zero(f.duration) if getattr(f, "pilot_in_command", False) else Decimal(
                "0.0"),   # PIC time = duration if logged as PIC
            dec_or_zero(f.duration) if getattr(f, "second_in_command", False) else Decimal(
                "0.0"),  # SIC time = duration if logged as SIC
            dec_or_zero(f.duration) if getattr(f, "cross_country", False) else Decimal(
                "0.0"),  # XC time = duration if logged as XC
            dec_or_zero(f.night),              # Night
            dec_or_zero(f.instrument),         # IFR
            appr,
            hold,
            dec_or_zero(f.landings_day),
            dec_or_zero(f.landings_night),
            dec_or_zero(f.simulated_instrument),
            dec_or_zero(f.duration) if getattr(f, "instructor", False) else Decimal(
                "0.0"),  # CFI time = duration if logged as CFI
            dec_or_zero(f.duration) if getattr(f, "dual", False) else Decimal(
                "0.0"),        # Dual time = duration if logged as Dual
            dec_or_zero(f.duration) if getattr(f, "solo", False) else Decimal(
                "0.0"),  # Solo time = duration if logged as Solo
            dec_or_zero(f.simulator),
        ]
        logbook_rows.append(row)

    # Now, build display rows for logbook (convert Decimals to pretty strings)
    from decimal import ROUND_HALF_UP

    def display_cell(val, colidx):
        # Numeric columns: 4,5,6,7,8,9,12,13,14,15,16,17,18
        # Landings columns (12, 13) as integer, others as 1 decimal
        if colidx in [4, 5, 6, 7, 8, 9, 12, 13, 14, 15, 16, 17, 18]:
            if colidx in (12, 13):
                # Landings: int, show 0 if 0
                try:
                    return str(int(val)) if val is not None else '0'
                except Exception:
                    return '0'
            else:
                # Other numerics: 1 decimal place
                try:
                    return str(val.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
                except Exception:
                    return '0.0'
        else:
            # Non-numeric fields: leave as is
            return val

    logbook_display_rows = []
    for row in logbook_rows:
        disp_row = [display_cell(row[i], i) for i in range(len(row))]
        logbook_display_rows.append(disp_row)
    # Map each display row to its corresponding raw row index (since 1:1)
    display_row_map = list(range(len(logbook_rows)))

    # --- Fixed rows-per-page pagination ---
    # Define ROWS_PER_PAGE constant for logbook rows per page
    ROWS_PER_PAGE = 20

    # Build a prototype LongTable to get column widths
    all_data = [logbook_header] + logbook_display_rows
    proto_table = LongTable(all_data, repeatRows=1, hAlign='LEFT')
    proto_style = TableStyle([
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 10),
        ('LINEBELOW', (0, 0), (-1, 0), 1.0, colors.black),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('LINEBELOW', (0, 0), (-1, -1), .25, colors.black),
        ('ALIGN', (4, 0), (-1, -1), 'RIGHT'),
        # Add padding to numeric columns to prevent overlap for large numbers
        ('RIGHTPADDING', (4, 0), (-1, -1), 10),
        ('LEFTPADDING', (4, 0), (-1, -1), 8),
    ])
    proto_table.setStyle(proto_style)
    proto_table.wrapOn(None, doc.width, doc.height)
    col_widths = getattr(proto_table, '_colWidths', None)
    # Slightly increase widths for Block, PIC, SIC, and XC columns
    if col_widths:
        for idx in [4, 5, 6, 7]:  # Block, PIC, SIC, XC
            col_widths[idx] += 10

        # Ensure table fits within available width
        total_width = sum(col_widths)
        available_width = doc.width
        if total_width > available_width:
            scale = available_width / total_width
            col_widths = [w * scale for w in col_widths]

    numeric_cols = [4, 5, 6, 7, 8, 9, 12, 13, 14, 15, 16, 17, 18]

    header_para = Paragraph(
        "<para size=15 align=left><u><b>Logbook</b></u></para>", style=styles["Normal"])
    _, header_h = header_para.wrap(doc.width, doc.height)
    first_spacer_h = 0.25 * inch

    # Measure a sample footer table with 3 rows to reserve accurate footer space (for vertical spacing)
    sample_footer = Table(
        [['' for _ in logbook_header]] * 3,
        colWidths=col_widths, hAlign='LEFT'
    )
    _, reserved_footer_h = sample_footer.wrap(doc.width, doc.height)

    # Fixed pagination: chunk logbook_display_rows into ROWS_PER_PAGE slices
    page_chunks = []
    page_row_indices = []
    n_rows = len(logbook_display_rows)
    for page_start in range(0, n_rows, ROWS_PER_PAGE):
        page_end = min(page_start + ROWS_PER_PAGE, n_rows)
        rows_this_page = list(range(page_start, page_end))
        table_data = [logbook_header] + [logbook_display_rows[idx]
                                         for idx in rows_this_page]
        page_table = Table(table_data, colWidths=col_widths,
                           repeatRows=1, hAlign='LEFT')
        page_table.setStyle(proto_style)
        page_chunks.append(page_table)
        page_row_indices.append([display_row_map[idx]
                                for idx in rows_this_page])

    # Second pass: render each page, append only the logbook table for each page
    num_pages = len(page_chunks)
    # --- Initialize cumulative totals for running total ---
    cumulative_vals = {col: Decimal("0.0") for col in numeric_cols}
    for i, (this_page_table, row_indices) in enumerate(zip(page_chunks, page_row_indices), start=1):
        is_first = (i == 1)
        is_last = (i == num_pages)
        if is_first:
            story.append(header_para)
            story.append(Spacer(1, first_spacer_h))
        story.append(this_page_table)
        # --- Compute page totals (footer) for this page ---
        footer_vals = ['Current page'] + \
            ['' for _ in range(len(logbook_header)-1)]
        footer_decimals = {}
        for col in numeric_cols:
            col_sum = Decimal("0.0")
            for idx in row_indices:
                if idx < len(logbook_rows):
                    val = logbook_rows[idx][col]
                    if isinstance(val, Decimal):
                        col_sum += val
                    else:
                        try:
                            col_sum += Decimal(str(val))
                        except Exception:
                            pass
            footer_decimals[col] = col_sum
            if col in (12, 13):
                footer_vals[col] = str(int(col_sum))
            else:
                footer_vals[col] = str(col_sum.quantize(
                    Decimal("0.1"), rounding=ROUND_HALF_UP))

        # --- Prepare "Amount Forwarded" row using cumulative_vals before updating for this page ---
        forwarded_vals = dict(cumulative_vals)  # snapshot before updating
        forwarded_row = ['Amount Forwarded'] + \
            ['' for _ in range(len(logbook_header)-1)]
        for col in numeric_cols:
            if col in (12, 13):
                forwarded_row[col] = str(int(forwarded_vals[col]))
            else:
                forwarded_row[col] = str(forwarded_vals[col].quantize(
                    Decimal("0.1"), rounding=ROUND_HALF_UP))

        # --- Prepare Running Total row (always last in reserved footer space) ---
        # Update cumulative_vals with the current page's footer_decimals (use raw Decimals)
        for col in numeric_cols:
            cumulative_vals[col] += footer_decimals[col]
        running_row = ['Running Total'] + \
            ['' for _ in range(len(logbook_header)-1)]
        for col in numeric_cols:
            if col in (12, 13):
                running_row[col] = str(int(cumulative_vals[col]))
            else:
                running_row[col] = str(cumulative_vals[col].quantize(
                    Decimal("0.1"), rounding=ROUND_HALF_UP))

        # --- Combine all footer rows into a single Table ---
        footer_data = [footer_vals]
        if not is_first:
            footer_data.append(forwarded_row)
        footer_data.append(running_row)
        footer_table = Table(footer_data, colWidths=col_widths, hAlign='LEFT')
        footer_table.setStyle(proto_style)
        # Align numeric columns for all rows
        for row_idx_ in range(len(footer_data)):
            for col in numeric_cols:
                footer_table.setStyle(TableStyle([
                    ('ALIGN', (col, row_idx_), (col, row_idx_), 'RIGHT'),
                ]))
        # Set background for Page Total (row 0) and Running Total (last row)
        footer_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
            ('BACKGROUND', (0, len(footer_data)-1),
             (-1, len(footer_data)-1), colors.whitesmoke),
        ]))
        # Insert a fixed spacer to separate table and footer
        story.append(Spacer(1, 0.1 * inch))
        story.append(footer_table)
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
