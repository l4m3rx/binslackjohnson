# Currencies to follow
currency_list = [ 'BTC', 'ETH', 'XRP', 'BNB', 'LTC' ]

### Slack Configuration ###
slack_msg_limit = 30
slack_channel = 'investments'
slack_bot_name = 'Pesho'
slack_bot_icon = ':robot_face:'
#slack_channel = 'domoticz'
slack_token = 'xoxb-1'
slack_api_url = 'https://slack.com/api/chat.postMessage'

### Binance Configuration ###
access_key = 'XVmrFIVuto'
secret_key = 'dfmdsQdDm'

### Other settings ###
use_stdout = True

### Do not edit below ###
symbols = {}
class datastore(object):
    def __init__(self):
        self.now  = {}
        self.avrg = {}
        self.cmax = {}
        self.cmin = {}
        self.last = {}
        self.hmin = {}
        self.hmax = {}
        self.min24 = {}
        self.max24 = {}
        self.percent24 = {}

