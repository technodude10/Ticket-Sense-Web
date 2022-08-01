from codecs import ignore_errors
from celery import shared_task
from celery.utils.log import get_task_logger
import requests
from .models import Trigger, TktnewData
from dateutil import parser

# for jsonp
from json import loads


# os module used for getting env variables
import os
# telegram module to interact with telegram chat app
import telebot
# used to source data from .env
from dotenv import load_dotenv

from time import sleep

from PIL import Image
import urllib.request


logger = get_task_logger(__name__)

# loads dotenv to collect data from .env
load_dotenv()

# assigns value collected from .env to variables
API_KEY_TEST = os.getenv('API_KEY_TEST')
API_KEY = os.getenv('API_KEY')

# get image from url
def getImage(img_link):

    URL = f'https://image.tmdb.org/t/p/w500{img_link}'

    with urllib.request.urlopen(URL) as url:
        img = Image.open(url)
    return img


# code to initialize telegram bot function
bot = telebot.TeleBot(API_KEY)
@shared_task(ignore_result=True)
def message(msg, pk, USER_ID, poster):
    trigger = Trigger.objects.get(id=pk)
    trigger.delete()

    try:
        if not poster:
            bot.send_message(USER_ID, msg, parse_mode= 'Markdown')
        else:
            bot.send_photo(USER_ID, getImage(poster), msg, parse_mode= 'Markdown')
    except:
        logger.info('issue with telegram user permissions')
    
    # for i in range(3):
    #     try:
    #         if not poster:
    #             bot.send_message(USER_ID, msg, parse_mode= 'Markdown')
    #         else:
    #             bot.send_photo(USER_ID, getImage(poster), msg, parse_mode= 'Markdown')
    #     except:
    #         logger.info('issue with telegram user permissions')
    #     sleep(60)
    

# testbot = telebot.TeleBot(API_KEY_TEST)
# def testmessage(msg):
#     testbot.send_message(USER_ID, msg)

@shared_task(ignore_result=True)
def daily_func():

    response = (requests.get(f'https://api.ticketnew.com/api?_api_access_key=b1ed36c7bdbe43c1a76d01a6b8ed9c46&_api_name=ticketnew.app.location.allCities&_api_timestamp=1658745104178&_api_version=1.0.0&request={{"appDevice":1658745104178,"appVersion":"4.4.8","appPlatform":"H5","appEnv":"PROD","appChannel":"TICKETNEW"}}&_api_signature=4ExixovOYhKwnTkuSm5v7p2uh/I=&_api_jsonp_callback=jsonp0'))
    
    startidx = response.text.find('(')
    endidx = response.text.rfind(')')
    data = loads(response.text[startidx + 1:endidx])

    for j in data['body']['data']['hots']:
        get_tktnew_data.delay(j['name'])
    # for i in data['body']['data']['all']:
    #     get_tktnew_data.delay(i['name'])
    
    
@shared_task(ignore_result=True)
def get_tktnew_data(location):

    response = (requests.get(f'http://127.0.0.1:9080/crawl.json?spider_name=tkdata&start_requests=true&crawl_args={{"location":"{location}"}}').json())
    try:
        data = response['items']
    except:
        data = ''

    store_tktnew_data.delay(data, location)


@shared_task(ignore_result=True)
def store_tktnew_data(response, location):
    tktnewData, created = TktnewData.objects.update_or_create(location=location, data=response, defaults={'location': location})
    # tktnewData = TktnewData.objects.create(location=location, data=response)




@shared_task(ignore_result=True)
def five_min_func():

    try:
        triggers = Trigger.objects.all()

        for trigger in triggers:
            pk = trigger.id
            link = trigger.link
            filmkeyword = (trigger.movie).lower() #make sure that this is lowercase otherwise the result will be incorrect
            date = (trigger.date).strftime('%Y-%m-%d')
            site = trigger.site
            USER_ID = trigger.tg_user.id #from foreign key data
            poster = trigger.poster
            fetch.delay(link, filmkeyword, date, site, pk, USER_ID, poster)
    except:
        pass

        

@shared_task(ignore_result=True)
def fetch(link, filmkeyword, date, site, pk, USER_ID, poster):
    
    response = (requests.get(f'http://127.0.0.1:9080/crawl.json?spider_name={site}&start_requests=true&crawl_args={{"link":"{link}","film":"{filmkeyword}","date":"{date}"}}').json())
    try:
        data = response['items']
    except:
        data = ''

    if data != []:
        for i in data:
            film = i['show']
            venue = i['venue']
            date = (parser.parse(i['date'])).strftime('%d-%m-%Y')

            if site == 'bms':
                websitelink = f'https://in.bookmyshow.com/buytickets/{link}'
            else:
                websitelink = f'{link}'

            #** ** to make text bold for telegram based on markdown parsing
            msg = f""" *Ticket Sense* found ticket booking

Movie:
*{film}*
            
Theater: 
*{venue}*

Date:
*{date}*

Link: {websitelink} 

_Make sure the booking date is correct when buying the ticket._ """  

            message.delay(msg, pk, USER_ID, poster)

    return 'done'

