@echo off
REM Run CryptoAnalyzer in development mode

echo 🚀 Starting CryptoAnalyzer...
echo.

REM Check if virtual environment exists
if exist venv\Scripts\activate (
    call venv\Scripts\activate
) else if exist .venv\Scripts\activate (
    call .venv\Scripts\activate
) else (
    echo ⚠️ Virtual environment not found, using system Python
)

REM Run the application
python src/main.py %*

if errorlevel 1 (
    echo.
    echo ❌ Error occurred. Check logs/cryptoanalyzer.log for details.
    pause
)