from unittest.mock import patch

import sentry_sdk
from sentry_sdk.transport import Transport
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from celery import Celery
from django.test import SimpleTestCase, override_settings
from logbook.monitoring import configure_sentry


class MemoryTransport(Transport):
    def __init__(self):
        super().__init__()
        self.events = []

    def capture_envelope(self, envelope):
        for item in envelope.items:
            if item.type == 'event':
                self.events.append(item.payload.json)


class SentryConfigurationTests(SimpleTestCase):
    def test_debug_and_empty_dsn_do_not_initialize_reporting(self):
        with patch('logbook.monitoring.sentry_sdk.init') as initialize:
            configure_sentry(debug=True, dsn='https://key@example.com/1', environment='development')
            configure_sentry(debug=False, dsn='', environment='production')
        initialize.assert_not_called()

    def test_production_options_preserve_error_reporting_without_tracing(self):
        with patch('logbook.monitoring.sentry_sdk.init') as initialize:
            configure_sentry(debug=False, dsn='https://key@example.com/1', environment='staging')
        options = initialize.call_args.kwargs
        self.assertEqual(options['environment'], 'staging')
        self.assertEqual({item.identifier for item in options['integrations']}, {'django', 'celery'})
        self.assertTrue(options['send_default_pii'])
        self.assertEqual(options['traces_sample_rate'], 0)
        self.assertEqual(options['profiles_sample_rate'], 0)
        self.assertFalse(options['enable_logs'])

    @override_settings(DEBUG=False, ALLOWED_HOSTS=['testserver'])
    def test_django_exception_is_captured_by_installed_sdk_without_network(self):
        transport = MemoryTransport()
        with sentry_sdk.init(dsn='https://key@example.com/1', transport=transport,
                             environment='sdk-upgrade-test', auto_enabling_integrations=False,
                             integrations=[DjangoIntegration()],
                             traces_sample_rate=0):
            with self.assertRaises(ZeroDivisionError):
                self.client.get('/sentry-debug/')
            sentry_sdk.flush()
        self.assertTrue(any(event.get('exception', {}).get('values', [{}])[-1].get('type') == 'ZeroDivisionError'
                            for event in transport.events))
        self.assertTrue(all(event['environment'] == 'sdk-upgrade-test' for event in transport.events))

    def test_celery_failure_is_captured_without_broker_or_network(self):
        transport = MemoryTransport()
        app = Celery('sentry-upgrade-test', broker='memory://', set_as_current=False)
        self.addCleanup(app.close)

        @app.task
        def failing_task():
            raise RuntimeError('Sentry SDK local Celery capture check')

        with sentry_sdk.init(dsn='https://key@example.com/1', transport=transport,
                             environment='sdk-upgrade-test', auto_enabling_integrations=False,
                             integrations=[CeleryIntegration()], traces_sample_rate=0):
            result = failing_task.apply(throw=False)
            self.assertTrue(result.failed())
            sentry_sdk.flush()
        self.assertTrue(any(event.get('exception', {}).get('values', [{}])[-1].get('type') == 'RuntimeError'
                            for event in transport.events))
