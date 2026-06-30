from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, List

from dotenv import load_dotenv
from openai import OpenAI

import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

TRADING_DAYS = 252

app = FastAPI(title="AI Investment Risk Dashboard API", version="0.1.0")


def get_allowed_origins() -> List[str]:
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    frontend_url = os.getenv("FRONTEND_URL")
    if frontend_url:
        origins.append(frontend_url.rstrip("/"))

    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _clean_ticker(ticker: str) -> str:
    ticker = ticker.strip().upper()

    if not ticker or len(ticker) > 15:
        raise HTTPException(
            status_code=400,
            detail="Enter a valid ticker, e.g. AAPL, CBA.AX, VAS.AX, SPY",
        )

    return ticker


def _to_float(value: Any) -> float | None:
    if value is None:
        return None

    try:
        value = float(value)
    except Exception:
        return None

    if math.isnan(value) or math.isinf(value):
        return None

    return round(value, 6)


def download_prices(ticker: str, benchmark: str, period: str) -> pd.DataFrame:
    raw = yf.download(
        tickers=[ticker, benchmark],
        period=period,
        interval="1d",
        auto_adjust=True,
        progress=False,
        group_by="ticker",
        threads=True,
    )

    if raw.empty:
        raise HTTPException(
            status_code=404,
            detail="No price data found. Try another ticker or add .AX for ASX stocks.",
        )

    def close_for(symbol: str) -> pd.Series:
        try:
            if isinstance(raw.columns, pd.MultiIndex):
                return raw[symbol]["Close"].rename(symbol)

            return raw["Close"].rename(symbol)

        except Exception:
            raise HTTPException(
                status_code=404,
                detail=f"No close price found for {symbol}.",
            )

    prices = pd.concat([close_for(ticker), close_for(benchmark)], axis=1).dropna()
    prices = prices[~prices.index.duplicated(keep="last")]

    if len(prices) < 60:
        raise HTTPException(
            status_code=400,
            detail="Not enough data returned. Try a longer period.",
        )

    return prices


def calculate_metrics(
    prices: pd.DataFrame,
    ticker: str,
    benchmark: str,
    var_confidence: float,
    risk_free_rate: float,
) -> Dict[str, Any]:
    ticker_price = prices[ticker]
    benchmark_price = prices[benchmark]

    daily_returns = ticker_price.pct_change().dropna()
    benchmark_returns = benchmark_price.pct_change().dropna()

    aligned = pd.concat(
        [
            daily_returns.rename("asset"),
            benchmark_returns.rename("benchmark"),
        ],
        axis=1,
    ).dropna()

    total_return = ticker_price.iloc[-1] / ticker_price.iloc[0] - 1

    years = max(
        (ticker_price.index[-1] - ticker_price.index[0]).days / 365.25,
        1 / 365.25,
    )

    annualised_return = (1 + total_return) ** (1 / years) - 1
    volatility = daily_returns.std() * np.sqrt(TRADING_DAYS)

    sharpe = (
        (annualised_return - risk_free_rate) / volatility
        if volatility and volatility > 0
        else np.nan
    )

    drawdown = ticker_price / ticker_price.cummax() - 1
    max_drawdown = drawdown.min()

    tail_probability = 1 - var_confidence
    var_cutoff = daily_returns.quantile(tail_probability)
    expected_shortfall = daily_returns[daily_returns <= var_cutoff].mean()

    benchmark_total_return = benchmark_price.iloc[-1] / benchmark_price.iloc[0] - 1
    benchmark_annualised = (1 + benchmark_total_return) ** (1 / years) - 1

    covariance = aligned["asset"].cov(aligned["benchmark"])
    benchmark_variance = aligned["benchmark"].var()

    beta = (
        covariance / benchmark_variance
        if benchmark_variance and benchmark_variance > 0
        else np.nan
    )

    correlation = aligned["asset"].corr(aligned["benchmark"])

    latest_returns = daily_returns.tail(90)

    return {
        "annualised_return": _to_float(annualised_return),
        "volatility": _to_float(volatility),
        "max_drawdown": _to_float(max_drawdown),
        "sharpe_ratio": _to_float(sharpe),
        "value_at_risk": _to_float(-var_cutoff),
        "expected_shortfall": _to_float(-expected_shortfall),
        "benchmark_annualised_return": _to_float(benchmark_annualised),
        "excess_return_vs_benchmark": _to_float(
            annualised_return - benchmark_annualised
        ),
        "beta_vs_benchmark": _to_float(beta),
        "correlation_vs_benchmark": _to_float(correlation),
        "latest_daily_returns": [
            {
                "date": idx.strftime("%Y-%m-%d"),
                "return": _to_float(ret),
            }
            for idx, ret in latest_returns.items()
        ],
    }


