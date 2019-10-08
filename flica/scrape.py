import requests
from lxml import html
import pandas
from bs4 import BeautifulSoup

with requests.Session() as session:

    payload = {
        'UserId': 'nks069069'
        'Password’: ‘1q2w3e'
        }

    home_url = 'https://spirit.flica.net/ui/public/login/index.html'
    login_url = 'https://www.flica.net/public/flicaLogon.cgi'
    payload = {'UserId': 'nks069069', 'Password': '1q2w3e'}

    login_page = session.post(login_url, data=payload)

    login_tree = html.fromstring(login_page.content)
    page_url = str(login_tree.xpath('//script/text()')[0])
    page_url = page_url.strip().strip('top.location=').strip("'")

    content_page = session.get(page_url)

    schedule_url = 'https://spirit.flica.net/online/leftmenu.cgi?whosepage=Crewmember'
    schedule_page = session.get(schedule_url)

    soup = BeautifulSoup(schedule_page.content, 'lxml')

    print(content_page.text, file=open("soup.txt", "a"))
