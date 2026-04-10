#!/bin/bash
# Script para executar a API de Automação

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# Ativa o ambiente virtual
source .venv/bin/activate

# Executa a API
python3 main.py
