"""
优化的TDX客户端，支持连接池
"""
from contextlib import contextmanager
from queue import Queue, Empty
from threading import Lock
from typing import Any, Dict, Generator, List, Optional
import logging

import pandas as pd
from pytdx.hq import TdxHq_API

from config import get_tdx_config, get_logger
from app.client.schemas import ColumnHandler, DataframeConfig
from app.core.singleton import Singleton
from app.utils.date import SIMPLE_FORMAT, date_parse, get_now, now_format
from app.utils.pandas_utils import scale_currency, scale_to_ten_thousands
from app.utils.stock import is_convertible_bond

logger = get_logger(__name__)


def _tdx_price_handler(row, column):
    stock_code = row["code"]
    if is_convertible_bond(stock_code):
        return scale_currency(row, column, 100)
    return row[column]


def _tdx_calc_pct_chg(row, column):
    pre_close = row["pre_close"]
    if pre_close == 0:
        return 0
    return round(((row["price"] - row["pre_close"]) / row["pre_close"]) * 100, 2)


class TdxClient(Singleton):
    """优化版TDX客户端，支持连接池"""

    def __init__(self):
        config = get_tdx_config()
        self.pool_size = config.pool_size
        self.timeout = config.timeout

        self.config = {
            "daily": DataframeConfig(
                rename_columns={},
                column_handlers=[
                    ColumnHandler(columns=["amount"], handler=scale_to_ten_thousands)
                ]
            ),
            "realtime": DataframeConfig(
                rename_columns={"last_close": "pre_close"},
                column_handlers=[
                    ColumnHandler(columns=["amount"], handler=scale_to_ten_thousands),
                    ColumnHandler(
                        columns=["price", "pre_close", "open", "high", "low"],
                        handler=_tdx_price_handler
                    ),
                    ColumnHandler(
                        columns=["change"],
                        handler=lambda row, column: round(row["price"] - row["pre_close"], 2)
                    ),
                    ColumnHandler(
                        columns=["pct_chg"],
                        handler=lambda row, column: _tdx_calc_pct_chg(row, column)
                    ),
                    ColumnHandler(
                        columns=["ts_code"],
                        handler=lambda row, column: row["code"] + (
                            ".SZ" if row["market"] == 0 else ".SH"
                        )
                    ),
                ],
            ),
        }

        # 连接池
        self._connection_pool: Queue = Queue(maxsize=self.pool_size)
        self._pool_lock = Lock()
        self._server_list = config.servers

        # 初始化连接池
        self._initialize_pool()

    def _initialize_pool(self):
        """初始化连接池，预创建连接"""
        logger.info(f"初始化TDX连接池，大小: {self.pool_size}")

        for i in range(self.pool_size):
            conn_info = self._create_connection()
            if conn_info:
                self._connection_pool.put(conn_info)
                logger.debug(f"连接池已初始化连接 {i+1}/{self.pool_size}")

        # 如果连接池为空，至少创建一个备用连接
        if self._connection_pool.empty():
            logger.warning("连接池初始化失败，将使用即时连接模式")

    def _create_connection(self) -> Optional[Dict[str, Any]]:
        """创建新的TDX连接"""
        api = TdxHq_API()

        for server in self._server_list:
            try:
                result = api.connect(server["ip"], server["port"], timeout=self.timeout)
                if result:
                    logger.info(f"成功连接到 {server['ip']}:{server['port']}")
                    return {"api": api, "server": server}
            except Exception as e:
                logger.warning(f"连接到 {server['ip']}:{server['port']} 失败: {e}")

        return None

    @contextmanager
    def _get_connection(self) -> Generator[TdxHq_API, Any, None]:
        """
        从连接池获取连接的上下文管理器
        """
        conn_info = None

        try:
            # 尝试从连接池获取
            with self._pool_lock:
                if not self._connection_pool.empty():
                    conn_info = self._connection_pool.get_nowait()

            # 如果池中没有连接，创建新连接
            if conn_info is None:
                logger.debug("连接池为空，创建新连接")
                conn_info = self._create_connection()

            if conn_info is None:
                raise RuntimeError("无法连接通达信服务器")

            api = conn_info["api"]
            yield api

        except Exception as e:
            logger.error(f"获取TDX连接失败: {e}")
            # 发生错误时不归还连接到池中
            raise

        finally:
            # 归还连接到池中
            if conn_info is not None:
                with self._pool_lock:
                    if not self._connection_pool.full():
                        self._connection_pool.put(conn_info)
                    else:
                        # 池已满，关闭多余连接
                        try:
                            conn_info["api"].disconnect()
                        except:
                            pass

    def get_stock_daily_data(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        period: str = "D"
    ) -> pd.DataFrame:
        """获取股票日线数据"""
        try:
            market = self._get_market_code(stock_code)
            # 转换日期格式
            start_date = date_parse(start_date)
            end_date = date_parse(end_date)
            days_diff = (get_now() - start_date).days

            # 根据周期调整数据量
            if period == "D":
                count = min(days_diff, 800)  # 日线最多800条
            elif period == "W":
                count = min(int(days_diff / 7) + 3, 800)
            elif period == "M":
                count = min(int(days_diff / 30) + 2, 800)
            else:
                count = 800

            if count == 0:
                count = 1

            # 获取K线数据
            category_map = {"D": 9, "W": 5, "M": 6}
            category = category_map.get(period, 9)

            with self._get_connection() as api:
                data_list = api.get_security_bars(category, market, stock_code, 0, count)

            if not data_list:
                return pd.DataFrame()

            new_data_list = []
            for data in data_list:
                date = date_parse(data.get("datetime")[0:10])
                if start_date <= date <= end_date:
                    new_data_list.append(data)

            return self.config["daily"].apply(pd.DataFrame(new_data_list))

        except Exception as e:
            logger.error(f"获取股票数据失败: {e}")
            return pd.DataFrame()

    def get_stock_realtime_data(self, stock_code_list: List[str]) -> pd.DataFrame:
        """获取实时数据（批量）"""
        try:
            req = [(self._get_market_code(code), code) for code in stock_code_list]

            with self._get_connection() as api:
                data_list = api.get_security_quotes(req)

            if not data_list:
                return pd.DataFrame()

            df = pd.DataFrame(data_list)
            return self.config["realtime"].apply(df)

        except Exception as e:
            logger.error(f"获取实时数据失败: {stock_code_list}", exc_info=e)
            return pd.DataFrame()

    @classmethod
    def _get_market_code(cls, stock_code: str) -> int:
        """
        根据股票/可转债代码判断市场
        Args:
            stock_code: 股票代码
        Returns:
            int: 市场代码 (0=深圳, 1=上海)
        """
        # ------ 可转债（先判断 11 / 12 / 13）------
        if stock_code.startswith("11"):
            return 1  # 上海可转债
        if stock_code.startswith(("12", "13")):
            return 0  # 深圳可转债

        # ------ 股票 ------
        if stock_code.startswith(("000", "002", "003", "300")):
            return 0  # 深圳

        if stock_code.startswith(("600", "601", "603", "605", "688")):
            return 1  # 上海

        # 默认深圳
        return 0

    def get_stock_indicator(self, stock_code: str, period: int = 20) -> Dict[str, Any]:
        """计算技术指标"""
        try:
            end_date = now_format(SIMPLE_FORMAT)
            start_date = get_now().shift(days=-period * 2).format(SIMPLE_FORMAT)
            df = self.get_stock_daily_data(stock_code, start_date, end_date)

            if df.empty:
                return {}

            # 计算技术指标
            indicators = {
                "MA5": df["close"].rolling(5).mean().iloc[-1] if len(df) >= 5 else None,
                "MA10": df["close"].rolling(10).mean().iloc[-1] if len(df) >= 10 else None,
                "MA20": df["close"].rolling(20).mean().iloc[-1] if len(df) >= 20 else None,
            }

            # RSI
            if len(df) >= 14:
                delta = df["close"].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                indicators["RSI"] = (100 - (100 / (1 + rs))).iloc[-1]

            # MACD
            if len(df) >= 26:
                exp1 = df["close"].ewm(span=12).mean()
                exp2 = df["close"].ewm(span=26).mean()
                macd = exp1 - exp2
                signal = macd.ewm(span=9).mean()
                indicators["MACD"] = macd.iloc[-1]
                indicators["MACD_Signal"] = signal.iloc[-1]
                indicators["MACD_Histogram"] = (macd - signal).iloc[-1]

            # 布林带
            if len(df) >= 20:
                sma = df["close"].rolling(20).mean()
                std = df["close"].rolling(20).std()
                indicators["BB_Upper"] = (sma + 2 * std).iloc[-1]
                indicators["BB_Middle"] = sma.iloc[-1]
                indicators["BB_Lower"] = (sma - 2 * std).iloc[-1]

            return indicators

        except Exception as e:
            logger.error(f"获取技术指标失败: {e}")
            return {}

    def close_all_connections(self):
        """关闭所有连接"""
        logger.info("关闭TDX连接池所有连接")
        while not self._connection_pool.empty():
            try:
                conn_info = self._connection_pool.get_nowait()
                conn_info["api"].disconnect()
            except:
                pass