def build_rule_based_summary(
    ticker: str,
    benchmark: str,
    metrics: Dict[str, Any],
) -> Dict[str, str]:
    vol = metrics.get("volatility") or 0
    dd = metrics.get("max_drawdown") or 0
    sharpe = metrics.get("sharpe_ratio") or 0
    var = metrics.get("value_at_risk") or 0
    es = metrics.get("expected_shortfall") or 0
    excess = metrics.get("excess_return_vs_benchmark") or 0

    if vol > 0.30 or dd < -0.35:
        risk_level = "higher risk"
    elif vol > 0.18 or dd < -0.20:
        risk_level = "moderate risk"
    else:
        risk_level = "lower risk"

    performance_line = "outperformed" if excess > 0 else "underperformed"

    return {
        "risks": (
            f"{ticker} screens as {risk_level} based on annualised volatility of "
            f"{vol:.1%}, max drawdown of {dd:.1%}, 95% daily VaR of {var:.1%}, "
            f"and Expected Shortfall of {es:.1%}."
        ),
        "bull_case": (
            f"The bull case is stronger if {ticker} keeps compounding returns, "
            f"improves its Sharpe ratio, and continues to {performance_line} "
            f"{benchmark} after adjusting for risk."
        ),
        "bear_case": (
            f"The bear case is that downside risk remains meaningful. Large drawdowns, "
            f"weak risk-adjusted returns, or beta-driven losses could hurt investors "
            f"if the market sells off."
        ),
        "catalysts": (
            "Catalysts to research next: earnings updates, margin trends, "
            "interest-rate sensitivity, sector news, valuation changes, and recent "
            "ASX/company announcements."
        ),
        "sharpe_comment": (
            f"Current Sharpe ratio: {sharpe:.2f}. Above 1.0 is generally stronger; "
            f"below 0.5 usually needs more investigation."
        ),
        "ai_note": (
            "This is a rule-based MVP summary generated from historical market metrics only."
        ),
        "summary_source": "rule_based",
        "model_used": "none",
        "ai_error": "",
    }


