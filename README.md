# API de Automação Python

API REST para automação de mouse e teclado com Python.

Suporta criação de executável Windows (.exe) que roda sem precisar instalar Python!

## 📋 Requisitos

- Python 3.13+ (ou Python 3.8+)
- python3-venv
- Dependências do sistema instaladas

## 🚀 Instalação

1. Instale as dependências do sistema (Ubuntu/Debian):
```bash
sudo apt install -y python3.13-venv python3-tk python3-dev scrot
```

2. Crie o ambiente virtual:
```bash
python3 -m venv .venv
```

3. Ative o ambiente virtual e instale as dependências:
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

4. Para o reconhecimento de imagem no `/click`, você precisará do arquivo `assets/button.png`.

## ▶️ Executando a API

### Opção 1: Usando o script (Linux - recomendado)
```bash
./scripts/run.sh
```

### Opção 2: Manualmente
```bash
source .venv/bin/activate
python3 main.py
```

### Opção 3: Windows executável
```cmd
python scripts/build_windows.py
```
Isso gerará `dist\automacao-api.exe` que pode rodar em qualquer Windows sem Python instalado.

A API estará disponível em: `http://localhost:5001`

Documentação interativa: `http://localhost:5001/docs`

## 🪟 Criar Executável Windows

Para criar um executável que roda no Windows sem precisar instalar Python:

**No Windows:**
1. Instale Python (https://www.python.org/downloads/) - marque "Add to PATH"
2. Execute: `scripts\\build_windows.bat` (duplo clique) OU `python scripts/build_windows.py`
3. O executável será criado em: `dist\automacao-api.exe`
4. Copie a pasta `dist\` para qualquer PC Windows e execute!

**Distribuir:** Basta copiar a pasta `dist\` com o executável para outro PC Windows. Não precisa instalar nada!

## 🔐 Autenticação

Todos os endpoints requerem o código de autenticação: `aa22`

## 📡 Endpoints

### POST `/click`

Busca um botão na tela (imagem `assets/button.png`), clica nele e move o mouse para x:1000 y:0

**Request:**
```json
{
  "code": "aa22"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Click processed successfully",
  "data": {
    "buttonFound": true,
    "buttonPosition": {"x": 500, "y": 300},
    "finalPosition": {"x": 1000, "y": 0},
    "message": "Button clicked and mouse moved to target position"
  }
}
```

### POST `/run-auto`

Executa o comando Ctrl+C

**Request:**
```json
{
  "code": "aa22"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Run-auto command executed successfully",
  "data": {
    "command": "Ctrl+C",
    "message": "Copy command executed"
  }
}
```

### POST `/kill`

Aperta ESC, aguarda 3 segundos e executa Alt+F4

**Request:**
```json
{
  "code": "aa22"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Kill command executed successfully",
  "data": {
    "commands": ["ESC", "Wait 3s", "Alt+F4"],
    "message": "Kill sequence completed successfully"
  }
}
```

## 🔧 Testando

### Com curl:

```bash
# Testar /click
curl -X POST http://localhost:5001/click \
  -H "Content-Type: application/json" \
  -d '{"code": "aa22"}'

# Testar /run-auto
curl -X POST http://localhost:5001/run-auto \
  -H "Content-Type: application/json" \
  -d '{"code": "aa22"}'

# Testar /kill
curl -X POST http://localhost:5001/kill \
  -H "Content-Type: application/json" \
  -d '{"code": "aa22"}'
```

### Com Python:

```python
import requests

url = "http://localhost:5001"
headers = {"Content-Type": "application/json"}
data = {"code": "aa22"}

# Testar /click
response = requests.post(f"{url}/click", json=data)
print(response.json())

# Testar /run-auto
response = requests.post(f"{url}/run-auto", json=data)
print(response.json())

# Testar /kill
response = requests.post(f"{url}/kill", json=data)
print(response.json())
```

## ⚠️ Notas Importantes

- **FAILSAFE**: Mova o mouse para o canto superior esquerdo da tela para interromper qualquer automação em caso de emergência
- **assets/button.png**: Certifique-se de ter uma imagem `button.png` em `assets/` do botão que deseja encontrar na tela
- **Permissões**: No Linux, pode ser necessário instalar dependências adicionais para o pyautogui funcionar corretamente

### Dependências Linux:

```bash
sudo apt install -y python3.13-venv python3-tk python3-dev scrot
```

