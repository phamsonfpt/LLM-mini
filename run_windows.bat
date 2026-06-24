@echo off
chcp 65001 >nul 2>&1
title NotebookLM-Mini 1-Click Run cho Windows
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo ==============================================================================
echo [*] Khoi dong NotebookLM-Mini cho Windows (Zero-Dependency)
echo ==============================================================================

cd /d "%~dp0"

:: 1. Kiem tra ffmpeg (Tuy chon)
where ffmpeg >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [!] Canh bao: Khong tim thay ffmpeg. Tinh nang doc file am thanh se khong hoat dong.
)

:: 2. Kiem tra xem moi truong ao da ton tai chua
if not exist ".venv" (
    echo [i] Moi truong ao .venv chua ton tai. Tien hanh thiet lap lan dau ^(Yeu cau Internet^)...

    rem Kiem tra va cai dat uv ^(Trinh quan ly package sieu toc bang Rust^)
    where uv >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo [i] Dang cai dat cong cu uv...
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
        rem uv duoc cai vao %USERPROFILE%\.local\bin hoac %APPDATA%\uv
        set "PATH=%USERPROFILE%\.local\bin;%APPDATA%\uv;%PATH%"
    )

    rem Kiem tra lai uv sau khi cai
    where uv >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo [X] LOI: Khong the cai dat uv. Vui long cai dat thu cong tai: https://docs.astral.sh/uv/
        echo     Hoac thu chay lai voi quyen Administrator.
        pause
        exit /b 1
    )

    echo [i] Dang tao moi truong ao Python doc lap...
    uv python install 3.11
    if %ERRORLEVEL% neq 0 (
        echo [X] LOI: Khong the cai dat Python 3.11. Kiem tra ket noi Internet.
        pause
        exit /b 1
    )

    uv venv --python 3.11
    if %ERRORLEVEL% neq 0 (
        echo [X] LOI: Khong the tao moi truong ao.
        pause
        exit /b 1
    )

    rem Kich hoat moi truong ao
    call .venv\Scripts\activate.bat

    echo [i] Dang cai dat thu vien Backend...
    uv pip install -r requirements.txt
    if %ERRORLEVEL% neq 0 (
        echo [X] LOI: Cai dat thu vien that bai. Kiem tra ket noi Internet va file requirements.txt.
        pause
        exit /b 1
    )

    echo [i] Dang quet cau hinh may tinh de toi uu AI...
    python src\utils\hardware_profiler.py
) else (
    echo [i] Moi truong ao .venv da ton tai. Bo qua kiem tra thu vien ^(Ho tro chay Offline^).
    call .venv\Scripts\activate.bat
)

:: Kiem tra venv da kich hoat thanh cong
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [X] LOI: Khong the kich hoat moi truong ao Python.
    echo     Thu xoa thu muc .venv roi chay lai.
    pause
    exit /b 1
)

:: 6.6 Tu dong build Frontend neu chua co ban dung
if not exist "frontend\dist" (
    echo [i] Khong tim thay ban dung frontend\dist. Dang tu dong build giao dien...
    where npm >nul 2>&1
    if %ERRORLEVEL% == 0 (
        cd frontend
        call npm install
        call npm run build
        cd ..
    ) else (
        echo [!] Canh bao: Khong tim thay npm ^(Node.js^) tren may. Giao dien web se khong hien thi duoc.
    )
)

:: 7. Khoi dong server
echo ==============================================================================
echo [*] Bat dau chay he thong...
echo [*] Mo trinh duyet tai: http://127.0.0.1:8000
echo ==============================================================================

:: Mo trinh duyet sau 3 giay (chay ngam)
start "" cmd /c "timeout /t 3 /nobreak >nul && start "" http://127.0.0.1:8000"

:: Chay Backend
echo [*] Dang khoi dong Backend Server...
python -m uvicorn src.api.api:app --host 127.0.0.1 --port 8000
if %ERRORLEVEL% neq 0 (
    echo.
    echo ==============================================================================
    echo [X] LOI: Backend Server da dung lai bat ngo!
    echo     Nguyen nhan co the:
    echo       - Cong 8000 dang bi chiem boi chuong trinh khac
    echo       - Thu vien Python chua duoc cai dat day du
    echo       - Loi cau hinh he thong
    echo.
    echo     Thu chay lai hoac xoa thu muc .venv roi cai dat lai.
    echo ==============================================================================
)

echo.
echo [*] He thong da dung. Nhan phim bat ky de dong cua so nay.
pause
