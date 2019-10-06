# import requests
#
# # from lmxl import html
# import datetime
#
# url = 'https://spirit.flica.net'
#
# date = datetime.datetime.now().strftime('%Y%m%d%H%m%S')
#
# page = 'https://spirit.flica.net/online/mainmenu.cgi'
# # page = 'https://spirit.flica.net/online/mainmenu.cgi?nocache={}'.format(date)
#
# payload = {
#     'UserId': 'nks69069'
#     'Password’: ‘1q2w3e'
#     }
#
# with requests.Session() as session:
#     post = session.post(url, data=payload)
#     r = session.get(page)
#     print(r.text)

from selenium import webdriver

driver = webdriver.Firefox()
driver.get("https://spirit.flica.net/ui/public/login/index.html")

user_id = driver.find_element_by_name("UserId")
user_id.send_keys("nks069069")

password = driver.find_element_by_name("Password")
password.send_keys("1q2w3e")

driver.find_element_by_class_name("spark-btn").click()

session_cookie = driver.get_cookie('FLiCASession')
print(session_cookie)
# driver.close()
