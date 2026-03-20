"""Lightweight Lighter signer client (no external SDK dependency).

This is a minimal extraction so callers (e.g., demos/tests) can sign and submit
orders/cancellations without importing example modules or the official SDK.
"""

from __future__ import annotations

import ctypes
import json
import os
import platform
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from exchanges.logger import setup_logger

logger = setup_logger("lighter.signer")

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_SIGNER_SEARCH_PATHS = [
    os.path.join(_MODULE_DIR, "signers"),
    os.path.join(os.path.dirname(_MODULE_DIR), "external", "lighter-python", "lighter", "signers"),
    os.path.join(os.path.dirname(_MODULE_DIR), "Signer", "Lighter"),
    os.path.join(os.path.dirname(_MODULE_DIR), "Signer", "lighter"),
]
_SIGNER_FILENAMES = {
    ("windows", "amd64"): ["lighter-signer-windows-amd64.dll"],
    ("windows", "x86_64"): ["lighter-signer-windows-amd64.dll"],
    ("linux", "x86_64"): ["lighter-signer-linux-amd64.so"],
    ("linux", "amd64"): ["lighter-signer-linux-amd64.so"],
    ("linux", "arm64"): ["lighter-signer-linux-arm64.so"],
    ("linux", "aarch64"): ["lighter-signer-linux-arm64.so"],
    ("darwin", "arm64"): ["lighter-signer-darwin-arm64.dylib"],
    ("darwin", "aarch64"): ["lighter-signer-darwin-arm64.dylib"],
}


class StrOrErr(ctypes.Structure):
    _fields_ = [("str", ctypes.c_char_p), ("err", ctypes.c_char_p)]


class SimpleSignerError(Exception):
    """Raised when the native signer cannot be initialised or used."""


