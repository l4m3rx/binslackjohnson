#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import time
import requests
import threading

import cryptocompare

from binance.client import Client
from binance.websockets import BinanceSocketManager

import slackbot.settings
from slackbot.bot import Bot
from slackbot.bot import listen_to
from slackbot.bot import respond_to

from config import *


__version__ = '1.0c1'
__license__ = 'GPLv3'


vstore = None


def get_1p(price):
    # Return 1%
    return round_it(price/100)


def percentage(part, whole):
    # Calculate percentage
    return 100 - (100 * float(part) / float(whole))


def get_watch_symbols():
    # Generate market event symbol name array
    arr = []
    for s in symbols.keys():
        arr.append(symbols[s][1])
    return arr


def init_vstore():
    # Init the vstore
    make_sdict()
    for s in symbols.keys():
        vstore.now[s] = 0
        vstore.cmin[s] = 0
        vstore.cmax[s] = 0
        vstore.last[s] = time.time() - 300


def make_sdict():
    # Make dict from the currency list
    for smb in currency_list:
        sname = smb.upper()
        mname = sname + 'USDT'
        ename = mname.lower() + '@aggTrade'
        symbols[mname] = [sname, ename]


def get_avrg(client, sevent):
    # Average price picker thread
    ran = False

    while True:
        for s in symbols.keys():
            price = client.get_avg_price(symbol=s)['price']
            vstore.avrg[s] = round_it(float(price))
            if not ran:
                time.sleep(1)

        get_24h(client, ran)

        ran = True
        sevent.set()

        time.sleep(300)


def get_hourly(currency):
    # Get hourly mix/max
    hd = cryptocompare.get_historical_price_hour(
                        currency, curr='USD', limit=1)
    currency += 'USDT'
    try:
        vstore.hmax[currency] = round_it(hd[-1]['high'])
        vstore.hmin[currency] = round_it(hd[-1]['low'])
    except:
        vstore.hmax[currency] = vstore.cmax[currency]
        vstore.hmin[currency] = vstore.cmin[currency]


def get_24h(client, ran=False):
    # Get last 24h top/low/%change for all currencies
    for s in symbols.keys():
        get_hourly(s[:3].upper())
        tk = client.get_ticker(symbol=s)
        vstore.max24[s] = round_it(float(tk['highPrice']))
        vstore.min24[s] = round_it(float(tk['lowPrice']))
        vstore.percent24[s] = tk['priceChangePercent']
        if not ran:
            time.sleep(1)

        # debug
        if use_stdout:
            print('[%s] %s: Min: $%s Max: $%s' %
                  (time.ctime(), s, tk['lowPrice'], tk['highPrice']))


def spam(currency, msg):
    # Slack message mutex function
    if use_stdout:
        print('[%s] spam() %s: %s' % (time.ctime(), currency, msg))

    if (vstore.last[currency] + slack_msg_limit) < time.time():
        slack_msg(':%s: %s %s' % (currency[:3].lower(), currency[:3], msg))
        vstore.last[currency] = time.time()


def round_it(price):
    # Round the prices to more human numbers
    if (price > 1) and (price < 10):
        price = round(price, 3)
    elif (price >= 10) and (price < 100):
        price = round(price, 2)
    elif (price >= 100) and (price < 1000):
        price = round(price, 1)
    elif (price >= 1000):
        price = round(price, 0)
    else:
        price = round(price, 4)
    return price


def slack_msg(text):
    # Send the slack message (POST)
    post = {
        'username': slack_bot_name,
        'icon_emoji': slack_bot_icon,
        'channel': slack_channel,
        'token': slack_token,
        'text': text
    }
    requests.post(url=slack_api_url, data=post)


