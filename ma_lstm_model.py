"""
甲醇深度学习预测模型 - LSTM
数据：akshare获取历史行情
模型：LSTM价格方向预测
"""
import numpy as np
import pandas as pd
import akshare as ak
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# 第一步：数据收集
# ============================================================
def fetch_data(symbol='MA0', days=500):
    """获取历史行情数据"""
    print(f"获取 {symbol} 历史数据...")
    df = ak.futures_main_sina(symbol=symbol)
    df = df.tail(days).reset_index(drop=True)
    df['日期'] = pd.to_datetime(df['日期'])
    print(f"获取 {len(df)} 条数据，时间范围: {df['日期'].iloc[0]} ~ {df['日期'].iloc[-1]}")
    return df

# ============================================================
# 第二步：特征工程
# ============================================================
def create_features(df):
    """创建技术指标特征"""
    data = df.copy()
    
    # 价格特征
    data['returns'] = data['收盘价'].pct_change()
    data['log_returns'] = np.log(data['收盘价'] / data['收盘价'].shift(1))
    
    # 移动平均
    for window in [5, 10, 20, 60]:
        data[f'MA{window}'] = data['收盘价'].rolling(window).mean()
        data[f'MA{window}_ratio'] = data['收盘价'] / data[f'MA{window}']
    
    # 波动率
    for window in [5, 10, 20]:
        data[f'volatility_{window}'] = data['returns'].rolling(window).std()
    
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
    
    # 成交量特征
    data['volume_ma5'] = data['成交量'].rolling(5).mean()
    data['volume_ratio'] = data['成交量'] / data['volume_ma5']
    
    # 持仓量特征
    data['hold_ma5'] = data['持仓量'].rolling(5).mean()
    data['hold_ratio'] = data['持仓量'] / data['hold_ma5']
    
    # 价格位置
    data['high_low_ratio'] = (data['收盘价'] - data['最低价']) / (data['最高价'] - data['最低价'])
    
    # 目标变量：次日涨跌（1=涨，0=跌）
    data['target'] = (data['收盘价'].shift(-1) > data['收盘价']).astype(int)
    
    return data

# ============================================================
# 第三步：数据预处理
# ============================================================
def prepare_data(data, lookback=20):
    """准备LSTM输入数据"""
    # 选择特征列
    feature_cols = [
        'returns', 'log_returns',
        'MA5_ratio', 'MA10_ratio', 'MA20_ratio', 'MA60_ratio',
        'volatility_5', 'volatility_10', 'volatility_20',
        'RSI_6', 'RSI_12', 'RSI_24',
        'MACD', 'MACD_signal', 'MACD_hist',
        'BB_width', 'BB_position',
        'volume_ratio', 'hold_ratio',
        'high_low_ratio'
    ]
    
    # 删除NaN
    data = data.dropna().reset_index(drop=True)
    
    # 标准化
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    features = scaler.fit_transform(data[feature_cols])
    
    # 创建序列
    X, y = [], []
    for i in range(lookback, len(features)):
        X.append(features[i-lookback:i])
        y.append(data['target'].iloc[i])
    
    X = np.array(X)
    y = np.array(y)
    
    # 划分训练集和测试集
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    
    print(f"训练集: {len(X_train)} 样本")
    print(f"测试集: {len(X_test)} 样本")
    print(f"特征维度: {X.shape[2]}")
    print(f"序列长度: {lookback}")
    
    return X_train, X_test, y_train, y_test, scaler, feature_cols

# ============================================================
# 第四步：LSTM模型
# ============================================================
def build_lstm_model(input_dim, hidden_dim=64, num_layers=2, dropout=0.2):
    """构建LSTM模型"""
    try:
        import torch
        import torch.nn as nn
        
        class LSTMModel(nn.Module):
            def __init__(self, input_dim, hidden_dim, num_layers, dropout):
                super(LSTMModel, self).__init__()
                self.hidden_dim = hidden_dim
                self.num_layers = num_layers
                
                self.lstm = nn.LSTM(
                    input_dim, hidden_dim, num_layers,
                    batch_first=True, dropout=dropout
                )
                self.fc = nn.Sequential(
                    nn.Linear(hidden_dim, 32),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                    nn.Linear(32, 1),
                    nn.Sigmoid()
                )
            
            def forward(self, x):
                h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_dim).to(x.device)
                c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_dim).to(x.device)
                out, _ = self.lstm(x, (h0, c0))
                out = self.fc(out[:, -1, :])
                return out
        
        model = LSTMModel(input_dim, hidden_dim, num_layers, dropout)
        print(f"LSTM模型构建成功，参数量: {sum(p.numel() for p in model.parameters()):,}")
        return model
    except ImportError:
        print("PyTorch未安装，使用备用方案...")
        return None

