# 🔔 AI Limited Edition Product Tracker

A full-stack application that monitors product pages for stock status changes, price drops, and low stock alerts — with instant Telegram notifications.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green?logo=fastapi&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## ✨ Features

- **Multi-Site Scraping** — Supports Amazon, Nike, and any site with structured product data (JSON-LD, Open Graph)
- **Smart Fallback** — Tries lightweight HTTP requests first, falls back to headless Playwright for JS-heavy pages
- **Real-Time Alerts** — Telegram notifications for price drops, back-in-stock, and low stock events
- **Beautiful Dashboard** — Dark-mode glassmorphism UI with live stats, product cards, and alert feed
- **Periodic Monitoring** — Configurable check intervals (default: every 3 minutes)
- **Price History** — Full historical tracking with trend indicators

---

## 🛠️ Setup

### Prerequisites

- **Python 3.10+**
- **pip** (Python package manager)

### 1. Clone & Install Dependencies

```bash
cd "c:\AI Project"
pip install -r requirements.txt
```

### 2. Install Playwright Browser

```bash
playwright install chromium
```

> This downloads a headless Chromium binary (~150 MB). Only needed once.

### 3. Configure Telegram (Optional)

1. Open Telegram and message [@BotFather](https://t.me/botfather)
2. Send `/newbot` and follow the prompts to get your **Bot Token**
3. Message [@userinfobot](https://t.me/userinfobot) to get your **Chat ID**
4. Copy `.env.example` to `.env` and fill in the values:

```bash
copy .env.example .env
```

Edit `.env`:
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

> **Note:** Telegram is optional. If not configured, alerts will only be logged to the console.

### 4. Run the Application

```bash
python run.py
```

Open your browser to: **http://localhost:8000**

---

## 🖥️ Dashboard

The web dashboard provides:

| Feature | Description |
|---------|-------------|
| **Stats Bar** | Total products, alerts today, active monitors |
| **Add Product** | Paste any product URL to start tracking |
| **Product Cards** | Live price, stock status, trend indicator |
| **Quick Actions** | Force-check or remove products |
| **Alert Feed** | Recent notifications with timestamps |

---

## 📡 API Reference

Base URL: `http://localhost:8000/api`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/products` | Add a product URL to track |
| `GET` | `/products` | List all tracked products |
| `GET` | `/products/{id}` | Get single product details |
| `DELETE` | `/products/{id}` | Stop tracking a product |
| `GET` | `/products/{id}/history` | Price history for a product |
| `POST` | `/products/{id}/check` | Force an immediate scrape |
| `GET` | `/stats` | Dashboard statistics |
| `GET` | `/alerts` | Recent alerts |

Interactive API docs: **http://localhost:8000/docs**

---

## 🔧 Configuration

All settings are in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | *(empty)* | Telegram bot token from BotFather |
| `TELEGRAM_CHAT_ID` | *(empty)* | Your Telegram chat ID |
| `SCRAPE_INTERVAL_SECONDS` | `180` | How often to check products (seconds) |
| `DATABASE_URL` | `sqlite+aiosqlite:///./tracker.db` | Database connection string |
| `USER_AGENT` | Chrome 125 UA | Custom User-Agent header |

---

## 🧩 Adding Custom Site Parsers

To add support for a new site, edit `app/scraper/parsers.py`:

```python
class MyStoreParser:
    @staticmethod
    def can_parse(url: str) -> bool:
        return "mystore.com" in url.lower()

    @staticmethod
    def parse(html: str, url: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        return {
            "product_name": soup.select_one("h1.title").get_text(strip=True),
            "price": _extract_price(soup.select_one(".price").text),
            "currency": "$",
            "stock_status": StockStatus.IN_STOCK,
            "stock_text": "In Stock",
        }
```

Then add it to the `PARSERS` list (before `GenericParser`).

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| **Playwright not installed** | Run `playwright install chromium` |
| **Telegram alerts not sending** | Check your `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env` |
| **Scraping returns "Unknown Product"** | The site may block automated requests. Try adding a custom parser |
| **Port 8000 in use** | Change the port in `run.py`: `uvicorn.run(..., port=8001)` |
| **Database errors** | Delete `tracker.db` and restart — tables will be recreated |

---

## 📂 Project Structure

```
├── .env.example          # Environment template
├── .gitignore
├── requirements.txt      # Python dependencies
├── run.py                # Entry point
├── README.md
│
├── app/
│   ├── main.py           # FastAPI app + lifespan
│   ├── config.py         # Settings from .env
│   ├── database.py       # SQLite + async SQLAlchemy
│   ├── models.py         # ORM models
│   ├── schemas.py        # Pydantic schemas
│   ├── api/
│   │   └── routes.py     # REST API endpoints
│   ├── scraper/
│   │   ├── engine.py     # Scraping pipeline
│   │   └── parsers.py    # Site-specific parsers
│   ├── scheduler/
│   │   └── jobs.py       # APScheduler jobs
│   └── notifications/
│       └── telegram.py   # Telegram alerts
│
└── frontend/
    ├── index.html        # Dashboard SPA
    ├── style.css         # Dark-mode styles
    └── app.js            # Frontend logic
```

---

## 📄 License

MIT — feel free to modify and use as you wish.
