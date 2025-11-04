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
    def get_assets(self, mode: str = "paper", currency: Optional[str] = None) -> Dict[str, Any]:
        """
        获取账户资产信息
        注意：LongPort SDK 的 TradeContext 可能没有 asset() 方法
        尝试多种方法获取资产信息
        """
        ctx = self._get_trade_context(mode)
        
        # 列出所有可用的方法和属性（用于调试）
        print(f"[DEBUG] TradeContext 类型: {type(ctx)}")
        print(f"[DEBUG] TradeContext 所有属性和方法:")
        try:
            all_attrs = dir(ctx)
            # 过滤出公共方法（不以_开头的可调用对象）
            methods = [attr for attr in all_attrs if not attr.startswith("_") and callable(getattr(ctx, attr, None))]
            print(f"[DEBUG] 可用方法: {methods[:20]}")  # 只显示前20个
        except Exception as e:
            print(f"[DEBUG] 无法列出方法: {e}")
        
        # 直接使用 account_balance() 方法（已验证存在）
        # account_balance() 接受可选的 currency 参数，返回 List[AccountBalance]
        try:
            if currency:
                resp = ctx.account_balance(currency=currency)  # type: ignore[attr-defined]
            else:
                resp = ctx.account_balance()  # type: ignore[attr-defined]
            print(f"[DEBUG] 使用 account_balance() 方法获取资产信息成功, currency={currency}")
            print(f"[DEBUG] account_balance() 返回类型: {type(resp)}")
            
            # account_balance() 返回 List[AccountBalance]
            if isinstance(resp, list):
                print(f"[DEBUG] account_balance() 返回列表，长度: {len(resp)}")
                if resp:
                    resp = resp[0]  # 使用第一个账户
                else:
                    resp = None
            else:
                resp = None
        except RuntimeError as e:
            # 凭证相关的错误
            error_msg = str(e)
            if "Missing LongPort credentials" in error_msg or "credentials" in error_msg.lower():
                raise RuntimeError(f"{mode}账户凭证未正确配置，请检查环境变量：LONGPORT_{mode.upper()}_APP_KEY, LONGPORT_{mode.upper()}_APP_SECRET, LONGPORT_{mode.upper()}_ACCESS_TOKEN")
            else:
                raise RuntimeError(f"{mode}账户配置错误: {error_msg}")
        except Exception as e:
            error_msg = str(e).lower()
            # 检查是否是认证相关的错误
            if "auth" in error_msg or "unauthorized" in error_msg or "credential" in error_msg or "token" in error_msg:
                raise RuntimeError(f"{mode}账户凭证验证失败，请检查账户凭证是否正确")
            elif "network" in error_msg or "connection" in error_msg or "timeout" in error_msg:
                raise RuntimeError(f"网络连接失败，请检查网络连接")
            else:
                print(f"[DEBUG] account_balance() 调用失败: {e}")
                import traceback
                print(f"[DEBUG] 错误详情: {traceback.format_exc()}")
                raise RuntimeError(f"获取{mode}账户资产信息失败: {str(e)}")
        
        if resp is None:
            print("[DEBUG] account_balance() 返回 None")
            # 如果返回None，可能是账户不存在或没有数据
            return {}
        
        # AccountBalance 对象的结构：
        # - total_cash: Decimal - 总现金
        # - currency: str - 货币
        # - cash_infos: List[CashInfo] - 现金详情列表
        #   - CashInfo: available_cash, frozen_cash, currency
        # - net_assets: Decimal - 净资产
        # - buy_power: Decimal - 购买力
        
        result: Dict[str, Any] = {}
        
        # 提取基本字段
        if hasattr(resp, "total_cash"):
            result["total_cash"] = self._convert_value(getattr(resp, "total_cash"))
        if hasattr(resp, "currency"):
            result["currency"] = self._convert_value(getattr(resp, "currency"))
        if hasattr(resp, "net_assets"):
            result["net_assets"] = self._convert_value(getattr(resp, "net_assets"))
        if hasattr(resp, "buy_power"):
            result["buy_power"] = self._convert_value(getattr(resp, "buy_power"))
        
        # 从 cash_infos 中提取可用现金和冻结现金
        available_cash = 0.0
        frozen_cash = 0.0
        
        if hasattr(resp, "cash_infos"):
            cash_infos = getattr(resp, "cash_infos")
            if cash_infos:
                print(f"[DEBUG] cash_infos 类型: {type(cash_infos)}, 长度: {len(cash_infos) if isinstance(cash_infos, list) else 'N/A'}")
                # 遍历所有 CashInfo，累加可用现金和冻结现金
                for cash_info in cash_infos:
                    if hasattr(cash_info, "available_cash"):
                        available_cash += self._safe_float(getattr(cash_info, "available_cash"))
                    if hasattr(cash_info, "frozen_cash"):
                        frozen_cash += self._safe_float(getattr(cash_info, "frozen_cash"))
        
        result["available_cash"] = available_cash
        result["frozen_cash"] = frozen_cash
        
        # 如果没有 total_cash，使用 available_cash + frozen_cash 作为总现金
        if "total_cash" not in result or result["total_cash"] == 0:
            result["total_cash"] = available_cash + frozen_cash
        
        print(f"[DEBUG] 提取的资产信息: {result}")
        return result

    def get_positions(self, mode: str = "paper") -> List[Dict[str, Any]]:
        try:
            ctx = self._get_trade_context(mode)
            # 使用 stock_positions() 方法（已验证存在）
            resp = ctx.stock_positions()  # type: ignore[attr-defined]
            if not resp:
                return []
            
            # StockPositionsResponse 对象的结构：
            # - channels: List[StockPositionChannel]
            #   - StockPositionChannel: account_channel, positions: List[StockPosition]
            
            positions: List[Dict[str, Any]] = []
            
            # 从 channels 中提取所有持仓
            if hasattr(resp, "channels"):
                channels = getattr(resp, "channels")
                print(f"[DEBUG] stock_positions channels 数量: {len(channels) if isinstance(channels, list) else 'N/A'}")
                
                if isinstance(channels, list):
                    for channel in channels:
                        if hasattr(channel, "positions"):
                            channel_positions = getattr(channel, "positions")
                            if isinstance(channel_positions, list):
                                for item in channel_positions:
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
            
            print(f"[DEBUG] 提取的持仓数量: {len(positions)}")
            return positions
        except RuntimeError:
            # 重新抛出RuntimeError（凭证相关错误）
            raise
        except Exception as e:
            error_msg = str(e).lower()
            if "credential" in error_msg or "auth" in error_msg or "unauthorized" in error_msg:
                raise RuntimeError(f"{mode}账户凭证验证失败，请检查账户凭证是否正确")
            elif "network" in error_msg or "connection" in error_msg or "timeout" in error_msg:
                raise RuntimeError(f"网络连接失败，请检查网络连接")
            else:
                raise RuntimeError(f"获取持仓信息失败: {str(e)}")

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
        try:
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
        except RuntimeError:
            # 重新抛出RuntimeError（凭证相关错误）
            raise
        except Exception as e:
            error_msg = str(e).lower()
            if "credential" in error_msg or "auth" in error_msg or "unauthorized" in error_msg:
                raise RuntimeError(f"{mode}账户凭证验证失败，请检查账户凭证是否正确")
            elif "network" in error_msg or "connection" in error_msg or "timeout" in error_msg:
                raise RuntimeError(f"网络连接失败，请检查网络连接")
            else:
                raise RuntimeError(f"获取当日订单失败: {str(e)}")

    # ============ Market-specific APIs ============
    @staticmethod
    def _get_market_from_symbol(symbol: str) -> Optional[str]:
        """从symbol中提取市场类型：US或HK"""
        if not symbol:
            return None
        if symbol.endswith(".US"):
            return "US"
        elif symbol.endswith(".HK"):
            return "HK"
        return None

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        """安全地将值转换为float"""
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def get_account_list(self, mode: str = "paper") -> List[Dict[str, Any]]:
        """
        获取账户列表，返回USD和HKD货币的账户信息
        通过获取不同货币的资产信息来区分
        """
        try:
            accounts = []
            
            # 获取所有持仓
            positions = self.get_positions(mode=mode)
            
            # 分别获取USD和HKD货币的资产信息
            usd_assets = self.get_assets(mode=mode, currency="USD")
            hkd_assets = self.get_assets(mode=mode, currency="HKD")
            
            # 统计各市场的持仓（用于计算持仓市值）
            us_positions = [p for p in positions if self._get_market_from_symbol(p.get("symbol", "")) == "US"]
            hk_positions = [p for p in positions if self._get_market_from_symbol(p.get("symbol", "")) == "HK"]
            
            # 计算各市场的持仓市值
            us_market_value = sum(self._safe_float(p.get("market_value", 0)) for p in us_positions)
            hk_market_value = sum(self._safe_float(p.get("market_value", 0)) for p in hk_positions)
            
            # 构建USD账户（如果有USD资产或持仓）
            if usd_assets or us_positions:
                usd_total_cash = self._safe_float(usd_assets.get("total_cash", 0))
                usd_available_cash = self._safe_float(usd_assets.get("available_cash", 0))
                
                accounts.append({
                    "market": "US",  # 保持兼容性，实际表示USD货币
                    "currency": "USD",
                    "total_cash": usd_total_cash,
                    "available_cash": usd_available_cash,
                    "market_value": us_market_value,
                    "total_asset": usd_total_cash + us_market_value,
                    "position_count": len(us_positions)
                })
            
            # 构建HKD账户（如果有HKD资产或持仓）
            if hkd_assets or hk_positions:
                hkd_total_cash = self._safe_float(hkd_assets.get("total_cash", 0))
                hkd_available_cash = self._safe_float(hkd_assets.get("available_cash", 0))
                
                accounts.append({
                    "market": "HK",  # 保持兼容性，实际表示HKD货币
                    "currency": "HKD",
                    "total_cash": hkd_total_cash,
                    "available_cash": hkd_available_cash,
                    "market_value": hk_market_value,
                    "total_asset": hkd_total_cash + hk_market_value,
                    "position_count": len(hk_positions)
                })
            
            # 如果都没有，至少返回一个默认USD账户
            if not accounts:
                accounts.append({
                    "market": "US",
                    "currency": "USD",
                    "total_cash": 0.0,
                    "available_cash": 0.0,
                    "market_value": 0.0,
                    "total_asset": 0.0,
                    "position_count": 0
                })
            
            return accounts
        except Exception as e:
            # 如果出错，至少返回一个默认账户
            return [{
                "market": "US",
                "currency": "USD",
                "total_cash": 0.0,
                "available_cash": 0.0,
                "market_value": 0.0,
                "total_asset": 0.0,
                "position_count": 0
            }]

    def get_assets_by_market(self, market: str, mode: str = "paper") -> Dict[str, Any]:
        """
        获取特定货币的资产信息
        market: "US" -> USD, "HK" -> HKD
        """
        try:
            # 根据 market 确定 currency
            currency = "USD" if market == "US" else "HKD"
            print(f"[DEBUG] 获取 {market} 市场资产，对应货币: {currency}")
            
            # 传入 currency 参数获取对应货币的资产
            all_assets = self.get_assets(mode=mode, currency=currency)
            positions = self.get_positions(mode=mode)
            
            print(f"[DEBUG] LongPort get_assets返回: {all_assets}")
            print(f"[DEBUG] LongPort get_positions返回: {positions}")
            print(f"[DEBUG] 持仓数量: {len(positions)}")
            
            # 过滤出指定市场的持仓
            market_positions = [
                p for p in positions 
                if self._get_market_from_symbol(p.get("symbol", "")) == market
            ]
            
            print(f"[DEBUG] {market}市场持仓数量: {len(market_positions)}")
            
            # 计算市场持仓价值
            market_value = sum(self._safe_float(p.get("market_value", 0)) for p in market_positions)
            
            # 获取所有市场的持仓价值，用于现金分配
            all_positions = positions
            total_market_value = sum(self._safe_float(p.get("market_value", 0)) for p in all_positions)
            
            # 获取现金信息，使用安全的类型转换
            currency = "USD" if market == "US" else "HKD"
            total_cash = self._safe_float(all_assets.get("total_cash"))
            available_cash = self._safe_float(all_assets.get("available_cash"))
            frozen_cash = self._safe_float(all_assets.get("frozen_cash"))
            
            print(f"[DEBUG] 现金信息 - total_cash: {total_cash}, available_cash: {available_cash}, frozen_cash: {frozen_cash}")
            print(f"[DEBUG] 持仓价值 - market_value: {market_value}, total_market_value: {total_market_value}")
            
            # 如果有多个市场的持仓，按持仓比例分配现金
            # 如果只有当前市场的持仓或没有持仓，显示全部现金
            if total_market_value > 0 and market_value < total_market_value:
                # 有多个市场，按比例分配
                cash_ratio = market_value / total_market_value if total_market_value > 0 else 0
                market_total_cash = total_cash * cash_ratio
                market_available_cash = available_cash * cash_ratio
                market_frozen_cash = frozen_cash * cash_ratio
            else:
                # 只有当前市场或没有持仓，显示全部现金
                market_total_cash = total_cash
                market_available_cash = available_cash
                market_frozen_cash = frozen_cash
            
            result = {
                "market": market,
                "currency": currency,
                "total_cash": market_total_cash,
                "available_cash": market_available_cash,
                "frozen_cash": market_frozen_cash,
                "market_value": market_value,
                "total_asset": market_total_cash + market_value,
                "position_count": len(market_positions)
            }
            
            print(f"[DEBUG] 最终返回的资产信息: {result}")
            return result
        except Exception as e:
            # 如果出错，返回默认值
            import traceback
            print(f"[ERROR] get_assets_by_market异常: {str(e)}")
            print(f"[ERROR] {traceback.format_exc()}")
            currency = "USD" if market == "US" else "HKD"
            return {
                "market": market,
                "currency": currency,
                "total_cash": 0.0,
                "available_cash": 0.0,
                "frozen_cash": 0.0,
                "market_value": 0.0,
                "total_asset": 0.0,
                "position_count": 0
            }

    def get_positions_by_market(self, market: str, mode: str = "paper") -> List[Dict[str, Any]]:
        """获取特定市场的持仓列表"""
        positions = self.get_positions(mode=mode)
        return [
            p for p in positions 
            if self._get_market_from_symbol(p.get("symbol", "")) == market
        ]

    def get_today_orders_by_market(self, market: str, mode: str = "paper") -> List[Dict[str, Any]]:
        """
        获取特定市场的当日订单
        会根据当地交易时间过滤（这里返回所有订单，由API层处理时间过滤）
        """
        orders = self.list_today_orders(mode=mode)
        return [
            o for o in orders 
            if self._get_market_from_symbol(o.get("symbol", "")) == market
        ]


