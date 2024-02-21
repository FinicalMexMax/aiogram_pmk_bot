import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent


ua = UserAgent().random

url = 'https://pmkedu.pro/schedules/fulltime/all/'
headers = {
    'user-agent': ua,
    'accept': 'ext/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Content-Type': 'text/html; charset=UTF-8'
}

responce = requests.get(url=url, headers=headers)

soup = BeautifulSoup(responce.text, 'lxml')
name = soup.find('div', class_='pmk_name').text.strip()

print(name)