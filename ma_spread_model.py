"""
甲醇价差预测模型 - 比方向预测更容易
预测：09-01价差 或 MA-EG价差
"""
import numpy as np
import pandas as pd
import akshare as ak
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import accuracy_score
import warnings
warnings.filterwarnings('ignore')

def fetch_spread_data():
    """获取价差数据"""
    print("获取价差数据...")
    
    # MA主力
    ma = ak.futures_main_sina(symbol='MA0')
    ma['date'] = pd.to_datetime(ma['日期'])
    ma = ma[['date','收盘价','成交量','持仓量']].rename(columns={'收盘价':'MA_close','成交量':'MA_vol','持仓量':'MA_hold'})
    
    # EG主力
    eg = ak.futures_main_sina(symbol='EG0')
    eg['date'] = pd.to_datetime(eg['日期'])
    eg = eg[['date','收盘价']].rename(columns={'收盘价':'EG_close'})
    
    # SC(原油)
    sc = ak.futures_main_sina(symbol='SC0')
    sc['date'] = pd.to_datetime(sc['日期'])
    sc = sc[['date','收盘价']].rename(columns={'收盘价':'SC_close'})
    
    # 合并
    data = ma.merge(eg, on='date', how='left').merge(sc, on='date', how='left')
    
    # 计算价差
    data['MA_EG_spread'] = data['MA_close'] - data['EG_close']
    data['MA_SC_ratio'] = data['MA_close'] / data['SC_close']
    
    # 价差变化（目标）
    data['spread_change'] = data['MA_EG_spread'].shift(-1) - data['MA_EG_spread']
    data['target'] = (data['spread_change'] > 0).astype(int)  # 1=价差扩大，0=价差收窄
    
    print(f"  数据: {len(data)}")
    return data

def create_features(data):
    """价差特征"""
    d = data.copy()
    
    # 价差自身特征
    d['spread_ma5'] = d['MA_EG_spread'].rolling(5).mean()
    d['spread_ma20'] = d['MA_EG_spread'].rolling(20).mean()
    d['spread_std5'] = d['MA_EG_spread'].rolling(5).std()
    d['spread_std20'] = d['MA_EG_spread'].rolling(20).std()
    d['spread_zscore'] = (d['MA_EG_spread'] - d['spread_ma20']) / d['spread_std20']
    
    # 价差动量
    d['spread_mom5'] = d['MA_EG_spread'].diff(5)
    d['spread_mom10'] = d['MA_EG_spread'].diff(10)
    d['spread_mom20'] = d['MA_EG_spread'].diff(20)
    
    # MA自身
    d['MA_ret'] = d['MA_close'].pct_change()
    d['MA_vol5'] = d['MA_ret'].rolling(5).std()
    d['MA_ma5'] = d['MA_close'].rolling(5).mean() / d['MA_close']
    d['MA_ma20'] = d['MA_close'].rolling(20).mean() / d['MA_close']
    
    # EG自身
    d['EG_ret'] = d['EG_close'].pct_change()
    d['EG_vol5'] = d['EG_ret'].rolling(5).std()
    
    # SC(原油)
    d['SC_ret'] = d['SC_close'].pct_change()
    d['SC_vol5'] = d['SC_ret'].rolling(5).std()
    
    # 相关性
    d['MA_EG_corr10'] = d['MA_ret'].rolling(10).corr(d['EG_ret'])
    d['MA_SC_corr10'] = d['MA_ret'].rolling(10).corr(d['SC_ret'])
    
    # 持仓量
    d['hold_ma5'] = d['MA_hold'].rolling(5).mean()
    d['hold_ratio'] = d['MA_hold'] / d['hold_ma5']
    
    return d

