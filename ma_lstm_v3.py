"""
甲醇LSTM v3 - 5分钟线，9合约合并，9207条数据
"""
import numpy as np
import pandas as pd
import akshare as ak
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score
import warnings
warnings.filterwarnings('ignore')

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

# 数据获取
def fetch_data():
    contracts = ['MA2507','MA2508','MA2509','MA2510','MA2511','MA2512','MA2601','MA2603','MA2605']
    all_data = []
    for c in contracts:
        try:
            df = ak.futures_zh_minute_sina(symbol=c, period='5')
            df['contract'] = c
            all_data.append(df)
            print(f"  {c}: {len(df)}")
        except:
            pass
    data = pd.concat(all_data, ignore_index=True)
    data['datetime'] = pd.to_datetime(data['datetime'])
    data = data.sort_values('datetime').reset_index(drop=True)
    return data

# 特征工程
def create_features(df):
    d = df.copy()
    d['returns'] = d['close'].pct_change()
    d['log_returns'] = np.log(d['close']/d['close'].shift(1))
    
    for w in [4,8,16,32,64,128]:
        d[f'MA{w}'] = d['close'].rolling(w).mean()
        d[f'MA{w}_r'] = d['close']/d[f'MA{w}']
    
    for w in [4,8,16,32]:
        d[f'vol_{w}'] = d['returns'].rolling(w).std()
    
    for p in [6,12,24]:
        delta = d['close'].diff()
        gain = (delta.where(delta>0,0)).rolling(p).mean()
        loss = (-delta.where(delta<0,0)).rolling(p).mean()
        d[f'RSI_{p}'] = 100-(100/(1+gain/loss))
    
    e1 = d['close'].ewm(span=12,adjust=False).mean()
    e2 = d['close'].ewm(span=26,adjust=False).mean()
    d['MACD'] = e1-e2
    d['MACD_s'] = d['MACD'].ewm(span=9,adjust=False).mean()
    d['MACD_h'] = d['MACD']-d['MACD_s']
    
    d['BB_m'] = d['close'].rolling(20).mean()
    d['BB_s'] = d['close'].rolling(20).std()
    d['BB_w'] = (4*d['BB_s'])/d['BB_m']
    d['BB_p'] = (d['close']-(d['BB_m']-2*d['BB_s']))/(4*d['BB_s'])
    
    d['vol_r'] = d['volume']/d['volume'].rolling(4).mean()
    d['hold_r'] = d['hold']/d['hold'].rolling(4).mean()
    d['hl_r'] = (d['close']-d['low'])/(d['high']-d['low'])
    
    d['contract_id'] = d['contract'].factorize()[0]
    d['target'] = (d['close'].shift(-1)>d['close']).astype(int)
    return d

# LSTM + Attention
class Model(nn.Module):
    def __init__(self, input_dim, hidden=128, layers=2, drop=0.3):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden, layers, batch_first=True, dropout=drop)
        self.attn = nn.MultiheadAttention(hidden, 4, dropout=drop, batch_first=True)
        self.norm = nn.LayerNorm(hidden)
        self.head = nn.Sequential(
            nn.Linear(hidden,64), nn.ReLU(), nn.Dropout(drop),
            nn.Linear(64,32), nn.ReLU(), nn.Dropout(drop),
            nn.Linear(32,1), nn.Sigmoid()
        )
    def forward(self,x):
        o,_ = self.lstm(x)
        a,_ = self.attn(o,o,o)
        o = self.norm(a+o)
        return self.head(o[:,-1,:])

def main():
    print("="*60)
    print("甲醇LSTM v3 - 5分钟9合约")
    print("="*60)
    
    data = fetch_data()
    data = create_features(data)
    
    feat_cols = [c for c in data.columns if c not in 
                 ['datetime','open','high','low','close','volume','hold','contract','target']]
    data = data.dropna().reset_index(drop=True)
    print(f"有效数据: {len(data)}")
    
    scaler = StandardScaler()
    X_all = scaler.fit_transform(data[feat_cols])
    y_all = data['target'].values
    
    lookback = 64
    X, y = [], []
    for i in range(lookback, len(X_all)):
        X.append(X_all[i-lookback:i])
        y.append(y_all[i])
    X, y = np.array(X), np.array(y)
    
    split = int(len(X)*0.8)
    Xtr, Xte = X[:split], X[split:]
    ytr, yte = y[:split], y[split:]
    print(f"训练: {len(Xtr)}, 测试: {len(Xte)}")
    print(f"特征: {X.shape[2]}, 序列: {lookback}")
    
    model = Model(Xtr.shape[2], hidden=128, layers=2, drop=0.3)
    print(f"参数: {sum(p.numel() for p in model.parameters()):,}")
    
    # 训练
    Xt = torch.FloatTensor(Xtr)
    yt = torch.FloatTensor(ytr).unsqueeze(1)
    ds = TensorDataset(Xt, yt)
    dl = DataLoader(ds, batch_size=128, shuffle=True)
    
    criterion = nn.BCELoss()
    opt = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=100)
    
    print("\n训练...")
    model.train()
    for ep in range(100):
        total = 0
        for bx, by in dl:
            opt.zero_grad()
            loss = criterion(model(bx), by)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            total += loss.item()
        sched.step()
        if (ep+1)%20==0:
            print(f"  Epoch {ep+1}/100, Loss: {total/len(dl):.4f}")
    
    # 评估
    model.eval()
    with torch.no_grad():
        pred = model(torch.FloatTensor(Xte)).numpy().flatten()
    
    pc = (pred>0.5).astype(int)
    acc = (pc==yte).mean()
    
    tp=((pc==1)&(yte==1)).sum()
    tn=((pc==0)&(yte==0)).sum()
    fp=((pc==1)&(yte==0)).sum()
    fn=((pc==0)&(yte==1)).sum()
    prec=tp/(tp+fp) if(tp+fp)>0 else 0
    rec=tp/(tp+fn) if(tp+fn)>0 else 0
    f1=2*prec*rec/(prec+rec) if(prec+rec)>0 else 0
    
    print(f"\n评估:")
    print(f"准确率: {acc:.2%}")
    print(f"精确率: {prec:.2%}")
    print(f"召回率: {rec:.2%}")
    print(f"F1: {f1:.2%}")
    print(f"TP={tp} FP={fp} TN={tn} FN={fn}")
    
    # 预测
    with torch.no_grad():
        latest = model(torch.FloatTensor(X_all[-lookback:]).unsqueeze(0)).item()
    
    d = "看涨" if latest>0.5 else "看跌"
    c = latest if latest>0.5 else 1-latest
    print(f"\n预测: {d} ({c:.2%}) 概率={latest:.2%}")
    
    torch.save({'model':model.state_dict(),'scaler':scaler,'cols':feat_cols,'acc':acc,'lb':lookback},
               'C:/Users/Administrator/gerenzhuanyong/ma_lstm_v3.pth')
    print(f"保存: ma_lstm_v3.pth")
    
    return acc, latest

if __name__=="__main__":
    main()
