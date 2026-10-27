# Single-table summary width

Category/class, aircraft and miscellaneous summaries now shrink uniformly to the
available PDF frame width only when their natural width exceeds it. Each summary
remains one table with every column on the same row. Narrow tables are not enlarged.
Scaling includes fonts and padding, so long labels/large totals can make the result
smaller. Tall category/aircraft tables still split vertically and repeat headers.

A controlled comparison of identical populated tables under ReportLab 3.6.12 and
5.1.0 measured the same natural width (1183.29pt vs 736.8pt frame width). This did
not establish an SDK regression. Explicit width scaling now avoids relying on
implicit layout behavior.

Tests cover frame width, unchanged row/column data, narrow tables, multi-page
splitting with repeated headers, and synthetic populated logbook generation.
The generated summary preview was rendered and visually checked.

After merge/deployment, restart Celery and request a logbook normally to verify
real summaries, pagination, signatures and email delivery. There are no dependency
changes, migrations or static assets in this layout fix. PDF security fixes remain.
