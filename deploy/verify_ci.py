"""Require the latest push-CI result for the exact master commit before deployment."""
import json
import os
import re
import sys
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


class VerificationError(Exception):
    pass


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_api(path):
    token = os.environ.get('GH_TOKEN')
    if not token:
        raise VerificationError('The read-only GitHub Actions token is missing.')
    request = Request('https://api.github.com/' + path, headers={
        'Authorization': 'Bearer ' + token,
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'Direct2Logbook-Deployment-Verification',
    })
    try:
        with build_opener(NoRedirects()).open(request, timeout=15) as response:
            return json.loads(response.read(2_000_000))
    except Exception:
        raise VerificationError('Could not verify CI through GitHub. Deployment is blocked; retry after checking Actions/API availability.') from None


def verify(repository, revision, request=read_api):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository or ''):
        raise VerificationError('Expected a GitHub owner/repository.')
    if not re.fullmatch(r'[0-9a-f]{40}', revision or ''):
        raise VerificationError('Expected an exact 40-character deployment commit SHA.')
    query = urlencode({'branch': 'master', 'event': 'push', 'head_sha': revision, 'per_page': 1})
    payload = request(f'repos/{repository}/actions/workflows/ci.yml/runs?{query}')
    runs = payload.get('workflow_runs') if isinstance(payload, dict) else None
    if not isinstance(runs, list) or not runs:
        raise VerificationError('No CI result for this exact master commit. Wait for master CI, then run deployment again.')
    run = runs[0]  # Latest run, not an older success hidden behind a failed/pending rerun.
    head_repository = run.get('head_repository') if isinstance(run, dict) else None
    if not isinstance(run, dict) or not isinstance(head_repository, dict) or (
        run.get('head_sha') != revision or run.get('head_branch') != 'master'
        or run.get('event') != 'push' or run.get('path') != '.github/workflows/ci.yml'
        or str(head_repository.get('full_name', '')).casefold() != repository.casefold()
    ):
        raise VerificationError('CI result does not belong to the expected workflow, repository, branch and exact commit.')
    if run.get('status') != 'completed' or run.get('conclusion') != 'success':
        raise VerificationError('Latest master CI has not completed successfully. Check Actions, then run deployment again.')
    run_id, attempt = run.get('id'), run.get('run_attempt')
    if type(run_id) is not int or run_id <= 0 or type(attempt) is not int or attempt <= 0:
        raise VerificationError('GitHub returned an invalid CI run or attempt.')
    payload = request(f'repos/{repository}/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100')
    jobs = payload.get('jobs') if isinstance(payload, dict) else None
    if not isinstance(jobs, list) or type(payload.get('total_count')) is not int or payload['total_count'] != len(jobs):
        raise VerificationError('GitHub returned an incomplete CI job list; deployment is blocked.')
    tests = [job for job in jobs if isinstance(job, dict) and job.get('name') == 'Django and JavaScript']
    if len(tests) != 1 or (
        tests[0].get('status') != 'completed' or tests[0].get('conclusion') != 'success'
        or tests[0].get('run_id') != run_id or tests[0].get('head_sha') != revision
    ):
        raise VerificationError('The required Django and JavaScript job did not pass for this CI attempt and commit.')
    return run_id


def main():
    try:
        if os.environ.get('GITHUB_REF') != 'refs/heads/master':
            raise VerificationError('Production deployments must run from master.')
        repository = os.environ.get('GITHUB_REPOSITORY', '')
        revision = os.environ.get('GITHUB_SHA', '')
        run_id = verify(repository, revision)
        print(f'CI verified for {revision}: https://github.com/{repository}/actions/runs/{run_id}')
    except VerificationError as error:
        print(f'Deployment blocked: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
