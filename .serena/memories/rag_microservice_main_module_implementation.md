if __name__ == "__main__":
    import uvicorn
    import sys
    import os
    from pathlib import Path

    # Garantir que estamos no diretório correto
    current_dir = Path(__file__).parent
    os.chdir(current_dir)

    # Adicionar ao path se necessário
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))

    try:
        # Importar e executar o app
        from main import app

        print("🚀 Iniciando RAG Microservice...")
        print(f"📁 Diretório de trabalho: {current_dir}")
        print(f"🐍 Python path: {sys.path[0]}")
        print("🌐 URL: http://localhost:8001")
        print("📊 Health check: http://localhost:8001/api/v1/health")
        print("📤 Upload endpoint: http://localhost:8001/api/v1/upload")
        print("🔍 Search endpoint: http://localhost:8001/api/v1/search")
        print("⏹️  Pressione Ctrl+C para parar")

        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8001,
            reload=True,
            log_level="info"
        )

    except ImportError as e:
        print(f"❌ Erro de importação: {e}")
        print("💡 Certifique-se de que todas as dependências estão instaladas:")
        print("   pip install -r requirements.txt")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 RAG Microservice parado pelo usuário")
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        sys.exit(1)