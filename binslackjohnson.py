#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
#import json
import requests
import threading
from binance.client import Client
from binance.websockets import BinanceSocketManager

from config import *


__version__ = '0.2a1'
__license__ = 'GPLv3'


vstore = None
symbols = None


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
    symbols = make_sdict()
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
    return symbols


def get_avrg(client, sevent):
    # Average price picker thread
    while True:
        for s in symbols.keys():
            price = client.get_avg_price(symbol=s)['price']
            vstore.avrg[s] = round(price, 4)
            time.sleep(0.5)
        get_24h(client)

        # Notify the main thread we are ready
        if not sevent.is_set():
            svent.set()
        time.sleep(300)


def get_24h(client):
    # Get last 24h top/low/%change for all currencies
    for s in symbols.keys():
        tk = client.get_ticker(symbol=s)
        vstore.max24[s] = float(tk['highPrice'])
        vstore.min24[s] = float(tk['lowPrice'])
        vstore.percent24[s] = tk['priceChangePercent']
        time.sleep(0.5)

        # debug
        if use_stdout:
            print('[%s] %s: Min: $%s Max: $%s' %
                  (time.ctime(), s, tk['lowPrice'], tk['highPrice']))


def spam(currency, msg):
    if (vstore.last[currnecy] + slack_msg_limit) < time.time():
        slack_msg(':%s: %s %s' % (currency[:3].lower(), currnecy[:3], m))
        vstore.last[currency] = time.time()

    # debug
    if use_stdout:
        print('[%s] %s: %s' % (time.ctime(), currency[:3], msg))


def round_to(price):
    # Find how should we round numbers
    if (price > 1) and (price < 10):
        r = 2
    elif (price >= 10) and (price < 100):
        r = 3
    elif (price >= 100) and (price < 1000):
        r = 1
    elif (price >= 1000):
        r = 0
    return r


def slack_msg(text):
    # Send the slack message (POST)
    post = {
        'username': 'Pesho',
        'icon_emoji': ':robot_face:',
        'channel': slack_channel,
        'token': slack_token,
        'text': text
    }
    requests.post(url=slack_api_url, data=post)


def process_message(msg, r=4):
    # Process incomming websocket message (binance API)
    currency = msg['data']['s']
    price = float(msg['data']['p'])

    # Set correct price rounding
    r = round_to(price)
    price = round(price, r)

    # Set some min/max value if none yet set
    if (vstore.cmax[currency] == 0) or (vstore.cmin[currency] == 0):
        vstore.cmax[currency] = round(price + (price * 0.005), r)
        vstore.cmin[currency] = round(price - (price * 0.005), r)
        spam(currency, 'Alert limits --- Low: $%s High: $%s' % (
            round(vstore.cmin[currency], r),
            round(vstore.cmax[currency], r))
        )
    # Check if we have new min/max
    if (vstore.cmax[currency] < price) and (vstore.max24[currency] < price):
        spam_msg = 'new top: $%s !!!\n' % (round(price, r))
        spam_msg += ' --- Last 24h top: $%s | Last 24h change: %s%%]' % \
                                        (round(vstore.max24[currency], r),
                                        round(vstore.percent24[currency], r))
        spam(currency, spam_msg)

        # Don't keep tops above 24h top
        if price < vstore.max24[currency]:
            vstore.cmax[currency] = price
        else:
            vstore.cmax[currency] = vstore.max24[currency]

    if (vstore.cmin[currency] > price) and (vstore.min24[currency] > price):
        spam_msg = 'new low: $%s !!!\n' % (round(price, r))
        spam_msg = ' --- Last 24h bottom: $%s | Last 24h change: %s%%]' % \
                                        (round(vstore.min24[currency], r),
                                        round(vstore.percent24[currency], r))
        spam(currency, spam_msg)

        # Don't keep lows below 24h low
        if price > vstore.min24[currency]:
            vstore.cmin[currency] = price
        else:
            vstore.cmin[currency] = vstore.min24[currency]

    # below 24h min?
    if price < vstore.min24[currency]:
        m = 'price - $%s.\n --- This is $-%s below daily minimum [$%s]' % \
            (round(price, r),
             round(vstore.min24[currency] - price, r),
             round(vstore.min24[currency], r))
        spam(currency, m)

    # Above 24h max?
    if price > vstore.max24[currency]:
        m = 'price - $%s\n --- This is $%s above the daily maximum [$%s]' % \
             (round(price, r),
              round(price - vstore.max24[currency], r),
              round(vstore.max24[currency], r))
        spam(currency, m)

    # Price change
    if vstore.now[currency] != price:
        p_change = round_it(percentage(vstore.avrg[currency], price), 5)
        vstore.now[currency] = price

        # Is price change bigger then 1%? 3%?
        if (abs(p_change) > 1) and (abs(p_change) < 3):
            m = 'price - $%s change %s%% from 5m avg\n' % \
                (round(price, r), round(p_change, 1))

            if price < vstore.min24[currency]:
                m += '@here This is $%s below the daily minium [$%s]' % \
                    (round(price - vstore.min24[currency], r),
                     round(vstore.min24[currency], r))
            else:
                m += 'That is $%s above the daily minimum [$%s]' % \
                    (round(price - vstore.min24[currency], r),
                     round(vstore.min24[currency], r))
            spam(currency, m)
        elif abs(p_change) > 3:
            m = '@here price $%s change %s%% from 5m avg!' % \
                (round(price, r), round(p_change, 1))
            if price > vstore.cmax24[currency]:
                m += 'This is $%s above the daily maximum [$%s]' % \
                    (round(vstore.max24[currency] - price, r),
                     round(vstore.max24[currency], r))
            spam(currency, m)


if __name__ == '__main__':
    # Init application
    sevent = threading.Event()
    vstore = datastore()
    init_vstore()

    # Spam that we are starting
    slack_msg('BinSlackJohnson v%s in da house!' % __version__)

    # Binance connection
    client = Client(access_key, secret_key)
    bm = BinanceSocketManager(client)

    # Average values thread
    threading.Thread(target=get_avrg, args=(client, sevent,)).start()

    # Sleep untill avg values are fetched
    while not sevent.is_set():
        time.sleep(0.1)

    # Send message to notify that we'll start watching the market
    slack_msg(':gledamte:')

    # 0ff we go
    conn_key = bm.start_multiplex_socket(get_watch_symbols(), process_message)
    bm.start()

# EOF
