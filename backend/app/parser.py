import tree_sitter_python
from tree_sitter import Language, Parser

# Initialize the Python Language
# In standard tree-sitter bindings, we pass the language object directly
PY_LANGUAGE = Language(tree_sitter_python.language())
parser = Parser(PY_LANGUAGE)

def get_dependencies(filename, code: str):
    """
    Parses Python code to find imports. 
    Fixes byte-slicing errors and normalizes names to match file nodes.
    """
    # 1. CRITICAL: Encode to bytes because Tree-sitter works on bytes
    # If we don't do this, byte offsets will slice the string incorrectly
    source_bytes = bytes(code, "utf8")
    
    try:
        tree = parser.parse(source_bytes)
    except Exception as e:
        print(f"Parser Error on {filename}: {e}")
        return []

    # Query to capture 'import x' and 'from x import y'
    query_scm = """
    (import_statement
        name: (dotted_name) @import_name)
    
    (import_from_statement
        module_name: (dotted_name) @from_import)
    
    (import_from_statement
        module_name: (relative_import) @relative_import)
    """
    
    query = PY_LANGUAGE.query(query_scm)
    captures = query.captures(tree.root_node)

    dependencies = set()

    # 2. CRITICAL FIX: 'captures' is a LIST of TUPLES [(Node, str)], not a dict
    # We unpack (node, capture_name)
    for node, capture_name in captures:
        # 3. CRITICAL FIX: Slice the BYTES, then decode back to string
        # Slicing the 'code' string directly with byte offsets is unsafe
        raw_name = source_bytes[node.start_byte : node.end_byte].decode("utf8")
        
        # Clean the name
        clean_name = raw_name.strip()
        
        # 4. Filter out standard library (Optional, keeps graph clean)
        if clean_name in ['os', 'sys', 'json', 'datetime', 'typing', 'fastapi']:
            continue

        # 5. CONNECTIVITY FIX: Normalize names to match your graph nodes
        # If we find "utils", we must save it as "utils.py" to match the file node
        if not clean_name.endswith('.py'):
            clean_name += ".py"
            
        # Handle relative imports like 'from . import config' -> 'config.py'
        if clean_name.startswith('.'):
            clean_name = clean_name.lstrip('.')

        # Don't let a file depend on itself
        if clean_name != filename:
            dependencies.add(clean_name)

    # Debug print to see what the backend is actually finding
    print(f"Parsed {filename} -> found: {list(dependencies)}")
    
    return list(dependencies)