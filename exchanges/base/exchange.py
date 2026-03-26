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
    PermissionDenied,
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

# cryptographic signing — only ed25519 (for eddsa/backpack) is actively used
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.serialization import load_pem_private_key

# eddsa signing (used by backpack)
try:
    import axolotl_curve25519 as eddsa
except ImportError:
    eddsa = None

# -----------------------------------------------------------------------------

__all__ = [
    'Exchange',
]

# -----------------------------------------------------------------------------

import types
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

class Exchange(object):
    """Base exchange class"""
    id = None
    name = None
    countries = None
    version = None
    certified = False  # if certified by the CCXT dev team
    pro = False  # if it is integrated with CCXT Pro for WebSocket support
    alias = False  # whether this exchange is an alias to another exchange
    # rate limiter settings
    enableRateLimit = True
    rateLimit = 2000  # milliseconds = seconds * 1000
    timeout = 10000   # milliseconds = seconds * 1000
    ssl_context = None
    trust_env = False
    requests_trust_env = False
    session = None  # Session () by default
    verify = True  # SSL verification
    validateServerSsl = True
    validateClientSsl = False
    logger = None  # logging.getLogger(__name__) by default
    verbose = False
    markets = None
    symbols = None
    codes = None
    timeframes = {}
    # Rate limiting: throttle() uses simple timestamp-based sleep

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
        '400': BadRequest,
        '401': AuthenticationError,
        '403': PermissionDenied,
        '404': BadSymbol,
        '405': BadRequest,
        '407': AuthenticationError,
        '408': RequestTimeout,
        '409': ExchangeNotAvailable,
        '410': ExchangeNotAvailable,
        '418': DDoSProtection,
        '422': ExchangeError,
        '429': RateLimitExceeded,
        '451': ExchangeNotAvailable,
        '500': ExchangeNotAvailable,
        '501': ExchangeNotAvailable,
        '502': ExchangeNotAvailable,
        '503': ExchangeNotAvailable,
        '504': RequestTimeout,
        '511': AuthenticationError,
        '520': ExchangeNotAvailable,
        '521': ExchangeNotAvailable,
        '522': ExchangeNotAvailable,
        '525': ExchangeNotAvailable,
        '526': ExchangeNotAvailable,
        '530': ExchangeNotAvailable,
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

    requiresEddsa = False
    base58_encoder = None
    base58_decoder = None
    # no lower case l or upper case I, O
    base58_alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

    commonCurrencies = {
        'XBT': 'BTC',
        'BCC': 'BCH',
        'BCHSV': 'BSV',
    }
    synchronous = True

    def __init__(self, config: ConstructorArgs = {}):
        # trust_env is used by requests session
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
        #     'User-Agent': 'ccxt/' + __version__ + ' (+https://github.com/ccxt/ccxt) Python/' + version
        # }

        self.origin = self.uuid()
        self.userAgent = default_user_agent()

        settings = self.deep_extend(self.describe(), config)

        for key in settings:
            if hasattr(self, key) and isinstance(getattr(self, key), dict):
                setattr(self, key, self.deep_extend(getattr(self, key), settings[key]))
            else:
                setattr(self, key, settings[key])

        self.after_construct()

        if self.safe_bool(config, 'sandbox') or self.safe_bool(config, 'testnet'):
            self.set_sandbox_mode(True)

        # convert all properties from underscore notation foo_bar to camelcase notation fooBar
        cls = type(self)
        for name in dir(self):
            if name[0] != '_' and name[-1] != '_' and '_' in name:
                parts = name.split('_')
                # fetch_ohlcv → fetchOHLCV (not fetchOhlcv!)
                exceptions = {'ohlcv': 'OHLCV', 'le': 'LE', 'be': 'BE'}
                camelcase = parts[0] + ''.join(exceptions.get(i, self.capitalize(i)) for i in parts[1:])
                attr = getattr(self, name)
                if isinstance(attr, types.MethodType):
                    setattr(cls, camelcase, getattr(cls, name))
                else:
                    if hasattr(self, camelcase):
                        if attr is not None:
                            setattr(self, camelcase, attr)
                    else:
                        setattr(self, camelcase, attr)

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
        return 'ccxt.' + ('async_support.' if self.asyncio_loop else '') + self.id + '()'

    def __str__(self):
        return self.name

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
                raise NotSupported(self.id + ' - to use SOCKS proxy with ccxt, you might need "pysocks" module that can be installed by "pip install pysocks"')
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
        # https://github.com/ccxt/ccxt/issues/5302
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
    def truncate(num, precision=0):
        """Deprecated, use decimal_to_precision instead"""
        if precision > 0:
            decimal_precision = math.pow(10, precision)
            return math.trunc(num * decimal_precision) / decimal_precision
        return int(Exchange.truncate_to_string(num, precision))

    @staticmethod
    def truncate_to_string(num, precision=0):
        """Deprecated, todo: remove references from subclasses"""
        if precision > 0:
            parts = ('{0:.%df}' % precision).format(Decimal(num)).split('.')
            decimal_digits = parts[1][:precision].rstrip('0')
            decimal_digits = decimal_digits if len(decimal_digits) else '0'
            return parts[0] + '.' + decimal_digits
        return ('%d' % num)

    @staticmethod
    def uuid22(length=22):
        return format(random.getrandbits(length * 4), 'x')

    @staticmethod
    def uuid16(length=16):
        return format(random.getrandbits(length * 4), 'x')

    @staticmethod
    def uuid():
        return str(uuid.uuid4())

    @staticmethod
    def uuidv1():
        return str(uuid.uuid1()).replace('-', '')

    @staticmethod
    def uuid5(namespace: str, name):
        return str(uuid.uuid5(uuid.UUID(namespace), name))

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
    def filterBy(array, key, value=None):
        return Exchange.filter_by(array, key, value)

    @staticmethod
    def group_by(array, key):
        result = {}
        array = Exchange.to_array(array)
        array = [entry for entry in array if (key in entry) and (entry[key] is not None)]
        for entry in array:
            if entry[key] not in result:
                result[entry[key]] = []
            result[entry[key]].append(entry)
        return result

    @staticmethod
    def groupBy(array, key):
        return Exchange.group_by(array, key)


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
    def urlencode_with_array_repeat(params={}):
        return re.sub(r'%5B\d*%5D', '', Exchange.urlencode(params, True))

    @staticmethod
    def urlencode_nested(params):
        result = {}

        def _encode_params(params, p_key=None):
            encode_params = {}
            if isinstance(params, dict):
                for key in params:
                    encode_key = '{}[{}]'.format(p_key, key)
                    encode_params[encode_key] = params[key]
            elif isinstance(params, (list, tuple)):
                for offset, value in enumerate(params):
                    encode_key = '{}[{}]'.format(p_key, offset)
                    encode_params[encode_key] = value
            else:
                result[p_key] = params
            for key in encode_params:
                value = encode_params[key]
                _encode_params(value, key)
        if isinstance(params, dict):
            for key in params:
                _encode_params(params[key], key)
        return _urlencode.urlencode(result, quote_via=_urlencode.quote)

    @staticmethod
    def rawencode(params={}, sort=False):
        return _urlencode.unquote(Exchange.urlencode(params))

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
    def unique(array):
        return list(set(array))

    @staticmethod
    def pluck(array, key):
        return [
            element[key]
            for element in array
            if (key in element) and (element[key] is not None)
        ]

    @staticmethod
    def sum(*args):
        return sum([arg for arg in args if isinstance(arg, (float, int))])

    @staticmethod
    def ordered(array):
        return collections.OrderedDict(array)

    @staticmethod
    def aggregate(bidasks):
        ordered = Exchange.ordered({})
        for [price, volume, *_] in bidasks:
            if volume > 0:
                ordered[price] = (ordered[price] if price in ordered else 0) + volume
        result = []
        items = list(ordered.items())
        for price, volume in items:
            result.append([price, volume])
        return result

    @staticmethod
    def sec():
        return Exchange.seconds()

    @staticmethod
    def msec():
        return Exchange.milliseconds()

    @staticmethod
    def usec():
        return Exchange.microseconds()

    @staticmethod
    def seconds():
        return int(time.time())

    @staticmethod
    def milliseconds():
        return int(time.time() * 1000)

    @staticmethod
    def microseconds():
        return int(time.time() * 1000000)

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
    def rfc2616(self, timestamp=None):
        if timestamp is None:
            ts = datetime.datetime.now()
        else:
            ts = timestamp
        stamp = mktime(ts.timetuple())
        return format_date_time(stamp)

    @staticmethod
    def dmy(timestamp, infix='-'):
        utc_datetime = datetime.datetime.fromtimestamp(int(round(timestamp / 1000)), datetime.timezone.utc)
        return utc_datetime.strftime('%m' + infix + '%d' + infix + '%Y')

    @staticmethod
    def ymd(timestamp, infix='-', fullYear=True):
        year_format = '%Y' if fullYear else '%y'
        utc_datetime = datetime.datetime.fromtimestamp(int(round(timestamp / 1000)), datetime.timezone.utc)
        return utc_datetime.strftime(year_format + infix + '%m' + infix + '%d')

    @staticmethod
    def yymmdd(timestamp, infix=''):
        return Exchange.ymd(timestamp, infix, False)

    @staticmethod
    def yyyymmdd(timestamp, infix='-'):
        return Exchange.ymd(timestamp, infix, True)

    @staticmethod
    def ymdhms(timestamp, infix=' '):
        utc_datetime = datetime.datetime.fromtimestamp(int(round(timestamp / 1000)), datetime.timezone.utc)
        return utc_datetime.strftime('%Y-%m-%d' + infix + '%H:%M:%S')

    @staticmethod
    def parse_date(timestamp=None):
        if timestamp is None:
            return timestamp
        if not isinstance(timestamp, str):
            return None
        if 'GMT' in timestamp:
            try:
                string = ''.join([str(value).zfill(2) for value in parsedate(timestamp)[:6]]) + '.000Z'
                dt = datetime.datetime.strptime(string, "%Y%m%d%H%M%S.%fZ")
                return calendar.timegm(dt.utctimetuple()) * 1000
            except (TypeError, OverflowError, OSError):
                return None
        else:
            return Exchange.parse8601(timestamp)

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
    def binary_concat(*args):
        result = bytes()
        for arg in args:
            result = result + arg
        return result

    @staticmethod
    def binary_concat_array(array):
        result = bytes()
        for element in array:
            result = result + element
        return result

    @staticmethod
    def urlencode_base64(s):
        return Exchange.decode(base64.urlsafe_b64encode(s)).replace('=', '')

    @staticmethod
    def binary_to_base64(s):
        return Exchange.decode(base64.standard_b64encode(s))

    @staticmethod
    def base64_to_binary(s):
        return base64.standard_b64decode(s)

    @staticmethod
    def string_to_base64(s):
        return Exchange.binary_to_base64(Exchange.encode(s))

    @staticmethod
    def base64_to_string(s):
        return Exchange.decode(base64.b64decode(s))

    @staticmethod
    def int_to_base16(num):
        return "%0.2X" % num

    @staticmethod
    def random_bytes(length):
        return format(random.getrandbits(length * 8), 'x')


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
    def check_required_version(required_version, error=True):
        result = True
        [major1, minor1, patch1] = required_version.split('.')
        [major2, minor2, patch2] = __version__.split('.')
        int_major1 = int(major1)
        int_minor1 = int(minor1)
        int_patch1 = int(patch1)
        int_major2 = int(major2)
        int_minor2 = int(minor2)
        int_patch2 = int(patch2)
        if int_major1 > int_major2:
            result = False
        if int_major1 == int_major2:
            if int_minor1 > int_minor2:
                result = False
            elif int_minor1 == int_minor2 and int_patch1 > int_patch2:
                result = False
        if not result:
            if error:
                raise NotSupported('Your current version of CCXT is ' + __version__ + ', a newer version ' + required_version + ' is required, please, upgrade your version of CCXT')
            else:
                return error
        return result

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

    def vwap(self, baseVolume, quoteVolume):
        return (quoteVolume / baseVolume) if (quoteVolume is not None) and (baseVolume is not None) and (baseVolume > 0) else None

    @staticmethod
    def remove0x_prefix(value):
        if value[:2] == '0x':
            return value[2:]
        return value

    @staticmethod
    def totp(key):
        def hex_to_dec(n):
            return int(n, base=16)

        def base32_to_bytes(n):
            missing_padding = len(n) % 8
            padding = 8 - missing_padding if missing_padding > 0 else 0
            padded = n.upper() + ('=' * padding)
            return base64.b32decode(padded)  # throws an error if the key is invalid

        epoch = int(time.time()) // 30
        hmac_res = Exchange.hmac(epoch.to_bytes(8, 'big'), base32_to_bytes(key.replace(' ', '')), hashlib.sha1, 'hex')
        offset = hex_to_dec(hmac_res[-1]) * 2
        otp = str(hex_to_dec(hmac_res[offset: offset + 8]) & 0x7fffffff)
        return otp[-6:]

    @staticmethod
    def number_to_le(n, size):
        return int(n).to_bytes(size, 'little')

    @staticmethod
    def number_to_be(n, size):
        return int(n).to_bytes(size, 'big')

    @staticmethod
    def base16_to_binary(s):
        return base64.b16decode(s, True)

    @staticmethod
    def binary_to_base16(s):
        return Exchange.decode(base64.b16encode(s)).lower()

    def sleep(self, milliseconds):
        return time.sleep(milliseconds / 1000)

    @staticmethod
    def base58_to_binary(s):
        """encodes a base58 string to as a big endian integer"""
        if Exchange.base58_decoder is None:
            Exchange.base58_decoder = {}
            Exchange.base58_encoder = {}
            for i, c in enumerate(Exchange.base58_alphabet):
                Exchange.base58_decoder[c] = i
                Exchange.base58_encoder[i] = c
        result = 0
        for i in range(len(s)):
            result *= 58
            result += Exchange.base58_decoder[s[i]]
        return result.to_bytes((result.bit_length() + 7) // 8, 'big')

    @staticmethod
    def binary_to_base58(b):
        if Exchange.base58_encoder is None:
            Exchange.base58_decoder = {}
            Exchange.base58_encoder = {}
            for i, c in enumerate(Exchange.base58_alphabet):
                Exchange.base58_decoder[c] = i
                Exchange.base58_encoder[i] = c
        result = 0
        # undo decimal_to_bytes
        for byte in b:
            result *= 0x100
            result += byte
        string = []
        while result > 0:
            result, next_character = divmod(result, 58)
            string.append(Exchange.base58_encoder[next_character])
        string.reverse()
        return ''.join(string)

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

    def clone(self, obj):
        return obj if isinstance(obj, list) else self.extend(obj)

    # def delete_key_from_dictionary(self, dictionary, key):
    #     newDictionary = self.clone(dictionary)
    #     del newDictionary[key]
    #     return newDictionary

    # def set_object_property(obj, prop, value):
    #     obj[prop] = value

    def convert_to_big_int(self, value):
        return int(value) if isinstance(value, str) else value

    def string_to_chars_array(self, value):
        return list(value)

    def value_is_defined(self, value):
        return value is not None

    def array_slice(self, array, first, second=None):
        return array[first:second] if second else array[first:]

    def get_property(self, obj, property, defaultValue=None):
        return getattr(obj, property) if hasattr(obj, property) else defaultValue

    def set_property(self, obj, property, value):
        setattr(obj, property, value)

    def exception_message(self, exc, include_stack=True):
        message = '[' + type(exc).__name__ + '] ' + (str(exc) if include_stack else "".join(format_exception(type(exc), exc, exc.__traceback__, limit=6)))
        length = min(100000, len(message))
        return message[0:length]

    def un_camel_case(self, str):
        return re.sub('(?!^)([A-Z]+)', r'_\1', str).lower()

    def fix_stringified_json_members(self, content):
        # when stringified json has members with their values also stringified, like:
        # '{"code":0, "data":{"order":{"orderId":1742968678528512345,"symbol":"BTC-USDT", "takeProfit":"{\"type\":\"TAKE_PROFIT\",\"stopPrice\":43320.1}","reduceOnly":false}}}'
        # we can fix with below manipulations
        # @ts-ignore
        modifiedContent = content.replace('\\', '')
        modifiedContent = modifiedContent.replace('"{', '{')
        modifiedContent = modifiedContent.replace('}"', '}')
        return modifiedContent

    def extend_exchange_options(self, newOptions):
        self.options = self.extend(self.options, newOptions)

    def create_safe_dictionary(self):
        return {}

    def convert_to_safe_dictionary(self, dictionary):
        return dictionary

    def rand_number(self, size):
        return int(''.join([str(random.randint(0, 9)) for _ in range(size)]))

    def binary_length(self, binary):
        return len(binary)

    def is_binary_message(self, message):
        return isinstance(message, bytes) or isinstance(message, bytearray)

    def lock_id(self):
        return None

    def unlock_id(self):
        return None

    # METHODS BELOW THIS LINE ARE TRANSPILED FROM TYPESCRIPT

    def describe(self) -> Any:
        return {
            'id': None,
            'name': None,
            'countries': None,
            'enableRateLimit': True,
            'rateLimit': 2000,  # milliseconds = seconds * 1000
            'timeout': self.timeout,  # milliseconds = seconds * 1000
            'certified': False,  # if certified by the CCXT dev team
            'pro': False,  # if it is integrated with CCXT Pro for WebSocket support
            'alias': False,  # whether self exchange is an alias to another exchange
            'dex': False,
            'has': {
                'publicAPI': True,
                'privateAPI': True,
                'CORS': None,
                'sandbox': None,
                'spot': None,
                'margin': None,
                'swap': None,
                'future': None,
                'option': None,
                'addMargin': None,
                'borrowCrossMargin': None,
                'borrowIsolatedMargin': None,
                'borrowMargin': None,
                'cancelAllOrders': None,
                'cancelAllOrdersWs': None,
                'cancelOrder': True,
                'cancelOrderWithClientOrderId': None,
                'cancelOrderWs': None,
                'cancelOrders': None,
                'cancelOrdersWithClientOrderId': None,
                'cancelOrdersWs': None,
                'closeAllPositions': None,
                'closePosition': None,
                'createDepositAddress': None,
                'createLimitBuyOrder': None,
                'createLimitBuyOrderWs': None,
                'createLimitOrder': True,
                'createLimitOrderWs': None,
                'createLimitSellOrder': None,
                'createLimitSellOrderWs': None,
                'createMarketBuyOrder': None,
                'createMarketBuyOrderWs': None,
                'createMarketBuyOrderWithCost': None,
                'createMarketBuyOrderWithCostWs': None,
                'createMarketOrder': True,
                'createMarketOrderWs': True,
                'createMarketOrderWithCost': None,
                'createMarketOrderWithCostWs': None,
                'createMarketSellOrder': None,
                'createMarketSellOrderWs': None,
                'createMarketSellOrderWithCost': None,
                'createMarketSellOrderWithCostWs': None,
                'createOrder': True,
                'createOrderWs': None,
                'createOrders': None,
                'createOrderWithTakeProfitAndStopLoss': None,
                'createOrderWithTakeProfitAndStopLossWs': None,
                'createPostOnlyOrder': None,
                'createPostOnlyOrderWs': None,
                'createReduceOnlyOrder': None,
                'createReduceOnlyOrderWs': None,
                'createStopLimitOrder': None,
                'createStopLimitOrderWs': None,
                'createStopLossOrder': None,
                'createStopLossOrderWs': None,
                'createStopMarketOrder': None,
                'createStopMarketOrderWs': None,
                'createStopOrder': None,
                'createStopOrderWs': None,
                'createTakeProfitOrder': None,
                'createTakeProfitOrderWs': None,
                'createTrailingAmountOrder': None,
                'createTrailingAmountOrderWs': None,
                'createTrailingPercentOrder': None,
                'createTrailingPercentOrderWs': None,
                'createTriggerOrder': None,
                'createTriggerOrderWs': None,
                'deposit': None,
                'editOrder': 'emulated',
                'editOrderWithClientOrderId': None,
                'editOrders': None,
                'editOrderWs': None,
                'fetchAccounts': None,
                'fetchBalance': True,
                'fetchBalanceWs': None,
                'fetchBidsAsks': None,
                'fetchBorrowInterest': None,
                'fetchBorrowRate': None,
                'fetchBorrowRateHistories': None,
                'fetchBorrowRateHistory': None,
                'fetchBorrowRates': None,
                'fetchBorrowRatesPerSymbol': None,
                'fetchCanceledAndClosedOrders': None,
                'fetchCanceledOrders': None,
                'fetchClosedOrder': None,
                'fetchClosedOrders': None,
                'fetchClosedOrdersWs': None,
                'fetchConvertCurrencies': None,
                'fetchConvertQuote': None,
                'fetchConvertTrade': None,
                'fetchConvertTradeHistory': None,
                'fetchCrossBorrowRate': None,
                'fetchCrossBorrowRates': None,
                'fetchCurrencies': 'emulated',
                'fetchCurrenciesWs': 'emulated',
                'fetchDeposit': None,
                'fetchDepositAddress': None,
                'fetchDepositAddresses': None,
                'fetchDepositAddressesByNetwork': None,
                'fetchDeposits': None,
                'fetchDepositsWithdrawals': None,
                'fetchDepositsWs': None,
                'fetchDepositWithdrawFee': None,
                'fetchDepositWithdrawFees': None,
                'fetchFundingHistory': None,
                'fetchFundingRate': None,
                'fetchFundingRateHistory': None,
                'fetchFundingInterval': None,
                'fetchFundingIntervals': None,
                'fetchFundingRates': None,
                'fetchGreeks': None,
                'fetchIndexOHLCV': None,
                'fetchIsolatedBorrowRate': None,
                'fetchIsolatedBorrowRates': None,
                'fetchMarginAdjustmentHistory': None,
                'fetchIsolatedPositions': None,
                'fetchL2OrderBook': True,
                'fetchL3OrderBook': None,
                'fetchLastPrices': None,
                'fetchLedger': None,
                'fetchLedgerEntry': None,
                'fetchLeverage': None,
                'fetchLeverages': None,
                'fetchLeverageTiers': None,
                'fetchLiquidations': None,
                'fetchLongShortRatio': None,
                'fetchLongShortRatioHistory': None,
                'fetchMarginMode': None,
                'fetchMarginModes': None,
                'fetchMarketLeverageTiers': None,
                'fetchMarkets': True,
                'fetchMarketsWs': None,
                'fetchMarkOHLCV': None,
                'fetchMyLiquidations': None,
                'fetchMySettlementHistory': None,
                'fetchMyTrades': None,
                'fetchMyTradesWs': None,
                'fetchOHLCV': None,
                'fetchOHLCVWs': None,
                'fetchOpenInterest': None,
                'fetchOpenInterests': None,
                'fetchOpenInterestHistory': None,
                'fetchOpenOrder': None,
                'fetchOpenOrders': None,
                'fetchOpenOrdersWs': None,
                'fetchOption': None,
                'fetchOptionChain': None,
                'fetchOrder': None,
                'fetchOrderWithClientOrderId': None,
                'fetchOrderBook': True,
                'fetchOrderBooks': None,
                'fetchOrderBookWs': None,
                'fetchOrders': None,
                'fetchOrdersByStatus': None,
                'fetchOrdersWs': None,
                'fetchOrderTrades': None,
                'fetchOrderWs': None,
                'fetchPosition': None,
                'fetchPositionHistory': None,
                'fetchPositionsHistory': None,
                'fetchPositionWs': None,
                'fetchPositionMode': None,
                'fetchPositions': None,
                'fetchPositionsWs': None,
                'fetchPositionsForSymbol': None,
                'fetchPositionsForSymbolWs': None,
                'fetchPositionsRisk': None,
                'fetchPremiumIndexOHLCV': None,
                'fetchSettlementHistory': None,
                'fetchStatus': None,
                'fetchTicker': True,
                'fetchTickerWs': None,
                'fetchTickers': None,
                'fetchMarkPrices': None,
                'fetchTickersWs': None,
                'fetchTime': None,
                'fetchTrades': True,
                'fetchTradesWs': None,
                'fetchTradingFee': None,
                'fetchTradingFees': None,
                'fetchTradingFeesWs': None,
                'fetchTradingLimits': None,
                'fetchTransactionFee': None,
                'fetchTransactionFees': None,
                'fetchTransactions': None,
                'fetchTransfer': None,
                'fetchTransfers': None,
                'fetchUnderlyingAssets': None,
                'fetchVolatilityHistory': None,
                'fetchWithdrawAddresses': None,
                'fetchWithdrawal': None,
                'fetchWithdrawals': None,
                'fetchWithdrawalsWs': None,
                'fetchWithdrawalWhitelist': None,
                'reduceMargin': None,
                'repayCrossMargin': None,
                'repayIsolatedMargin': None,
                'setLeverage': None,
                'setMargin': None,
                'setMarginMode': None,
                'setPositionMode': None,
                'signIn': None,
                'transfer': None,
                'watchBalance': None,
                'watchMyTrades': None,
                'watchOHLCV': None,
                'watchOHLCVForSymbols': None,
                'watchOrderBook': None,
                'watchBidsAsks': None,
                'watchOrderBookForSymbols': None,
                'watchOrders': None,
                'watchOrdersForSymbols': None,
                'watchPosition': None,
                'watchPositions': None,
                'watchStatus': None,
                'watchTicker': None,
                'watchTickers': None,
                'watchTrades': None,
                'watchTradesForSymbols': None,
                'watchLiquidations': None,
                'watchLiquidationsForSymbols': None,
                'watchMyLiquidations': None,
                'unWatchOrders': None,
                'unWatchTrades': None,
                'unWatchTradesForSymbols': None,
                'unWatchOHLCVForSymbols': None,
                'unWatchOrderBookForSymbols': None,
                'unWatchPositions': None,
                'unWatchOrderBook': None,
                'unWatchTickers': None,
                'unWatchMyTrades': None,
                'unWatchTicker': None,
                'unWatchOHLCV': None,
                'watchMyLiquidationsForSymbols': None,
                'withdraw': None,
                'ws': None,
            },
            'urls': {
                'logo': None,
                'api': None,
                'www': None,
                'doc': None,
                'fees': None,
            },
            'api': None,
            'requiredCredentials': {
                'apiKey': True,
                'secret': True,
                'uid': False,
                'accountId': False,
                'login': False,
                'password': False,
                'twofa': False,  # 2-factor authentication(one-time password key)
                'privateKey': False,  # a "0x"-prefixed hexstring private key for a wallet
                'walletAddress': False,  # the wallet address "0x"-prefixed hexstring
                'token': False,  # reserved for HTTP auth in some cases
            },
            'markets': None,  # to be filled manually or by fetchMarkets
            'currencies': {},  # to be filled manually or by fetchMarkets
            'timeframes': None,  # redefine if the exchange has.fetchOHLCV
            'fees': {
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
            },
            'status': {
                'status': 'ok',
                'updated': None,
                'eta': None,
                'url': None,
            },
            'exceptions': None,
            'httpExceptions': {
                '400': BadRequest,
                '401': AuthenticationError,
                '403': PermissionDenied,
                '404': BadSymbol,
                '405': BadRequest,
                '407': AuthenticationError,
                '408': RequestTimeout,
                '409': ExchangeNotAvailable,
                '410': ExchangeNotAvailable,
                '418': DDoSProtection,
                '422': ExchangeError,
                '429': RateLimitExceeded,
                '451': ExchangeNotAvailable,
                '500': ExchangeNotAvailable,
                '501': ExchangeNotAvailable,
                '502': ExchangeNotAvailable,
                '503': ExchangeNotAvailable,
                '504': RequestTimeout,
                '511': AuthenticationError,
                '520': ExchangeNotAvailable,
                '521': ExchangeNotAvailable,
                '522': ExchangeNotAvailable,
                '525': ExchangeNotAvailable,
                '526': ExchangeNotAvailable,
                '530': ExchangeNotAvailable,
            },
            'commonCurrencies': {
                'XBT': 'BTC',
                'BCHSV': 'BSV',
            },
            'precisionMode': TICK_SIZE,
            'paddingMode': NO_PADDING,
            'limits': {
                'leverage': {'min': None, 'max': None},
                'amount': {'min': None, 'max': None},
                'price': {'min': None, 'max': None},
                'cost': {'min': None, 'max': None},
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

    def check_address(self, address: Str = None):
        if address is None:
            raise InvalidAddress(self.id + ' address is None')
        # check the address is not the same letter like 'aaaaa' nor too short nor has a space
        uniqChars = (self.unique(self.string_to_chars_array(address)))
        length = len(uniqChars)  # py transpiler trick
        if length == 1 or len(address) < self.minFundingAddressLength or address.find(' ') > -1:
            raise InvalidAddress(self.id + ' address is invalid or has less than ' + str(self.minFundingAddressLength) + ' characters: "' + str(address) + '"')
        return address

    def find_message_hashes(self, client, element: str):
        result = []
        messageHashes = list(client.futures.keys())
        for i in range(0, len(messageHashes)):
            messageHash = messageHashes[i]
            if messageHash.find(element) >= 0:
                result.append(messageHash)
        return result

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

    def fetch_trades(self, symbol: str, since: Int = None, limit: Int = None, params={}):
        raise NotSupported(self.id + ' fetchTrades() is not supported yet')

    def fetch_order_book(self, symbol: str, limit: Int = None, params={}):
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

    def parse_currency(self, rawCurrency: dict):
        raise NotSupported(self.id + ' parseCurrency() is not supported yet')

    def parse_currencies(self, rawCurrencies):
        result = {}
        arr = self.to_array(rawCurrencies)
        for i in range(0, len(arr)):
            parsed = self.parse_currency(arr[i])
            code = parsed['code']
            result[code] = parsed
        return result

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

    def parse_order(self, order: dict, market: Market = None):
        raise NotSupported(self.id + ' parseOrder() is not supported yet')

    def parse_position(self, position: dict, market: Market = None):
        raise NotSupported(self.id + ' parsePosition() is not supported yet')

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

    def feature_value(self, symbol: str, methodName: Str = None, paramName: Str = None, defaultValue: Any = None):
        """
        self method is a very deterministic to help users to know what feature is supported by the exchange
        :param str [symbol]: unified symbol
        :param str [methodName]: view currently supported methods: https://docs.ccxt.com/#/README?id=features
        :param str [paramName]: unified param value, like: `triggerPrice`, `stopLoss.triggerPrice`(check docs for supported param names)
        :param dict [defaultValue]: return default value if no result found
        :returns dict: returns feature value
        """
        market = self.market(symbol)
        return self.feature_value_by_type(market['type'], market['subType'], methodName, paramName, defaultValue)

    def feature_value_by_type(self, marketType: str, subType: Str, methodName: Str = None, paramName: Str = None, defaultValue: Any = None):
        """
        self method is a very deterministic to help users to know what feature is supported by the exchange
        :param str [marketType]: supported only: "spot", "swap", "future"
        :param str [subType]: supported only: "linear", "inverse"
        :param str [methodName]: view currently supported methods: https://docs.ccxt.com/#/README?id=features
        :param str [paramName]: unified param value(check docs for supported param names)
        :param dict [defaultValue]: return default value if no result found
        :returns dict: returns feature value
        """
        # if exchange does not yet have features manually implemented
        if self.features is None:
            return defaultValue
        if marketType is None:
            return defaultValue  # marketType is required
        # if marketType(e.g. 'option') does not exist in features
        if not (marketType in self.features):
            return defaultValue  # unsupported marketType, check "exchange.features" for details
        # if marketType dict None
        if self.features[marketType] is None:
            return defaultValue
        methodsContainer = self.features[marketType]
        if subType is None:
            if marketType != 'spot':
                return defaultValue  # subType is required for non-spot markets
        else:
            if not (subType in self.features[marketType]):
                return defaultValue  # unsupported subType, check "exchange.features" for details
            # if subType dict None
            if self.features[marketType][subType] is None:
                return defaultValue
            methodsContainer = self.features[marketType][subType]
        # if user wanted only marketType and didn't provide methodName, eg: featureIsSupported('spot')
        if methodName is None:
            return defaultValue if (defaultValue is not None) else methodsContainer
        if not (methodName in methodsContainer):
            return defaultValue  # unsupported method, check "exchange.features" for details')
        methodDict = methodsContainer[methodName]
        if methodDict is None:
            return defaultValue
        # if user wanted only method and didn't provide `paramName`, eg: featureIsSupported('swap', 'linear', 'createOrder')
        if paramName is None:
            return defaultValue if (defaultValue is not None) else methodDict
        splited = paramName.split('.')  # can be only parent key(`stopLoss`) or with child(`stopLoss.triggerPrice`)
        parentKey = splited[0]
        subKey = self.safe_string(splited, 1)
        if not (parentKey in methodDict):
            return defaultValue  # unsupported paramName, check "exchange.features" for details')
        dictionary = self.safe_dict(methodDict, parentKey)
        if dictionary is None:
            # if the value is not dictionary but a scalar value(or None), return
            return methodDict[parentKey]
        else:
            # return, when calling without subKey eg: featureValueByType('spot', None, 'createOrder', 'stopLoss')
            if subKey is None:
                return methodDict[parentKey]
            # raise an exception for unsupported subKey
            if not (subKey in methodDict[parentKey]):
                return defaultValue  # unsupported subKey, check "exchange.features" for details
            return methodDict[parentKey][subKey]

    def orderbook_checksum_message(self, symbol: Str):
        return symbol + '  = False'

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

    def set_markets_from_exchange(self, sourceExchange):
        # Validate that both exchanges are of the same type
        if self.id != sourceExchange.id:
            raise ArgumentsRequired(self.id + ' shareMarkets() can only share markets with exchanges of the same type(got ' + sourceExchange['id'] + ')')
        # Validate that source exchange has loaded markets
        if not sourceExchange.markets:
            raise ExchangeError('setMarketsFromExchange() source exchange must have loaded markets first. Can call by using loadMarkets function')
        # Set all market-related data
        self.markets = sourceExchange.markets
        self.markets_by_id = sourceExchange.markets_by_id
        self.symbols = sourceExchange.symbols
        self.ids = sourceExchange.ids
        self.currencies = sourceExchange.currencies
        self.currencies_by_id = sourceExchange.currencies_by_id
        self.baseCurrencies = sourceExchange.baseCurrencies
        self.quoteCurrencies = sourceExchange.quoteCurrencies
        self.codes = sourceExchange.codes
        # check marketHelperProps
        sourceExchangeHelpers = self.safe_list(sourceExchange.options, 'marketHelperProps', [])
        for i in range(0, len(sourceExchangeHelpers)):
            helper = sourceExchangeHelpers[i]
            if sourceExchange.options[helper] is not None:
                self.options[helper] = sourceExchange.options[helper]
        return self

    def get_describe_for_extended_ws_exchange(self, currentRestInstance: Any, parentRestInstance: Any, wsBaseDescribe: dict):
        extendedRestDescribe = self.deep_extend(parentRestInstance.describe(), currentRestInstance.describe())
        superWithRestDescribe = self.deep_extend(extendedRestDescribe, wsBaseDescribe)
        return superWithRestDescribe

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

    def calculate_fee_with_rate(self, symbol: str, type: str, side: str, amount: float, price: float, takerOrMaker='taker', feeRate: Num = None, params={}):
        if type == 'market' and takerOrMaker == 'maker':
            raise ArgumentsRequired(self.id + ' calculateFee() - you have provided incompatible arguments - "market" type order can not be "maker". Change either the "type" or the "takerOrMaker" argument to calculate the fee.')
        market = self.markets[symbol]
        feeSide = self.safe_string(market, 'feeSide', 'quote')
        useQuote = None
        if feeSide == 'get':
            # the fee is always in the currency you get
            useQuote = side == 'sell'
        elif feeSide == 'give':
            # the fee is always in the currency you give
            useQuote = side == 'buy'
        else:
            # the fee is always in feeSide currency
            useQuote = feeSide == 'quote'
        cost = self.number_to_string(amount)
        key = None
        if useQuote:
            priceString = self.number_to_string(price)
            cost = Precise.string_mul(cost, priceString)
            key = 'quote'
        else:
            key = 'base'
        # for derivatives, the fee is in 'settle' currency
        if not market['spot']:
            key = 'settle'
        # even if `takerOrMaker` argument was set to 'maker', for 'market' orders we should forcefully override it to 'taker'
        if type == 'market':
            takerOrMaker = 'taker'
        rate = self.number_to_string(feeRate) if (feeRate is not None) else self.safe_string(market, takerOrMaker)
        cost = Precise.string_mul(cost, rate)
        return {
            'type': takerOrMaker,
            'currency': market[key],
            'rate': self.parse_number(rate),
            'cost': self.parse_number(cost),
        }

    def calculate_fee(self, symbol: str, type: str, side: str, amount: float, price: float, takerOrMaker='taker', params={}):
        """
        calculates the presumptive fee that would be charged for an order
        :param str symbol: unified market symbol
        :param str type: 'market' or 'limit'
        :param str side: 'buy' or 'sell'
        :param float amount: how much you want to trade, in units of the base currency on most exchanges, or number of contracts
        :param float price: the price for the order to be filled at, in units of the quote currency
        :param str takerOrMaker: 'taker' or 'maker'
        :param dict params:
        :returns dict: contains the rate, the percentage multiplied to the order amount to obtain the fee amount, and cost, the total value of the fee in units of the quote currency, for the order
        """
        return self.calculate_fee_with_rate(symbol, type, side, amount, price, takerOrMaker, None, params)

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

    def create_ccxt_trade_id(self, timestamp=None, side=None, amount=None, price=None, takerOrMaker=None):
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

    def repay_isolated_margin(self, symbol: str, code: str, amount: float, params={}):
        raise NotSupported(self.id + ' repayIsolatedMargin is not support yet')

    def borrow_isolated_margin(self, symbol: str, code: str, amount: float, params={}):
        raise NotSupported(self.id + ' borrowIsolatedMargin is not support yet')

    def fetch_ohlcv(self, symbol: str, timeframe: str = '1m', since: Int = None, limit: Int = None, params={}):
        message = ''
        if self.has['fetchTrades']:
            message = '. If you want to build OHLCV candles from trade executions data, visit https://github.com/ccxt/ccxt/tree/master/examples/ and see "build-ohlcv-bars" file'
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

    def select_network_code_from_unified_networks(self, currencyCode, networkCode, indexedNetworkEntries):
        return self.select_network_key_from_networks(currencyCode, networkCode, indexedNetworkEntries, True)

    def select_network_id_from_raw_networks(self, currencyCode, networkCode, indexedNetworkEntries):
        return self.select_network_key_from_networks(currencyCode, networkCode, indexedNetworkEntries, False)

    def select_network_key_from_networks(self, currencyCode, networkCode, indexedNetworkEntries, isIndexedByUnifiedNetworkCode=False):
        # self method is used against raw & unparse network entries, which are just indexed by network id
        chosenNetworkId = None
        availableNetworkIds = list(indexedNetworkEntries.keys())
        responseNetworksLength = len(availableNetworkIds)
        if networkCode is not None:
            if responseNetworksLength == 0:
                raise NotSupported(self.id + ' - ' + networkCode + ' network did not return any result for ' + currencyCode)
            else:
                # if networkCode was provided by user, we should check it after response, referenced exchange doesn't support network-code during request
                networkIdOrCode = networkCode if isIndexedByUnifiedNetworkCode else self.network_code_to_id(networkCode, currencyCode)
                if networkIdOrCode in indexedNetworkEntries:
                    chosenNetworkId = networkIdOrCode
                else:
                    raise NotSupported(self.id + ' - ' + networkIdOrCode + ' network was not found for ' + currencyCode + ', use one of ' + ', '.join(availableNetworkIds))
        else:
            if responseNetworksLength == 0:
                raise NotSupported(self.id + ' - no networks were returned for ' + currencyCode)
            else:
                # if networkCode was not provided by user, then we try to use the default network(if it was defined in "defaultNetworks"), otherwise, we just return the first network entry
                defaultNetworkCode = self.default_network_code(currencyCode)
                defaultNetworkId = defaultNetworkCode if isIndexedByUnifiedNetworkCode else self.network_code_to_id(defaultNetworkCode, currencyCode)
                if defaultNetworkId in indexedNetworkEntries:
                    return defaultNetworkId
                raise NotSupported(self.id + ' - can not determine the default network, please pass param["network"] one from : ' + ', '.join(availableNetworkIds))
        return chosenNetworkId

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

    def parse_accounts(self, accounts: List[Any], params={}):
        accounts = self.to_array(accounts)
        result = []
        for i in range(0, len(accounts)):
            account = self.extend(self.parse_account(accounts[i]), params)
            result.append(account)
        return result

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

    def parse_transfers(self, transfers: List[Any], currency: Currency = None, since: Int = None, limit: Int = None, params={}):
        transfers = self.to_array(transfers)
        result = []
        for i in range(0, len(transfers)):
            transfer = self.extend(self.parse_transfer(transfers[i], currency), params)
            result.append(transfer)
        result = self.sort_by(result, 'timestamp')
        code = currency['code'] if (currency is not None) else None
        return self.filter_by_currency_since_limit(result, code, since, limit)

    def parse_ledger(self, data, currency: Currency = None, since: Int = None, limit: Int = None, params={}):
        result = []
        arrayData = self.to_array(data)
        for i in range(0, len(arrayData)):
            itemOrItems = self.parse_ledger_entry(arrayData[i], currency)
            if isinstance(itemOrItems, list):
                for j in range(0, len(itemOrItems)):
                    result.append(self.extend(itemOrItems[j], params))
            else:
                result.append(self.extend(itemOrItems, params))
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

    def handle_param_string_2(self, params: object, paramName1: str, paramName2: str, defaultValue: Str = None):
        value = self.safe_string_2(params, paramName1, paramName2, defaultValue)
        if value is not None:
            params = self.omit(params, [paramName1, paramName2])
        return [value, params]

    def handle_param_integer(self, params: object, paramName: str, defaultValue: Int = None):
        value = self.safe_integer(params, paramName, defaultValue)
        if value is not None:
            params = self.omit(params, paramName)
        return [value, params]

    def handle_param_integer_2(self, params: object, paramName1: str, paramName2: str, defaultValue: Int = None):
        value = self.safe_integer_2(params, paramName1, paramName2, defaultValue)
        if value is not None:
            params = self.omit(params, [paramName1, paramName2])
        return [value, params]

    def handle_param_bool(self, params: object, paramName: str, defaultValue: Bool = None):
        value = self.safe_bool(params, paramName, defaultValue)
        if value is not None:
            params = self.omit(params, paramName)
        return [value, params]

    def handle_param_bool_2(self, params: object, paramName1: str, paramName2: str, defaultValue: Bool = None):
        value = self.safe_bool_2(params, paramName1, paramName2, defaultValue)
        if value is not None:
            params = self.omit(params, [paramName1, paramName2])
        return [value, params]

    def handle_request_network(self, params: dict, request: dict, exchangeSpecificKey: str, currencyCode: Str = None, isRequired: bool = False):
        """
        :param dict params: - extra parameters
        :param dict request: - existing dictionary of request
        :param str exchangeSpecificKey: - the key for chain id to be set in request
        :param dict currencyCode: - (optional) existing dictionary of request
        :param boolean isRequired: - (optional) whether that param is required to be present
        :returns dict[]: - returns [request, params] where request is the modified request object and params is the modified params object
        """
        networkCode = None
        networkCode, params = self.handle_network_code_and_params(params)
        if networkCode is not None:
            request[exchangeSpecificKey] = self.network_code_to_id(networkCode, currencyCode)
        elif isRequired:
            raise ArgumentsRequired(self.id + ' - "network" param is required for self request')
        return [request, params]

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

    def parse_trading_view_ohlcv(self, ohlcvs, market=None, timeframe='1m', since: Int = None, limit: Int = None):
        result = self.convert_trading_view_to_ohlcv(ohlcvs)
        return self.parse_ohlcvs(result, market, timeframe, since, limit)

    def edit_order_with_client_order_id(self, clientOrderId: str, symbol: str, type: OrderType, side: OrderSide, amount: Num = None, price: Num = None, params={}):
        return self.edit_order('', symbol, type, side, amount, price, self.extend({'clientOrderId': clientOrderId}, params))

    def fetch_position(self, symbol: str, params={}):
        raise NotSupported(self.id + ' fetchPosition() is not supported yet')

    def fetch_positions_for_symbol(self, symbol: str, params={}):
        """
        fetches all open positions for specific symbol, unlike fetchPositions(which is designed to work with multiple symbols) so self method might be preffered for one-market position, because of less rate-limit consumption and speed
        :param str symbol: unified market symbol
        :param dict params: extra parameters specific to the endpoint
        :returns dict[]: a list of `position structure <https://docs.ccxt.com/?id=position-structure>` with maximum 3 items - possible one position for "one-way" mode, and possible two positions(long & short) for "two-way"(a.k.a. hedge) mode
        """
        raise NotSupported(self.id + ' fetchPositionsForSymbol() is not supported yet')

    def fetch_positions(self, symbols: Strings = None, params={}):
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

    def oath(self):
        if self.twofa is not None:
            return self.totp(self.twofa)
        else:
            raise ExchangeError(self.id + ' exchange.twofa has not been set for 2FA Two-Factor Authentication')

    def fetch_balance(self, params={}):
        raise NotSupported(self.id + ' fetchBalance() is not supported yet')

    def parse_balance(self, response):
        raise NotSupported(self.id + ' parseBalance() is not supported yet')

    def get_supported_mapping(self, key, mapping={}):
        if key in mapping:
            return mapping[key]
        else:
            raise NotSupported(self.id + ' ' + key + ' does not have a value in mapping')

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

    def handle_option_and_params_2(self, params: object, methodName1: str, optionName1: str, optionName2: str, defaultValue=None):
        value = None
        value, params = self.handle_option_and_params(params, methodName1, optionName1)
        if value is not None:
            # omit optionName2 too from params
            params = self.omit(params, optionName2)
            return [value, params]
        # if still None, try optionName2
        value2 = None
        value2, params = self.handle_option_and_params(params, methodName1, optionName2, defaultValue)
        return [value2, params]

    def handle_option(self, methodName: str, optionName: str, defaultValue=None):
        res = self.handle_option_and_params({}, methodName, optionName, defaultValue)
        return self.safe_value(res, 0)

    def handle_market_type_and_params(self, methodName: str, market: Market = None, params={}, defaultValue=None):
        """
 @ignore
 @param methodName the method calling handleMarketTypeAndParams
        :param Market market:
        :param dict params:
        :param str [params.type]: type assigned by user
        :param str [params.defaultType]: same.type
        :param str [defaultValue]: assigned programatically in the method calling handleMarketTypeAndParams
        :returns [str, dict]: the market type and params with type and defaultType omitted
        """
        # type from param
        type = self.safe_string_2(params, 'defaultType', 'type')
        if type is not None:
            params = self.omit(params, ['defaultType', 'type'])
            return [type, params]
        # type from market
        if market is not None:
            return [market['type'], params]
        # type from default-argument
        if defaultValue is not None:
            return [defaultValue, params]
        methodOptions = self.safe_dict(self.options, methodName)
        if methodOptions is not None:
            if isinstance(methodOptions, str):
                return [methodOptions, params]
            else:
                typeFromMethod = self.safe_string_2(methodOptions, 'defaultType', 'type')
                if typeFromMethod is not None:
                    return [typeFromMethod, params]
        defaultType = self.safe_string_2(self.options, 'defaultType', 'type', 'spot')
        return [defaultType, params]

    def handle_sub_type_and_params(self, methodName: str, market=None, params={}, defaultValue=None):
        subType = None
        # if set in params, it takes precedence
        subTypeInParams = self.safe_string_2(params, 'subType', 'defaultSubType')
        # avoid omitting if it's not present
        if subTypeInParams is not None:
            subType = subTypeInParams
            params = self.omit(params, ['subType', 'defaultSubType'])
        else:
            # at first, check from market object
            if market is not None:
                if market['linear']:
                    subType = 'linear'
                elif market['inverse']:
                    subType = 'inverse'
            # if it was not defined in market object
            if subType is None:
                values = self.handle_option_and_params({}, methodName, 'subType', defaultValue)  # no need to re-test params here
                subType = values[0]
        return [subType, params]

    def handle_margin_mode_and_params(self, methodName: str, params={}, defaultValue=None):
        """
 @ignore
        :param dict [params]: extra parameters specific to the exchange API endpoint
        :returns Array: the marginMode in lowercase by params["marginMode"], params["defaultMarginMode"] self.options["marginMode"] or self.options["defaultMarginMode"]
        """
        return self.handle_option_and_params(params, methodName, 'marginMode', defaultValue)

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

    def calculate_rate_limiter_cost(self, api, method, path, params, config={}):
        return self.safe_value(config, 'cost', 1)

    def fetch_ticker(self, symbol: str, params={}):
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

    def fetch_mark_price(self, symbol: str, params={}):
        if self.has['fetchMarkPrices']:
            self.load_markets()
            market = self.market(symbol)
            symbol = market['symbol']
            tickers = self.fetch_mark_prices([symbol], params)
            ticker = self.safe_dict(tickers, symbol)
            if ticker is None:
                raise NullResponse(self.id + ' fetchMarkPrices() could not find a ticker for ' + symbol)
            else:
                return ticker
        else:
            raise NotSupported(self.id + ' fetchMarkPrices() is not supported yet')

    def fetch_tickers(self, symbols: Strings = None, params={}):
        raise NotSupported(self.id + ' fetchTickers() is not supported yet')

    def fetch_order(self, id: str, symbol: Str = None, params={}):
        raise NotSupported(self.id + ' fetchOrder() is not supported yet')

    def fetch_order_with_client_order_id(self, clientOrderId: str, symbol: Str = None, params={}):
        """
        create a market order by providing the symbol, side and cost
        :param str clientOrderId: client order Id
        :param str symbol: unified symbol of the market to create an order in
        :param dict [params]: extra parameters specific to the exchange API endpoint
        :returns dict: an `order structure <https://docs.ccxt.com/?id=order-structure>`
        """
        extendedParams = self.extend(params, {'clientOrderId': clientOrderId})
        return self.fetch_order('', symbol, extendedParams)

    def create_order(self, symbol: str, type: OrderType, side: OrderSide, amount: float, price: Num = None, params={}):
        raise NotSupported(self.id + ' createOrder() is not supported yet')

    def edit_orders(self, orders: List[OrderRequest], params={}):
        raise NotSupported(self.id + ' editOrders() is not supported yet')

    def cancel_order(self, id: str, symbol: Str = None, params={}):
        raise NotSupported(self.id + ' cancelOrder() is not supported yet')

    def cancel_order_with_client_order_id(self, clientOrderId: str, symbol: Str = None, params={}):
        """
        create a market order by providing the symbol, side and cost
        :param str clientOrderId: client order Id
        :param str symbol: unified symbol of the market to create an order in
        :param dict [params]: extra parameters specific to the exchange API endpoint
        :returns dict: an `order structure <https://docs.ccxt.com/?id=order-structure>`
        """
        extendedParams = self.extend(params, {'clientOrderId': clientOrderId})
        return self.cancel_order('', symbol, extendedParams)

    def cancel_orders(self, ids: List[str], symbol: Str = None, params={}):
        raise NotSupported(self.id + ' cancelOrders() is not supported yet')

    def cancel_orders_with_client_order_ids(self, clientOrderIds: List[str], symbol: Str = None, params={}):
        """
        create a market order by providing the symbol, side and cost
        :param str[] clientOrderIds: client order Ids
        :param str symbol: unified symbol of the market to create an order in
        :param dict [params]: extra parameters specific to the exchange API endpoint
        :returns dict: an `order structure <https://docs.ccxt.com/?id=order-structure>`
        """
        extendedParams = self.extend(params, {'clientOrderIds': clientOrderIds})
        return self.cancel_orders([], symbol, extendedParams)

    def cancel_orders_for_symbols(self, orders: List[CancellationRequest], params={}):
        raise NotSupported(self.id + ' cancelOrdersForSymbols() is not supported yet')

    def fetch_orders(self, symbol: Str = None, since: Int = None, limit: Int = None, params={}):
        if self.has['fetchOpenOrders'] and self.has['fetchClosedOrders']:
            raise NotSupported(self.id + ' fetchOrders() is not supported yet, consider using fetchOpenOrders() and fetchClosedOrders() instead')
        raise NotSupported(self.id + ' fetchOrders() is not supported yet')

    def fetch_open_orders(self, symbol: Str = None, since: Int = None, limit: Int = None, params={}):
        if self.has['fetchOrders']:
            orders = self.fetch_orders(symbol, since, limit, params)
            return self.filter_by(orders, 'status', 'open')
        raise NotSupported(self.id + ' fetchOpenOrders() is not supported yet')

    def fetch_closed_orders(self, symbol: Str = None, since: Int = None, limit: Int = None, params={}):
        if self.has['fetchOrders']:
            orders = self.fetch_orders(symbol, since, limit, params)
            return self.filter_by(orders, 'status', 'closed')
        raise NotSupported(self.id + ' fetchClosedOrders() is not supported yet')

    def fetch_my_trades(self, symbol: Str = None, since: Int = None, limit: Int = None, params={}):
        raise NotSupported(self.id + ' fetchMyTrades() is not supported yet')

    def parse_last_price(self, price, market: Market = None):
        raise NotSupported(self.id + ' parseLastPrice() is not supported yet')

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
        elif (symbol.endswith('-C')) or (symbol.endswith('-P')) or (symbol.startswith('C-')) or (symbol.startswith('P-')):
            return self.create_expired_option_market(symbol)
        raise BadSymbol(self.id + ' does not have market symbol ' + symbol)

    def create_expired_option_market(self, symbol: str):
        raise NotSupported(self.id + ' createExpiredOptionMarket() is not supported yet')

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

    def cost_to_precision(self, symbol: str, cost):
        if cost is None:
            return None
        market = self.market(symbol)
        precision = market['precision']['price']
        if self.precisionMode == TICK_SIZE and isinstance(precision, (int, float)) and precision >= 1:
            precision = 10 ** (-int(precision))
        return self.decimal_to_precision(cost, TRUNCATE, precision, self.precisionMode, self.paddingMode)

    def price_to_precision(self, symbol: str, price):
        if price is None:
            return None
        market = self.market(symbol)
        precision = market['precision']['price']
        if self.precisionMode == TICK_SIZE and isinstance(precision, (int, float)) and precision >= 1:
            precision = 10 ** (-int(precision))
        result = self.decimal_to_precision(price, ROUND, precision, self.precisionMode, self.paddingMode)
        if result == '0':
            raise InvalidOrder(self.id + ' price of ' + market['symbol'] + ' must be greater than minimum price precision of ' + self.number_to_string(market['precision']['price']))
        return result

    def amount_to_precision(self, symbol: str, amount):
        if amount is None:
            return None
        market = self.market(symbol)
        precision = market['precision']['amount']
        if self.precisionMode == TICK_SIZE and isinstance(precision, (int, float)) and precision >= 1:
            # precision is stored as decimal places count (e.g. 3) but TICK_SIZE mode
            # expects actual tick value (e.g. 0.001). Convert integer to tick size.
            precision = 10 ** (-int(precision))
        result = self.decimal_to_precision(amount, TRUNCATE, precision, self.precisionMode, self.paddingMode)
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

    def fetch_market_leverage_tiers(self, symbol: str, params={}):
        if self.has['fetchLeverageTiers']:
            market = self.market(symbol)
            if not market['contract']:
                raise BadSymbol(self.id + ' fetchMarketLeverageTiers() supports contract markets only')
            tiers = self.fetch_leverage_tiers([symbol])
            return self.safe_value(tiers, symbol)
        else:
            raise NotSupported(self.id + ' fetchMarketLeverageTiers() is not supported yet')

    def create_sub_account(self, name: str, params={}):
        raise NotSupported(self.id + ' createSubAccount() is not supported yet')

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

    def parse_deposit_addresses(self, addresses, codes: Strings = None, indexed=True, params={}):
        result = []
        for i in range(0, len(addresses)):
            address = self.extend(self.parse_deposit_address(addresses[i]), params)
            result.append(address)
        if codes is not None:
            result = self.filter_by_array(result, 'currency', codes, False)
        if indexed:
            result = self.filter_by_array(result, 'currency', None, indexed)
        return result

    def parse_borrow_interests(self, response, market: Market = None):
        interests = []
        for i in range(0, len(response)):
            row = response[i]
            interests.append(self.parse_borrow_interest(row, market))
        return interests

    def parse_borrow_rate(self, info, currency: Currency = None):
        raise NotSupported(self.id + ' parseBorrowRate() is not supported yet')

    def parse_borrow_rate_history(self, response, code: Str, since: Int, limit: Int):
        result = []
        for i in range(0, len(response)):
            item = response[i]
            borrowRate = self.parse_borrow_rate(item)
            result.append(borrowRate)
        sorted = self.sort_by(result, 'timestamp')
        return self.filter_by_currency_since_limit(sorted, code, since, limit)

    def parse_isolated_borrow_rates(self, info: Any):
        result = {}
        for i in range(0, len(info)):
            item = info[i]
            borrowRate = self.parse_isolated_borrow_rate(item)
            symbol = self.safe_string(borrowRate, 'symbol')
            result[symbol] = borrowRate
        return result

    def parse_funding_rate_histories(self, response, market=None, since: Int = None, limit: Int = None):
        rates = []
        for i in range(0, len(response)):
            entry = response[i]
            rates.append(self.parse_funding_rate_history(entry, market))
        sorted = self.sort_by(rates, 'timestamp')
        symbol = None if (market is None) else market['symbol']
        return self.filter_by_symbol_since_limit(sorted, symbol, since, limit)

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

    def handle_trigger_prices_and_params(self, symbol, params, omitParams=True):
        #
        triggerPrice = self.safe_string_2(params, 'triggerPrice', 'stopPrice')
        triggerPriceStr: Str = None
        stopLossPrice = self.safe_string(params, 'stopLossPrice')
        stopLossPriceStr: Str = None
        takeProfitPrice = self.safe_string(params, 'takeProfitPrice')
        takeProfitPriceStr: Str = None
        #
        if triggerPrice is not None:
            if omitParams:
                params = self.omit(params, ['triggerPrice', 'stopPrice'])
            triggerPriceStr = self.price_to_precision(symbol, float(triggerPrice))
        if stopLossPrice is not None:
            if omitParams:
                params = self.omit(params, 'stopLossPrice')
            stopLossPriceStr = self.price_to_precision(symbol, float(stopLossPrice))
        if takeProfitPrice is not None:
            if omitParams:
                params = self.omit(params, 'takeProfitPrice')
            takeProfitPriceStr = self.price_to_precision(symbol, float(takeProfitPrice))
        return [triggerPriceStr, stopLossPriceStr, takeProfitPriceStr, params]

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

    def parse_open_interest(self, interest, market: Market = None):
        raise NotSupported(self.id + ' parseOpenInterest() is not supported yet')

    def parse_open_interests(self, response, symbols: Strings = None):
        result = {}
        for i in range(0, len(response)):
            entry = response[i]
            parsed = self.parse_open_interest(entry)
            result[parsed['symbol']] = parsed
        return self.filter_by_array(result, 'symbol', symbols)

    def parse_open_interests_history(self, response, market=None, since: Int = None, limit: Int = None):
        interests = []
        for i in range(0, len(response)):
            entry = response[i]
            interest = self.parse_open_interest(entry, market)
            interests.append(interest)
        sorted = self.sort_by(interests, 'timestamp')
        symbol = self.safe_string(market, 'symbol')
        return self.filter_by_symbol_since_limit(sorted, symbol, since, limit)

    def fetch_funding_interval(self, symbol: str, params={}):
        if self.has['fetchFundingIntervals']:
            self.load_markets()
            market = self.market(symbol)
            symbol = market['symbol']
            if not market['contract']:
                raise BadSymbol(self.id + ' fetchFundingInterval() supports contract markets only')
            rates = self.fetch_funding_intervals([symbol], params)
            rate = self.safe_value(rates, symbol)
            if rate is None:
                raise NullResponse(self.id + ' fetchFundingInterval() returned no data for ' + symbol)
            else:
                return rate
        else:
            raise NotSupported(self.id + ' fetchFundingInterval() is not supported yet')

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

    def fetch_premium_index_ohlcv(self, symbol: str, timeframe: str = '1m', since: Int = None, limit: Int = None, params={}):
        """
        fetches historical premium index price candlestick data containing the open, high, low, and close price of a market
        :param str symbol: unified symbol of the market to fetch OHLCV data for
        :param str timeframe: the length of time each candle represents
        :param int [since]: timestamp in ms of the earliest candle to fetch
        :param int [limit]: the maximum amount of candles to fetch
        :param dict [params]: extra parameters specific to the exchange API endpoint
        :returns float[][]: A list of candles ordered, open, high, low, close, None
        """
        if self.has['fetchPremiumIndexOHLCV']:
            request: dict = {
                'price': 'premiumIndex',
            }
            return self.fetch_ohlcv(symbol, timeframe, since, limit, self.extend(request, params))
        else:
            raise NotSupported(self.id + ' fetchPremiumIndexOHLCV() is not supported yet')

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

    def check_required_margin_argument(self, methodName: str, symbol: Str, marginMode: str):
        """
 @ignore
        :param str symbol: unified symbol of the market
        :param str methodName: name of the method that requires a symbol
        :param str marginMode: is either 'isolated' or 'cross'
        """
        if (marginMode == 'isolated') and (symbol is None):
            raise ArgumentsRequired(self.id + ' ' + methodName + '() requires a symbol argument for isolated margin')
        elif (marginMode == 'cross') and (symbol is not None):
            raise ArgumentsRequired(self.id + ' ' + methodName + '() cannot have a symbol argument for cross margin')

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

    def parse_deposit_withdraw_fee(self, fee, currency: Currency = None):
        raise NotSupported(self.id + ' parseDepositWithdrawFee() is not supported yet')

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

    def parse_incomes(self, incomes, market=None, since: Int = None, limit: Int = None):
        """
 @ignore
        parses funding fee info from exchange response
        :param dict[] incomes: each item describes once instance of currency being received or paid
        :param dict market: ccxt market
        :param int [since]: when defined, the response items are filtered to only include items after self timestamp
        :param int [limit]: limits the number of items in the response
        :returns dict[]: an array of `funding history structures <https://docs.ccxt.com/?id=funding-history-structure>`
        """
        result = []
        for i in range(0, len(incomes)):
            entry = incomes[i]
            parsed = self.parse_income(entry, market)
            result.append(parsed)
        sorted = self.sort_by(result, 'timestamp')
        symbol = self.safe_string(market, 'symbol')
        return self.filter_by_symbol_since_limit(sorted, symbol, since, limit)

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

    def handle_max_entries_per_request_and_params(self, method: str, maxEntriesPerRequest: Int = None, params={}):
        newMaxEntriesPerRequest = None
        newMaxEntriesPerRequest, params = self.handle_option_and_params(params, method, 'maxEntriesPerRequest')
        if (newMaxEntriesPerRequest is not None) and (newMaxEntriesPerRequest != maxEntriesPerRequest):
            maxEntriesPerRequest = newMaxEntriesPerRequest
        if maxEntriesPerRequest is None:
            maxEntriesPerRequest = 1000  # default to 1000
        return [maxEntriesPerRequest, params]

    def safe_deterministic_call(self, method: str, symbol: Str = None, since: Int = None, limit: Int = None, timeframe: Str = None, params={}):
        maxRetries = None
        maxRetries, params = self.handle_option_and_params(params, method, 'maxRetries', 3)
        errors = 0
        while(errors <= maxRetries):
            try:
                if timeframe and method != 'fetchFundingRateHistory':
                    return getattr(self, method)(symbol, timeframe, since, limit, params)
                else:
                    return getattr(self, method)(symbol, since, limit, params)
            except Exception as e:
                if isinstance(e, RateLimitExceeded):
                    raise e  # if we are rate limited, we should not retry and fail fast
                errors += 1
                if errors > maxRetries:
                    raise e
        return []

    def sort_cursor_paginated_result(self, result):
        first = self.safe_value(result, 0)
        if first is not None:
            if 'timestamp' in first:
                return self.sort_by(result, 'timestamp', True)
            if 'id' in first:
                return self.sort_by(result, 'id', True)
        return result

    def remove_repeated_elements_from_array(self, input, fallbackToTimestamp: bool = True):
        uniqueDic = {}
        uniqueResult = []
        for i in range(0, len(input)):
            entry = input[i]
            uniqValue = self.safe_string_n(entry, ['id', 'timestamp', 0]) if fallbackToTimestamp else self.safe_string(entry, 'id')
            if uniqValue is not None and not (uniqValue in uniqueDic):
                uniqueDic[uniqValue] = 1
                uniqueResult.append(entry)
        valuesLength = len(uniqueResult)
        if valuesLength > 0:
            return uniqueResult
        return input

    def remove_repeated_trades_from_array(self, input):
        uniqueResult = {}
        for i in range(0, len(input)):
            entry = input[i]
            id = self.safe_string(entry, 'id')
            if id is None:
                price = self.safe_string(entry, 'price')
                amount = self.safe_string(entry, 'amount')
                timestamp = self.safe_string(entry, 'timestamp')
                side = self.safe_string(entry, 'side')
                # unique trade identifier
                id = 't_' + str(timestamp) + '_' + side + '_' + price + '_' + amount
            if id is not None and not (id in uniqueResult):
                uniqueResult[id] = entry
        values = list(uniqueResult.values())
        return values

    def remove_keys_from_dict(self, dict: dict, removeKeys: List[str]):
        keys = list(dict.keys())
        newDict = {}
        for i in range(0, len(keys)):
            key = keys[i]
            if not self.in_array(key, removeKeys):
                newDict[key] = dict[key]
        return newDict

    def handle_until_option(self, key: str, request, params, multiplier=1):
        until = self.safe_integer_2(params, 'until', 'till')
        if until is not None:
            request[key] = self.parse_to_int(until * multiplier)
            params = self.omit(params, ['until', 'till'])
        return [request, params]

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

    def parse_liquidation(self, liquidation, market: Market = None):
        raise NotSupported(self.id + ' parseLiquidation() is not supported yet')

    def parse_liquidations(self, liquidations: List[dict], market: Market = None, since: Int = None, limit: Int = None):
        """
 @ignore
        parses liquidation info from the exchange response
        :param dict[] liquidations: each item describes an instance of a liquidation event
        :param dict market: ccxt market
        :param int [since]: when defined, the response items are filtered to only include items after self timestamp
        :param int [limit]: limits the number of items in the response
        :returns dict[]: an array of `liquidation structures <https://docs.ccxt.com/?id=liquidation-structure>`
        """
        result = []
        for i in range(0, len(liquidations)):
            entry = liquidations[i]
            parsed = self.parse_liquidation(entry, market)
            result.append(parsed)
        sorted = self.sort_by(result, 'timestamp')
        symbol = self.safe_string(market, 'symbol')
        return self.filter_by_symbol_since_limit(sorted, symbol, since, limit)

    def parse_greeks(self, greeks: dict, market: Market = None):
        raise NotSupported(self.id + ' parseGreeks() is not supported yet')

    def parse_all_greeks(self, greeks, symbols: Strings = None, params={}):
        #
        # the value of greeks is either a dict or a list
        #
        results = []
        if isinstance(greeks, list):
            for i in range(0, len(greeks)):
                parsedTicker = self.parse_greeks(greeks[i])
                greek = self.extend(parsedTicker, params)
                results.append(greek)
        else:
            marketIds = list(greeks.keys())
            for i in range(0, len(marketIds)):
                marketId = marketIds[i]
                market = self.safe_market(marketId)
                parsed = self.parse_greeks(greeks[marketId], market)
                greek = self.extend(parsed, params)
                results.append(greek)
        symbols = self.market_symbols(symbols)
        return self.filter_by_array(results, 'symbol', symbols)

    def parse_option(self, chain: dict, currency: Currency = None, market: Market = None):
        raise NotSupported(self.id + ' parseOption() is not supported yet')

    def parse_option_chain(self, response: List[object], currencyKey: Str = None, symbolKey: Str = None):
        optionStructures = {}
        for i in range(0, len(response)):
            info = response[i]
            currencyId = self.safe_string(info, currencyKey)
            currency = self.safe_currency(currencyId)
            marketId = self.safe_string(info, symbolKey)
            market = self.safe_market(marketId, None, None, 'option')
            optionStructures[market['symbol']] = self.parse_option(info, currency, market)
        return optionStructures

    def parse_margin_modes(self, response: List[object], symbols: List[str] = None, symbolKey: Str = None, marketType: MarketType = None):
        marginModeStructures = {}
        if marketType is None:
            marketType = 'swap'  # default to swap
        for i in range(0, len(response)):
            info = response[i]
            marketId = self.safe_string(info, symbolKey)
            market = self.safe_market(marketId, None, None, marketType)
            if (symbols is None) or self.in_array(market['symbol'], symbols):
                marginModeStructures[market['symbol']] = self.parse_margin_mode(info, market)
        return marginModeStructures

    def parse_margin_mode(self, marginMode: dict, market: Market = None):
        raise NotSupported(self.id + ' parseMarginMode() is not supported yet')

    def parse_leverages(self, response: List[object], symbols: List[str] = None, symbolKey: Str = None, marketType: MarketType = None):
        leverageStructures = {}
        if marketType is None:
            marketType = 'swap'  # default to swap
        for i in range(0, len(response)):
            info = response[i]
            marketId = self.safe_string(info, symbolKey)
            market = self.safe_market(marketId, None, None, marketType)
            if (symbols is None) or self.in_array(market['symbol'], symbols):
                leverageStructures[market['symbol']] = self.parse_leverage(info, market)
        return leverageStructures

    def parse_leverage(self, leverage: dict, market: Market = None):
        raise NotSupported(self.id + ' parseLeverage() is not supported yet')

    def parse_conversion(self, conversion: dict, fromCurrency: Currency = None, toCurrency: Currency = None):
        raise NotSupported(self.id + ' parseConversion() is not supported yet')

    def fetch_position_history(self, symbol: str, since: Int = None, limit: Int = None, params={}):
        """
        fetches the history of margin added or reduced from contract isolated positions
        :param str [symbol]: unified market symbol
        :param int [since]: timestamp in ms of the position
        :param int [limit]: the maximum amount of candles to fetch, default=1000
        :param dict params: extra parameters specific to the exchange api endpoint
        :returns dict[]: a list of `position structures <https://docs.ccxt.com/?id=position-structure>`
        """
        if self.has['fetchPositionsHistory']:
            positions = self.fetch_positions_history([symbol], since, limit, params)
            return positions
        else:
            raise NotSupported(self.id + ' fetchPositionHistory() is not supported yet')

    def load_markets_and_sign_in(self):
        [self.load_markets(), self.sign_in()]

    def fetch_positions_history(self, symbols: Strings = None, since: Int = None, limit: Int = None, params={}):
        """
        fetches the history of margin added or reduced from contract isolated positions
        :param str [symbol]: unified market symbol
        :param int [since]: timestamp in ms of the position
        :param int [limit]: the maximum amount of candles to fetch, default=1000
        :param dict params: extra parameters specific to the exchange api endpoint
        :returns dict[]: a list of `position structures <https://docs.ccxt.com/?id=position-structure>`
        """
        raise NotSupported(self.id + ' fetchPositionsHistory() is not supported yet')

    def parse_margin_modification(self, data: dict, market: Market = None):
        raise NotSupported(self.id + ' parseMarginModification() is not supported yet')

    def parse_margin_modifications(self, response: List[object], symbols: Strings = None, symbolKey: Str = None, marketType: MarketType = None):
        marginModifications = []
        for i in range(0, len(response)):
            info = response[i]
            marketId = self.safe_string(info, symbolKey)
            market = self.safe_market(marketId, None, None, marketType)
            if (symbols is None) or self.in_array(market['symbol'], symbols):
                marginModifications.append(self.parse_margin_modification(info, market))
        return marginModifications

    def fetch_transfer(self, id: str, code: Str = None, params={}):
        """
        fetches a transfer
        :param str id: transfer id
        :param [str] code: unified currency code
        :param dict params: extra parameters specific to the exchange api endpoint
        :returns dict: a `transfer structure <https://docs.ccxt.com/?id=transfer-structure>`
        """
        raise NotSupported(self.id + ' fetchTransfer() is not supported yet')

    def clean_unsubscription(self, client, subHash: str, unsubHash: str, subHashIsPrefix=False):
        if unsubHash in client.subscriptions:
            del client.subscriptions[unsubHash]
        if not subHashIsPrefix:
            if subHash in client.subscriptions:
                del client.subscriptions[subHash]
            if subHash in client.futures:
                error = UnsubscribeError(self.id + ' ' + subHash)
                client.reject(error, subHash)
        else:
            clientSubscriptions = list(client.subscriptions.keys())
            for i in range(0, len(clientSubscriptions)):
                sub = clientSubscriptions[i]
                if sub.startswith(subHash):
                    del client.subscriptions[sub]
            clientFutures = list(client.futures.keys())
            for i in range(0, len(clientFutures)):
                future = clientFutures[i]
                if future.startswith(subHash):
                    error = UnsubscribeError(self.id + ' ' + future)
                    client.reject(error, future)
        client.resolve(True, unsubHash)

    # =========================================================================
    # Async REST interface
    # =========================================================================
    #
    # Provides async variants of the core HTTP chain so that callers in async
    # contexts (strategies, WebSocket handlers) can await exchange methods
    # directly instead of wrapping them with asyncio.to_thread().
    #
    # Usage:
    #   response = await exchange._request_async(endpoint, params)
    #
    # The sync interface (fetch / fetch2 / request / _request) is unchanged.
    # =========================================================================

    _async_client = None  # lazily initialized httpx.AsyncClient

    async def _get_async_client(self):
        """Lazily create a shared httpx.AsyncClient."""
        if self._async_client is None:
            import httpx
            timeout = httpx.Timeout(self.timeout / 1000, connect=self.timeout / 1000)
            self._async_client = httpx.AsyncClient(timeout=timeout, verify=self.verify and self.validateServerSsl)
        return self._async_client

    async def close_async(self):
        """Close the async HTTP client. Call this on shutdown."""
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None

    async def throttle_async(self, cost=None):
        """Async-friendly rate limiter using asyncio.sleep instead of time.sleep."""
        import asyncio
        now = float(self.milliseconds())
        elapsed = now - self.lastRestRequestTimestamp
        cost = 1 if cost is None else cost
        sleep_time = self.rateLimit * cost
        if elapsed < sleep_time:
            delay = sleep_time - elapsed
            await asyncio.sleep(delay / 1000.0)

    async def fetch_async(self, url, method='GET', headers=None, body=None):
        """Async HTTP request using httpx. Mirrors fetch() error handling."""
        request_headers = self.prepare_request_headers(headers)

        if self.verbose:
            self.log("\nfetch_async Request:", self.id, method, url, "RequestHeaders:", request_headers, "RequestBody:", body)
        self.logger.debug("%s %s, Request: %s %s", method, url, request_headers, body)

        client = await self._get_async_client()

        http_response = None
        http_status_code = None
        http_status_text = None
        json_response = None
        try:
            response = await client.request(
                method,
                url,
                content=body.encode() if body else None,
                headers=request_headers,
            )
            http_status_code = response.status_code
            http_status_text = response.reason_phrase
            http_response = response.text
            json_response = self.parse_json(http_response)

            if self.enableLastHttpResponse:
                self.last_http_response = http_response
            if self.enableLastJsonResponse:
                self.last_json_response = json_response
            if self.enableLastResponseHeaders:
                self.last_response_headers = dict(response.headers)
            if self.verbose:
                self.log("\nfetch_async Response:", self.id, method, url, http_status_code, "ResponseHeaders:", dict(response.headers), "ResponseBody:", http_response)
            self.logger.debug("%s %s, Response: %s %s %s", method, url, http_status_code, dict(response.headers), http_response)

            if http_status_code >= 400:
                self.handle_errors(http_status_code, http_status_text, url, method, dict(response.headers), http_response, json_response, request_headers, body)
                self.handle_http_status_code(http_status_code, http_status_text, url, method, http_response)

        except ExchangeError:
            raise
        except NetworkError:
            raise
        except Exception as e:
            import httpx as _httpx
            if isinstance(e, _httpx.TimeoutException):
                raise RequestTimeout(' '.join([self.id, method, url])) from e
            elif isinstance(e, _httpx.ConnectError):
                raise NetworkError(' '.join([self.id, method, url])) from e
            raise ExchangeError(' '.join([self.id, method, url])) from e

        self.handle_errors(http_status_code, http_status_text, url, method, dict(response.headers), http_response, json_response, request_headers, body)
        if json_response is not None:
            return json_response
        return http_response

    async def fetch2_async(self, path, api='public', method='GET', params=None, headers=None, body=None, config=None):
        """Async version of fetch2: rate limiting + signing + fetch_async."""
        if params is None:
            params = {}
        if config is None:
            config = {}
        if self.enableRateLimit:
            cost = self.calculate_rate_limiter_cost(api, method, path, params, config)
            await self.throttle_async(cost)
        self.lastRestRequestTimestamp = self.milliseconds()
        request = self.sign(path, api, method, params, headers, body)
        self.last_request_headers = request['headers']
        self.last_request_body = request['body']
        self.last_request_url = request['url']
        return await self.fetch_async(request['url'], request['method'], request['headers'], request['body'])

    async def request_async(self, path, api='public', method='GET', params=None, headers=None, body=None, config=None):
        """Async version of request()."""
        return await self.fetch2_async(path, api, method, params or {}, headers, body, config or {})

    async def _request_async(self, endpoint, params=None, config=None):
        """Async version of _request(): unified endpoint handler."""
        if params is None:
            params = {}

        endpoint_config = endpoint.config if endpoint is not None else {}
        if config:
            endpoint_config = self.extend(endpoint_config, config)

        path = endpoint.path
        if isinstance(params, dict) and self.extract_params(path):
            path, params = self.resolve_path(path, params)

        response = await self.request_async(path, endpoint.api, endpoint.method, params, config=endpoint_config)

        if hasattr(self, 'parse_error') and callable(getattr(self, 'parse_error')):
            self.parse_error(response)

        return response
