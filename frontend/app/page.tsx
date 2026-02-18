"use client";

import { useState, useEffect } from "react";

// ── Type definitions
interface RateComponent {
  name: string;
  rate: number;
  rate_pct: string;
}

interface FailedRule {
  rule: string;
  actual: string;
  required: string;
}

interface PredictionResult {
  final_rate: number;
  final_rate_pct: string;
  pd_score: number;
  pd_score_pct: string;
  risk_grade: number;
  risk_grade_name: string;
  risk_color: string;
  components: RateComponent[];
  monthly_payment: number;
  total_payment: number;
  total_interest: number;
  approval_decision: string;
  approval_authority: string;
  approval_conditions: string;
  market_benchmark_rate: number;
  rate_vs_market: number;
  is_eligible: boolean;
  failed_rules: FailedRule[];
  ml_model_used: boolean;
  message: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const formatNTD = (v: number) =>
  new Intl.NumberFormat("zh-TW", {
    style: "currency",
    currency: "TWD",
    maximumFractionDigits: 0,
  }).format(v);

const formatNTDShort = (v: number) => {
  if (v >= 100_000_000) return `NT$ ${(v / 100_000_000).toFixed(1)} 億`;
  if (v >= 10_000) return `NT$ ${(v / 10_000).toFixed(0)} 萬`;
  return formatNTD(v);
};

const NAV_ITEMS = [
  { id: "home",     label: "首頁",   icon: HomeIcon },
  { id: "transfer", label: "轉帳",   icon: TransferIcon },
  { id: "invest",   label: "投資",   icon: InvestIcon },
  { id: "service",  label: "客服",   icon: ServiceIcon },
];

export default function HomePage() {
  const [activeNav, setActiveNav] = useState("home");
  const [mounted, setMounted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showComponents, setShowComponents] = useState(false);

  const [form, setForm] = useState({
    annual_revenue_ntd: 5_000_000,
    years_in_business: 5,
    num_employees: 20,
    business_sector: "manufacturing",
    credit_score: 680,
    loan_amount_ntd: 2_000_000,
    tenor_months: 36,
    collateral_value_ntd: 2_500_000,
    is_existing_customer: false,
    has_credit_guarantee: false,
  });

  useEffect(() => { setMounted(true); }, []);

  const dbr = (form.loan_amount_ntd / Math.max(form.annual_revenue_ntd, 1)) * 100;
  const ccr = (form.collateral_value_ntd / Math.max(form.loan_amount_ntd, 1)) * 100;

  const update = (key: string, value: unknown) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`${API_URL}/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d?.detail ?? `HTTP ${res.status}`);
      }
      setResult(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "連線失敗");
    } finally {
      setLoading(false);
    }
  };

  if (!mounted) return null;

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;600;700&family=DM+Serif+Display:ital@0;1&family=Roboto+Mono:wght@400;500;600&display=swap');

        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        :root {
          --red:       #C8102E;
          --red-deep:  #9B0D22;
          --red-light: #E8354F;
          --red-pale:  #FFF0F2;
          --black:     #111111;
          --charcoal:  #2A2A2A;
          --slate:     #4A4A4A;
          --mid:       #8A8A8A;
          --silver:    #C4C4C4;
          --smoke:     #F5F5F5;
          --white:     #FFFFFF;
          --success:   #1A7F37;
          --warn:      #B45309;
          --danger:    #C8102E;
        }

        html, body {
          height: 100%;
          background: #E8E8E8;
          font-family: 'Noto Sans TC', sans-serif;
          color: var(--black);
        }

        .page-shell {
          min-height: 100dvh;
          max-width: 480px;
          margin: 0 auto;
          background: var(--white);
          display: flex;
          flex-direction: column;
          position: relative;
          box-shadow: 0 0 60px rgba(0,0,0,0.15);
        }

        /* ── Header ─────────────────── */
        .site-header {
          background: var(--white);
          border-bottom: 1px solid #EBEBEB;
          padding: 0 20px;
          height: 64px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          position: sticky;
          top: 0;
          z-index: 100;
        }
        .logo-lockup {
          display: flex;
          align-items: center;
          gap: 11px;
        }
        .logo-mark {
          width: 40px; height: 40px;
          background: var(--red);
          border-radius: 10px;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          box-shadow: 0 2px 10px rgba(200,16,46,0.3);
        }
        .logo-text-block { line-height: 1; }
        .logo-zh {
          font-size: 17px;
          font-weight: 700;
          color: var(--black);
          letter-spacing: 0.3px;
        }
        .logo-en {
          font-size: 9px;
          font-weight: 400;
          color: var(--mid);
          letter-spacing: 2px;
          text-transform: uppercase;
          margin-top: 3px;
          display: block;
        }
        .header-right {
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .ai-badge {
          background: var(--red-pale);
          color: var(--red);
          font-size: 10px;
          font-weight: 700;
          padding: 4px 10px;
          border-radius: 20px;
          letter-spacing: 0.5px;
          border: 1px solid rgba(200,16,46,0.2);
        }
        .icon-btn {
          width: 36px; height: 36px;
          border-radius: 50%;
          border: 1px solid #EBEBEB;
          background: var(--smoke);
          display: flex; align-items: center; justify-content: center;
          cursor: pointer;
          color: var(--slate);
          transition: background 0.15s, border-color 0.15s;
        }
        .icon-btn:hover { background: #EBEBEB; border-color: #D0D0D0; }

        /* ── Hero ─────────────────── */
        .hero {
          background: var(--red);
          background: linear-gradient(150deg, #C8102E 0%, #7D0A1E 100%);
          padding: 26px 20px 32px;
          position: relative;
          overflow: hidden;
        }
        .hero-deco-1 {
          position: absolute;
          width: 200px; height: 200px;
          border-radius: 50%;
          border: 1px solid rgba(255,255,255,0.08);
          top: -60px; right: -60px;
        }
        .hero-deco-2 {
          position: absolute;
          width: 120px; height: 120px;
          border-radius: 50%;
          border: 1px solid rgba(255,255,255,0.06);
          bottom: -30px; left: 20px;
        }
        .hero-deco-3 {
          position: absolute;
          width: 60px; height: 60px;
          border-radius: 50%;
          background: rgba(255,255,255,0.05);
          top: 20px; right: 40px;
        }
        .hero-eyebrow {
          font-size: 10px;
          font-weight: 600;
          color: rgba(255,255,255,0.6);
          letter-spacing: 2.5px;
          text-transform: uppercase;
          margin-bottom: 10px;
          position: relative;
          z-index: 1;
        }
        .hero-title {
          font-family: 'DM Serif Display', serif;
          font-size: 30px;
          font-style: italic;
          color: white;
          line-height: 1.15;
          margin-bottom: 4px;
          position: relative;
          z-index: 1;
        }
        .hero-subtitle {
          font-size: 12px;
          color: rgba(255,255,255,0.65);
          margin-bottom: 24px;
          position: relative;
          z-index: 1;
        }
        .hero-metrics {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 10px;
          position: relative;
          z-index: 1;
        }
        .hero-metric-card {
          background: rgba(255,255,255,0.1);
          border: 1px solid rgba(255,255,255,0.15);
          border-radius: 12px;
          padding: 13px 15px;
          backdrop-filter: blur(4px);
        }
        .hm-label {
          font-size: 10px;
          color: rgba(255,255,255,0.55);
          margin-bottom: 6px;
          letter-spacing: 0.3px;
        }
        .hm-value {
          font-family: 'Roboto Mono', monospace;
          font-size: 20px;
          font-weight: 600;
          color: white;
          line-height: 1;
        }
        .hm-unit {
          font-size: 10px;
          color: rgba(255,255,255,0.5);
          margin-top: 4px;
        }

        /* ── Tabs ─────────────────── */
        .tabs {
          display: flex;
          background: white;
          border-bottom: 1px solid #EBEBEB;
          position: sticky;
          top: 64px;
          z-index: 90;
        }
        .tab {
          flex: 1;
          padding: 13px 6px;
          border: none; background: none;
          font-family: 'Noto Sans TC', sans-serif;
          font-size: 13px; font-weight: 500;
          color: var(--silver);
          cursor: pointer;
          border-bottom: 2.5px solid transparent;
          transition: color 0.15s, border-color 0.15s;
          letter-spacing: 0.3px;
        }
        .tab.active {
          color: var(--red);
          border-bottom-color: var(--red);
          font-weight: 700;
        }

        /* ── Content ─────────────────── */
        .content {
          flex: 1;
          padding: 18px 16px 100px;
          overflow-y: auto;
          background: #F8F8F8;
        }

        /* ── Cards ─────────────────── */
        .card {
          background: white;
          border: 1px solid #E8E8E8;
          border-radius: 14px;
          overflow: hidden;
          margin-bottom: 14px;
          box-shadow: 0 1px 4px rgba(0,0,0,0.04);
        }
        .card-head {
          padding: 14px 16px 12px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          border-bottom: 1px solid #F2F2F2;
        }
        .card-title {
          font-size: 11px;
          font-weight: 700;
          color: var(--mid);
          letter-spacing: 1.2px;
          text-transform: uppercase;
        }
        .card-pill {
          font-size: 10px;
          font-weight: 600;
          background: var(--smoke);
          color: var(--slate);
          padding: 3px 9px;
          border-radius: 20px;
          border: 1px solid #E0E0E0;
        }
        .card-body { padding: 16px; }

        /* ── Form ─────────────────── */
        .field { margin-bottom: 16px; }
        .field:last-child { margin-bottom: 0; }
        .field-label {
          display: block;
          font-size: 10px;
          font-weight: 700;
          color: var(--slate);
          letter-spacing: 1px;
          text-transform: uppercase;
          margin-bottom: 7px;
        }
        .field-input {
          width: 100%;
          padding: 11px 13px;
          border: 1.5px solid #E0E0E0;
          border-radius: 9px;
          font-family: 'Noto Sans TC', sans-serif;
          font-size: 15px;
          color: var(--black);
          background: white;
          transition: border-color 0.15s, box-shadow 0.15s;
          outline: none;
          -moz-appearance: textfield;
        }
        .field-input::-webkit-inner-spin-button,
        .field-input::-webkit-outer-spin-button { -webkit-appearance: none; }
        .field-input:focus {
          border-color: var(--red);
          box-shadow: 0 0 0 3px rgba(200,16,46,0.08);
        }
        select.field-input {
          appearance: none;
          background-image: url("data:image/svg+xml,%3Csvg width='10' height='6' viewBox='0 0 10 6' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1L5 5L9 1' stroke='%238A8A8A' stroke-width='1.5' stroke-linecap='round'/%3E%3C/svg%3E");
          background-repeat: no-repeat;
          background-position: right 13px center;
          padding-right: 34px;
          cursor: pointer;
        }
        .field-hint {
          font-size: 11px;
          color: var(--mid);
          margin-top: 5px;
          font-family: 'Roboto Mono', monospace;
        }
        .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }

        /* Slider */
        .score-display {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 10px;
        }
        .score-num {
          font-family: 'Roboto Mono', monospace;
          font-size: 28px;
          font-weight: 600;
          color: var(--black);
        }
        .score-label-badge {
          font-size: 12px;
          font-weight: 700;
          padding: 4px 12px;
          border-radius: 20px;
        }
        input[type=range] {
          -webkit-appearance: none;
          width: 100%;
          height: 5px;
          border-radius: 3px;
          outline: none;
          cursor: pointer;
        }
        input[type=range]::-webkit-slider-thumb {
          -webkit-appearance: none;
          width: 22px; height: 22px;
          border-radius: 50%;
          background: white;
          cursor: pointer;
          box-shadow: 0 2px 8px rgba(0,0,0,0.2), 0 0 0 2px var(--red);
        }
        .range-ends {
          display: flex;
          justify-content: space-between;
          margin-top: 6px;
          font-size: 10px;
          color: var(--silver);
        }

        /* Tenor chips */
        .tenor-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 7px;
        }
        .tenor-chip {
          padding: 10px 4px;
          border: 1.5px solid #E0E0E0;
          border-radius: 9px;
          background: white;
          font-family: 'Noto Sans TC', sans-serif;
          font-size: 12px;
          font-weight: 600;
          color: var(--slate);
          cursor: pointer;
          text-align: center;
          transition: all 0.15s;
        }
        .tenor-chip.sel {
          background: var(--red);
          color: white;
          border-color: var(--red);
          box-shadow: 0 3px 8px rgba(200,16,46,0.3);
        }
        .tenor-chip:hover:not(.sel) {
          border-color: var(--red);
          color: var(--red);
        }

        /* DBR/CCR metrics */
        .metric-duo {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 10px;
          margin-top: 16px;
        }
        .metric-duo-item {
          background: var(--smoke);
          border-radius: 10px;
          padding: 12px;
          text-align: center;
          border: 1px solid #EBEBEB;
        }
        .mdi-label {
          font-size: 9px;
          font-weight: 700;
          color: var(--mid);
          letter-spacing: 1px;
          text-transform: uppercase;
          margin-bottom: 6px;
        }
        .mdi-val {
          font-family: 'Roboto Mono', monospace;
          font-size: 22px;
          font-weight: 700;
          line-height: 1;
        }
        .mdi-sub {
          font-size: 9px;
          color: var(--mid);
          margin-top: 3px;
        }

        /* Toggles */
        .toggle-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 13px 0;
          border-bottom: 1px solid #F4F4F4;
        }
        .toggle-row:last-child { border-bottom: none; padding-bottom: 0; }
        .toggle-text {}
        .toggle-name {
          font-size: 14px;
          font-weight: 500;
          color: var(--black);
        }
        .toggle-desc {
          font-size: 11px;
          color: var(--mid);
          margin-top: 2px;
        }
        .pill-switch {
          width: 46px; height: 26px;
          border-radius: 13px;
          border: none;
          cursor: pointer;
          position: relative;
          transition: background 0.2s;
          flex-shrink: 0;
        }
        .pill-switch::after {
          content: '';
          position: absolute;
          top: 3px; left: 3px;
          width: 20px; height: 20px;
          border-radius: 50%;
          background: white;
          box-shadow: 0 1px 4px rgba(0,0,0,0.2);
          transition: transform 0.22s cubic-bezier(.4,0,.2,1);
        }
        .pill-switch.on { background: var(--red); }
        .pill-switch.on::after { transform: translateX(20px); }
        .pill-switch.off { background: #D4D4D4; }

        /* Submit */
        .submit-btn {
          width: 100%;
          padding: 16px;
          background: var(--red);
          color: white;
          border: none;
          border-radius: 12px;
          font-family: 'Noto Sans TC', sans-serif;
          font-size: 16px;
          font-weight: 700;
          cursor: pointer;
          letter-spacing: 0.5px;
          transition: background 0.2s, box-shadow 0.2s, transform 0.1s;
          box-shadow: 0 4px 16px rgba(200,16,46,0.35);
          position: relative;
          overflow: hidden;
        }
        .submit-btn:hover:not(:disabled) {
          background: var(--red-deep);
          box-shadow: 0 6px 20px rgba(200,16,46,0.4);
          transform: translateY(-1px);
        }
        .submit-btn:active:not(:disabled) { transform: translateY(0); }
        .submit-btn:disabled {
          background: var(--silver);
          box-shadow: none;
          cursor: not-allowed;
          transform: none;
        }
        .spin {
          display: inline-block;
          width: 16px; height: 16px;
          border: 2.5px solid rgba(255,255,255,0.3);
          border-top-color: white;
          border-radius: 50%;
          animation: spin 0.75s linear infinite;
          vertical-align: middle;
          margin-right: 8px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        .error-msg {
          margin-top: 12px;
          padding: 13px 15px;
          background: var(--red-pale);
          border: 1px solid rgba(200,16,46,0.2);
          border-radius: 9px;
          font-size: 13px;
          color: var(--red);
        }

        /* ── Results ─────────────────── */
        .result-wrap { margin-top: 24px; }

        .rate-hero-card {
          background: linear-gradient(150deg, #C8102E 0%, #7D0A1E 100%);
          border-radius: 14px;
          padding: 26px 20px;
          margin-bottom: 12px;
          text-align: center;
          position: relative;
          overflow: hidden;
        }
        .rate-hero-card::before {
          content: '';
          position: absolute;
          top: -50px; right: -50px;
          width: 160px; height: 160px;
          border-radius: 50%;
          background: rgba(255,255,255,0.06);
        }
        .rate-hero-card::after {
          content: '';
          position: absolute;
          bottom: -40px; left: -20px;
          width: 120px; height: 120px;
          border-radius: 50%;
          background: rgba(255,255,255,0.04);
        }
        .rate-eyebrow {
          font-size: 10px;
          font-weight: 600;
          color: rgba(255,255,255,0.6);
          letter-spacing: 2px;
          text-transform: uppercase;
          margin-bottom: 14px;
          position: relative;
          z-index: 1;
        }
        .rate-number {
          font-family: 'DM Serif Display', serif;
          font-size: 68px;
          color: white;
          line-height: 0.9;
          margin-bottom: 16px;
          position: relative;
          z-index: 1;
        }
        .grade-chip {
          display: inline-flex;
          align-items: center;
          gap: 7px;
          background: rgba(255,255,255,0.14);
          border: 1px solid rgba(255,255,255,0.22);
          border-radius: 22px;
          padding: 7px 16px;
          color: white;
          font-size: 13px;
          font-weight: 600;
          position: relative;
          z-index: 1;
        }
        .grade-dot {
          width: 8px; height: 8px;
          border-radius: 50%;
          background: white;
          flex-shrink: 0;
        }
        .ai-tag {
          font-size: 9px;
          background: rgba(255,255,255,0.2);
          padding: 2px 7px;
          border-radius: 10px;
          letter-spacing: 0.5px;
        }

        .stats-row {
          display: grid;
          grid-template-columns: 1fr 1fr 1fr;
          gap: 9px;
          margin-bottom: 12px;
        }
        .stat-box {
          background: white;
          border: 1px solid #E8E8E8;
          border-radius: 11px;
          padding: 13px 10px;
          text-align: center;
          box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }
        .stat-box-label {
          font-size: 9px;
          font-weight: 700;
          color: var(--mid);
          letter-spacing: 0.5px;
          text-transform: uppercase;
          margin-bottom: 6px;
        }
        .stat-box-val {
          font-family: 'Roboto Mono', monospace;
          font-size: 15px;
          font-weight: 700;
          color: var(--black);
          line-height: 1;
        }
        .stat-box-sub {
          font-size: 9px;
          color: var(--mid);
          margin-top: 4px;
        }

        /* Approval */
        .approval-block {
          background: white;
          border: 1px solid #E8E8E8;
          border-radius: 14px;
          overflow: hidden;
          margin-bottom: 12px;
          box-shadow: 0 1px 4px rgba(0,0,0,0.04);
        }
        .approval-head {
          background: var(--smoke);
          padding: 12px 16px;
          border-bottom: 1px solid #EBEBEB;
          font-size: 10px;
          font-weight: 700;
          color: var(--mid);
          letter-spacing: 1.2px;
          text-transform: uppercase;
        }
        .approval-content { padding: 16px; }
        .approval-decision-text {
          font-size: 19px;
          font-weight: 700;
          color: var(--black);
          margin-bottom: 12px;
        }
        .approval-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 10px;
        }
        .ag-label {
          font-size: 9px;
          font-weight: 700;
          color: var(--mid);
          letter-spacing: 0.8px;
          text-transform: uppercase;
          margin-bottom: 4px;
        }
        .ag-val {
          font-size: 13px;
          font-weight: 600;
          color: var(--charcoal);
        }

        /* Repayment */
        .repay-item {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 13px 0;
          border-bottom: 1px solid #F4F4F4;
        }
        .repay-item:last-child { border-bottom: none; padding-bottom: 0; }
        .repay-lbl { font-size: 13px; color: var(--slate); }
        .repay-val {
          font-family: 'Roboto Mono', monospace;
          font-size: 15px;
          font-weight: 700;
          color: var(--black);
        }
        .repay-val.primary { color: var(--red); font-size: 18px; }

        /* Components */
        .comp-toggle {
          width: 100%;
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 13px 15px;
          background: white;
          border: 1px solid #E8E8E8;
          border-radius: 11px;
          cursor: pointer;
          font-family: 'Noto Sans TC', sans-serif;
          font-size: 13px;
          font-weight: 600;
          color: var(--slate);
          margin-bottom: 8px;
          transition: background 0.15s;
          box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }
        .comp-toggle:hover { background: #FAFAFA; }
        .comp-list-inner { margin-bottom: 12px; }
        .comp-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 10px 12px;
          border-radius: 8px;
          transition: background 0.1s;
        }
        .comp-row:hover { background: #F8F8F8; }
        .comp-name { font-size: 13px; color: var(--slate); }
        .comp-pct {
          font-family: 'Roboto Mono', monospace;
          font-size: 13px;
          font-weight: 600;
        }
        .comp-pct.plus { color: var(--black); }
        .comp-pct.minus { color: var(--success); }
        .comp-total {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 13px 14px;
          background: var(--red-pale);
          border-radius: 10px;
          border: 1px solid rgba(200,16,46,0.12);
        }
        .comp-total-lbl {
          font-size: 14px;
          font-weight: 700;
          color: var(--red);
        }
        .comp-total-val {
          font-family: 'Roboto Mono', monospace;
          font-size: 17px;
          font-weight: 800;
          color: var(--red);
        }

        /* Rejected */
        .rejected-wrap {
          background: var(--red-pale);
          border: 1.5px solid rgba(200,16,46,0.2);
          border-radius: 14px;
          padding: 22px 18px;
          margin-bottom: 12px;
        }
        .rejected-title {
          font-size: 17px;
          font-weight: 700;
          color: var(--red);
          margin-bottom: 14px;
        }
        .fail-item {
          background: white;
          border: 1px solid rgba(200,16,46,0.1);
          border-radius: 9px;
          padding: 11px 13px;
          margin-bottom: 8px;
        }
        .fail-name {
          font-size: 13px;
          font-weight: 700;
          color: var(--black);
          margin-bottom: 4px;
        }
        .fail-detail {
          font-size: 11px;
          color: var(--mid);
        }

        /* Disclaimer */
        .disclaimer {
          font-size: 11px;
          color: var(--silver);
          text-align: center;
          line-height: 1.65;
          padding: 10px 0 0;
        }

        /* Empty */
        .empty {
          padding: 60px 20px;
          text-align: center;
        }
        .empty-icon { font-size: 44px; margin-bottom: 16px; }
        .empty-ttl {
          font-size: 18px;
          font-weight: 600;
          color: var(--charcoal);
          margin-bottom: 8px;
        }
        .empty-desc {
          font-size: 13px;
          color: var(--mid);
          line-height: 1.6;
        }

        /* ── Bottom nav ─────────────────── */
        .bottom-nav {
          position: sticky;
          bottom: 0;
          background: white;
          border-top: 1px solid #E8E8E8;
          display: flex;
          z-index: 100;
          padding-bottom: env(safe-area-inset-bottom, 0);
        }
        .nav-btn {
          flex: 1;
          padding: 10px 4px 12px;
          border: none;
          background: none;
          cursor: pointer;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 4px;
          transition: all 0.15s;
          font-family: 'Noto Sans TC', sans-serif;
        }
        .nav-icon {
          width: 28px; height: 28px;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 8px;
          transition: background 0.15s;
        }
        .nav-btn.active .nav-icon { background: var(--red-pale); }
        .nav-btn svg { width: 20px; height: 20px; }
        .nav-btn.active svg { color: var(--red); }
        .nav-btn:not(.active) svg { color: var(--silver); }
        .nav-lbl {
          font-size: 10px;
          font-weight: 600;
          letter-spacing: 0.2px;
        }
        .nav-btn.active .nav-lbl { color: var(--red); }
        .nav-btn:not(.active) .nav-lbl { color: var(--silver); }

        /* Animations */
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(14px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .anim { animation: fadeUp 0.3s ease both; }
        .d1 { animation-delay: 0.05s; }
        .d2 { animation-delay: 0.1s; }
        .d3 { animation-delay: 0.15s; }
        .d4 { animation-delay: 0.2s; }
      `}</style>

