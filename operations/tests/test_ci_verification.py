import copy
from io import StringIO
import os
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.test import SimpleTestCase

from deploy.verify_ci import VerificationError, main, read_api, verify


REPOSITORY = 'example/logbook'
SHA = 'a' * 40


class CIVerificationTests(SimpleTestCase):
    def setUp(self):
        self.run = dict(id=123, run_attempt=2, head_sha=SHA, head_branch='master',
                        event='push', path='.github/workflows/ci.yml', status='completed',
                        conclusion='success', head_repository={'full_name': REPOSITORY})
        self.job = dict(name='Django and JavaScript', status='completed', conclusion='success',
                        head_sha=SHA, run_id=123)
        self.paths = []

    def request(self, path):
        self.paths.append(path)
        if 'workflows/ci.yml/runs?' in path:
            return {'workflow_runs': [self.run]}
        return {'total_count': 1, 'jobs': [self.job]}

    def test_exact_master_push_and_current_attempt_are_required(self):
        self.assertEqual(verify(REPOSITORY, SHA, self.request), 123)
        query = parse_qs(urlsplit(self.paths[0]).query)
        self.assertEqual(query, {'head_sha': [SHA], 'event': ['push'], 'branch': ['master'], 'per_page': ['1']})
        self.assertIn('/runs/123/attempts/2/jobs?', self.paths[1])

    def test_pending_and_unsuccessful_runs_block_before_job_lookup(self):
        for status, conclusion in [('queued', None), ('in_progress', None), ('waiting', None),
                                   ('completed', 'failure'), ('completed', 'cancelled'),
                                   ('completed', 'timed_out'), ('completed', 'skipped'),
                                   ('completed', 'neutral')]:
            with self.subTest(status=status, conclusion=conclusion):
                self.run.update(status=status, conclusion=conclusion)
                self.paths = []
                with self.assertRaises(VerificationError):
                    verify(REPOSITORY, SHA, self.request)
                self.assertEqual(len(self.paths), 1)

    def test_missing_or_malformed_run_lists_block(self):
        for payload in ({}, {'workflow_runs': []}, {'workflow_runs': None},
                        {'workflow_runs': [None]}, []):
            with self.subTest(payload=payload), self.assertRaises(VerificationError):
                verify(REPOSITORY, SHA, lambda path: payload)

    def test_wrong_commit_branch_event_workflow_and_repository_block(self):
        for changes in ({'head_sha': 'b' * 40}, {'head_branch': 'feature'},
                        {'event': 'pull_request'}, {'path': '.github/workflows/other.yml'},
                        {'head_repository': {'full_name': 'other/fork'}}, {'head_repository': None},
                        {'id': None}, {'run_attempt': 0}):
            with self.subTest(changes=changes):
                original = copy.deepcopy(self.run)
                self.run.update(changes)
                with self.assertRaises(VerificationError):
                    verify(REPOSITORY, SHA, self.request)
                self.run = original

    def test_failed_skipped_pending_or_wrong_job_blocks(self):
        for changes in ({'conclusion': 'failure'}, {'conclusion': 'skipped'},
                        {'status': 'in_progress'}, {'head_sha': 'b' * 40},
                        {'run_id': 456}, {'name': 'Unrelated job'}):
            with self.subTest(changes=changes):
                original = self.job.copy()
                self.job.update(changes)
                with self.assertRaises(VerificationError):
                    verify(REPOSITORY, SHA, self.request)
                self.job = original

    def test_latest_failed_run_does_not_fall_back_to_older_success(self):
        failed = dict(self.run, id=124, conclusion='failure')
        with self.assertRaises(VerificationError):
            verify(REPOSITORY, SHA, lambda path: {'workflow_runs': [failed, self.run]})

    def test_missing_duplicate_and_incomplete_job_lists_block(self):
        for jobs in ({'total_count': 0, 'jobs': []}, {'total_count': 2, 'jobs': [self.job, self.job]},
                     {'total_count': 2, 'jobs': [self.job]}, {'total_count': 1, 'jobs': None}):
            with self.subTest(jobs=jobs):
                def request(path):
                    return {'workflow_runs': [self.run]} if 'workflows/' in path else jobs
                with self.assertRaises(VerificationError):
                    verify(REPOSITORY, SHA, request)

    def test_invalid_input_never_contacts_github(self):
        for repository, revision in [('bad repository', SHA), (REPOSITORY, 'master'), (REPOSITORY, 'a' * 39)]:
            with self.subTest(repository=repository, revision=revision), self.assertRaises(VerificationError):
                verify(repository, revision, self.request)
        self.assertEqual(self.paths, [])

    @patch.dict(os.environ, {'GH_TOKEN': ''})
    def test_missing_token_blocks(self):
        with self.assertRaises(VerificationError):
            read_api('repos/example/logbook/actions/runs')

    @patch.dict(os.environ, {'GH_TOKEN': 'test-only-secret'})
    @patch('deploy.verify_ci.build_opener')
    def test_api_errors_are_sanitized(self, opener):
        opener.return_value.open.side_effect = RuntimeError('test-only-secret response contents')
        with self.assertRaises(VerificationError) as raised:
            read_api('repos/example/logbook/actions/runs')
        self.assertNotIn('test-only-secret', str(raised.exception))
        self.assertNotIn('response contents', str(raised.exception))

    @patch.dict(os.environ, {'GITHUB_REF': 'refs/heads/feature'})
    @patch('deploy.verify_ci.verify')
    def test_cli_rejects_other_branches_without_verifying(self, gate):
        with patch('sys.stderr', new_callable=StringIO):
            self.assertEqual(main(), 1)
        gate.assert_not_called()

    @patch.dict(os.environ, {'GITHUB_REF': 'refs/heads/master', 'GITHUB_REPOSITORY': REPOSITORY, 'GITHUB_SHA': SHA})
    @patch('deploy.verify_ci.verify')
    def test_cli_success_reports_verified_run(self, gate):
        gate.return_value = 123
        with patch('sys.stdout', new_callable=StringIO) as output:
            self.assertEqual(main(), 0)
        gate.assert_called_once_with(REPOSITORY, SHA)
        self.assertIn('/actions/runs/123', output.getvalue())
