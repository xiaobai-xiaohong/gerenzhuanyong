"""
甲醇预测模型 v4 - 多品种联动+Transformer (修复版)
"""
import numpy as np
import pandas as pd
import akshare as ak
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
import warnings
warnings.filterwarnings('ignore')

import torch
import torch.nn as nn

def fetch_data():
    datasets = {}
    for name, sym in [('MA','MA0'),('EG','EG0'),('SC','SC0')]:
        try:
            df = ak.futures_main_sina(symbol=sym)
            df['date'] = pd.to_datetime(df['日期'])
            df = df.sort_values('date').reset_index(drop=True)
            datasets[name] = df
            print(f"  {name}: {len(df)}")
        except: pass
    return datasets

def create_features(datasets):
    ma = datasets['MA'].copy()
    
    # MA特征
    ma['MA_ret'] = ma['收盘价'].pct_change()
    ma['MA_vol5'] = ma['MA_ret'].rolling(5).std()
    ma['MA_vol20'] = ma['MA_ret'].rolling(20).std()
    ma['MA_ma5'] = ma['收盘价'].rolling(5).mean() / ma['收盘价']
    ma['MA_ma20'] = ma['收盘价'].rolling(20).mean() / ma['收盘价']
    ma['MA_ma60'] = ma['收盘价'].rolling(60).mean() / ma['收盘价']
    
    delta = ma['收盘价'].diff()
    gain = (delta.where(delta>0,0)).rolling(14).mean()
    loss = (-delta.where(delta<0,0)).rolling(14).mean()
    ma['MA_RSI'] = 100-(100/(1+gain/loss))
    
    e1 = ma['收盘价'].ewm(span=12,adjust=False).mean()
    e2 = ma['收盘价'].ewm(span=26,adjust=False).mean()
    ma['MA_MACD'] = (e1-e2) / ma['收盘价']
    
    # EG特征
    if 'EG' in datasets:
        eg = datasets['EG'][['date','收盘价']].copy()
        eg.columns = ['date','EG_close']
        ma = ma.merge(eg, on='date', how='left')
        ma['EG_ret'] = ma['EG_close'].pct_change()
        ma['EG_ma5'] = ma['EG_close'].rolling(5).mean() / ma['EG_close']
        ma['MA_EG_spread'] = (ma['收盘价'] - ma['EG_close']) / ma['EG_close']
    
    # SC(原油)特征
    if 'SC' in datasets:
        sc = datasets['SC'][['date','收盘价']].copy()
        sc.columns = ['date','SC_close']
        ma = ma.merge(sc, on='date', how='left')
        ma['SC_ret'] = ma['SC_close'].pct_change()
        ma['SC_ma5'] = ma['SC_close'].rolling(5).mean() / ma['SC_close']
        ma['MA_SC_ratio'] = ma['收盘价'] / ma['SC_close']
    
    ma['target'] = (ma['收盘价'].shift(-1) > ma['收盘价']).astype(int)
    return ma

class TransformerModel(nn.Module):
    def __init__(self, input_dim, d_model=64, nhead=4, num_layers=2, dropout=0.3):
        super().__init__()
        self.proj = nn.Linear(input_dim, d_model)
        self.pos = nn.Parameter(torch.randn(1,50,d_model)*0.1)
        layer = nn.TransformerEncoderLayer(d_model,nhead,128,dropout,batch_first=True)
        self.transformer = nn.TransformerEncoder(layer,num_layers)
        self.head = nn.Sequential(
            nn.Linear(d_model,32), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(32,1), nn.Sigmoid()
        )
    def forward(self,x):
        x = self.proj(x) + self.pos[:,:x.size(1),:]
        x = self.transformer(x)
        return self.head(x[:,-1,:])