      <div className="page-shell">

        {/* ════ HEADER ════ */}
        <header className="site-header">
          <div className="logo-lockup">
            <div className="logo-mark">
              <SinopacLogo />
            </div>
            <div className="logo-text-block">
              <span className="logo-zh">永豐銀行</span>
              <span className="logo-en">SinoPac Bank</span>
            </div>
          </div>
          <div className="header-right">
            <span className="ai-badge">AI 試算版</span>
            <button className="icon-btn" aria-label="通知"><BellIcon /></button>
          </div>
        </header>

        {/* ════ HERO ════ */}
        <section className="hero">
          <div className="hero-deco-1" />
          <div className="hero-deco-2" />
          <div className="hero-deco-3" />
          <div className="hero-eyebrow">中小企業專屬服務</div>
          <div className="hero-title">法金貸款<br />利率智慧試算</div>
          <div className="hero-subtitle">AI 模型 × 台灣市場基準，即時精準定價</div>
          <div className="hero-metrics">
            <div className="hero-metric-card">
              <div className="hm-label">台灣央行重貼現率</div>
              <div className="hm-value">1.875<span style={{ fontSize: 13 }}>%</span></div>
              <div className="hm-unit">2025 年基準</div>
            </div>
            <div className="hero-metric-card">
              <div className="hm-label">中小企業貸款區間</div>
              <div className="hm-value">2.5<span style={{ fontSize: 12, opacity: 0.6 }}>% ~ 12%</span></div>
              <div className="hm-unit">年利率參考範圍</div>
            </div>
          </div>
        </section>

