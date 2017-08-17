import twitter
import configparser
import os, sys
import datetime
from dateutil.relativedelta import relativedelta
import requests
import scrapy
import urllib.parse
from scrapy.crawler import CrawlerProcess
import bs4 as bs
import xml.etree.ElementTree as ET
import humanize
from blessings import Terminal

config = configparser.ConfigParser()
config.read(os.getenv("HOME") + '/.config/sachajob.ini')

today = datetime.datetime.today()
matches = []
areas = ["nantes", "rennes"]
words = ["devops", "sysops", "linux", "administrateur systèmes"]

# --- Linuxjobs.fr ----
linux_jobs_rss = {
    "Nantes": "https://www.linuxjobs.fr/cities/14/nantes/rss",
    "Rennes": "https://www.linuxjobs.fr/cities/17/rennes/rss"
}

print("Crawling Linuxjobs.fr…")
for city, rss in linux_jobs_rss.items():
    r = requests.get(rss)
    tree = ET.fromstring(r.text)
    items = tree.iter('item')
    for item in items:
        date = datetime.datetime.strptime(
            item.find('pubDate').text, "%a, %d %b %Y %H:%M:%S %z").replace(
                tzinfo=None)
        if (today - date) < datetime.timedelta(days=8):
            matches.append({
                "date": date,
                "source": "Linuxjobs.fr",
                "word": '',
                "area": city.title(),
                "user": '',
                "text": item.find('title').text,
                "url": item.find('link').text,
            })

# --- Ouest France Emploi ---
print("Crawling Ouest France Emploi…")
query_url = "https://www.ouestfrance-emploi.com"
for area in areas:
    for word in words:
        query = f"/recherche-emploi/?q={area}+{'+'.join(word.split(' '))}"
        r = requests.get(query_url + query)
        soup = bs.BeautifulSoup(r.text, "html.parser")

        none_result = soup.find('h1').find('b')
        if none_result:
            continue

        offers = soup.find_all("div", {"class": 'offer-info'})
        for o in offers:
            title = o.find('meta', {'itemprop': 'title'})['content']
            date_raw = o.find('meta', {'itemprop': 'datePosted'})['content']
            date = datetime.datetime.strptime(date_raw, "%Y-%m-%d")
            if (today - date) < datetime.timedelta(days=8):
                company = o.find('div', {'class': 'libEntreprise'}).text
                url = query_url + o.find('meta', {'itemprop': 'url'
                                                  })['content']
                matches.append({
                    "date": date,
                    "source": "Ouest France Emploi",
                    "word": word,
                    "area": area.title(),
                    "user": company,
                    "text": title,
                    "url": url,
                })
# --- Les Jeudis ---
print("Crawling Les Jeudis…")
for area in areas:
    for word in words:
        search_url = f"https://www.lesjeudis.com/recherche?utf8=%E2%9C%93&q={'+'.join(word.split(' '))}&loc={area}"
        r = requests.get(search_url)
        soup = bs.BeautifulSoup(r.text, "html.parser")
        offers = soup.find_all("div",
                               {"itemtype": "http://schema.org/JobPosting"})
        for o in offers:
            title = o.find('a', {'itemprop': 'title'}).text.strip()
            url = "https://www.lesjeudis.com" + o.find(
                'a', {'itemprop': 'title'})['href']
            company = o.find('span', {'itemprop': 'hiringOrganization'}).a.text
            date_since_raw = o.find('div', {'itemprop':
                                            'datePosted'}).text.strip()
            date_since = date_since_raw.split('postée il y a ')[1].split(' ')
            if date_since[1] == 'jour' or date_since[1] == 'jours':
                date = today - relativedelta(days=+int(date_since[0]))
            elif date_since[1] == 'heure' or date_since[1] == 'heures':
                date = today - relativedelta(hours=+int(date_since[0]))
            elif date_since[1] == 'mois':
                date = today - relativedelta(months=+int(date_since[0]))
            if (today - date) < datetime.timedelta(days=8):
                matches.append({
                    "date": date,
                    "source": "Les Jeudis",
                    "word": word,
                    "area": area.title(),
                    "user": company,
                    "text": title,
                    "url": url,
                })

# --- APEC ----
print("Crawling APEC…")
SPLASH_URL = 'http://localhost:8050'


