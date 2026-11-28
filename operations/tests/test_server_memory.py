from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.admin.models import LogEntry
from django.template.loader import render_to_string
from django.test import SimpleTestCase

from operations.server_memory import memory_snapshot


class ServerMemoryTests(SimpleTestCase):
    def test_linux_totals_and_grouped_process_memory(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'meminfo').write_text(
                'MemTotal: 1048576 kB\nMemAvailable: 524288 kB\n'
                'SwapTotal: 1048576 kB\nSwapFree: 786432 kB\n'
            )
            for pid, name, rss, swap in (
                ('1', 'gunicorn', 102400, 2048),
                ('2', 'gunicorn', 51200, 1024),
                ('3', 'celery', 204800, 0),
                ('4', 'unrelated', 1024, 0),
            ):
                process = root / pid
                process.mkdir()
                (process / 'status').write_text(
                    f'Name:\t{name}\nVmRSS:\t{rss} kB\nVmSwap:\t{swap} kB\n'
                )
            snapshot = memory_snapshot(root)
            self.assertEqual(snapshot['total'], 1024)
            self.assertEqual(snapshot['used'], 512)
            self.assertEqual(snapshot['free'], 512)
            self.assertEqual(snapshot['swap_used'], 256)
            self.assertEqual(snapshot['processes'][0], {
                'name': 'Django / Gunicorn', 'count': 2,
                'rss': 150, 'swap': 3, 'swap_known': True,
            })
            self.assertEqual(len(snapshot['processes']), 2)

    def test_missing_proc_is_unavailable(self):
        with TemporaryDirectory() as directory:
            self.assertEqual(memory_snapshot(Path(directory)), {'available': False})

    def test_restricted_swap_is_not_reported_as_zero(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'meminfo').write_text(
                'MemTotal: 1024 kB\nMemAvailable: 512 kB\n'
                'SwapTotal: 0 kB\nSwapFree: 0 kB\n'
            )
            (root / '1').mkdir()
            (root / '1' / 'status').write_text('Name: nginx\nVmRSS: 64 kB\n')
            self.assertIsNone(memory_snapshot(root)['processes'][0]['swap'])

    @patch('operations.templatetags.server_memory.memory_snapshot')
    def test_panel_does_not_collect_or_render_for_nonstaff(self, collect):
        for staff, active in ((False, True), (True, False)):
            request = SimpleNamespace(user=SimpleNamespace(is_staff=staff, is_active=active, pk=1))
            html = render_to_string('admin/index.html', {'request': request, 'user': request.user, 'app_list': [], 'log_entries': LogEntry.objects.none()})
            self.assertNotIn('SERVER MEMORY', html)
        collect.assert_not_called()

    @patch('operations.templatetags.server_memory.memory_snapshot', return_value={'available': False})
    def test_staff_index_preserves_dashboard_and_explains_unavailable_metrics(self, collect):
        user = SimpleNamespace(is_staff=True, is_active=True, pk=1)
        request = SimpleNamespace(user=user)
        html = render_to_string('admin/index.html', {
            'request': request, 'user': request.user, 'app_list': [], 'log_entries': LogEntry.objects.none(),
        })
        self.assertIn('SERVER MEMORY', html)
        self.assertIn('Linux /proc access', html)
        collect.assert_called_once_with()
