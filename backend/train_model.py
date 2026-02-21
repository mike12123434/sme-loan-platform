"""
train_model.py — 訓練腳本（Render 部署安全版）

設計原則：
1. 若 model.pkl 已存在 → 跳過訓練（節省 Build 時間）
2. 若 CSV 不存在 → 用合成資料訓練一個輕量 fallback 模型
3. 完全不依賴 streamlit，純 CLI 可執行
"""

import os
import pickle
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

# ── 路徑設定
MODEL_PATH = os.getenv("MODEL_PATH", "model.pkl")
DATA_PATH  = os.getenv("DATA_PATH",  "nigeria_sme_loans_full_sample.csv")

# ── 特徵名稱（與 main.py 必須一致）
FEATURE_NAMES = [
    "annual_revenue_ntd",
    "revenue_per_employee",
    "years_in_business",
    "num_employees",
    "business_growth_proxy",
    "credit_score",
    "owner_experience_years",
    "business_sector_risk",
    "loan_amount_ntd",
    "debt_to_revenue_ratio",
    "collateral_coverage",
    "tenor_months",
    "existing_debt_proxy",
]

NGN_TO_NTD = 0.08

SECTOR_RISK = {
    "manufacturing": 0.15, "retail_trade": 0.20, "services": 0.25,
    "agriculture":   0.30, "construction": 0.28, "technology": 0.22,
    "other":         0.25,
}


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """將原始 CSV 欄位轉換為模型特徵。"""
    out = pd.DataFrame()
    out["annual_revenue_ntd"]     = df["annual_revenue_ngn"] * NGN_TO_NTD
    out["revenue_per_employee"]   = (df["annual_revenue_ngn"] / df["num_employees"].replace(0, 1)) * NGN_TO_NTD
    out["years_in_business"]      = df["years_in_business"]
    out["num_employees"]          = df["num_employees"]
    out["business_growth_proxy"]  = df["principal_ngn"] / df["annual_revenue_ngn"].replace(0, 1)
    out["credit_score"]           = df["credit_score"]
    out["owner_experience_years"] = df["years_in_business"]
    out["business_sector_risk"]   = df["business_sector"].map(SECTOR_RISK).fillna(0.25)
    out["loan_amount_ntd"]        = df["principal_ngn"] * NGN_TO_NTD
    out["debt_to_revenue_ratio"]  = df["principal_ngn"] / df["annual_revenue_ngn"].replace(0, 1)
    out["collateral_coverage"]    = df["collateral_value_ngn"] / df["principal_ngn"].replace(0, 1)
    out["tenor_months"]           = df["tenor_months"]
    out["existing_debt_proxy"]    = df["interest_rate_annual"]
    return out


def make_synthetic_data(n: int = 400) -> tuple:
    """
    當 CSV 不存在時，產生合成訓練資料。
    僅用於確保部署時 model.pkl 能被建立。
    """
    rng = np.random.default_rng(42)
    X = pd.DataFrame({
        "annual_revenue_ntd":     rng.uniform(1e6,  20e6, n),
        "revenue_per_employee":   rng.uniform(5e4,   5e5, n),
        "years_in_business":      rng.integers(1, 30, n).astype(float),
        "num_employees":          rng.integers(1, 200, n).astype(float),
        "business_growth_proxy":  rng.uniform(0.05, 2.0, n),
        "credit_score":           rng.uniform(350, 820, n),
        "owner_experience_years": rng.integers(1, 30, n).astype(float),
        "business_sector_risk":   rng.choice([0.15, 0.20, 0.22, 0.25, 0.28, 0.30], n),
        "loan_amount_ntd":        rng.uniform(2e5, 10e6, n),
        "debt_to_revenue_ratio":  rng.uniform(0.05, 3.0, n),
        "collateral_coverage":    rng.uniform(0.3,  3.0, n),
        "tenor_months":           rng.choice([12, 24, 36, 48, 60, 72, 84], n).astype(float),
        "existing_debt_proxy":    rng.uniform(0.04, 0.15, n),
    })
    # 違約機率：信用分數越低、DBR越高 → 違約率越高
    prob = 1 / (1 + np.exp(
        (X["credit_score"] - 580) * 0.02
        - X["debt_to_revenue_ratio"] * 1.5
        + X["collateral_coverage"] * 0.5
    ))
    y = (rng.uniform(0, 1, n) < prob).astype(int)
    return X, y


