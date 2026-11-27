from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from csv_app.validation import MAX_BYTES, MAX_ROWS, CSVValidationError, parse_csv
from csv_app.formats import prepare_csv
from csv_app.mapping import read_source
from csv_app.rows import stage_rows
from csv_app.forms import InspectForm
from csv_app.tests.test_atomic_import import content, row


class CSVLimitTests(SimpleTestCase):
    def test_all_ingestion_paths_reject_rows_above_the_shared_ceiling(self):
        text=content([row()]*10_001)
        for entry in (parse_csv,prepare_csv,read_source,stage_rows):
            with self.subTest(entry=entry.__name__),self.assertRaisesRegex(CSVValidationError,'10,000'):
                entry(text)

    def test_exact_byte_limit_passes_upload_guard_and_one_more_byte_fails(self):
        for size,valid in ((20*1024*1024,True),(20*1024*1024+1,False)):
            form=InspectForm(files={'file':SimpleUploadedFile('limit.csv',b'x'*size)})
            self.assertEqual(form.is_valid(),valid)
            if not valid:self.assertIn(f'{MAX_BYTES//(1024*1024)} MB',str(form.errors))

    def test_ten_thousand_entries_are_accepted(self):
        parsed,preview=parse_csv(content([row()]*10_000))
        self.assertEqual(len(parsed),10_000)
        self.assertEqual(len(preview),10_000)
