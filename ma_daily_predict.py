"""
甲醇每日预测工具
用法: python ma_daily_predict.py
"""
import numpy as np
import pandas as pd
import akshare as ak
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
import warnings
warnings.filterwarnings('ignore')

def get_data():
    df = ak.futures_main_sina(symbol='MA0')
    df = df.tail(500).reset_index(drop=True)
    return df

def create_features(df):
    d = df.copy()
    d['returns'] = d['收盘价'].pct_change()
    d['log_returns'] = np.log(d['收盘价']/d['收盘价'].shift(1))
    
    for w in [5,10,20,60]:
        d[f'MA{w}'] = d['收盘价'].rolling(w).mean()
        d[f'MA{w}_ratio'] = d['收盘价']/d[f'MA{w}']
    
    for w in [5,10,20]:
        d[f'volatility_{w}'] = d['returns'].rolling(w).std()
    
    for p in [6,12,24]:
        delta = d['收盘价'].diff()
        gain = (delta.where(delta>0,0)).rolling(p).mean()
        loss = (-delta.where(delta<0,0)).rolling(p).mean()
        d[f'RSI_{p}'] = 100-(100/(1+gain/loss))
    
    e1 = d['收盘价'].ewm(span=12,adjust=False).mean()
    e2 = d['收盘价'].ewm(span=26,adjust=False).mean()
    d['MACD'] = e1-e2
    d['MACD_signal'] = d['MACD'].ewm(span=9,adjust=False).mean()
    d['MACD_hist'] = d['MACD']-d['MACD_signal']
    
    d['BB_mid'] = d['收盘价'].rolling(20).mean()
    d['BB_std'] = d['收盘价'].rolling(20).std()
    d['BB_width'] = (d['BB_mid']+2*d['BB_std']-(d['BB_mid']-2*d['BB_std']))/d['BB_mid']
    d['BB_position'] = (d['收盘价']-(d['BB_mid']-2*d['BB_std']))/(4*d['BB_std'])
    
    d['volume_ma5'] = d['成交量'].rolling(5).mean()
    d['volume_ratio'] = d['成交量']/d['volume_ma5']
    d['hold_ma5'] = d['持仓量'].rolling(5).mean()
    d['hold_ratio'] = d['持仓量']/d['hold_ma5']
    d['high_low_ratio'] = (d['收盘价']-d['最低价'])/(d['最高价']-d['最低价'])
    
    d['target'] = (d['收盘价'].shift(-1)>d['收盘价']).astype(int)
    return d

def main():
    print("="*50)
    print("甲醇每日预测")
    print("="*50)
    
    df = get_data()
    data = create_features(df)
    
    feature_cols = [c for c in data.columns if c not in 
                    ['日期','开盘价','最高价','最低价','收盘价','成交量','持仓量','动态结算价','target']]
    data = data.dropna().reset_index(drop=True)
    
    scaler = StandardScaler()
    X = scaler.fit_transform(data[feature_cols].values)
    y = data['target'].values
    
    split = int(len(X)*0.8)
    Xtr,Xte = X[:split],X[split:]
    ytr,yte = y[:split],y[split:]
    
    # 随机森林
    rf = RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42)
    rf.fit(Xtr, ytr)
    rf_pred = rf.predict(Xte)
    rf_acc = (rf_pred==yte).mean()
    
    # 梯度提升
    gb = GradientBoostingClassifier(n_estimators=150, max_depth=5, random_state=42)
    gb.fit(Xtr, ytr)
    gb_pred = gb.predict(Xte)
    gb_acc = (gb_pred==yte).mean()
    
    # 预测
    rf_prob = rf.predict_proba(X[-1:])[0][1]
    gb_prob = gb.predict_proba(X[-1:])[0][1]
    
    # 结果
    print(f"\n模型准确率:")
    print(f"  随机森林: {rf_acc:.2%}")
    print(f"  梯度提升: {gb_acc:.2%}")
    
    print(f"\n最新收盘价: {data['收盘价'].iloc[-1]}")
    
    print(f"\n下一交易日预测:")
    print(f"  随机森林: {'看涨' if rf_prob>0.5 else '看跌'} ({rf_prob:.2%})")
    print(f"  梯度提升: {'看涨' if gb_prob>0.5 else '看跌'} ({gb_prob:.2%})")
    
    # 综合判断
    avg_prob = (rf_prob + gb_prob) / 2
    if avg_prob > 0.55:
        signal = "看涨"
    elif avg_prob < 0.45:
        signal = "看跌"
    else:
        signal = "观望"
    
    print(f"\n综合信号: {signal} (概率: {avg_prob:.2%})")
    print("="*50)

if __name__=="__main__":
    main()
