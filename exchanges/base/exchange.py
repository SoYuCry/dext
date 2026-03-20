# -*- coding: utf-8 -*-

"""Base exchange class"""

# -----------------------------------------------------------------------------

__version__ = '4.5.32'

# -----------------------------------------------------------------------------

from traceback import format_exception
from .errors import (
    ExchangeError,
    NetworkError,
    NotSupported,
    AuthenticationError,
    DDoSProtection,
    RequestTimeout,
    ExchangeNotAvailable,
    InvalidAddress,
    InvalidOrder,
    ArgumentsRequired,
    BadSymbol,
    NullResponse,
    RateLimitExceeded,
    OperationFailed,
    BadRequest,
    BadResponse,
    InvalidProxySettings,
    UnsubscribeError,
)

# -----------------------------------------------------------------------------

from .decimal_to_precision import (
    decimal_to_precision,
    DECIMAL_PLACES,
    TICK_SIZE,
    NO_PADDING,
    TRUNCATE,
    ROUND,
    ROUND_UP,
    ROUND_DOWN,
    SIGNIFICANT_DIGITS,
    number_to_string,
)
from .precise import Precise
from .types import (
    ConstructorArgs,
    BalanceAccount,
    Currency,
    Entry,
    IndexType,
    OrderSide,
    OrderType,
    Trade,
    OrderRequest,
    Market,
    MarketType,
    Str,
    Num,
    Strings,
    CancellationRequest,
    Bool,
    Order,
    Int,
)

# -----------------------------------------------------------------------------

# rsa jwt signing
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.serialization import load_pem_private_key

# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------

__all__ = [
    'Exchange',
]

# -----------------------------------------------------------------------------

import logging
import base64
import binascii
import calendar
import collections
import datetime
from email.utils import parsedate
# import functools
import gzip
import hashlib
import hmac
import io

# load orjson if available, otherwise default to json
orjson = None
try:
    import orjson as orjson
except ImportError:
    pass

import json
import math
import random
from numbers import Number
import re
from requests import Session
from requests.utils import default_user_agent
from requests.exceptions import HTTPError, Timeout, TooManyRedirects, RequestException, ConnectionError as requestsConnectionError
# import socket
from ssl import SSLError
# import sys
import time
import uuid
import zlib
from decimal import Decimal
from time import mktime
from wsgiref.handlers import format_date_time
import urllib.parse as _urlencode
from typing import Any, List
from .types import Int

# -----------------------------------------------------------------------------

class SafeJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Exception):
            return {"name": obj.__class__.__name__}
        try:
            return super().default(obj)
        except TypeError:
            return f"TypeError: Object of type {type(obj).__name__} is not JSON serializable"

class _HasDict(dict):
    """Dict subclass that returns None for missing keys.

    Used for the ``has`` capability dict so that ``self.has['someCap']``
    returns None (falsy) instead of raising KeyError when the capability
    is not explicitly listed.
    """
    def __missing__(self, key):
        return None

