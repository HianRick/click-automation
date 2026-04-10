"""
Script para criar executável Windows da API
Execute este script em um PC Windows com Python instalado
"""

import subprocess
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"
SPEC_FILE = PROJECT_ROOT / "automacao-api-windows.spec"

def check_python():
    """Verifica se Python está instalado"""
    print("🔍 Verificando Python...")
    print(f"Python {sys.version}")
    print(f"Localização: {sys.executable}")
    print()

def install_dependencies():
    """Instala as dependências necessárias"""
    print("📦 Instalando dependências...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)], cwd=str(PROJECT_ROOT))
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    print()

def build_exe():
    """Gera o executável"""
    print("🔨 Gerando executável Windows...")
    
    # Limpa builds anteriores
    if os.path.exists(PROJECT_ROOT / "build"):
        print("🧹 Limpando build anterior...")
        import shutil
        shutil.rmtree(PROJECT_ROOT / "build", ignore_errors=True)
    if os.path.exists(PROJECT_ROOT / "dist"):
        import shutil
        shutil.rmtree(PROJECT_ROOT / "dist", ignore_errors=True)
    
    # Gera o executável
    subprocess.check_call([sys.executable, "-m", "PyInstaller", str(SPEC_FILE)], cwd=str(PROJECT_ROOT))
    print()

def main():
    print("=" * 60)
    print("   Criador de Executável - API de Automação Windows")
    print("=" * 60)
    print()
    
    try:
        check_python()
        install_dependencies()
        build_exe()
        
        print("✅ Executável gerado com sucesso!")
        print()
        print("📁 Localização: dist\\automacao-api.exe")
        print()
        print("ℹ️  Para executar: Clique duas vezes em dist\\automacao-api.exe")
        print("    A API estará disponível em http://localhost:5001")
        print()
        
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        print("\nCertifique-se de que:")
        print("1. Python está instalado")
        print("2. A estrutura do projeto está intacta")
        print("3. Tem conexão com a internet para baixar dependências")
        sys.exit(1)

if __name__ == "__main__":
    main()
