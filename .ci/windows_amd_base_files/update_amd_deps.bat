@echo off
setlocal enabledelayedexpansion

:: ── Defaults ─────────────────────────────────────────────────────────────────
if not defined PORTABLE_ROOT set "PORTABLE_ROOT=%CD%"
if not defined COMFYUI_ROOT  if exist "%PORTABLE_ROOT%\ComfyUI\main.py" set "COMFYUI_ROOT=%PORTABLE_ROOT%\ComfyUI"
if not defined PYTHON (
    if exist "%PORTABLE_ROOT%\python_embeded\python.exe" (
        set "PYTHON=%PORTABLE_ROOT%\python_embeded\python.exe"
    ) else if exist "%PORTABLE_ROOT%\.venv\Scripts\python.exe" (
        set "PYTHON=%PORTABLE_ROOT%\.venv\Scripts\python.exe"
    ) else (
        set "PYTHON=python"
    )
)

set "FETCH_URLS=%~dp0fetch_rocm_urls.py"

echo.
echo  ============================================
echo    ComfyUI  -  Upgrade AMD Deps
echo  ============================================
echo   Fetches latest ROCm wheels from AMD repo
echo   and installs them together with
echo   requirements.txt in a single pip call.
echo  ============================================
echo.
pause

echo.
echo [1/2] Fetching ROCm package URLs...
set "ROCM_URLS="
for /f "delims=" %%u in ('cmd /c ""%PYTHON%" -s "%FETCH_URLS%""') do set "ROCM_URLS=!ROCM_URLS! %%u"
if "!ROCM_URLS!"=="" (
    echo Failed to resolve ROCm URLs.
    pause
    exit /b 1
)

echo.
echo [2/2] Installing ROCm packages + requirements in one pass...
"%PYTHON%" -s -m pip install --upgrade !ROCM_URLS! -r "%COMFYUI_ROOT%\requirements.txt"
if errorlevel 1 (
    echo pip install failed. See output above.
    pause
    exit /b 1
)

echo.
echo All done!
pause
