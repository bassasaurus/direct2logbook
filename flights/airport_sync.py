"""Conservative, additive refresh of airport reference data from OurAirports."""
import csv
import hashlib
import io
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from django.db import connection, transaction
from django.utils import timezone

from flights.models import AirportCode, MapData

BASE_URL = 'https://davidmegginson.github.io/ourairports-data/'
MAX_DOWNLOAD = 50 * 1024 * 1024
FIELDS = ('name', 'city', 'state', 'country', 'iata', 'icao', 'latitude', 'longitude',
          'elevation', 'ourairports_id', 'ourairports_ident', 'airport_type')
TYPES = {'small_airport', 'medium_airport', 'large_airport', 'heliport', 'seaplane_base',
         'balloonport', 'closed', 'closed_airport'}


@dataclass
class AirportRecord:
    source_id: int
    values: dict
    codes: set


def read_csv(data, required):
    try:
        reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig'), newline=''))
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError('Missing CSV columns: ' + ', '.join(sorted(required - set(reader.fieldnames or []))))
        rows = list(reader)
    except (UnicodeError, csv.Error) as error:
        raise ValueError('Invalid UTF-8 CSV data') from error
    if not rows or any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError('Empty or malformed CSV data')
    return rows


def code(value):
    value = value.strip().upper()
    return value if re.fullmatch(r'[A-Z0-9]{1,12}', value) else ''


def parse_sources(airports, countries, regions):
    country_names = {row['code']: row['name'] for row in read_csv(countries, {'code', 'name'})}
    region_names = {row['code']: row['name'] for row in read_csv(regions, {'code', 'name'})}
    rows = read_csv(airports, {'id', 'ident', 'type', 'name', 'latitude_deg', 'longitude_deg',
                              'elevation_ft', 'iso_country', 'iso_region', 'municipality',
                              'icao_code', 'iata_code', 'gps_code', 'local_code'})
    ids = [int(row['id']) for row in rows if row['id'].isascii() and row['id'].isdigit()]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate OurAirports IDs; no airport data applied')
    records, skipped = [], []
    for row in rows:
        try:
            source_id = int(row['id'])
            if not 1 <= source_id <= 2147483647:
                raise ValueError('invalid source ID')
            latitude, longitude = float(row['latitude_deg']), float(row['longitude_deg'])
            if not (math.isfinite(latitude) and math.isfinite(longitude) and -90 <= latitude <= 90 and -180 <= longitude <= 180):
                raise ValueError('invalid coordinates')
            if row['iso_country'] not in country_names:
                raise ValueError('unknown country')
            if row['type'] not in TYPES:
                raise ValueError('unknown airport type')
            icao = row['icao_code'].strip().upper()
            if icao and not re.fullmatch(r'[A-Z]{4}', icao):
                raise ValueError('invalid ICAO code')
            iata_code = row['iata_code'].strip().upper()
            if iata_code and not re.fullmatch(r'[A-Z]{3}', iata_code):
                raise ValueError('invalid IATA code')
            codes = {(value, kind) for kind, value in (
                ('icao', icao), ('iata', iata_code),
                ('gps', code(row['gps_code'])),
                ('faa' if row['iso_country'] in {'US', 'PR', 'VI', 'GU', 'AS', 'MP', 'UM'}
                 and re.fullmatch(r'[A-Z0-9]{3,4}', code(row['local_code'])) else 'local', code(row['local_code']))) if value}
            local = code(row['local_code']) if row['iso_country'] == 'US' else ''
            iata = iata_code or local
            if len(iata) > 4:
                iata = ''
            values = dict(name=row['name'].strip(), city=row['municipality'].strip(),
                          country=country_names[row['iso_country']],
                          state=region_names.get(row['iso_region'], ''),
                          icao=icao, iata=iata, latitude=latitude, longitude=longitude,
                          elevation=int(row['elevation_ft']) if row['elevation_ft'].strip() else None,
                          ourairports_id=source_id, ourairports_ident=row['ident'].strip(),
                          airport_type='closed' if row['type'] == 'closed_airport' else row['type'])
            if not values['name'] or any(len(str(values[field])) > MapData._meta.get_field(field).max_length
                                         for field in ('name', 'city', 'country', 'state', 'ourairports_ident')):
                raise ValueError('invalid name or overlong text')
            records.append(AirportRecord(source_id, values, codes))
        except (TypeError, ValueError, OverflowError) as error:
            skipped.append({'source_id': row['id'], 'name': row['name'], 'reason': str(error)})
    if not records:
        raise ValueError('No valid airport rows; no data applied')
    return records, skipped


def distance_km(airport, values):
    if (airport.latitude is None or airport.longitude is None
            or not math.isfinite(airport.latitude) or not math.isfinite(airport.longitude)
            or not -90 <= airport.latitude <= 90 or not -180 <= airport.longitude <= 180):
        return math.inf
    lat1, lon1, lat2, lon2 = map(math.radians, (airport.latitude, airport.longitude, values['latitude'], values['longitude']))
    a = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371 * 2 * math.asin(math.sqrt(min(1, max(0, a))))


