import os
from neo4j import GraphDatabase

# The "Archaeology Brush": Files/Folders we ignore to avoid cluttering the graph
IGNORE_LIST = {'.git', 'node_modules', '__pycache__', '.venv', 'dist', 'build'}

def universal_scan(target_directory):
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))
    
    with driver.session() as session:
        # 1. Clear the old "site" to avoid mixing project ruins
        session.run("MATCH (n) DETACH DELETE n")
        
        # 2. Walk through every folder in the provided path
        for root, dirs, files in os.walk(target_directory):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if d not in IGNORE_LIST]
            
            for file in files:
                if file.endswith(('.py', '.js', '.ts', '.cpp', '.h')): # Supported Artifacts
                    file_path = os.path.join(root, file)
                    with open(file_path, 'r', errors='ignore') as f:
                        content = f.read()
                    
                    # 3. Create the Node with its raw content for the "Code Lens"
                    session.run("""
                        MERGE (f:File {name: $name})
                        SET f.code = $code, f.path = $path
                    """, name=file, code=content, path=file_path)

        # 4. Infer Relationships (Simple import-based archaeology)
        # (This logic would look for 'import' or 'require' strings in the saved f.code)
    driver.close()