def build_ai_summary(
    ticker: str,
    benchmark: str,
    metrics: Dict[str, Any],
) -> Dict[str, str]:
    api_key = os.getenv("GROQ_API_KEY")
    base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    if not api_key:
        summary = build_rule_based_summary(ticker, benchmark, metrics)
        summary["summary_source"] = "rule_based_no_api_key"
        summary["model_used"] = "none"
        summary["ai_note"] = "Rule-based summary used because no Groq API key was configured."
        summary["ai_error"] = "Missing GROQ_API_KEY environment variable."
        return summary

    prompt_data = {
        "ticker": ticker,
        "benchmark": benchmark,
        "metrics": metrics,
    }

    system_prompt = """
You are an investment risk analyst.

Use ONLY the metrics provided by the backend.
Do not invent company news, analyst ratings, earnings results, macro events, recommendations, or current events.
Do not say buy, sell, or hold.
Do not provide personalised financial advice.

Return ONLY valid JSON with these exact keys:
{
  "risks": "...",
  "bull_case": "...",
  "bear_case": "...",
  "catalysts": "...",
  "sharpe_comment": "...",
  "ai_note": "..."
}
"""

    user_prompt = f"""
Analyse this investment risk profile.

Ticker: {ticker}
Benchmark: {benchmark}

Metrics JSON:
{json.dumps(prompt_data, indent=2)}

Make the response specific to {ticker}.
Mention the actual annualised return, volatility, max drawdown, Sharpe ratio, VaR,
Expected Shortfall, beta, correlation, and benchmark comparison where useful.

Keep it concise and professional for a finance internship portfolio project.
"""

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=800,
        )

        text = response.choices[0].message.content

        if not text:
            raise ValueError("AI response was empty.")

        parsed = json.loads(text)

        required_keys = [
            "risks",
            "bull_case",
            "bear_case",
            "catalysts",
            "sharpe_comment",
            "ai_note",
        ]

        for key in required_keys:
            if key not in parsed:
                parsed[key] = "Not provided."

        parsed["summary_source"] = "groq"
        parsed["model_used"] = model
        parsed["ai_error"] = ""

        return parsed

    except Exception as error:
        print("AI SUMMARY ERROR:", repr(error), flush=True)

        summary = build_rule_based_summary(ticker, benchmark, metrics)
        summary["summary_source"] = "rule_based_ai_failed"
        summary["model_used"] = model
        summary["ai_note"] = (
            "Rule-based summary used because the AI API call failed. "
            "Check the ai_error field or Render logs."
        )
        summary["ai_error"] = f"{type(error).__name__}: {str(error)}"

        return summary


@app.get("/")
def root() -> Dict[str, str]:
    return {
        "message": "AI Investment Risk Dashboard API is running",
        "docs": "/docs",
        "health": "/api/health",
        "analyze": "/api/analyze",
        "debug_ai": "/api/debug-ai",
    }


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/debug-ai")
def debug_ai() -> Dict[str, Any]:
    api_key = os.getenv("GROQ_API_KEY")
    base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    frontend_url = os.getenv("FRONTEND_URL")

    return {
        "has_groq_key": bool(api_key),
        "groq_key_starts_correctly": bool(api_key and api_key.startswith("gsk_")),
        "groq_key_length": len(api_key) if api_key else 0,
        "base_url": base_url,
        "model": model,
        "frontend_url": frontend_url,
        "allowed_origins": get_allowed_origins(),
    }


@app.get("/api/analyze")
def analyze(
    ticker: str = Query(
        "CBA.AX",
        description="Stock or ETF ticker. Use .AX for ASX tickers.",
    ),
    benchmark: str = Query(
        "^AXJO",
        description="Benchmark ticker, e.g. ^AXJO, SPY, VAS.AX",
    ),
    period: str = Query(
        "5y",
        pattern="^(6mo|1y|2y|5y|10y|max)$",
    ),
    var_confidence: float = Query(
        0.95,
        ge=0.90,
        le=0.99,
    ),
    risk_free_rate: float = Query(
        0.04,
        ge=0,
        le=0.20,
    ),
) -> Dict[str, Any]:
    ticker = _clean_ticker(ticker)
    benchmark = _clean_ticker(benchmark)

    prices = download_prices(ticker, benchmark, period)
    metrics = calculate_metrics(prices, ticker, benchmark, var_confidence, risk_free_rate)

    chart_data: List[Dict[str, Any]] = []

    first_asset = prices[ticker].iloc[0]
    first_benchmark = prices[benchmark].iloc[0]

    for idx, row in prices.tail(750).iterrows():
        chart_data.append(
            {
                "date": idx.strftime("%Y-%m-%d"),
                "price": _to_float(row[ticker]),
                "benchmark_price": _to_float(row[benchmark]),
                "indexed_price": _to_float(row[ticker] / first_asset * 100),
                "indexed_benchmark": _to_float(row[benchmark] / first_benchmark * 100),
            }
        )

    summary = build_ai_summary(ticker, benchmark, metrics)

    return {
        "ticker": ticker,
        "benchmark": benchmark,
        "period": period,
        "var_confidence": var_confidence,
        "risk_free_rate": risk_free_rate,
        "metrics": metrics,
        "chart_data": chart_data,
        "summary": summary,
        "disclaimer": "Educational project only. Not financial advice.",
    }