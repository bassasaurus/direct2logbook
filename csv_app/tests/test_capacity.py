"""Opt-in 10,000-entry PostgreSQL acceptance tests; ordinary suites skip these.

D2L_RUN_CSV_CAPACITY_TESTS=1 python manage.py test csv_app.tests.test_capacity
Tests use the real wizard, transaction boundaries, signals and worker entry point.
Only mail delivery and broker publishing are replaced.
"""
import json
import os
import resource
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
from threading import Event, Barrier
from unittest import skipUnless
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection, close_old_connections, DatabaseError
from django.db.models import Sum
from django.test import TransactionTestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from csv_app.models import CSVImportBatch
from csv_app.tasks import import_csv_batch
from csv_app.tests.airport_fixtures import seed_airports
from csv_app.tests.record_fixtures import seed_records
from csv_app.tests.test_atomic_import import content, row
from csv_app.validation import HEADERS, OPTIONAL_HEADERS, MAX_BYTES, MAX_ROWS
from flights.models import Flight, Aircraft, TailNumber, Approach, Holding, Total, Stat, Regs, MapData


COUNT = 10_000
PROPOSED_BYTES = 20 * 1024 * 1024


def payload(mixed=False):
    records=[]
    for index in range(COUNT):
        duration=str(Decimal(10+index%10)/10)
        device=mixed and index%5==1
        sic=index%5==0
        approaches=not index%5
        values=row(**{'0':str(date(2026,11,27)-timedelta(days=index%3650)),
            '1':'B737' if sic else 'C172','2':'' if device else 'N737TS' if sic else 'N12345',
            '3':'' if device else 'KIAH-KCLL' if index%2 else 'KCLL-KIAH',
            '4':duration,'5':'0' if sic or device else duration,'6':duration if sic else '0',
            '7':'0' if device else duration,'8':'0' if device else '.3','9':'0' if device else '.2',
            '10':'2' if approaches else '0','11':'0' if device else '1','12':'0' if device else '1',
            '13':duration if device else '.1','14':'0','15':duration if device else '0',
            '16':'0','17':duration if device else '0',
            '18':f'Capacity entry {index:05d} '+ 'A'*200})
        records.append(values+['FFS' if device else '', 'Capacity device' if device else '', '', '0', '',
            'Yes' if index%7==0 else 'No','ILS:1; LPV:1' if approaches else '', '' if device else 'Yes'])
    return content(records,HEADERS+OPTIONAL_HEADERS),records


