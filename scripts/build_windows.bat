@echo off
REM Script para gerar executável Windows da API

pushd "%~dp0.."

echo ==============================================
echo    Gerando executavel da API de Automacao
echo ==============================================
echo.

REM Verifica se Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python nao encontrado!
    echo Por favor, instale Python de python.org
    pause
    exit /b 1
)

echo ✓ Python encontrado
echo.

REM Instala dependências
echo 📦 Instalando dependencias...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller
echo.

REM Limpa builds anteriores
echo 🧹 Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo.

REM Gera o executável
echo 🔨 Gerando executavel...
python -m PyInstaller automacao-api-windows.spec
echo.

REM Verifica se foi criado
if exist "dist\automacao-api.exe" (
    echo.
    echo ✅ Executavel gerado com sucesso!
    echo.
    echo 📁 Localizacao: dist\automacao-api.exe
    echo.
    echo Para executar: Clique duas vezes em dist\automacao-api.exe
    echo A API estara disponivel em http://localhost:5001
    echo.
) else (
    echo.
    echo ❌ Erro ao gerar executavel
    echo.
)

pause
popd
