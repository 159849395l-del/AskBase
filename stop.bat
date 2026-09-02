@echo off
chcp 65001 >nul 2>&1
set "PROJECT_DIR=%~dp0"
set "ASK_BASE=%PROJECT_DIR%"

echo ============================================
echo   AskBase - stopping dev servers
echo ============================================
echo.
REM Same cleanup as start.bat step 4 (inlined, logic identical).
powershell -NoProfile -ExecutionPolicy Bypass -Command "$b=$env:ASK_BASE.TrimEnd('\'); Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*.exe' -and $_.ExecutablePath -like ($b+'*') -and $_.CommandLine -match 'uvicorn|app\.main' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }"
powershell -NoProfile -ExecutionPolicy Bypass -Command "foreach($p in 5175,8000){ if($p -eq 5175){$pat='vite'}else{$pat='app\.main:app'}; Get-NetTCPConnection -State Listen -LocalPort $p -EA SilentlyContinue | ForEach-Object { $q=Get-CimInstance Win32_Process -Filter ('ProcessId='+$_.OwningProcess); if($q -and $q.CommandLine -match $pat){ Stop-Process -Id $q.ProcessId -Force -EA SilentlyContinue } } }"
powershell -NoProfile -ExecutionPolicy Bypass -Command "if(@(Get-NetTCPConnection -State Listen -LocalPort 8000 -EA SilentlyContinue).Count -gt 0){ Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*.exe' -and $_.CommandLine -match 'multiprocessing' } | ForEach-Object { $m=[regex]::Match($_.CommandLine,'parent_pid=(\d+)'); if($m.Success -and -not (Get-Process -Id ([int]$m.Groups[1].Value) -EA SilentlyContinue)){ Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue } } }"
echo.
echo   Done. Ports 8000 / 5175 should be free now.
echo   If a port is still held by an "unknown" PID,
echo   rerun this file as Administrator.
echo ============================================
pause
