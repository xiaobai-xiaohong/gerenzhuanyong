"""
甲醇LSTM分钟线预测模型
数据：15分钟K线（3合约合并，3000+条）
模型：LSTM + Attention
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

# ============================================================
# 数据获取
# ============================================================
def fetch_minute_data():
    """获取15分钟K线数据"""
    print("获取甲醇15分钟K线数据...")
    contracts = ['MA2509', 'MA2601', 'MA2605']
    all_data = []
    
    for contract in contracts:
        try:
            df = ak.futures_zh_minute_sina(symbol=contract, period='15')
            df['contract'] = contract
            all_data.append(df)
            print(f"  {contract}: {len(df)} 条")
        except Exception as e:
            print(f"  {contract}: 失败 {e}")
    
    data = pd.concat(all_data, ignore_index=True)
    data['datetime'] = pd.to_datetime(data['datetime'])
    data = data.sort_values('datetime').reset_index(drop=True)
    print(f"合并数据: {len(data)} 条")
    return data

# ============================================================
# 特征工程
# ============================================================
def create_features(data):
    """创建15分钟级别特征"""
    df = data.copy()
    
    # 价格特征
    df['returns'] = df['close'].pct_change()
    df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
    
    # 移动平均
    for window in [4, 8, 16, 32, 64]:  # 对应1h, 2h, 4h, 8h, 16h
        df[f'MA{window}'] = df['close'].rolling(window).mean()
        df[f'MA{window}_ratio'] = df['close'] / df[f'MA{window}']
    
    # 波动率
    for window in [4, 8, 16]:
        df[f'volatility_{window}'] = df['returns'].rolling(window).std()
    
    # RSI
    for period in [6, 12, 24]:
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        df[f'RSI_{period}'] = 100 - (100 / (1 + rs))
    
    # MACD
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_hist'] = df['MACD'] - df['MACD_signal']
    
    # 布林带
    df['BB_mid'] = df['close'].rolling(20).mean()
    df['BB_std'] = df['close'].rolling(20).std()
    df['BB_width'] = (df['BB_mid'] + 2*df['BB_std'] - (df['BB_mid'] - 2*df['BB_std'])) / df['BB_mid']
    df['BB_position'] = (df['close'] - (df['BB_mid'] - 2*df['BB_std'])) / (4*df['BB_std'])
    
    # 成交量特征
    df['volume_ma4'] = df['volume'].rolling(4).mean()
    df['volume_ratio'] = df['volume'] / df['volume_ma4']
    df['hold_ma4'] = df['hold'].rolling(4).mean()
    df['hold_ratio'] = df['hold'] / df['hold_ma4']
    
    # 价格位置
    df['high_low_ratio'] = (df['close'] - df['low']) / (df['high'] - df['low'])
    
    # 时间特征
    df['hour'] = df['datetime'].dt.hour
    df['minute'] = df['datetime'].dt.minute
    df['is_morning'] = (df['hour'] < 11).astype(int)
    df['is_afternoon'] = (df['hour'] >= 13).astype(int)
    
    # 合约编码
    df['contract_id'] = df['contract'].map({'MA2509': 0, 'MA2601': 1, 'MA2605': 2})
    
    # 目标变量
    df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
    
    return df

# ============================================================
# LSTM + Attention
# ============================================================
class LSTMAttention(nn.Module):
    def __init__(self, input_dim, hidden_dim=128, num_layers=2, dropout=0.3, num_heads=4):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, num_layers, batch_first=True, dropout=dropout)
        self.attention = nn.MultiheadAttention(embed_dim=hidden_dim, num_heads=num_heads, dropout=dropout, batch_first=True)
        self.norm = nn.LayerNorm(hidden_dim)
        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )
    
    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        attn_out, _ = self.attention(lstm_out, lstm_out, lstm_out)
        out = self.norm(attn_out + lstm_out)
        out = self.classifier(out[:, -1, :])
        return out

# ============================================================
# 训练
# ============================================================
def train_model(model, X_train, y_train, epochs=100, batch_size=64, lr=0.001):
    X_tensor = torch.FloatTensor(X_train)
    y_tensor = torch.FloatTensor(y_train).unsqueeze(1)
    dataset = TensorDataset(X_tensor, y_tensor)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    
    criterion = nn.BCELoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    
    best_loss = float('inf')
    patience = 15
    counter = 0
    
    model.train()
    for epoch in range(epochs):
        total_loss = 0
        for batch_X, batch_y in dataloader:
            optimizer.zero_grad()
            output = model(batch_X)
            loss = criterion(output, batch_y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            total_loss += loss.item()
        
        scheduler.step()
        avg_loss = total_loss / len(dataloader)
        
        if avg_loss < best_loss:
            best_loss = avg_loss
            counter = 0
        else:
            counter += 1
        
        if (epoch + 1) % 10 == 0:
            print(f"  Epoch {epoch+1}/{epochs}, Loss: {avg_loss:.4f}")
        
        if counter >= patience:
            print(f"  Early stopping at epoch {epoch+1}")
            break
    
    return model

# ============================================================
# 主函数
# ============================================================
def main():
    print("="*60)
    print("甲醇LSTM分钟线预测模型")
    print("="*60)
    
    # 1. 获取数据
    data = fetch_minute_data()
    
    # 2. 特征工程
    data = create_features(data)
    
    # 3. 准备数据
    feature_cols = [col for col in data.columns if col not in 
                    ['datetime', 'open', 'high', 'low', 'close', 'volume', 'hold', 'contract', 'target']]
    
    data = data.dropna().reset_index(drop=True)
    print(f"有效数据: {len(data)} 条")
    
    scaler = StandardScaler()
    features = scaler.fit_transform(data[feature_cols])
    
    lookback = 32  # 32个15分钟 = 8小时
    X, y = [], []
    for i in range(lookback, len(features)):
        X.append(features[i-lookback:i])
        y.append(data['target'].iloc[i])
    
    X = np.array(X)
    y = np.array(y)
    
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    
    print(f"训练集: {len(X_train)} 样本")
    print(f"测试集: {len(X_test)} 样本")
    print(f"特征维度: {X.shape[2]}")
    print(f"序列长度: {lookback}")
    
    # 4. 构建模型
    model = LSTMAttention(
        input_dim=X_train.shape[2],
        hidden_dim=128,
        num_layers=2,
        dropout=0.3,
        num_heads=4
    )
    print(f"模型参数量: {sum(p.numel() for p in model.parameters()):,}")
    
    # 5. 训练
    print("\n开始训练...")
    model = train_model(model, X_train, y_train, epochs=100, batch_size=64)
    
    # 6. 评估
    model.eval()
    with torch.no_grad():
        X_tensor = torch.FloatTensor(X_test)
        predictions = model(X_tensor).numpy().flatten()
    
    pred_classes = (predictions > 0.5).astype(int)
    accuracy = (pred_classes == y_test).mean()
    
    print(f"\n模型评估结果:")
    print(f"准确率: {accuracy:.2%}")
    
    # 混淆矩阵
    tp = ((pred_classes == 1) & (y_test == 1)).sum()
    tn = ((pred_classes == 0) & (y_test == 0)).sum()
    fp = ((pred_classes == 1) & (y_test == 0)).sum()
    fn = ((pred_classes == 0) & (y_test == 1)).sum()
    print(f"TP: {tp}, FP: {fp}, TN: {tn}, FN: {fn}")
    
    # 7. 预测最新
    with torch.no_grad():
        latest = torch.FloatTensor(features[-lookback:]).unsqueeze(0)
        pred = model(latest).item()
    
    direction = "看涨" if pred > 0.5 else "看跌"
    confidence = pred if pred > 0.5 else 1 - pred
    print(f"\n下一周期预测:")
    print(f"方向: {direction}")
    print(f"置信度: {confidence:.2%}")
    print(f"概率: {pred:.2%}")
    
    # 8. 保存
    torch.save({
        'model_state_dict': model.state_dict(),
        'scaler': scaler,
        'feature_cols': feature_cols,
        'accuracy': accuracy,
        'lookback': lookback,
    }, 'C:/Users/Administrator/gerenzhuanyong/ma_lstm_minute.pth')
    print(f"\n模型已保存: ma_lstm_minute.pth")
    
    return accuracy, pred

if __name__ == "__main__":
    acc, pred = main()
