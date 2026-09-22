@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Cai dat Vietsub AI Studio
if not defined PUBLIC set "PUBLIC=C:\Users\Public"
set "SETUP_LOG=%~dp0nhat_ky_cai_dat.txt"
set "PY_EXE="
set "USE_PY_LAUNCHER=0"
set "RUNTIME_ROOT=%PUBLIC%\VietsubAI_Runtime"
set "VENV_DIR=%PUBLIC%\VietsubAI_Runtime\venv"
set "VENV_PY=%PUBLIC%\VietsubAI_Runtime\venv\Scripts\python.exe"
set "VIETSUB_MODEL_DIR=%PUBLIC%\VietsubAI_Runtime\models"
set "HF_HOME=%PUBLIC%\VietsubAI_Runtime\huggingface"
>"%SETUP_LOG%" echo Bat dau sua loi %date% %time%

echo =============================================
echo       VIETSUB AI STUDIO - SUA LOI MO TOOL
echo =============================================
echo.
echo [1/5] Dang kiem tra Python 3.12...

py -3.12 -c "import sys; assert sys.version_info[:2] == (3,12)" >nul 2>nul
if not errorlevel 1 set "USE_PY_LAUNCHER=1"

if "%USE_PY_LAUNCHER%"=="0" if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PY_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"
if "%USE_PY_LAUNCHER%"=="0" if not defined PY_EXE if exist "%ProgramFiles%\Python312\python.exe" set "PY_EXE=%ProgramFiles%\Python312\python.exe"

if "%USE_PY_LAUNCHER%"=="0" if not defined PY_EXE (
  echo Chua co Python 3.12. Dang thu cai tu dong bang Windows Package Manager...
  where winget >nul 2>nul
  if errorlevel 1 goto :python_missing
  winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
  if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PY_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"
)

if "%USE_PY_LAUNCHER%"=="0" if not defined PY_EXE goto :python_missing

echo [2/5] Dang tao moi truong rieng...
if not exist "%RUNTIME_ROOT%" mkdir "%RUNTIME_ROOT%" >>"%SETUP_LOG%" 2>&1
if errorlevel 1 goto :runtime_folder_failed
if exist "%VENV_PY%" (
  "%VENV_PY%" -c "import sys; assert sys.version_info[:2] == (3,12)" >nul 2>nul
  if errorlevel 1 (
    echo Moi truong cu sai phien ban. Dang tao lai...
    rmdir /s /q "%VENV_DIR%"
  )
)
if exist "%VENV_PY%" goto :venv_ready
if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%"
if "%USE_PY_LAUNCHER%"=="1" goto :create_venv_launcher
"%PY_EXE%" -m venv "%VENV_DIR%" >>"%SETUP_LOG%" 2>&1
if errorlevel 1 goto :create_venv_local
goto :venv_ready

:create_venv_launcher
py -3.12 -m venv "%VENV_DIR%" >>"%SETUP_LOG%" 2>&1
if errorlevel 1 goto :create_venv_local
goto :venv_ready

:create_venv_local
echo Khong tao duoc o thu muc dung chung. Dang thu phuong an du phong...
>>"%SETUP_LOG%" echo Thu tao moi truong du phong trong thu muc tool.
set "VENV_DIR=%~dp0.venv"
set "VENV_PY=%~dp0.venv\Scripts\python.exe"
if exist "%VENV_PY%" goto :venv_ready
if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%"
if "%USE_PY_LAUNCHER%"=="1" py -3.12 -m venv "%VENV_DIR%" >>"%SETUP_LOG%" 2>&1
if "%USE_PY_LAUNCHER%"=="0" "%PY_EXE%" -m venv "%VENV_DIR%" >>"%SETUP_LOG%" 2>&1
if errorlevel 1 goto :venv_failed

:venv_ready
if not exist "%VENV_PY%" goto :venv_failed

echo [3/5] Dang cai Microsoft Visual C++ Runtime...
set "VC_INSTALLER=%TEMP%\vc_redist_vietsub_x64.exe"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -UseBasicParsing 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile '%VC_INSTALLER%'; exit 0 } catch { Write-Host $_; exit 1 }"
if errorlevel 1 goto :runtime_failed
start /wait "" "%VC_INSTALLER%" /install /quiet /norestart
del /q "%VC_INSTALLER%" >nul 2>nul

