"""Helper module for interacting with Bybit V5 API using HMAC signatures.

This module provides a `BybitClient` class that encapsulates common REST
operations against Bybit's V5 API. It supports both testnet and mainnet
endpoints, authenticating via system‑generated API keys (HMAC) and signing
requests according to Bybit's specification. The code deliberately avoids
external dependencies beyond the widely available `requests` library.

Typical usage:

    from bybit_api_helpers import BybitClient

    client = BybitClient(
        api_key="your_api_key",
        api_secret="your_api_secret",
        base_url="https://api-testnet.bybit.com",
    )

    # Get consolidated USD value of unified account
    usd_total = client.unified_total_usd()
    print("Unified balance (USD):", usd_total)

    # Transfer 0.1 BTC from FUND to UNIFIED
    resp = client.inter_transfer("BTC", "0.1", "FUND", "UNIFIED")
    print("Transfer response:", resp)

    # Get list of transferable coins
    print(client.transfer_coin_list())

The client attempts to minimise duplicate network requests and leave most
error handling to the caller. Raw API responses are returned as Python
dictionaries (JSON objects) for convenience.

"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Dict, List, Optional

import requests


class BybitClient:
    """Simple REST client for Bybit V5 API using HMAC authentication.

    Only system‑generated (HMAC) keys are supported. RSA keys require a
    different signature algorithm and are not implemented here.
    """

    def __init__(self, api_key: str, api_secret: str, base_url: str, recv_window: int = 5000) -> None:
        self.api_key = api_key.strip()
        self.api_secret = api_secret.strip().encode()
        self.base_url = base_url.rstrip("/")
        self.recv_window = int(recv_window)

    def _sign(self, payload: str, timestamp: str) -> str:
        """Compute the HMAC‑SHA256 signature for the given payload.

        The sign string is composed of ``timestamp + api_key + recv_window + payload``
        as described in Bybit's documentation. The resulting signature is a
        lowercase hexadecimal string. See
        https://bybit-exchange.github.io/docs/v5/guide#http-request-signature for details.

        Args:
            payload: The query string (for GET) or raw request body (for POST).
            timestamp: The millisecond timestamp as a string.

        Returns:
            Hex digest of the signature as a string.
        """
        sign_str = f"{timestamp}{self.api_key}{self.recv_window}{payload}"
        digest = hmac.new(self.api_secret, sign_str.encode(), hashlib.sha256).hexdigest()
        return digest

    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None,
                 body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a signed HTTP request to the Bybit API.

        Args:
            method: HTTP verb ('GET', 'POST', etc.).
            path: Endpoint path starting with '/v5/...'.
            params: Query parameters for GET requests.
            body: JSON body for POST requests.

        Returns:
            Parsed JSON response as a dictionary.

        Raises:
            requests.HTTPError: If the response status is not 200.
            ValueError: On JSON decode failure.
        """
        url = f"{self.base_url}{path}"
        # Build query string. Must sort keys alphabetically for signature
        query_string = ''
        if params:
            sorted_items = sorted((k, params[k]) for k in params)
            query_string = '&'.join(f"{k}={v}" for k, v in sorted_items)
        # Prepare body for signing
        body_str = ''
        if body is not None and method.upper() != 'GET':
            # Use compact JSON (no whitespace) for signature and sending
            body_str = json.dumps(body, separators=(',', ':'))
        # Compute timestamp and signature
        timestamp = str(int(time.time() * 1000))
        payload = query_string if method.upper() == 'GET' else body_str
        signature = self._sign(payload, timestamp)
        # Prepare headers
        headers = {
            'X-BAPI-API-KEY': self.api_key,
            'X-BAPI-TIMESTAMP': timestamp,
            'X-BAPI-SIGN': signature,
            'X-BAPI-RECV-WINDOW': str(self.recv_window),
        }
        # For POST/PUT we send JSON body
        response = requests.request(method=method, url=url,
                                    params=params if method.upper() == 'GET' else None,
                                    data=body_str if method.upper() != 'GET' else None,
                                    headers=headers)
        # Raise on HTTP errors
        response.raise_for_status()
        return response.json()

    # ----------------------- Public API methods -----------------------

    def unified_coins(self) -> List[Dict[str, Any]]:
        """Return all coins and balances for the Unified account.

        Returns a list of dictionaries. Each dictionary has keys like
        ``coin``, ``walletBalance``, ``usdValue``, etc. Note that Bybit
        requires the ``accountType`` parameter and that ``coin`` is optional
        (omitting it returns all coins). See
        https://bybit-exchange.github.io/docs/v5/account/wallet-balance.
        """
        resp = self._request('GET', '/v5/account/wallet-balance', params={'accountType': 'UNIFIED'})
        if resp.get('retCode') != 0:
            return []
        list_items = resp.get('result', {}).get('list', [])
        if not list_items:
            return []
        return list_items[0].get('coin', [])

    def unified_total_usd(self) -> float:
        """Return the total equity (USD) for the Unified account.

        This corresponds to the ``totalEquity`` field in the API
        response. If no data is available, returns 0.0.
        """
        resp = self._request('GET', '/v5/account/wallet-balance', params={'accountType': 'UNIFIED'})
        if resp.get('retCode') != 0:
            return 0.0
        list_items = resp.get('result', {}).get('list', [])
        if not list_items:
            return 0.0
        try:
            return float(list_items[0].get('totalEquity', 0))
        except Exception:
            return 0.0

    def fund_coins(self) -> List[Dict[str, Any]]:
        """Return all coin balances in the Funding (FUND) account.

        The response includes fields ``walletBalance`` and ``transferBalance``
        per coin, but does not provide USD values. See
        https://bybit-exchange.github.io/docs/v5/asset/balance/all-balance for
        parameter details【908210606956782†L110-L124】.
        """
        resp = self._request('GET', '/v5/asset/transfer/query-account-coins-balance',
                              params={'accountType': 'FUND'})
        if resp.get('retCode') != 0:
            return []
        return resp.get('result', {}).get('balance', [])

    def transfer_coin_list(self, from_account: str = 'FUND', to_account: str = 'UNIFIED') -> List[str]:
        """Return a list of coins transferable between the given account types.

        Args:
            from_account: Source account type (e.g. 'FUND', 'UNIFIED').
            to_account: Destination account type (e.g. 'UNIFIED', 'FUND').

        Returns:
            A list of coin symbols.
        """
        params = {'fromAccountType': from_account, 'toAccountType': to_account}
        resp = self._request('GET', '/v5/asset/transfer/query-transfer-coin-list', params=params)
        if resp.get('retCode') != 0:
            return []
        return resp.get('result', {}).get('list', [])

    def inter_transfer(self, coin: str, amount: str, from_account: str, to_account: str) -> Dict[str, Any]:
        """Perform an internal transfer between account types.

        Args:
            coin: Coin symbol (e.g. 'BTC', 'USDT').
            amount: Amount to transfer (string). Decimal amounts are allowed.
            from_account: Source account type (e.g. 'FUND').
            to_account: Destination account type (e.g. 'UNIFIED').

        Returns:
            The API response as a dictionary.
        """
        # Generate a random transferId (UUID v4). Here we use time and random bits for simplicity.
        import uuid
        transfer_id = str(uuid.uuid4())
        body = {
            'transferId': transfer_id,
            'coin': coin,
            'amount': amount,
            'fromAccountType': from_account,
            'toAccountType': to_account,
        }
        return self._request('POST', '/v5/asset/transfer/inter-transfer', body=body)

    def get_unified_balance(self, coin: str) -> Dict[str, Any]:
        """Return the balance for a specific coin in the Unified account.

        Args:
            coin: Coin symbol (uppercase).

        Returns:
            A dictionary with balance information. Empty dict if not found.
        """
        params = {'accountType': 'UNIFIED', 'coin': coin}
        resp = self._request('GET', '/v5/account/wallet-balance', params=params)
        if resp.get('retCode') != 0:
            return {}
        list_items = resp.get('result', {}).get('list', [])
        if not list_items:
            return {}
        coins = list_items[0].get('coin', [])
        for c in coins:
            if c.get('coin') == coin:
                return c
        return {}

    def ticker(self, category: str, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch market ticker information for a given symbol.

        The ticker endpoint does not require authentication and supports
        categories like 'spot', 'linear' (USDT perpetual), or 'inverse'.

        Args:
            category: Market category ('spot', 'linear', 'inverse', etc.).
            symbol: Trading pair symbol (e.g. 'BTCUSDT').

        Returns:
            Dictionary with ticker info (including lastPrice, bid1Price, etc.)
            or None on failure.
        """
        url = f"{self.base_url}/v5/market/tickers"
        params = {'category': category, 'symbol': symbol}
        resp = requests.get(url, params=params)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get('retCode') != 0:
            return None
        items = data.get('result', {}).get('list', [])
        return items[0] if items else None
