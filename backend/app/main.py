import os
import zipfile
import shutil
from contextlib import asynccontextmanager
import google.generativeai as genai 
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from neo4j import GraphDatabase

# Internal imports
from app.parser import get_dependencies
from app.database import store_dependencies, close_driver, get_graph_data

# --- 1. SETTINGS & MODELS ---
class Settings(BaseSettings):
    gemini_api_key: str
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://arch_neo4j:7687") # Default to container name
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "password123")
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()

class AnalysisRequest(BaseModel):
    node_name: str
    code_context: str = ""

# --- 2. DATABASE DRIVER ---
driver = GraphDatabase.driver(settings.neo4j_uri, auth=("neo4j", settings.neo4j_password))

def universal_scan(target_directory):
    """Wipes database and re-scans directory structure."""
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    
    IGNORE_LIST = {'.git', 'node_modules', '__pycache__', '.venv', 'dist', 'build'}

    for root, dirs, files in os.walk(target_directory):
        dirs[:] = [d for d in dirs if d not in IGNORE_LIST]
        for file in files:
            if file.endswith(('.py', '.js', '.ts', '.cpp', '.h')): 
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', errors='ignore') as f:
                        content = f.read()
                    
                    # FIX 1: Pass BOTH filename and content to the parser
                    deps = get_dependencies(file, content)
                    
                    store_dependencies(file, deps, content=content)
                    print(f"Scanned {file} -> Found {len(deps)} imports")
                except Exception as e:
                    print(f"DEBUG: Failed to read {file}: {e}")

# --- 3. LIFESPAN ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    driver.close()

app = FastAPI(title="Code Archaeologist Pro", lifespan=lifespan)
# Configure GenAI globally
genai.configure(api_key=settings.gemini_api_key)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for debugging
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
        
        universal_scan(temp_dir)
        return {"message": "Project excavated successfully!"}
    except Exception as e:
        print(f"Upload Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/graph")
def get_graph():
    """
    FIX 2: Use the robust function from database.py that correctly gets EDGES.
    """
    return get_graph_data()

# FIX 3: Model Rotation Logic to prevent 429 Errors
MODEL_POOL = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-flash-8b"]

@app.post("/ai/explain")
async def explain_module(request: AnalysisRequest):
    """Explains a specific artifact's implementation with fallback."""
    prompt = f"Analyze this software module: '{request.node_name}'. Context:\n{request.code_context}\nExplain its implementation role."

    last_error = ""
    for model_name in MODEL_POOL:
        try:
            # Create a model instance for this specific version
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return {"analysis": response.text, "model_used": model_name}
        except Exception as e:
            last_error = str(e)
            if "429" in last_error or "RESOURCE_EXHAUSTED" in last_error:
                print(f"Model {model_name} exhausted. Switching...")
                continue # Try next model
            break # Stop for other errors (like auth)
            
    raise HTTPException(status_code=429, detail=f"All AI models busy. Last error: {last_error}")

@app.post("/ai/search")
async def semantic_search(query: str):
    """Semantic search with Archaeological Era classification."""
    # Updated query to match the relationship type [:IMPORTS]
    db_query = "MATCH (f:File) RETURN f.name as name, left(f.code, 1000) as snippet"
    with driver.session() as session:
        files = [record.data() for record in session.run(db_query)]

    if not files: return {"results": []}

    context_str = "\n".join([f"File: {f['name']}\nCode: {f['snippet']}" for f in files])
    prompt = f"Identify files related to: '{query}'. Context: {context_str}\nCategorize as: Ancient, Stable, or Active. Return format: filename|age (comma separated)."

    try:
        # Use a lightweight model for search
        model = genai.GenerativeModel('gemini-1.5-flash-8b')
        response = model.generate_content(prompt)
        raw_results = [item.strip() for item in response.text.split(",") if "|" in item]
        final_results = [{"name": i.split("|")[0], "age": i.split("|")[1]} for i in raw_results]
        return {"results": final_results}
    except Exception:
        return {"results": []}

@app.get("/ai/refactor-analysis")
async def refactor_audit():
    """System-wide audit for God Modules."""
    # FIX 4: Query updated to use [:IMPORTS] instead of [:DEPENDS_ON]
    db_query = """
    MATCH (n:File)-[r:IMPORTS]->()
    WITH n, count(r) as complexity
    WHERE complexity > 2
    RETURN n.name as file, n.code as code, complexity
    """
    with driver.session() as session:
        complex_files = [record.data() for record in session.run(db_query)]

    if not complex_files:
        return {"refactor_report": [{"file": "System", "suggestion": "Architecture appears modular and stable."}]}

    report = []
    # Use standard Flash model for reasoning
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    for f in complex_files:
        prompt = f"Audit this highly coupled file: {f['file']}. Complexity Score: {f['complexity']}. Code:\n{f['code']}\nSuggest a refactoring plan."
        try:
            response = model.generate_content(prompt)
            report.append({"file": f['file'], "suggestion": response.text})
        except:
            report.append({"file": f['file'], "suggestion": "Analysis unavailable due to load."})

    return {"refactor_report": report}

@app.post("/cleanup")
async def cleanup_database():
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    return {"message": "Site cleared."}