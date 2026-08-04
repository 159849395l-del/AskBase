@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0"

echo ============================================
echo   RAG E-Commerce Q&A System
echo ============================================
echo.

REM === Check Python ===
echo [1/5] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.10+
    pause
    exit /b 1
)
python --version

REM === Check Node ===
echo [1/5] Checking Node.js...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Install Node.js 18+
    pause
    exit /b 1
)
node --version

REM === Setup Python venv and install deps ===
echo.
echo [2/5] Setup Python backend...
cd /d "%PROJECT_DIR%backend"

if not exist "venv" (
    echo Creating Python venv...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create venv
        pause
        exit /b 1
    )
)

REM Check if fastapi is installed
venv\Scripts\python.exe -c "import fastapi" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing Python dependencies...
    venv\Scripts\python.exe -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
    if %errorlevel% neq 0 (
        echo [ERROR] pip install failed
        pause
        exit /b 1
    )
    echo Done.
) else (
    echo Python deps OK.
)

REM === Setup frontend ===
echo.
echo [3/5] Setup frontend...
cd /d "%PROJECT_DIR%frontend"

if not exist "node_modules" (
    echo Installing frontend dependencies...
    call npm install
    if %errorlevel% neq 0 (
        echo [ERROR] npm install failed
        pause
        exit /b 1
    )
    echo Done.
) else (
    echo Frontend deps OK.
)

REM === Init DB ===
echo.
echo [4/5] Init database...
cd /d "%PROJECT_DIR%backend"
venv\Scripts\python.exe -c "import asyncio; from app.database import init_db, async_session_factory; from app.services.auth_service import seed_admin; asyncio.run(init_db()); print('DB OK')" >nul 2>&1
if %errorlevel% neq 0 (
    echo DB already exists, skip init.
) else (
    echo DB init OK.
)

REM Seed admin user
venv\Scripts\python.exe -c "import asyncio; from app.database import async_session_factory; from app.services.auth_service import seed_admin; async def run(): async with async_session_factory() as s: await seed_admin(s); await s.commit(); asyncio.run(run()); print('Admin OK')"

REM === Start services ===
echo.
echo [5/5] Starting services...
echo.
echo Backend window will open at http://localhost:8000
echo Frontend window will open at http://localhost:5173
echo.
echo Login: admin / 123456
echo.

cd /d "%PROJECT_DIR%backend"
start "RAG-Backend" venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

timeout /t 3 /nobreak >nul

cd /d "%PROJECT_DIR%frontend"
start "RAG-Frontend" cmd /k "npm run dev"

timeout /t 3 /nobreak >nul
start http://localhost:5173

echo.
echo ============================================
echo System started. Check the two new windows:
echo   - RAG-Backend  (port 8000)
echo   - RAG-Frontend (port 5173)
echo.
echo Admin login: admin / 123456
echo ============================================
pause
