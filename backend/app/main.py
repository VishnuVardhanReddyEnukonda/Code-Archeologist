import os

import zipfile

import shutil

from contextlib import asynccontextmanager

import google as genai

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

    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://arch_neo4j:7687") # Default to container name for Render

    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "password123")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")



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

            if file.endswith(('.py', '.js', '.ts', '.cpp', '.h', '.java')):

                file_path = os.path.join(root, file)

                try:

                    with open(file_path, 'r', errors='ignore') as f:

                        content = f.read()

                   

                    # FIX 1: Pass filename AND content to parser

                    deps = get_dependencies(file, content)

                    store_dependencies(file, deps, content=content)

                    print(f"DEBUG: Scanned {file} -> {len(deps)} imports")

                except Exception as e:

                    print(f"DEBUG: Failed to read {file}: {e}")



# --- 3. LIFESPAN ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    # REMOVED genai.configure because it does not exist in the new SDK
    print("Code Archaeologist Startup...")
    yield
    driver.close()



app = FastAPI(title="Code Archaeologist Pro", lifespan=lifespan)



app.add_middleware(

    CORSMiddleware,

    allow_origins=["*"], # Allow all for production/dev compatibility

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

    """Returns nodes and edges using the correct relationship type."""

    # FIX 2: Use [:IMPORTS] to match what database.py saves

    nodes_query = "MATCH (n:File) RETURN n.name as id, n.code as code, n.age as age"

    edges_query = "MATCH (n:File)-[:IMPORTS]->(m:File) RETURN n.name as source, m.name as target"

   

    nodes, edges = [], []

    try:

        with driver.session() as session:

            node_results = session.run(nodes_query)

            for record in node_results:

                nodes.append({

                    "id": record["id"],

                    "label": record["id"],

                    "code": record["code"],

                    "age": record.get("age", "Stable")

                })

           

            edge_results = session.run(edges_query)

            for record in edge_results:

                edges.append({

                    "id": f"e-{record['source']}-{record['target']}",

                    "source": record["source"],

                    "target": record["target"],

                    "animated": True

                })

        return {"nodes": nodes, "edges": edges}

    except Exception as e:

        print(f"Graph Error: {e}")

        return {"nodes": [], "edges": []}



@app.post("/ai/explain")

async def explain_module(request: AnalysisRequest):

    """Explains a specific artifact's implementation."""

    prompt = f"Analyze this software module: '{request.node_name}'. Context:\n{request.code_context}\nExplain its implementation role."



    try:

        model = genai.GenerativeModel('gemini-2.0-flash')

        response = model.generate_content(prompt)

        return {"analysis": response.text}

    except Exception as e:

        # Graceful fallback for rate limits

        return {"analysis": f"AI unavailable ({str(e)}). Try again later."}



@app.post("/ai/search")

async def semantic_search(query: str):

    """Semantic search with Archaeological Era classification."""

    db_query = "MATCH (f:File) RETURN f.name as name, left(f.code, 1000) as snippet"

    with driver.session() as session:

        files = [record.data() for record in session.run(db_query)]



    if not files: return {"results": []}



    context_str = "\n".join([f"File: {f['name']}\nCode: {f['snippet']}" for f in files])

    prompt = f"Identify files related to: '{query}'. Context: {context_str}\nCategorize as: Ancient, Stable, or Active. Return format: filename|age (comma separated)."



    try:

        # Use Flash-Lite for speed/cost efficiency

        model = genai.GenerativeModel('gemini-1.5-flash')

        response = model.generate_content(prompt)

        raw_results = [item.strip() for item in response.text.split(",") if "|" in item]

        final_results = [{"name": i.split("|")[0], "age": i.split("|")[1]} for i in raw_results]

        return {"results": final_results}

    except Exception:

        return {"results": []}



@app.get("/ai/refactor-analysis")

async def refactor_audit():

    """System-wide audit for God Modules and technical debt."""

    # FIX 3: Use [:IMPORTS] to correctly find high-coupling nodes

    db_query = """

    MATCH (n:File)-[r:IMPORTS]->()

    WITH n, count(r) as complexity

    WHERE complexity > 3

    RETURN n.name as file, n.code as code, complexity

    """

    with driver.session() as session:

        complex_files = [record.data() for record in session.run(db_query)]



    if not complex_files:

        return {"refactor_report": [{"file": "System", "suggestion": "Architecture appears modular and stable."}]}



    report = []

    model = genai.GenerativeModel('gemini-2.0-flash')

   

    for f in complex_files:

        prompt = f"Audit this highly coupled file: {f['file']}. Complexity Score: {f['complexity']}. Code:\n{f['code']}\nSuggest a refactoring plan."

        try:

            response = model.generate_content(prompt)

            report.append({"file": f['file'], "suggestion": response.text})

        except:

             report.append({"file": f['file'], "suggestion": "Analysis skipped due to high load."})



    return {"refactor_report": report}



@app.post("/cleanup")

async def cleanup_database():

    with driver.session() as session:

        session.run("MATCH (n) DETACH DELETE n")

    return {"message": "Site cleared."}