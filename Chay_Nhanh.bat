@echo off
cd /d "%~dp0"
if not defined PUBLIC set "PUBLIC=C:\Users\Public"
set "VENV_PY=%PUBLIC%\VietsubAI_Runtime\venv\Scripts\pythonw.exe"
set "VIETSUB_MODEL_DIR=%PUBLIC%\VietsubAI_Runtime\models"
set "HF_HOME=%PUBLIC%\VietsubAI_Runtime\huggingface"
if not exist "%VENV_PY%" if exist "%~dp0.venv\Scripts\pythonw.exe" set "VENV_PY=%~dp0.venv\Scripts\pythonw.exe"
if not exist "%VENV_PY%" (
  call Cai_Dat_Va_Chay.bat
  exit /b
)
start "Vietsub AI Studio" "%VENV_PY%" launcher.py