        {/* ════ TABS ════ */}
        <div className="tabs">
          <button className="tab active">申請試算</button>
          <button className="tab">貸款紀錄</button>
          <button className="tab">還款計畫</button>
        </div>

        {/* ════ CONTENT ════ */}
        <div className="content">

          {/* ── Card 1：企業資料 */}
          <div className="card anim d1">
            <div className="card-head">
              <span className="card-title">企業基本資料</span>
              <span className="card-pill">必填</span>
            </div>
            <div className="card-body">
              <div className="field">
                <label className="field-label">年營收（新台幣）</label>
                <input type="number" className="field-input"
                  value={form.annual_revenue_ntd} step={100000} min={0}
                  onChange={(e) => update("annual_revenue_ntd", +e.target.value)} />
                <div className="field-hint">{formatNTDShort(form.annual_revenue_ntd)}</div>
              </div>
              <div className="two-col">
                <div className="field" style={{ marginBottom: 0 }}>
                  <label className="field-label">營業年數</label>
                  <input type="number" className="field-input"
                    value={form.years_in_business} min={1} max={100} step={1}
                    onChange={(e) => update("years_in_business", +e.target.value)} />
                </div>
                <div className="field" style={{ marginBottom: 0 }}>
                  <label className="field-label">員工人數</label>
                  <input type="number" className="field-input"
                    value={form.num_employees} min={1} step={1}
                    onChange={(e) => update("num_employees", +e.target.value)} />
                </div>
              </div>
              <div className="field" style={{ marginTop: 16 }}>
                <label className="field-label">產業別</label>
                <select className="field-input"
                  value={form.business_sector}
                  onChange={(e) => update("business_sector", e.target.value)}>
                  <option value="manufacturing">製造業</option>
                  <option value="technology">科技業</option>
                  <option value="services">服務業</option>
                  <option value="retail_trade">零售業</option>
                  <option value="construction">營建業</option>
                  <option value="agriculture">農業</option>
                  <option value="other">其他</option>
                </select>
              </div>
            </div>
          </div>