class Exchange(object):
    """Base exchange class"""
    id = None
    name = None
    countries = None
    version = None
    certified = False  # if certified by the dev team
    pro = False  # if it is integrated with Pro for WebSocket support
    alias = False  # whether this exchange is an alias to another exchange
    # rate limiter settings
    enableRateLimit = True
    rateLimit = 2000  # milliseconds = seconds * 1000
    timeout = 10000   # milliseconds = seconds * 1000
    asyncio_loop = None
    aiohttp_proxy = None
    ssl_context = None
    trust_env = False
    aiohttp_trust_env = False
    requests_trust_env = False
    session = None  # Session () by default
    tcp_connector = None  # aiohttp.TCPConnector
    aiohttp_socks_connector = None
    socks_proxy_sessions = None
    verify = True  # SSL verification
    validateServerSsl = True
    validateClientSsl = False
    logger = None  # logging.getLogger(__name__) by default
    verbose = False
    markets = None
    symbols = None
    codes = None
    timeframes = {}
    tokenBucket = None
    rollingWindowSize = 0.0  # set to 0.0 to use leaky bucket rate limiter
    rateLimiterAlgorithm = 'leakyBucket'

    fees = {
        'trading': {
            'tierBased': None,
            'percentage': None,
            'taker': None,
            'maker': None,
        },
        'funding': {
            'tierBased': None,
            'percentage': None,
            'withdraw': {},
            'deposit': {},
        },
    }
    loaded_fees = {
        'trading': {
            'percentage': True,
        },
        'funding': {
            'withdraw': {},
            'deposit': {},
        },
    }
    ids = None
    urls = None
    api = None
    parseJsonResponse = True
    throttler = None

    # PROXY & USER-AGENTS (see "examples/proxy-usage" file for explanation)
    proxy = None  # for backwards compatibility
    proxyUrl = None
    proxy_url = None
    proxyUrlCallback = None
    proxy_url_callback = None
    httpProxy = None
    http_proxy = None
    httpProxyCallback = None
    http_proxy_callback = None
    httpsProxy = None
    https_proxy = None
    httpsProxyCallback = None
    https_proxy_callback = None
    socksProxy = None
    socks_proxy = None
    socksProxyCallback = None
    socks_proxy_callback = None
    userAgent = None
    user_agent = None
    wsProxy = None
    ws_proxy = None
    wssProxy = None
    wss_proxy = None
    wsSocksProxy = None
    ws_socks_proxy = None
    #
    userAgents = {
        'chrome': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.94 Safari/537.36',
        'chrome39': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36',
        'chrome100': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.75 Safari/537.36',
    }
    headers = None
    returnResponseHeaders = False
    origin = '*'  # CORS origin
    MAX_VALUE = float('inf')
    #
    proxies = None

    hostname = None  # in case of inaccessibility of the "main" domain
    apiKey = ''
    secret = ''
    password = ''
    uid = ''
    accountId = None
    privateKey = ''  # a "0x"-prefixed hexstring private key for a wallet
    walletAddress = ''  # the wallet address "0x"-prefixed hexstring
    token = ''  # reserved for HTTP auth in some cases
    twofa = None
    markets_by_id = None
    currencies_by_id = None

    precision = None
    exceptions = None
    limits = {
        'leverage': {
            'min': None,
            'max': None,
        },
        'amount': {
            'min': None,
            'max': None,
        },
        'price': {
            'min': None,
            'max': None,
        },
        'cost': {
            'min': None,
            'max': None,
        },
    }

    httpExceptions = {
        '422': ExchangeError,
        '418': DDoSProtection,
        '429': RateLimitExceeded,
        '404': ExchangeNotAvailable,
        '409': ExchangeNotAvailable,
        '410': ExchangeNotAvailable,
        '451': ExchangeNotAvailable,
        '500': ExchangeNotAvailable,
        '501': ExchangeNotAvailable,
        '502': ExchangeNotAvailable,
        '520': ExchangeNotAvailable,
        '521': ExchangeNotAvailable,
        '522': ExchangeNotAvailable,
        '525': ExchangeNotAvailable,
        '526': ExchangeNotAvailable,
        '400': ExchangeNotAvailable,
        '403': ExchangeNotAvailable,
        '405': ExchangeNotAvailable,
        '503': ExchangeNotAvailable,
        '530': ExchangeNotAvailable,
        '408': RequestTimeout,
        '504': RequestTimeout,
        '401': AuthenticationError,
        '407': AuthenticationError,
        '511': AuthenticationError,
    }
    balance = None
    liquidations = None
    orderbooks = None
    orders = None
    triggerOrders = None
    myLiquidations = None
    myTrades = None
    trades = None
    transactions = None
    ohlcvs = None
    tickers = None
    fundingRates = None
    bidsasks = None
    base_currencies = None
    quote_currencies = None
    currencies = {}
    options = None  # Python does not allow to define properties in run-time with setattr
    isSandboxModeEnabled = False
    accounts = None
    positions = None

    status = None

    requiredCredentials = {
        'apiKey': True,
        'secret': True,
        'uid': False,
        'accountId': False,
        'login': False,
        'password': False,
        'twofa': False,  # 2-factor authentication (one-time password key)
        'privateKey': False,  # a "0x"-prefixed hexstring private key for a wallet
        'walletAddress': False,  # the wallet address "0x"-prefixed hexstring
        'token': False,  # reserved for HTTP auth in some cases
    }

    # API method metainfo
    has = {}
    features = {}
    precisionMode = DECIMAL_PLACES
    paddingMode = NO_PADDING
    minFundingAddressLength = 1  # used in check_address
    substituteCommonCurrencyCodes = True
    quoteJsonNumbers = True
    number: Num = float  # or str (a pointer to a class)
    handleContentTypeApplicationZip = False
    # whether fees should be summed by currency code
    reduceFees = True
    lastRestRequestTimestamp = 0
    lastRestPollTimestamp = 0
    restRequestQueue = None
    restPollerLoopIsRunning = False
    rateLimitTokens = 16
    rateLimitMaxTokens = 16
    rateLimitUpdateTime = 0
    enableLastHttpResponse = True
    enableLastJsonResponse = False
    enableLastResponseHeaders = True
    last_http_response = None
    last_json_response = None
    last_response_headers = None
    last_request_body = None
    last_request_url = None
    last_request_headers = None

    commonCurrencies = {
        'XBT': 'BTC',
        'BCC': 'BCH',
        'BCHSV': 'BSV',
    }
    synchronous = True

    def __init__(self, config: ConstructorArgs = {}):
        self.aiohttp_trust_env = self.aiohttp_trust_env or self.trust_env
        self.requests_trust_env = self.requests_trust_env or self.trust_env

        self.precision = dict() if self.precision is None else self.precision
        self.limits = dict() if self.limits is None else self.limits
        self.exceptions = dict() if self.exceptions is None else self.exceptions
        self.headers = dict() if self.headers is None else self.headers
        self.balance = dict() if self.balance is None else self.balance
        self.orderbooks = dict() if self.orderbooks is None else self.orderbooks
        self.fundingRates = dict() if self.fundingRates is None else self.fundingRates
        self.tickers = dict() if self.tickers is None else self.tickers
        self.bidsasks = dict() if self.bidsasks is None else self.bidsasks
        self.trades = dict() if self.trades is None else self.trades
        self.transactions = dict() if self.transactions is None else self.transactions
        self.ohlcvs = dict() if self.ohlcvs is None else self.ohlcvs
        self.liquidations = dict() if self.liquidations is None else self.liquidations
        self.myLiquidations = dict() if self.myLiquidations is None else self.myLiquidations
        self.currencies = dict() if self.currencies is None else self.currencies
        self.options = self.get_default_options() if self.options is None else self.options  # Python does not allow to define properties in run-time with setattr
        self.decimal_to_precision = decimal_to_precision
        self.number_to_string = number_to_string

        # version = '.'.join(map(str, sys.version_info[:3]))
        # self.userAgent = {
        #     'User-Agent': 'dext/' + __version__ + ' Python/' + version
        # }

        self.origin = self.uuid()
        self.userAgent = default_user_agent()

        settings = self.deep_extend(self.describe(), config)

        for key in settings:
            if hasattr(self, key) and isinstance(getattr(self, key), dict):
                setattr(self, key, self.deep_extend(getattr(self, key), settings[key]))
            else:
                setattr(self, key, settings[key])

        # Wrap has dict so missing keys return None instead of KeyError
        if hasattr(self, 'has') and not isinstance(self.has, _HasDict):
            self.has = _HasDict(self.has)

        self.after_construct()

        if self.safe_bool(config, 'sandbox') or self.safe_bool(config, 'testnet'):
            self.set_sandbox_mode(True)

        if not self.session and self.synchronous:
            self.session = Session()
            self.session.trust_env = self.requests_trust_env
        self.logger = self.logger if self.logger else logging.getLogger(__name__)

    def __del__(self):
        if self.session:
            try:
                self.session.close()
            except Exception as e:
                pass

    def __repr__(self):
        return 'dext.' + ('async_support.' if self.asyncio_loop else '') + self.id + '()'

    def __str__(self):
        return self.name

    def init_throttler(self, cost=None):
        # stub in sync
        pass

    def throttle(self, cost=None):
        now = float(self.milliseconds())
        elapsed = now - self.lastRestRequestTimestamp
        cost = 1 if cost is None else cost
        sleep_time = self.rateLimit * cost
        if elapsed < sleep_time:
            delay = sleep_time - elapsed
            time.sleep(delay / 1000.0)

    @staticmethod
    def gzip_deflate(response, text):
        encoding = response.info().get('Content-Encoding')
        if encoding in ('gzip', 'x-gzip', 'deflate'):
            if encoding == 'deflate':
                return zlib.decompress(text, -zlib.MAX_WBITS)
            else:
                return gzip.GzipFile('', 'rb', 9, io.BytesIO(text)).read()
        return text

    def prepare_request_headers(self, headers=None):
        headers = headers or {}
        if self.session:
            headers.update(self.session.headers)
        headers.update(self.headers)
        userAgent = self.userAgent if self.userAgent is not None else self.user_agent
        if userAgent:
            if type(userAgent) is str:
                headers.update({'User-Agent': userAgent})
            elif (type(userAgent) is dict) and ('User-Agent' in userAgent):
                headers.update(userAgent)
        headers.update({'Accept-Encoding': 'gzip, deflate'})
        return self.set_headers(headers)

    def log(self, *args):
        print(*args)

    def on_rest_response(self, code, reason, url, method, response_headers, response_body, request_headers, request_body):
        return response_body.strip()

    def on_json_response(self, response_body):
        if self.quoteJsonNumbers and orjson is None:
            return json.loads(response_body, parse_float=str, parse_int=str)
        else:
            if orjson:
                return orjson.loads(response_body)
            return json.loads(response_body)

    def fetch(self, url, method='GET', headers=None, body=None):
        """Perform a HTTP request and return decoded JSON data"""

        # ##### PROXY & HEADERS #####
        request_headers = self.prepare_request_headers(headers)
        # proxy-url
        proxyUrl = self.check_proxy_url_settings(url, method, headers, body)
        if proxyUrl is not None:
            request_headers.update({'Origin': self.origin})
            url = proxyUrl + self.url_encoder_for_proxy_url(url)
        # proxy agents
        proxies = None  # set default
        httpProxy, httpsProxy, socksProxy = self.check_proxy_settings(url, method, headers, body)
        if httpProxy:
            proxies = {}
            proxies['http'] = httpProxy
        elif httpsProxy:
            proxies = {}
            proxies['https'] = httpsProxy
        elif socksProxy:
            proxies = {}
            # https://stackoverflow.com/a/15661226/2377343
            proxies['http'] = socksProxy
            proxies['https'] = socksProxy
        proxyAgentSet = proxies is not None
        self.check_conflicting_proxies(proxyAgentSet, proxyUrl)
        # specifically for async-python, there is ".proxies" property maintained
        if (self.proxies is not None):
            if (proxyAgentSet or proxyUrl):
                raise ExchangeError(self.id + ' you have conflicting proxy settings - use either .proxies or http(s)Proxy / socksProxy / proxyUrl')
            proxies = self.proxies
        # log
        if self.verbose:
            self.log("\nfetch Request:", self.id, method, url, "RequestHeaders:", request_headers, "RequestBody:", body)
        self.logger.debug("%s %s, Request: %s %s", method, url, request_headers, body)
        # end of proxies & headers

        request_body = body
        if body:
            body = body.encode()

        self.session.cookies.clear()

        http_response = None
        http_status_code = None
        http_status_text = None
        json_response = None
        try:
            response = self.session.request(
                method,
                url,
                data=body,
                headers=request_headers,
                timeout=(self.timeout / 1000),
                proxies=proxies,
                verify=self.verify and self.validateServerSsl
            )
            # does not try to detect encoding
            response.encoding = 'utf-8'
            headers = response.headers
            http_status_code = response.status_code
            http_status_text = response.reason
            http_response = self.on_rest_response(http_status_code, http_status_text, url, method, headers, response.text, request_headers, request_body)
            json_response = self.parse_json(http_response)
            # FIXME remove last_x_responses from subclasses
            if self.enableLastHttpResponse:
                self.last_http_response = http_response
            if self.enableLastJsonResponse:
                self.last_json_response = json_response
            if self.enableLastResponseHeaders:
                self.last_response_headers = headers
            if self.verbose:
                self.log("\nfetch Response:", self.id, method, url, http_status_code, "ResponseHeaders:", headers, "ResponseBody:", http_response)
            self.logger.debug("%s %s, Response: %s %s %s", method, url, http_status_code, headers, http_response)
            if json_response and not isinstance(json_response, list) and self.returnResponseHeaders:
                json_response['responseHeaders'] = headers
            response.raise_for_status()

        except Timeout as e:
            details = ' '.join([self.id, method, url])
            raise RequestTimeout(details) from e

        except TooManyRedirects as e:
            details = ' '.join([self.id, method, url])
            raise ExchangeError(details) from e

        except SSLError as e:
            details = ' '.join([self.id, method, url])
            raise ExchangeError(details) from e

        except HTTPError as e:
            details = ' '.join([self.id, method, url])
            skip_further_error_handling = self.handle_errors(http_status_code, http_status_text, url, method, headers, http_response, json_response, request_headers, request_body)
            if not skip_further_error_handling:
                self.handle_http_status_code(http_status_code, http_status_text, url, method, http_response)
            raise ExchangeError(details) from e

        except requestsConnectionError as e:
            error_string = str(e)
            details = ' '.join([self.id, method, url])
            if 'Read timed out' in error_string:
                raise RequestTimeout(details) from e
            else:
                raise NetworkError(details) from e

        except ConnectionResetError as e:
            error_string = str(e)
            details = ' '.join([self.id, method, url])
            raise NetworkError(details) from e

        except RequestException as e:  # base exception class
            error_string = str(e)
            if ('Missing dependencies for SOCKS support' in error_string):
                raise NotSupported(self.id + ' - to use SOCKS proxy with dext, you might need "pysocks" module that can be installed by "pip install pysocks"')
            details = ' '.join([self.id, method, url])
            if any(x in error_string for x in ['ECONNRESET', 'Connection aborted.', 'Connection broken:']):
                raise NetworkError(details) from e
            else:
                raise ExchangeError(details) from e

        self.handle_errors(http_status_code, http_status_text, url, method, headers, http_response, json_response, request_headers, request_body)
        if json_response is not None:
            return json_response
        elif self.is_text_response(headers):
            return http_response
        else:
            if isinstance(response.content, bytes):
                return response.content.decode('utf8')
            return response.content

    def parse_json(self, http_response):
        try:
            if Exchange.is_json_encoded_object(http_response):
                return self.on_json_response(http_response)
        except ValueError:  # superclass of JsonDecodeError (python2)
            pass

    def is_text_response(self, headers):
        # Check if response is text/json content type
        content_type = headers.get('Content-Type', '')
        return content_type.startswith('application/json') or content_type.startswith('text/')

    @staticmethod
    def key_exists(dictionary, key):
        try:
            value = dictionary[key]
            return value is not None and value != ''
        except Exception:
            # catch any exception, not only (KeyError, IndexError, TypeError):
            return False

    @staticmethod
    def safe_float(dictionary, key, default_value=None):
        try:
            return float(dictionary[key])
        except Exception:
            return default_value

    @staticmethod
    def safe_string(dictionary, key, default_value=None):
        try:
            value = dictionary[key]
            if value is not None and value != '':
                return str(value)
        except Exception:
            pass
        return default_value

    @staticmethod
    def safe_string_lower(dictionary, key, default_value=None):
        try:
            value = dictionary[key]
            if value is not None and value != '':
                return str(value).lower()
        except Exception:
            pass
        return default_value.lower() if default_value is not None else default_value

    @staticmethod
    def safe_string_upper(dictionary, key, default_value=None):
        try:
            value = dictionary[key]
            if value is not None and value != '':
                return str(value).upper()
        except Exception:
            pass
        return default_value.upper() if default_value is not None else default_value

    @staticmethod
    def safe_integer(dictionary, key, default_value=None):
        try:
            # needed to avoid breaking on "100.0"
            # https://stackoverflow.com/questions/1094717/convert-a-string-to-integer-with-decimal-in-python#1094721
            return int(float(dictionary[key]))
        except Exception:
            # catch any exception, not only (KeyError, IndexError, TypeError, ValueError):
            return default_value

    @staticmethod
    def safe_integer_product(dictionary, key, factor, default_value=None):
        try:
            return int(float(dictionary[key]) * factor)
        except Exception:
            return default_value

    @staticmethod
    def safe_timestamp(dictionary, key, default_value=None):
        return Exchange.safe_integer_product(dictionary, key, 1000, default_value)

    @staticmethod
    def safe_value(dictionary, key, default_value=None):
        try:
            value = dictionary[key]
            if value is not None and value != '':
                return value
        except Exception:
            pass
        return default_value

    # we're not using safe_floats with a list argument as we're trying to save some cycles here
    # we're not using safe_float_3 either because those cases are too rare to deserve their own optimization

    @staticmethod
    def safe_float_2(dictionary, key1, key2, default_value=None):
        try:
            return float(dictionary[key1])
        except Exception:
            try:
                return float(dictionary[key2])
            except Exception:
                return default_value

    @staticmethod
    def safe_string_2(dictionary, key1, key2, default_value=None):
        try:
            value = dictionary[key1]
            if value is not None and value != '':
                return str(value)
        except Exception:
            pass
        try:
            value = dictionary[key2]
            if value is not None and value != '':
                return str(value)
        except Exception:
            pass
        return default_value

    @staticmethod
    def safe_string_lower_2(dictionary, key1, key2, default_value=None):
        value = Exchange.safe_string_2(dictionary, key1, key2, default_value)
        return value.lower() if value is not None else value

    @staticmethod
    def safe_string_upper_2(dictionary, key1, key2, default_value=None):
        value = Exchange.safe_string_2(dictionary, key1, key2, default_value)
        return value.upper() if value is not None else value

    @staticmethod
    def safe_integer_2(dictionary, key1, key2, default_value=None):
        try:
            return int(float(dictionary[key1]))
        except Exception:
            try:
                return int(float(dictionary[key2]))
            except Exception:
                return default_value

    @staticmethod
    def safe_integer_product_2(dictionary, key1, key2, factor, default_value=None):
        try:
            return int(float(dictionary[key1]) * factor)
        except Exception:
            try:
                return int(float(dictionary[key2]) * factor)
            except Exception:
                return default_value

    @staticmethod
    def safe_timestamp_2(dictionary, key1, key2, default_value=None):
        return Exchange.safe_integer_product_2(dictionary, key1, key2, 1000, default_value)

    @staticmethod
    def safe_value_2(dictionary, key1, key2, default_value=None):
        try:
            value = dictionary[key1]
            if value is not None and value != '':
                return value
        except Exception:
            pass
        try:
            value = dictionary[key2]
            if value is not None and value != '':
                return value
        except Exception:
            pass
        return default_value

    # safe_method_n methods family

    @staticmethod
    def safe_float_n(dictionary, key_list, default_value=None):
        value = Exchange.get_object_value_from_key_list(dictionary, key_list)
        if value is None:
            return default_value
        try:
            return float(value)
        except ValueError as e:
            return default_value

    @staticmethod
    def safe_string_n(dictionary, key_list, default_value=None):
        value = Exchange.get_object_value_from_key_list(dictionary, key_list)
        return str(value) if value is not None else default_value

    @staticmethod
    def safe_string_lower_n(dictionary, key_list, default_value=None):
        value = Exchange.get_object_value_from_key_list(dictionary, key_list)
        if value is not None:
            return str(value).lower()
        elif default_value is None:
            return default_value
        else:
            return default_value.lower()

    @staticmethod
    def safe_string_upper_n(dictionary, key_list, default_value=None):
        value = Exchange.get_object_value_from_key_list(dictionary, key_list)
        if value is not None:
            return str(value).upper()
        elif default_value is None:
            return default_value
        else:
            return default_value.upper()

    @staticmethod
    def safe_integer_n(dictionary, key_list, default_value=None):
        value = Exchange.get_object_value_from_key_list(dictionary, key_list)
        if value is None:
            return default_value
        try:
            # needed to avoid breaking on "100.0"
            # https://stackoverflow.com/questions/1094717/convert-a-string-to-integer-with-decimal-in-python#1094721
            return int(float(value))
        except ValueError:
            return default_value
        except TypeError:
            return default_value

    @staticmethod
    def safe_integer_product_n(dictionary, key_list, factor, default_value=None):
        if dictionary is None:
            return default_value
        value = Exchange.get_object_value_from_key_list(dictionary, key_list)
        if value is None:
            return default_value
        if isinstance(value, Number):
            return int(value * factor)
        elif isinstance(value, str):
            try:
                return int(float(value) * factor)
            except ValueError:
                pass
        return default_value

    @staticmethod
    def safe_timestamp_n(dictionary, key_list, default_value=None):
        return Exchange.safe_integer_product_n(dictionary, key_list, 1000, default_value)

    @staticmethod
    def safe_value_n(dictionary, key_list, default_value=None):
        if dictionary is None:
            return default_value
        value = Exchange.get_object_value_from_key_list(dictionary, key_list)
        return value if value is not None else default_value

    @staticmethod
    def get_object_value_from_key_list(dictionary_or_list, key_list):
        isDataArray = isinstance(dictionary_or_list, list)
        isDataDict = isinstance(dictionary_or_list, dict)
        for key in key_list:
            if isDataDict:
                if key in dictionary_or_list and dictionary_or_list[key] is not None and dictionary_or_list[key] != '':
                    return dictionary_or_list[key]
            elif isDataArray and not isinstance(key, str):
                if (key < len(dictionary_or_list)) and (dictionary_or_list[key] is not None) and (dictionary_or_list[key] != ''):
                    return dictionary_or_list[key]
        return None

    @staticmethod
    def safe_either(method, dictionary, key1, key2, default_value=None):
        """A helper-wrapper for the safe_value_2() family."""
        value = method(dictionary, key1)
        return value if value is not None else method(dictionary, key2, default_value)


    @staticmethod
    def uuid():
        return str(uuid.uuid4())


    @staticmethod
    def capitalize(string):  # first character only, rest characters unchanged
        # the native pythonic .capitalize() method lowercases all other characters
        # which is an unwanted behaviour, therefore we use this custom implementation
        # check it yourself: print('foobar'.capitalize(), 'fooBar'.capitalize())
        if len(string) > 1:
            return "%s%s" % (string[0].upper(), string[1:])
        return string.upper()

    @staticmethod
    def strip(string):
        return string.strip()

    @staticmethod
    def keysort(dictionary):
        return collections.OrderedDict(sorted(dictionary.items(), key=lambda t: t[0]))

    @staticmethod
    def sort(array):
        return sorted(array)

    @staticmethod
    def extend(*args):
        if args is not None:
            result = None
            if type(args[0]) is collections.OrderedDict:
                result = collections.OrderedDict()
            else:
                result = {}
            for arg in args:
                result.update(arg)
            return result
        return {}

    @staticmethod
    def deep_extend(*args):
        result = None
        for arg in args:
            if isinstance(arg, dict):
                if not isinstance(result, dict):
                    result = {}
                for key in arg:
                    result[key] = Exchange.deep_extend(result[key] if key in result else None, arg[key])
            else:
                result = arg
        return result

    @staticmethod
    def filter_by(array, key, value=None):
        array = Exchange.to_array(array)
        return list(filter(lambda x: x[key] == value, array))


    @staticmethod

    @staticmethod

    @staticmethod
    def index_by_safe(array, key):
        return Exchange.index_by(array, key)  # wrapper for go

    @staticmethod
    def index_by(array, key):
        result = {}
        if type(array) is dict:
            array = Exchange.keysort(array).values()
        is_int_key = isinstance(key, int)
        for element in array:
            if ((is_int_key and (key < len(element))) or (key in element)) and (element[key] is not None):
                k = element[key]
                result[k] = element
        return result

    @staticmethod
    def sort_by(array, key, descending=False, default=0):
        return sorted(array, key=lambda k: k[key] if k[key] is not None else default, reverse=descending)

    @staticmethod
    def sort_by_2(array, key1, key2, descending=False):
        return sorted(array, key=lambda k: (k[key1] if k[key1] is not None else "", k[key2] if k[key2] is not None else ""), reverse=descending)

    @staticmethod
    def array_concat(a, b):
        return a + b

    @staticmethod
    def in_array(needle, haystack):
        return needle in haystack

    @staticmethod
    def is_empty(object):
        return not object

    @staticmethod
    def extract_params(string):
        return re.findall(r'{([\w-]+)}', string)

    @staticmethod
    def implode_params(string, params):
        if isinstance(params, dict):
            for key in params:
                if not isinstance(params[key], list):
                    string = string.replace('{' + key + '}', str(params[key]))
        return string

    @staticmethod
    def urlencode(params={}, doseq=False, sort=False):
        newParams = params.copy()
        for key, value in params.items():
            if isinstance(value, bool):
                newParams[key] = 'true' if value else 'false'
        return _urlencode.urlencode(newParams, doseq, quote_via=_urlencode.quote)


    @staticmethod
    def encode_uri_component(uri, safe="~()*!.'"):
        return _urlencode.quote(uri, safe=safe)

    @staticmethod
    def omit(d, *args):
        if isinstance(d, dict):
            result = d.copy()
            for arg in args:
                if type(arg) is list:
                    for key in arg:
                        if key in result:
                            del result[key]
                else:
                    if arg in result:
                        del result[arg]
            return result
        return d

    @staticmethod
    def sum(*args):
        return sum([arg for arg in args if isinstance(arg, (float, int))])


    @staticmethod
    def seconds():
        return int(time.time())

    @staticmethod
    def milliseconds():
        return int(time.time() * 1000)


    @staticmethod
    def iso8601(timestamp=None):
        if timestamp is None:
            return timestamp
        if not isinstance(timestamp, int):
            return None
        if int(timestamp) < 0:
            return None

        try:
            utc = datetime.datetime.fromtimestamp(timestamp // 1000, datetime.timezone.utc)
            return utc.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-6] + "{:03d}".format(int(timestamp) % 1000) + 'Z'
        except (TypeError, OverflowError, OSError):
            return None

    @staticmethod

    @staticmethod

    @staticmethod

    @staticmethod

    @staticmethod

    @staticmethod

    @staticmethod

    @staticmethod
    def parse8601(timestamp=None):
        if timestamp is None:
            return timestamp
        yyyy = '([0-9]{4})-?'
        mm = '([0-9]{2})-?'
        dd = '([0-9]{2})(?:T|[\\s])?'
        h = '([0-9]{2}):?'
        m = '([0-9]{2}):?'
        s = '([0-9]{2})'
        ms = '(\\.[0-9]{1,3})?'
        tz = '(?:(\\+|\\-)([0-9]{2})\\:?([0-9]{2})|Z)?'
        regex = r'' + yyyy + mm + dd + h + m + s + ms + tz
        try:
            match = re.search(regex, timestamp, re.IGNORECASE)
            if match is None:
                return None
            yyyy, mm, dd, h, m, s, ms, sign, hours, minutes = match.groups()
            ms = ms or '.000'
            ms = (ms + '00')[0:4]
            msint = int(ms[1:])
            sign = sign or ''
            sign = int(sign + '1') * -1
            hours = int(hours or 0) * sign
            minutes = int(minutes or 0) * sign
            offset = datetime.timedelta(hours=hours, minutes=minutes)
            string = yyyy + mm + dd + h + m + s + ms + 'Z'
            dt = datetime.datetime.strptime(string, "%Y%m%d%H%M%S.%fZ")
            dt = dt + offset
            return calendar.timegm(dt.utctimetuple()) * 1000 + msint
        except (TypeError, OverflowError, OSError, ValueError):
            return None

    @staticmethod
    def hash(request, algorithm='md5', digest='hex'):
        h = hashlib.new(algorithm, request)
        binary = h.digest()
        if digest == 'base64':
            return Exchange.binary_to_base64(binary)
        elif digest == 'hex':
            return Exchange.binary_to_base16(binary)
        return binary

    @staticmethod
    def hmac(request, secret, algorithm=hashlib.sha256, digest='hex'):
        h = hmac.new(secret, request, algorithm)
        binary = h.digest()
        if digest == 'hex':
            return Exchange.binary_to_base16(binary)
        elif digest == 'base64':
            return Exchange.binary_to_base64(binary)
        return binary


    @staticmethod
    def binary_to_base64(s):
        return Exchange.decode(base64.standard_b64encode(s))

    @staticmethod
    def base64_to_binary(s):
        return base64.standard_b64decode(s)


    @staticmethod
    def int_to_base16(num):
        return "%0.2X" % num

    def binary_to_urlencoded_base64(data: bytes) -> str:
        encoded = base64.urlsafe_b64encode(data).decode("utf-8")
        return encoded.rstrip("=")

    @staticmethod
    def eddsa(request, secret, curve='ed25519', url_encode=False):
        if isinstance(secret, str):
            secret = Exchange.encode(secret)
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(secret) if len(secret) == 32 else load_pem_private_key(secret, None)
        signature = private_key.sign(request)
        if url_encode:
            return Exchange.binary_to_urlencoded_base64(signature)

        return Exchange.binary_to_base64(signature)

    @staticmethod
    def json(data, params=None):
        if orjson:
            return orjson.dumps(data).decode('utf-8')
        return json.dumps(data, separators=(',', ':'), cls=SafeJSONEncoder)

    @staticmethod
    def is_json_encoded_object(input):
        try:
            return (isinstance(input, str) and ((input[0] == '{') or (input[0] == '[')))
        except Exception:
            return False

    @staticmethod
    def encode(string):
        return string.encode('utf-8')

    @staticmethod
    def decode(string):
        return string.decode('utf-8')

    @staticmethod
    def to_array(value):
        return list(value.values()) if type(value) is dict else value

    @staticmethod

    def precision_from_string(self, str):
        # support string formats like '1e-4'
        if 'e' in str or 'E' in str:
            numStr = re.sub(r'\d\.?\d*[eE]', '', str)
            return int(numStr) * -1
        # support integer formats (without dot) like '1', '10' etc [Note: bug in decimalToPrecision, so this should not be used atm]
        # if not ('.' in str):
        #     return len(str) * -1
        # default strings like '0.0001'
        parts = re.sub(r'0+$', '', str).split('.')
        return len(parts[1]) if len(parts) > 1 else 0

    def map_to_safe_map(self, dictionary):
        return dictionary  # wrapper for go

    def safe_map_to_map(self, dictionary):
        return dictionary  # wrapper for go

    def load_markets(self, reload=False, params={}):
        """
        Loads and prepares the markets for trading.

        Args:
            reload (bool): If True, the markets will be reloaded from the exchange.
            params (dict): Additional exchange-specific parameters for the request.

        Returns:
            dict: A dictionary of markets.

        Raises:
            Exception: If the markets cannot be loaded or prepared.

        Notes:
            It ensures that the markets are only loaded once, even if called multiple times.
            If the markets are already loaded and `reload` is False or not provided, it returns the existing markets.
            If a reload is in progress, it waits for completion before returning.
            If an error occurs during loading or preparation, an exception is raised.
        """
        if not reload:
            if self.markets:
                if not self.markets_by_id:
                    return self.set_markets(self.markets)
                return self.markets
        currencies = None
        if self.has['fetchCurrencies'] is True:
            currencies = self.fetch_currencies()
            self.options['cachedCurrencies'] = currencies
        markets = self.fetch_markets(params)
        if 'cachedCurrencies' in self.options:
            del self.options['cachedCurrencies']
        return self.set_markets(markets, currencies)

    def fetch_markets(self, params={}):
        """Fetch all available markets from the exchange.

        :param dict params: Extra parameters for the exchange API
        :returns list: List of market structures with symbol, base, quote, limits, etc.
        """
        # markets are returned as a list
        # currencies are returned as a dict
        # this is for historical reasons
        # and may be changed for consistency later
        return self.to_array(self.markets)

    def fetch_currencies(self, params={}):
        # markets are returned as a list
        # currencies are returned as a dict
        # this is for historical reasons
        # and may be changed for consistency later
        return self.currencies

    def fetch_fees(self):
        trading = {}
        funding = {}
        if self.has['fetchTradingFees']:
            trading = self.fetch_trading_fees()
        if self.has['fetchFundingFees']:
            funding = self.fetch_funding_fees()
        return {
            'trading': trading,
            'funding': funding,
        }

    @staticmethod
    def parse_timeframe(timeframe):
        amount = int(timeframe[0:-1])
        unit = timeframe[-1]
        if 'y' == unit:
            scale = 60 * 60 * 24 * 365
        elif 'M' == unit:
            scale = 60 * 60 * 24 * 30
        elif 'w' == unit:
            scale = 60 * 60 * 24 * 7
        elif 'd' == unit:
            scale = 60 * 60 * 24
        elif 'h' == unit:
            scale = 60 * 60
        elif 'm' == unit:
            scale = 60
        elif 's' == unit:
            scale = 1
        else:
            raise NotSupported('timeframe unit {} is not supported'.format(unit))
        return amount * scale

    @staticmethod
    def round_timeframe(timeframe, timestamp, direction=ROUND_DOWN):
        ms = Exchange.parse_timeframe(timeframe) * 1000
        # Get offset based on timeframe in milliseconds
        offset = timestamp % ms
        return timestamp - offset + (ms if direction == ROUND_UP else 0)


    @staticmethod
    def binary_to_base16(s):
        return Exchange.decode(base64.b16encode(s)).lower()

    def sleep(self, milliseconds):
        return time.sleep(milliseconds / 1000)

    def parse_number(self, value, default=None):
        if value is None:
            return default
        else:
            try:
                return self.number(value)
            except Exception:
                return default

    def omit_zero(self, string_number):
        try:
            if string_number is None or string_number == '':
                return None
            if float(string_number) == 0:
                return None
            return string_number
        except Exception:
            return string_number

    def check_order_arguments(self, market, type, side, amount, price, params):
        if price is None:
            if type == 'limit':
                raise ArgumentsRequired(self.id + ' create_order() requires a price argument for a limit order')
        if amount <= 0:
            raise InvalidOrder(self.id + ' create_order() amount should be above 0')

    def handle_http_status_code(self, code, reason, url, method, body):
        codeAsString = str(code)
        if codeAsString in self.httpExceptions:
            ErrorClass = self.httpExceptions[codeAsString]
            raise ErrorClass(self.id + ' ' + method + ' ' + url + ' ' + codeAsString + ' ' + reason + ' ' + body)


    # def delete_key_from_dictionary(self, dictionary, key):
    #     newDictionary = self.clone(dictionary)
    #     del newDictionary[key]
    #     return newDictionary

    # def set_object_property(obj, prop, value):
    #     obj[prop] = value

    def value_is_defined(self, value):
        return value is not None

    def array_slice(self, array, first, second=None):
        return array[first:second] if second else array[first:]

    # METHODS BELOW THIS LINE ARE TRANSPILED FROM TYPESCRIPT

    def describe(self) -> Any:
        # Most defaults live as class-level attributes (id, name, rateLimit,
        # timeout, certified, pro, alias, requiredCredentials, fees,
        # httpExceptions, commonCurrencies, limits, precisionMode, paddingMode,
        # etc.).  Only values that subclasses commonly override via
        # deep_extend(super().describe(), {...}) need to appear here.
        return {
            'id': None,
            'name': None,
            'countries': None,
            'dex': False,
            'has': {
                'publicAPI': True,
                'privateAPI': True,
                'cancelOrder': True,
                'createLimitOrder': True,
                'createMarketOrder': True,
                'createOrder': True,
                'fetchBalance': True,
                'fetchL2OrderBook': True,
                'fetchMarkets': True,
                'fetchOrderBook': True,
                'fetchTicker': True,
                'fetchTrades': True,
            },
            'urls': {
                'logo': None,
                'api': None,
                'www': None,
                'doc': None,
            },
            'api': None,
            'status': {
                'status': 'ok',
                'updated': None,
                'eta': None,
                'url': None,
            },
        }

    def safe_bool_n(self, dictionaryOrList, keys: List[IndexType], defaultValue: bool = None):
        """
 @ignore
        safely extract boolean value from dictionary or list
        :returns bool | None:
        """
        value = self.safe_value_n(dictionaryOrList, keys, defaultValue)
        if isinstance(value, bool):
            return value
        return defaultValue

    def safe_bool_2(self, dictionary, key1: IndexType, key2: IndexType, defaultValue: bool = None):
        """
 @ignore
        safely extract boolean value from dictionary or list
        :returns bool | None:
        """
        return self.safe_bool_n(dictionary, [key1, key2], defaultValue)

    def safe_bool(self, dictionary, key: IndexType, defaultValue: bool = None):
        """
 @ignore
        safely extract boolean value from dictionary or list
        :returns bool | None:
        """
        return self.safe_bool_n(dictionary, [key], defaultValue)

    def safe_dict_n(self, dictionaryOrList, keys: List[IndexType], defaultValue: dict = None):
        """
 @ignore
        safely extract a dictionary from dictionary or list
        :returns dict | None:
        """
        value = self.safe_value_n(dictionaryOrList, keys, defaultValue)
        if value is None:
            return defaultValue
        if isinstance(value, dict):
            return value
        return defaultValue

    def safe_dict(self, dictionary, key: IndexType, defaultValue: dict = None):
        """
 @ignore
        safely extract a dictionary from dictionary or list
        :returns dict | None:
        """
        return self.safe_dict_n(dictionary, [key], defaultValue)

    def safe_dict_2(self, dictionary, key1: IndexType, key2: str, defaultValue: dict = None):
        """
 @ignore
        safely extract a dictionary from dictionary or list
        :returns dict | None:
        """
        return self.safe_dict_n(dictionary, [key1, key2], defaultValue)

    def safe_list_n(self, dictionaryOrList, keys: List[IndexType], defaultValue: List[Any] = None):
        """
 @ignore
        safely extract an Array from dictionary or list
        :returns Array | None:
        """
        value = self.safe_value_n(dictionaryOrList, keys, defaultValue)
        if value is None:
            return defaultValue
        if isinstance(value, list):
            return value
        return defaultValue

    def safe_list_2(self, dictionaryOrList, key1: IndexType, key2: str, defaultValue: List[Any] = None):
        """
 @ignore
        safely extract an Array from dictionary or list
        :returns Array | None:
        """
        return self.safe_list_n(dictionaryOrList, [key1, key2], defaultValue)

    def safe_list(self, dictionaryOrList, key: IndexType, defaultValue: List[Any] = None):
        """
 @ignore
        safely extract an Array from dictionary or list
        :returns Array | None:
        """
        return self.safe_list_n(dictionaryOrList, [key], defaultValue)

    def handle_deltas(self, orderbook, deltas):
        for i in range(0, len(deltas)):
            self.handle_delta(orderbook, deltas[i])

    def handle_delta(self, bookside, delta):
        raise NotSupported(self.id + ' handleDelta not supported yet')

    def handle_deltas_with_keys(self, bookSide: Any, deltas, priceKey: IndexType = 0, amountKey: IndexType = 1, countOrIdKey: IndexType = 2):
        for i in range(0, len(deltas)):
            bidAsk = self.parse_bid_ask(deltas[i], priceKey, amountKey, countOrIdKey)
            bookSide.storeArray(bidAsk)

    def get_cache_index(self, orderbook, deltas):
        # return the first index of the cache that can be applied to the orderbook or -1 if not possible.
        return -1

    def arrays_concat(self, arraysOfArrays: List[Any]):
        result = []
        for i in range(0, len(arraysOfArrays)):
            result = self.array_concat(result, arraysOfArrays[i])
        return result

    def find_timeframe(self, timeframe, timeframes=None):
        if timeframes is None:
            timeframes = self.timeframes
        keys = list(timeframes.keys())
        for i in range(0, len(keys)):
            key = keys[i]
            if timeframes[key] == timeframe:
                return key
        return None

    def check_proxy_url_settings(self, url: Str = None, method: Str = None, headers=None, body=None):
        usedProxies = []
        proxyUrl = None
        if self.proxyUrl is not None:
            usedProxies.append('proxyUrl')
            proxyUrl = self.proxyUrl
        if self.proxy_url is not None:
            usedProxies.append('proxy_url')
            proxyUrl = self.proxy_url
        if self.proxyUrlCallback is not None:
            usedProxies.append('proxyUrlCallback')
            proxyUrl = self.proxyUrlCallback(url, method, headers, body)
        if self.proxy_url_callback is not None:
            usedProxies.append('proxy_url_callback')
            proxyUrl = self.proxy_url_callback(url, method, headers, body)
        # backwards-compatibility
        if self.proxy is not None:
            usedProxies.append('proxy')
            if callable(self.proxy):
                proxyUrl = self.proxy(url, method, headers, body)
            else:
                proxyUrl = self.proxy
        length = len(usedProxies)
        if length > 1:
            joinedProxyNames = ','.join(usedProxies)
            raise InvalidProxySettings(self.id + ' you have multiple conflicting proxy settings(' + joinedProxyNames + '), please use only one from : proxyUrl, proxy_url, proxyUrlCallback, proxy_url_callback')
        return proxyUrl

    def url_encoder_for_proxy_url(self, targetUrl: str):
        # to be overriden
        includesQuery = targetUrl.find('?') >= 0
        finalUrl = self.encode_uri_component(targetUrl) if includesQuery else targetUrl
        return finalUrl

    def check_proxy_settings(self, url: Str = None, method: Str = None, headers=None, body=None):
        usedProxies = []
        httpProxy = None
        httpsProxy = None
        socksProxy = None
        # httpProxy
        isHttpProxyDefined = self.value_is_defined(self.httpProxy)
        isHttp_proxy_defined = self.value_is_defined(self.http_proxy)
        if isHttpProxyDefined or isHttp_proxy_defined:
            usedProxies.append('httpProxy')
            httpProxy = self.httpProxy if isHttpProxyDefined else self.http_proxy
        ishttpProxyCallbackDefined = self.value_is_defined(self.httpProxyCallback)
        ishttp_proxy_callback_defined = self.value_is_defined(self.http_proxy_callback)
        if ishttpProxyCallbackDefined or ishttp_proxy_callback_defined:
            usedProxies.append('httpProxyCallback')
            httpProxy = self.httpProxyCallback(url, method, headers, body) if ishttpProxyCallbackDefined else self.http_proxy_callback(url, method, headers, body)
        # httpsProxy
        isHttpsProxyDefined = self.value_is_defined(self.httpsProxy)
        isHttps_proxy_defined = self.value_is_defined(self.https_proxy)
        if isHttpsProxyDefined or isHttps_proxy_defined:
            usedProxies.append('httpsProxy')
            httpsProxy = self.httpsProxy if isHttpsProxyDefined else self.https_proxy
        ishttpsProxyCallbackDefined = self.value_is_defined(self.httpsProxyCallback)
        ishttps_proxy_callback_defined = self.value_is_defined(self.https_proxy_callback)
        if ishttpsProxyCallbackDefined or ishttps_proxy_callback_defined:
            usedProxies.append('httpsProxyCallback')
            httpsProxy = self.httpsProxyCallback(url, method, headers, body) if ishttpsProxyCallbackDefined else self.https_proxy_callback(url, method, headers, body)
        # socksProxy
        isSocksProxyDefined = self.value_is_defined(self.socksProxy)
        isSocks_proxy_defined = self.value_is_defined(self.socks_proxy)
        if isSocksProxyDefined or isSocks_proxy_defined:
            usedProxies.append('socksProxy')
            socksProxy = self.socksProxy if isSocksProxyDefined else self.socks_proxy
        issocksProxyCallbackDefined = self.value_is_defined(self.socksProxyCallback)
        issocks_proxy_callback_defined = self.value_is_defined(self.socks_proxy_callback)
        if issocksProxyCallbackDefined or issocks_proxy_callback_defined:
            usedProxies.append('socksProxyCallback')
            socksProxy = self.socksProxyCallback(url, method, headers, body) if issocksProxyCallbackDefined else self.socks_proxy_callback(url, method, headers, body)
        # check
        length = len(usedProxies)
        if length > 1:
            joinedProxyNames = ','.join(usedProxies)
            raise InvalidProxySettings(self.id + ' you have multiple conflicting proxy settings(' + joinedProxyNames + '), please use only one from: httpProxy, httpsProxy, httpProxyCallback, httpsProxyCallback, socksProxy, socksProxyCallback')
        return [httpProxy, httpsProxy, socksProxy]

    def check_conflicting_proxies(self, proxyAgentSet, proxyUrlSet):
        if proxyAgentSet and proxyUrlSet:
            raise InvalidProxySettings(self.id + ' you have multiple conflicting proxy settings, please use only one from : proxyUrl, httpProxy, httpsProxy, socksProxy')


    def filter_by_limit(self, array: List[object], limit: Int = None, key: IndexType = 'timestamp', fromStart: bool = False):
        if self.value_is_defined(limit):
            arrayLength = len(array)
            if arrayLength > 0:
                ascending = True
                if (key in array[0]):
                    first = array[0][key]
                    last = array[arrayLength - 1][key]
                    if first is not None and last is not None:
                        ascending = first <= last  # True if array is sorted in ascending order based on 'timestamp'
                if fromStart:
                    if limit > arrayLength:
                        limit = arrayLength
                    # array = self.array_slice(array, 0, limit) if ascending else self.array_slice(array, -limit)
                    if ascending:
                        array = self.array_slice(array, 0, limit)
                    else:
                        array = self.array_slice(array, -limit)
                else:
                    # array = self.array_slice(array, -limit) if ascending else self.array_slice(array, 0, limit)
                    if ascending:
                        array = self.array_slice(array, -limit)
                    else:
                        array = self.array_slice(array, 0, limit)
        return array

    def filter_by_since_limit(self, array: List[object], since: Int = None, limit: Int = None, key: IndexType = 'timestamp', tail=False):
        sinceIsDefined = self.value_is_defined(since)
        parsedArray = self.to_array(array)
        result = parsedArray
        if sinceIsDefined:
            result = []
            for i in range(0, len(parsedArray)):
                entry = parsedArray[i]
                value = self.safe_value(entry, key)
                if value and (value >= since):
                    result.append(entry)
        if tail and limit is not None:
            return self.array_slice(result, -limit)
        # if the user provided a 'since' argument
        # we want to limit the result starting from the 'since'
        shouldFilterFromStart = not tail and sinceIsDefined
        return self.filter_by_limit(result, limit, key, shouldFilterFromStart)

    def filter_by_value_since_limit(self, array: List[object], field: IndexType, value=None, since: Int = None, limit: Int = None, key='timestamp', tail=False):
        valueIsDefined = self.value_is_defined(value)
        sinceIsDefined = self.value_is_defined(since)
        parsedArray = self.to_array(array)
        result = parsedArray
        # single-pass filter for both symbol and since
        if valueIsDefined or sinceIsDefined:
            result = []
            for i in range(0, len(parsedArray)):
                entry = parsedArray[i]
                entryFiledEqualValue = entry[field] == value
                firstCondition = entryFiledEqualValue if valueIsDefined else True
                entryKeyValue = self.safe_value(entry, key)
                entryKeyGESince = (entryKeyValue) and (since is not None) and (entryKeyValue >= since)
                secondCondition = entryKeyGESince if sinceIsDefined else True
                if firstCondition and secondCondition:
                    result.append(entry)
        if tail and limit is not None:
            return self.array_slice(result, -limit)
        return self.filter_by_limit(result, limit, key, sinceIsDefined)

    def set_sandbox_mode(self, enabled: bool):
        """
        set the sandbox mode for the exchange
        :param boolean enabled: True to enable sandbox mode, False to disable it
        """
        if enabled:
            if 'test' in self.urls:
                if isinstance(self.urls['api'], str):
                    self.urls['apiBackup'] = self.urls['api']
                    self.urls['api'] = self.urls['test']
                else:
                    self.urls['apiBackup'] = self.clone(self.urls['api'])
                    self.urls['api'] = self.clone(self.urls['test'])
            else:
                raise NotSupported(self.id + ' does not have a sandbox URL')
            # set flag
            self.isSandboxModeEnabled = True
        elif 'apiBackup' in self.urls:
            if isinstance(self.urls['api'], str):
                self.urls['api'] = self.urls['apiBackup']
            else:
                self.urls['api'] = self.clone(self.urls['apiBackup'])
            newUrls = self.omit(self.urls, 'apiBackup')
            self.urls = newUrls
            # set flag
            self.isSandboxModeEnabled = False


    def sign(self, path, api: Any = 'public', method='GET', params={}, headers: Any = None, body: Any = None):
        return {}

    def fetch_accounts(self, params={}):
        raise NotSupported(self.id + ' fetchAccounts() is not supported yet')

    def fetch_trades(self, symbol: str, since: Int = None, limit: Int = None, params={}):
        raise NotSupported(self.id + ' fetchTrades() is not supported yet')


    def fetch_deposit_addresses(self, codes: Strings = None, params={}):
        raise NotSupported(self.id + ' fetchDepositAddresses() is not supported yet')

    def fetch_order_book(self, symbol: str, limit: Int = None, params={}):
        """Fetch L2 order book for a symbol.

        :param str symbol: Trading pair symbol (e.g. 'ETH/USDC')
        :param int|None limit: Number of order book entries per side to return
        :param dict params: Extra parameters for the exchange API
        :returns dict: Order book with bids, asks, timestamp, and nonce
        """
        raise NotSupported(self.id + ' fetchOrderBook() is not supported yet')


    def fetch_rest_order_book_safe(self, symbol, limit=None, params={}):
        fetchSnapshotMaxRetries = self.handle_option('watchOrderBook', 'maxRetries', 3)
        for i in range(0, fetchSnapshotMaxRetries):
            try:
                orderBook = self.fetch_order_book(symbol, limit, params)
                return orderBook
            except Exception as e:
                if (i + 1) == fetchSnapshotMaxRetries:
                    raise e
        return None


    def fetch_time(self, params={}):
        raise NotSupported(self.id + ' fetchTime() is not supported yet')

    def fetch_trading_limits(self, symbols: Strings = None, params={}):
        raise NotSupported(self.id + ' fetchTradingLimits() is not supported yet')

    def parse_currency(self, rawCurrency: dict):
        raise NotSupported(self.id + ' parseCurrency() is not supported yet')


    def parse_market(self, market: dict):
        raise NotSupported(self.id + ' parseMarket() is not supported yet')

    def parse_markets(self, markets):
        result = []
        for i in range(0, len(markets)):
            result.append(self.parse_market(markets[i]))
        return result

    def parse_ticker(self, ticker: dict, market: Market = None):
        raise NotSupported(self.id + ' parseTicker() is not supported yet')

    def parse_deposit_address(self, depositAddress, currency: Currency = None):
        raise NotSupported(self.id + ' parseDepositAddress() is not supported yet')

    def parse_trade(self, trade: dict, market: Market = None):
        raise NotSupported(self.id + ' parseTrade() is not supported yet')

    def parse_transaction(self, transaction: dict, currency: Currency = None):
        raise NotSupported(self.id + ' parseTransaction() is not supported yet')


    def parse_account(self, account: dict):
        raise NotSupported(self.id + ' parseAccount() is not supported yet')

    def parse_order(self, order: dict, market: Market = None):
        raise NotSupported(self.id + ' parseOrder() is not supported yet')


    def parse_position(self, position: dict, market: Market = None):
        raise NotSupported(self.id + ' parsePosition() is not supported yet')

    def parse_isolated_borrow_rate(self, info: dict, market: Market = None):
        raise NotSupported(self.id + ' parseIsolatedBorrowRate() is not supported yet')

    def parse_ws_trade(self, trade: dict, market: Market = None):
        raise NotSupported(self.id + ' parseWsTrade() is not supported yet')


    def parse_ws_ohlcv(self, ohlcv, market: Market = None):
        return self.parse_ohlcv(ohlcv, market)

    def fetch_funding_rates(self, symbols: Strings = None, params={}):
        raise NotSupported(self.id + ' fetchFundingRates() is not supported yet')


    def withdraw(self, code: str, amount: float, address: str, tag: Str = None, params={}):
        raise NotSupported(self.id + ' withdraw() is not supported yet')


    def set_leverage(self, leverage: int, symbol: Str = None, params={}):
        raise NotSupported(self.id + ' setLeverage() is not supported yet')


    def fetch_leverage(self, symbol: str, params={}):
        if self.has['fetchLeverages']:
            leverages = self.fetch_leverages([symbol], params)
            return self.safe_dict(leverages, symbol)
        else:
            raise NotSupported(self.id + ' fetchLeverage() is not supported yet')

    def fetch_leverages(self, symbols: Strings = None, params={}):
        raise NotSupported(self.id + ' fetchLeverages() is not supported yet')


    def fetch_deposit_addresses_by_network(self, code: str, params={}):
        raise NotSupported(self.id + ' fetchDepositAddressesByNetwork() is not supported yet')

    def fetch_open_interest_history(self, symbol: str, timeframe: str = '1h', since: Int = None, limit: Int = None, params={}):
        raise NotSupported(self.id + ' fetchOpenInterestHistory() is not supported yet')

    def fetch_open_interest(self, symbol: str, params={}):
        raise NotSupported(self.id + ' fetchOpenInterest() is not supported yet')


    def parse_to_int(self, number):
        # Solve Common intmisuse ex: int((since / str(1000)))
        # using a number which is not valid in ts
        stringifiedNumber = self.number_to_string(number)
        convertedNumber = float(stringifiedNumber)
        return int(convertedNumber)

    def parse_to_numeric(self, number):
        stringVersion = self.number_to_string(number)  # self will convert 1.0 and 1 to "1" and 1.1 to "1.1"
        # keep self in mind:
        # in JS:     1 == 1.0 is True
        # in Python: 1 == 1.0 is True
        # in PHP:    1 == 1.0 is True, but 1 == 1.0 is False.
        if stringVersion.find('.') >= 0:
            return float(stringVersion)
        return int(stringVersion)

    def is_round_number(self, value: float):
        # self method is similar to isInteger, but self is more loyal and does not check for types.
        # i.e. isRoundNumber(1.000) returns True, while isInteger(1.000) returns False
        res = self.parse_to_numeric((value % 1))
        return res == 0

    def safe_number_omit_zero(self, obj: object, key: IndexType, defaultValue: Num = None):
        value = self.safe_string(obj, key)
        final = self.parse_number(self.omit_zero(value))
        return defaultValue if (final is None) else final

    def safe_integer_omit_zero(self, obj: object, key: IndexType, defaultValue: Int = None):
        timestamp = self.safe_integer(obj, key, defaultValue)
        if timestamp is None or timestamp == 0:
            return None
        return timestamp

    def after_construct(self):
        # networks
        self.create_networks_by_id_object()
        self.features_generator()
        # init predefined markets if any
        if self.markets:
            self.set_markets(self.markets)
        # init the request rate limiter
        self.init_rest_rate_limiter()
        # sanbox mode
        isSandbox = self.safe_bool_2(self.options, 'sandbox', 'testnet', False)
        if isSandbox:
            self.set_sandbox_mode(isSandbox)

    def init_rest_rate_limiter(self):
        if self.rateLimit is None or (self.id is not None and self.rateLimit == -1):
            raise ExchangeError(self.id + '.rateLimit property is not configured')
        refillRate = self.MAX_VALUE
        if self.rateLimit > 0:
            refillRate = 1 / self.rateLimit
        useLeaky = (self.rollingWindowSize == 0.0) or (self.rateLimiterAlgorithm == 'leakyBucket')
        algorithm = 'leakyBucket' if useLeaky else 'rollingWindow'
        defaultBucket = {
            'delay': 0.001,
            'capacity': 1,
            'cost': 1,
            'refillRate': refillRate,
            'algorithm': algorithm,
            'windowSize': self.rollingWindowSize,
            'rateLimit': self.rateLimit,
        }
        existingBucket = {} if (self.tokenBucket is None) else self.tokenBucket
        self.tokenBucket = self.extend(defaultBucket, existingBucket)
        self.init_throttler()

    def features_generator(self):
        #
        # in the exchange-specific features can be something like self, where we support 'string' aliases too:
        #
        #     {
        #         'my' : {
        #             'createOrder' : {...},
        #         },
        #         'swap': {
        #             'linear': {
        #                 'extends': my',
        #             },
        #         },
        #     }
        #
        if self.features is None:
            return
        # reconstruct
        initialFeatures = self.features
        self.features = {}
        unifiedMarketTypes = ['spot', 'swap', 'future', 'option']
        subTypes = ['linear', 'inverse']
        # atm only support basic methods, eg: 'createOrder', 'fetchOrder', 'fetchOrders', 'fetchMyTrades'
        for i in range(0, len(unifiedMarketTypes)):
            marketType = unifiedMarketTypes[i]
            # if marketType is not filled for self exchange, don't add that in `features`
            if not (marketType in initialFeatures):
                self.features[marketType] = None
            else:
                if marketType == 'spot':
                    self.features[marketType] = self.features_mapper(initialFeatures, marketType, None)
                else:
                    self.features[marketType] = {}
                    for j in range(0, len(subTypes)):
                        subType = subTypes[j]
                        self.features[marketType][subType] = self.features_mapper(initialFeatures, marketType, subType)

    def features_mapper(self, initialFeatures: Any, marketType: Str, subType: Str = None):
        featuresObj = initialFeatures[marketType][subType] if (subType is not None) else initialFeatures[marketType]
        # if exchange does not have that market-type(eg. future>inverse)
        if featuresObj is None:
            return None
        extendsStr: Str = self.safe_string(featuresObj, 'extends')
        if extendsStr is not None:
            featuresObj = self.omit(featuresObj, 'extends')
            extendObj = self.features_mapper(initialFeatures, extendsStr)
            featuresObj = self.deep_extend(extendObj, featuresObj)
        #
        #  ### corrections  ###
        #
        # createOrder
        if 'createOrder' in featuresObj:
            value = self.safe_dict(featuresObj['createOrder'], 'attachedStopLossTakeProfit')
            featuresObj['createOrder']['stopLoss'] = value
            featuresObj['createOrder']['takeProfit'] = value
            if marketType == 'spot':
                # default 'hedged': False
                featuresObj['createOrder']['hedged'] = False
                # default 'leverage': False
                if not ('leverage' in featuresObj['createOrder']):
                    featuresObj['createOrder']['leverage'] = False
            # default 'GTC' to True
            if self.safe_bool(featuresObj['createOrder']['timeInForce'], 'GTC') is None:
                featuresObj['createOrder']['timeInForce']['GTC'] = True
        # other methods
        keys = list(featuresObj.keys())
        for i in range(0, len(keys)):
            key = keys[i]
            featureBlock = featuresObj[key]
            if not self.in_array(key, ['sandbox']) and featureBlock is not None:
                # default "symbolRequired" to False to all methods(except `createOrder`)
                if not ('symbolRequired' in featureBlock):
                    featureBlock['symbolRequired'] = self.in_array(key, ['createOrder', 'createOrders', 'fetchOHLCV'])
        return featuresObj


    def create_networks_by_id_object(self):
        # automatically generate network-id-to-code mappings
        networkIdsToCodesGenerated = self.invert_flat_string_dictionary(self.safe_value(self.options, 'networks', {}))  # invert defined networks dictionary
        self.options['networksById'] = self.extend(networkIdsToCodesGenerated, self.safe_value(self.options, 'networksById', {}))  # support manually overriden "networksById" dictionary too

    def get_default_options(self):
        return {
            'defaultNetworkCodeReplacements': {
                'ETH': {'ERC20': 'ETH'},
                'TRX': {'TRC20': 'TRX'},
                'CRO': {'CRC20': 'CRONOS'},
                'BRC20': {'BRC20': 'BTC'},
            },
        }

    def safe_currency_structure(self, currency: object):
        # derive data from networks: deposit, withdraw, active, fee, limits, precision
        networks = self.safe_dict(currency, 'networks', {})
        keys = list(networks.keys())
        length = len(keys)
        if length != 0:
            for i in range(0, length):
                key = keys[i]
                network = networks[key]
                deposit = self.safe_bool(network, 'deposit')
                currencyDeposit = self.safe_bool(currency, 'deposit')
                if currencyDeposit is None or deposit:
                    currency['deposit'] = deposit
                withdraw = self.safe_bool(network, 'withdraw')
                currencyWithdraw = self.safe_bool(currency, 'withdraw')
                if currencyWithdraw is None or withdraw:
                    currency['withdraw'] = withdraw
                # set network 'active' to False if D or W is disabled
                active = self.safe_bool(network, 'active')
                if active is None:
                    if deposit and withdraw:
                        currency['networks'][key]['active'] = True
                    elif deposit is not None and withdraw is not None:
                        currency['networks'][key]['active'] = False
                active = self.safe_bool(currency['networks'][key], 'active')  # dict might have been updated on above lines, so access directly instead of `network` variable
                currencyActive = self.safe_bool(currency, 'active')
                if currencyActive is None or active:
                    currency['active'] = active
                # find lowest fee(which is more desired)
                fee = self.safe_string(network, 'fee')
                feeMain = self.safe_string(currency, 'fee')
                if feeMain is None or Precise.string_lt(fee, feeMain):
                    currency['fee'] = self.parse_number(fee)
                # find lowest precision(which is more desired)
                precision = self.safe_string(network, 'precision')
                precisionMain = self.safe_string(currency, 'precision')
                if precisionMain is None or Precise.string_gt(precision, precisionMain):
                    currency['precision'] = self.parse_number(precision)
                # limits
                limits = self.safe_dict(network, 'limits')
                limitsMain = self.safe_dict(currency, 'limits')
                if limitsMain is None:
                    currency['limits'] = {}
                # deposits
                limitsDeposit = self.safe_dict(limits, 'deposit')
                limitsDepositMain = self.safe_dict(limitsMain, 'deposit')
                if limitsDepositMain is None:
                    currency['limits']['deposit'] = {}
                limitsDepositMin = self.safe_string(limitsDeposit, 'min')
                limitsDepositMax = self.safe_string(limitsDeposit, 'max')
                limitsDepositMinMain = self.safe_string(limitsDepositMain, 'min')
                limitsDepositMaxMain = self.safe_string(limitsDepositMain, 'max')
                # find min
                if limitsDepositMinMain is None or Precise.string_lt(limitsDepositMin, limitsDepositMinMain):
                    currency['limits']['deposit']['min'] = self.parse_number(limitsDepositMin)
                # find max
                if limitsDepositMaxMain is None or Precise.string_gt(limitsDepositMax, limitsDepositMaxMain):
                    currency['limits']['deposit']['max'] = self.parse_number(limitsDepositMax)
                # withdrawals
                limitsWithdraw = self.safe_dict(limits, 'withdraw')
                limitsWithdrawMain = self.safe_dict(limitsMain, 'withdraw')
                if limitsWithdrawMain is None:
                    currency['limits']['withdraw'] = {}
                limitsWithdrawMin = self.safe_string(limitsWithdraw, 'min')
                limitsWithdrawMax = self.safe_string(limitsWithdraw, 'max')
                limitsWithdrawMinMain = self.safe_string(limitsWithdrawMain, 'min')
                limitsWithdrawMaxMain = self.safe_string(limitsWithdrawMain, 'max')
                # find min
                if limitsWithdrawMinMain is None or Precise.string_lt(limitsWithdrawMin, limitsWithdrawMinMain):
                    currency['limits']['withdraw']['min'] = self.parse_number(limitsWithdrawMin)
                # find max
                if limitsWithdrawMaxMain is None or Precise.string_gt(limitsWithdrawMax, limitsWithdrawMaxMain):
                    currency['limits']['withdraw']['max'] = self.parse_number(limitsWithdrawMax)
        return self.extend({
            'info': None,
            'id': None,
            'numericId': None,
            'code': None,
            'precision': None,
            'type': None,
            'name': None,
            'active': None,
            'deposit': None,
            'withdraw': None,
            'fee': None,
            'fees': {},
            'networks': {},
            'limits': {
                'deposit': {
                    'min': None,
                    'max': None,
                },
                'withdraw': {
                    'min': None,
                    'max': None,
                },
            },
        }, currency)

    def safe_market_structure(self, market: dict = None):
        cleanStructure = {
            'id': None,
            'lowercaseId': None,
            'symbol': None,
            'base': None,
            'quote': None,
            'settle': None,
            'baseId': None,
            'quoteId': None,
            'settleId': None,
            'type': None,
            'spot': None,
            'margin': None,
            'swap': None,
            'future': None,
            'option': None,
            'index': None,
            'active': None,
            'contract': None,
            'linear': None,
            'inverse': None,
            'subType': None,
            'taker': None,
            'maker': None,
            'contractSize': None,
            'expiry': None,
            'expiryDatetime': None,
            'strike': None,
            'optionType': None,
            'precision': {
                'amount': None,
                'price': None,
                'cost': None,
                'base': None,
                'quote': None,
            },
            'limits': {
                'leverage': {
                    'min': None,
                    'max': None,
                },
                'amount': {
                    'min': None,
                    'max': None,
                },
                'price': {
                    'min': None,
                    'max': None,
                },
                'cost': {
                    'min': None,
                    'max': None,
                },
            },
            'marginModes': {
                'cross': None,
                'isolated': None,
            },
            'created': None,
            'info': None,
        }
        if market is not None:
            result = self.extend(cleanStructure, market)
            # set None swap/future/etc
            if result['spot']:
                if result['contract'] is None:
                    result['contract'] = False
                if result['swap'] is None:
                    result['swap'] = False
                if result['future'] is None:
                    result['future'] = False
                if result['option'] is None:
                    result['option'] = False
                if result['index'] is None:
                    result['index'] = False
            return result
        return cleanStructure

    def set_markets(self, markets, currencies=None):
        values = []
        self.markets_by_id = self.create_safe_dictionary()
        # handle marketId conflicts
        # we insert spot markets first
        marketValues = self.sort_by(self.to_array(markets), 'spot', True, True)
        for i in range(0, len(marketValues)):
            value = marketValues[i]
            if value['id'] in self.markets_by_id:
                marketsByIdArray = (self.markets_by_id[value['id']])
                marketsByIdArray.append(value)
                self.markets_by_id[value['id']] = marketsByIdArray
            else:
                self.markets_by_id[value['id']] = [value]
            market = self.deep_extend(self.safe_market_structure(), {
                'precision': self.precision,
                'limits': self.limits,
            }, self.fees['trading'], value)
            if market['linear']:
                market['subType'] = 'linear'
            elif market['inverse']:
                market['subType'] = 'inverse'
            else:
                market['subType'] = None
            values.append(market)
        self.markets = self.map_to_safe_map(self.index_by(values, 'symbol'))
        marketsSortedBySymbol = self.keysort(self.markets)
        marketsSortedById = self.keysort(self.markets_by_id)
        self.symbols = list(marketsSortedBySymbol.keys())
        self.ids = list(marketsSortedById.keys())
        numCurrencies = 0
        if currencies is not None:
            keys = list(currencies.keys())
            numCurrencies = len(keys)
        if numCurrencies > 0:
            # currencies is always None when called in constructor but not when called from loadMarkets
            self.currencies = self.map_to_safe_map(self.deep_extend(self.currencies, currencies))
        else:
            baseCurrencies = []
            quoteCurrencies = []
            for i in range(0, len(values)):
                market = values[i]
                defaultCurrencyPrecision = 8 if (self.precisionMode == DECIMAL_PLACES) else self.parse_number('1e-8')
                marketPrecision = self.safe_dict(market, 'precision', {})
                if 'base' in market:
                    currency = self.safe_currency_structure({
                        'id': self.safe_string_2(market, 'baseId', 'base'),
                        'numericId': self.safe_integer(market, 'baseNumericId'),
                        'code': self.safe_string(market, 'base'),
                        'precision': self.safe_value_2(marketPrecision, 'base', 'amount', defaultCurrencyPrecision),
                    })
                    baseCurrencies.append(currency)
                if 'quote' in market:
                    currency = self.safe_currency_structure({
                        'id': self.safe_string_2(market, 'quoteId', 'quote'),
                        'numericId': self.safe_integer(market, 'quoteNumericId'),
                        'code': self.safe_string(market, 'quote'),
                        'precision': self.safe_value_2(marketPrecision, 'quote', 'price', defaultCurrencyPrecision),
                    })
                    quoteCurrencies.append(currency)
            baseCurrencies = self.sort_by(baseCurrencies, 'code', False, '')
            quoteCurrencies = self.sort_by(quoteCurrencies, 'code', False, '')
            self.baseCurrencies = self.map_to_safe_map(self.index_by(baseCurrencies, 'code'))
            self.quoteCurrencies = self.map_to_safe_map(self.index_by(quoteCurrencies, 'code'))
            allCurrencies = self.array_concat(baseCurrencies, quoteCurrencies)
            groupedCurrencies = self.group_by(allCurrencies, 'code')
            codes = list(groupedCurrencies.keys())
            resultingCurrencies = []
            for i in range(0, len(codes)):
                code = codes[i]
                groupedCurrenciesCode = self.safe_list(groupedCurrencies, code, [])
                highestPrecisionCurrency = self.safe_value(groupedCurrenciesCode, 0)
                for j in range(1, len(groupedCurrenciesCode)):
                    currentCurrency = groupedCurrenciesCode[j]
                    if self.precisionMode == TICK_SIZE:
                        highestPrecisionCurrency = currentCurrency if (currentCurrency['precision'] < highestPrecisionCurrency['precision']) else highestPrecisionCurrency
                    else:
                        highestPrecisionCurrency = currentCurrency if (currentCurrency['precision'] > highestPrecisionCurrency['precision']) else highestPrecisionCurrency
                resultingCurrencies.append(highestPrecisionCurrency)
            sortedCurrencies = self.sort_by(resultingCurrencies, 'code')
            self.currencies = self.map_to_safe_map(self.deep_extend(self.currencies, self.index_by(sortedCurrencies, 'code')))
        self.currencies_by_id = self.index_by_safe(self.currencies, 'id')
        currenciesSortedByCode = self.keysort(self.currencies)
        self.codes = list(currenciesSortedByCode.keys())
        return self.markets


    def safe_balance(self, balance: dict):
        balances = self.omit(balance, ['info', 'timestamp', 'datetime', 'free', 'used', 'total'])
        codes = list(balances.keys())
        balance['free'] = {}
        balance['used'] = {}
        balance['total'] = {}
        debtBalance = {}
        for i in range(0, len(codes)):
            code = codes[i]
            total = self.safe_string(balance[code], 'total')
            free = self.safe_string(balance[code], 'free')
            used = self.safe_string(balance[code], 'used')
            debt = self.safe_string(balance[code], 'debt')
            if (total is None) and (free is not None) and (used is not None):
                total = Precise.string_add(free, used)
            if (free is None) and (total is not None) and (used is not None):
                free = Precise.string_sub(total, used)
            if (used is None) and (total is not None) and (free is not None):
                used = Precise.string_sub(total, free)
            balance[code]['free'] = self.parse_number(free)
            balance[code]['used'] = self.parse_number(used)
            balance[code]['total'] = self.parse_number(total)
            balance['free'][code] = balance[code]['free']
            balance['used'][code] = balance[code]['used']
            balance['total'][code] = balance[code]['total']
            if debt is not None:
                balance[code]['debt'] = self.parse_number(debt)
                debtBalance[code] = balance[code]['debt']
        debtBalanceArray = list(debtBalance.keys())
        length = len(debtBalanceArray)
        if length:
            balance['debt'] = debtBalance
        return balance

    def safe_order(self, order: dict, market: Market = None):
        # parses numbers
        # * it is important pass the trades rawTrades
        amount = self.omit_zero(self.safe_string(order, 'amount'))
        remaining = self.safe_string(order, 'remaining')
        filled = self.safe_string(order, 'filled')
        cost = self.safe_string(order, 'cost')
        average = self.omit_zero(self.safe_string(order, 'average'))
        price = self.omit_zero(self.safe_string(order, 'price'))
        lastTradeTimeTimestamp = self.safe_integer(order, 'lastTradeTimestamp')
        symbol = self.safe_string(order, 'symbol')
        side = self.safe_string(order, 'side')
        status = self.safe_string(order, 'status')
        parseFilled = (filled is None)
        parseCost = (cost is None)
        parseLastTradeTimeTimestamp = (lastTradeTimeTimestamp is None)
        fee = self.safe_value(order, 'fee')
        parseFee = (fee is None)
        parseFees = self.safe_value(order, 'fees') is None
        parseSymbol = symbol is None
        parseSide = side is None
        shouldParseFees = parseFee or parseFees
        fees = self.safe_list(order, 'fees', [])
        trades = []
        isTriggerOrSLTpOrder = ((self.safe_string(order, 'triggerPrice') is not None or (self.safe_string(order, 'stopLossPrice') is not None)) or (self.safe_string(order, 'takeProfitPrice') is not None))
        if parseFilled or parseCost or shouldParseFees:
            rawTrades = self.safe_value(order, 'trades', trades)
            # oldNumber = self.number
            # we parse trades here!
            # i don't think self is needed anymore
            # self.number = str
            firstTrade = self.safe_value(rawTrades, 0)
            # parse trades if they haven't already been parsed
            tradesAreParsed = ((firstTrade is not None) and ('info' in firstTrade) and ('id' in firstTrade))
            if not tradesAreParsed:
                trades = self.parse_trades(rawTrades, market)
            else:
                trades = rawTrades
            # self.number = oldNumber; why parse trades if you read the value using `safeString` ?
            tradesLength = 0
            isArray = isinstance(trades, list)
            if isArray:
                tradesLength = len(trades)
            if isArray and (tradesLength > 0):
                # move properties that are defined in trades up into the order
                if order['symbol'] is None:
                    order['symbol'] = trades[0]['symbol']
                if order['side'] is None:
                    order['side'] = trades[0]['side']
                if order['type'] is None:
                    order['type'] = trades[0]['type']
                if order['id'] is None:
                    order['id'] = trades[0]['order']
                if parseFilled:
                    filled = '0'
                if parseCost:
                    cost = '0'
                for i in range(0, len(trades)):
                    trade = trades[i]
                    tradeAmount = self.safe_string(trade, 'amount')
                    if parseFilled and (tradeAmount is not None):
                        filled = Precise.string_add(filled, tradeAmount)
                    tradeCost = self.safe_string(trade, 'cost')
                    if parseCost and (tradeCost is not None):
                        cost = Precise.string_add(cost, tradeCost)
                    if parseSymbol:
                        symbol = self.safe_string(trade, 'symbol')
                    if parseSide:
                        side = self.safe_string(trade, 'side')
                    tradeTimestamp = self.safe_value(trade, 'timestamp')
                    if parseLastTradeTimeTimestamp and (tradeTimestamp is not None):
                        if lastTradeTimeTimestamp is None:
                            lastTradeTimeTimestamp = tradeTimestamp
                        else:
                            lastTradeTimeTimestamp = max(lastTradeTimeTimestamp, tradeTimestamp)
                    if shouldParseFees:
                        tradeFees = self.safe_value(trade, 'fees')
                        if tradeFees is not None:
                            for j in range(0, len(tradeFees)):
                                tradeFee = tradeFees[j]
                                fees.append(self.extend({}, tradeFee))
                        else:
                            tradeFee = self.safe_value(trade, 'fee')
                            if tradeFee is not None:
                                fees.append(self.extend({}, tradeFee))
        if shouldParseFees:
            reducedFees = self.reduce_fees_by_currency(fees) if self.reduceFees else fees
            reducedLength = len(reducedFees)
            for i in range(0, reducedLength):
                reducedFees[i]['cost'] = self.safe_number(reducedFees[i], 'cost')
                if 'rate' in reducedFees[i]:
                    reducedFees[i]['rate'] = self.safe_number(reducedFees[i], 'rate')
            if not parseFee and (reducedLength == 0):
                # copy fee to avoid modification by reference
                feeCopy = self.deep_extend(fee)
                feeCopy['cost'] = self.safe_number(feeCopy, 'cost')
                if 'rate' in feeCopy:
                    feeCopy['rate'] = self.safe_number(feeCopy, 'rate')
                reducedFees.append(feeCopy)
            order['fees'] = reducedFees
            if parseFee and (reducedLength == 1):
                order['fee'] = reducedFees[0]
        if amount is None:
            # ensure amount = filled + remaining
            if filled is not None and remaining is not None:
                amount = Precise.string_add(filled, remaining)
            elif status == 'closed':
                amount = filled
        if filled is None:
            if amount is not None and remaining is not None:
                filled = Precise.string_sub(amount, remaining)
            elif status == 'closed' and amount is not None:
                filled = amount
        if remaining is None:
            if amount is not None and filled is not None:
                remaining = Precise.string_sub(amount, filled)
            elif status == 'closed':
                remaining = '0'
        # ensure that the average field is calculated correctly
        inverse = self.safe_bool(market, 'inverse', False)
        contractSize = self.number_to_string(self.safe_value(market, 'contractSize', 1))
        # inverse
        # price = filled * contract size / cost
        #
        # linear
        # price = cost / (filled * contract size)
        if average is None:
            if (filled is not None) and (cost is not None) and Precise.string_gt(filled, '0'):
                filledTimesContractSize = Precise.string_mul(filled, contractSize)
                if inverse:
                    average = Precise.string_div(filledTimesContractSize, cost)
                else:
                    average = Precise.string_div(cost, filledTimesContractSize)
        # similarly
        # inverse
        # cost = filled * contract size / price
        #
        # linear
        # cost = filled * contract size * price
        costPriceExists = (average is not None) or (price is not None)
        if parseCost and (filled is not None) and costPriceExists:
            multiplyPrice = None
            if average is None:
                multiplyPrice = price
            else:
                multiplyPrice = average
            # contract trading
            filledTimesContractSize = Precise.string_mul(filled, contractSize)
            if inverse:
                cost = Precise.string_div(filledTimesContractSize, multiplyPrice)
            else:
                cost = Precise.string_mul(filledTimesContractSize, multiplyPrice)
        # support for market orders
        orderType = self.safe_value(order, 'type')
        emptyPrice = (price is None) or Precise.string_equals(price, '0')
        if emptyPrice and (orderType == 'market'):
            price = average
        # we have trades with string values at self point so we will mutate them
        for i in range(0, len(trades)):
            entry = trades[i]
            entry['amount'] = self.safe_number(entry, 'amount')
            entry['price'] = self.safe_number(entry, 'price')
            entry['cost'] = self.safe_number(entry, 'cost')
            tradeFee = self.safe_dict(entry, 'fee', {})
            tradeFee['cost'] = self.safe_number(tradeFee, 'cost')
            if 'rate' in tradeFee:
                tradeFee['rate'] = self.safe_number(tradeFee, 'rate')
            entryFees = self.safe_list(entry, 'fees', [])
            for j in range(0, len(entryFees)):
                entryFees[j]['cost'] = self.safe_number(entryFees[j], 'cost')
            entry['fees'] = entryFees
            entry['fee'] = tradeFee
        timeInForce = self.safe_string(order, 'timeInForce')
        postOnly = self.safe_value(order, 'postOnly')
        # timeInForceHandling
        if timeInForce is None:
            if not isTriggerOrSLTpOrder and (self.safe_string(order, 'type') == 'market'):
                timeInForce = 'IOC'
            # allow postOnly override
            if postOnly:
                timeInForce = 'PO'
        elif postOnly is None:
            # timeInForce is not None here
            postOnly = timeInForce == 'PO'
        timestamp = self.safe_integer(order, 'timestamp')
        lastUpdateTimestamp = self.safe_integer(order, 'lastUpdateTimestamp')
        datetime = self.safe_string(order, 'datetime')
        if datetime is None:
            datetime = self.iso8601(timestamp)
        triggerPrice = self.parse_number(self.safe_string_2(order, 'triggerPrice', 'stopPrice'))
        takeProfitPrice = self.parse_number(self.safe_string(order, 'takeProfitPrice'))
        stopLossPrice = self.parse_number(self.safe_string(order, 'stopLossPrice'))
        return self.extend(order, {
            'id': self.safe_string(order, 'id'),
            'clientOrderId': self.safe_string(order, 'clientOrderId'),
            'timestamp': timestamp,
            'datetime': datetime,
            'symbol': symbol,
            'type': self.safe_string(order, 'type'),
            'side': side,
            'lastTradeTimestamp': lastTradeTimeTimestamp,
            'lastUpdateTimestamp': lastUpdateTimestamp,
            'price': self.parse_number(price),
            'amount': self.parse_number(amount),
            'cost': self.parse_number(cost),
            'average': self.parse_number(average),
            'filled': self.parse_number(filled),
            'remaining': self.parse_number(remaining),
            'timeInForce': timeInForce,
            'postOnly': postOnly,
            'trades': trades,
            'reduceOnly': self.safe_value(order, 'reduceOnly'),
            'stopPrice': triggerPrice,  # ! deprecated, use triggerPrice instead
            'triggerPrice': triggerPrice,
            'takeProfitPrice': takeProfitPrice,
            'stopLossPrice': stopLossPrice,
            'status': status,
            'fee': self.safe_value(order, 'fee'),
        })

    def parse_orders(self, orders: object, market: Market = None, since: Int = None, limit: Int = None, params={}):
        #
        # the value of orders is either a dict or a list
        #
        # dict
        #
        #     {
        #         'id1': {...},
        #         'id2': {...},
        #         'id3': {...},
        #         ...
        #     }
        #
        # list
        #
        #     [
        #         {'id': 'id1', ...},
        #         {'id': 'id2', ...},
        #         {'id': 'id3', ...},
        #         ...
        #     ]
        #
        results = []
        if isinstance(orders, list):
            for i in range(0, len(orders)):
                parsed = self.parse_order(orders[i], market)  # don't inline self call
                order = self.extend(parsed, params)
                results.append(order)
        else:
            ids = list(orders.keys())
            for i in range(0, len(ids)):
                id = ids[i]
                idExtended = self.extend({'id': id}, orders[id])
                parsedOrder = self.parse_order(idExtended, market)  # don't  inline these calls
                order = self.extend(parsedOrder, params)
                results.append(order)
        results = self.sort_by(results, 'timestamp')
        symbol = market['symbol'] if (market is not None) else None
        return self.filter_by_symbol_since_limit(results, symbol, since, limit)


    def safe_liquidation(self, liquidation: dict, market: Market = None):
        contracts = self.safe_string(liquidation, 'contracts')
        contractSize = self.safe_string(market, 'contractSize')
        price = self.safe_string(liquidation, 'price')
        baseValue = self.safe_string(liquidation, 'baseValue')
        quoteValue = self.safe_string(liquidation, 'quoteValue')
        if (baseValue is None) and (contracts is not None) and (contractSize is not None) and (price is not None):
            baseValue = Precise.string_mul(contracts, contractSize)
        if (quoteValue is None) and (baseValue is not None) and (price is not None):
            quoteValue = Precise.string_mul(baseValue, price)
        liquidation['contracts'] = self.parse_number(contracts)
        liquidation['contractSize'] = self.parse_number(contractSize)
        liquidation['price'] = self.parse_number(price)
        liquidation['baseValue'] = self.parse_number(baseValue)
        liquidation['quoteValue'] = self.parse_number(quoteValue)
        return liquidation

    def safe_trade(self, trade: dict, market: Market = None):
        amount = self.safe_string(trade, 'amount')
        price = self.safe_string(trade, 'price')
        cost = self.safe_string(trade, 'cost')
        if cost is None:
            # contract trading
            contractSize = self.safe_string(market, 'contractSize')
            multiplyPrice = price
            if contractSize is not None:
                inverse = self.safe_bool(market, 'inverse', False)
                if inverse:
                    multiplyPrice = Precise.string_div('1', price)
                multiplyPrice = Precise.string_mul(multiplyPrice, contractSize)
            cost = Precise.string_mul(multiplyPrice, amount)
        resultFee, resultFees = self.parsed_fee_and_fees(trade)
        trade['fee'] = resultFee
        trade['fees'] = resultFees
        trade['amount'] = self.parse_number(amount)
        trade['price'] = self.parse_number(price)
        trade['cost'] = self.parse_number(cost)
        return trade

    def create_synthetic_trade_id(self, timestamp=None, side=None, amount=None, price=None, takerOrMaker=None):
        # self approach is being used by multiple exchanges(mexc, woo, coinsbit, dydx, ...)
        id = None
        if timestamp is not None:
            id = self.number_to_string(timestamp)
            if side is not None:
                id += '-' + side
            if amount is not None:
                id += '-' + self.number_to_string(amount)
            if price is not None:
                id += '-' + self.number_to_string(price)
            if takerOrMaker is not None:
                id += '-' + takerOrMaker
        return id

    def parsed_fee_and_fees(self, container: Any):
        fee = self.safe_dict(container, 'fee')
        fees = self.safe_list(container, 'fees')
        feeDefined = fee is not None
        feesDefined = fees is not None
        # parsing only if at least one of them is defined
        shouldParseFees = (feeDefined or feesDefined)
        if shouldParseFees:
            if feeDefined:
                fee = self.parse_fee_numeric(fee)
            if not feesDefined:
                # just set it directly, no further processing needed.
                fees = [fee]
            # 'fees' were set, so reparse them
            reducedFees = self.reduce_fees_by_currency(fees) if self.reduceFees else fees
            reducedLength = len(reducedFees)
            for i in range(0, reducedLength):
                reducedFees[i] = self.parse_fee_numeric(reducedFees[i])
            fees = reducedFees
            if reducedLength == 1:
                fee = reducedFees[0]
            elif reducedLength == 0:
                fee = None
        # in case `fee & fees` are None, set `fees` array
        if fee is None:
            fee = {
                'cost': None,
                'currency': None,
            }
        if fees is None:
            fees = []
        return [fee, fees]

    def parse_fee_numeric(self, fee: Any):
        fee['cost'] = self.safe_number(fee, 'cost')  # ensure numeric
        if 'rate' in fee:
            fee['rate'] = self.safe_number(fee, 'rate')
        return fee

    def find_nearest_ceiling(self, arr: List[float], providedValue: float):
        #  i.e. findNearestCeiling([10, 30, 50],  23) returns 30
        length = len(arr)
        for i in range(0, length):
            current = arr[i]
            if providedValue <= current:
                return current
        return arr[length - 1]

    def invert_flat_string_dictionary(self, dict):
        reversed = {}
        keys = list(dict.keys())
        for i in range(0, len(keys)):
            key = keys[i]
            value = dict[key]
            if isinstance(value, str):
                reversed[value] = key
        return reversed

    def reduce_fees_by_currency(self, fees):
        #
        # self function takes a list of fee structures having the following format
        #
        #     string = True
        #
        #     [
        #         {'currency': 'BTC', 'cost': '0.1'},
        #         {'currency': 'BTC', 'cost': '0.2'  },
        #         {'currency': 'BTC', 'cost': '0.2', 'rate': '0.00123'},
        #         {'currency': 'BTC', 'cost': '0.4', 'rate': '0.00123'},
        #         {'currency': 'BTC', 'cost': '0.5', 'rate': '0.00456'},
        #         {'currency': 'USDT', 'cost': '12.3456'},
        #     ]
        #
        #     string = False
        #
        #     [
        #         {'currency': 'BTC', 'cost': 0.1},
        #         {'currency': 'BTC', 'cost': 0.2},
        #         {'currency': 'BTC', 'cost': 0.2, 'rate': 0.00123},
        #         {'currency': 'BTC', 'cost': 0.4, 'rate': 0.00123},
        #         {'currency': 'BTC', 'cost': 0.5, 'rate': 0.00456},
        #         {'currency': 'USDT', 'cost': 12.3456},
        #     ]
        #
        # and returns a reduced fee list, where fees are summed per currency and rate(if any)
        #
        #     string = True
        #
        #     [
        #         {'currency': 'BTC', 'cost': '0.4'  },
        #         {'currency': 'BTC', 'cost': '0.6', 'rate': '0.00123'},
        #         {'currency': 'BTC', 'cost': '0.5', 'rate': '0.00456'},
        #         {'currency': 'USDT', 'cost': '12.3456'},
        #     ]
        #
        #     string  = False
        #
        #     [
        #         {'currency': 'BTC', 'cost': 0.3  },
        #         {'currency': 'BTC', 'cost': 0.6, 'rate': 0.00123},
        #         {'currency': 'BTC', 'cost': 0.5, 'rate': 0.00456},
        #         {'currency': 'USDT', 'cost': 12.3456},
        #     ]
        #
        reduced = {}
        for i in range(0, len(fees)):
            fee = fees[i]
            code = self.safe_string(fee, 'currency')
            feeCurrencyCode = code if (code is not None) else str(i)
            if feeCurrencyCode is not None:
                rate = self.safe_string(fee, 'rate')
                cost = self.safe_string(fee, 'cost')
                if cost is None:
                    # omit None cost, does not make sense, however, don't omit '0' costs, still make sense
                    continue
                if not (feeCurrencyCode in reduced):
                    reduced[feeCurrencyCode] = {}
                rateKey = '' if (rate is None) else rate
                if rateKey in reduced[feeCurrencyCode]:
                    reduced[feeCurrencyCode][rateKey]['cost'] = Precise.string_add(reduced[feeCurrencyCode][rateKey]['cost'], cost)
                else:
                    reduced[feeCurrencyCode][rateKey] = {
                        'currency': code,
                        'cost': cost,
                    }
                    if rate is not None:
                        reduced[feeCurrencyCode][rateKey]['rate'] = rate
        result = []
        feeValues = list(reduced.values())
        for i in range(0, len(feeValues)):
            reducedFeeValues = list(feeValues[i].values())
            result = self.array_concat(result, reducedFeeValues)
        return result

    def safe_ticker(self, ticker: dict, market: Market = None):
        open = self.omit_zero(self.safe_string(ticker, 'open'))
        close = self.omit_zero(self.safe_string_2(ticker, 'close', 'last'))
        change = self.omit_zero(self.safe_string(ticker, 'change'))
        percentage = self.omit_zero(self.safe_string(ticker, 'percentage'))
        average = self.omit_zero(self.safe_string(ticker, 'average'))
        vwap = self.safe_string(ticker, 'vwap')
        baseVolume = self.safe_string(ticker, 'baseVolume')
        quoteVolume = self.safe_string(ticker, 'quoteVolume')
        if vwap is None:
            vwap = Precise.string_div(self.omit_zero(quoteVolume), baseVolume)
        # calculate open
        if change is not None:
            if close is None and average is not None:
                close = Precise.string_add(average, Precise.string_div(change, '2'))
            if open is None and close is not None:
                open = Precise.string_sub(close, change)
        elif percentage is not None:
            if close is None and average is not None:
                openAddClose = Precise.string_mul(average, '2')
                # openAddClose = open * (1 + (100 + percentage)/100)
                denominator = Precise.string_add('2', Precise.string_div(percentage, '100'))
                calcOpen = open if (open is not None) else Precise.string_div(openAddClose, denominator)
                close = Precise.string_mul(calcOpen, Precise.string_add('1', Precise.string_div(percentage, '100')))
            if open is None and close is not None:
                open = Precise.string_div(close, Precise.string_add('1', Precise.string_div(percentage, '100')))
        # change
        if change is None:
            if close is not None and open is not None:
                change = Precise.string_sub(close, open)
            elif close is not None and percentage is not None:
                change = Precise.string_mul(Precise.string_div(percentage, '100'), Precise.string_div(close, '100'))
            elif open is not None and percentage is not None:
                change = Precise.string_mul(open, Precise.string_div(percentage, '100'))
        # calculate things according to "open"(similar can be done with "close")
        if open is not None:
            # percentage(using change)
            if percentage is None and change is not None:
                percentage = Precise.string_mul(Precise.string_div(change, open), '100')
            # close(using change)
            if close is None and change is not None:
                close = Precise.string_add(open, change)
            # close(using average)
            if close is None and average is not None:
                close = Precise.string_mul(average, '2')
            # average
            if average is None and close is not None:
                precision = 18
                if market is not None and self.is_tick_precision():
                    marketPrecision = self.safe_dict(market, 'precision')
                    precisionPrice = self.safe_string(marketPrecision, 'price')
                    if precisionPrice is not None:
                        precision = self.precision_from_string(precisionPrice)
                average = Precise.string_div(Precise.string_add(open, close), '2', precision)
        # timestamp and symbol operations don't belong in safeTicker
        # they should be done in the derived classes
        closeParsed = self.parse_number(self.omit_zero(close))
        return self.extend(ticker, {
            'bid': self.parse_number(self.omit_zero(self.safe_string(ticker, 'bid'))),
            'bidVolume': self.safe_number(ticker, 'bidVolume'),
            'ask': self.parse_number(self.omit_zero(self.safe_string(ticker, 'ask'))),
            'askVolume': self.safe_number(ticker, 'askVolume'),
            'high': self.parse_number(self.omit_zero(self.safe_string(ticker, 'high'))),
            'low': self.parse_number(self.omit_zero(self.safe_string(ticker, 'low'))),
            'open': self.parse_number(self.omit_zero(open)),
            'close': closeParsed,
            'last': closeParsed,
            'change': self.parse_number(change),
            'percentage': self.parse_number(percentage),
            'average': self.parse_number(average),
            'vwap': self.parse_number(vwap),
            'baseVolume': self.parse_number(baseVolume),
            'quoteVolume': self.parse_number(quoteVolume),
            'previousClose': self.safe_number(ticker, 'previousClose'),
            'indexPrice': self.safe_number(ticker, 'indexPrice'),
            'markPrice': self.safe_number(ticker, 'markPrice'),
        })


    def fetch_ohlcv(self, symbol: str, timeframe: str = '1m', since: Int = None, limit: Int = None, params={}):
        """Fetch OHLCV candles for a symbol.

        :param str symbol: Trading pair symbol (e.g. 'ETH/USDC')
        :param str timeframe: Candle timeframe (e.g. '1m', '5m', '1h', '1d')
        :param int|None since: Timestamp in ms of the earliest candle to fetch
        :param int|None limit: Maximum number of candles to return
        :param dict params: Extra parameters for the exchange API
        :returns list: List of [timestamp, open, high, low, close, volume] arrays
        """
        message = ''
        if self.has['fetchTrades']:
            message = '. You can build OHLCV candles from trade executions data if needed'
        raise NotSupported(self.id + ' fetchOHLCV() is not supported yet' + message)


    def market_ids(self, symbols: Strings = None):
        if symbols is None:
            return symbols
        result = []
        for i in range(0, len(symbols)):
            result.append(self.market_id(symbols[i]))
        return result

    def currency_ids(self, codes: Strings = None):
        if codes is None:
            return codes
        result = []
        for i in range(0, len(codes)):
            result.append(self.currency_id(codes[i]))
        return result

    def markets_for_symbols(self, symbols: Strings = None):
        if symbols is None:
            return symbols
        result = []
        for i in range(0, len(symbols)):
            result.append(self.market(symbols[i]))
        return result

    def market_symbols(self, symbols: Strings = None, type: Str = None, allowEmpty=True, sameTypeOnly=False, sameSubTypeOnly=False):
        if symbols is None:
            if not allowEmpty:
                raise ArgumentsRequired(self.id + ' empty list of symbols is not supported')
            return symbols
        symbolsLength = len(symbols)
        if symbolsLength == 0:
            if not allowEmpty:
                raise ArgumentsRequired(self.id + ' empty list of symbols is not supported')
            return symbols
        result = []
        marketType = None
        isLinearSubType = None
        for i in range(0, len(symbols)):
            market = self.market(symbols[i])
            if sameTypeOnly and (marketType is not None):
                if market['type'] != marketType:
                    raise BadRequest(self.id + ' symbols must be of the same type, either ' + marketType + ' or ' + market['type'] + '.')
            if sameSubTypeOnly and (isLinearSubType is not None):
                if market['linear'] != isLinearSubType:
                    raise BadRequest(self.id + ' symbols must be of the same subType, either linear or inverse.')
            if type is not None and market['type'] != type:
                raise BadRequest(self.id + ' symbols must be of the same type ' + type + '. If the type is incorrect you can change it in options or the params of the request')
            marketType = market['type']
            if not market['spot']:
                isLinearSubType = market['linear']
            symbol = self.safe_string(market, 'symbol', symbols[i])
            result.append(symbol)
        return result

    def market_codes(self, codes: Strings = None):
        if codes is None:
            return codes
        result = []
        for i in range(0, len(codes)):
            result.append(self.common_currency_code(codes[i]))
        return result

    def parse_bids_asks(self, bidasks, priceKey: IndexType = 0, amountKey: IndexType = 1, countOrIdKey: IndexType = 2):
        bidasks = self.to_array(bidasks)
        result = []
        for i in range(0, len(bidasks)):
            result.append(self.parse_bid_ask(bidasks[i], priceKey, amountKey, countOrIdKey))
        return result

    def fetch_l2_order_book(self, symbol: str, limit: Int = None, params={}):
        orderbook = self.fetch_order_book(symbol, limit, params)
        return self.extend(orderbook, {
            'asks': self.sort_by(self.aggregate(orderbook['asks']), 0),
            'bids': self.sort_by(self.aggregate(orderbook['bids']), 0, True),
        })

    def filter_by_symbol(self, objects, symbol: Str = None):
        if symbol is None:
            return objects
        result = []
        for i in range(0, len(objects)):
            objectSymbol = self.safe_string(objects[i], 'symbol')
            if objectSymbol == symbol:
                result.append(objects[i])
        return result

    def parse_ohlcv(self, ohlcv, market: Market = None) -> list:
        if isinstance(ohlcv, list):
            return [
                self.safe_integer(ohlcv, 0),  # timestamp
                self.safe_number(ohlcv, 1),  # open
                self.safe_number(ohlcv, 2),  # high
                self.safe_number(ohlcv, 3),  # low
                self.safe_number(ohlcv, 4),  # close
                self.safe_number(ohlcv, 5),  # volume
            ]
        return ohlcv

    def network_code_to_id(self, networkCode: str, currencyCode: Str = None):
        """
 @ignore
        tries to convert the provided networkCode(which is expected to be an unified network code) to a network id. In order to achieve self, derived class needs to have 'options->networks' defined.
        :param str networkCode: unified network code
        :param str currencyCode: unified currency code, but self argument is not required by default, unless there is an exchange(like huobi) that needs an override of the method to be able to pass currencyCode argument additionally
        :returns str|None: exchange-specific network id
        """
        if networkCode is None:
            return None
        networkIdsByCodes = self.safe_value(self.options, 'networks', {})
        networkId = self.safe_string(networkIdsByCodes, networkCode)
        # for example, if 'ETH' is passed for networkCode, but 'ETH' key not defined in `options->networks` object
        if networkId is None:
            if currencyCode is None:
                currencies = list(self.currencies.values())
                for i in range(0, len(currencies)):
                    currency = currencies[i]
                    networks = self.safe_dict(currency, 'networks')
                    network = self.safe_dict(networks, networkCode)
                    networkId = self.safe_string(network, 'id')
                    if networkId is not None:
                        break
            else:
                # if currencyCode was provided, then we try to find if that currencyCode has a replacement(i.e. ERC20 for ETH) or is in the currency
                defaultNetworkCodeReplacements = self.safe_value(self.options, 'defaultNetworkCodeReplacements', {})
                if currencyCode in defaultNetworkCodeReplacements:
                    # if there is a replacement for the passed networkCode, then we use it to find network-id in `options->networks` object
                    replacementObject = defaultNetworkCodeReplacements[currencyCode]  # i.e. {'ERC20': 'ETH'}
                    keys = list(replacementObject.keys())
                    for i in range(0, len(keys)):
                        key = keys[i]
                        value = replacementObject[key]
                        # if value matches to provided unified networkCode, then we use it's key to find network-id in `options->networks` object
                        if value == networkCode:
                            networkId = self.safe_string(networkIdsByCodes, key)
                            break
                else:
                    # serach for network inside currency
                    currency = self.safe_dict(self.currencies, currencyCode)
                    networks = self.safe_dict(currency, 'networks')
                    network = self.safe_dict(networks, networkCode)
                    networkId = self.safe_string(network, 'id')
            # if it wasn't found, we just set the provided value to network-id
            if networkId is None:
                networkId = networkCode
        return networkId

    def network_id_to_code(self, networkId: Str = None, currencyCode: Str = None):
        """
 @ignore
        tries to convert the provided exchange-specific networkId to an unified network Code. In order to achieve self, derived class needs to have "options['networksById']" defined.
        :param str networkId: exchange specific network id/title, like: TRON, Trc-20, usdt-erc20, etc
        :param str|None currencyCode: unified currency code, but self argument is not required by default, unless there is an exchange(like huobi) that needs an override of the method to be able to pass currencyCode argument additionally
        :returns str|None: unified network code
        """
        if networkId is None:
            return None
        networkCodesByIds = self.safe_dict(self.options, 'networksById', {})
        networkCode = self.safe_string(networkCodesByIds, networkId, networkId)
        # replace mainnet network-codes(i.e. ERC20->ETH)
        if currencyCode is not None:
            defaultNetworkCodeReplacements = self.safe_dict(self.options, 'defaultNetworkCodeReplacements', {})
            if currencyCode in defaultNetworkCodeReplacements:
                replacementObject = self.safe_dict(defaultNetworkCodeReplacements, currencyCode, {})
                networkCode = self.safe_string(replacementObject, networkCode, networkCode)
        return networkCode

    def handle_network_code_and_params(self, params):
        networkCodeInParams = self.safe_string_2(params, 'networkCode', 'network')
        if networkCodeInParams is not None:
            params = self.omit(params, ['networkCode', 'network'])
        # if it was not defined by user, we should not set it from 'defaultNetworks', because handleNetworkCodeAndParams is for only request-side and thus we do not fill it with anything. We can only use 'defaultNetworks' after parsing response-side
        return [networkCodeInParams, params]

    def default_network_code(self, currencyCode: str):
        defaultNetworkCode = None
        defaultNetworks = self.safe_dict(self.options, 'defaultNetworks', {})
        if currencyCode in defaultNetworks:
            # if currency had set its network in "defaultNetworks", use it
            defaultNetworkCode = defaultNetworks[currencyCode]
        else:
            # otherwise, try to use the global-scope 'defaultNetwork' value(even if that network is not supported by currency, it doesn't make any problem, self will be just used "at first" if currency supports self network at all)
            defaultNetwork = self.safe_string(self.options, 'defaultNetwork')
            if defaultNetwork is not None:
                defaultNetworkCode = defaultNetwork
        return defaultNetworkCode


    def safe_number_2(self, dictionary: object, key1: IndexType, key2: IndexType, d=None):
        value = self.safe_string_2(dictionary, key1, key2)
        return self.parse_number(value, d)

    def parse_order_book(self, orderbook: object, symbol: str, timestamp: Int = None, bidsKey='bids', asksKey='asks', priceKey: IndexType = 0, amountKey: IndexType = 1, countOrIdKey: IndexType = 2):
        bids = self.parse_bids_asks(self.safe_value(orderbook, bidsKey, []), priceKey, amountKey, countOrIdKey)
        asks = self.parse_bids_asks(self.safe_value(orderbook, asksKey, []), priceKey, amountKey, countOrIdKey)
        return {
            'symbol': symbol,
            'bids': self.sort_by(bids, 0, True),
            'asks': self.sort_by(asks, 0),
            'timestamp': timestamp,
            'datetime': self.iso8601(timestamp),
            'nonce': None,
        }

    def parse_ohlcvs(self, ohlcvs: List[object], market: Any = None, timeframe: str = '1m', since: Int = None, limit: Int = None, tail: Bool = False):
        results = []
        for i in range(0, len(ohlcvs)):
            results.append(self.parse_ohlcv(ohlcvs[i], market))
        sorted = self.sort_by(results, 0)
        return self.filter_by_since_limit(sorted, since, limit, 0, tail)

    def load_trading_limits(self, symbols: Strings = None, reload=False, params={}):
        if self.has['fetchTradingLimits']:
            if reload or not ('limitsLoaded' in self.options):
                response = self.fetch_trading_limits(symbols)
                for i in range(0, len(symbols)):
                    symbol = symbols[i]
                    self.markets[symbol] = self.deep_extend(self.markets[symbol], response[symbol])
                self.options['limitsLoaded'] = self.milliseconds()
        return self.markets

    def safe_position(self, position: dict):
        # simplified version of: /pull/12765/
        unrealizedPnlString = self.safe_string(position, 'unrealisedPnl')
        initialMarginString = self.safe_string(position, 'initialMargin')
        #
        # PERCENTAGE
        #
        percentage = self.safe_value(position, 'percentage')
        if (percentage is None) and (unrealizedPnlString is not None) and (initialMarginString is not None):
            # was done in all implementations( aax, btcex, bybit, deribit, ftx, gate, kucoinfutures, phemex )
            percentageString = Precise.string_mul(Precise.string_div(unrealizedPnlString, initialMarginString, 4), '100')
            position['percentage'] = self.parse_number(percentageString)
        # if contractSize is None get from market
        contractSize = self.safe_number(position, 'contractSize')
        symbol = self.safe_string(position, 'symbol')
        market = None
        if symbol is not None:
            market = self.safe_value(self.markets, symbol)
        if contractSize is None and market is not None:
            contractSize = self.safe_number(market, 'contractSize')
            position['contractSize'] = contractSize
        return position

    def parse_positions(self, positions: List[Any], symbols: List[str] = None, params={}):
        symbols = self.market_symbols(symbols)
        positions = self.to_array(positions)
        result = []
        for i in range(0, len(positions)):
            position = self.extend(self.parse_position(positions[i], None), params)
            result.append(position)
        return self.filter_by_array_positions(result, 'symbol', symbols, False)


    def parse_trades_helper(self, isWs: bool, trades: List[Any], market: Market = None, since: Int = None, limit: Int = None, params={}):
        trades = self.to_array(trades)
        result = []
        for i in range(0, len(trades)):
            parsed = None
            if isWs:
                parsed = self.parse_ws_trade(trades[i], market)
            else:
                parsed = self.parse_trade(trades[i], market)
            trade = self.extend(parsed, params)
            result.append(trade)
        result = self.sort_by_2(result, 'timestamp', 'id')
        symbol = market['symbol'] if (market is not None) else None
        return self.filter_by_symbol_since_limit(result, symbol, since, limit)

    def parse_trades(self, trades: List[Any], market: Market = None, since: Int = None, limit: Int = None, params={}):
        return self.parse_trades_helper(False, trades, market, since, limit, params)

    def parse_ws_trades(self, trades: List[Any], market: Market = None, since: Int = None, limit: Int = None, params={}):
        return self.parse_trades_helper(True, trades, market, since, limit, params)

    def parse_transactions(self, transactions: List[Any], currency: Currency = None, since: Int = None, limit: Int = None, params={}):
        transactions = self.to_array(transactions)
        result = []
        for i in range(0, len(transactions)):
            transaction = self.extend(self.parse_transaction(transactions[i], currency), params)
            result.append(transaction)
        result = self.sort_by(result, 'timestamp')
        code = currency['code'] if (currency is not None) else None
        return self.filter_by_currency_since_limit(result, code, since, limit)

    def nonce(self):
        return self.seconds()

    def set_headers(self, headers):
        return headers

    def currency_id(self, code: str):
        currency = self.safe_dict(self.currencies, code)
        if currency is None:
            currency = self.safe_currency(code)
        if currency is not None:
            return currency['id']
        return code

    def market_id(self, symbol: str):
        market = self.market(symbol)
        if market is not None:
            return market['id']
        return symbol

    def symbol(self, symbol: str):
        market = self.market(symbol)
        return self.safe_string(market, 'symbol', symbol)

    def handle_param_string(self, params: object, paramName: str, defaultValue: Str = None):
        value = self.safe_string(params, paramName, defaultValue)
        if value is not None:
            params = self.omit(params, paramName)
        return [value, params]

    def resolve_path(self, path, params):
        return [
            self.implode_params(path, params),
            self.omit(params, self.extract_params(path)),
        ]

    def get_list_from_object_values(self, objects, key: IndexType):
        newArray = objects
        if not isinstance(objects, list):
            newArray = self.to_array(objects)
        results = []
        for i in range(0, len(newArray)):
            results.append(newArray[i][key])
        return results

    def get_symbols_for_market_type(self, marketType: Str = None, subType: Str = None, symbolWithActiveStatus: bool = True, symbolWithUnknownStatus: bool = True):
        filteredMarkets = self.markets
        if marketType is not None:
            filteredMarkets = self.filter_by(filteredMarkets, 'type', marketType)
        if subType is not None:
            self.check_required_argument('getSymbolsForMarketType', subType, 'subType', ['linear', 'inverse', 'quanto'])
            filteredMarkets = self.filter_by(filteredMarkets, 'subType', subType)
        activeStatuses = []
        if symbolWithActiveStatus:
            activeStatuses.append(True)
        if symbolWithUnknownStatus:
            activeStatuses.append(None)
        filteredMarkets = self.filter_by_array(filteredMarkets, 'active', activeStatuses, False)
        return self.get_list_from_object_values(filteredMarkets, 'symbol')

    def filter_by_array(self, objects, key: IndexType, values=None, indexed=True):
        objects = self.to_array(objects)
        # return all of them if no values were passed
        if values is None or not values:
            # return self.index_by(objects, key) if indexed else objects
            if indexed:
                return self.index_by(objects, key)
            else:
                return objects
        results = []
        for i in range(0, len(objects)):
            if self.in_array(objects[i][key], values):
                results.append(objects[i])
        # return self.index_by(results, key) if indexed else results
        if indexed:
            return self.index_by(results, key)
        return results

    def fetch2(self, path, api: Any = 'public', method='GET', params={}, headers: Any = None, body: Any = None, config={}):
        if self.enableRateLimit:
            cost = self.calculate_rate_limiter_cost(api, method, path, params, config)
            self.throttle(cost)
        retries = None
        retries, params = self.handle_option_and_params(params, path, 'maxRetriesOnFailure', 0)
        retryDelay = None
        retryDelay, params = self.handle_option_and_params(params, path, 'maxRetriesOnFailureDelay', 0)
        self.lastRestRequestTimestamp = self.milliseconds()
        request = self.sign(path, api, method, params, headers, body)
        self.last_request_headers = request['headers']
        self.last_request_body = request['body']
        self.last_request_url = request['url']
        for i in range(0, retries + 1):
            try:
                return self.fetch(request['url'], request['method'], request['headers'], request['body'])
            except Exception as e:
                if isinstance(e, OperationFailed):
                    if i < retries:
                        if self.verbose:
                            index = i + 1
                            self.log('Request failed with the error: ' + str(e) + ', retrying ' + str(index) + ' of ' + str(retries) + '...')
                        if (retryDelay is not None) and (retryDelay != 0):
                            self.sleep(retryDelay)
                    else:
                        raise e
                else:
                    raise e
        return None  # self line is never reached, but exists for c# value return requirement

    def request(self, path, api: Any = 'public', method='GET', params={}, headers: Any = None, body: Any = None, config={}):
        return self.fetch2(path, api, method, params, headers, body, config)

    def _request(self, endpoint: Entry, params=None, config=None):
        """
        Unified request method for API endpoints

        This method provides a complete request-response lifecycle:
        1. Build request URL and parameters
        2. Sign request if private endpoint
        3. Send HTTP request via fetch2/request
        4. Handle errors (HTTP errors handled by fetch, business errors by parse_error)

        Args:
            endpoint: Entry object defining the API endpoint
            params: Request parameters (query params or body data)
            config: Additional configuration for this request

        Returns:
            Parsed JSON response

        Note:
            - Signing is done via the sign() method (exchange-specific)
            - HTTP errors are handled by fetch() method
            - Business errors are handled by parse_error() if implemented by subclass
        """
        if params is None:
            params = {}

        # 1. Merge endpoint config with custom config
        endpoint_config = endpoint.config if endpoint is not None else {}
        if config:
            endpoint_config = self.extend(endpoint_config, config)

        # 2. Resolve path with parameters (for path parameters like /api/v1/order/{id})
        path = endpoint.path
        if isinstance(params, dict) and self.extract_params(path):
            path, params = self.resolve_path(path, params)

        # 3. Make the request (fetch2 handles rate limiting, signing, and HTTP errors)
        # The sign() method is called inside fetch2 -> request -> sign(path, api, method, params)
        response = self.request(path, endpoint.api, endpoint.method, params, config=endpoint_config)

        # 4. Check for exchange-specific business errors
        # This allows subclasses to implement parse_error() for custom error handling
        if hasattr(self, 'parse_error') and callable(getattr(self, 'parse_error')):
            self.parse_error(response)

        # TODO: Rate limiting improvements
        # - Current implementation uses enableRateLimit flag with throttle()
        # - Future: Implement token bucket or sliding window algorithm
        # - Track request timestamps and costs per endpoint
        # - Reference: token bucket throttle implementation
        # - Priority: Medium (after basic refactor is stable)

        return response

    def load_accounts(self, reload=False, params={}):
        if reload:
            self.accounts = self.fetch_accounts(params)
        else:
            if self.accounts:
                return self.accounts
            else:
                self.accounts = self.fetch_accounts(params)
        self.accountsById = self.index_by(self.accounts, 'id')
        return self.accounts

    def fetch_position(self, symbol: str, params={}):
        raise NotSupported(self.id + ' fetchPosition() is not supported yet')


    def fetch_positions(self, symbols: Strings = None, params={}):
        """Fetch open positions.

        :param list[str]|None symbols: List of symbols to fetch positions for, None for all
        :param dict params: Extra parameters for the exchange API
        :returns list: List of position structures with symbol, side, size, entryPrice, etc.
        """
        raise NotSupported(self.id + ' fetchPositions() is not supported yet')


    def parse_bid_ask(self, bidask, priceKey: IndexType = 0, amountKey: IndexType = 1, countOrIdKey: IndexType = 2):
        price = self.safe_float(bidask, priceKey)
        amount = self.safe_float(bidask, amountKey)
        countOrId = self.safe_integer(bidask, countOrIdKey)
        bidAsk = [price, amount]
        if countOrId is not None:
            bidAsk.append(countOrId)
        return bidAsk

    def safe_currency(self, currencyId: Str, currency: Currency = None):
        if (currencyId is None) and (currency is not None):
            return currency
        if (self.currencies_by_id is not None) and (currencyId in self.currencies_by_id) and (self.currencies_by_id[currencyId] is not None):
            return self.currencies_by_id[currencyId]
        code = currencyId
        if currencyId is not None:
            code = self.common_currency_code(currencyId.upper())
        return self.safe_currency_structure({
            'id': currencyId,
            'code': code,
            'precision': None,
        })

    def safe_market(self, marketId: Str = None, market: Market = None, delimiter: Str = None, marketType: Str = None):
        if marketId is not None:
            if (self.markets_by_id is not None) and (marketId in self.markets_by_id):
                markets = self.markets_by_id[marketId]
                numMarkets = len(markets)
                if numMarkets == 1:
                    return markets[0]
                else:
                    if marketType is None:
                        if market is None:
                            raise ArgumentsRequired(self.id + ' safeMarket() requires a fourth argument for ' + marketId + ' to disambiguate between different markets with the same market id')
                        else:
                            marketType = market['type']
                    for i in range(0, len(markets)):
                        currentMarket = markets[i]
                        if currentMarket[marketType]:
                            return currentMarket
            elif delimiter is not None and delimiter != '':
                parts = marketId.split(delimiter)
                partsLength = len(parts)
                result = self.safe_market_structure({
                    'symbol': marketId,
                    'marketId': marketId,
                })
                if partsLength == 2:
                    result['baseId'] = self.safe_string(parts, 0)
                    result['quoteId'] = self.safe_string(parts, 1)
                    result['base'] = self.safe_currency_code(result['baseId'])
                    result['quote'] = self.safe_currency_code(result['quoteId'])
                    result['symbol'] = result['base'] + '/' + result['quote']
                return result
        if market is not None:
            return market
        return self.safe_market_structure({'symbol': marketId, 'marketId': marketId})

    def market_or_null(self, symbol: Str = None):
        if symbol is None:
            return None
        return self.market(symbol)

    def check_required_credentials(self, error=True):
        """
 @ignore
        :param boolean error: raise an error that a credential is required if True
        :returns boolean: True if all required credentials have been set, otherwise False or an error is thrown is param error=true
        """
        keys = list(self.requiredCredentials.keys())
        for i in range(0, len(keys)):
            key = keys[i]
            if self.requiredCredentials[key] and not getattr(self, key):
                if error:
                    raise AuthenticationError(self.id + ' requires "' + key + '" credential')
                else:
                    return False
        return True


    def fetch_balance(self, params={}):
        """Fetch account balance.

        :param dict params: Extra parameters for the exchange API
        :returns dict: Balance structure with free, used, and total for each currency
        """
        raise NotSupported(self.id + ' fetchBalance() is not supported yet')


    def parse_balance(self, response):
        raise NotSupported(self.id + ' parseBalance() is not supported yet')


    def fetch_partial_balance(self, part, params={}):
        balance = self.fetch_balance(params)
        return balance[part]

    def fetch_free_balance(self, params={}):
        return self.fetch_partial_balance('free', params)

    def fetch_used_balance(self, params={}):
        return self.fetch_partial_balance('used', params)

    def fetch_total_balance(self, params={}):
        return self.fetch_partial_balance('total', params)

    def fetch_status(self, params={}):
        raise NotSupported(self.id + ' fetchStatus() is not supported yet')


    def handle_option_and_params(self, params: object, methodName: str, optionName: str, defaultValue=None):
        # This method can be used to obtain method specific properties, i.e: self.handle_option_and_params(params, 'fetchPosition', 'marginMode', 'isolated')
        defaultOptionName = 'default' + self.capitalize(optionName)  # we also need to check the 'defaultXyzWhatever'
        # check if params contain the key
        value = self.safe_value_2(params, optionName, defaultOptionName)
        if value is not None:
            params = self.omit(params, [optionName, defaultOptionName])
        else:
            # handle routed methods like "watchTrades > watchTradesForSymbols"(or "watchTicker > watchTickers")
            methodName, params = self.handle_param_string(params, 'callerMethodName', methodName)
            # check if exchange has properties for self method
            exchangeWideMethodOptions = self.safe_value(self.options, methodName)
            if exchangeWideMethodOptions is not None:
                # check if the option is defined inside self method's props
                value = self.safe_value_2(exchangeWideMethodOptions, optionName, defaultOptionName)
            if value is None:
                # if it's still None, check if global exchange-wide option exists
                value = self.safe_value_2(self.options, optionName, defaultOptionName)
            # if it's still None, use the default value
            value = value if (value is not None) else defaultValue
        return [value, params]

    def throw_exactly_matched_exception(self, exact, string, message):
        if string is None:
            return
        if string in exact:
            raise exact[string](message)

    def throw_broadly_matched_exception(self, broad, string, message):
        broadKey = self.find_broadly_matched_key(broad, string)
        if broadKey is not None:
            raise broad[broadKey](message)

    def find_broadly_matched_key(self, broad, string):
        # a helper for matching error strings exactly vs broadly
        keys = list(broad.keys())
        for i in range(0, len(keys)):
            key = keys[i]
            if string is not None:  # #issues/12698
                if string.find(key) >= 0:
                    return key
        return None

    def handle_errors(self, statusCode: int, statusText: str, url: str, method: str, responseHeaders: dict, responseBody: str, response, requestHeaders, requestBody):
        # it is a stub method that must be overrided in the derived exchange classes
        # raise NotSupported(self.id + ' handleErrors() not implemented yet')
        return None

    def _handle_http_error(self, status_code: int, status_text: str, url: str, method: str, body: str):
        """
        Unified HTTP error handler for common HTTP status codes

        This method maps standard HTTP status codes to appropriate dext exceptions.
        It provides a first layer of error handling before exchange-specific errors.

        Args:
            status_code: HTTP status code (400, 401, 404, 429, 5xx, etc.)
            status_text: HTTP status text (e.g., "Bad Request")
            url: Request URL
            method: HTTP method (GET, POST, etc.)
            body: Response body

        Raises:
            BadRequest: For 400 errors
            AuthenticationError: For 401/403 errors
            BadSymbol: For 404 errors (typically invalid symbol)
            RateLimitExceeded: For 429 errors
            ExchangeNotAvailable: For 5xx server errors
            ExchangeError: For other unhandled errors

        Note:
            This is called automatically by fetch() when HTTP errors occur.
            Exchange-specific business errors should be handled by parse_error().
        """
        error_details = f"{self.id} {method} {url} {status_code} {status_text} {body}"

        if status_code == 400:
            raise BadRequest(error_details)
        elif status_code == 401 or status_code == 403:
            raise AuthenticationError(error_details)
        elif status_code == 404:
            raise BadSymbol(error_details)
        elif status_code == 429:
            raise RateLimitExceeded(error_details)
        elif status_code >= 500:
            raise ExchangeNotAvailable(error_details)
        else:
            # Fallback to the existing handle_http_status_code for other codes
            self.handle_http_status_code(status_code, status_text, url, method, body)

    def calculate_rate_limiter_cost(self, api, method, path, params, config={}):
        return self.safe_value(config, 'cost', 1)

    def fetch_ticker(self, symbol: str, params={}):
        """Fetch latest ticker data for a trading pair.

        :param str symbol: Trading pair symbol (e.g. 'ETH/USDC')
        :param dict params: Extra parameters for the exchange API
        :returns dict: Ticker with bid, ask, last, volume, etc.
        """
        if self.has['fetchTickers']:
            self.load_markets()
            market = self.market(symbol)
            symbol = market['symbol']
            tickers = self.fetch_tickers([symbol], params)
            ticker = self.safe_dict(tickers, symbol)
            if ticker is None:
                raise NullResponse(self.id + ' fetchTickers() could not find a ticker for ' + symbol)
            else:
                return ticker
        else:
            raise NotSupported(self.id + ' fetchTicker() is not supported yet')


    def fetch_tickers(self, symbols: Strings = None, params={}):
        """Fetch tickers for multiple symbols.

        :param list[str]|None symbols: List of symbols to fetch, None for all
        :param dict params: Extra parameters for the exchange API
        :returns dict: Dictionary of symbol to ticker structure
        """
        raise NotSupported(self.id + ' fetchTickers() is not supported yet')


    def fetch_order(self, id: str, symbol: Str = None, params={}):
        """Fetch a single order by ID.

        :param str id: Order ID
        :param str|None symbol: Trading pair symbol (required by some exchanges)
        :param dict params: Extra parameters for the exchange API
        :returns dict: Order structure with id, status, symbol, type, side, price, amount, etc.
        """
        raise NotSupported(self.id + ' fetchOrder() is not supported yet')

    def fetch_order_with_client_order_id(self, clientOrderId: str, symbol: Str = None, params={}):
        """
        create a market order by providing the symbol, side and cost
        :param str clientOrderId: client order Id
        :param str symbol: unified symbol of the market to create an order in
        :param dict [params]: extra parameters specific to the exchange API endpoint
        :returns dict: a standardized order structure
        """
        extendedParams = self.extend(params, {'clientOrderId': clientOrderId})
        return self.fetch_order('', symbol, extendedParams)


    def fetch_order_status(self, id: str, symbol: Str = None, params={}):
        # TODO: TypeScript: change method signature by replacing
        # Promise<string> with Promise<Order['status']>.
        order = self.fetch_order(id, symbol, params)
        return order['status']

    def fetch_unified_order(self, order, params={}):
        return self.fetch_order(self.safe_string(order, 'id'), self.safe_string(order, 'symbol'), params)

    def create_order(self, symbol: str, type: OrderType, side: OrderSide, amount: float, price: Num = None, params={}):
        """Create a new order.

        :param str symbol: Trading pair symbol (e.g. 'ETH/USDC')
        :param str type: Order type ('limit' or 'market')
        :param str side: Order side ('buy' or 'sell')
        :param float amount: Order amount in base currency
        :param float|None price: Order price (required for limit orders)
        :param dict params: Extra parameters for the exchange API
        :returns dict: Order structure with id, status, symbol, type, side, price, amount, etc.
        """
        raise NotSupported(self.id + ' createOrder() is not supported yet')


    def create_orders(self, orders: List[OrderRequest], params={}):
        raise NotSupported(self.id + ' createOrders() is not supported yet')

    def cancel_order(self, id: str, symbol: Str = None, params={}):
        """Cancel an order by ID.

        :param str id: Order ID to cancel
        :param str|None symbol: Trading pair symbol (required by some exchanges)
        :param dict params: Extra parameters for the exchange API
        :returns dict: Order structure of the canceled order
        """
        raise NotSupported(self.id + ' cancelOrder() is not supported yet')

    def cancel_orders(self, ids: List[str], symbol: Str = None, params={}):
        raise NotSupported(self.id + ' cancelOrders() is not supported yet')

    def cancel_all_orders(self, symbol: Str = None, params={}):
        """Cancel all open orders for a symbol.

        :param str|None symbol: Trading pair symbol, None to cancel all orders
        :param dict params: Extra parameters for the exchange API
        :returns list: List of canceled order structures
        """
        raise NotSupported(self.id + ' cancelAllOrders() is not supported yet')


    def fetch_orders(self, symbol: Str = None, since: Int = None, limit: Int = None, params={}):
        if self.has['fetchOpenOrders'] and self.has['fetchClosedOrders']:
            raise NotSupported(self.id + ' fetchOrders() is not supported yet, consider using fetchOpenOrders() and fetchClosedOrders() instead')
        raise NotSupported(self.id + ' fetchOrders() is not supported yet')


    def fetch_open_orders(self, symbol: Str = None, since: Int = None, limit: Int = None, params={}):
        """Fetch all open orders.

        :param str|None symbol: Trading pair symbol to filter by, None for all
        :param int|None since: Timestamp in ms of the earliest order to fetch
        :param int|None limit: Maximum number of orders to return
        :param dict params: Extra parameters for the exchange API
        :returns list: List of open order structures
        """
        if self.has['fetchOrders']:
            orders = self.fetch_orders(symbol, since, limit, params)
            return self.filter_by(orders, 'status', 'open')
        raise NotSupported(self.id + ' fetchOpenOrders() is not supported yet')


    def fetch_my_trades(self, symbol: Str = None, since: Int = None, limit: Int = None, params={}):
        raise NotSupported(self.id + ' fetchMyTrades() is not supported yet')


    def fetch_deposits(self, code: Str = None, since: Int = None, limit: Int = None, params={}):
        raise NotSupported(self.id + ' fetchDeposits() is not supported yet')

    def fetch_withdrawals(self, code: Str = None, since: Int = None, limit: Int = None, params={}):
        raise NotSupported(self.id + ' fetchWithdrawals() is not supported yet')


    def fetch_funding_rate_history(self, symbol: Str = None, since: Int = None, limit: Int = None, params={}):
        raise NotSupported(self.id + ' fetchFundingRateHistory() is not supported yet')

    def fetch_funding_history(self, symbol: Str = None, since: Int = None, limit: Int = None, params={}):
        raise NotSupported(self.id + ' fetchFundingHistory() is not supported yet')

    def close_position(self, symbol: str, side: OrderSide = None, params={}):
        raise NotSupported(self.id + ' closePosition() is not supported yet')


    def fetch_l3_order_book(self, symbol: str, limit: Int = None, params={}):
        raise BadRequest(self.id + ' fetchL3OrderBook() is not supported yet')


    def fetch_deposit_address(self, code: str, params={}):
        if self.has['fetchDepositAddresses']:
            depositAddresses = self.fetch_deposit_addresses([code], params)
            depositAddress = self.safe_value(depositAddresses, code)
            if depositAddress is None:
                raise InvalidAddress(self.id + ' fetchDepositAddress() could not find a deposit address for ' + code + ', make sure you have created a corresponding deposit address in your wallet on the exchange website')
            else:
                return depositAddress
        elif self.has['fetchDepositAddressesByNetwork']:
            network = self.safe_string(params, 'network')
            params = self.omit(params, 'network')
            addressStructures = self.fetch_deposit_addresses_by_network(code, params)
            if network is not None:
                return self.safe_dict(addressStructures, network)
            else:
                keys = list(addressStructures.keys())
                key = self.safe_string(keys, 0)
                return self.safe_dict(addressStructures, key)
        else:
            raise NotSupported(self.id + ' fetchDepositAddress() is not supported yet')

    def account(self) -> BalanceAccount:
        return {
            'free': None,
            'used': None,
            'total': None,
        }

    def common_currency_code(self, code: str):
        if not self.substituteCommonCurrencyCodes:
            return code
        return self.safe_string(self.commonCurrencies, code, code)

    def currency(self, code: str):
        keys = list(self.currencies.keys())
        numCurrencies = len(keys)
        if numCurrencies == 0:
            raise ExchangeError(self.id + ' currencies not loaded')
        if isinstance(code, str):
            if code in self.currencies:
                return self.currencies[code]
            elif code in self.currencies_by_id:
                return self.currencies_by_id[code]
        raise ExchangeError(self.id + ' does not have currency code ' + code)

    def market(self, symbol: str):
        if self.markets is None:
            raise ExchangeError(self.id + ' markets not loaded')
        if symbol in self.markets:
            return self.markets[symbol]
        elif symbol in self.markets_by_id:
            markets = self.markets_by_id[symbol]
            defaultType = self.safe_string_2(self.options, 'defaultType', 'defaultSubType', 'spot')
            for i in range(0, len(markets)):
                market = markets[i]
                if market[defaultType]:
                    return market
            return markets[0]
        raise BadSymbol(self.id + ' does not have market symbol ' + symbol)


    def is_leveraged_currency(self, currencyCode, checkBaseCoin: Bool = False, existingCurrencies: dict = None):
        leverageSuffixes = [
            '2L', '2S', '3L', '3S', '4L', '4S', '5L', '5S',  # Leveraged Tokens(LT)
            'UP', 'DOWN',  # exchange-specific(e.g. BLVT)
            'BULL', 'BEAR',  # similar
        ]
        for i in range(0, len(leverageSuffixes)):
            leverageSuffix = leverageSuffixes[i]
            if currencyCode.endswith(leverageSuffix):
                if not checkBaseCoin:
                    return True
                else:
                    # check if base currency is inside dict
                    baseCurrencyCode = currencyCode.replace(leverageSuffix, '')
                    if baseCurrencyCode in existingCurrencies:
                        return True
        return False

    def handle_withdraw_tag_and_params(self, tag, params):
        if (tag is not None) and (isinstance(tag, dict)):
            params = self.extend(tag, params)
            tag = None
        if tag is None:
            tag = self.safe_string(params, 'tag')
            if tag is not None:
                params = self.omit(params, 'tag')
        return [tag, params]

    def create_limit_order(self, symbol: str, side: OrderSide, amount: float, price: float, params={}):
        return self.create_order(symbol, 'limit', side, amount, price, params)

    def create_market_order(self, symbol: str, side: OrderSide, amount: float, price: Num = None, params={}):
        return self.create_order(symbol, 'market', side, amount, price, params)

    def cost_to_precision(self, symbol: str, cost):
        if cost is None:
            return None
        market = self.market(symbol)
        return self.decimal_to_precision(cost, TRUNCATE, market['precision']['price'], self.precisionMode, self.paddingMode)

    def price_to_precision(self, symbol: str, price):
        if price is None:
            return None
        market = self.market(symbol)
        result = self.decimal_to_precision(price, ROUND, market['precision']['price'], self.precisionMode, self.paddingMode)
        if result == '0':
            raise InvalidOrder(self.id + ' price of ' + market['symbol'] + ' must be greater than minimum price precision of ' + self.number_to_string(market['precision']['price']))
        return result

    def amount_to_precision(self, symbol: str, amount):
        if amount is None:
            return None
        market = self.market(symbol)
        result = self.decimal_to_precision(amount, TRUNCATE, market['precision']['amount'], self.precisionMode, self.paddingMode)
        if result == '0':
            raise InvalidOrder(self.id + ' amount of ' + market['symbol'] + ' must be greater than minimum amount precision of ' + self.number_to_string(market['precision']['amount']))
        return result

    def fee_to_precision(self, symbol: str, fee):
        if fee is None:
            return None
        market = self.market(symbol)
        return self.decimal_to_precision(fee, ROUND, market['precision']['price'], self.precisionMode, self.paddingMode)

    def currency_to_precision(self, code: str, fee, networkCode=None):
        currency = self.currencies[code]
        precision = self.safe_value(currency, 'precision')
        if networkCode is not None:
            networks = self.safe_dict(currency, 'networks', {})
            networkItem = self.safe_dict(networks, networkCode, {})
            precision = self.safe_value(networkItem, 'precision', precision)
        if precision is None:
            return self.force_string(fee)
        else:
            roundingMode = self.safe_integer(self.options, 'currencyToPrecisionRoundingMode', ROUND)
            return self.decimal_to_precision(fee, roundingMode, precision, self.precisionMode, self.paddingMode)

    def force_string(self, value):
        if not isinstance(value, str):
            return self.number_to_string(value)
        return value

    def is_tick_precision(self):
        return self.precisionMode == TICK_SIZE

    def is_decimal_precision(self):
        return self.precisionMode == DECIMAL_PLACES

    def is_significant_precision(self):
        return self.precisionMode == SIGNIFICANT_DIGITS

    def safe_number(self, obj, key: IndexType, defaultNumber: Num = None):
        value = self.safe_string(obj, key)
        return self.parse_number(value, defaultNumber)

    def safe_number_n(self, obj: object, arr: List[IndexType], defaultNumber: Num = None):
        value = self.safe_string_n(obj, arr)
        return self.parse_number(value, defaultNumber)

    def parse_precision(self, precision: str):
        """
 @ignore
        :param str precision: The number of digits to the right of the decimal
        :returns str: a string number equal to 1e-precision
        """
        if precision is None:
            return None
        precisionNumber = int(precision)
        if precisionNumber == 0:
            return '1'
        if precisionNumber > 0:
            parsedPrecision = '0.'
            for i in range(0, precisionNumber - 1):
                parsedPrecision = parsedPrecision + '0'
            return parsedPrecision + '1'
        else:
            parsedPrecision = '1'
            for i in range(0, precisionNumber * -1 - 1):
                parsedPrecision = parsedPrecision + '0'
            return parsedPrecision + '0'

    def integer_precision_to_amount(self, precision: Str):
        """
 @ignore
        handles positive & negative numbers too. parsePrecision() does not handle negative numbers, but self method handles
        :param str precision: The number of digits to the right of the decimal
        :returns str: a string number equal to 1e-precision
        """
        if precision is None:
            return None
        if Precise.string_ge(precision, '0'):
            return self.parse_precision(precision)
        else:
            positivePrecisionString = Precise.string_abs(precision)
            positivePrecision = int(positivePrecisionString)
            parsedPrecision = '1'
            for i in range(0, positivePrecision - 1):
                parsedPrecision = parsedPrecision + '0'
            return parsedPrecision + '0'

    def load_time_difference(self, params={}):
        serverTime = self.fetch_time(params)
        after = self.milliseconds()
        self.options['timeDifference'] = after - serverTime
        return self.options['timeDifference']

    def implode_hostname(self, url: str):
        return self.implode_params(url, {'hostname': self.hostname})


    def safe_currency_code(self, currencyId: Str, currency: Currency = None):
        currency = self.safe_currency(currencyId, currency)
        return currency['code']

    def filter_by_symbol_since_limit(self, array, symbol: Str = None, since: Int = None, limit: Int = None, tail=False):
        return self.filter_by_value_since_limit(array, 'symbol', symbol, since, limit, 'timestamp', tail)

    def filter_by_currency_since_limit(self, array, code=None, since: Int = None, limit: Int = None, tail=False):
        return self.filter_by_value_since_limit(array, 'currency', code, since, limit, 'timestamp', tail)

    def filter_by_symbols_since_limit(self, array, symbols: List[str] = None, since: Int = None, limit: Int = None, tail=False):
        result = self.filter_by_array(array, 'symbol', symbols, False)
        return self.filter_by_since_limit(result, since, limit, 'timestamp', tail)

    def parse_tickers(self, tickers, symbols: Strings = None, params={}):
        #
        # the value of tickers is either a dict or a list
        #
        #
        # dict
        #
        #     {
        #         'marketId1': {...},
        #         'marketId2': {...},
        #         'marketId3': {...},
        #         ...
        #     }
        #
        # list
        #
        #     [
        #         {'market': 'marketId1', ...},
        #         {'market': 'marketId2', ...},
        #         {'market': 'marketId3', ...},
        #         ...
        #     ]
        #
        results = []
        if isinstance(tickers, list):
            for i in range(0, len(tickers)):
                parsedTicker = self.parse_ticker(tickers[i])
                ticker = self.extend(parsedTicker, params)
                results.append(ticker)
        else:
            marketIds = list(tickers.keys())
            for i in range(0, len(marketIds)):
                marketId = marketIds[i]
                market = self.safe_market(marketId)
                parsed = self.parse_ticker(tickers[marketId], market)
                ticker = self.extend(parsed, params)
                results.append(ticker)
        symbols = self.market_symbols(symbols)
        return self.filter_by_array(results, 'symbol', symbols)

    def parse_isolated_borrow_rates(self, info: Any):
        result = {}
        for i in range(0, len(info)):
            item = info[i]
            borrowRate = self.parse_isolated_borrow_rate(item)
            symbol = self.safe_string(borrowRate, 'symbol')
            result[symbol] = borrowRate
        return result

    def safe_symbol(self, marketId: Str, market: Market = None, delimiter: Str = None, marketType: Str = None):
        market = self.safe_market(marketId, market, delimiter, marketType)
        return market['symbol']

    def parse_funding_rate(self, contract: str, market: Market = None):
        raise NotSupported(self.id + ' parseFundingRate() is not supported yet')

    def parse_funding_rates(self, response, symbols: Strings = None):
        fundingRates = {}
        for i in range(0, len(response)):
            entry = response[i]
            parsed = self.parse_funding_rate(entry)
            fundingRates[parsed['symbol']] = parsed
        return self.filter_by_array(fundingRates, 'symbol', symbols)

    def parse_long_short_ratio(self, info: dict, market: Market = None):
        raise NotSupported(self.id + ' parseLongShortRatio() is not supported yet')

    def parse_long_short_ratio_history(self, response, market=None, since: Int = None, limit: Int = None):
        rates = []
        for i in range(0, len(response)):
            entry = response[i]
            rates.append(self.parse_long_short_ratio(entry, market))
        sorted = self.sort_by(rates, 'timestamp')
        symbol = None if (market is None) else market['symbol']
        return self.filter_by_symbol_since_limit(sorted, symbol, since, limit)

    def handle_trigger_direction_and_params(self, params, exchangeSpecificKey: Str = None, allowEmpty: Bool = False):
        """
 @ignore
        :returns [str, dict]: the trigger-direction value and omited params
        """
        triggerDirection = self.safe_string(params, 'triggerDirection')
        exchangeSpecificDefined = (exchangeSpecificKey is not None) and (exchangeSpecificKey in params)
        if triggerDirection is not None:
            params = self.omit(params, 'triggerDirection')
        # raise exception if:
        # A) if provided value is not unified(support old "up/down" strings too)
        # B) if exchange specific "trigger direction key"(eg. "stopPriceSide") was not provided
        if not self.in_array(triggerDirection, ['ascending', 'descending', 'up', 'down', 'above', 'below']) and not exchangeSpecificDefined and not allowEmpty:
            raise ArgumentsRequired(self.id + ' createOrder() : trigger orders require params["triggerDirection"] to be either "ascending" or "descending"')
        # if old format was provided, overwrite to new
        if triggerDirection == 'up' or triggerDirection == 'above':
            triggerDirection = 'ascending'
        elif triggerDirection == 'down' or triggerDirection == 'below':
            triggerDirection = 'descending'
        return [triggerDirection, params]

    def handle_trigger_and_params(self, params):
        isTrigger = self.safe_bool_2(params, 'trigger', 'stop')
        if isTrigger:
            params = self.omit(params, ['trigger', 'stop'])
        return [isTrigger, params]

    def is_trigger_order(self, params):
        # for backwards compatibility
        return self.handle_trigger_and_params(params)

    def handle_post_only(self, isMarketOrder: bool, exchangeSpecificPostOnlyOption: bool, params: Any = {}):
        """
 @ignore
        :param str type: Order type
        :param boolean exchangeSpecificBoolean: exchange specific postOnly
        :param dict [params]: exchange specific params
        :returns Array:
        """
        timeInForce = self.safe_string_upper(params, 'timeInForce')
        postOnly = self.safe_bool(params, 'postOnly', False)
        ioc = timeInForce == 'IOC'
        fok = timeInForce == 'FOK'
        po = timeInForce == 'PO'
        postOnly = postOnly or po or exchangeSpecificPostOnlyOption
        if postOnly:
            if ioc or fok:
                raise InvalidOrder(self.id + ' postOnly orders cannot have timeInForce equal to ' + timeInForce)
            elif isMarketOrder:
                raise InvalidOrder(self.id + ' market orders cannot be postOnly')
            else:
                if po:
                    params = self.omit(params, 'timeInForce')
                params = self.omit(params, 'postOnly')
                return [True, params]
        return [False, params]


    def fetch_trading_fees(self, params={}):
        raise NotSupported(self.id + ' fetchTradingFees() is not supported yet')


    def fetch_trading_fee(self, symbol: str, params={}):
        if not self.has['fetchTradingFees']:
            raise NotSupported(self.id + ' fetchTradingFee() is not supported yet')
        fees = self.fetch_trading_fees(params)
        return self.safe_dict(fees, symbol)


    def parse_open_interest(self, interest, market: Market = None):
        raise NotSupported(self.id + ' parseOpenInterest() is not supported yet')

    def fetch_funding_rate(self, symbol: str, params={}):
        if self.has['fetchFundingRates']:
            self.load_markets()
            market = self.market(symbol)
            symbol = market['symbol']
            if not market['contract']:
                raise BadSymbol(self.id + ' fetchFundingRate() supports contract markets only')
            rates = self.fetch_funding_rates([symbol], params)
            rate = self.safe_value(rates, symbol)
            if rate is None:
                raise NullResponse(self.id + ' fetchFundingRate() returned no data for ' + symbol)
            else:
                return rate
        else:
            raise NotSupported(self.id + ' fetchFundingRate() is not supported yet')


    def fetch_mark_ohlcv(self, symbol: str, timeframe: str = '1m', since: Int = None, limit: Int = None, params={}):
        """
        fetches historical mark price candlestick data containing the open, high, low, and close price of a market
        :param str symbol: unified symbol of the market to fetch OHLCV data for
        :param str timeframe: the length of time each candle represents
        :param int [since]: timestamp in ms of the earliest candle to fetch
        :param int [limit]: the maximum amount of candles to fetch
        :param dict [params]: extra parameters specific to the exchange API endpoint
        :returns float[][]: A list of candles ordered, open, high, low, close, None
        """
        if self.has['fetchMarkOHLCV']:
            request: dict = {
                'price': 'mark',
            }
            return self.fetch_ohlcv(symbol, timeframe, since, limit, self.extend(request, params))
        else:
            raise NotSupported(self.id + ' fetchMarkOHLCV() is not supported yet')

    def fetch_index_ohlcv(self, symbol: str, timeframe: str = '1m', since: Int = None, limit: Int = None, params={}):
        """
        fetches historical index price candlestick data containing the open, high, low, and close price of a market
        :param str symbol: unified symbol of the market to fetch OHLCV data for
        :param str timeframe: the length of time each candle represents
        :param int [since]: timestamp in ms of the earliest candle to fetch
        :param int [limit]: the maximum amount of candles to fetch
        :param dict [params]: extra parameters specific to the exchange API endpoint
 @returns {} A list of candles ordered, open, high, low, close, None
        """
        if self.has['fetchIndexOHLCV']:
            request: dict = {
                'price': 'index',
            }
            return self.fetch_ohlcv(symbol, timeframe, since, limit, self.extend(request, params))
        else:
            raise NotSupported(self.id + ' fetchIndexOHLCV() is not supported yet')


    def handle_time_in_force(self, params={}):
        """
 @ignore
 Must add timeInForce to self.options to use self method
        :returns str: returns the exchange specific value for timeInForce
        """
        timeInForce = self.safe_string_upper(params, 'timeInForce')  # supported values GTC, IOC, PO
        if timeInForce is not None:
            exchangeValue = self.safe_string(self.options['timeInForce'], timeInForce)
            if exchangeValue is None:
                raise ExchangeError(self.id + ' does not support timeInForce "' + timeInForce + '"')
            return exchangeValue
        return None


    def check_required_argument(self, methodName: str, argument, argumentName, options=[]):
        """
 @ignore
        :param str methodName: the name of the method that the argument is being checked for
        :param str argument: the argument's actual value provided
        :param str argumentName: the name of the argument being checked(for logging purposes)
        :param str[] options: a list of options that the argument can be
        :returns None:
        """
        optionsLength = len(options)
        if (argument is None) or ((optionsLength > 0) and (not(self.in_array(argument, options)))):
            messageOptions = ', '.join(options)
            message = self.id + ' ' + methodName + '() requires a ' + argumentName + ' argument'
            if messageOptions != '':
                message += ', one of ' + '(' + messageOptions + ')'
            raise ArgumentsRequired(message)


    def parse_deposit_withdraw_fees(self, response, codes: Strings = None, currencyIdKey=None):
        """
 @ignore
        :param object[]|dict response: unparsed response from the exchange
        :param str[]|None codes: the unified currency codes to fetch transactions fees for, returns all currencies when None
        :param str currencyIdKey: *should only be None when response is a dictionary* the object key that corresponds to the currency id
        :returns dict: objects with withdraw and deposit fees, indexed by currency codes
        """
        depositWithdrawFees = {}
        isArray = isinstance(response, list)
        responseKeys = response
        if not isArray:
            responseKeys = list(response.keys())
        for i in range(0, len(responseKeys)):
            entry = responseKeys[i]
            dictionary = entry if isArray else response[entry]
            currencyId = self.safe_string(dictionary, currencyIdKey) if isArray else entry
            currency = self.safe_currency(currencyId)
            code = self.safe_string(currency, 'code')
            if (codes is None) or (self.in_array(code, codes)):
                depositWithdrawFees[code] = self.parse_deposit_withdraw_fee(dictionary, currency)
        return depositWithdrawFees


    def deposit_withdraw_fee(self, info):
        return {
            'info': info,
            'withdraw': {
                'fee': None,
                'percentage': None,
            },
            'deposit': {
                'fee': None,
                'percentage': None,
            },
            'networks': {},
        }

    def assign_default_deposit_withdraw_fees(self, fee, currency=None):
        """
 @ignore
        Takes a depositWithdrawFee structure and assigns the default values for withdraw and deposit
        :param dict fee: A deposit withdraw fee structure
        :param dict currency: A currency structure, the response from self.currency()
        :returns dict: A deposit withdraw fee structure
        """
        networkKeys = list(fee['networks'].keys())
        numNetworks = len(networkKeys)
        if numNetworks == 1:
            fee['withdraw'] = fee['networks'][networkKeys[0]]['withdraw']
            fee['deposit'] = fee['networks'][networkKeys[0]]['deposit']
            return fee
        currencyCode = self.safe_string(currency, 'code')
        for i in range(0, numNetworks):
            network = networkKeys[i]
            if network == currencyCode:
                fee['withdraw'] = fee['networks'][networkKeys[i]]['withdraw']
                fee['deposit'] = fee['networks'][networkKeys[i]]['deposit']
        return fee

    def parse_income(self, info, market: Market = None):
        raise NotSupported(self.id + ' parseIncome() is not supported yet')

    def get_market_from_symbols(self, symbols: Strings = None):
        if symbols is None:
            return None
        firstMarket = self.safe_string(symbols, 0)
        market = self.market(firstMarket)
        return market

    def parse_ws_ohlcvs(self, ohlcvs: List[object], market: Any = None, timeframe: str = '1m', since: Int = None, limit: Int = None):
        results = []
        for i in range(0, len(ohlcvs)):
            results.append(self.parse_ws_ohlcv(ohlcvs[i], market))
        return results

    def fetch_transactions(self, code: Str = None, since: Int = None, limit: Int = None, params={}):
        """
 @deprecated
        *DEPRECATED* use fetchDepositsWithdrawals instead
        :param str code: unified currency code for the currency of the deposit/withdrawals, default is None
        :param int [since]: timestamp in ms of the earliest deposit/withdrawal, default is None
        :param int [limit]: max number of deposit/withdrawals to return, default is None
        :param dict [params]: extra parameters specific to the exchange API endpoint
        :returns dict: a list of standardized transaction structures
        """
        if self.has['fetchDepositsWithdrawals']:
            return self.fetch_deposits_withdrawals(code, since, limit, params)
        else:
            raise NotSupported(self.id + ' fetchTransactions() is not supported yet')

    def filter_by_array_positions(self, objects, key: IndexType, values=None, indexed=True):
        """
 @ignore
        Typed wrapper for filterByArray that returns a list of positions
        """
        return self.filter_by_array(objects, key, values, indexed)

    def filter_by_array_tickers(self, objects, key: IndexType, values=None, indexed=True):
        """
 @ignore
        Typed wrapper for filterByArray that returns a dictionary of tickers
        """
        return self.filter_by_array(objects, key, values, indexed)

    def create_ohlcv_object(self, symbol: str, timeframe: str, data):
        res = {}
        res[symbol] = {}
        res[symbol][timeframe] = data
        return res


    def safe_open_interest(self, interest: dict, market: Market = None):
        symbol = self.safe_string(interest, 'symbol')
        if symbol is None:
            symbol = self.safe_string(market, 'symbol')
        return self.extend(interest, {
            'symbol': symbol,
            'baseVolume': self.safe_number(interest, 'baseVolume'),  # deprecated
            'quoteVolume': self.safe_number(interest, 'quoteVolume'),  # deprecated
            'openInterestAmount': self.safe_number(interest, 'openInterestAmount'),
            'openInterestValue': self.safe_number(interest, 'openInterestValue'),
            'timestamp': self.safe_integer(interest, 'timestamp'),
            'datetime': self.safe_string(interest, 'datetime'),
            'info': self.safe_value(interest, 'info'),
        })

    def parse_greeks(self, greeks: dict, market: Market = None):
        raise NotSupported(self.id + ' parseGreeks() is not supported yet')


    def parse_option(self, chain: dict, currency: Currency = None, market: Market = None):
        raise NotSupported(self.id + ' parseOption() is not supported yet')


    def parse_margin_modification(self, data: dict, market: Market = None):
        raise NotSupported(self.id + ' parseMarginModification() is not supported yet')

