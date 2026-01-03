from neo4j import GraphDatabase
import os
from datetime import datetime

# Connection Configuration
# Uses environment variables for Render compatibility, defaults to localhost for dev
URI = os.getenv("NEO4J_URI", "bolt://arch_neo4j:7687")
AUTH = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password123"))

# Initialize Driver
try:
    driver = GraphDatabase.driver(URI, auth=AUTH)
    # Verify connection immediately
    driver.verify_connectivity()
    print(f"Connected to Neo4j at {URI}")
except Exception as e:
    print(f"Failed to create Neo4j driver: {e}")
    driver = None

def store_dependencies(filename, dependencies, content=""):
    """
    Stores a file node and its import relationships safely.
    Fixes the issue where empty dependencies caused the save to fail.
    """
    if driver is None:
        print("Database driver is not initialized.")
        return

    # "Safe Query": Handles empty dependency lists using CASE
    # If $deps is empty, it unwinds [null] so the query continues to create the main file node
    query = """
    MERGE (f:File {name: $filename})
    SET f.code = $content, f.last_analyzed = datetime()
    WITH f
    UNWIND (CASE WHEN size($deps) = 0 THEN [null] ELSE $deps END) AS dep_name
    WITH f, dep_name
    WHERE dep_name IS NOT NULL
    MERGE (d:File {name: dep_name})
    MERGE (f)-[:IMPORTS]->(d)
    """
    
    try:
        with driver.session() as session:
            session.run(query, filename=filename, deps=dependencies, content=content)
        print(f"Successfully stored {filename} with {len(dependencies)} imports.")
    except Exception as e:
        print(f"Database Error in store_dependencies: {e}")

def get_graph_data():
    """
    Fetches nodes and edges for the frontend.
    Fixes the 'No Connections' bug by explicitly querying relationships.
    """
    if driver is None:
        return {"nodes": [], "edges": []}

    # OPTIONAL MATCH ensures we get isolated nodes (files with no imports) too
    query = """
    MATCH (n:File)
    OPTIONAL MATCH (n)-[r:IMPORTS]->(m:File)
    RETURN n, r, m
    """
    
    nodes_dict = {}
    edges_list = []
    
    try:
        with driver.session() as session:
            result = session.run(query)
            
            for record in result:
                # 1. Process Source Node
                source_node = record["n"]
                if source_node:
                    nodes_dict[source_node["name"]] = {
                        "id": source_node["name"],
                        "label": source_node["name"],
                        "code": source_node.get("code", ""),
                        "age": str(source_node.get("last_analyzed", "Stable"))
                    }
                
                # 2. Process Target Node (if exists)
                target_node = record["m"]
                if target_node:
                    nodes_dict[target_node["name"]] = {
                        "id": target_node["name"],
                        "label": target_node["name"],
                        "code": target_node.get("code", ""),
                        "age": str(target_node.get("last_analyzed", "Stable"))
                    }
                
                # 3. Process Relationship (The Edge)
                rel = record["r"]
                if rel:
                    edge_id = f"e_{source_node['name']}_{target_node['name']}"
                    edges_list.append({
                        "id": edge_id,
                        "source": source_node["name"],
                        "target": target_node["name"],
                        "animated": True,
                        "style": {"stroke": "#94a3b8", "strokeWidth": 2}
                    })
                    
        return {
            "nodes": list(nodes_dict.values()), 
            "edges": edges_list
        }
        
    except Exception as e:
        print(f"Database Error in get_graph_data: {e}")
        return {"nodes": [], "edges": []}

def clear_database():
    """
    Wipes the database clean.
    """
    if driver is None: return
    query = "MATCH (n) DETACH DELETE n"
    try:
        with driver.session() as session:
            session.run(query)
        print("Database cleared.")
    except Exception as e:
        print(f"Error clearing database: {e}")

def close_driver():
    if driver:
        driver.close()