          {/* ── Card 2：信用評分 */}
          <div className="card anim d2">
            <div className="card-head">
              <span className="card-title">負責人信用資料</span>
              <span className="card-pill">必填</span>
            </div>
            <div className="card-body">
              <div className="score-display">
                <div className="score-num">{form.credit_score}</div>
                <span className="score-label-badge" style={{
                  background: creditScoreBg(form.credit_score),
                  color: creditScoreColor(form.credit_score),
                }}>
                  {creditScoreLabel(form.credit_score)}
                </span>
              </div>
              <input type="range" min={300} max={850}
                value={form.credit_score}
                style={{
                  background: `linear-gradient(to right, ${creditScoreColor(form.credit_score)} ${((form.credit_score - 300) / 550) * 100}%, #E4E4E4 ${((form.credit_score - 300) / 550) * 100}%)`
                }}
                onChange={(e) => update("credit_score", +e.target.value)} />
              <div className="range-ends">
                <span>300 偏低風險</span>
                <span>850 優質信用</span>
              </div>
            </div>
          </div>

          {/* ── Card 3：貸款條件 */}
          <div className="card anim d3">
            <div className="card-head">
              <span className="card-title">貸款條件</span>
              <span className="card-pill">必填</span>
            </div>
            <div className="card-body">
              <div className="field">
                <label className="field-label">貸款金額（新台幣）</label>
                <input type="number" className="field-input"
                  value={form.loan_amount_ntd} step={100000} min={0} max={50000000}
                  onChange={(e) => update("loan_amount_ntd", +e.target.value)} />
                <div className="field-hint">{formatNTDShort(form.loan_amount_ntd)}｜上限 NT$5,000 萬</div>
              </div>
              <div className="field">
                <label className="field-label">貸款期限</label>
                <div className="tenor-grid">
                  {[12, 24, 36, 48, 60, 72, 84].map((m) => (
                    <button key={m}
                      className={`tenor-chip${form.tenor_months === m ? " sel" : ""}`}
                      onClick={() => update("tenor_months", m)}>
                      {m}月
                    </button>
                  ))}
                </div>
              </div>
              <div className="field">
                <label className="field-label">擔保品價值（新台幣）</label>
                <input type="number" className="field-input"
                  value={form.collateral_value_ntd} step={100000} min={0}
                  onChange={(e) => update("collateral_value_ntd", +e.target.value)} />
                <div className="field-hint">{formatNTDShort(form.collateral_value_ntd)}</div>
              </div>
              <div className="metric-duo">
                <div className="metric-duo-item">
                  <div className="mdi-label">負債營收比 DBR</div>
                  <div className="mdi-val" style={{ color: dbr > 200 ? "var(--danger)" : dbr > 100 ? "var(--warn)" : "var(--success)" }}>
                    {dbr.toFixed(1)}<span style={{ fontSize: 12, fontWeight: 500 }}>%</span>
                  </div>
                  <div className="mdi-sub">{dbr > 200 ? "過高" : dbr > 100 ? "偏高" : "良好"}</div>
                </div>
                <div className="metric-duo-item">
                  <div className="mdi-label">擔保覆蓋率 CCR</div>
                  <div className="mdi-val" style={{ color: ccr < 50 ? "var(--danger)" : ccr < 100 ? "var(--warn)" : "var(--success)" }}>
                    {ccr.toFixed(1)}<span style={{ fontSize: 12, fontWeight: 500 }}>%</span>
                  </div>
                  <div className="mdi-sub">{ccr < 50 ? "不足" : ccr < 100 ? "待加強" : "充足"}</div>
                </div>
              </div>
            </div>
          </div>

