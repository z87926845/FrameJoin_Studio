@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 extract_source.py
) else (
    python extract_source.py
)
if errorlevel 1 (
    echo.
    echo 源码展开失败，请检查上面的提示。
    pause
    exit /b 1
)
echo.
echo 源码展开完成。
pause
