@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "LOG_FILE=%SCRIPT_DIR%install_service.log"
echo [%date% %time%] Старт install_service.bat > "%LOG_FILE%"

pushd "%SCRIPT_DIR%" >nul

set "EVERYTHING_EXE="
for %%F in ("Everything.exe" "Everything64.exe") do (
    if exist "%%~fF" set "EVERYTHING_EXE=%%~fF"
)
if not defined EVERYTHING_EXE (
    for %%F in ("%SCRIPT_DIR%Everything\\Everything.exe" "%SCRIPT_DIR%Everything\\Everything64.exe" "%SCRIPT_DIR%_internal\\Everything\\Everything.exe" "%SCRIPT_DIR%_internal\\Everything\\Everything64.exe") do (
        if exist "%%~fF" set "EVERYTHING_EXE=%%~fF"
    )
)

if not defined EVERYTHING_EXE (
    echo [ERROR] Everything.exe не найден. >> "%LOG_FILE%"
    popd >nul
    exit /b 1
)

echo [INFO] Использую: %EVERYTHING_EXE% >> "%LOG_FILE%"
start "" "%EVERYTHING_EXE%" -instance gemini_voice_assistant >> "%LOG_FILE%" 2>&1
echo [INFO] Команда запуска отправлена. >> "%LOG_FILE%"

popd >nul
exit /b 0
