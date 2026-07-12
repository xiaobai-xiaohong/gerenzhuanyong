"""
甲醇LSTM优化模型 v2
改进：增加数据量、Attention机制、更好的正则化、学习率调度
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
# 数据收集 - 增加数据量
# ============================================================
def fetch_data(symbol='MA0', days=1500):
    """获取更长历史数据"""
    print(f"获取 {symbol} 历史数据...")
    df = ak.futures_main_sina(symbol=symbol)
    df = df.tail(days).reset_index(drop=True)
    df['日期'] = pd.to_datetime(df['日期'])
    print(f"获取 {len(df)} 条数据，时间范围: {df['日期'].iloc[0]} ~ {df['日期'].iloc[-1]}")
    return df

# ============================================================
# 特征工程 - 增强版
# ============================================================
def create_features(df):
    """创建增强版技术指标特征"""
    data = df.copy()
    
    # 价格特征
    data['returns'] = data['收盘价'].pct_change()
    data['log_returns'] = np.log(data['收盘价'] / data['收盘价'].shift(1))
    data['returns_2'] = data['returns'] ** 2
    
    # 移动平均
    for window in [5, 10, 20, 60, 120]:
        data[f'MA{window}'] = data['收盘价'].rolling(window).mean()
        data[f'MA{window}_ratio'] = data['收盘价'] / data[f'MA{window}']
    
    # 价格变化率
    for period in [1, 3, 5, 10]:
        data[f'return_{period}d'] = data['收盘价'].pct_change(period)
    
    # 波动率
    for window in [5, 10, 20, 60]:
        data[f'volatility_{window}'] = data['returns'].rolling(window).std()
        data[f'volatility_{window}_ratio'] = data[f'volatility_{window}'] / data[f'volatility_{window}'].rolling(20).mean()
    
    # RSI
    for period in [6, 12, 24]:
        delta = data['收盘价'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        data[f'RSI_{period}'] = 100 - (100 / (1 + rs))
    
    # MACD
    exp1 = data['收盘价'].ewm(span=12, adjust=False).mean()
    exp2 = data['收盘价'].ewm(span=26, adjust=False).mean()
    data['MACD'] = exp1 - exp2
    data['MACD_signal'] = data['MACD'].ewm(span=9, adjust=False).mean()
    data['MACD_hist'] = data['MACD'] - data['MACD_signal']
    
    # 布林带
    data['BB_mid'] = data['收盘价'].rolling(20).mean()
    data['BB_std'] = data['收盘价'].rolling(20).std()
    data['BB_upper'] = data['BB_mid'] + 2 * data['BB_std']
    data['BB_lower'] = data['BB_mid'] - 2 * data['BB_std']
    data['BB_width'] = (data['BB_upper'] - data['BB_lower']) / data['BB_mid']
    data['BB_position'] = (data['收盘价'] - data['BB_lower']) / (data['BB_upper'] - data['BB_lower'])
    
    # KDJ
    low_min = data['最低价'].rolling(9).min()
    high_max = data['最高价'].rolling(9).max()
    rsv = (data['收盘价'] - low_min) / (high_max - low_min) * 100
    data['K'] = rsv.ewm(com=2, adjust=False).mean()
    data['D'] = data['K'].ewm(com=2, adjust=False).mean()
    data['J'] = 3 * data['K'] - 2 * data['D']
    
    # ATR
    high_low = data['最高价'] - data['最低价']
    high_close = np.abs(data['最高价'] - data['收盘价'].shift())
    low_close = np.abs(data['最低价'] - data['收盘价'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    data['ATR_14'] = tr.rolling(14).mean()
    data['ATR_ratio'] = data['ATR_14'] / data['收盘价']
    
    # 成交量特征
    data['volume_ma5'] = data['成交量'].rolling(5).mean()
    data['volume_ma20'] = data['成交量'].rolling(20).mean()
    data['volume_ratio'] = data['成交量'] / data['volume_ma5']
    data['volume_ratio20'] = data['成交量'] / data['volume_ma20']
    
    # 持仓量特征
    data['hold_ma5'] = data['持仓量'].rolling(5).mean()
    data['hold_ma20'] = data['持仓量'].rolling(20).mean()
    data['hold_ratio'] = data['持仓量'] / data['hold_ma5']
    
    # 价格位置
    data['high_low_ratio'] = (data['收盘价'] - data['最低价']) / (data['最高价'] - data['最低价'])
    data['close_high_ratio'] = (data['收盘价'] - data['最低价'].rolling(20).min()) / (data['最高价'].rolling(20).max() - data['最低价'].rolling(20).min())
    
    # 趋势强度
    data['trend_5'] = (data['收盘价'] - data['收盘价'].shift(5)) / 5
    data['trend_10'] = (data['收盘价'] - data['收盘价'].shift(10)) / 10
    data['trend_20'] = (data['收盘价'] - data['收盘价'].shift(20)) / 20
    
    # 目标变量：次日涨跌（1=涨，0=跌）
    data['target'] = (data['收盘价'].shift(-1) > data['收盘价']).astype(int)
    
    return data

# ============================================================
# LSTM + Attention模型
# ============================================================
class LSTMAttention(nn.Module):
    def __init__(self, input_dim, hidden_dim=128, num_layers=3, dropout=0.3, num_heads=4):
        super(LSTMAttention, self).__init__()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        
        # LSTM层
        self.lstm = nn.LSTM(
            input_dim, hidden_dim, num_layers,
            batch_first=True, dropout=dropout if num_layers > 1 else 0
        )
        
        # Attention层
        self.attention = nn.MultiheadAttention(
            embed_dim=hidden_dim, num_heads=num_heads, dropout=dropout, batch_first=True
        )
        
        # 分类头
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
        
        # Layer Norm
        self.norm = nn.LayerNorm(hidden_dim)
    
    def forward(self, x):
        # LSTM
        lstm_out, _ = self.lstm(x)  # (batch, seq_len, hidden)
        
        # Self-Attention
        attn_out, _ = self.attention(lstm_out, lstm_out, lstm_out)
        attn_out = self.norm(attn_out + lstm_out)  # Residual
        
        # 取最后一个时间步
        out = attn_out[:, -1, :]
        
        # 分类
        out = self.classifier(out)
        return out

# ============================================================
# 训练函数
# ============================================================
def train_model(model, X_train, y_train, epochs=150, batch_size=64, lr=0.001):
    """训练模型（带学习率调度）"""
    X_tensor = torch.FloatTensor(X_train)
    y_tensor = torch.FloatTensor(y_train).unsqueeze(1)
    
    dataset = TensorDataset(X_tensor, y_tensor)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    
    criterion = nn.BCELoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    
    best_loss = float('inf')
    patience = 20
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
        
        # Early stopping
        if avg_loss < best_loss:
            best_loss = avg_loss
            counter = 0
        else:
            counter += 1
        
        if (epoch + 1) % 10 == 0:
            lr_now = scheduler.get_last_lr()[0]
            print(f"Epoch {epoch+1}/{epochs}, Loss: {avg_loss:.4f}, LR: {lr_now:.6f}, Best: {best_loss:.4f}")
        
        if counter >= patience:
            print(f"Early stopping at epoch {epoch+1}")
            break
    
    return model

# ============================================================
# 评估函数
# ============================================================
def evaluate_model(model, X_test, y_test):
    """评估模型"""
    model.eval()
    with torch.no_grad():
        X_tensor = torch.FloatTensor(X_test)
        predictions = model(X_tensor).numpy()
    
    pred_classes = (predictions > 0.5).astype(int).flatten()
    accuracy = (pred_classes == y_test).mean()
    
    tp = ((pred_classes == 1) & (y_test == 1)).sum()
    tn = ((pred_classes == 0) & (y_test == 0)).sum()
    fp = ((pred_classes == 1) & (y_test == 0)).sum()
    fn = ((pred_classes == 0) & (y_test == 1)).sum()
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    print(f"\n模型评估结果:")
    print(f"准确率: {accuracy:.2%}")
    print(f"精确率: {precision:.2%}")
    print(f"召回率: {recall:.2%}")
    print(f"F1分数: {f1:.2%}")
    
    return accuracy, predictions

# ============================================================
# 主函数
# ============================================================
def main():
    print("="*60)
    print("甲醇LSTM优化模型 v2")
    print("="*60)
    
    # 1. 获取更长历史数据
    df = fetch_data('MA0', days=1500)
    
    # 2. 特征工程
    data = create_features(df)
    
    # 3. 准备数据
    feature_cols = [col for col in data.columns if col not in ['日期', '开盘价', '最高价', '最低价', '收盘价', '成交量', '持仓量', '动态结算价', 'target']]
    data = data.dropna().reset_index(drop=True)
    
    scaler = StandardScaler()
    features = scaler.fit_transform(data[feature_cols])
    
    lookback = 30  # 增加回看窗口
    X, y = [], []
    for i in range(lookback, len(features)):
        X.append(features[i-lookback:i])
        y.append(data['target'].iloc[i])
    
    X = np.array(X)
    y = np.array(y)
    
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    
    print(f"\n训练集: {len(X_train)} 样本")
    print(f"测试集: {len(X_test)} 样本")
    print(f"特征维度: {X.shape[2]}")
    print(f"序列长度: {lookback}")
    
    # 4. 构建增强模型
    model = LSTMAttention(
        input_dim=X_train.shape[2],
        hidden_dim=128,
        num_layers=3,
        dropout=0.3,
        num_heads=4
    )
    print(f"\n模型参数量: {sum(p.numel() for p in model.parameters()):,}")
    
    # 5. 训练
    print("\n开始训练...")
    model = train_model(model, X_train, y_train, epochs=150, batch_size=64)
    
    # 6. 评估
    accuracy, predictions = evaluate_model(model, X_test, y_test)
    
    # 7. 预测
    model.eval()
    with torch.no_grad():
        latest = torch.FloatTensor(features[-lookback:]).unsqueeze(0)
        pred = model(latest).item()
    
    direction = "看涨" if pred > 0.5 else "看跌"
    confidence = pred if pred > 0.5 else 1 - pred
    print(f"\n下一交易日预测:")
    print(f"方向: {direction}")
    print(f"置信度: {confidence:.2%}")
    print(f"概率: {pred:.2%}")
    
    # 8. 保存模型
    torch.save({
        'model_state_dict': model.state_dict(),
        'scaler': scaler,
        'feature_cols': feature_cols,
        'accuracy': accuracy,
        'lookback': lookback,
    }, 'C:/Users/Administrator/gerenzhuanyong/ma_lstm_v2.pth')
    print(f"\n模型已保存到: ma_lstm_v2.pth")
    
    return model, accuracy, pred

if __name__ == "__main__":
    model, accuracy, pred = main()