def sync_airports(records, skipped=(), *, apply=False):
    """Preview or apply one transaction. Never delete rows or change flights."""
    with transaction.atomic():
        if apply and connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_try_advisory_xact_lock(%s)', [734201965])
                if not cursor.fetchone()[0]:
                    raise ValueError('Another airport sync is running')
        queryset = MapData.objects.order_by('pk').prefetch_related('codes')
        if apply:
            queryset = queryset.select_for_update()
        existing = list(queryset)
        by_id = {airport.ourairports_id: airport for airport in existing if airport.ourairports_id}
        by_icao, by_code = defaultdict(list), defaultdict(list)
        existing_codes = {}
        for airport in existing:
            aliases = {(alias.code, alias.kind) for alias in airport.codes.all()}
            existing_codes[airport.pk] = aliases
            icao_history = {value for value, kind in aliases if kind == 'icao'}
            if airport.icao:
                icao_history.add(airport.icao.strip().upper())
            for value in icao_history:
                by_icao[value].append(airport)
            for value in {airport.icao.strip().upper(), airport.iata.strip().upper()} | {alias[0] for alias in aliases}:
                if value:
                    by_code[value].append(airport)
        source_icaos = Counter(record.values['icao'] for record in records if record.values['icao'])
        report = {'applied': apply, 'checked_at': timezone.now().isoformat(), 'source_rows': len(records) + len(skipped),
                  'created': 0, 'updated': 0, 'unchanged': 0, 'aliases_added': 0,
                  'retained_missing': 0, 'skipped': list(skipped), 'changes': []}
        updates, creates, code_updates, claimed = [], [], [], set()
        for record in records:
            values = record.values
            airport = by_id.get(record.source_id)
            reason = None
            if airport is None:
                matches = by_icao.get(values['icao'], []) if values['icao'] else []
                if matches:
                    # Existing duplicate ICAOs can be referenced by saved choices: never merge or guess.
                    if len(matches) != 1:
                        reason = 'multiple legacy rows share this ICAO'
                    else:
                        airport = matches[0]
                        if airport.ourairports_id:
                            reason = 'ICAO belongs to a different source ID'
                else:
                    candidates = {item.pk: item for value, _ in record.codes for item in by_code.get(value, [])
                                  if not item.ourairports_id and item.country.strip().casefold() == values['country'].strip().casefold()
                                  and distance_km(item, values) <= 2}
                    if len(candidates) == 1:
                        airport = next(iter(candidates.values()))
                    elif candidates:
                        reason = 'multiple nearby legacy code matches'
                if source_icaos.get(values['icao'], 0) > 1:
                    reason = 'ICAO shared by multiple source airports'
            if airport is not None and not reason:
                if airport.pk in claimed:
                    reason = 'legacy row already claimed by another source airport'
                elif airport.country.strip().casefold() != values['country'].strip().casefold():
                    reason = 'country differs; manual review required'
                elif not airport.ourairports_id and distance_km(airport, values) > 2:
                    reason = 'legacy coordinates differ by more than 2 km; manual review required'
                elif distance_km(airport, values) > 10:
                    reason = 'coordinates differ by more than 10 km; manual review required'
                elif values['icao'] and any(item.pk != airport.pk for item in by_icao.get(values['icao'], [])):
                    reason = 'new ICAO conflicts with another database row'
            if airport is None and not record.codes:
                reason = reason or 'no routable codes'
            if reason:
                report['skipped'].append({'source_id': record.source_id, 'name': values['name'], 'reason': reason})
                continue
            aliases = set(record.codes)
            if airport is not None:
                claimed.add(airport.pk)
                # Keep legacy/closed airports' previous codes and populated fields when the source is blank.
                aliases.update((value, kind) for value, kind in ((airport.icao.strip().upper(), 'icao'), (airport.iata.strip().upper(), 'legacy')) if value)
                effective = {field: value for field, value in values.items() if value not in ('', None)}
                changes = {field: {'old': getattr(airport, field), 'new': value}
                           for field, value in effective.items() if getattr(airport, field) != value}
                new_codes = aliases - existing_codes[airport.pk]
                # A no-change run must not add the same old primary code again under a new kind.
                new_codes = {(value, kind) for value, kind in new_codes
                             if kind != 'legacy' or not any(code_value == value for code_value, _ in existing_codes[airport.pk] | record.codes)}
                if changes or new_codes:
                    report['updated'] += 1
                    report['changes'].append({'action': 'update', 'pk': airport.pk, 'source_id': record.source_id,
                                              'name': values['name'], 'fields': changes, 'codes_added': sorted(new_codes)})
                    for field, value in effective.items():
                        setattr(airport, field, value)
                    updates.append(airport)
                else:
                    report['unchanged'] += 1
            else:
                airport = MapData(**values)
                creates.append(airport)
                new_codes = aliases
                report['created'] += 1
                report['changes'].append({'action': 'create', 'source_id': record.source_id, 'name': values['name'],
                                          'fields': values, 'codes_added': sorted(new_codes)})
            code_updates.append((airport, new_codes))
            report['aliases_added'] += len(new_codes)
        source_ids = {record.source_id for record in records}
        report['retained_missing'] = sum(airport.ourairports_id is not None and airport.ourairports_id not in source_ids for airport in existing)
        if apply:
            MapData.objects.bulk_create(creates, batch_size=500)
            MapData.objects.bulk_update(updates, FIELDS, batch_size=250)
            AirportCode.objects.bulk_create([AirportCode(airport=airport, code=value, kind=kind)
                                            for airport, aliases in code_updates for value, kind in aliases], batch_size=500)
        return report


def source_hash(data):
    return hashlib.sha256(data).hexdigest()
