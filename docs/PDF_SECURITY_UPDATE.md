# PDF rendering security update

ReportLab is upgraded from 3.6.12 to 5.1.0, compatible with Python 3.10 and the
existing Pillow/charset-normalizer requirements. The pinned release has no known
advisories in the current pip-audit/PyPI result. This does not resolve the separate
Pillow advisories or other dependency findings in the overall audit.

The PDF cover now XML-escapes user first/last names before interpolating them into
ReportLab Paragraph markup. Tags and entities in names display literally. Cover
leading is 60 points for the existing 50-point font so wrapped names do not overlap.
Other Paragraph calls use application-controlled static strings/date formatting;
plain text table cells and Canvas drawString do not parse Paragraph markup.

Tests generate real PDFs using synthetic flight rows, malformed names, entities,
and a PNG signature, without database, storage, email, or cloud access. Visual
checks covered normal cover, summary/logbook pages, and literal markup cover.
The original synthetic fixture exposed existing summary clipping. The subsequent
single-table width fix is described in PDF_SUMMARY_WIDTH.md. Long cover names
wrap with readable line spacing after this change.

## Deployment

After merging and pulling the branch on production, install dependencies BEFORE
restarting both Django and Celery (the worker renders the PDFs):

```sh
cd /home/blakepowell/app
/home/blakepowell/venv/bin/python -m pip install -r requirements.txt
/home/blakepowell/venv/bin/python -m pip check
/home/blakepowell/venv/bin/python -c "import reportlab; print(reportlab.Version)"
sudo supervisorctl restart logbook celery
sudo supervisorctl status logbook celery
```

Require ReportLab 5.1.0. No migrations or collectstatic needed. Then request a real
logbook through the normal UI and check email delivery, cover, populated summaries,
rows, pagination, totals and signature. Local synthetic rendering does not prove
production email/storage/native dependencies. The remaining audit upgrades should
be handled separately with their own regression coverage.

Reference: https://github.com/advisories/GHSA-9q9m-c65c-37pq