def main():
    print("="*60)
    print("甲醇价差预测模型")
    print("="*60)
    
    # 获取数据
    data = fetch_spread_data()
    data = create_features(data)
    
    # 选择特征
    exclude = ['date','MA_close','EG_close','SC_close','MA_vol','MA_hold','MA_EG_spread','MA_SC_ratio','spread_change','target']
    feat_cols = [c for c in data.columns if c not in exclude]
    
    data = data.dropna().reset_index(drop=True)
    print(f"有效数据: {len(data)}, 特征: {len(feat_cols)}")
    
    # 标准化
    scaler = StandardScaler()
    X = scaler.fit_transform(data[feat_cols].values)
    y = data['target'].values
    
    # 划分
    split = int(len(X)*0.8)
    Xtr, Xte = X[:split], X[split:]
    ytr, yte = y[:split], y[split:]
    print(f"训练: {len(Xtr)}, 测试: {len(Xte)}")
    print(f"目标分布: 价差扩大{y.sum()}次, 价差收窄{(1-y).sum()}次")
    
    # 随机森林
    print("\n训练随机森林...")
    rf = RandomForestClassifier(n_estimators=300, max_depth=12, random_state=42, class_weight='balanced')
    rf.fit(Xtr, ytr)
    rf_pred = rf.predict(Xte)
    rf_acc = (rf_pred==yte).mean()
    
    tp=((rf_pred==1)&(yte==1)).sum()
    tn=((rf_pred==0)&(yte==0)).sum()
    fp=((rf_pred==1)&(yte==0)).sum()
    fn=((rf_pred==0)&(yte==1)).sum()
    prec=tp/(tp+fp) if(tp+fp)>0 else 0
    rec=tp/(tp+fn) if(tp+fn)>0 else 0
    f1=2*prec*rec/(prec+rec) if(prec+rec)>0 else 0
    
    print(f"\n随机森林结果:")
    print(f"  准确率: {rf_acc:.2%}")
    print(f"  精确率: {prec:.2%}")
    print(f"  召回率: {rec:.2%}")
    print(f"  F1: {f1:.2%}")
    print(f"  TP={tp} FP={fp} TN={tn} FN={fn}")
    
    # 梯度提升
    print("\n训练梯度提升...")
    gb = GradientBoostingClassifier(n_estimators=200, max_depth=6, learning_rate=0.08, random_state=42)
    gb.fit(Xtr, ytr)
    gb_pred = gb.predict(Xte)
    gb_acc = (gb_pred==yte).mean()
    
    tp_g=((gb_pred==1)&(yte==1)).sum()
    tn_g=((gb_pred==0)&(yte==0)).sum()
    fp_g=((gb_pred==1)&(yte==0)).sum()
    fn_g=((gb_pred==0)&(yte==1)).sum()
    prec_g=tp_g/(tp_g+fp_g) if(tp_g+fp_g)>0 else 0
    rec_g=tp_g/(tp_g+fn_g) if(tp_g+fn_g)>0 else 0
    f1_g=2*prec_g*rec_g/(prec_g+rec_g) if(prec_g+rec_g)>0 else 0
    
    print(f"\n梯度提升结果:")
    print(f"  准确率: {gb_acc:.2%}")
    print(f"  精确率: {prec_g:.2%}")
    print(f"  召回率: {rec_g:.2%}")
    print(f"  F1: {f1_g:.2%}")
    print(f"  TP={tp_g} FP={fp_g} TN={tn_g} FN={fn_g}")
    
    # 集成
    ensemble_pred = ((rf_pred.astype(int) + gb_pred.astype(int)) >= 1).astype(int)
    ensemble_acc = (ensemble_pred==yte).mean()
    print(f"\n集成结果:")
    print(f"  准确率: {ensemble_acc:.2%}")
    
    # 预测
    rf_prob = rf.predict_proba(X[-1:])[0][1]
    gb_prob = gb.predict_proba(X[-1:])[0][1]
    ens_prob = (rf_prob + gb_prob) / 2
    
    print(f"\n下一交易日价差预测:")
    print(f"  随机森林: {'扩大' if rf_prob>0.5 else '收窄'} ({rf_prob:.2%})")
    print(f"  梯度提升: {'扩大' if gb_prob>0.5 else '收窄'} ({gb_prob:.2%})")
    print(f"  集成: {'扩大' if ens_prob>0.5 else '收窄'} ({ens_prob:.2%})")
    
    # 特征重要性
    print(f"\n特征重要性 TOP10:")
    imp = pd.Series(rf.feature_importances_, index=feat_cols)
    for f,i in imp.sort_values(ascending=False).head(10).items():
        print(f"  {f}: {i:.4f}")

if __name__=="__main__":
    main()
