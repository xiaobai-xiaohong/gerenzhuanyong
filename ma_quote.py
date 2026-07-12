"""天勤甲醇实时行情工具"""
import json
import sys
from tqsdk import TqApi, TqAuth

def load_config():
    with open("C:/Users/Administrator/gerenzhuanyong/config_tqsdk.json") as f:
        return json.load(f)

def get_ma_quote():
    """获取甲醇主力合约实时行情"""
    cfg = load_config()
    api = TqApi(auth=TqAuth(cfg["tqsdk"]["user"], cfg["tqsdk"]["password"]))
    
    try:
        # 订阅甲醇主力合约（郑商所）
        quote = api.get_quote("CZCE.MA2509")  # MA2509主力
        klines = api.get_kline_serial("CZCE.MA2509", 86400, 5)  # 日K，最近5根
        
        print("=" * 50)
        print("甲醇 MA2509 实时行情")
        print("=" * 50)
        print(f"最新价:   {quote.last_price}")
        print(f"开盘价:   {quote.open}")
        print(f"最高价:   {quote.highest}")
        print(f"最低价:   {quote.lowest}")
        print(f"昨收价:   {quote.pre_close}")
        print(f"涨跌:     {quote.last_price - quote.pre_close:.1f}")
        print(f"涨跌幅:   {(quote.last_price - quote.pre_close) / quote.pre_close * 100:.2f}%")
        print(f"成交量:   {quote.volume}")
        print(f"持仓量:   {quote.open_interest}")
        print(f"涨停价:   {quote.limit_up}")
        print(f"跌停价:   {quote.limit_down}")
        print("=" * 50)
        
        # 近5日K线
        print("\n近5日K线:")
        for i in range(len(klines)):
            bar = klines.iloc[i]
            print(f"  {bar['datetime']}: O={bar['open']:.0f} H={bar['high']:.0f} L={bar['low']:.0f} C={bar['close']:.0f} V={bar['volume']:.0f}")
        
        return quote.last_price
    finally:
        api.close()

if __name__ == "__main__":
    get_ma_quote()
