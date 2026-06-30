# AI Investment Risk Dashboard

A finance + actuarial + coding + AI project 

## Live Demo

Frontend: https://ai-investment-dashboard-six.vercel.app  
Backend API: https://ai-investment-dashboard-thuk.onrender.com/docs

Users enter a listed stock or ETF ticker and benchmark. The app returns a price chart, daily returns, annualised return, volatility, max drawdown, Sharpe ratio, historical Value at Risk, Expected Shortfall, beta/correlation vs benchmark, and an AI-style risk summary.

> Educational project only. Not financial advice.

## Tech stack

- Frontend: React + Vite + Recharts
- Backend: Python + FastAPI
- Data: yfinance
- Analysis: pandas + numpy
- Optional AI summary: OpenAI API

## Folder structure

```txt
ai-investment-risk-dashboard/
  backend/
    main.py
    requirements.txt
  frontend/
    src/
      App.jsx
      main.jsx
      styles.css
    index.html
    package.json
  README.md
```

## Run backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
fastapi dev main.py
```

Backend runs at:

```txt
http://localhost:8000
```

API docs:

```txt
http://localhost:8000/docs
```

## Run frontend

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at:

```txt
http://localhost:5173
```

## Example tickers

- Australian stocks: `CBA.AX`, `MQG.AX`, `BHP.AX`
- Australian ETFs: `VAS.AX`, `VGS.AX`, `NDQ.AX`
- US stocks: `AAPL`, `MSFT`, `NVDA`
- Benchmarks: `^AXJO`, `SPY`, `QQQ`, `VAS.AX`

## Optional: enable real AI summary

Create a backend `.env` or export environment variables:

```bash
export OPENAI_API_KEY="your_api_key_here"
export OPENAI_MODEL="your_preferred_model_here"
```

Without these variables, the app uses a rule-based MVP summary.

## Next improvements

- Add CSV export of returns and metrics
- Add rolling volatility chart
- Add rolling beta chart
- Add ASX announcements link for each ticker
- Add portfolio mode with multiple tickers
- Add proper JSON structured AI output
- Add unit tests for risk metric calculations

## Deployment

- Frontend deployed on Vercel
- Backend deployed on Render
- AI summary generated using Groq's OpenAI-compatible API
- Market data fetched using yfinance