def train_and_save():
    """主訓練函式。"""

    # ── 若 model.pkl 已存在，跳過
    if os.path.exists(MODEL_PATH):
        print(f"✅ {MODEL_PATH} 已存在，跳過訓練。")
        return

    # ── 嘗試讀取真實資料
    if os.path.exists(DATA_PATH):
        print(f"📥 讀取資料：{DATA_PATH}")
        df = pd.read_csv(DATA_PATH)
        print(f"   資料筆數：{len(df)}")
        X_raw = build_features(df).fillna(0)
        y = df["default_180d"].astype(int)

        # 嘗試使用 Stacking（需要 imbalanced-learn + xgboost）
        try:
            from xgboost import XGBClassifier
            from sklearn.ensemble import StackingClassifier, GradientBoostingClassifier
            from imblearn.over_sampling import SMOTE

            X_train, X_test, y_train, y_test = train_test_split(
                X_raw, y, test_size=0.3, random_state=42, stratify=y
            )
            scaler = StandardScaler()
            Xtr = scaler.fit_transform(X_train)
            Xte = scaler.transform(X_test)

            smote = SMOTE(random_state=42, k_neighbors=min(5, y_train.sum() - 1))
            Xb, yb = smote.fit_resample(Xtr, y_train)

            estimators = [
                ("xgb", XGBClassifier(n_estimators=100, max_depth=5, learning_rate=0.1,
                                       subsample=0.8, colsample_bytree=0.8,
                                       random_state=42, eval_metric="logloss", verbosity=0)),
                ("rf",  RandomForestClassifier(n_estimators=100, max_depth=10,
                                               class_weight="balanced", random_state=42, n_jobs=-1)),
                ("gb",  GradientBoostingClassifier(n_estimators=100, max_depth=5,
                                                   learning_rate=0.1, subsample=0.8, random_state=42)),
            ]
            model = StackingClassifier(
                estimators=estimators,
                final_estimator=LogisticRegression(C=1.0, max_iter=1000, random_state=42),
                cv=5, n_jobs=-1
            )
            print("🤖 訓練 Stacking 集成模型...")
            model.fit(Xb, yb)
            auc = roc_auc_score(y_test, model.predict_proba(Xte)[:, 1])
            print(f"   ✅ Stacking ROC AUC：{auc:.4f}")

        except Exception as e:
            print(f"⚠️  Stacking 失敗 ({e})，改用 RandomForest...")
            scaler = StandardScaler()
            Xtr = scaler.fit_transform(X_raw)
            model = RandomForestClassifier(n_estimators=200, max_depth=10,
                                           class_weight="balanced", random_state=42, n_jobs=-1)
            model.fit(Xtr, y)
            auc = roc_auc_score(y, model.predict_proba(Xtr)[:, 1])
            print(f"   ✅ RandomForest ROC AUC（訓練集）：{auc:.4f}")

    else:
        # ── 合成資料 fallback
        print(f"⚠️  找不到 {DATA_PATH}，使用合成資料訓練 fallback 模型...")
        X_raw, y = make_synthetic_data(400)

        scaler = StandardScaler()
        Xtr = scaler.fit_transform(X_raw)
        model = RandomForestClassifier(n_estimators=100, max_depth=8,
                                       class_weight="balanced", random_state=42, n_jobs=-1)
        model.fit(Xtr, y)
        auc = roc_auc_score(y, model.predict_proba(Xtr)[:, 1])
        print(f"   ✅ Fallback RandomForest AUC（訓練集）：{auc:.4f}")

    # ── 儲存
    bundle = {
        "model":         model,
        "scaler":        scaler,
        "feature_names": FEATURE_NAMES,
    }
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(bundle, f, protocol=4)

    size_mb = os.path.getsize(MODEL_PATH) / 1e6
    print(f"💾 {MODEL_PATH} 已儲存（{size_mb:.1f} MB）")
    print("   FastAPI 啟動後將自動載入此模型。")


if __name__ == "__main__":
    train_and_save()
