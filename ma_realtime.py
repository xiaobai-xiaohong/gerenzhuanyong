"""甲醇实时行情工具 - akshare + 天勤"""
import json
import akshare as ak
import pandas as pd
from datetime import datetime

def get_ma_realtime():
    """获取甲醇实时行情"""
    print("=" * 55)
    print(f"甲醇 MA 实时行情  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 55)
    
    # 主力连续合约
    df = ak.futures_main_sina(symbol='MA0')
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    price = latest['收盘价']
    pre_close = prev['收盘价']
    change = price - pre_close
    change_pct = change / pre_close * 100
    
    print(f"主力连续:  收盘 {price:.0f}  涨跌 {change:+.0f}  涨幅 {change_pct:+.2f}%")
    print(f"今日区间:  {latest['最低价']:.0f} - {latest['最高价']:.0f}")
    print(f"成交量:    {latest['成交量']:,.0f}手")
    print(f"持仓量:    {latest['持仓量']:,.0f}手")
    
    # 各月份合约
    print("\n各月份合约:")
    try:
        contracts = ['MA2509', 'MA2510', 'MA2601', 'MA2605']
        for c in contracts:
            try:
                df_c = ak.futures_zh_daily_sina(symbol=c)
                if len(df_c) > 0:
                    row = df_c.iloc[-1]
                    print(f"  {c}: {row['close']:.0f}")
            except:
                pass
    except:
        pass
    
    # 近5日K线
    print("\n近5日K线:")
    for _, row in df.tail(5).iterrows():
        print(f"  {row['日期']}: O={row['开盘价']:.0f} H={row['最高价']:.0f} L={row['最低价']:.0f} C={row['收盘价']:.0f} V={row['成交量']:,.0f}")
    
    print("=" * 55)
    return price

def get_ma_analysis():
    """甲醇技术分析"""
    df = ak.futures_main_sina(symbol='MA0')
    
    # 计算均线
    df['MA5'] = df['收盘价'].rolling(5).mean()
    df['MA10'] = df['收盘价'].rolling(10).mean()
    df['MA20'] = df['收盘价'].rolling(20).mean()
    
    latest = df.iloc[-1]
    
    print("\n技术指标:")
    print(f"  MA5:  {latest['MA5']:.1f}")
    print(f"  MA10: {latest['MA10']:.1f}")
    print(f"  MA20: {latest['MA20']:.1f}")
    
    price = latest['收盘价']
    if price > latest['MA5'] > latest['MA10']:
        print("  趋势: 短期多头排列")
    elif price < latest['MA5'] < latest['MA10']:
        print("  趋势: 短期空头排列")
    else:
        print("  趋势: 震荡")

if __name__ == "__main__":
    get_ma_realtime()
    get_ma_analysis()
