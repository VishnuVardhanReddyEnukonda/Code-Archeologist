import os
import zipfile
import shutil
from contextlib import asynccontextmanager
from google import genai 
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from neo4j import GraphDatabase

# Internal imports
from app.parser import get_dependencies
from app.database import store_dependencies

# --- 1. SETTINGS & MODELS ---
class Settings(BaseSettings):
    gemini_api_key: str
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://arch_neo4j:7687")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "password123")
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

class AnalysisRequest(BaseModel):
    node_name: str
    code_context: str = ""

# --- 2. DATABASE DRIVER & AI CLIENT ---
driver = GraphDatabase.driver(settings.neo4j_uri, auth=("neo4j", settings.neo4j_password))
# Use the 2026-compliant SDK
client = genai.Client(api_key=settings.gemini_api_key)

def universal_scan(target_directory):
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")

    for root, dirs, files in os.walk(target_directory):
        rel_root = os.path.relpath(root, target_directory)
        folder_id = "root" if rel_root == "." else rel_root

        for file in files:
            if file.endswith(('.py', '.js', '.ts', '.cpp', '.h')):
                unique_id = os.path.join(rel_root, file).replace("./", "")
                file_path = os.path.join(root, file)
                
                try:
                    with open(file_path, 'r', errors='ignore') as f:
                        content = f.read()
                    
                    deps = get_dependencies(unique_id, content)

                    with driver.session() as session:
                        # Map Hierarchy
                        session.run("""
                            MERGE (folder:Directory {name: $folder_id})
                            MERGE (file:File {name: $unique_id})
                            SET file.code = $code
                            MERGE (folder)-[:CONTAINS]->(file)
                        """, folder_id=folder_id, unique_id=unique_id, code=content)

                        # Map Logic
                        for dep in deps:
                            if dep and dep != ".py":
                                session.run("""
                                    MERGE (f:File {name: $unique_id})
                                    MERGE (t:File {name: $dep_name})
                                    MERGE (f)-[:IMPORTS]->(t)
                                """, unique_id=unique_id, dep_name=dep)
                except Exception as e:
                    print(f"DEBUG: Skipping {file}: {e}")

# --- 3. LIFESPAN ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Code Archaeologist Startup...")
    yield
    driver.close()

app = FastAPI(title="Code Archaeologist Pro", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 4. ENDPOINTS ---

@app.get("/")
def health_check():
    return {"status": "active", "system": "Code Archaeologist", "year": 2026}

@app.post("/upload-project")
async def upload_project(file: UploadFile = File(...)):
    temp_dir = "/tmp/excavation_site"
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)

    zip_path = os.path.join(temp_dir, "project.zip")
    try:
        with open(zip_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        extracted_items = os.listdir(temp_dir)
        scan_target = temp_dir
        for item in extracted_items:
            item_path = os.path.join(temp_dir, item)
            if os.path.isdir(item_path) and item not in ['__MACOSX']:
                scan_target = item_path
                break
        
        universal_scan(scan_target)
        return {"message": "Project excavated successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/graph")
def get_graph():
    nodes_query = "MATCH (n) RETURN n.name as id, labels(n)[0] as type, n.code as code, n.age as age"
    edges_query = "MATCH (n)-[r:IMPORTS|CONTAINS]->(m) RETURN n.name as source, m.name as target, type(r) as rel_type"
    
    nodes, edges = [], []
    with driver.session() as session:
        node_results = session.run(nodes_query)
        for record in node_results:
            nodes.append({
                "id": record["id"], 
                "label": record["id"], 
                "code": record["code"], 
                "type": record["type"],
                "age": record.get("age", "Stable")
            })
        
        edge_results = session.run(edges_query)
        for record in edge_results:
            edges.append({
                "id": f"e-{record['source']}-{record['target']}",
                "source": record["source"], 
                "target": record["target"], 
                "type": record["rel_type"]
            })
    return {"nodes": nodes, "edges": edges}

@app.post("/ai/explain")
async def explain_module(request: AnalysisRequest):
    prompt = f"Analyze this software module: '{request.node_name}'. Context:\n{request.code_context}\nExplain its implementation role."
    try:
        # Correct 2026 Client Call
        response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
        return {"analysis": response.text}
    except Exception as e:
        return {"analysis": f"AI unavailable ({str(e)})."}

@app.post("/ai/search")
async def semantic_search(query: str):
    db_query = "MATCH (f:File) RETURN f.name as name, left(f.code, 1000) as snippet"
    with driver.session() as session:
        files = [record.data() for record in session.run(db_query)]

    if not files: return {"results": []}

    context_str = "\n".join([f"File: {f['name']}\nCode: {f['snippet']}" for f in files])
    prompt = f"Identify files related to: '{query}'. Context: {context_str}\nReturn ONLY filename|age (comma separated)."

    try:
        response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
        raw_results = [item.strip() for item in response.text.split(",") if "|" in item]
        return {"results": [{"name": i.split("|")[0], "age": i.split("|")[1]} for i in raw_results]}
    except Exception:
        return {"results": []}

@app.get("/ai/refactor-analysis")
async def refactor_audit():
    db_query = "MATCH (n:File)-[r:IMPORTS]->() WITH n, count(r) as complexity WHERE complexity > 3 RETURN n.name as file, n.code as code, complexity"
    with driver.session() as session:
        complex_files = [record.data() for record in session.run(db_query)]

    if not complex_files:
        return {"refactor_report": [{"file": "System", "suggestion": "Architecture appears modular and stable."}]}

    report = []
    for f in complex_files:
        prompt = f"Audit this highly coupled file: {f['file']}. Code:\n{f['code']}\nSuggest refactoring."
        try:
            response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
            report.append({"file": f['file'], "suggestion": response.text})
        except:
            continue

    return {"refactor_report": report}

@app.post("/cleanup")
async def cleanup_database():
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    return {"message": "Site cleared."}