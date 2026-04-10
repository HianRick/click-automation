"""
Cliente de teste para a API de Automação
Execute este script para testar os endpoints da API
"""

import requests
import json

BASE_URL = "http://localhost:5001"
CODE = "aa22"


def test_root():
    """Testa o endpoint raiz"""
    print("\n=== Testando GET / ===")
    response = requests.get(f"{BASE_URL}/")
    print(f"Status: {response.status_code}")
    print(f"Resposta: {json.dumps(response.json(), indent=2)}")


def test_click():
    """Testa o endpoint /click"""
    print("\n=== Testando POST /click ===")
    data = {"code": CODE}
    response = requests.post(f"{BASE_URL}/click", json=data)
    print(f"Status: {response.status_code}")
    print(f"Resposta: {json.dumps(response.json(), indent=2)}")


def test_run_auto():
    """Testa o endpoint /run-auto"""
    print("\n=== Testando POST /run-auto ===")
    data = {"code": CODE}
    response = requests.post(f"{BASE_URL}/run-auto", json=data)
    print(f"Status: {response.status_code}")
    print(f"Resposta: {json.dumps(response.json(), indent=2)}")


def test_kill():
    """Testa o endpoint /kill"""
    print("\n=== Testando POST /kill ===")
    data = {"code": CODE}
    response = requests.post(f"{BASE_URL}/kill", json=data)
    print(f"Status: {response.status_code}")
    print(f"Resposta: {json.dumps(response.json(), indent=2)}")


def test_invalid_code():
    """Testa autenticação com código inválido"""
    print("\n=== Testando código inválido ===")
    data = {"code": "wrong_code"}
    response = requests.post(f"{BASE_URL}/click", json=data)
    print(f"Status: {response.status_code}")
    print(f"Resposta: {json.dumps(response.json(), indent=2)}")


if __name__ == "__main__":
    print("=" * 60)
    print("Cliente de Teste - API de Automação")
    print("=" * 60)
    print("\nCertifique-se de que a API está rodando em http://localhost:5001")
    print("Execute: ./scripts/run.sh em outro terminal\n")
    
    try:
        # Testa endpoint raiz
        test_root()
        
        # Aguarda input do usuário para continuar
        input("\nPressione Enter para testar /run-auto (Ctrl+C)...")
        test_run_auto()
        
        input("\nPressione Enter para testar /click (procura assets/button.png)...")
        test_click()
        
        input("\nPressione Enter para testar /kill (ESC + Alt+F4)...")
        test_kill()
        
        # Teste de autenticação
        input("\nPressione Enter para testar código inválido...")
        test_invalid_code()
        
        print("\n" + "=" * 60)
        print("Testes concluídos!")
        print("=" * 60)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ Erro: Não foi possível conectar à API.")
        print("Certifique-se de que a API está rodando com: ./scripts/run.sh")
    except KeyboardInterrupt:
        print("\n\nTestes interrompidos pelo usuário.")
