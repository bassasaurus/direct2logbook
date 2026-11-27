from django.core.paginator import Paginator
from django.utils import timezone
from django.shortcuts import render, reverse, redirect, get_object_or_404
import csv
import io
from django.http import HttpResponse, JsonResponse, Http404
from flights.models import Flight
from .submission import queue_csv_import
from .models import CSVImportBatch, CSV_PREVIEW_MAX_AGE
import uuid
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.db import transaction
from django.views.decorators.csrf import csrf_protect
from django.db.models import Sum, F, Q
from .validation import parse_csv, CSVValidationError, CSVPreviewExpired, MAX_BYTES, MAX_ROWS, OPTIONAL_HEADERS
from .forms import InspectForm, DateOrderForm, ColumnMappingForm, RecordResolutionForm, RowCorrectionForm, OverlapReviewForm
from .records import RecordResolution, validate_record_snapshot, RecordReviewRequired, reopen_record_review
from .rows import stage_rows, included_content, validate_rows, normalize_values
from flights.forms import AircraftForm, TailNumberForm
from django.db import DatabaseError
from logbook.db_errors import database_feedback
from .dates import interpret_dates, AmbiguousDates, DATE_ORDER_LABELS
from .formats import prepare_csv, ColumnsNeedMapping
from .mapping import read_source, normalize_mapping, HOUR_FIELDS, source_record_choices
from .duplicates import upload_digest, submitted_copy
from .summary import import_summary, note_route_conversion
from .overlaps import unresolved_overlaps, OverlapReviewRequired
from .airports import normalize_airport_routes
from .validation import HEADERS
import logging

logger = logging.getLogger('django.csv_app')


@login_required
@require_GET
def csv_download_view(request):
    user = request.user
    # Create the HttpResponse object with the appropriate CSV header.

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="{}_{}_logbook.csv"'.format(
        user.first_name, user.last_name)

    flights = Flight.objects.filter(user=user)
    writer = csv.writer(response)
    writer.writerow([
        'date',
        'aircraft',
        'registration',
        'route',
        'duration',
        'pilot in command',
        'second in command',
        'cross country',
        'night',
        'instrument',
        'approaches',
        'day landing',
        'night landing',
        'simulated instrument',
        'instructor',
        'dual',
        'solo',
        'simulator',
        'remarks',
        *OPTIONAL_HEADERS,
    ])

    for flight in flights:

        pic = flight.duration if flight.pilot_in_command else 0

        sic = flight.duration if flight.second_in_command else 0

        xc = flight.duration if flight.cross_country else 0

        if not flight.night:
            night = 0
        else:
            night = flight.night

        if not flight.instrument:
            ifr = 0
        else:
            ifr = flight.instrument

        if not flight.landings_day:
            day_ldg = 0
        else:
            day_ldg = flight.landings_day

        if not flight.landings_night:
            night_ldg = 0
        else:
            night_ldg = flight.landings_night

        if not flight.simulated_instrument:
            sim_inst = 0
        else:
            sim_inst = flight.simulated_instrument

        cfi = flight.duration if flight.instructor else 0

        dual = flight.duration if flight.dual else 0

        solo = flight.duration if flight.solo else 0

        if not flight.simulator:
            sim = 0
        else:
            sim = flight.duration

        writer.writerow([
            str(flight.date),
            str(flight.aircraft_type),
            str(flight.registration or ''),
            str(flight.route),
            flight.duration,
            pic,
            sic,
            xc,
            night,
            ifr,
            flight.approach_set.aggregate(total=Sum('number'))['total'] or 0,
            day_ldg,
            night_ldg,
            sim_inst,
            cfi,
            dual,
            solo,
            sim,
            flight.remarks,
            flight.device_type, flight.device_id, flight.atd_type,
            int(flight.instrument_credit_eligible), flight.launch_method,
            'Yes' if flight.hold or any(item.hold for item in flight.holding_set.all()) else 'No',
            '; '.join(f'{item.approach_type or "Unspecified"}: {item.number}' for item in flight.approach_set.all() if item.number),
            '' if flight.night_landings_full_stop is None else 'Yes' if flight.night_landings_full_stop else 'No',
        ])

    return response


