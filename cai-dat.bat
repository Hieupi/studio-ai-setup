@echo off
setlocal EnableExtensions

pushd "%~dp0"

if not exist "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" goto :FALLBACK_CLI

rem Mo cua so giao dien WPF qua conhost --headless va thoat ngay (~50 ms, khong giu cua so den)
if exist "%SystemRoot%\System32\conhost.exe" (
    start "" "%SystemRoot%\System32\conhost.exe" --headless powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0scripts\cai-dat.ps1"
) else (
    start "" powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -STA -File "%~dp0scripts\cai-dat.ps1"
)

popd
exit /b 0

:FALLBACK_CLI
chcp 65001 >nul 2>&1
echo ============================================================================
echo  Khong tim thay PowerShell tren may nay; dang chuyen sang che do chu.
echo ============================================================================
set "PYTHONUTF8=1"
set "PYTHONDONTWRITEBYTECODE=1"
where python >nul 2>&1
if not errorlevel 1 (
    python -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
    if not errorlevel 1 (
        python -B "%~dp0engine\setup_engine.py" --interactive
        popd
        exit /b %errorlevel%
    )
)
echo [!] Chua tim thay PowerShell hoac Python 3.10+ hop le.
echo [*] Vui long mo Windows PowerShell va chay:
echo     powershell -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0scripts\cai-dat.ps1"
pause
popd
exit /b 1
