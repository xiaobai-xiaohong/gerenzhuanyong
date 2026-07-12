"""
甲醇预测集成模型
集成：随机森林 + LSTM + XGBoost
取多数投票
"""
import numpy as np
import pandas as pd
import akshare as ak
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import accuracy_score
import warnings
warnings.filterwarnings('ignore')

import torch
import torch.nn as nn

# ============================================================
# 数据获取和特征工程
# ============================================================
def fetch_and_prepare():
    """获取数据并准备特征"""
    print("获取甲醇历史数据...")
    df = ak.futures_main_sina(symbol='MA0')
    df = df.tail(1500).reset_index(drop=True)
    
    data = df.copy()
    data['returns'] = data['收盘价'].pct_change()
    data['log_returns'] = np.log(data['收盘价'] / data['收盘价'].shift(1))
    
    for window in [5, 10, 20, 60]:
        data[f'MA{window}'] = data['收盘价'].rolling(window).mean()
        data[f'MA{window}_ratio'] = data['收盘价'] / data[f'MA{window}']
    
    for window in [5, 10, 20]:
        data[f'volatility_{window}'] = data['returns'].rolling(window).std()
    
    for period in [6, 12, 24]:
        delta = data['收盘价'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        data[f'RSI_{period}'] = 100 - (100 / (1 + rs))
    
    exp1 = data['收盘价'].ewm(span=12, adjust=False).mean()
    exp2 = data['收盘价'].ewm(span=26, adjust=False).mean()
    data['MACD'] = exp1 - exp2
    data['MACD_signal'] = data['MACD'].ewm(span=9, adjust=False).mean()
    data['MACD_hist'] = data['MACD'] - data['MACD_signal']
    
    data['BB_mid'] = data['收盘价'].rolling(20).mean()
    data['BB_std'] = data['收盘价'].rolling(20).std()
    data['BB_width'] = (data['BB_mid'] + 2*data['BB_std'] - (data['BB_mid'] - 2*data['BB_std'])) / data['BB_mid']
    data['BB_position'] = (data['收盘价'] - (data['BB_mid'] - 2*data['BB_std'])) / (4*data['BB_std'])
    
    data['volume_ma5'] = data['成交量'].rolling(5).mean()
    data['volume_ratio'] = data['成交量'] / data['volume_ma5']
    data['hold_ma5'] = data['持仓量'].rolling(5).mean()
    data['hold_ratio'] = data['持仓量'] / data['hold_ma5']
    data['high_low_ratio'] = (data['收盘价'] - data['最低价']) / (data['最高价'] - data['最低价'])
    
    data['target'] = (data['收盘价'].shift(-1) > data['收盘价']).astype(int)
    
    feature_cols = [col for col in data.columns if col not in 
                    ['日期', '开盘价', '最高价', '最低价', '收盘价', '成交量', '持仓量', '动态结算价', 'target']]
    
    data = data.dropna().reset_index(drop=True)
    return data, feature_cols

# ============================================================
# LSTM模型（简化版，防过拟合）
# ============================================================
class SimpleLSTM(nn.Module):
    def __init__(self, input_dim, hidden_dim=64, dropout=0.4):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, 2, batch_first=True, dropout=dropout)
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )
    
    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])

