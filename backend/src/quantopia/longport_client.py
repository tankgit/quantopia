import os
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum

from longport.openapi import Config, QuoteContext, TradeContext


class LongPortCredentials:
    def __init__(self, app_key: str, app_secret: str, access_token: str):
        self.app_key = app_key
        self.app_secret = app_secret
        self.access_token = access_token


class LongPortService:
    """
    LongPort OpenAPI integration service.

    Supports two modes: "live" and "paper" (simulation). Credentials are loaded from environment variables.

    Required environment variables:
      - LIVE:  LONGPORT_LIVE_APP_KEY, LONGPORT_LIVE_APP_SECRET, LONGPORT_LIVE_ACCESS_TOKEN
      - PAPER: LONGPORT_PAPER_APP_KEY, LONGPORT_PAPER_APP_SECRET, LONGPORT_PAPER_ACCESS_TOKEN

    Optional:
      - LONGPORT_HTTP_DOMAIN (e.g. open.longportapp.com)
    """

    _lock = threading.Lock()

    def __init__(self) -> None:
        self._quote_ctx_by_mode: Dict[str, QuoteContext] = {}
        self._trade_ctx_by_mode: Dict[str, TradeContext] = {}

    @staticmethod
    def _load_credentials(mode: str) -> LongPortCredentials:
        mode_upper = mode.upper()
        if mode_upper not in {"LIVE", "PAPER"}:
            raise ValueError("mode must be 'live' or 'paper'")

        prefix = f"LONGPORT_{mode_upper}_"
        app_key = os.getenv(prefix + "APP_KEY")
        app_secret = os.getenv(prefix + "APP_SECRET")
        access_token = os.getenv(prefix + "ACCESS_TOKEN")

        if not app_key or not app_secret or not access_token:
            raise RuntimeError(
                f"Missing LongPort credentials for {mode}. Required: {prefix}APP_KEY, {prefix}APP_SECRET, {prefix}ACCESS_TOKEN"
            )

        return LongPortCredentials(
            app_key=app_key,
            app_secret=app_secret,
            access_token=access_token,
        )

    def _get_quote_context(self, mode: str) -> QuoteContext:
        mode_key = mode.lower()
        if mode_key in self._quote_ctx_by_mode:
            return self._quote_ctx_by_mode[mode_key]
        with self._lock:
            if mode_key in self._quote_ctx_by_mode:
                return self._quote_ctx_by_mode[mode_key]
            creds = self._load_credentials(mode)
            # Map our env vars to SDK expected keys for from_env
            os.environ["LONGPORT_APP_KEY"] = creds.app_key
            os.environ["LONGPORT_APP_SECRET"] = creds.app_secret
            os.environ["LONGPORT_ACCESS_TOKEN"] = creds.access_token
            # Build config from environment
            config = Config.from_env()
            ctx = QuoteContext(config)
            self._quote_ctx_by_mode[mode_key] = ctx
            return ctx

    def _get_trade_context(self, mode: str) -> TradeContext:
        mode_key = mode.lower()
        if mode_key in self._trade_ctx_by_mode:
            return self._trade_ctx_by_mode[mode_key]
        with self._lock:
            if mode_key in self._trade_ctx_by_mode:
                return self._trade_ctx_by_mode[mode_key]
            creds = self._load_credentials(mode)
            # Map our env vars to SDK expected keys for from_env
            os.environ["LONGPORT_APP_KEY"] = creds.app_key
            os.environ["LONGPORT_APP_SECRET"] = creds.app_secret
            os.environ["LONGPORT_ACCESS_TOKEN"] = creds.access_token
            # Build config from environment
            config = Config.from_env()
            ctx = TradeContext(config)
            self._trade_ctx_by_mode[mode_key] = ctx
            return ctx

    # ============ Quote APIs ============
    def _convert_value(self, value: Any) -> Any:
        """Convert Decimal, datetime, Enum to JSON-serializable types"""
        if value is None:
            return None
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value if hasattr(value, "value") else str(value)
        return value

    def get_realtime_quotes(self, symbols: List[str], mode: str = "paper") -> List[Dict[str, Any]]:
        """
        Fetch realtime quotes for the provided symbols.
        Symbols format example: ["AAPL.US", "700.HK"]
        """
        ctx = self._get_quote_context(mode)
        data = ctx.quote(symbols)  # type: ignore[attr-defined]
        quotes: List[Dict[str, Any]] = []
        for item in data or []:
            quote_dict: Dict[str, Any] = {}
            
            # Basic fields
            quote_dict["symbol"] = getattr(item, "symbol", None)
            quote_dict["last_done"] = self._convert_value(getattr(item, "last_done", None))
            quote_dict["open"] = self._convert_value(getattr(item, "open", None))
            quote_dict["high"] = self._convert_value(getattr(item, "high", None))
            quote_dict["low"] = self._convert_value(getattr(item, "low", None))
            quote_dict["prev_close"] = self._convert_value(getattr(item, "prev_close", None))
            quote_dict["volume"] = getattr(item, "volume", None)
            quote_dict["turnover"] = self._convert_value(getattr(item, "turnover", None))
            
            # Status and timestamp
            trade_status = getattr(item, "trade_status", None)
            quote_dict["trade_status"] = self._convert_value(trade_status)
            timestamp = getattr(item, "timestamp", None)
            quote_dict["timestamp"] = self._convert_value(timestamp)
            
            # Optional fields
            quote_dict["price_change"] = self._convert_value(getattr(item, "change_val", None))
            quote_dict["pct_change"] = self._convert_value(getattr(item, "change_rate", None))
            quote_dict["currency"] = getattr(item, "currency", None)
            
            # Pre/post/overnight quotes (can be None or objects)
            pre_quote = getattr(item, "pre_market_quote", None)
            post_quote = getattr(item, "post_market_quote", None)
            overnight_quote = getattr(item, "overnight_quote", None)
            
            if pre_quote is not None:
                quote_dict["pre_market_quote"] = {
                    "last_done": self._convert_value(getattr(pre_quote, "last_done", None)),
                    "timestamp": self._convert_value(getattr(pre_quote, "timestamp", None)),
                }
            else:
                quote_dict["pre_market_quote"] = None
                
            if post_quote is not None:
                quote_dict["post_market_quote"] = {
                    "last_done": self._convert_value(getattr(post_quote, "last_done", None)),
                    "timestamp": self._convert_value(getattr(post_quote, "timestamp", None)),
                }
            else:
                quote_dict["post_market_quote"] = None
                
            if overnight_quote is not None:
                quote_dict["overnight_quote"] = {
                    "last_done": self._convert_value(getattr(overnight_quote, "last_done", None)),
                    "timestamp": self._convert_value(getattr(overnight_quote, "timestamp", None)),
                }
            else:
                quote_dict["overnight_quote"] = None
            
            quotes.append(quote_dict)
        return quotes

    def get_last_done_for_session(self, symbol: str, session_cn: str, mode: str = "paper") -> Dict[str, Any]:
        """
        Return last_done based on target session (中文): 盘前/盘中/盘后/夜盘。
        Falls back to regular last_done when specific session quote is unavailable.
        """
        ctx = self._get_quote_context(mode)
        data = ctx.quote([symbol])  # type: ignore[attr-defined]
        last_done = None
        quote_session = session_cn
        if data:
            item = data[0]
            try:
                if session_cn == "盘前" and getattr(item, "pre_market_quote", None) is not None:
                    last_done = self._convert_value(getattr(item.pre_market_quote, "last_done", None))
                elif session_cn == "盘后" and getattr(item, "post_market_quote", None) is not None:
                    last_done = self._convert_value(getattr(item.post_market_quote, "last_done", None))
                elif session_cn == "夜盘" and getattr(item, "overnight_quote", None) is not None:
                    last_done = self._convert_value(getattr(item.overnight_quote, "last_done", None))
                else:
                    quote_session = "盘中"
                    last_done = self._convert_value(getattr(item, "last_done", None))
            except Exception:
                last_done = self._convert_value(getattr(item, "last_done", None))
        return {"symbol": symbol, "last_done": last_done, "quote_session": quote_session}

    # ============ Asset/Position APIs ============
    def get_assets(self, mode: str = "paper") -> Dict[str, Any]:
        ctx = self._get_trade_context(mode)
        resp = ctx.asset()  # type: ignore[attr-defined]
        if resp is None:
            return {}
        
        # Extract common asset fields manually
        result: Dict[str, Any] = {}
        # Common fields that might exist
        for attr in ["cash", "total_cash", "available_cash", "frozen_cash", "currency"]:
            if hasattr(resp, attr):
                value = getattr(resp, attr)
                result[attr] = self._convert_value(value)
        
        # If it's a dict-like structure, try to convert all values
        try:
            attrs = vars(resp)
            for key, value in attrs.items():
                if not key.startswith("_") and not callable(value):
                    result[key] = self._convert_value(value)
        except Exception:
            pass
        
        return result

    def get_positions(self, mode: str = "paper") -> List[Dict[str, Any]]:
        ctx = self._get_trade_context(mode)
        resp = ctx.position_list()  # type: ignore[attr-defined]
        if not resp:
            return []
        
        positions: List[Dict[str, Any]] = []
        for item in resp:
            pos_dict: Dict[str, Any] = {}
            # Extract common position fields
            for attr in ["symbol", "quantity", "available_quantity", "cost_price", "current_price", "market_value"]:
                if hasattr(item, attr):
                    value = getattr(item, attr)
                    pos_dict[attr] = self._convert_value(value)
            
            # Also try to get all non-private attributes
            try:
                attrs = vars(item)
                for key, value in attrs.items():
                    if not key.startswith("_") and not callable(value) and key not in pos_dict:
                        pos_dict[key] = self._convert_value(value)
            except Exception:
                pass
            
            positions.append(pos_dict)
        return positions

    # ============ Order APIs ============
    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        mode: str = "paper",
        order_type: str = "Limit",
        price: Optional[float] = None,
        time_in_force: Optional[str] = None,
        remark: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        ctx = self._get_trade_context(mode)
        resp = ctx.submit_order(  # type: ignore[attr-defined]
            symbol=symbol,
            order_type=order_type,
            side=side,
            submitted_quantity=quantity,
            price=price,
            time_in_force=time_in_force,
            remark=remark,
            **kwargs,
        )
        
        if resp is None:
            return {}
        
        result: Dict[str, Any] = {}
        # Common order response fields
        for attr in ["order_id", "status", "submitted_at", "updated_at", "filled_quantity", "executed_price"]:
            if hasattr(resp, attr):
                value = getattr(resp, attr)
                result[attr] = self._convert_value(value)
        
        # Get all attributes
        try:
            attrs = vars(resp)
            for key, value in attrs.items():
                if not key.startswith("_") and not callable(value) and key not in result:
                    result[key] = self._convert_value(value)
        except Exception:
            pass
        
        return result

    def cancel_order(self, order_id: str, mode: str = "paper") -> Dict[str, Any]:
        ctx = self._get_trade_context(mode)
        resp = ctx.cancel_order(order_id=order_id)  # type: ignore[attr-defined]
        
        if resp is None:
            return {}
        
        result: Dict[str, Any] = {}
        try:
            attrs = vars(resp)
            for key, value in attrs.items():
                if not key.startswith("_") and not callable(value):
                    result[key] = self._convert_value(value)
        except Exception:
            pass
        
        return result

    def list_today_orders(self, mode: str = "paper") -> List[Dict[str, Any]]:
        ctx = self._get_trade_context(mode)
        resp = ctx.today_orders()  # type: ignore[attr-defined]
        
        if not resp:
            return []
        
        orders: List[Dict[str, Any]] = []
        for item in resp:
            order_dict: Dict[str, Any] = {}
            try:
                attrs = vars(item)
                for key, value in attrs.items():
                    if not key.startswith("_") and not callable(value):
                        order_dict[key] = self._convert_value(value)
            except Exception:
                pass
            orders.append(order_dict)
        return orders


