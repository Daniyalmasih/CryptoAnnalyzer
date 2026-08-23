@echo off
REM Setup script for CryptoAnalyzer

echo 🔨 CryptoAnalyzer Setup
echo ========================
echo.

echo 1. Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ❌ Failed to create virtual environment
    pause
    exit /b 1
)

echo 2. Activating virtual environment...
call venv\Scripts\activate

echo 3. Upgrading pip...
python -m pip install --upgrade pip

echo 4. Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ Failed to install dependencies
    pause
    exit /b 1
)

echo 5. Installing Rust engine (optional)...
echo    Note: This requires Rust to be installed
echo    If Rust is not installed, the Python fallback will be used
echo.
set /p build_rust="Build Rust engine? (y/n): "
if /i "%build_rust%"=="y" (
    echo Building Rust engine...
    cd src\rust_engine
    pip install maturin
    maturin develop --release
    if errorlevel 1 (
        echo ⚠️ Rust build failed, Python fallback will be used
    )
    cd ..\..
)

echo.
echo ========================
echo ✅ Setup complete!
echo.
echo Next steps:
echo   - Run: python run.bat --help
echo   - Or use: python src/main.py --symbol BTCUSDT
echo.
pause