@login_required
@require_GET
def csv_template_view(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="direct2logbook-import-template.csv"'
    writer = csv.writer(response)
    writer.writerow(HEADERS + OPTIONAL_HEADERS)
    writer.writerow(['2026-11-26', 'C172', 'N12345', 'KIAH-KCLL', '1.5', '1.5', '0', '1.5',
                     '0', '0', '0', '1', '0', '0', '0', '0', '0', '0', '', '', '', '', '0', '', 'No', '', ''])
    return response


@login_required
@csrf_protect
@require_http_methods(['GET', 'POST'])
def csv_inspect_view(request):
    form = InspectForm(request.POST or None, request.FILES or None)
    context = inspect_context(request, form)
    if request.method == 'POST':
        request.session.pop('file', None)
        if form.is_valid():
            try:
                raw = form.cleaned_data['file'].read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise CSVValidationError(f'The CSV must be no larger than {MAX_BYTES // (1024 * 1024)} MB.')
                original = raw.decode('utf-8-sig')
                digest = upload_digest(original)
                previous = submitted_copy(request.user, digest)
                if previous is not None:
                    context.update(latest_import=previous, duplicate_upload=(
                        'This file has already been imported. No flights were added.' if previous.completed else
                        'This file is already being imported. Check its progress below.'))
                    return render(request, 'csv_app/inspect_csv.html', context)
                try:
                    _, content = prepare_csv(original)
                except ColumnsNeedMapping:
                    table = read_source(original, user=request.user)
                    batch = CSVImportBatch.objects.create(user=request.user, content=original, source_digest=digest,
                        row_count=table.row_count, mapping_complete=False, records_complete=False, rows_complete=False)
                    context.update(mapping_context(batch, ColumnMappingForm(table=table)))
                else:
                    table = read_source(original, user=request.user)
                    source_form = ColumnMappingForm(table=table)
                    notes = [row['label'] + ': ' + row['conversion'] for row in source_form.rows() if row['conversion']]
                    context.update(resolve_preview(request.user, content, filename=form.cleaned_data['file'].name, source_digest=digest, source_metadata={'time_units': 'hours', 'conversion_notes': notes, 'record_choices': source_record_choices(table)}))
            except UnicodeDecodeError:
                form.add_error('file', 'Save the CSV with UTF-8 encoding.')
            except CSVValidationError as exc:
                form.add_error('file', str(exc))
    return render(request, 'csv_app/inspect_csv.html', context)


def resolve_preview(user, content, batch=None, filename='', check_rows=True, source_digest='', source_metadata=None):
    batch = batch or CSVImportBatch(user=user, source_digest=source_digest, records_complete=False, rows_complete=False)
    if source_metadata is not None:
        batch.source_metadata = source_metadata
    if check_rows:
        batch.row_data = stage_rows(content)
        batch.row_data['record_choices'] = batch.source_metadata.get('record_choices', {})
        batch.row_data['role_times'] = batch.source_metadata.get('role_times', False)
        batch.row_data['source_errors'] = batch.source_metadata.get('source_errors', {})
        batch.content = content
        batch.mapping_complete = True
        batch.row_count = len(batch.row_data['rows'])
        errors = validate_rows(user, batch.row_data)
        batch.rows_complete = not bool(errors)
        batch.save()
        if errors:
            return rows_context(batch, errors=errors)
        batch.row_data = normalize_values(batch.row_data)
        content = included_content(batch.row_data)
        batch.save(update_fields=['row_data'])
    try:
        interpreted, order = interpret_dates(content, batch.date_order if not check_rows and batch.date_order in ('mdy', 'dmy') else 'auto')
    except AmbiguousDates as ambiguity:
        provisional, _ = interpret_dates(content, 'mdy')
        rows, _ = parse_csv(provisional)
        original_content = content
        content = normalize_airport_routes(content, rows)
        note_route_conversion(batch, original_content, content)
        batch.content, batch.date_order, batch.row_count = content, 'pending', len(rows)
        batch.mapping_complete = True
        batch.save()
        return dict(date_choice=True, date_form=DateOrderForm(), date_examples=ambiguity.examples,
                    batch=batch, row_count=batch.row_count, latest_import=None)
    rows, preview = parse_csv(interpreted)
    original_content = interpreted
    interpreted = normalize_airport_routes(interpreted, rows)
    note_route_conversion(batch, original_content, interpreted)
    _, preview = parse_csv(interpreted)
    batch.content, batch.date_order, batch.row_count = interpreted, order, len(rows)
    batch.mapping_complete = True
    batch.save()
    return finish_records(user, batch, filename)


def finish_records(user, batch, filename=''):
    if batch.records_complete and batch.record_resolution.get('snapshot'):
        validate_record_snapshot(batch, user)
        _, preview = parse_csv(batch.content)
        return review_context(batch, preview, filename)
    resolution = RecordResolution(user, batch.content, batch.record_resolution)
    if resolution.issues:
        batch.records_complete = False
        batch.save(update_fields=['records_complete'])
        return records_context(batch, RecordResolutionForm(user=user, resolution=resolution))
    resolution.saved.pop('needs_review', None)
    batch.error_message = ''
    batch.content, batch.record_resolution = resolution.normalized()
    if batch.row_data:
        current = stage_rows(batch.content)
        current_rows = {row['line']: row for row in current['rows']}
        for row in batch.row_data['rows']:
            if row['line'] in current_rows:
                row['values'] = current_rows[row['line']]['values']
        errors = validate_rows(user, batch.row_data, batch.date_order)
        if errors:
            batch.rows_complete = False
            batch.records_complete = False
            batch.save(update_fields=['content', 'record_resolution', 'row_data', 'rows_complete', 'records_complete', 'error_message'])
            return rows_context(batch, errors=errors)
    batch.records_complete = True
    batch.save(update_fields=['content', 'record_resolution', 'records_complete', 'row_data', 'error_message'])
    _, preview = parse_csv(batch.content)
    return review_context(batch, preview, filename)


def rows_context(batch, form=None, errors=None, page=1):
    errors = errors if errors is not None else validate_rows(batch.user, batch.row_data, batch.date_order)
    form = form or RowCorrectionForm(data_rows=batch.row_data, page=page, errors=errors)
    form.row_errors = errors
    excluded = sum(row['excluded'] for row in batch.row_data['rows'])
    return dict(row_choice=True, row_form=form, correction_rows=form.rows(), batch=batch,
        included_count=len(batch.row_data['rows']) - excluded, excluded_count=excluded,
        error_count=len(errors), latest_import=None,
        previous_page=form.page - 1 if form.page > 1 else None,
        next_page=form.page + 1 if form.page < form.page_count else None)


@login_required
@csrf_protect
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def csv_rows_view(request, batch_id):
    batch = get_object_or_404(CSVImportBatch.objects.select_for_update(), pk=batch_id, user=request.user)
    if batch.is_expired:
        return HttpResponse('This CSV preview has expired. Upload and inspect the file again.', status=410)
    if batch.completed or batch.status != CSVImportBatch.Status.PREVIEW:
        return HttpResponse('This import has already been submitted.', status=409)
    if not batch.mapping_complete:
        return redirect('csv_mapping', batch_id=batch.pk)
    if not batch.row_data:
        batch.row_data = stage_rows(batch.content)
    try:
        page = int(request.POST.get('page', request.GET.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    batch.rows_complete = False
    batch.records_complete = False
    batch.record_resolution = {}  # Re-match all edited references; never reuse stale identities.
    batch.overlap_review = {}
    batch.save(update_fields=['overlap_review'])
    form = RowCorrectionForm(request.POST if request.method == 'POST' else None, data_rows=batch.row_data, page=page)
    context = inspect_context(request)
    if request.method == 'POST' and form.is_valid():
        batch.row_data = form.corrected()
        errors = validate_rows(request.user, batch.row_data, batch.date_order)
        included = sum(not row['excluded'] for row in batch.row_data['rows'])
        batch.row_count = included
        batch.content = included_content(batch.row_data)
        batch.save()
        destination = request.POST.get('show_page')
        if destination:
            try:
                page = int(destination)
            except ValueError:
                page = 1
            context.update(rows_context(batch, errors=errors, page=page))
        elif not included:
            context.update(rows_context(batch, errors=errors, page=page))
            context['wizard_error'] = 'Include at least one flight before continuing.'
        elif errors:
            first_bad = next(i for i, row in enumerate(batch.row_data['rows']) if row['line'] in errors)
            from .rows import PAGE_SIZE
            context.update(rows_context(batch, errors=errors, page=first_bad // PAGE_SIZE + 1))
        else:
            batch.row_data = normalize_values(batch.row_data)
            batch.rows_complete = True
            batch.content = included_content(batch.row_data)
            batch.save()
            try:
                context.update(resolve_preview(request.user, batch.content, batch=batch, check_rows=False))
            except CSVValidationError as exc:
                batch.rows_complete = False
                batch.save(update_fields=['rows_complete'])
                context.update(rows_context(batch))
                context['wizard_error'] = str(exc)
    else:
        batch.save(update_fields=['row_data', 'rows_complete', 'records_complete', 'record_resolution'])
        context.update(rows_context(batch, form=form))
    return render(request, 'csv_app/inspect_csv.html', context)


def records_context(batch, form):
    return dict(record_choice=True, record_form=form, record_rows=form.rows(),
                aircraft_stage=form.aircraft_stage, remaining=len(form.resolution.issues),
                record_review_message=batch.error_message if batch.record_resolution.get('needs_review') else '',
                batch=batch, row_count=batch.row_count, latest_import=None)


def records_guard(request, batch):
    if batch.is_expired:
        return HttpResponse('This CSV preview has expired. Upload and inspect the file again.', status=410)
    if batch.status != CSVImportBatch.Status.PREVIEW or batch.completed:
        return HttpResponse('This import has already been submitted.', status=409)
    if not batch.mapping_complete:
        return redirect('csv_mapping', batch_id=batch.pk)
    if not batch.rows_complete:
        return redirect('csv_rows', batch_id=batch.pk)
    if batch.date_order == 'pending':
        return redirect('csv_date_order', batch_id=batch.pk)


@login_required
@csrf_protect
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def csv_records_view(request, batch_id):
    batch = get_object_or_404(CSVImportBatch.objects.select_for_update(), pk=batch_id, user=request.user)
    blocked = records_guard(request, batch)
    if blocked is not None:
        return blocked
    context = inspect_context(request)
    try:
        if batch.records_complete:
            validate_record_snapshot(batch, request.user)
            _, preview = parse_csv(batch.content)
            context.update(review_context(batch, preview))
        else:
            resolution = RecordResolution(request.user, batch.content, batch.record_resolution)
            form = RecordResolutionForm(request.POST if request.method == 'POST' else None,
                                        user=request.user, resolution=resolution)
            if request.method == 'POST' and form.is_valid():
                try:
                    with transaction.atomic():
                        choices = form.cleaned_data['resolution']
                        for entry, tail_form in form.pending_tail_forms:
                            tail = tail_form.save(commit=False)
                            tail.user = request.user
                            tail.save()
                            choices['pairs'][entry['key']] = {'aircraft': tail.aircraft_id, 'tailnumber': tail.pk}
                        batch.record_resolution = choices
                        batch.save(update_fields=['record_resolution'])
                except DatabaseError:
                    form.add_error(None, 'A record changed while saving. Reload this step to check the aircraft and tailnumbers.')
                    context.update(records_context(batch, form))
                else:
                    context.update(finish_records(request.user, batch))
            elif resolution.issues:
                context.update(records_context(batch, form))
            else:
                context.update(finish_records(request.user, batch))
    except RecordReviewRequired:
        batch = reopen_record_review(request.user, batch.pk)
        resolution = RecordResolution(request.user, batch.content, batch.record_resolution)
        context.update(records_context(batch, RecordResolutionForm(user=request.user, resolution=resolution)))
    except CSVValidationError as exc:
        context['wizard_error'] = str(exc)
    return render(request, 'csv_app/inspect_csv.html', context)


@login_required
@csrf_protect
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def csv_create_record_view(request, batch_id, kind, index):
    batch = get_object_or_404(CSVImportBatch.objects.select_for_update(), pk=batch_id, user=request.user)
    blocked = records_guard(request, batch)
    if blocked is not None:
        return blocked
    if batch.records_complete:
        return redirect('csv_records', batch_id=batch.pk)
    resolution = RecordResolution(request.user, batch.content, batch.record_resolution)
    if kind not in ('aircraft', 'tailnumber'):
        raise Http404
    entries = resolution.sources if kind == 'aircraft' else resolution.pairs
    if index >= len(entries):
        raise Http404
    entry = entries[index]
    form_class = AircraftForm if kind == 'aircraft' else TailNumberForm
    initial = {'aircraft_type': entry['source']} if kind == 'aircraft' else {
        'registration': entry['source'], 'aircraft': entry['aircraft']}
    form = form_class(request.POST if request.method == 'POST' else None, user=request.user, initial=initial)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                item = form.save(commit=False)
                item.user = request.user
                item.save()
                choices = batch.record_resolution.copy()
                if kind == 'aircraft':
                    choices.setdefault('aircraft', {})[entry['key']] = item.pk
                else:
                    choices.setdefault('pairs', {})[entry['key']] = {
                        'aircraft': item.aircraft_id, 'tailnumber': item.pk}
                batch.record_resolution = choices
                batch.save(update_fields=['record_resolution'])
        except DatabaseError as exc:
            errors, _ = database_feedback(exc, kind)
            for field, messages in errors.items():
                for message in messages:
                    form.add_error(field if field in form.fields else None, message)
        else:
            return redirect('csv_records', batch_id=batch.pk)
    context = inspect_context(request)
    context.update(form=form, batch=batch, record_kind=kind,
                   record_title='New Aircraft' if kind == 'aircraft' else 'New Tailnumber')
    return render(request, 'csv_app/create_record.html', context)


def mapping_context(batch, form):
    rows = form.rows()
    return dict(mapping_choice=True, mapping_form=form, batch=batch, row_count=batch.row_count,
                source_notices=form.table.notices, needs_time_units=form.fields['time_units'].required,
                show_time_units=form.show_time_units,
                block_checks=form.block_checks(), block_check_count=len(form.block_checks()),
                uses_block_times=form.uses_block_times, mapping_native_times=form.table.role_times,
                mapping_dependencies=form.table.dependencies,
                mapping_column_formats=form.table.column_formats, mapping_sample_rows=[record for record in form.table.records if any(record)][:3],
                mapping_route_columns=[str(index) for index, target in form.table.derived.items() if target == 'route'],
                mapping_hour_fields=sorted(HOUR_FIELDS),
                mapping_rows=[row for row in rows if row['target'] not in ('departure', 'destination', 'block out', 'block in')],
                conversion_mapping_rows=[row for row in rows if row['target'] in ('departure', 'destination', 'block out', 'block in')],
                required_mapping_rows=[row for row in rows if row['group'] == 'required'],
                review_mapping_rows=[row for row in rows if row['group'] == 'review'],
                matched_mapping_rows=[row for row in rows if row['group'] == 'matched'],
                extra_mapping_rows=[row for row in rows if row['group'] == 'optional'],
                unused_columns=form.unused_columns(),
                source_columns=form.source_columns(),
                latest_import=None)


@login_required
@csrf_protect
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def csv_mapping_view(request, batch_id):
    batch = get_object_or_404(CSVImportBatch.objects.select_for_update(), pk=batch_id, user=request.user)
    context = inspect_context(request)
    if batch.is_expired:
        context['wizard_error'] = 'This CSV preview has expired. Upload and inspect the file again.'
        return render(request, 'csv_app/inspect_csv.html', context, status=410)
    if batch.status != CSVImportBatch.Status.PREVIEW or batch.completed:
        context['wizard_error'] = 'This import has already been submitted. Check its progress before starting another.'
        return render(request, 'csv_app/inspect_csv.html', context, status=409)
    if batch.mapping_complete:
        return redirect('csv_date_order', batch_id=batch.pk)
    table = read_source(batch.content, user=request.user)
    form = ColumnMappingForm(request.POST if request.method == 'POST' else None, table=table)
    if request.method == 'POST' and request.POST.get('validate_only') == '1':
        valid = form.is_valid()
        return JsonResponse({'valid': valid, 'errors': form.errors.get_json_data(),
                             'year_required': form.needs_year_confirmation, 'block_checks': form.block_checks(),
                             'mapping_requirements': {name: field.required for name, field in form.fields.items() if name.startswith('map_')}})
    if request.method == 'POST' and form.is_valid():
        try:
            content = normalize_mapping(table, form.cleaned_data['mapping'], form.cleaned_data['time_units'] or 'hours', form.cleaned_data['confirm_short_years'], form.cleaned_data['confirm_overnight'])
            batch.source_metadata = {'source': table.source_key, 'delimiter': table.delimiter,
                'time_units': form.cleaned_data['time_units'] or 'hours', 'role_times': table.role_times,
                'record_choices': source_record_choices(table, form.cleaned_data['mapping']),
                'block_overnight_confirmed': form.cleaned_data['confirm_overnight'],
                'short_years_confirmed': form.cleaned_data['confirm_short_years'],
                'block_duration_differences_confirmed': form.cleaned_data['confirm_block_difference'],
                'source_errors': table.source_errors, 'notices': table.notices,
                'conversion_notes': [row['label'] + ': ' + row['conversion'] for row in form.rows() if row['conversion']]}
            batch.column_mapping = form.cleaned_data['mapping']
            context.update(resolve_preview(request.user, content, batch=batch))
        except CSVValidationError as exc:
            form.add_error(None, str(exc))
            context.update(mapping_context(batch, form))
    else:
        context.update(mapping_context(batch, form))
    return render(request, 'csv_app/inspect_csv.html', context)



def overlaps_context(batch, issues, form=None):
    form = form or OverlapReviewForm(issues=issues)
    return dict(overlap_choice=True, batch=batch, overlap_form=form, overlap_rows=form.rows(),
                overlap_remaining=len(issues), latest_import=None)


@login_required
@csrf_protect
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def csv_overlaps_view(request, batch_id):
    batch = get_object_or_404(CSVImportBatch.objects.select_for_update(), pk=batch_id, user=request.user)
    blocked = records_guard(request, batch)
    if blocked is not None:
        return blocked
    if not batch.records_complete:
        return redirect('csv_records', batch_id=batch.pk)
    context = inspect_context(request)
    issues = unresolved_overlaps(batch, request.user)
    if not issues:
        return redirect('csv_records', batch_id=batch.pk)
    form = OverlapReviewForm(request.POST if request.method == 'POST' else None, issues=issues)
    if request.method == 'POST' and form.is_valid():
        if not batch.row_data:
            batch.row_data = stage_rows(batch.content)
        excluded = set()
        for issue in form.issues:
            action = form.cleaned_data[f'decision_{issue["line"]}']
            batch.overlap_review[str(issue['line'])] = {'action': action, 'token': issue['token']}
            if action == 'exclude':
                excluded.add(issue['line'])
        for row in batch.row_data['rows']:
            if row['line'] in excluded:
                row['excluded'] = True
                row['exclusion_reason'] = 'Possible duplicate'
        if not any(not row['excluded'] for row in batch.row_data['rows']):
            output = io.StringIO()
            csv.writer(output).writerow(batch.row_data['header'])
            batch.content = output.getvalue()
            batch.row_count = 0
            batch.rows_complete = False
            batch.save(update_fields=['content', 'row_count', 'rows_complete', 'row_data', 'overlap_review'])
            context.update(all_excluded=True, batch=batch, latest_import=None)
        else:
            # Keep resolved account identities and the original source row numbers.
            records = list(csv.reader(io.StringIO(batch.content)))
            for line in excluded:
                records[line - 1] = []
            output = io.StringIO()
            csv.writer(output).writerows(records)
            batch.content = output.getvalue()
            batch.row_count = sum(not row['excluded'] for row in batch.row_data['rows'])
            batch.save(update_fields=['content', 'row_count', 'row_data', 'overlap_review'])
            pending = unresolved_overlaps(batch, request.user)
            if pending:
                context.update(overlaps_context(batch, pending))
            else:
                _, preview = parse_csv(batch.content)
                context.update(review_context(batch, preview))
    else:
        if form.stale:
            context['wizard_error'] = 'Matching entries changed. Review the updated records and choose again.'
            form = OverlapReviewForm(issues=issues)
        context.update(overlaps_context(batch, issues, form))
    return render(request, 'csv_app/inspect_csv.html', context)


def inspect_context(request, form=None):
    return {
        'csv_max_bytes': MAX_BYTES, 'csv_max_mb': MAX_BYTES // (1024 * 1024), 'csv_max_rows_label': f'{MAX_ROWS:,}',
        'inspect_form': form or InspectForm(), 'title': 'CSV Upload', 'page_title': 'Import Logbook',
        'home_link': reverse('home'), 'parent_link': reverse('profile'),
        'parent_name': 'Profile',
        'latest_import': CSVImportBatch.objects.filter(
            Q(status__in=[CSVImportBatch.Status.QUEUED, CSVImportBatch.Status.PROCESSING, CSVImportBatch.Status.UNCONFIRMED]) |
            Q(status=CSVImportBatch.Status.PREVIEW, record_resolution__needs_review=True, created_at__gt=timezone.now() - CSV_PREVIEW_MAX_AGE),
            user=request.user, completed=False,
        ).order_by(F('submitted_at').desc(nulls_last=True), '-created_at').first(),
    }


def review_context(batch, preview, filename='', page=1):
    pending = unresolved_overlaps(batch, batch.user)
    if pending:
        return overlaps_context(batch, pending)
    summary = import_summary(batch)
    preview_page = Paginator(preview, 50).get_page(page)
    return dict(excluded_count=summary['excluded_count'], file=preview_page.object_list, preview_page=preview_page, preview_ready=True,
                row_count=summary['entry_count'], batch=batch, latest_import=None,
                csv_filename=filename, date_order_label=DATE_ORDER_LABELS.get(batch.date_order, 'Dates recognized'),
                import_summary=summary, preview_warnings=summary['warnings'])


@login_required
@require_GET
def csv_preview_view(request, batch_id):
    batch = get_object_or_404(CSVImportBatch, pk=batch_id, user=request.user)
    context = inspect_context(request)
    if batch.is_expired:
        context['wizard_error'] = 'This CSV preview has expired. Upload and inspect the file again.'
        return render(request, 'csv_app/inspect_csv.html', context, status=410)
    if batch.status != CSVImportBatch.Status.PREVIEW or batch.completed:
        context['wizard_error'] = 'This import has already been submitted. Check its progress before starting another.'
        return render(request, 'csv_app/inspect_csv.html', context, status=409)
    if not batch.mapping_complete:
        return redirect('csv_mapping', batch_id=batch.pk)
    if not batch.rows_complete:
        return redirect('csv_rows', batch_id=batch.pk)
    if batch.date_order == 'pending':
        return redirect('csv_date_order', batch_id=batch.pk)
    if not batch.records_complete or batch.record_resolution.get('needs_review'):
        return redirect('csv_records', batch_id=batch.pk)
    try:
        _, preview = parse_csv(batch.content)
        context.update(review_context(batch, preview, page=request.GET.get('page', 1)))
    except CSVValidationError as exc:
        context['wizard_error'] = str(exc)
        return render(request, 'csv_app/inspect_csv.html', context, status=400)
    return render(request, 'csv_app/inspect_csv.html', context)


@login_required
@csrf_protect
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def csv_date_order_view(request, batch_id):
    batch = get_object_or_404(CSVImportBatch.objects.select_for_update(), pk=batch_id, user=request.user)
    context = inspect_context(request)
    if batch.is_expired:
        context['wizard_error'] = 'This CSV preview has expired. Upload and inspect the file again.'
        return render(request, 'csv_app/inspect_csv.html', context, status=410)
    if batch.status != CSVImportBatch.Status.PREVIEW or batch.completed:
        context['wizard_error'] = 'This import has already been submitted. Check its progress before starting another.'
        return render(request, 'csv_app/inspect_csv.html', context, status=409)
    if not batch.mapping_complete:
        return redirect('csv_mapping', batch_id=batch.pk)
    if not batch.rows_complete:
        return redirect('csv_rows', batch_id=batch.pk)
    if batch.date_order != 'pending':
        try:
            context.update(finish_records(request.user, batch))
        except CSVValidationError as exc:
            context['wizard_error'] = str(exc)
        return render(request, 'csv_app/inspect_csv.html', context)
    form = DateOrderForm(request.POST if request.method == 'POST' else None)
    try:
        if request.method == 'POST' and form.is_valid():
            interpreted, order = interpret_dates(batch.content, form.cleaned_data['date_order'])
            _, preview = parse_csv(interpreted)
            batch.content = interpreted
            batch.date_order = order
            batch.save(update_fields=['content', 'date_order'])
            context.update(finish_records(request.user, batch))
        else:
            interpret_dates(batch.content)
    except AmbiguousDates as ambiguity:
        context.update(date_choice=True, date_form=form, date_examples=ambiguity.examples,
                       batch=batch, row_count=batch.row_count, latest_import=None)
    except CSVValidationError as exc:
        context['wizard_error'] = str(exc)
    return render(request, 'csv_app/inspect_csv.html', context)


@transaction.non_atomic_requests
@login_required
@require_POST
@csrf_protect
def csv_upload_view(request):
    try:
        batch_id = uuid.UUID(request.POST.get('batch_id', ''))
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({'message': 'Inspect a valid CSV file before importing.'}, status=400)
    try:
        batch, duplicate = queue_csv_import(request.user, batch_id)
        count = batch.row_count
    except CSVPreviewExpired as exc:
        return JsonResponse({'message': str(exc)}, status=410)
    except RecordReviewRequired:
        batch = reopen_record_review(request.user, batch_id)
        return JsonResponse(csv_import_status_data(batch), status=409 if batch.record_resolution.get('needs_review') else 202)
    except OverlapReviewRequired as exc:
        return JsonResponse({'message': str(exc) + ' No flights were imported.', 'review_url': reverse('csv_overlaps', args=[batch_id])}, status=400)
    except CSVValidationError as exc:
        return JsonResponse({'message': str(exc) + ' No flights were imported.'}, status=400)
    except Http404:
        raise
    except Exception:
        logger.exception('CSV import failed user_id=%s', request.user.pk)
        return JsonResponse({'message': 'Completion could not be confirmed. Retry this same confirmation to check without importing duplicates.'}, status=503)
    payload = csv_import_status_data(batch)
    payload['already_submitted'] = duplicate
    payload['already_completed'] = batch.completed and duplicate
    code = 200 if batch.completed else (503 if batch.status == CSVImportBatch.Status.UNCONFIRMED else
                                       409 if batch.status == CSVImportBatch.Status.FAILED else 202)
    return JsonResponse(payload, status=code)


def csv_import_status_data(batch):
    messages = {
        'preview': 'Your CSV preview is ready to import.',
        'queued': f'Import queued: {batch.row_count} entries. You can leave this page and check back later.',
        'unconfirmed': 'Queue submission could not be confirmed. Check progress here before starting another import.',
        'processing': f'Importing {batch.row_count} entries. Changes will appear together when the import finishes.',
        'completed': f'Import complete: {batch.row_count} entries.',
        'needs_review': batch.error_message,
        'expired': 'This CSV preview has expired. Upload and inspect the file again.',
        'failed': batch.error_message or 'The import could not finish. Upload and inspect the file again.',
    }
    status = batch.status
    if batch.completed:
        status = CSVImportBatch.Status.COMPLETED
    elif batch.is_expired:
        status = 'expired'
    elif batch.status == CSVImportBatch.Status.PREVIEW and batch.record_resolution.get('needs_review'):
        status = 'needs_review'
    payload = {
        'status': status, 'row_count': batch.row_count,
        'imported_count': batch.row_count if batch.completed else 0,
        'message': messages[status],
        'status_url': reverse('csv_import_status', args=[batch.pk]),
    }
    if status == 'needs_review':
        payload['review_url'] = reverse('csv_records', args=[batch.pk])
        payload['review_label'] = 'Correct aircraft/tailnumber'
    return payload


@login_required
@require_GET
def csv_import_status(request, batch_id):
    from django.shortcuts import get_object_or_404
    batch = get_object_or_404(CSVImportBatch, pk=batch_id, user=request.user)
    response = JsonResponse(csv_import_status_data(batch))
    response['Cache-Control'] = 'no-store'
    return response
