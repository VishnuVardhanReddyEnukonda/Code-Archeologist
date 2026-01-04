import tree_sitter_python
from tree_sitter import Language, Parser

# Initialize the Python Language
PY_LANGUAGE = Language(tree_sitter_python.language())
parser = Parser(PY_LANGUAGE)

def get_dependencies(filename, code: str):
    source_bytes = bytes(code, "utf8")
    
    try:
        tree = parser.parse(source_bytes)
    except Exception as e:
        print(f"Parser Error on {filename}: {e}")
        return []

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

    for node, _ in captures:
        raw_name = source_bytes[node.start_byte : node.end_byte].decode("utf8")
        clean_name = raw_name.strip()
        
        if not clean_name:
            continue

        # 1. First, handle relative imports by removing leading dots
        clean_name = clean_name.lstrip('.')

        # 2. Second, handle dotted imports (e.g., utils.logger -> utils)
        # We take the base module name to match your file-based graph nodes
        if "." in clean_name and not clean_name.endswith('.py'):
            clean_name = clean_name.split('.')[0]
        
        # 3. Finally, ensure it has the .py extension to prevent ghost nodes
        if not clean_name.endswith('.py'):
            clean_name += ".py"

        # Avoid self-references
        if clean_name != filename:
            dependencies.add(clean_name)

    print(f"Parsed {filename} -> found: {list(dependencies)}")
    return list(dependencies)