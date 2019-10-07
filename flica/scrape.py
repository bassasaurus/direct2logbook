import requests
from lxml import html


with requests.Session() as session:

    payload = {
        'UserId': 'nks069069'
        'Password’: ‘1q2w3e'
        }

    home_url = 'https://spirit.flica.net/ui/public/login/index.html'
    login_url = 'https://www.flica.net/public/flicaLogon.cgi'
    payload = {'UserId': 'nks069069', 'Password': '1q2w3e'}

    login_page = session.post(login_url, data=payload)

    tree = html.fromstring(login_page.content)
    page_url = str(tree.xpath('//script/text()')[0])

    page_url = page_url.strip().strip('top.location=').strip("'")

    content_page = session.get(page_url)

    print(content_page.text)
