"""Read-only HTTPS smoke checks; run with Python's standard library only."""
import argparse
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.inputs = set()
        self.assets = set()
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input':
            self.inputs.add(attrs.get('name'))
        if tag == 'script' and attrs.get('src'):
            self.assets.add(attrs['src'])
        if tag == 'link' and 'stylesheet' in attrs.get('rel', '').split():
            if attrs.get('href'):
                self.assets.add(attrs['href'])


def fetch(url):
    request = Request(url, headers={'User-Agent': 'Direct2Logbook-Smoke/1.0'})
    with urlopen(request, timeout=15) as response:
        return response.status, response.geturl(), response.headers.get_content_type(), response.read(2_000_000)


def check(base, get=fetch, report=print):
    origin = urlsplit(base)
    if origin.scheme != 'https' or not origin.netloc or origin.path not in ('', '/'):
        raise ValueError('Expected an HTTPS site origin without a path.')
    assets = set()
    for path, fields in (
        ('/accounts/login/', {'login', 'password', 'csrfmiddlewaretoken'}),
        ('/accounts/signup/', {'email', 'password1', 'csrfmiddlewaretoken', 'g-recaptcha-response'}),
    ):
        status, final, content_type, body = get(urljoin(base, path))
        if status != 200 or final != urljoin(base, path) or content_type != 'text/html':
            raise RuntimeError(f'{path}: expected the HTML page without a redirect')
        page = Page(body.decode('utf-8'))
        # Google creates its response input in the browser, so inspect its server-rendered widget.
        expected = fields - {'g-recaptcha-response'}
        if not expected <= page.inputs or ('g-recaptcha-response' in fields and b'g-recaptcha' not in body):
            raise RuntimeError(f'{path}: expected form or reCAPTCHA is missing')
        local_assets = {urljoin(base, asset) for asset in page.assets
                        if urlsplit(urljoin(base, asset)).netloc == origin.netloc
                        and urlsplit(urljoin(base, asset)).scheme == 'https'}
        if not local_assets:
            raise RuntimeError(f'{path}: no local stylesheets or scripts found')
        assets.update(local_assets)
        report(f'PASS {path}: form present')
    for asset in sorted(assets):
        status, final, content_type, body = get(asset)
        if status != 200 or final != asset or not body or content_type not in (
            'text/css', 'text/javascript', 'application/javascript', 'application/x-javascript',
        ):
            raise RuntimeError(f'{urlsplit(asset).path}: static asset missing or unexpected response')
        report(f'PASS {urlsplit(asset).path}: static asset served')
    for path in ('/home/', '/csv/upload/'):
        status, final, content_type, body = get(urljoin(base, path))
        target = urlsplit(final)
        if status != 200 or (target.scheme, target.netloc, target.path) != (
            'https', origin.netloc, '/accounts/login/',
        ):
            raise RuntimeError(f'{path}: anonymous request did not reach login')
        report(f'PASS {path}: anonymous access redirected to login')
    report('Production smoke checks passed (read-only; no accounts or jobs created).')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='https://direct2logbook.com')
    args = parser.parse_args()
    try:
        check(args.base_url)
    except Exception as error:
        parser.exit(1, f'Smoke check failed: {error}\n')