          {/* ── Card 4：加值選項 */}
          <div className="card anim d4">
            <div className="card-head">
              <span className="card-title">加值選項</span>
              <span className="card-pill" style={{ color: "var(--success)", borderColor: "rgba(26,127,55,0.2)", background: "#F0FFF4" }}>可降低利率</span>
            </div>
            <div className="card-body">
              <div className="toggle-row">
                <div className="toggle-text">
                  <div className="toggle-name">永豐既有客戶</div>
                  <div className="toggle-desc">享有關係折扣 −0.30%</div>
                </div>
                <button className={`pill-switch ${form.is_existing_customer ? "on" : "off"}`}
                  onClick={() => update("is_existing_customer", !form.is_existing_customer)}
                  aria-label="既有客戶" />
              </div>
              <div className="toggle-row">
                <div className="toggle-text">
                  <div className="toggle-name">中小企業信保基金擔保</div>
                  <div className="toggle-desc">享有信保折扣 −0.25%</div>
                </div>
                <button className={`pill-switch ${form.has_credit_guarantee ? "on" : "off"}`}
                  onClick={() => update("has_credit_guarantee", !form.has_credit_guarantee)}
                  aria-label="信保基金" />
              </div>
            </div>
          </div>

          {/* ── Submit */}
          <button className="submit-btn" onClick={handleSubmit} disabled={loading}>
            {loading ? <><span className="spin" />AI 風險評估中...</> : "立即試算貸款利率"}
          </button>

