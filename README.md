<div align="center">

# 🔍 CryptoAnalyzer

### Professional Binance Futures Market Analysis Terminal

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-00D9A3?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows)]()
[![Status](https://img.shields.io/badge/Status-Active-success?style=for-the-badge)]()

**Real-time market intelligence, whale detection, and multi-factor analysis — all in your terminal.**

[Features](#-features) • [Installation](#-installation) • [Usage](#-usage) • [Screenshots](#-screenshots) • [Contact](#-contact)

</div>

---

## 🎯 About The Project

**CryptoAnalyzer** is a professional-grade terminal application designed for serious crypto traders who trade **Binance Futures**. It provides institutional-level market analysis directly in your terminal — no bloated GUIs, no unnecessary chrome, just pure data intelligence.

Built with performance in mind, featuring an optional **Rust acceleration engine** for lightning-fast calculations on large datasets.

### 🌟 Why CryptoAnalyzer?

- 🎯 **Purpose-Built** for Binance Futures (USDⓈ-M)
- 📊 **1000+ Order Book Depth Levels** — see what others can't
- 🐋 **Whale Detection Algorithm** — spot the big players
- 📈 **Multi-Factor Analysis** — EMA, RSI, ADX, CVD combined
- 🖥️ **Beautiful TUI** — hacker-themed terminal interface
- ⚡ **Blazing Fast** — Python + optional Rust engine
- 💾 **JSON Export** — integrate with your own tools

---

## ✨ Features

### 📊 Order Book Analysis
- ✅ 1000+ depth levels (bids & asks)
- ✅ Support / resistance level detection
- ✅ Liquidity cluster identification
- ✅ Real-time buying / selling pressure calculation
- ✅ Bid-ask spread analysis with slippage estimation

### 📈 Trend Analysis
- ✅ Trend direction & strength detection
- ✅ EMA (9, 21, 50, 200) crossovers
- ✅ RSI (Relative Strength Index)
- ✅ ADX (Average Directional Index)
- ✅ Price structure (Higher Highs / Lower Lows)

### 💹 Volume Analysis
- ✅ Buy vs Sell volume split
- ✅ **CVD** (Cumulative Volume Delta)
- ✅ Volume spike detection
- ✅ Tape reading (live trade flow)
- ✅ Volume profile by price level

### 🐋 Whale Detection
- ✅ Large order detection in book
- ✅ Large trade detection on tape
- ✅ Whale bias analysis (bullish / bearish)
- ✅ Spoofing / wall detection
- ✅ Iceberg order hints

### 🖥️ Terminal UI
- ✅ Hacker-themed TUI (Rich + Textual)
- ✅ Live auto-refresh (configurable interval)
- ✅ ASCII sparkline charts
- ✅ Color-coded signal panels
- ✅ Keyboard-driven navigation

### ⚙️ Engineering
- ✅ JSON snapshot export
- ✅ Optional Rust performance engine
- ✅ Single-file Windows executable (PyInstaller)
- ✅ Modular architecture
- ✅ Type hints throughout

---

## 📸 Screenshots

> *(Add your `banner.png` here in the root folder)*
┌──────────────────────────────────────────────────────────────┐
│ 🔍 CRYPTO ANALYZER | BTCUSDT | ⚡ LONG BIAS | 14:23:11 │
├──────────────────────────────────────────────────────────────┤
│ 📊 ORDER BOOK │ 📈 TREND ANALYSIS │
│ Best Bid: 67,234.50 │ EMA 9: 67,401 ▲ │
│ Best Ask: 67,235.00 │ EMA 21: 67,289 ▲ │
│ Spread: 0.50 bps │ RSI: 62.4 (Bullish) │
│ Depth ±2%: 4.2M USDT │ ADX: 28.7 (Strong Trend) │
│ │ Bias: ▲▲ BULLISH │
├──────────────────────────────────────────────────────────────┤
│ 🐋 WHALE ACTIVITY │ 💹 VOLUME / CVD │
│ Detected: 7 whales │ Buy Vol: 62% ████████░░ │
│ Largest: $1.2M │ Sell Vol: 38% █████░░░░░ │
│ Bias: 🟢 BULLISH │ CVD: +284K USDT │
└──────────────────────────────────────────────────────────────┘

text


---

## 🚀 Installation

### Prerequisites
- **Python 3.10+** (for source run)
- **Windows 10/11** (for prebuilt `.exe`)
- Internet connection (Binance Futures API)

### Option 1: Quick Setup (Recommended)

```batch
# Clone the repository
git clone https://github.com/Daniyalmashi/CryptoAnalyzer.git
cd CryptoAnalyzer

# Run the setup script
setup.bat

# Launch the analyzer
run.bat
Option 2: Manual Setup
Bash

# Clone
git clone https://github.com/Daniyalmashi/CryptoAnalyzer.git
cd CryptoAnalyzer

# Create virtual environment
python -m venv venv

# Activate
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run
python -m crypto_analyzer
Option 3: Windows Executable (No Python Required)
Download CryptoAnalyzer.exe from Releases
Double-click to run — that's it!
🎮 Usage
Basic Launch
batch

run.bat
Command Line Options
Bash

python -m crypto_analyzer --symbol BTCUSDT --interval 5 --export
Flag	Description	Default
--symbol	Trading pair	BTCUSDT
--interval	Refresh interval (sec)	5
--depth	Order book depth	1000
--export	Export JSON snapshot	False
--rust	Use Rust engine	False
Keyboard Shortcuts (TUI)
Key	Action
R	Refresh now
E	Export JSON
Q	Quit
↑/↓	Navigate panels
1-5	Switch view
🏗️ Architecture
text

CryptoAnalyzer/
├── crypto_analyzer/        # Main Python package
│   ├── core/              # Core analysis logic
│   │   ├── orderbook.py   # Order book engine
│   │   ├── trend.py       # Trend indicators
│   │   ├── volume.py      # Volume & CVD
│   │   └── whales.py      # Whale detection
│   ├── ui/                # Terminal UI
│   ├── api/               # Binance API client
│   └── exporter/          # JSON export
├── rust_engine/           # Optional Rust acceleration
├── run.bat                # Quick launcher
├── setup.bat              # Setup script
├── build.bat              # Build .exe
├── requirements.txt
└── README.md
🛠️ Tech Stack
Language: Python 3.10+
UI Framework: Rich + Textual
API Client: CCXT / native Binance API
Performance: Rust (optional engine via PyO3)
Data: Pandas + NumPy
Build: PyInstaller for .exe
🤝 Contributing
Contributions are welcome and appreciated! 💖

Fork the Project
Create your Feature Branch (git checkout -b feature/AmazingFeature)
Commit your Changes (git commit -m 'Add some AmazingFeature')
Push to the Branch (git push origin feature/AmazingFeature)
Open a Pull Request
📜 License
Distributed under the MIT License. See LICENSE for more information.

⚠️ Disclaimer
This tool is for educational and analytical purposes only. It is not financial advice. Cryptocurrency trading carries substantial risk. Always do your own research (DYOR) and never trade with money you cannot afford to lose.

📬 Contact & Connect
Let's build together — reach out on any platform 👇

<div align="center">
Email
Fiverr
Discord
Instagram
LinkedIn

</div>
<div align="center">
⭐ Star this repo if you find it useful!
Made with ❤️ by Daniyal Mashi

</div> ```
