"""
Create vector index for Neo4j RAG system
"""
import asyncio
import traceback

from neo4j import AsyncGraphDatabase

from resync.config.settings import settings


async def create_vector_index():
    """Create vector index for Neo4j RAG system"""
    driver = AsyncGraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )

    try:
        async with driver.session(database="rag") as session:
            # Create vector index for semantic search
            # This matches the expected index name in knowledge_graph.py
            result = await session.run(
                """
                CREATE VECTOR INDEX embedding_index FOR (c:Content) ON (c.content)
                OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}
                """
            )

            # Wait for index to be created
            await result.consume()

            print("Vector index 'embedding_index' created successfully!")

            # Verify index was created
            result = await session.run("""
                SHOW INDEXES YIELD name, type, labelsOrTypes, properties, options
                WHERE name = 'embedding_index'
                RETURN name, type, labelsOrTypes, properties, options
                """)

            records = await result.data()
            if records:
                print(f"Index found: {records[0]}")
            else:
                print("Index not found after creation")

    except Exception as e:
        print(f"Error creating vector index: {str(e)}")
        traceback.print_exc()
    finally:
        await driver.close()

if __name__ == "__main__":
    asyncio.run(create_vector_index())




