@echo off
setlocal
cd /d "%~dp0"

if not "%~1"=="" goto run_with_arguments

echo Active Elden Ring characters:
echo.
py -m death_counter --list
if errorlevel 1 goto finished

echo.
set /p "SLOT=Enter the slot number to watch (1-10): "
if not defined SLOT (
    echo No slot selected.
    goto finished
)

py -m death_counter --output "%~dp0death_count.txt" --slot "%SLOT%"
goto finished

:run_with_arguments
py -m death_counter --output "%~dp0death_count.txt" %*

:finished
echo.
pause