# ============================================================
# 集成预测
# ============================================================
def ensemble_predict(X_train, y_train, X_test, y_test, X_latest):
    """集成多个模型"""
    results = {}
    
    # 1. 随机森林（多个参数）
    print("\n训练随机森林...")
    rf_models = []
    for n_est, depth in [(100, 8), (200, 10), (150, 12)]:
        rf = RandomForestClassifier(n_estimators=n_est, max_depth=depth, random_state=42, class_weight='balanced')
        rf.fit(X_train, y_train)
        rf_models.append(rf)
    
    rf_preds = np.mean([m.predict_proba(X_test)[:, 1] for m in rf_models], axis=0)
    rf_latest = np.mean([m.predict_proba(X_latest.reshape(1, -1))[:, 1] for m in rf_models], axis=0)
    results['RandomForest'] = {
        'test_pred': (rf_preds > 0.5).astype(int),
        'latest_prob': rf_latest[0]
    }
    
    # 2. 梯度提升（多个参数）
    print("训练梯度提升...")
    gb_models = []
    for n_est, depth, lr in [(100, 5, 0.1), (200, 4, 0.05), (150, 6, 0.08)]:
        gb = GradientBoostingClassifier(n_estimators=n_est, max_depth=depth, learning_rate=lr, random_state=42)
        gb.fit(X_train, y_train)
        gb_models.append(gb)
    
    gb_preds = np.mean([m.predict_proba(X_test)[:, 1] for m in gb_models], axis=0)
    gb_latest = np.mean([m.predict_proba(X_latest.reshape(1, -1))[:, 1] for m in gb_models], axis=0)
    results['GradientBoosting'] = {
        'test_pred': (gb_preds > 0.5).astype(int),
        'latest_prob': gb_latest[0]
    }
    
    # 3. LSTM（简化版）
    print("训练LSTM...")
    try:
        scaler_lstm = StandardScaler()
        X_train_lstm = scaler_lstm.fit_transform(X_train.reshape(-1, X_train.shape[-1])).reshape(X_train.shape)
        X_test_lstm = scaler_lstm.transform(X_test.reshape(-1, X_test.shape[-1])).reshape(X_test.shape)
        X_latest_lstm = scaler_lstm.transform(X_latest.reshape(1, -1))
        
        # 转换为序列
        lookback = 20
        X_seq_train, y_seq_train = [], []
        for i in range(lookback, len(X_train_lstm)):
            X_seq_train.append(X_train_lstm[i-lookback:i])
            y_seq_train.append(y_train[i])
        
        X_seq_train = np.array(X_seq_train)
        y_seq_train = np.array(y_seq_train)
        
        model = SimpleLSTM(input_dim=X_train.shape[-1], hidden_dim=64, dropout=0.4)
        criterion = nn.BCELoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-4)
        
        X_tensor = torch.FloatTensor(X_seq_train)
        y_tensor = torch.FloatTensor(y_seq_train).unsqueeze(1)
        
        model.train()
        for epoch in range(80):
            optimizer.zero_grad()
            output = model(X_tensor)
            loss = criterion(output, y_tensor)
            loss.backward()
            optimizer.step()
        
        model.eval()
        with torch.no_grad():
            # 测试集预测
            X_test_seq = []
            for i in range(lookback, len(X_test_lstm)):
                X_test_seq.append(X_test_lstm[i-lookback:i])
            X_test_seq = np.array(X_test_seq)
            lstm_test_pred = model(torch.FloatTensor(X_test_seq)).numpy().flatten()
            
            # 最新预测
            lstm_latest = model(torch.FloatTensor(X_latest_lstm)).item()
        
        results['LSTM'] = {
            'test_pred': (lstm_test_pred > 0.5).astype(int),
            'latest_prob': lstm_latest
        }
    except Exception as e:
        print(f"LSTM训练失败: {e}")
    
    # 4. 集成投票
    print("\n" + "="*60)
    print("集成预测结果")
    print("="*60)
    
    test_preds = []
    latest_probs = []
    for name, res in results.items():
        acc = (res['test_pred'] == y_test).mean()
        print(f"{name}: 准确率 {acc:.2%}, 最新概率 {res['latest_prob']:.2%}")
        test_preds.append(res['test_pred'])
        latest_probs.append(res['latest_prob'])
    
    # 多数投票
    ensemble_test = (np.mean(test_preds, axis=0) > 0.5).astype(int)
    ensemble_acc = (ensemble_test == y_test).mean()
    ensemble_prob = np.mean(latest_probs)
    
    print(f"\n集成准确率: {ensemble_acc:.2%}")
    print(f"集成最新概率: {ensemble_prob:.2%}")
    
    direction = "看涨" if ensemble_prob > 0.5 else "看跌"
    confidence = ensemble_prob if ensemble_prob > 0.5 else 1 - ensemble_prob
    print(f"预测方向: {direction}")
    print(f"置信度: {confidence:.2%}")
    
    return ensemble_acc, ensemble_prob

# ============================================================
# 主函数
# ============================================================
def main():
    print("="*60)
    print("甲醇集成预测模型")
    print("="*60)
    
    # 获取数据
    data, feature_cols = fetch_and_prepare()
    print(f"数据量: {len(data)} 条")
    
    # 准备特征
    scaler = StandardScaler()
    X = scaler.fit_transform(data[feature_cols])
    y = data['target'].values
    
    # 划分
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    
    print(f"训练集: {len(X_train)}, 测试集: {len(X_test)}")
    
    # 集成预测
    acc, prob = ensemble_predict(X_train, y_train, X_test, y_test, X[-1:])
    
    print("\n" + "="*60)
    print("最终结论")
    print("="*60)
    print(f"集成模型准确率: {acc:.2%}")
    print(f"下一交易日预测: {'看涨' if prob > 0.5 else '看跌'} ({prob:.2%})")
    
    return acc, prob

if __name__ == "__main__":
    acc, prob = main()