          {error && (
            <div className="error-msg">
              ⚠ {error}<br />
              <span style={{ fontSize: 11, opacity: 0.75 }}>確認後端已啟動：{API_URL}</span>
            </div>
          )}

          {/* ════ RESULTS ════ */}
          {result && (
            <div className="result-wrap">
              {!result.is_eligible ? (
                <div className="rejected-wrap anim">
                  <div className="rejected-title">⛔ 未通過基本准入條件</div>
                  {result.failed_rules.map((r, i) => (
                    <div key={i} className="fail-item">
                      <div className="fail-name">{r.rule}</div>
                      <div className="fail-detail">要求：{r.required}｜實際：{r.actual}</div>
                    </div>
                  ))}
                  <div style={{ fontSize: 12, color: "var(--mid)", marginTop: 12 }}>
                    請修正條件後重新申請，或洽詢永豐企業金融顧問
                  </div>
                </div>
              ) : (
                <>
                  {/* Rate hero */}
                  <div className="rate-hero-card anim">
                    <div className="rate-eyebrow">AI 建議貸款年利率</div>
                    <div className="rate-number">{result.final_rate_pct}</div>
                    <div className="grade-chip">
                      <span className="grade-dot" style={{ background: result.risk_color }} />
                      風險等級 {result.risk_grade}｜{result.risk_grade_name}
                      {result.ml_model_used && <span className="ai-tag">AI</span>}
                    </div>
                  </div>

                  {/* Stats */}
                  <div className="stats-row anim">
                    <div className="stat-box">
                      <div className="stat-box-label">違約機率 PD</div>
                      <div className="stat-box-val">{result.pd_score_pct}</div>
                      <div className="stat-box-sub">校準後</div>
                    </div>
                    <div className="stat-box">
                      <div className="stat-box-label">市場基準</div>
                      <div className="stat-box-val">{(result.market_benchmark_rate * 100).toFixed(2)}%</div>
                      <div className="stat-box-sub">同等級均值</div>
                    </div>
                    <div className="stat-box">
                      <div className="stat-box-label">利差</div>
                      <div className="stat-box-val" style={{ color: result.rate_vs_market > 0 ? "var(--danger)" : "var(--success)" }}>
                        {result.rate_vs_market >= 0 ? "+" : ""}{(result.rate_vs_market * 100).toFixed(2)}%
                      </div>
                      <div className="stat-box-sub">{result.rate_vs_market > 0 ? "高於市場" : "低於市場"}</div>
                    </div>
                  </div>

                  {/* Approval */}
                  <div className="approval-block anim">
                    <div className="approval-head">審批建議</div>
                    <div className="approval-content">
                      <div className="approval-decision-text">{result.approval_decision}</div>
                      <div className="approval-grid">
                        <div>
                          <div className="ag-label">核准層級</div>
                          <div className="ag-val">{result.approval_authority}</div>
                        </div>
                        <div>
                          <div className="ag-label">附加條件</div>
                          <div className="ag-val">{result.approval_conditions}</div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Repayment */}
                  <div className="card anim">
                    <div className="card-head">
                      <span className="card-title">還款試算</span>
                      <span className="card-pill">本息平均攤還</span>
                    </div>
                    <div className="card-body">
                      <div className="repay-item">
                        <span className="repay-lbl">每月還款</span>
                        <span className="repay-val primary">{formatNTD(result.monthly_payment)}</span>
                      </div>
                      <div className="repay-item">
                        <span className="repay-lbl">總還款金額</span>
                        <span className="repay-val">{formatNTD(result.total_payment)}</span>
                      </div>
                      <div className="repay-item">
                        <span className="repay-lbl">總利息支出</span>
                        <span className="repay-val">{formatNTD(result.total_interest)}</span>
                      </div>
                    </div>
                  </div>

                  {/* Components */}
                  <button className="comp-toggle" onClick={() => setShowComponents(!showComponents)}>
                    <span>利率成分明細</span>
                    <span style={{ fontSize: 11, color: "var(--mid)" }}>{showComponents ? "▲ 收起" : "▼ 展開"}</span>
                  </button>
                  {showComponents && (
                    <div className="comp-list-inner anim">
                      {result.components.map((c, i) => (
                        <div key={i} className="comp-row">
                          <span className="comp-name">{c.name}</span>
                          <span className={`comp-pct ${c.rate < 0 ? "minus" : "plus"}`}>{c.rate_pct}</span>
                        </div>
                      ))}
                      <div className="comp-total">
                        <span className="comp-total-lbl">最終貸款年利率</span>
                        <span className="comp-total-val">{result.final_rate_pct}</span>
                      </div>
                    </div>
                  )}

                  <div className="disclaimer">
                    本試算結果僅供參考，不作為正式授信承諾。<br />
                    實際核准利率以永豐銀行正式審查結果為準。
                  </div>
                </>
              )}
            </div>
          )}

          {/* Empty state */}
          {!result && !loading && (
            <div className="empty">
              <div className="empty-icon">📋</div>
              <div className="empty-ttl">填寫表單開始試算</div>
              <div className="empty-desc">
                輸入企業與貸款資料後<br />點擊「立即試算」取得 AI 利率建議
              </div>
            </div>
          )}
        </div>

        {/* ════ BOTTOM NAV ════ */}
        <nav className="bottom-nav">
          {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
            <button key={id}
              className={`nav-btn ${activeNav === id ? "active" : ""}`}
              onClick={() => setActiveNav(id)}>
              <div className="nav-icon"><Icon /></div>
              <span className="nav-lbl">{label}</span>
            </button>
          ))}
        </nav>
      </div>
    </>
  );
}

