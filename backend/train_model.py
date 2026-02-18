"""
模型訓練腳本：train_model.py
用途：從 nigeria_sme_loans_full_sample.csv 訓練模型並匯出 model.pkl
執行方式：python train_model.py
"""

import pickle
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import StackingClassifier, RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from xgboost import XGBClassifier
from imblearn.over_sampling import SMOTE
import os

# ── 讀取資料集
DATA_PATH = os.getenv("DATA_PATH", "nigeria_sme_loans_full_sample.csv")

print(f"📥 讀取資料：{DATA_PATH}")
df = pd.read_csv(DATA_PATH)
print(f"   資料筆數：{len(df)}")
print(f"   欄位：{list(df.columns)}")

# ── 特徵轉換（與 Streamlit app 一致）
NGN_TO_NTD = 0.08

SECTOR_RISK = {
    "manufacturing": 0.15, "retail_trade": 0.20, "services": 0.25,
    "agriculture": 0.30, "construction": 0.28, "technology": 0.22, "other": 0.25
}

df_feat = pd.DataFrame()
df_feat["annual_revenue_ntd"]       = df["annual_revenue_ngn"] * NGN_TO_NTD
df_feat["revenue_per_employee"]     = (df["annual_revenue_ngn"] / df["num_employees"].replace(0, 1)) * NGN_TO_NTD
df_feat["years_in_business"]        = df["years_in_business"]
df_feat["num_employees"]            = df["num_employees"]
df_feat["business_growth_proxy"]    = df["principal_ngn"] / df["annual_revenue_ngn"].replace(0, 1)
df_feat["credit_score"]             = df["credit_score"]
df_feat["owner_experience_years"]   = df["years_in_business"]
df_feat["business_sector_risk"]     = df["business_sector"].map(SECTOR_RISK).fillna(0.25)
df_feat["loan_amount_ntd"]          = df["principal_ngn"] * NGN_TO_NTD
df_feat["debt_to_revenue_ratio"]    = df["principal_ngn"] / df["annual_revenue_ngn"].replace(0, 1)
df_feat["collateral_coverage"]      = df["collateral_value_ngn"] / df["principal_ngn"].replace(0, 1)
df_feat["tenor_months"]             = df["tenor_months"]
df_feat["existing_debt_proxy"]      = df["interest_rate_annual"]

FEATURE_NAMES = list(df_feat.columns)
y = df["default_180d"].astype(int)

print(f"\n🔢 特徵數量：{len(FEATURE_NAMES)}")
print(f"   違約率：{y.mean()*100:.1f}%")

# ── 清理缺失值
df_feat = df_feat.fillna(df_feat.median())

# ── 分割訓練/測試集
X_train, X_test, y_train, y_test = train_test_split(
    df_feat, y, test_size=0.3, random_state=42, stratify=y
)

# ── 標準化
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled  = scaler.transform(X_test)

# ── SMOTE 過採樣（處理不平衡）
smote = SMOTE(random_state=42, k_neighbors=min(5, y_train.sum()-1))
X_balanced, y_balanced = smote.fit_resample(X_train_scaled, y_train)

# ── Stacking 集成模型
print("\n🤖 訓練 Stacking 集成模型...")
estimators = [
    ("xgb", XGBClassifier(
        n_estimators=100, max_depth=5, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8,
        reg_alpha=0.1, reg_lambda=1.0,
        random_state=42, eval_metric="logloss", verbosity=0
    )),
    ("rf", RandomForestClassifier(
        n_estimators=100, max_depth=10,
        min_samples_split=10, min_samples_leaf=5,
        class_weight="balanced", random_state=42, n_jobs=-1
    )),
    ("gb", GradientBoostingClassifier(
        n_estimators=100, max_depth=5, learning_rate=0.1,
        subsample=0.8, random_state=42
    )),
]

model = StackingClassifier(
    estimators=estimators,
    final_estimator=LogisticRegression(penalty="l2", C=1.0, max_iter=1000, random_state=42),
    cv=5, n_jobs=-1
)

model.fit(X_balanced, y_balanced)

# ── 評估
y_pred = model.predict_proba(X_test_scaled)[:, 1]
auc = roc_auc_score(y_test, y_pred)
print(f"   ✅ ROC AUC：{auc:.4f}")

# ── 匯出 model.pkl
bundle = {
    "model": model,
    "scaler": scaler,
    "feature_names": FEATURE_NAMES,
    "roc_auc": auc,
}

with open("model.pkl", "wb") as f:
    pickle.dump(bundle, f)

print("\n💾 model.pkl 已儲存！")
print("   現在可以啟動 FastAPI：uvicorn main:app --reload")
