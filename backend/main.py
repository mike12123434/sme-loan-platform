"""
永豐金控 AI法金貸款利率試算平台 - FastAPI Backend
版本：1.1 — 修復 CORS / 部署問題
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, List
import pickle
import os
import logging
import numpy as np
import pandas as pd
from pathlib import Path

# ─────────────────────────────────────────────
# 日誌設定
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# FastAPI App 初始化
# ─────────────────────────────────────────────
app = FastAPI(
    title="永豐金控 SME貸款利率試算API",
    description="AI驅動的中小企業法金貸款利率預測系統",
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─────────────────────────────────────────────
# CORS 設定
#
# 【重要設計說明】
# 生產環境有兩種策略：
#
# 策略 A（簡單，適合 Demo）：
#   allow_origins=["*"]  → 允許所有來源
#   缺點：不能同時設定 allow_credentials=True
#
# 策略 B（安全，適合正式環境）：
#   allow_origins=[明確的前端網址]
#   優點：精確控制，安全性高
#
# 目前使用策略 A 確保 Demo 可以運作。
# 部署後在 Render 環境變數設定 ALLOWED_ORIGINS 即可切換到策略 B。
# ─────────────────────────────────────────────

ALLOWED_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS", "*")

# 判斷是否使用萬用字元
if ALLOWED_ORIGINS_RAW.strip() == "*":
    ALLOWED_ORIGINS = ["*"]
    USE_CREDENTIALS = False   # 使用 * 時不能開 credentials
else:
    ALLOWED_ORIGINS = [o.strip() for o in ALLOWED_ORIGINS_RAW.split(",") if o.strip()]
    USE_CREDENTIALS = True

logger.info(f"CORS allowed origins: {ALLOWED_ORIGINS}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=USE_CREDENTIALS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ─────────────────────────────────────────────
# 全域 ML 模型
# ─────────────────────────────────────────────
MODEL = None
SCALER = None
FEATURE_NAMES = None


def load_model():
    global MODEL, SCALER, FEATURE_NAMES
    model_path = Path(os.getenv("MODEL_PATH", "model.pkl"))

    if not model_path.exists():
        logger.warning(f"⚠️  找不到 {model_path}，使用規則式定價（無ML調整）")
        return False

    try:
        with open(model_path, "rb") as f:
            bundle = pickle.load(f)
        MODEL = bundle.get("model")
        SCALER = bundle.get("scaler")
        FEATURE_NAMES = bundle.get("feature_names")
        logger.info(f"✅ 模型載入成功，特徵數：{len(FEATURE_NAMES) if FEATURE_NAMES else 'N/A'}")
        return True
    except Exception as e:
        logger.error(f"❌ 模型載入失敗：{e}")
        return False


@app.on_event("startup")
async def startup_event():
    load_model()


# ═══════════════════════════════════════════════════════════════
# Request / Response Schema
# ═══════════════════════════════════════════════════════════════

class LoanApplication(BaseModel):
    annual_revenue_ntd: float = Field(..., gt=0, description="年營收（新台幣）", example=5_000_000)
    years_in_business: int = Field(..., ge=1, le=100, description="營業年數", example=5)
    num_employees: int = Field(..., ge=1, le=10000, description="員工數", example=20)
    business_sector: str = Field(..., description="產業別", example="manufacturing")
    credit_score: int = Field(..., ge=300, le=850, description="信用分數", example=680)
    loan_amount_ntd: float = Field(..., gt=0, le=50_000_000, description="貸款金額", example=2_000_000)
    tenor_months: int = Field(..., ge=6, le=84, description="貸款期限（月）", example=36)
    collateral_value_ntd: float = Field(..., ge=0, description="擔保品價值", example=2_500_000)
    is_existing_customer: bool = Field(False, description="是否既有客戶")
    has_credit_guarantee: bool = Field(False, description="是否有信保基金")

    @validator("business_sector")
    def validate_sector(cls, v):
        valid = {"manufacturing", "retail_trade", "services", "agriculture",
                 "construction", "technology", "other"}
        if v not in valid:
            raise ValueError(f"產業別必須為：{', '.join(sorted(valid))}")
        return v


class PredictionResponse(BaseModel):
    final_rate: float
    final_rate_pct: str
    pd_score: float
    pd_score_pct: str
    risk_grade: int
    risk_grade_name: str
    risk_color: str
    components: list
    monthly_payment: float
    total_payment: float
    total_interest: float
    approval_decision: str
    approval_authority: str
    approval_conditions: str
    market_benchmark_rate: float
    rate_vs_market: float
    is_eligible: bool
    failed_rules: list
    ml_model_used: bool
    message: str


# ═══════════════════════════════════════════════════════════════
# 台灣市場基準利率（2025年）
# ═══════════════════════════════════════════════════════════════

TAIWAN_REDISCOUNT_RATE = 0.01875  # 央行重貼現率

RISK_GRADES = {
    1: {"name": "優良", "pd_max": 0.005, "color": "#28a745", "market_rate": 0.0280},
    2: {"name": "良好", "pd_max": 0.010, "color": "#5cb85c", "market_rate": 0.0350},
    3: {"name": "尚可", "pd_max": 0.025, "color": "#f0ad4e", "market_rate": 0.0450},
    4: {"name": "普通", "pd_max": 0.050, "color": "#ec971f", "market_rate": 0.0580},
    5: {"name": "注意", "pd_max": 0.100, "color": "#d58512", "market_rate": 0.0720},
    6: {"name": "次級", "pd_max": 0.200, "color": "#d9534f", "market_rate": 0.0900},
    7: {"name": "可疑", "pd_max": 0.500, "color": "#c9302c", "market_rate": 0.1100},
    8: {"name": "損失", "pd_max": 1.000, "color": "#ac2925", "market_rate": 0.1200},
}

APPROVAL_MATRIX = {
    1: {"decision": "建議核准", "authority": "分行經理",  "conditions": "標準條件"},
    2: {"decision": "建議核准", "authority": "分行經理",  "conditions": "標準條件"},
    3: {"decision": "建議核准", "authority": "區域主管",  "conditions": "標準條件加強擔保"},
    4: {"decision": "條件核准", "authority": "區域主管",  "conditions": "需額外擔保或保證人"},
    5: {"decision": "條件核准", "authority": "總行審查",  "conditions": "強化擔保及密切追蹤"},
    6: {"decision": "審慎評估", "authority": "總行審查",  "conditions": "特別簽報及風險控管"},
    7: {"decision": "不建議核准", "authority": "總行審查", "conditions": "除非有特殊理由及高階核准"},
    8: {"decision": "拒絕",     "authority": "N/A",       "conditions": "不符合授信政策"},
}


# ═══════════════════════════════════════════════════════════════
# Risk-Based Pricing Layer
# ═══════════════════════════════════════════════════════════════

class TaiwanMarketBenchmark:
    def __init__(self):
        self.base_rate = float(os.getenv("BASE_RATE", str(TAIWAN_REDISCOUNT_RATE + 0.00125)))
        self.credit_score_tiers = [
            {"min": 750, "max": 850, "premium": 0.000, "label": "優質"},
            {"min": 700, "max": 749, "premium": 0.005, "label": "良好"},
            {"min": 650, "max": 699, "premium": 0.015, "label": "尚可"},
            {"min": 600, "max": 649, "premium": 0.030, "label": "普通"},
            {"min": 550, "max": 599, "premium": 0.050, "label": "偏低"},
            {"min": 300, "max": 549, "premium": 0.080, "label": "低"},
        ]
        self.dbr_surcharge_tiers = [
            {"max_dbr": 0.5,  "surcharge": 0.000},
            {"max_dbr": 1.0,  "surcharge": 0.005},
            {"max_dbr": 2.0,  "surcharge": 0.015},
            {"max_dbr": 3.0,  "surcharge": 0.030},
            {"max_dbr": 5.0,  "surcharge": 0.050},
        ]

    def get_credit_score_premium(self, credit_score: int):
        for tier in self.credit_score_tiers:
            if tier["min"] <= credit_score <= tier["max"]:
                return tier["premium"], tier["label"]
        return 0.080, "低"

    def get_dbr_surcharge(self, dbr: float) -> float:
        for tier in self.dbr_surcharge_tiers:
            if dbr <= tier["max_dbr"]:
                return tier["surcharge"]
        return 0.050


class RiskBasedPricingLayer:
    def __init__(self):
        self.market = TaiwanMarketBenchmark()
        self.industry_premium = {
            "manufacturing": 0.0000, "technology": 0.0000,
            "services":      0.0025, "retail_trade": 0.0030,
            "construction":  0.0040, "agriculture":  0.0045,
            "other":         0.0030,
        }
        self.min_rate = 0.025
        self.max_rate = 0.120

    def calculate(self, pd_score, credit_score, dbr, loan_amount_ntd,
                  tenor_months, industry, collateral_coverage,
                  is_existing_customer, has_credit_guarantee, ml_adjustment=0.0):

        base = self.market.base_rate
        credit_premium, credit_label = self.market.get_credit_score_premium(credit_score)
        dbr_surcharge = self.market.get_dbr_surcharge(dbr)
        lgd = 0.40 * (1 - min(collateral_coverage * 0.4, 0.4))
        expected_loss = pd_score * lgd
        funding_cost = 0.0100
        target_spread = 0.0150
        maturity_premium = 0.0015 * (tenor_months / 12)
        size_discount = max(-0.0008 * (loan_amount_ntd / 10_000_000), -0.0100)
        industry_prem = self.industry_premium.get(industry, 0.0030)
        competitive_adj = -0.0050
        relationship_adj = -0.0030 if is_existing_customer else 0.0
        guarantee_adj = -0.0025 if has_credit_guarantee else 0.0
        ml_adj = max(-0.005, min(ml_adjustment, 0.005))

        total = (base + credit_premium + dbr_surcharge + expected_loss +
                 funding_cost + target_spread + maturity_premium + size_discount +
                 industry_prem + competitive_adj + relationship_adj + guarantee_adj + ml_adj)

        final_rate = max(self.min_rate, min(total, self.max_rate))

        return {
            "final_rate": final_rate,
            "components": {
                "市場基準利率": base,
                "信用評分溢酬": credit_premium,
                "負債比加成": dbr_surcharge,
                "預期損失成本(PD×LGD)": expected_loss,
                "資金成本": funding_cost,
                "目標利差": target_spread,
                "期限溢酬": maturity_premium,
                "規模折扣": size_discount,
                "產業溢酬": industry_prem,
                "市場競爭調整": competitive_adj,
                "客戶關係折扣": relationship_adj,
                "信保擔保折扣": guarantee_adj,
                "ML模型微調": ml_adj,
            },
        }


# ═══════════════════════════════════════════════════════════════
# 輔助函式
# ═══════════════════════════════════════════════════════════════

def classify_risk_grade(pd_score: float) -> int:
    for grade, info in RISK_GRADES.items():
        if pd_score < info["pd_max"]:
            return grade
    return 8


def check_rule_gate(data: dict):
    rules = [
        ("最低年營收 NT$1,000,000", data["annual_revenue_ntd"] >= 1_000_000,
         f"NT$ {data['annual_revenue_ntd']:,.0f}", "NT$ 1,000,000"),
        ("最低信用分數 400", data["credit_score"] >= 400,
         str(data["credit_score"]), "400"),
        ("最低營業年數 1年", data["years_in_business"] >= 1,
         f"{data['years_in_business']} 年", "1 年"),
        ("DBR不得超過500%", data["dbr"] <= 5.0,
         f"{data['dbr']*100:.1f}%", "500%"),
        ("擔保覆蓋率不得低於50%", data["collateral_coverage"] >= 0.5,
         f"{data['collateral_coverage']*100:.1f}%", "50%"),
    ]
    failed = [{"rule": n, "actual": a, "required": r}
              for n, passed, a, r in rules if not passed]
    return len(failed) == 0, failed


def calculate_monthly_payment(loan_amount: float, annual_rate: float, tenor_months: int) -> float:
    monthly_rate = annual_rate / 12
    if monthly_rate == 0:
        return loan_amount / tenor_months
    return (loan_amount * monthly_rate * (1 + monthly_rate) ** tenor_months
            / ((1 + monthly_rate) ** tenor_months - 1))


def predict_pd(features: dict):
    global MODEL, SCALER, FEATURE_NAMES
    cs = features.get("credit_score", 600)
    simple_pd = max(0.001, min(0.5, (800 - cs) / 800 * 0.15))

    if MODEL is None or SCALER is None or FEATURE_NAMES is None:
        return simple_pd, 0.0, False

    try:
        row = {name: features.get(name, 0.0) for name in FEATURE_NAMES}
        X = pd.DataFrame([row])[FEATURE_NAMES].fillna(0)
        X_scaled = SCALER.transform(X)
        pd_raw = float(MODEL.predict_proba(X_scaled)[:, 1][0])
        pd_calibrated = max(0.0001, min(pd_raw * (0.02 / 0.16), 0.9999))
        ml_adj = (pd_calibrated - simple_pd) * 0.1
        return pd_calibrated, ml_adj, True
    except Exception as e:
        logger.error(f"ML推論失敗：{e}")
        return simple_pd, 0.0, False


# ═══════════════════════════════════════════════════════════════
# API Routes
# ═══════════════════════════════════════════════════════════════

@app.get("/", tags=["Health"])
async def root():
    return {
        "status": "ok",
        "service": "永豐金控 SME利率試算API",
        "version": "1.1.0",
        "model_loaded": MODEL is not None,
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "model_loaded": MODEL is not None,
        "taiwan_base_rate": f"{TAIWAN_REDISCOUNT_RATE*100:.3f}%",
        "cors_origins": ALLOWED_ORIGINS,
    }


@app.options("/predict", tags=["CORS"])
async def predict_options():
    """顯式處理 CORS preflight OPTIONS 請求"""
    return JSONResponse(content={}, status_code=200)


@app.post("/predict", response_model=PredictionResponse, tags=["Prediction"])
async def predict_interest_rate(application: LoanApplication, request: Request):
    """主要預測端點"""

    # 記錄請求來源（方便 Debug）
    origin = request.headers.get("origin", "unknown")
    logger.info(f"POST /predict from origin: {origin}")

    # 衍生指標
    dbr = application.loan_amount_ntd / max(application.annual_revenue_ntd, 1)
    collateral_coverage = application.collateral_value_ntd / max(application.loan_amount_ntd, 1)

    # 規則閘門
    is_eligible, failed_rules = check_rule_gate({
        "annual_revenue_ntd": application.annual_revenue_ntd,
        "credit_score": application.credit_score,
        "years_in_business": application.years_in_business,
        "dbr": dbr,
        "collateral_coverage": collateral_coverage,
    })

    if not is_eligible:
        return PredictionResponse(
            final_rate=0.0, final_rate_pct="N/A",
            pd_score=0.0, pd_score_pct="N/A",
            risk_grade=8, risk_grade_name="損失", risk_color="#ac2925",
            components=[], monthly_payment=0.0, total_payment=0.0, total_interest=0.0,
            approval_decision="拒絕", approval_authority="N/A",
            approval_conditions="未通過基本准入條件",
            market_benchmark_rate=0.0, rate_vs_market=0.0,
            is_eligible=False, failed_rules=failed_rules,
            ml_model_used=False, message="申請案未通過基本准入規則",
        )

    # ML 預測 PD
    ml_features = {
        "annual_revenue_ntd":     application.annual_revenue_ntd,
        "revenue_per_employee":   application.annual_revenue_ntd / max(application.num_employees, 1),
        "years_in_business":      application.years_in_business,
        "num_employees":          application.num_employees,
        "business_growth_proxy":  dbr,
        "credit_score":           application.credit_score,
        "owner_experience_years": application.years_in_business,
        "business_sector_risk":   {"manufacturing":0.15,"retail_trade":0.20,"services":0.25,
                                    "agriculture":0.30,"construction":0.28,"technology":0.22,
                                    "other":0.25}.get(application.business_sector, 0.25),
        "loan_amount_ntd":        application.loan_amount_ntd,
        "debt_to_revenue_ratio":  dbr,
        "collateral_coverage":    collateral_coverage,
        "tenor_months":           application.tenor_months,
        "existing_debt_proxy":    0.08,
    }
    pd_score, ml_adj, ml_used = predict_pd(ml_features)

    # 定價
    pricer = RiskBasedPricingLayer()
    pricing = pricer.calculate(
        pd_score=pd_score, credit_score=application.credit_score,
        dbr=dbr, loan_amount_ntd=application.loan_amount_ntd,
        tenor_months=application.tenor_months, industry=application.business_sector,
        collateral_coverage=collateral_coverage,
        is_existing_customer=application.is_existing_customer,
        has_credit_guarantee=application.has_credit_guarantee,
        ml_adjustment=ml_adj,
    )

    final_rate = pricing["final_rate"]
    risk_grade = classify_risk_grade(pd_score)
    grade_info = RISK_GRADES[risk_grade]
    approval = APPROVAL_MATRIX[risk_grade]

    monthly_payment = calculate_monthly_payment(application.loan_amount_ntd, final_rate, application.tenor_months)
    total_payment = monthly_payment * application.tenor_months
    total_interest = total_payment - application.loan_amount_ntd

    components_list = [
        {"name": k, "rate": v, "rate_pct": f"{v*100:+.2f}%"}
        for k, v in pricing["components"].items()
    ]

    logger.info(f"Prediction: rate={final_rate:.4f}, grade={risk_grade}, ml={ml_used}")

    return PredictionResponse(
        final_rate=round(final_rate, 6),
        final_rate_pct=f"{final_rate*100:.2f}%",
        pd_score=round(pd_score, 6),
        pd_score_pct=f"{pd_score*100:.2f}%",
        risk_grade=risk_grade,
        risk_grade_name=grade_info["name"],
        risk_color=grade_info["color"],
        components=components_list,
        monthly_payment=round(monthly_payment, 0),
        total_payment=round(total_payment, 0),
        total_interest=round(total_interest, 0),
        approval_decision=approval["decision"],
        approval_authority=approval["authority"],
        approval_conditions=approval["conditions"],
        market_benchmark_rate=grade_info["market_rate"],
        rate_vs_market=round(final_rate - grade_info["market_rate"], 6),
        is_eligible=True,
        failed_rules=[],
        ml_model_used=ml_used,
        message="評估完成",
    )
