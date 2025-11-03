@echo off
echo Installing Neo4j Database Server...

REM Download Neo4j Desktop for Windows
powershell -Command "Invoke-WebRequest -Uri \"https://neo4j.com/product/neo4j-desktop/download/?version=5.20.0\" -OutFile \"neo4j-desktop-setup.exe\""

REM Install Neo4j Desktop silently
start /wait neo4j-desktop-setup.exe /S

REM Start Neo4j Desktop
"C:\Program Files\Neo4j Desktop\Neo4j Desktop.exe"

REM Wait for user to install and start Neo4j
pause

echo Please open Neo4j Desktop, create a new database, and start it.
echo Then run 'python init_neo4j_vector_index.py' to create the vector index.
echo The database should be accessible at bolt://localhost:7687