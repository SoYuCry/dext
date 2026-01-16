"""Minimal signer wrapper for Lighter REST transactions (no BaseExchangeClient dependency)."""
from __future__ import annotations

import ctypes
import json
import os
import platform
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

DEFAULT_HTTP_TIMEOUT = 10.0

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
        self.timeout = timeout or DEFAULT_HTTP_TIMEOUT
        self.verify_ssl = verify_ssl
        self._nonce: Optional[int] = None
        self._nonce_lock = threading.Lock()
        self.session = session or requests.Session()
        self.private_key = self._sanitize_private_key(private_key)
        self.chain_id = int(chain_id) if chain_id is not None else (304 if "mainnet" in self.base_url else 300)

        self.signer = self._load_library(signer_dir)
        self._configure_library()
        self._create_client()

    # ---- initialisation helpers -------------------------------------------------
    def _sanitize_private_key(self, key: str) -> str:
        cleaned = key.strip()
        cleaned = cleaned[2:] if cleaned.startswith("0x") else cleaned
        if len(cleaned) not in (64, 80):
            raise SimpleSignerError(
                "API private key must be 32 or 40 bytes expressed as hex (64 or 80 characters)"
            )
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
        if isinstance(filenames, str):
            filenames = [filenames]

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
            f"Searched in: {search_paths}. "
            "Set `signer_lib_dir` in config or place the library under api/signers/ or Signer/lighter/."
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
        result = self.signer.CreateClient(
            ctypes.c_char_p(self.base_url.encode("utf-8")),
            ctypes.c_char_p(self.private_key.encode("utf-8")),
            ctypes.c_int(self.api_key_index),
            ctypes.c_int(self.account_index),
            ctypes.c_longlong(self.chain_id),
        )
        if result:
            message = result.decode("utf-8")
            if message:
                raise SimpleSignerError(message)
        self._fetch_nonce()

    # ---- nonce helpers ---------------------------------------------------------
    def _decode_str_or_err(self, payload: StrOrErr) -> Tuple[Optional[str], Optional[str]]:
        return (payload.str.decode("utf-8") if payload.str else None, payload.err.decode("utf-8") if payload.err else None)

    def _fetch_nonce(self) -> Optional[int]:
        url = f"{self.base_url}/api/v1/nonce"
        try:
            response = self.session.get(
                url,
                params={
                    "api_key_index": self.api_key_index,
                    "account_index": self.account_index,
                },
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise SimpleSignerError(f"Failed to fetch nonce: {exc}") from exc

        nonce_value = payload.get("nonce") if isinstance(payload, dict) else None
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

    # ---- public API ------------------------------------------------------------
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
        if not tx_list:
            raise SimpleSignerError("Empty transaction list")

        url = f"{self.base_url}/api/v1/sendTxBatch"
        tx_types = []
        tx_infos = []
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
                    with self._nonce_lock:
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
                    with self._nonce_lock:
                        self._fetch_nonce()
                    time.sleep(0.1)
                    continue
                return parsed_payload, None, error_msg
        return parsed_payload, None, "Unable to cancel order after nonce retries"