// ── SVG Icons ────────────────────────────────────────────────
function SinopacLogo() {
  return (
    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" width="26" height="26">
      {/* Stylized 'S' representing SinoPac */}
      <path
        d="M10 13C10 10.791 11.791 9 14 9H27C28.657 9 30 10.343 30 12C30 13.657 28.657 15 27 15H14C11.791 15 10 16.791 10 19C10 21.209 11.791 23 14 23H26C28.209 23 30 24.791 30 27C30 29.209 28.209 31 26 31H13C11.343 31 10 29.657 10 28"
        stroke="white"
        strokeWidth="2.8"
        strokeLinecap="round"
      />
    </svg>
  );
}

function BellIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}

function HomeIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  );
}

function TransferIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="17 1 21 5 17 9" /><path d="M3 11V9a4 4 0 0 1 4-4h14" />
      <polyline points="7 23 3 19 7 15" /><path d="M21 13v2a4 4 0 0 1-4 4H3" />
    </svg>
  );
}

function InvestIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
      <polyline points="16 7 22 7 22 13" />
    </svg>
  );
}

function ServiceIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}

// ── Helpers ──────────────────────────────────────────────────
function creditScoreColor(s: number) {
  if (s >= 750) return "#1A7F37";
  if (s >= 700) return "#2D9F4E";
  if (s >= 650) return "#B45309";
  if (s >= 600) return "#C17A1A";
  return "#C8102E";
}
function creditScoreBg(s: number) {
  if (s >= 750) return "#F0FFF4";
  if (s >= 700) return "#F2FBF4";
  if (s >= 650) return "#FFFBEB";
  if (s >= 600) return "#FFF8E1";
  return "#FFF0F2";
}
function creditScoreLabel(s: number) {
  if (s >= 750) return "優質";
  if (s >= 700) return "良好";
  if (s >= 650) return "尚可";
  if (s >= 600) return "普通";
  if (s >= 550) return "偏低";
  return "低";
}
