# Glider launch method

Actual glider flights require one launch method: Aerotow, Ground Launch, or
Self-launch. This applies to new flights and every update; there is no historical
blank exception. The local database audit on November 24, 2026 found zero glider
aircraft and zero actual glider flights.

Self-launch is offered and accepted only when the selected aircraft is marked
self-launch capable. The capability describes the aircraft; the launch method
describes the particular flight. No method is inferred from capability.

Web and mobile show the field after aircraft selection. Changing to a non-glider
or a simulator clears the launch selection. This feature does not introduce
special glider simulator support or calculate simulator credit.

Django validates the field in the web form, model validation (including admin and
CSV import), and mobile API. A database check restricts stored method codes;
category/capability checks use the related aircraft through application validation.
Blank remains the storage value for non-glider and simulator records. Existing
non-glider records and queued revision fingerprints remain unchanged.

Mobile drafts may remain incomplete; a flight cannot become a valid submission
until its launch method is chosen. The method is stored with the offline flight,
sent in its sync operation, included in conflict comparisons, and displayed on
flight detail. No launch count or training-credit summary is added in this step.

## CSV round trips

Exports append an optional `launch method` column after the existing device
columns. Imports retain support for the older 18- and 19-column files and device
extensions, and accept `launch method` after the standard 19 columns. Methods may
use AEROTOW / GROUND / SELF codes or the displayed labels. Actual glider imports
require a method and validate self-launch capability before committing the batch.
No existing non-glider data is reclassified or assigned a launch method.