# ============================================================
# 第五步：训练
# ============================================================
def train_model(model, X_train, y_train, epochs=100, batch_size=32, lr=0.001):
    """训练模型"""
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    
    # 转换为Tensor
    X_tensor = torch.FloatTensor(X_train)
    y_tensor = torch.FloatTensor(y_train).unsqueeze(1)
    
    dataset = TensorDataset(X_tensor, y_tensor)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    
    criterion = nn.BCELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    
    model.train()
    for epoch in range(epochs):
        total_loss = 0
        for batch_X, batch_y in dataloader:
            optimizer.zero_grad()
            output = model(batch_X)
            loss = criterion(output, batch_y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        
        if (epoch + 1) % 10 == 0:
            avg_loss = total_loss / len(dataloader)
            print(f"Epoch {epoch+1}/{epochs}, Loss: {avg_loss:.4f}")
    
    return model

# ============================================================
# 第六步：评估
# ============================================================
def evaluate_model(model, X_test, y_test):
    """评估模型"""
    import torch
    
    model.eval()
    with torch.no_grad():
        X_tensor = torch.FloatTensor(X_test)
        predictions = model(X_tensor).numpy()
    
    # 转换为类别
    pred_classes = (predictions > 0.5).astype(int).flatten()
    
    # 准确率
    accuracy = (pred_classes == y_test).mean()
    
    # 混淆矩阵
    tp = ((pred_classes == 1) & (y_test == 1)).sum()
    tn = ((pred_classes == 0) & (y_test == 0)).sum()
    fp = ((pred_classes == 1) & (y_test == 0)).sum()
    fn = ((pred_classes == 0) & (y_test == 1)).sum()
    
    print(f"\n模型评估结果:")
    print(f"准确率: {accuracy:.2%}")
    print(f"预测涨: {(pred_classes == 1).sum()} 次")
    print(f"预测跌: {(pred_classes == 0).sum()} 次")
    print(f"实际涨: {(y_test == 1).sum()} 次")
    print(f"实际跌: {(y_test == 0).sum()} 次")
    print(f"真正例(TP): {tp}, 假正例(FP): {fp}")
    print(f"真负例(TN): {tn}, 假负例(FN): {fn}")
    
    # 精确率和召回率
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    print(f"精确率: {precision:.2%}")
    print(f"召回率: {recall:.2%}")
    print(f"F1分数: {f1:.2%}")
    
    return accuracy, predictions

# ============================================================
# 第七步：预测
# ============================================================
def predict_next(model, data, scaler, feature_cols, lookback=20):
    """预测下一个交易日"""
    import torch
    
    # 获取最新数据
    features = scaler.transform(data[feature_cols].values[-lookback:])
    X = torch.FloatTensor(features).unsqueeze(0)
    
    model.eval()
    with torch.no_grad():
        pred = model(X).item()
    
    direction = "看涨" if pred > 0.5 else "看跌"
    confidence = pred if pred > 0.5 else 1 - pred
    
    print(f"\n下一交易日预测:")
    print(f"方向: {direction}")
    print(f"置信度: {confidence:.2%}")
    print(f"概率: {pred:.2%}")
    
    return pred, direction

# ============================================================
# 主函数
# ============================================================
def main():
    print("="*60)
    print("甲醇LSTM预测模型")
    print("="*60)
    
    # 1. 获取数据
    df = fetch_data('MA0', days=500)
    
    # 2. 特征工程
    data = create_features(df)
    
    # 3. 准备数据
    X_train, X_test, y_train, y_test, scaler, feature_cols = prepare_data(data)
    
    # 4. 构建模型
    model = build_lstm_model(input_dim=X_train.shape[2])
    
    if model is None:
        print("无法构建模型，请先安装PyTorch")
        return
    
    # 5. 训练
    print("\n开始训练...")
    model = train_model(model, X_train, y_train, epochs=100)
    
    # 6. 评估
    accuracy, predictions = evaluate_model(model, X_test, y_test)
    
    # 7. 预测
    pred, direction = predict_next(model, data, scaler, feature_cols)
    
    # 8. 保存模型
    import torch
    torch.save({
        'model_state_dict': model.state_dict(),
        'scaler': scaler,
        'feature_cols': feature_cols,
        'accuracy': accuracy,
    }, 'C:/Users/Administrator/gerenzhuanyong/ma_lstm_model.pth')
    print(f"\n模型已保存到: ma_lstm_model.pth")
    
    return model, accuracy, pred

if __name__ == "__main__":
    model, accuracy, pred = main()