def process_message(msg):
    # Process incomming websocket message (binance API)
    currency = msg['data']['s']
    price = float(msg['data']['p'])
    # Current price and change
    p_change  = round_it(percentage(vstore.avrg[currency], price))

    price = round_it(price)
    vstore.now[currency] = price

    # Set some min/max value if none yet set
    if (vstore.cmax[currency] == 0) or (vstore.cmin[currency] == 0):
        vstore.cmax[currency] = round_it(price + get_1p(price))
        vstore.cmin[currency] = round_it(price - get_1p(price))
    # Check if we have new min/max
    if (vstore.cmax[currency] < price) and (vstore.max24[currency] > price):
        spam_msg = 'new top: *$%s* :top: !!!\n' % (round_it(price))
        spam_msg += ' --- :black_small_square: Last 24h top: *$%s* | Last 24h change: `%s%%`]' % \
                                        (round_it(vstore.max24[currency]),
                                        vstore.percent24[currency])
        spam(currency, spam_msg)

        # Don't keep tops above 24h top
        if price < vstore.max24[currency]:
            vstore.cmax[currency] = round_it(price + get_1p(price))
        else:
            vstore.cmax[currency] = vstore.max24[currency]

    if (vstore.cmin[currency] > price) and (vstore.min24[currency] < price):
        spam_msg = 'new low: *$%s* :arrow_down: !!!\n' % (round_it(price))
        spam_msg += ' --- :black_small_square: Last 24h bottom: *$%s* | Last 24h change: `%s%%`]' % \
                                        (round_it(vstore.min24[currency]),
                                        vstore.percent24[currency])
        spam(currency, spam_msg)

        # Don't keep lows below 24h low
        if price > vstore.min24[currency]:
            vstore.cmin[currency] = round_it(price - get_1p(price))
        else:
            vstore.cmin[currency] = vstore.min24[currency]

    # below 24h min?
    if price < vstore.min24[currency]:
        msg = 'price - *$%s* :arrow_down: \n' % price
        msg += '--- :black_small_square: This is $-%s below daily minimum [*$%s*]' % \
            (round_it(vstore.min24[currency] - price), round_it(vstore.min24[currency]))
        spam(currency, msg)
        vstore.min24[currency] = price

    # Above 24h max?
    if price > vstore.max24[currency]:
        msg = 'price - *$%s* :top: \n' % price
        msg += '--- :black_small_square: This is $%s above the daily maximum [*$%s*]' % \
             (round_it(price - vstore.max24[currency]), round_it(vstore.max24[currency]))
        spam(currency, msg)
        vstore.max24[currency] = price

    # Is price change bigger then 1%? 3%?
    if (abs(p_change) > 1) and (abs(p_change) < 2):
        msg = 'price - *$%s* change `%s%%` from 5m avg\n' % \
            (price, round(p_change, 1))

        if price < vstore.min24[currency]:
            msg += '@here This is :arrow_down: *$%s* below the daily minium [*$%s*]' % \
                (round_it(price - vstore.min24[currency]), round_it(vstore.min24[currency]))
        else:
            msg += 'That is *$%s* above the daily minimum [*$%s*]' % \
                (round_it(price - vstore.min24[currency]), round_it(vstore.min24[currency]))

        spam(currency, msg)
        # We do this so we don't get constant spam
        vstore.avrg[currency] = price

    elif abs(p_change) >= 2:
        msg = '@here price - *$%s*. ' % price
        msg += 'This is `%s%%` deviation from the 5 min average!!!' % round(p_change, 1)

        if price > vstore.cmax24[currency]:
            msg += 'This is *$%s* above the daily maximum [*$%s*]' % \
                (round_it(vstore.max24[currency] - price),
                 round_it(vstore.max24[currency]))

        spam(currency, msg)
        # We do this so we don't get constant spam
        vstore.avrg[currency] = price



class sbot(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        slackbot.settings.API_TOKEN = slack_token
        slackbot.settings.DEFAULT_REPLY = 'Ko?'
        slackbot.settings.BOT_EMOJI = slack_bot_icon
        #slackbot.settings.BOT_ICON = slack_bot_icon
        self.bot = Bot()

    def run(self):
        self.bot.run()


    @listen_to('.help$', re.IGNORECASE)
    def help(message):
        msg = 'Available commands:\n *.help* --- Display help\n'
        msg += ' :black_small_square: *.status* --- Display all monitored currency status\n'
        msg += ' :black_small_square: *.stats* --- Display short stats (current price)\n'
        msg += ' :black_small_square: *.price <coin>* --- To display current stats for a specific coin\n'
        message.send(msg)


    @listen_to('.stats$', re.IGNORECASE)
    def stats(message):
        msg = 'Current prices: \n'
        for c in symbols.keys():
            msg += ' :black_small_square: :%s: %s -- *$%s*\n' % \
                (symbols[c][0].lower(), symbols[c][0], vstore.now[c])
        message.send(msg)


    @listen_to('.status$', re.IGNORECASE)
    def status(message):
        for c in symbols.keys():
            msg = ':%s: %s current price: *$%s*\n' % \
                (symbols[c][0].lower(), symbols[c][0], vstore.now[c])
            msg += ' --- :black_small_square: Hourly: $%s-$%s [Delta: *$%s*]\n' % \
                (vstore.hmin[c], vstore.hmax[c], round_it(vstore.hmax[c] - vstore.hmin[c]))
            msg += ' --- :black_small_square: Daily:  $%s-$%s [Delta: *$%s*] [`%s%%`]\n' % \
                (vstore.min24[c], vstore.max24[c],
                round_it(vstore.max24[c] - vstore.min24[c]), vstore.percent24[c])
            msg += ' --- :black_small_square: Notificaiton threshold: $%s-$%s\n' % \
                (vstore.cmin[c], vstore.cmax[c])
            message.send(msg)


    @listen_to('.price (.*)', re.IGNORECASE)
    def price(message, cur):
        currency = cur.upper() + 'USDT'
        if currency in symbols.keys():
            msg = ':%s: *%s* current price *$%s*\n' % (cur.lower(), cur.upper(), vstore.now[currency])
            msg += ' --- :black_small_square: Hourly stats $%s-$%s [Delta: *$%s*]\n' % \
                (vstore.hmin[currency], vstore.hmax[currency],
                round_it(vstore.hmax[currency] - vstore.hmin[currency]))
            msg += ' --- :black_small_square: Daily  stats $%s-$%s [Delta: *$%s*] [`%s%%`]' % \
                (vstore.min24[currency], vstore.max24[currency],
                round_it(vstore.max24[currency] - vstore.min24[currency]),
                vstore.percent24[currency])
            message.send(msg)


if __name__ == '__main__':
    # Init application
    sevent = threading.Event()
    vstore = datastore()
    init_vstore()

    # Spam that we are starting
    slack_msg('BinSlackJohnson `v%s` in da house!' % __version__)

    # Binance connection
    client = Client(access_key, secret_key)
    bm = BinanceSocketManager(client)

    # Average values thread
    threading.Thread(target=get_avrg, args=(client, sevent,)).start()

    # Start slackbot
    bot = sbot().start()

    # Sleep untill avg values are fetched
    sevent.wait()
    slack_msg(':gledamte:')

    # 0ff we go
    conn_key = bm.start_multiplex_socket(get_watch_symbols(), process_message)
    bm.start()

# EOF
