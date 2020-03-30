### Slack Configuration ###
# Slack channel
slack_channel = 'investments'
# Slack token
slack_token = 'xoxb-ffffffffffff-fffffffffffff-ffffffffffffffffffffffffff'
# Don't send messages to slack more often then X
# The limis it per currency
slack_msg_limit = 30
# Slack URL used for the message posting
slack_api_url = 'https://slack.com/api/chat.postMessage'

### Binance Configuration ###
# Binance API keys
access_key = 'ffffffff'
secret_key = 'ffffffff'

### Other ###
# Currencies to follow
currency_list = [ 'BTC', 'ETH', 'XRP', 'BNB', 'LTC' ]

# Print evenets in stdout (a lot of information)
# Mainly used for debuging
use_stdout = True


### Do not edit below ###
# Class used for shared data storage betwheen threads
class datastore(object):
    def __init__(self):
        self.now  = {}
        self.avrg = {}
        self.cmax = {}
        self.cmin = {}
        self.last = {}
        self.min24 = {}
        self.max24 = {}
        self.percent24 = {}

