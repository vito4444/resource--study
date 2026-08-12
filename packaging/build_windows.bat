@echo off
REM One-click Windows build for the Resource Study Harvester GUI.
REM Run from the repository root in a "x64 Native Tools" or plain Command Prompt.
setlocal

echo === Creating virtual environment ===
python -m venv .venv || goto :error
call .venv\Scripts\activate.bat || goto :error

echo === Installing build dependencies ===
python -m pip install --upgrade pip || goto :error
python -m pip install .[build] || goto :error

echo === Building single-file executable ===
pyinstaller --noconfirm --clean packaging\harvester_gui.spec || goto :error

echo.
echo === Done ===
echo Executable: dist\ResourceStudyHarvester.exe
goto :eof

:error
echo.
echo Build failed with error %errorlevel%.
exit /b %errorlevel%
