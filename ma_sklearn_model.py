"""
甲醇预测模型 - sklearn版本（无需PyTorch）
用于验证特征工程和数据流程
"""
import numpy as np
import pandas as pd
import akshare as ak
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, classification_report
import warnings
warnings.filterwarnings('ignore')

# 获取数据
print("获取甲醇历史数据...")
df = ak.futures_main_sina(symbol='MA0')
df = df.tail(500).reset_index(drop=True)
print(f"获取 {len(df)} 条数据")

# 特征工程
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
data['BB_upper'] = data['BB_mid'] + 2 * data['BB_std']
data['BB_lower'] = data['BB_mid'] - 2 * data['BB_std']
data['BB_width'] = (data['BB_upper'] - data['BB_lower']) / data['BB_mid']
data['BB_position'] = (data['收盘价'] - data['BB_lower']) / (data['BB_upper'] - data['BB_lower'])

data['volume_ma5'] = data['成交量'].rolling(5).mean()
data['volume_ratio'] = data['成交量'] / data['volume_ma5']
data['hold_ma5'] = data['持仓量'].rolling(5).mean()
data['hold_ratio'] = data['持仓量'] / data['hold_ma5']
data['high_low_ratio'] = (data['收盘价'] - data['最低价']) / (data['最高价'] - data['最低价'])

data['target'] = (data['收盘价'].shift(-1) > data['收盘价']).astype(int)

# 选择特征
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

data = data.dropna().reset_index(drop=True)

# 标准化
scaler = StandardScaler()
X = scaler.fit_transform(data[feature_cols])
y = data['target'].values

# 划分
split = int(len(X) * 0.8)
X_train, X_test = X[:split], X[split:]
y_train, y_test = y[:split], y[split:]

print(f"\n训练集: {len(X_train)} 样本")
print(f"测试集: {len(X_test)} 样本")

# 随机森林
print("\n" + "="*50)
print("模型1: 随机森林")
print("="*50)
rf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
rf.fit(X_train, y_train)
rf_pred = rf.predict(X_test)
rf_acc = accuracy_score(y_test, rf_pred)
print(f"准确率: {rf_acc:.2%}")
print(classification_report(y_test, rf_pred, target_names=['跌', '涨']))

# 梯度提升
print("="*50)
print("模型2: 梯度提升")
print("="*50)
gb = GradientBoostingClassifier(n_estimators=100, max_depth=5, random_state=42)
gb.fit(X_train, y_train)
gb_pred = gb.predict(X_test)
gb_acc = accuracy_score(y_test, gb_pred)
print(f"准确率: {gb_acc:.2%}")
print(classification_report(y_test, gb_pred, target_names=['跌', '涨']))

# 预测下一个交易日
print("="*50)
print("下一交易日预测")
print("="*50)
latest = X[-1:].reshape(1, -1)
rf_prob = rf.predict_proba(latest)[0]
gb_prob = gb.predict_proba(latest)[0]

print(f"随机森林: 涨{rf_prob[1]:.2%} 跌{rf_prob[0]:.2%} → {'看涨' if rf_prob[1]>0.5 else '看跌'}")
print(f"梯度提升: 涨{gb_prob[1]:.2%} 跌{gb_prob[0]:.2%} → {'看涨' if gb_prob[1]>0.5 else '看跌'}")

# 特征重要性
print("\n" + "="*50)
print("特征重要性 TOP10")
print("="*50)
importances = pd.Series(rf.feature_importances_, index=feature_cols)
for feat, imp in importances.sort_values(ascending=False).head(10).items():
    print(f"  {feat}: {imp:.4f}")
