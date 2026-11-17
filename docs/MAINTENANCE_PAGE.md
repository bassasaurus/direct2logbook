# Maintenance page

Nginx serves a standalone page when the Django upstream is unavailable (502,
503, or 504). It returns HTTP 503 with Retry-After and no-store headers. The
page does not depend on Django, collected static files, JavaScript, or a CDN.
It also covers unexpected upstream downtime, so its wording does not promise
that every outage is an update. Normal Django validation and error pages are
unchanged. Failed form submissions are never automatically replayed.

## One-time server setup

After these files are present in /home/blakepowell/app:

```sh
sudo install -d -m 755 /var/www/direct2logbook-maintenance
sudo install -m 644 deploy/maintenance.html /var/www/direct2logbook-maintenance/maintenance.html
sudo install -m 644 deploy/nginx-maintenance.conf /etc/nginx/snippets/direct2logbook-maintenance.conf
```

Add the following inside the existing HTTPS `server {}` block for
Direct2Logbook, at the same level as `location /`, using sudoedit on that site's
Nginx configuration:

```nginx
include /etc/nginx/snippets/direct2logbook-maintenance.conf;
```

Check for existing error_page directives for these status codes in the server
and proxy location. Replace conflicting mappings rather than adding duplicates;
location-level mappings can override the server mapping.

```sh
sudo nginx -t && sudo systemctl reload nginx
```

No additional deploy privileges or deployment-script changes are required.
The current workflow stops Django after its verified backup and restarts it
before its HTTPS health check. During that downtime Nginx displays this page;
once Django answers normally, the site works normally again. A deployment that
fails with services stopped continues to display this page until repaired.

The HTML and snippet are installed copies: future edits to either file must be
installed again. Removing the include and reloading Nginx reverses this setup.

## Verification

During the next planned deployment, request a page while Django is stopped:
confirm the maintenance page, status 503, Retry-After: 60 and Cache-Control:
no-store. When deployment finishes, confirm the login page returns 200. Do not
stop a healthy production service solely to preview the page. Open the HTML
file locally to review its appearance first.
