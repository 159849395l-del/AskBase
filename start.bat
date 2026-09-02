@echo off
setlocal enabledelayedexpansion

REM Fix the console code page first: the backend logs contain Chinese, and under
REM the default GBK code page Python raises UnicodeEncodeError and uvicorn dies.
chcp 65001 >nul 2>&1
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

set "PROJECT_DIR=%~dp0"
set "FORCE_INSTALL=0"
if /i "%~1"=="--reinstall" set "FORCE_INSTALL=1"
set "BOOT_TMP=%TEMP%\askbase_boot.tmp"

echo ============================================
echo   AskBase - RAG Q^&A System
echo ============================================
echo.

REM ================= [1/6] runtime check =================
echo [1/6] Checking runtime ...

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo   [ERROR] python not found in PATH. Install Python 3.11 first.
    pause
    exit /b 1
)
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo   [ERROR] node not found in PATH. Install Node.js 18+ first.
    pause
    exit /b 1
)

REM "where python" also matches the Microsoft Store stub, which exists but fails
REM to run, so actually execute python to read its version.
python -c "import sys;print('%%d.%%d.%%d' %% sys.version_info[:3])" >"%BOOT_TMP%" 2>nul
set "PY_VER="
if exist "%BOOT_TMP%" for /f "usebackq delims=" %%V in ("%BOOT_TMP%") do if not defined PY_VER set "PY_VER=%%V"
del "%BOOT_TMP%" >nul 2>&1
if not defined PY_VER (
    echo   [ERROR] python is on PATH but cannot run.
    echo           Reinstall Python 3.11 and tick "Add python.exe to PATH".
    pause
    exit /b 1
)
set "NODE_VER="
for /f "tokens=*" %%V in ('node --version 2^>^&1') do set "NODE_VER=%%V"
echo   python !PY_VER!  /  node !NODE_VER!

set "PY_MAJOR=0"
set "PY_MINOR=0"
for /f "tokens=1,2 delims=." %%A in ("!PY_VER!") do (
    set "PY_MAJOR=%%A"
    set "PY_MINOR=%%B"
)

REM ================= [2/6] backend venv + deps =================
echo.
echo [2/6] Preparing Python backend ...
cd /d "%PROJECT_DIR%backend"
set "PYEXE=%PROJECT_DIR%backend\venv\Scripts\python.exe"

if not exist "venv\Scripts\python.exe" (
    REM The venv inherits the python that created it, and the pinned wheels are
    REM built for 3.11, so complain now rather than after a broken pip install.
    if not "!PY_MAJOR!"=="3" (
        echo   [WARN] unexpected python major version !PY_MAJOR!
    ) else if !PY_MINOR! LSS 10 (
        echo   [ERROR] Python 3.10+ required, found !PY_VER!
        pause
        exit /b 1
    ) else if !PY_MINOR! GTR 12 (
        echo   [WARN] Python !PY_VER! about to create the venv.
        echo          Wheels are pinned for 3.11; if pip install fails, install
        echo          Python 3.11, delete backend\venv and run start.bat again.
    )
    echo   Creating virtualenv ...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo   [ERROR] Failed to create venv.
        pause
        exit /b 1
    )
)

REM Reinstall whenever requirements.txt changes (md5 stamped into venv\deps.md5).
set "NEED_INSTALL=0"
if "%FORCE_INSTALL%"=="1" set "NEED_INSTALL=1"
if not exist "venv\deps.md5" set "NEED_INSTALL=1"

REM Hash requirements.txt through a temp file: for /f mangles a command whose
REM exe path is quoted (which %PYEXE% is), and "set /p <file" breaks whenever
REM the script itself is started with redirected stdin.
set "CUR_MD5="
"%PYEXE%" -c "import hashlib,pathlib;print(hashlib.md5(pathlib.Path('requirements.txt').read_bytes()).hexdigest())" >"%BOOT_TMP%" 2>nul
if exist "%BOOT_TMP%" for /f "usebackq delims=" %%H in ("%BOOT_TMP%") do if not defined CUR_MD5 set "CUR_MD5=%%H"
del "%BOOT_TMP%" >nul 2>&1

if defined CUR_MD5 (
    if not exist "venv\deps.md5" (
        set "NEED_INSTALL=1"
    ) else (
        set "OLD_MD5="
        if exist "venv\deps.md5" for /f "usebackq delims=" %%M in ("venv\deps.md5") do if not defined OLD_MD5 set "OLD_MD5=%%M"
        if /i not "!CUR_MD5!"=="!OLD_MD5!" (
            echo   requirements.txt changed, reinstalling ...
            set "NEED_INSTALL=1"
        )
    )
) else (
    echo   [WARN] could not hash requirements.txt, keeping current packages.
)

if "%NEED_INSTALL%"=="1" (
    echo   Installing Python dependencies, first run takes a few minutes ...
    "%PYEXE%" -m pip install -r requirements.txt --disable-pip-version-check -i https://mirrors.aliyun.com/pypi/simple/
    if %errorlevel% neq 0 (
        echo   [ERROR] pip install failed. Check your network or the mirror URL.
        pause
        exit /b 1
    )
    if defined CUR_MD5 >"venv\deps.md5" echo !CUR_MD5!
    echo   Dependencies installed.
) else (
    echo   Python deps up to date.
)

REM ================= [3/6] frontend deps =================
echo.
echo [3/6] Preparing frontend ...
cd /d "%PROJECT_DIR%frontend"

