from neo4j import GraphDatabase
import os

# "arch_neo4j" is the name of the container defined in docker-compose
# Internal Docker networking uses the service name 'graph_db' or container name
URI = os.getenv("NEO4J_URI", "bolt://arch_neo4j:7687")
AUTH = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password123"))

# Create a connection driver
driver = GraphDatabase.driver(URI, auth=AUTH)

def store_dependencies(filename, dependencies, content=""):
    """
    Stores file nodes, their source code, and their import relationships.
    """
    if not dependencies:
        print(f"No dependencies found for {filename}")
        # We still MERGE the file itself so it appears in the graph even without imports
    
    # Combined query for atomic storage
    query = """
    MERGE (f:File {name: $filename})
    SET f.code = $content, f.last_analyzed = datetime()
    WITH f
    UNWIND $deps as dep_name
    MERGE (d:File {name: dep_name})
    MERGE (f)-[:IMPORTS]->(d)
    """
    
    try:
        with driver.session() as session:
            session.run(query, filename=filename, deps=dependencies, content=content)
        print(f"Successfully stored {filename} and {len(dependencies)} dependencies.")
    except Exception as e:
        print(f"Database Error: {e}")

def close_driver():
    driver.close()