@skipUnless(os.environ.get('D2L_RUN_CSV_CAPACITY_TESTS')=='1','Opt-in 10,000-entry capacity acceptance test.')
@override_settings(SECURE_SSL_REDIRECT=False)
class CSVCapacityTests(TransactionTestCase):
    def setUp(self):
        self.assertEqual(connection.vendor,'postgresql')
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.assertGreaterEqual(MAX_ROWS,COUNT)
        self.assertGreaterEqual(MAX_BYTES,PROPOSED_BYTES)
        self.notify=self.stack.enter_context(patch('csv_app.csv_import.email_confirmation'))
        seed_airports()
        for code,lat,lon in (('KIAH',29.984,-95.341),('KCLL',30.588,-96.364),('KMCO',28.429,-81.309)):
            MapData.objects.filter(icao=code).update(latitude=lat,longitude=lon)

    def metric(self,name,elapsed,**details):
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2 if sys.platform=='darwin' else 1024)
        item=dict(test=self._testMethodName,stage=name,seconds=round(elapsed,3),peak_process_mb=round(peak,1),**details)
        print('CAPACITY '+json.dumps(item),flush=True)
        if os.environ.get('CSV_CAPACITY_METRICS'):
            with Path(os.environ['CSV_CAPACITY_METRICS']).open('a') as output:output.write(json.dumps(item)+'\n')

    def account(self,name):
        user=get_user_model().objects.create_user(name,email=name+'@example.com')
        aircraft,tail=seed_records(user)
        jet=Aircraft.objects.create(user=user,aircraft_type='B737',aircraft_category='A',aircraft_class='MEL',turbine=True,large=True)
        TailNumber.objects.create(user=user,aircraft=jet,registration='N737TS',is_121=True)
        original=Flight.objects.create(user=user,aircraft_type=aircraft,registration=tail,
            date='1990-01-01',route='KIAH-KCLL',duration='.5',pilot_in_command=True)
        return user,original.pk

    def upload(self,user,text):
        client=Client();client.force_login(user)
        started=time.perf_counter()
        response=client.post(reverse('csv_inspect'),{'file':SimpleUploadedFile('capacity.csv',text.encode())})
        self.metric('preview',time.perf_counter()-started,bytes=len(text.encode()))
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.context['preview_ready'],str(response.context.get('row_form') or response.context.get('inspect_form')))
        self.assertEqual(response.context['row_count'],COUNT)
        self.assertEqual(len(response.context['file']),50)
        self.assertLess(len(response.content),200_000)
        self.assertGreater(len(text.encode()),2*1024*1024)
        self.assertLess(time.perf_counter()-started,20,'Preview exceeds the web-request budget.')
        batch=response.context['batch']
        started=time.perf_counter()
        last=client.get(reverse('csv_preview',args=[batch.pk]),{'page':200})
        self.metric('last_page',time.perf_counter()-started)
        self.assertEqual(last.context['preview_page'].number,200)
        self.assertEqual(len(last.context['file']),50)
        self.assertContains(last,'Capacity entry 09999')
        self.assertNotContains(last,'Capacity entry 00000')
        self.assertLess(time.perf_counter()-started,10,'Preview paging exceeds the web-request budget.')
        started=time.perf_counter()
        with patch('csv_app.submission.import_csv_batch.apply_async') as publish:
            result=client.post(reverse('csv_upload'),{'batch_id':batch.pk})
        self.metric('queue',time.perf_counter()-started)
        self.assertEqual(result.status_code,202,result.content[:500])
        self.assertEqual(publish.call_count,1)
        batch.refresh_from_db()
        return batch

    def worker(self,user_pk,batch_pk,task_id,barrier=None):
        close_old_connections()
        try:
            if barrier:barrier.wait(timeout=10)
            import_csv_batch.push_request(id=task_id)
            try:import_csv_batch.run(user_pk,str(batch_pk))
            finally:import_csv_batch.pop_request()
        finally:connection.close()

    def verify(self,user,original,records,batch):
        batch.refresh_from_db();self.assertTrue(batch.completed)
        self.assertEqual(batch.row_count,COUNT)
        self.assertEqual(batch.content,'');self.assertEqual(batch.row_data,{})
        self.assertTrue(Flight.objects.filter(pk=original,user=user,duration='.5').exists())
        saved=list(Flight.objects.filter(user=user).exclude(pk=original).order_by('pk').values(
            'date','aircraft_type__aircraft_type','registration__registration','route','duration',
            'pilot_in_command','second_in_command','cross_country','instructor','dual','solo','simulator',
            'night','instrument','simulated_instrument','landings_day','landings_night','hold','remarks',
            'device_type','device_id','night_landings_full_stop','map_error','aircraft_type_error','registration_error','app_markers'))
        self.assertEqual(len(saved),COUNT)
        actual=Decimal('.5');device=Decimal(0);roles={name:Decimal('.5') if name=='pilot_in_command' else Decimal(0)
            for name in ('pilot_in_command','second_in_command','cross_country','dual','instructor','solo')}
        for index,(saved_row,raw) in enumerate(zip(saved,records)):
            sim=Decimal(raw[17])>0
            expected=dict(date=date.fromisoformat(raw[0]),aircraft_type__aircraft_type=raw[1],registration__registration=raw[2] or None,
                route=raw[3],duration=Decimal(raw[4]),night=Decimal(raw[8]),instrument=Decimal(raw[9]),
                simulated_instrument=Decimal(raw[13]),landings_day=int(raw[11]),landings_night=int(raw[12]),remarks=raw[18],
                hold=raw[24]=='Yes',device_type=raw[19],device_id=raw[20],night_landings_full_stop=None if sim else True)
            for column,name in ((5,'pilot_in_command'),(6,'second_in_command'),(7,'cross_country'),(14,'instructor'),(15,'dual'),(16,'solo'),(17,'simulator')):
                expected[name]=Decimal(raw[column])>0
            self.assertEqual({key:saved_row[key] for key in expected},expected,f'Entry {index}')
            self.assertFalse(saved_row['map_error']);self.assertFalse(saved_row['aircraft_type_error']);self.assertFalse(saved_row['registration_error'])
            self.assertEqual(len(saved_row['app_markers']),0 if sim else 2)
            if sim:device+=Decimal(raw[4])
            else:
                actual+=Decimal(raw[4])
                for name in roles:
                    if expected[name]:roles[name]+=Decimal(raw[4])
        totals=Total.objects.get(user=user,total='All')
        self.assertEqual(totals.total_time,actual);self.assertEqual(totals.simulator,device)
        for name,amount in roles.items():self.assertEqual(getattr(totals,name),amount,name)
        self.assertEqual(Stat.objects.filter(user=user).aggregate(n=Sum('total_time'))['n'],actual)
        self.assertEqual(Stat.objects.filter(user=user).aggregate(n=Sum('simulator'))['n'],device)
        self.assertEqual(Regs.objects.filter(user=user).aggregate(n=Sum('pilot_in_command'))['n'],roles['pilot_in_command'])
        self.assertEqual(Regs.objects.filter(user=user).aggregate(n=Sum('second_in_command'))['n'],roles['second_in_command'])
        self.assertEqual(Approach.objects.filter(flight_object__user=user).count(),4000)
        self.assertEqual(Approach.objects.filter(flight_object__user=user,approach_type='ILS').aggregate(n=Sum('number'))['n'],2000)
        self.assertEqual(Holding.objects.filter(flight_object__user=user,hold=True).count(),sum(raw[24]=='Yes' for raw in records))
        self.metric('verified',0,entries=COUNT,flight_hours=str(actual),device_hours=str(device))

    def test_concurrent_accounts_and_duplicate_worker_delivery(self):
        first,original_a=self.account('capacity-a');second,original_b=self.account('capacity-b')
        text_a,records_a=payload();text_b,records_b=payload(mixed=True)
        batch_a=self.upload(first,text_a);batch_b=self.upload(second,text_b)
        started=time.perf_counter();barrier=Barrier(3)
        with ThreadPoolExecutor(max_workers=3) as pool:
            jobs=[pool.submit(self.worker,first.pk,batch_a.pk,batch_a.task_id,barrier),
                  pool.submit(self.worker,second.pk,batch_b.pk,batch_b.task_id,barrier),
                  pool.submit(self.worker,first.pk,batch_a.pk,batch_a.task_id,barrier)]
            for job in jobs:job.result(timeout=900)
        elapsed=time.perf_counter()-started;self.metric('concurrent_workers',elapsed,accounts=2,entries=2*COUNT)
        self.assertLess(elapsed,900)
        self.verify(first,original_a,records_a,batch_a);self.verify(second,original_b,records_b,batch_b)
        self.assertEqual(self.notify.call_count,2)
        self.worker(first.pk,batch_a.pk,batch_a.task_id)
        self.assertEqual(Flight.objects.filter(user=first).count(),COUNT+1)
        self.assertEqual(self.notify.call_count,2)

    def test_near_20mb_wide_export_maps_and_imports_10000_entries(self):
        from csv_app.mapping import read_source
        from csv_app.tests.test_mapping import choices
        user,original=self.account('capacity-wide')
        _,records=payload()
        extra=[f'External custom column {index}' for index in range(16)]
        wide=content([values+['B'*100]*16 for values in records],HEADERS+OPTIONAL_HEADERS+extra)
        self.assertGreater(len(wide.encode()),18*1024*1024)
        self.assertLess(len(wide.encode()),PROPOSED_BYTES)
        client=Client();client.force_login(user)
        started=time.perf_counter()
        response=client.post(reverse('csv_inspect'),{'file':SimpleUploadedFile('wide.csv',wide.encode())})
        self.metric('wide_upload',time.perf_counter()-started,bytes=len(wide.encode()))
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.context['mapping_choice'])
        self.assertLess(time.perf_counter()-started,20)
        batch=response.context['batch']
        table=read_source(wide,user=user)
        fields=choices(table);fields.update(time_units='hours',ignore_unused='on')
        started=time.perf_counter()
        response=client.post(reverse('csv_mapping',args=[batch.pk]),fields)
        self.metric('wide_mapping_preview',time.perf_counter()-started)
        self.assertTrue(response.context['preview_ready'],str(response.context.get('row_form') or response.context.get('mapping_form')))
        self.assertLess(time.perf_counter()-started,20)
        self.assertEqual(len(response.context['file']),50)
        self.assertEqual(response.context['row_count'],COUNT)
        with patch('csv_app.submission.import_csv_batch.apply_async'):
            response=client.post(reverse('csv_upload'),{'batch_id':batch.pk})
        self.assertEqual(response.status_code,202,response.content[:500])
        batch.refresh_from_db()
        started=time.perf_counter();self.worker(user.pk,batch.pk,batch.task_id)
        self.metric('wide_worker',time.perf_counter()-started)
        self.verify(user,original,records,batch)

    def test_database_interruption_at_5000_then_retry_imports_once(self):
        user,original=self.account('capacity-retry');text,records=payload()
        batch=self.upload(user,text)
        paused,release=Event(),Event();worker_pid=[];attempted=[];save=Flight.save
        def paused_save(instance,*args,**kwargs):
            creating=instance._state.adding
            result=save(instance,*args,**kwargs)
            if creating:
                attempted.append(instance.pk)
                if len(attempted)%1000==0:print(f'CAPACITY interruption progress {len(attempted)}',flush=True)
                if len(attempted)==5000:
                    paused.set()
                    if not release.wait(timeout=30):raise RuntimeError('Interruption test was not released')
            return result
        def worker():
            close_old_connections()
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_backend_pid()');worker_pid.append(cursor.fetchone()[0])
            import_csv_batch.push_request(id=batch.task_id)
            try:import_csv_batch.run(user.pk,str(batch.pk))
            finally:
                import_csv_batch.pop_request()
                connection.close()
        started=time.perf_counter()
        with patch.object(Flight,'save',autospec=True,side_effect=paused_save), self.assertLogs('django.csv_app',level='ERROR'):
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending=pool.submit(worker)
                try:
                    deadline=time.monotonic()+600
                    while not paused.wait(timeout=1) and not pending.done() and time.monotonic()<deadline:
                        pass
                    if pending.done():pending.result()
                    self.assertTrue(paused.is_set(),'Worker did not reach entry 5000')
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT datname FROM pg_stat_activity WHERE pid=%s',[worker_pid[0]])
                        self.assertEqual(cursor.fetchone()[0],connection.settings_dict['NAME'])
                        cursor.execute('SELECT pg_terminate_backend(%s)',[worker_pid[0]])
                        self.assertTrue(cursor.fetchone()[0])
                finally:release.set()
                with self.assertRaises(DatabaseError):pending.result(timeout=30)
        self.metric('interrupted_rollback',time.perf_counter()-started,attempted=len(attempted))
        self.assertEqual(Flight.objects.filter(user=user).count(),1)
        self.assertEqual(Total.objects.get(user=user,total='All').total_time,Decimal('.5'))
        self.assertFalse(Approach.objects.filter(flight_object__user=user).exists())
        batch.refresh_from_db()
        if batch.status==CSVImportBatch.Status.PROCESSING:
            CSVImportBatch.objects.filter(pk=batch.pk).update(updated_at=timezone.now()-timedelta(minutes=21))
            call_command('cleanup_csv_previews',stdout=StringIO());batch.refresh_from_db()
        self.assertEqual(batch.status,CSVImportBatch.Status.FAILED)
        retry=self.upload(user,text)
        started=time.perf_counter();self.worker(user.pk,retry.pk,retry.task_id)
        self.metric('retry_worker',time.perf_counter()-started)
        self.verify(user,original,records,retry)
        self.worker(user.pk,batch.pk,batch.task_id);self.worker(user.pk,retry.pk,retry.task_id)
        self.assertEqual(Flight.objects.filter(user=user).count(),COUNT+1)
        self.assertEqual(self.notify.call_count,1)