class ApecSpider(scrapy.Spider):
    custom_settings = {
        'LOG_ENABLED': False,
        'DOWNLOADER_MIDDLEWARES': {
            'scrapy_splash.SplashCookiesMiddleware':
            723,
            'scrapy_splash.SplashMiddleware':
            725,
            'scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware':
            810,
        },
        'SPIDER_MIDDLEWARES': {
            'scrapy_splash.SplashDeduplicateArgsMiddleware': 100,
        },
        'DUPEFILTER_CLASS': 'scrapy_splash.SplashAwareDupeFilter',
        'HTTPCACHE_STORAGE': 'scrapy_splash.SplashAwareFSCacheStorage'
    }
    name = "apec"
    allowed_domains = ["https://cadres.apec.fr"]
    apec_areas = {'nantes': 577013, 'rennes': 573974}
    apec_areas_reverse = {v: k for k, v in apec_areas.items()}

    query_url = "https://cadres.apec.fr/home/mes-offres/recherche-des-offres-demploi/liste-des-offres-demploi.html"
    start_urls = []

    for area in areas:
        for word in words:
            start_urls.append(
                query_url +
                f"?motsCles={word}&sortsType=SCORE&sortsDirection=DESCENDING&lieux={apec_areas[area]}"
            )

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                self.parse,
                meta={
                    'splash': {
                        'endpoint': 'render.html',
                        'args': {
                            'wait': 1
                        }
                    }
                })

    def parse(self, response):
        query = urllib.parse.urlparse(response.url)
        keywords = urllib.parse.parse_qs(query.query)
        word = keywords['motsCles'][0]
        area = self.apec_areas_reverse[int(keywords['lieux'][0])]
        soup = bs.BeautifulSoup(response.text, "html.parser")
        offers = soup.find_all("div",
                               {"itemtype": "http://schema.org/JobPosting"})

        for o in offers:
            url = 'https://cadres.apec.fr' + o.find('a')['href']
            title = o.find('span', {'itemprop': 'title'}).text
            company = o.find('span', {'itemprop': 'hiringOrganization'}).find(
                'span', {'itemprop': 'name'}).text
            date_raw = o.find('meta', {'itemprop': 'datePosted'})["content"]
            date = datetime.datetime.strptime(date_raw,
                                              "%Y-%m-%dT%H:%M:%S%z").replace(
                                                  tzinfo=None)
            if (today - date) < datetime.timedelta(days=8):
                matches.append({
                    "date": date,
                    "source": "APEC",
                    "word": word,
                    "area": area.title(),
                    "user": company,
                    "text": title,
                    "url": url,
                })


process = CrawlerProcess({
    'USER_AGENT':
    'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1)'
})
process.crawl(ApecSpider)
process.start()

# --- Lolix ----
print("Crawling Lolix…")
lolix_regions = {'nantes': 20, 'rennes': 6}
for area, region in lolix_regions.items():
    url = f"http://fr.lolix.org/search/offre/liste.php?type=region&oid={region}"
    r = requests.get(url)
    soup = bs.BeautifulSoup(r.text, "html.parser")
    offres = soup.find('div', {'class':
                               'PageTitre'}).find_next('table').find_all('tr')
    for o in offres:
        tds = o.findAll('td')
        cell = []
        for td in tds:
            link = td.find('a')
            if link:
                cell.append(link['href'])
            if td.text:
                cell.append(td.text)
        if len(cell) == 5:
            date = datetime.datetime.strptime(cell[0], "%d %B %Y")
            company = cell[2]
            url = 'http://fr.lolix.org/' + cell[3]
            title = cell[4]
            if (today - date) < datetime.timedelta(days=8):
                matches.append({
                    "date": date,
                    "source": "Lolix",
                    "word": '',
                    "area": area.title(),
                    "user": company,
                    "text": title,
                    "url": url,
                })

# --- Twitter ---
print("Crawling Twitter…")
api = twitter.Api(
    consumer_key=config['twitter']['consumer_key'],
    consumer_secret=config['twitter']['consumer_secret'],
    access_token_key=config['twitter']['access_token_key'],
    access_token_secret=config['twitter']['access_token_secret'])

for area in areas:
    for word in words:
        results = api.GetSearch(
            raw_query="q=" + area + " " + word + "&result_type=recent")
        for result in results:
            date = datetime.datetime.strptime(result.created_at,
                                              "%a %b %d %X %z %Y").replace(
                                                  tzinfo=None)
            if (today - date) < datetime.timedelta(days=8):
                match = ({
                    "date": date,
                    "word": word,
                    "source": "Twitter",
                    "area": area.title(),
                    "user": result.user.name,
                    "text": result.text,
                })
                for url in result.urls:
                    match['url'] = url.expanded_url
                matches.append(match)

sorted_jobs = sorted(matches, key=lambda k: k['date'])
t = Terminal()

for job in sorted_jobs:
    str_date = humanize.naturalday(job['date'])
    print(t.green(f"▶ {job['source']} | {job['area']} | {str_date}"))
    print(t.bold(f"{job['user']}" + " → " + job['text']))
    print(t.underline_cyan(f"{job['url']}"))
    print()