if not exist "node_modules" (
    echo   Installing npm packages, first run takes a few minutes ...
    call npm install
    if %errorlevel% neq 0 (
        echo   [ERROR] npm install failed.
        pause
        exit /b 1
    )
) else (
    echo   Frontend deps OK.
)

REM ================= [4/6] kill leftovers & wait for ports =================
echo.
echo [4/6] Stopping leftover AskBase processes ...
set "ASK_BASE=%PROJECT_DIR%"

REM Kill only THIS project's leftovers (logic inlined, was cleanup_dev.ps1).
REM Rule A: backend started from this project's venv (uvicorn / app.main).
powershell -NoProfile -ExecutionPolicy Bypass -Command "$b=$env:ASK_BASE.TrimEnd('\'); Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*.exe' -and $_.ExecutablePath -like ($b+'*') -and $_.CommandLine -match 'uvicorn|app\.main' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }"
REM Rule B: port 5175 vite frontend / port 8000 app.main:app fallback.
powershell -NoProfile -ExecutionPolicy Bypass -Command "foreach($p in 5175,8000){ if($p -eq 5175){$pat='vite'}else{$pat='app\.main:app'}; Get-NetTCPConnection -State Listen -LocalPort $p -EA SilentlyContinue | ForEach-Object { $q=Get-CimInstance Win32_Process -Filter ('ProcessId='+$_.OwningProcess); if($q -and $q.CommandLine -match $pat){ Stop-Process -Id $q.ProcessId -Force -EA SilentlyContinue } } }"
REM Rule C: orphaned uvicorn --reload workers (command line only says
REM "multiprocessing.spawn"; netstat reports their dead parent pid as the owner,
REM so they are invisible to Rule A/B - kill only if parent pid is gone).
powershell -NoProfile -ExecutionPolicy Bypass -Command "if(@(Get-NetTCPConnection -State Listen -LocalPort 8000 -EA SilentlyContinue).Count -gt 0){ Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*.exe' -and $_.CommandLine -match 'multiprocessing' } | ForEach-Object { $m=[regex]::Match($_.CommandLine,'parent_pid=(\d+)'); if($m.Success -and -not (Get-Process -Id ([int]$m.Groups[1].Value) -EA SilentlyContinue)){ Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue } } }"

set "PORT_WAIT=0"
:WAIT_FREE
set "BUSY=0"
netstat -ano -p tcp | findstr /R /C:":8000 .*LISTENING" >nul
if %errorlevel% equ 0 set "BUSY=1"
netstat -ano -p tcp | findstr /R /C:":5175 .*LISTENING" >nul
if %errorlevel% equ 0 set "BUSY=1"
if "%BUSY%"=="0" goto PORTS_FREE
set /a PORT_WAIT+=1
if !PORT_WAIT! GEQ 15 (
    echo   [ERROR] Ports 8000 / 5175 are still occupied after 15s.
    echo           Find the owner with:  netstat -ano ^| findstr ":8000"
    echo           Then kill it with:    taskkill /PID ^<pid^> /F
    echo           If taskkill says the PID does not exist, run stop.bat
    echo           as Administrator, or simply reboot.
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto WAIT_FREE
:PORTS_FREE
echo   Ports 8000 / 5175 are free.

REM ================= [5/6] init database =================
echo.
echo [5/6] Initializing database ...
cd /d "%PROJECT_DIR%backend"
"%PYEXE%" scripts\init_all.py
if %errorlevel% neq 0 (
    echo   [ERROR] Database init failed, see the message above.
    pause
    exit /b 1
)

REM ================= [6/6] start services =================
echo.
echo [6/6] Starting services ...

cd /d "%PROJECT_DIR%backend"
start "RAG-Backend" "%PYEXE%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

echo   Waiting for backend on :8000 ...
set "TRIES=0"
:WAIT_BACKEND
set /a TRIES+=1
timeout /t 1 /nobreak >nul
"%PYEXE%" -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/docs',timeout=2)" >nul 2>&1
if %errorlevel% equ 0 goto BACKEND_UP
if !TRIES! GEQ 60 (
    echo   [ERROR] Backend did not answer on :8000 within 60s.
    echo           Read the RAG-Backend window for the traceback.
    pause
    exit /b 1
)
goto WAIT_BACKEND
:BACKEND_UP
echo   Backend is up  -^> http://localhost:8000/docs

cd /d "%PROJECT_DIR%frontend"
start "RAG-Frontend" cmd /k "npm run dev"

echo   Waiting for frontend on :5175 ...
set "TRIES=0"
:WAIT_FRONTEND
set /a TRIES+=1
timeout /t 1 /nobreak >nul
"%PYEXE%" -c "import urllib.request;urllib.request.urlopen('http://localhost:5175/',timeout=2)" >nul 2>&1
if %errorlevel% equ 0 goto FRONTEND_UP
if !TRIES! GEQ 60 (
    echo   [ERROR] Frontend did not answer on :5175 within 60s.
    echo           Read the RAG-Frontend window for the error.
    pause
    exit /b 1
)
goto WAIT_FRONTEND
:FRONTEND_UP
echo   Frontend is up -^> http://localhost:5175

start "" http://localhost:5175

echo.
echo ============================================
echo   AskBase is running
echo     Frontend : http://localhost:5175
echo     Backend  : http://localhost:8000/docs
echo     Login    : admin / 123456
echo.
echo   Close the RAG-Backend and RAG-Frontend
echo   windows to stop the services.
echo.
echo   Tip: run  start.bat --reinstall  to force a
echo        dependency reinstall after editing requirements.txt
echo ============================================
pause
