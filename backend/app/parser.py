from tree_sitter import Language, Parser
import tree_sitter_python

# Load the Python Language
# In 0.23+, Language() takes the language object directly
PY_LANGUAGE = Language(tree_sitter_python.language())

# Initialize the Parser with the language
parser = Parser(PY_LANGUAGE)

def parse_code_dependencies(code: str):
    # Parse the code into a tree
    tree = parser.parse(bytes(code, "utf8"))
    
    # Define the search query for imports
    query_scm = """
    (import_statement
        name: (dotted_name) @import_name)
    
    (import_from_statement
        module_name: (dotted_name) @from_import)
    """
    
    # Create the query object
    query = PY_LANGUAGE.query(query_scm)
    
    # Execute query on the root node
    # .captures() returns a dictionary in version 0.23+
    captures = query.captures(tree.root_node)

    dependencies = []
    
    # In 0.23+, captures is a dict: {'capture_name': [nodes]}
    for capture_name, nodes in captures.items():
        for node in nodes:
            dep_name = code[node.start_byte : node.end_byte]
            dependencies.append(dep_name)
        
    return list(set(dependencies))