class SimpleSignerClient:
    """Thin wrapper around Lighter's native signer shared library."""

    TX_TYPE_CREATE_ORDER = 14
    TX_TYPE_CANCEL_ORDER = 15

    ORDER_TYPE_LIMIT = 0
    ORDER_TYPE_MARKET = 1
    ORDER_TYPE_STOP_LOSS = 2
    ORDER_TYPE_STOP_LOSS_LIMIT = 3
    ORDER_TYPE_TAKE_PROFIT = 4
    ORDER_TYPE_TAKE_PROFIT_LIMIT = 5

    ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL = 0
    ORDER_TIME_IN_FORCE_GOOD_TILL_TIME = 1
    ORDER_TIME_IN_FORCE_POST_ONLY = 2

    NIL_TRIGGER_PRICE = 0
    DEFAULT_28_DAY_ORDER_EXPIRY = -1
    DEFAULT_IOC_EXPIRY = 0
    DEFAULT_10_MIN_AUTH_EXPIRY = -1
    MINUTE = 60

    def __init__(
        self,
        base_url: str,
        private_key: str,
        account_index: int,
        api_key_index: int = 0,
        *,
        session: Optional[requests.Session] = None,
        timeout: Optional[float] = None,
        verify_ssl: bool = True,
        signer_dir: Optional[str] = None,
        chain_id: Optional[int] = None,
    ) -> None:
        if not private_key:
            raise SimpleSignerError("API private key is required for signer initialisation")

        self.base_url = base_url.rstrip("/")
        self.account_index = int(account_index)
        self.api_key_index = int(api_key_index or 0)
        self.timeout = timeout or 10.0
        self.verify_ssl = verify_ssl
        self._nonce: Optional[int] = None
        self._nonce_lock = threading.Lock()
        self.session = session or requests.Session()
        self.private_key = self._sanitize_private_key(private_key)
        self.chain_id = int(chain_id) if chain_id is not None else (304 if "mainnet" in self.base_url else 300)
        self._market_multipliers: Dict[int, Tuple[int, int]] = {}

        self.signer = self._load_library(signer_dir)
        self._configure_library()
        self._create_client()

    # ---- initialisation helpers -------------------------------------------------
    def _sanitize_private_key(self, key: str) -> str:
        cleaned = key.strip()
        cleaned = cleaned[2:] if cleaned.startswith("0x") else cleaned
        if len(cleaned) not in (64, 80):
            raise SimpleSignerError("API private key must be 32 or 40 bytes (64/80 hex characters)")
        try:
            int(cleaned, 16)
        except ValueError as exc:
            raise SimpleSignerError("API private key contains non-hex characters") from exc
        return cleaned

    def _load_library(self, signer_dir: Optional[str]) -> ctypes.CDLL:
        system = platform.system().lower()
        arch = platform.machine().lower()
        filenames = _SIGNER_FILENAMES.get((system, arch))
        if not filenames:
            raise SimpleSignerError(f"Unsupported platform/architecture: {system}/{arch}")

        search_paths: List[str] = []
        if signer_dir:
            search_paths.append(signer_dir)
        search_paths.extend(_DEFAULT_SIGNER_SEARCH_PATHS)

        for candidate_dir in search_paths:
            if not candidate_dir:
                continue
            for filename in filenames:
                candidate = os.path.join(candidate_dir, filename)
                if os.path.isfile(candidate):
                    return ctypes.CDLL(candidate)

        filenames_str = "', '".join(filenames)
        raise SimpleSignerError(
            f"Unable to locate signer library. Tried filenames: '{filenames_str}'. "
            f"Searched in: {search_paths}. Set `signer_dir` or place the library under api/signers/ or Signer/lighter/."
        )

    def _configure_library(self) -> None:
        self.signer.CreateClient.argtypes = [
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_longlong,
        ]
        self.signer.CreateClient.restype = ctypes.c_char_p

        self.signer.CheckClient.argtypes = [ctypes.c_int, ctypes.c_longlong]
        self.signer.CheckClient.restype = ctypes.c_char_p

        self.signer.CreateAuthToken.argtypes = [
            ctypes.c_longlong,
            ctypes.c_int,
            ctypes.c_longlong,
        ]
        self.signer.CreateAuthToken.restype = StrOrErr

        self.signer.SignCreateOrder.argtypes = [
            ctypes.c_int,
            ctypes.c_longlong,
            ctypes.c_longlong,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_longlong,
            ctypes.c_longlong,
            ctypes.c_int,
            ctypes.c_longlong,
        ]
        self.signer.SignCreateOrder.restype = StrOrErr

        self.signer.SignCancelOrder.argtypes = [
            ctypes.c_int,
            ctypes.c_longlong,
            ctypes.c_longlong,
            ctypes.c_int,
            ctypes.c_longlong,
        ]
        self.signer.SignCancelOrder.restype = StrOrErr

    def _create_client(self) -> None:
        err_ptr = self.signer.CreateClient(
            self.base_url.encode("utf-8"),
            self.private_key.encode("utf-8"),
            ctypes.c_int(self.chain_id),
            ctypes.c_int(self.api_key_index),
            ctypes.c_longlong(self.account_index),
        )
        if err_ptr:
            raise SimpleSignerError(err_ptr.decode("utf-8"))

    # ---- signer primitives ------------------------------------------------------
    def _decode_str_or_err(self, result: StrOrErr) -> Tuple[Optional[str], Optional[str]]:
        payload = result.str.decode("utf-8") if result.str else None
        error = result.err.decode("utf-8") if result.err else None
        return payload, error

    def _fetch_nonce(self) -> int:
        url = f"{self.base_url}/api/v1/nextNonce"
        params = {
            "account_index": self.account_index,
            "api_key_index": self.api_key_index,
        }
        try:
            response = self.session.get(url, params=params, timeout=self.timeout, verify=self.verify_ssl)
        except requests.RequestException as exc:
            raise SimpleSignerError(f"Failed to fetch nonce: {exc}") from exc

        if response.status_code != 200:
            raise SimpleSignerError(f"Nonce request failed with status {response.status_code}: {response.text}")

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise SimpleSignerError(f"Invalid nonce response: {exc}") from exc

        nonce_value = payload.get("nonce")
        if nonce_value is None:
            raise SimpleSignerError(f"Nonce missing in response: {payload}")
        self._nonce = int(nonce_value) - 1
        return self._nonce

    def _next_nonce(self) -> int:
        with self._nonce_lock:
            if self._nonce is None:
                self._fetch_nonce()
            assert self._nonce is not None
            self._nonce += 1
            return self._nonce

    def _send_tx(self, tx_type: int, tx_info: str, price_protection: bool = True) -> Dict[str, Any]:
        if not tx_info:
            raise SimpleSignerError("Signer returned empty tx_info payload")

        url = f"{self.base_url}/api/v1/sendTx"
        files = {
            "tx_type": (None, str(int(tx_type))),
            "tx_info": (None, tx_info),
            "price_protection": (None, "true" if price_protection else "false"),
        }
        try:
            response = self.session.post(url, files=files, timeout=self.timeout, verify=self.verify_ssl)
        except requests.RequestException as exc:
            raise SimpleSignerError(f"Failed to submit transaction: {exc}") from exc

        try:
            payload = response.json() if response.text else {}
        except json.JSONDecodeError as exc:
            raise SimpleSignerError(f"Failed to decode sendTx response: {exc}") from exc

        if response.status_code != 200:
            message = payload.get("message") or response.text
            raise SimpleSignerError(f"Transaction rejected ({response.status_code}): {message}")
        return payload

    def _send_tx_batch(self, tx_list: List[Tuple[int, str]], price_protection: bool = True) -> Dict[str, Any]:
        """Submit a batch of signed transactions."""
        if not tx_list:
            raise SimpleSignerError("Empty transaction list")

        url = f"{self.base_url}/api/v1/sendTxBatch"

        tx_types: List[int] = []
        tx_infos: List[str] = []

        for tx_type, tx_info in tx_list:
            if not tx_info:
                raise SimpleSignerError("Empty tx_info in batch")
            tx_types.append(int(tx_type))
            tx_infos.append(tx_info)

        files = {
            "tx_types": (None, json.dumps(tx_types)),
            "tx_infos": (None, json.dumps(tx_infos)),
            "price_protection": (None, "true" if price_protection else "false"),
        }

        try:
            response = self.session.post(url, files=files, timeout=self.timeout * 2, verify=self.verify_ssl)
        except requests.RequestException as exc:
            raise SimpleSignerError(f"Failed to submit batch transaction: {exc}") from exc

        try:
            payload = response.json() if response.text else {}
        except json.JSONDecodeError as exc:
            raise SimpleSignerError(f"Failed to decode sendTxBatch response: {exc}") from exc

        if response.status_code != 200:
            message = payload.get("message") or response.text
            raise SimpleSignerError(f"Batch transaction rejected ({response.status_code}): {message}")
        return payload

    # ---- public API -------------------------------------------------------------
    def check_client(self) -> Optional[str]:
        result = self.signer.CheckClient(ctypes.c_int(self.api_key_index), ctypes.c_longlong(self.account_index))
        return result.decode("utf-8") if result else None

    def create_auth_token_with_expiry(self, deadline: int = DEFAULT_10_MIN_AUTH_EXPIRY) -> Tuple[Optional[str], Optional[str]]:
        actual_deadline = deadline
        if deadline == self.DEFAULT_10_MIN_AUTH_EXPIRY:
            actual_deadline = int(time.time() + 10 * self.MINUTE)
        payload, error = self._decode_str_or_err(
            self.signer.CreateAuthToken(
                ctypes.c_longlong(actual_deadline),
                ctypes.c_int(self.api_key_index),
                ctypes.c_longlong(self.account_index)
            )
        )
        return payload, error

    def create_order(
        self,
        *,
        market_index: int,
        client_order_index: int,
        base_amount: int,
        price: int,
        is_ask: bool,
        order_type: int,
        time_in_force: int,
        reduce_only: bool = False,
        trigger_price: int = NIL_TRIGGER_PRICE,
        order_expiry: int = DEFAULT_28_DAY_ORDER_EXPIRY,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[str]]:
        for attempt in range(2):
            nonce = self._next_nonce()
            payload, error = self._decode_str_or_err(
                self.signer.SignCreateOrder(
                    ctypes.c_int(market_index),
                    ctypes.c_longlong(client_order_index),
                    ctypes.c_longlong(base_amount),
                    ctypes.c_int(price),
                    ctypes.c_int(int(is_ask)),
                    ctypes.c_int(order_type),
                    ctypes.c_int(time_in_force),
                    ctypes.c_int(int(reduce_only)),
                    ctypes.c_int(trigger_price),
                    ctypes.c_longlong(order_expiry),
                    ctypes.c_longlong(nonce),
                    ctypes.c_int(self.api_key_index),
                    ctypes.c_longlong(self.account_index),
                )
            )
            if error:
                return None, None, error
            try:
                parsed_payload = json.loads(payload) if payload else None
            except json.JSONDecodeError:
                parsed_payload = {"raw": payload}

            try:
                response = self._send_tx(self.TX_TYPE_CREATE_ORDER, payload or "")
                return parsed_payload, response, None
            except SimpleSignerError as exc:
                error_msg = str(exc)
                if "invalid nonce" in error_msg.lower() and attempt == 0:
                    self._fetch_nonce()
                    time.sleep(0.1)
                    continue
                return parsed_payload, None, error_msg

        return parsed_payload, None, "Unable to submit order after nonce retries"

    def cancel_order(
        self,
        *,
        market_index: int,
        order_index: int,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[str]]:
        for attempt in range(2):
            nonce = self._next_nonce()
            payload, error = self._decode_str_or_err(
                self.signer.SignCancelOrder(
                    ctypes.c_int(market_index),
                    ctypes.c_longlong(order_index),
                    ctypes.c_longlong(nonce),
                    ctypes.c_int(self.api_key_index),
                    ctypes.c_longlong(self.account_index),
                )
            )
            if error:
                return None, None, error
            try:
                parsed_payload = json.loads(payload) if payload else None
            except json.JSONDecodeError:
                parsed_payload = {"order_index": order_index, "raw": payload}

            try:
                response = self._send_tx(self.TX_TYPE_CANCEL_ORDER, payload or "")
                return parsed_payload, response, None
            except SimpleSignerError as exc:
                error_msg = str(exc)
                if "invalid nonce" in error_msg.lower() and attempt == 0:
                    self._fetch_nonce()
                    time.sleep(0.1)
                    continue
                return parsed_payload, None, error_msg

        return parsed_payload, None, "Unable to cancel order after nonce retries"

    def create_order_batch(
        self,
        orders: List[Dict[str, Any]],
    ) -> Tuple[List[Optional[Dict[str, Any]]], Optional[Dict[str, Any]], Optional[str]]:
        """Create multiple orders in a single batch transaction."""
        if not orders:
            return [], None, "Empty order list"

        tx_list: List[Tuple[int, str]] = []
        payloads: List[Optional[Dict[str, Any]]] = []

        for attempt in range(2):
            tx_list.clear()
            payloads.clear()

            for order in orders:
                nonce = self._next_nonce()

                payload, error = self._decode_str_or_err(
                    self.signer.SignCreateOrder(
                        ctypes.c_int(order.get("market_index")),
                        ctypes.c_longlong(order.get("client_order_index")),
                        ctypes.c_longlong(order.get("base_amount")),
                        ctypes.c_int(order.get("price")),
                        ctypes.c_int(int(order.get("is_ask"))),
                        ctypes.c_int(order.get("order_type")),
                        ctypes.c_int(order.get("time_in_force")),
                        ctypes.c_int(int(order.get("reduce_only", False))),
                        ctypes.c_int(order.get("trigger_price", self.NIL_TRIGGER_PRICE)),
                        ctypes.c_longlong(order.get("order_expiry", self.DEFAULT_28_DAY_ORDER_EXPIRY)),
                        ctypes.c_longlong(nonce),
                        ctypes.c_int(self.api_key_index),
                        ctypes.c_longlong(self.account_index),
                    )
                )

                if error:
                    return payloads, None, error

                try:
                    parsed_payload = json.loads(payload) if payload else None
                except json.JSONDecodeError:
                    parsed_payload = {"raw": payload}

                payloads.append(parsed_payload)
                tx_list.append((self.TX_TYPE_CREATE_ORDER, payload or ""))

            try:
                response = self._send_tx_batch(tx_list)
                return payloads, response, None
            except SimpleSignerError as exc:
                message = str(exc)
                if "invalid nonce" in message.lower() and attempt == 0:
                    with self._nonce_lock:
                        self._fetch_nonce()
                    time.sleep(0.1)
                    continue
                return payloads, None, message

        return payloads, None, "Unable to submit batch orders after nonce retries"

    # ---- account helpers ------------------------------------------------------
    def fetch_account(self) -> Optional[Dict[str, Any]]:
        params = {"by": "index", "value": str(self.account_index), "api_key_index": self.api_key_index}
        endpoints = ["/api/v1/account", f"/api/v1/accounts/{self.account_index}"]
        payload = None
        for endpoint in endpoints:
            try:
                resp = self.session.get(f"{self.base_url}{endpoint}", params=params, timeout=self.timeout, verify=self.verify_ssl)
                payload = resp.json()
            except requests.RequestException as exc:
                raise SimpleSignerError(f"Account request failed: {exc}") from exc
            except json.JSONDecodeError as exc:
                raise SimpleSignerError(f"Account response decode failed: {exc}") from exc
            if isinstance(payload, dict) and payload.get("error"):
                continue
            break

        if isinstance(payload, dict):
            accounts = payload.get("accounts")
            if isinstance(accounts, list) and accounts:
                primary = accounts[0]
                if isinstance(primary, dict):
                    return primary
            if "account" in payload and isinstance(payload.get("account"), dict):
                return payload.get("account")
        return payload if isinstance(payload, dict) else None

    def fetch_positions(self) -> Optional[List[Dict[str, Any]]]:
        account = self.fetch_account()
        if not isinstance(account, dict):
            return None
        positions = account.get("positions")
        if isinstance(positions, list):
            return positions
        return None

    def _infer_position_sign(self, payload: Dict[str, Any]) -> Optional[int]:
        sign_raw = payload.get("sign")
        if sign_raw is not None:
            try:
                sign_num = float(sign_raw)
            except (TypeError, ValueError):
                sign_num = None
            if sign_num is not None:
                if sign_num > 0:
                    return 1
                if sign_num < 0:
                    return -1
                return 0
        for key in ("side", "position_side", "positionSide", "direction"):
            side_raw = payload.get(key)
            if side_raw is None:
                continue
            side = str(side_raw).strip().lower()
            if side in ("long", "buy"):
                return 1
            if side in ("short", "sell"):
                return -1
            if side in ("flat", "none"):
                return 0
        for key in ("is_long", "isLong"):
            if key in payload:
                return 1 if bool(payload.get(key)) else 0
        for key in ("is_short", "isShort"):
            if key in payload:
                return -1 if bool(payload.get(key)) else 0
        return None

    def parse_position_size(
        self, payload: Dict[str, Any], *, position_sign: Optional[int] = None
    ) -> Optional[float]:
        size_raw = payload.get("position")
        if size_raw is None:
            size_raw = payload.get("position_size") or payload.get("size") or payload.get("qty")
        try:
            size_val = float(size_raw or 0.0)
        except (TypeError, ValueError):
            return None
        sign_val = self._infer_position_sign(payload)
        if sign_val is not None:
            return abs(size_val) * sign_val
        if position_sign is not None:
            return size_val * float(position_sign or 1)
        return size_val

    def fetch_position_size(self, market_index: int, position_sign: Optional[int] = None) -> Optional[float]:
        positions = self.fetch_positions()
        if positions is None:
            return None
        for position in positions:
            if not isinstance(position, dict):
                continue
            if int(position.get("market_id", -1)) != int(market_index):
                continue
            size_val = self.parse_position_size(position, position_sign=position_sign)
            if size_val is None:
                return None
            return size_val
        return 0.0

    def fetch_market_multipliers(self, market_index: int) -> Optional[Tuple[int, int]]:
        cached = self._market_multipliers.get(int(market_index))
        if cached:
            return cached
        try:
            resp = self.session.get(
                f"{self.base_url}/api/v1/orderBookDetails",
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
            payload = resp.json()
        except requests.RequestException as exc:
            raise SimpleSignerError(f"Market details request failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise SimpleSignerError(f"Market details response decode failed: {exc}") from exc

        books: List[Dict[str, Any]] = []
        if isinstance(payload, dict):
            primary = payload.get("order_book_details")
            if isinstance(primary, list):
                books.extend(primary)
            spot = payload.get("spot_order_book_details")
            if isinstance(spot, list):
                books.extend(spot)

        if not books:
            return None

        for item in books:
            try:
                if int(item.get("market_id")) != int(market_index):
                    continue
                size_dec = int(item.get("supported_size_decimals", 3))
                price_dec = int(item.get("supported_price_decimals", 3))
                multipliers = (10 ** size_dec, 10 ** price_dec)
                self._market_multipliers[int(market_index)] = multipliers
                return multipliers
            except Exception:
                continue
        return None

    def place_market_order(
        self,
        *,
        market_index: int,
        side: str,
        amount: float,
        price: float,
        reduce_only: bool = False,
    ) -> Optional[Dict[str, Any]]:
        # Lighter "market" execution is commonly done as an aggressive IOC limit.
        # The native signer expects a valid `order_expiry` for IOC; -1 is rejected.
        multipliers = self.fetch_market_multipliers(market_index)
        if not multipliers:
            logger.warning("Market multipliers missing (market_index=%s); cannot place order", market_index)
            return None
        size_mult, price_mult = multipliers
        client_order_index = int(time.time() * 1000) % 1_000_000_000
        base_amount = int(amount * size_mult)
        price_int = int(price * price_mult)
        is_ask = side.lower() == "sell"
        payload, tx_resp, err = self.create_order(
            market_index=market_index,
            client_order_index=client_order_index,
            base_amount=base_amount,
            price=price_int,
            is_ask=is_ask,
            order_type=self.ORDER_TYPE_LIMIT,
            time_in_force=self.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL,
            reduce_only=reduce_only,
            trigger_price=self.NIL_TRIGGER_PRICE,
            order_expiry=self.DEFAULT_IOC_EXPIRY,
        )
        if err:
            logger.warning(
                "Lighter order rejected (market_index=%s side=%s amount=%s price=%s): %s",
                market_index,
                side,
                amount,
                price,
                err,
            )
            return None
        order_id = client_order_index
        if isinstance(payload, dict):
            order_id = (
                payload.get("client_order_index")
                or payload.get("clientOrderIndex")
                or payload.get("ClientOrderIndex")
                or client_order_index
            )
        result = {
            "order_id": str(order_id),
            "amount": amount,
            "price": price,
            "raw": {"payload": payload, "tx": tx_resp},
        }
        return result
