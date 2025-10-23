import sys
import os
import pytest

# Adiciona o diretório raiz ao PYTHONPATH
sys.path.insert(0, os.path.abspath("."))

# Executa os testes
if __name__ == "__main__":
    pytest.main(["-v", "resync/RAG/microservice/tests/"])