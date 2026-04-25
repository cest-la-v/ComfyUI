@echo off
setlocal EnableDelayedExpansion

:: ============================================================
::  ComfyUI AMD GPU Launcher
::
::  Env vars (injected by root shim, or set manually to override):
::    PORTABLE_ROOT   — root of the portable package
::    PYTHON          — path to python.exe
::                      (auto-detected: python_embeded → .venv → system python)
::    COMFYUI_ROOT    — path to the ComfyUI git repo
::    FRONTEND_ROOT   — path to the built frontend dist folder
::
::  Flags (combinable):
::    --no-smart-mem      Launch with smart memory disabled
::    --local-frontend    Launch with local frontend build
::    --build-frontend    Run `pnpm build` in the frontend dir before launching
::                        (implies --local-frontend)
::
::  Examples:
::    start.bat --no-smart-mem
::    start.bat --local-frontend --no-smart-mem
::    start.bat --build-frontend
::    start.bat --build-frontend --no-smart-mem
::
::  To update/upgrade deps, use update.bat instead.
:: ============================================================

:: ── Defaults ────────────────────────────────────────────────
if not defined PORTABLE_ROOT set "PORTABLE_ROOT=%CD%"
if not defined COMFYUI_ROOT  if exist "%PORTABLE_ROOT%\ComfyUI\main.py"       set "COMFYUI_ROOT=%PORTABLE_ROOT%\ComfyUI"
if not defined FRONTEND_ROOT if exist "%PORTABLE_ROOT%\ComfyUI_frontend\dist" set "FRONTEND_ROOT=%PORTABLE_ROOT%\ComfyUI_frontend\dist"
if not defined PYTHON (
    if exist "%PORTABLE_ROOT%\python_embeded\python.exe" (
        set "PYTHON=%PORTABLE_ROOT%\python_embeded\python.exe"
    ) else if exist "%PORTABLE_ROOT%\.venv\Scripts\python.exe" (
        set "PYTHON=%PORTABLE_ROOT%\.venv\Scripts\python.exe"
    ) else (
        set "PYTHON=python"
    )
)

set "COMFYUI_MAIN=%COMFYUI_ROOT%\main.py"
set "BASE_ARGS=--windows-standalone-build --enable-manager"

:: ── Parse flags ──────────────────────────────────────────────
set "OPT_NO_SMART_MEM="
set "OPT_LOCAL_FRONTEND="
set "OPT_BUILD_FRONTEND="
set "HAS_FLAGS="

:parse
if "%~1"=="" goto :after_parse
set "HAS_FLAGS=1"
if /I "%~1"=="--no-smart-mem"     set "OPT_NO_SMART_MEM=1"
if /I "%~1"=="--local-frontend"   set "OPT_LOCAL_FRONTEND=1"
if /I "%~1"=="--build-frontend"   ( set "OPT_BUILD_FRONTEND=1" & set "OPT_LOCAL_FRONTEND=1" )
shift
goto :parse
:after_parse

if defined HAS_FLAGS goto :launch

:: ── Interactive menu ─────────────────────────────────────────
:menu
cls
echo.
echo  ================================================
echo    ComfyUI  ^|  AMD GPU Launcher
echo  ================================================
echo.
echo    [1]  Launch normally                (default)
echo    [2]  Launch  -  disable smart memory
echo    [3]  Launch  -  local frontend build
echo    [4]  Build + launch local frontend
echo    [Q]  Quit
echo.
echo    To update/upgrade deps: run update.bat
echo  ================================================
echo.
set /p "CHOICE=Choice [1]: "
if "!CHOICE!"==""   goto :launch
if "!CHOICE!"=="1"  goto :launch
if "!CHOICE!"=="2"  ( set "OPT_NO_SMART_MEM=1"  & goto :launch )
if "!CHOICE!"=="3"  ( set "OPT_LOCAL_FRONTEND=1" & goto :launch )
if "!CHOICE!"=="4"  ( set "OPT_BUILD_FRONTEND=1" & set "OPT_LOCAL_FRONTEND=1" & goto :launch )
if /I "!CHOICE!"=="Q" goto :quit
echo  Invalid choice. Try again.
timeout /t 1 >nul
goto :menu

:: ── Launch ────────────────────────────────────────────────────
:launch
set "LAUNCH_ARGS=%BASE_ARGS%"
if defined OPT_NO_SMART_MEM  set "LAUNCH_ARGS=%LAUNCH_ARGS% --disable-smart-memory"
if defined OPT_LOCAL_FRONTEND (
    if not exist "%FRONTEND_ROOT%" (
        echo.
        echo  ERROR: Local frontend not found at %FRONTEND_ROOT%
        echo         Clone https://github.com/Comfy-Org/ComfyUI_frontend and build it first.
        goto :end
    )
    if defined OPT_BUILD_FRONTEND (
        echo.
        echo  Building frontend...
        pushd "%FRONTEND_ROOT%\.."
        pnpm build
        if errorlevel 1 ( echo. & echo  pnpm build failed. & popd & goto :end )
        popd
    )
    set "LAUNCH_ARGS=%LAUNCH_ARGS% --front-end-root "%FRONTEND_ROOT%""
)
echo.
echo  Starting ComfyUI...
"%PYTHON%" -s "%COMFYUI_MAIN%" %LAUNCH_ARGS%
goto :end

:quit
echo.
:end
endlocal

