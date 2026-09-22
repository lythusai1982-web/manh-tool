@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Kiem tra loi Vietsub AI Studio
if not defined PUBLIC set "PUBLIC=C:\Users\Public"
set "VENV_PY=%PUBLIC%\VietsubAI_Runtime\venv\Scripts\python.exe"
set "VIETSUB_MODEL_DIR=%PUBLIC%\VietsubAI_Runtime\models"
set "HF_HOME=%PUBLIC%\VietsubAI_Runtime\huggingface"
if not exist "%VENV_PY%" if exist "%~dp0.venv\Scripts\python.exe" set "VENV_PY=%~dp0.venv\Scripts\python.exe"

echo =============================================
echo      KIEM TRA LOI VIETSUB AI STUDIO
echo =============================================
echo.
if not exist "%VENV_PY%" (
  echo Chua co moi truong cai dat.
  echo Hay chay Cai_Dat_Va_Chay.bat truoc.
  pause
  exit /b 1
)

echo Phien ban Python:
"%VENV_PY%" --version
echo.
echo Kiem tra thu vien:
"%VENV_PY%" kiem_tra_he_thong.py
if errorlevel 1 (
  echo.
  echo Co thu vien bi loi. Hay chay SUA_LOI_VA_MO_TOOL.bat.
  pause
  exit /b 1
)

echo.
echo Dang mo tool o che do hien thi loi...
"%VENV_PY%" launcher.py
echo.
echo Ma ket thuc: %errorlevel%
if exist "loi_khoi_dong.txt" (
  echo Da tim thay loi_khoi_dong.txt
  type "loi_khoi_dong.txt"
)
pause