echo [4/5] Dang cai cac thanh phan can thiet. Vui long cho...
>>"%SETUP_LOG%" echo Bat dau cai thu vien %date% %time%
"%VENV_PY%" -m pip install --upgrade pip >>"%SETUP_LOG%" 2>&1
if errorlevel 1 goto :install_failed
"%VENV_PY%" -m pip install --no-cache-dir --force-reinstall "setuptools==80.9.0" >>"%SETUP_LOG%" 2>&1
if errorlevel 1 goto :install_failed
"%VENV_PY%" -m pip uninstall -y faster-whisper ctranslate2 numpy edge-tts deep-translator >>"%SETUP_LOG%" 2>&1
"%VENV_PY%" -m pip install --no-cache-dir --prefer-binary -r requirements.txt >>"%SETUP_LOG%" 2>&1
if errorlevel 1 goto :install_failed
"%VENV_PY%" -c "import pkg_resources; print('pkg_resources: OK')" >>"%SETUP_LOG%" 2>&1
if errorlevel 1 goto :setuptools_failed

echo [5/5] Dang kiem tra tool...
"%VENV_PY%" kiem_tra_he_thong.py >>"%SETUP_LOG%" 2>&1
if errorlevel 1 goto :dll_failed

echo.
echo Cai dat thanh cong. Dang mo tool...
"%VENV_PY%" launcher.py
if errorlevel 1 (
  echo.
  echo Tool gap loi khi khoi dong. Hay xem file loi_khoi_dong.txt.
  pause
)
exit /b 0

:python_missing
echo.
echo KHONG TIM THAY PYTHON 3.12.
echo Hay cai Python 3.12 tu python.org, danh dau Add Python to PATH,
echo sau do chay lai file nay.
pause
exit /b 1

:install_failed
echo.
echo CAI DAT THAT BAI.
echo Khong cai duoc thu vien. Hay kiem tra Internet. Chi tiet nam trong file:
echo %SETUP_LOG%
echo.
if exist "%SETUP_LOG%" powershell -NoProfile -Command "Get-Content -Tail 18 -LiteralPath '%SETUP_LOG%'"
pause
exit /b 1

:venv_failed
echo.
echo KHONG TAO DUOC MOI TRUONG PYTHON.
echo Day la loi duong dan Python, khong phai loi Internet.
echo Chi tiet nam trong file:
echo %SETUP_LOG%
echo.
if exist "%SETUP_LOG%" powershell -NoProfile -Command "Get-Content -Tail 25 -LiteralPath '%SETUP_LOG%'"
pause
exit /b 1

:setuptools_failed
echo.
echo SETUPTOOLS CHUA TUONG THICH VOI CTRANSLATE2.
echo Dang sua rieng thanh phan pkg_resources...
"%VENV_PY%" -m pip install --no-cache-dir --force-reinstall "setuptools==80.9.0" >>"%SETUP_LOG%" 2>&1
"%VENV_PY%" -c "import pkg_resources" >>"%SETUP_LOG%" 2>&1
if errorlevel 1 goto :dll_failed
goto :venv_ready_after_packages

:venv_ready_after_packages
echo [5/5] Dang kiem tra lai tool...
"%VENV_PY%" kiem_tra_he_thong.py >>"%SETUP_LOG%" 2>&1
if errorlevel 1 goto :dll_failed
echo.
echo Cai dat thanh cong. Dang mo tool...
"%VENV_PY%" launcher.py
exit /b %errorlevel%

:runtime_failed
echo.
echo KHONG TAI DUOC MICROSOFT VISUAL C++ RUNTIME.
echo Hay kiem tra Internet, sau do chay lai file nay.
pause
exit /b 1

:runtime_folder_failed
echo.
echo KHONG TAO DUOC THU MUC CHAY ON DINH:
echo %RUNTIME_ROOT%
echo Hay bam chuot phai file SUA_LOI_VA_MO_TOOL.bat va chon Run as administrator.
pause
exit /b 1

:dll_failed
echo.
echo THU VIEN NHAN DIEN GIONG NOI VAN CHUA HOAT DONG.
echo Thu khoi dong lai Windows mot lan, sau do chay lai file nay.
echo Chi tiet nam trong: %SETUP_LOG%
echo.
if exist "%SETUP_LOG%" powershell -NoProfile -Command "Get-Content -Tail 25 -LiteralPath '%SETUP_LOG%'"
pause
exit /b 1