def main():
    print("="*60)
    print("甲醇预测 v4 - 多品种+Transformer")
    print("="*60)
    
    datasets = fetch_data()
    data = create_features(datasets)
    
    feat_cols = [c for c in data.columns if c not in 
                 ['日期','开盘价','最高价','最低价','收盘价','成交量','持仓量','动态结算价','date','target',
                  'EG_close','SC_close']]
    
    data = data.dropna().reset_index(drop=True)
    print(f"\n数据: {len(data)}, 特征: {len(feat_cols)}")
    
    scaler = StandardScaler()
    X = scaler.fit_transform(data[feat_cols].values)
    y = data['target'].values
    
    lookback = 20
    Xs, ys = [], []
    for i in range(lookback, len(X)):
        Xs.append(X[i-lookback:i])
        ys.append(y[i])
    Xs, ys = np.array(Xs), np.array(ys)
    
    sp = int(len(Xs)*0.8)
    Xtr,Xte = Xs[:sp],Xs[sp:]
    ytr,yte = ys[:sp],ys[sp:]
    print(f"训练: {len(Xtr)}, 测试: {len(Xte)}")
    
    # Transformer
    print("\n训练Transformer...")
    model = TransformerModel(Xtr.shape[2])
    print(f"参数: {sum(p.numel() for p in model.parameters()):,}")
    
    crit = nn.BCELoss()
    opt = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=80)
    
    Xt = torch.FloatTensor(Xtr)
    yt = torch.FloatTensor(ytr).unsqueeze(1)
    
    model.train()
    for ep in range(80):
        opt.zero_grad()
        loss = crit(model(Xt), yt)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)
        opt.step()
        sched.step()
        if (ep+1)%20==0:
            print(f"  Epoch {ep+1}/80, Loss: {loss.item():.4f}")
    
    model.eval()
    with torch.no_grad():
        pred_t = model(torch.FloatTensor(Xte)).numpy().flatten()
    
    pc = (pred_t>0.5).astype(int)
    acc_t = (pc==yte).mean()
    tp_t=((pc==1)&(yte==1)).sum()
    tn_t=((pc==0)&(yte==0)).sum()
    fp_t=((pc==1)&(yte==0)).sum()
    fn_t=((pc==0)&(yte==1)).sum()
    
    # 随机森林
    print("\n训练随机森林...")
    Xtr_f = Xtr.reshape(len(Xtr),-1)
    Xte_f = Xte.reshape(len(Xte),-1)
    rf = RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42)
    rf.fit(Xtr_f, ytr)
    rf_pred = rf.predict(Xte_f)
    acc_rf = (rf_pred==yte).mean()
    tp_rf=((rf_pred==1)&(yte==1)).sum()
    tn_rf=((rf_pred==0)&(yte==0)).sum()
    fp_rf=((rf_pred==1)&(yte==0)).sum()
    fn_rf=((rf_pred==0)&(yte==1)).sum()
    
    # 结果
    print("\n" + "="*60)
    print("最终结果")
    print("="*60)
    print(f"\nTransformer:")
    print(f"  准确率: {acc_t:.2%}")
    print(f"  TP={tp_t} FP={fp_t} TN={tn_t} FN={fn_t}")
    prec=tp_t/(tp_t+fp_t) if(tp_t+fp_t)>0 else 0
    rec=tp_t/(tp_t+fn_t) if(tp_t+fn_t)>0 else 0
    f1=2*prec*rec/(prec+rec) if(prec+rec)>0 else 0
    print(f"  精确率: {prec:.2%}, 召回率: {rec:.2%}, F1: {f1:.2%}")
    
    print(f"\n随机森林:")
    print(f"  准确率: {acc_rf:.2%}")
    print(f"  TP={tp_rf} FP={fp_rf} TN={tn_rf} FN={fn_rf}")
    prec_rf=tp_rf/(tp_rf+fp_rf) if(tp_rf+fp_rf)>0 else 0
    rec_rf=tp_rf/(tp_rf+fn_rf) if(tp_rf+fn_rf)>0 else 0
    f1_rf=2*prec_rf*rec_rf/(prec_rf+rec_rf) if(prec_rf+rec_rf)>0 else 0
    print(f"  精确率: {prec_rf:.2%}, 召回率: {rec_rf:.2%}, F1: {f1_rf:.2%}")
    
    # 预测
    with torch.no_grad():
        latest = model(torch.FloatTensor(X[-lookback:]).unsqueeze(0)).item()
    rf_prob = rf.predict_proba(X[-1:].reshape(1,-1))[0][1]
    
    print(f"\n下一交易日预测:")
    print(f"  Transformer: {'看涨' if latest>0.5 else '看跌'} ({latest:.2%})")
    print(f"  随机森林: {'看涨' if rf_prob>0.5 else '看跌'} ({rf_prob:.2%})")
    
    torch.save({'model':model.state_dict(),'scaler':scaler,'cols':feat_cols,'acc':acc_t},
               'C:/Users/Administrator/gerenzhuanyong/ma_v4.pth')
    print(f"\n保存: ma_v4.pth")

if __name__=="__main__":
    main()
