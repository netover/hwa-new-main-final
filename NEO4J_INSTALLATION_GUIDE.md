# Neo4j Installation Guide for RAG Microservice

## Overview
The RAG microservice requires Neo4j with a vector index for semantic search functionality. This guide provides step-by-step instructions to install and configure Neo4j on Windows.

## Prerequisites
- Windows 10 or 11
- Internet connection
- Administrative privileges

## Step 1: Download Neo4j Desktop

1. Open your web browser and navigate to: https://neo4j.com/download/
2. Under "Neo4j Desktop", click the "Download" button for Windows
3. Save the installer file (neo4j-desktop-setup.exe) to your Downloads folder

## Step 2: Install Neo4j Desktop

1. Navigate to your Downloads folder
2. Double-click on "neo4j-desktop-setup.exe"
3. Follow the installation wizard:
   - Accept the license agreement
   - Choose installation location (default recommended)
   - Click "Install"
4. Wait for installation to complete
5. Click "Finish"

## Step 3: Launch Neo4j Desktop and Create Database

1. Open Neo4j Desktop from the Start Menu
2. Click "New Database" button
3. Configure the database:
   - Name: "RAG" (or any name you prefer)
   - Version: Select "5.20.0" (or latest available)
   - Password: Set a secure password (remember this!)
4. Click "Create"
5. Wait for the database to download and install
6. Once installed, click "Start" to start the database

## Step 4: Verify Neo4j is Running

1. In Neo4j Desktop, ensure the database status shows "Running"
2. Click "Open" to open the Neo4j Browser
3. In the browser, run the following query:
   ```cypher
   CALL dbms.components()
   ```
4. Verify that Neo4j is running and the version matches what you installed

## Step 5: Configure Application Settings

Update your application configuration to match your Neo4j setup:

1. Open `resync/settings.py`
2. Locate the `neo4j_uri` setting and update it:
   ```python
   neo4j_uri: str = Field(
       default="bolt://localhost:7687", 
       description="URI de conexão Neo4j"
   )
   ```
3. If you set a password during database creation, update the `neo4j_password`:
   ```python
   neo4j_password: str = Field(
       default="your_password_here", 
       min_length=1, 
       description="Senha Neo4j"
   )
   ```

## Step 6: Create the Vector Index

1. Open a command prompt in the project root directory
2. Run the vector index creation script:
   ```bash
   python init_neo4j_vector_index.py
   ```
3. You should see output confirming the index was created successfully:
   ```
   Vector index 'embedding_index' created successfully!
   Index found: {'name': 'embedding_index', 'type': 'VECTOR', 'labelsOrTypes': ['Content'], 'properties': ['content'], 'options': {'vector.dimensions': 1536, 'vector.similarity_function': 'cosine'}}
   ```

## Step 7: Verify RAG Functionality

1. Start your application:
   ```bash
   uvicorn resync.main:app --reload
   ```
2. Test the RAG service by uploading a file to http://localhost:8003/api/v1/upload
3. Test semantic search by sending a POST request to http://localhost:8003/api/v1/search with a query

## Troubleshooting

### Connection Issues
- Ensure Neo4j Desktop shows the database as "Running"
- Check that the port (7687) is not blocked by firewall
- Verify the URI in settings.py matches your Neo4j configuration

### Authentication Issues
- Ensure the password in settings.py matches the one set in Neo4j Desktop
- Try resetting the password in Neo4j Desktop if needed

### Vector Index Creation Fails
- Ensure you're using Neo4j version 5.0 or higher (vector indexes require 5.0+)
- Verify the database is running before running the script
- Check that the database name in the script matches your database

## Important Notes

- Neo4j Desktop is for development and testing
- For production, consider using Neo4j Aura (cloud) or Neo4j Enterprise
- The vector index requires 1536 dimensions to match OpenAI's text-embedding-3-small model
- The cosine similarity function is recommended for semantic search
- Always backup your Neo4j database regularly

## Next Steps

After successfully creating the vector index:
1. Verify the filesystem configuration (create resync/RAG/BASE and resync/RAG/UPLOADS directories)
2. Update the RAG service URL in settings.py to http://localhost:8003
3. Test the complete RAG workflow with file upload and semantic search

Congratulations! You've successfully configured Neo4j for the RAG microservice.