import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { 
  ReactFlow, 
  Background, 
  Controls, 
  useNodesState, 
  useEdgesState,
  Panel,
  Handle,
  Position
} from '@xyflow/react';
import '@xyflow/react/dist/style.css'; 
import axios from 'axios';

// 1. DYNAMIC API URL
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const btnStyle = { padding: '8px 14px', background: '#4f46e5', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold', transition: 'all 0.2s', fontSize: '12px' };
const inputStyle = { padding: '8px', borderRadius: '4px', border: '1px solid #334155', background: '#1e293b', color: '#fff', outline: 'none', width: '180px' };

// --- CUSTOM NODE COMPONENT (The missing piece for Edges) ---
const FileNode = ({ data }) => {
  return (
    <div style={{ 
      background: '#6366f1', 
      color: '#fff', 
      padding: '10px', 
      borderRadius: '8px', 
      border: '1px solid #4338ca',
      minWidth: '120px',
      textAlign: 'center',
      position: 'relative',
      boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
    }}>
      {/* Target Handle (Top) - Recieves connections */}
      <Handle type="target" position={Position.Top} style={{ background: '#cbd5e1', width: '10px', height: '10px' }} />
      
      <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>{data.label}</div>
      <div style={{ fontSize: '10px', opacity: 0.8, textTransform: 'uppercase' }}>{data.age}</div>

      {/* Source Handle (Bottom) - Sends connections */}
      <Handle type="source" position={Position.Bottom} style={{ background: '#cbd5e1', width: '10px', height: '10px' }} />
    </div>
  );
};

export default function Flow() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [aiAnalysis, setAiAnalysis] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [refactorReport, setRefactorReport] = useState([]);
  const [isAuditing, setIsAuditing] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  // Register the custom node type
  const nodeTypes = useMemo(() => ({ fileNode: FileNode }), []);

  // 2. Sync Graph from Backend
  const fetchGraph = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE_URL}/graph?t=${new Date().getTime()}`);
      const { nodes: newNodes, edges: newEdges } = res.data;

      console.log("DEBUG: Backend sent edges:", newEdges); // CHECK CONSOLE IF THIS IS EMPTY!

      setNodes(newNodes.map(n => ({
        id: n.id,
        type: 'fileNode', // <--- IMPORTANT: Use our custom node
        data: { label: n.label, code: n.code, age: n.age || 'Stable' }, 
        // Random position fallback if backend doesn't provide layout
        position: { x: Math.random() * 600 + 50, y: Math.random() * 400 + 50 },
      })));

      setEdges(newEdges.map((e, i) => ({ 
        id: e.id || `e${i}`, // Use backend ID if available
        source: e.source,
        target: e.target,
        animated: true, 
        style: { stroke: '#94a3b8', strokeWidth: 2 },
        type: 'default' 
      })));
    } catch (err) {
      console.error("Graph Sync Error:", err);
    }
  }, [setNodes, setEdges]);

  // 3. Clear Database
  const handleCleanup = async () => {
    if (window.confirm("Are you sure you want to clear all excavated artifacts?")) {
      try {
        await axios.post(`${API_BASE_URL}/cleanup`);
        setNodes([]);
        setEdges([]);
        setSelectedNodeId(null);
        setAiAnalysis("Workspace cleared.");
      } catch (err) {
        console.error("Cleanup failed", err);
      }
    }
  };

  // 4. File Upload
  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      setAiAnalysis("Re-excavating artifacts...");
      await axios.post(`${API_BASE_URL}/upload-project`, formData);
      await new Promise(resolve => setTimeout(resolve, 1000)); 
      await fetchGraph(); 
      event.target.value = null; 
      alert("Excavation Complete!");
    } catch (err) {
      alert("Extraction failed.");
    } finally {
      setIsUploading(false);
    }
  };

  // 5. Semantic Search
  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setIsSearching(true); 
    try {
      const res = await axios.post(`${API_BASE_URL}/ai/search?query=${searchQuery}`);
      const matchedData = res.data.results;

      setNodes((nds) =>
        nds.map((node) => {
          const match = matchedData.find(m => 
            node.data.label.toLowerCase().includes(m.name.toLowerCase())
          );
          return {
            ...node,
            data: { ...node.data, age: match ? match.age : node.data.age },
            // Highlight visually via props if passing to custom node, or force update
          };
        })
      );
    } catch (err) {
      console.error("Search failed:", err);
    } finally {
      setIsSearching(false); 
    }
  };

  // 6. Audit Logic
  const runRefactorAudit = async () => {
    setIsAuditing(true);
    setSelectedNodeId(null);
    try {
      const res = await axios.get(`${API_BASE_URL}/ai/refactor-analysis`);
      setRefactorReport(res.data.refactor_report);
    } catch (err) {
      console.error(err);
    } finally {
      setIsAuditing(false);
    }
  };

  // 7. Explain Artifacts
  const onNodeClick = useCallback(async (_, node) => {
    setSelectedNodeId(node.id);
    setAiAnalysis("Analyzing artifact context...");
    
    // Simple visual highlighting
    const connectedEdges = edges.filter(e => e.source === node.id || e.target === node.id);
    const connectedNodeIds = new Set([node.id, ...connectedEdges.flatMap(e => [e.source, e.target])]);

    setNodes(nds => nds.map(n => ({
      ...n,
      style: { ...n.style, opacity: connectedNodeIds.has(n.id) ? 1 : 0.25 }
    })));

    try {
      const res = await axios.post(`${API_BASE_URL}/ai/explain`, {
        node_name: node.data.label,
        code_context: node.data.code || "" 
      });
      setAiAnalysis(res.data.analysis);
    } catch (err) {
      setAiAnalysis("AI analysis offline.");
    }
  }, [edges, setNodes]);

  const selectedNode = nodes.find(n => n.id === selectedNodeId);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  return (
    <div style={{ width: '100vw', height: '100vh', display: 'flex', background: '#0f172a', fontFamily: 'Inter, sans-serif' }}>
      <style>{`
        @keyframes fadeIn { from { opacity: 0; transform: translateX(20px); } to { opacity: 1; transform: translateX(0); } }
        .era-badge { font-size: 10px; padding: 4px 10px; border-radius: 20px; font-weight: bold; text-transform: uppercase; }
      `}</style>

      <div style={{ flex: 1, position: 'relative' }}>
        <ReactFlow 
          nodes={nodes} 
          edges={edges} 
          nodeTypes={nodeTypes} // <--- This enables the Custom Node
          onNodesChange={onNodesChange} 
          onEdgesChange={onEdgesChange} 
          onNodeClick={onNodeClick} 
          fitView
        >
          <Background color="#1e293b" variant="dots" gap={20} />
          <Controls />
          
          <Panel position="top-left" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', gap: '10px', background: '#1e293b', padding: '12px', borderRadius: '10px', border: '1px solid #334155' }}>
              <input type="text" placeholder="Search intent..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} style={inputStyle} />
              <button onClick={handleSearch} style={btnStyle} disabled={isSearching}>{isSearching ? "..." : "🔍"}</button>
              
              <label style={{...btnStyle, background: '#10b981', display: 'flex', alignItems: 'center', gap: '5px'}}>
                {isUploading ? "Digging..." : "📁 ZIP"}
                <input type="file" accept=".zip" onChange={handleFileUpload} style={{display: 'none'}} />
              </label>

              <button onClick={fetchGraph} style={{...btnStyle, background: '#334155'}}>Sync</button>
              <button onClick={handleCleanup} style={{...btnStyle, background: '#ef4444'}}>Clear</button>
              <button onClick={runRefactorAudit} style={{...btnStyle, background: '#7c3aed'}} disabled={isAuditing}>
                {isAuditing ? "Auditing..." : "Audit"}
              </button>
            </div>
            <div style={{ display: 'flex', gap: '10px', fontSize: '10px', color: '#94a3b8' }}>
              <span>📜 Ancient</span><span>⚖️ Stable</span><span>⚡ Active</span>
            </div>
          </Panel>
        </ReactFlow>
      </div>

      {(selectedNode || refactorReport.length > 0) && (
        <div style={{ width: '400px', background: '#1e293b', color: '#fff', padding: '20px', overflowY: 'auto', borderLeft: '1px solid #334155', animation: 'fadeIn 0.3s ease' }}>
          {selectedNode && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h2 style={{ color: '#818cf8', margin: 0 }}>{selectedNode.data.label}</h2>
                <button onClick={() => { setSelectedNodeId(null); setNodes(nds => nds.map(n => ({...n, style: {...n.style, opacity: 1}}))); }} style={{ color: '#94a3b8', background: 'none', border: 'none', cursor: 'pointer', fontSize: '24px' }}>×</button>
              </div>
              <span className="era-badge" style={{ background: selectedNode.data.age === 'Ancient' ? '#4b5563' : '#2563eb', marginTop: '10px', display: 'inline-block' }}>
                ERA: {selectedNode.data.age}
              </span>
              <div style={{ background: '#0f172a', padding: '15px', borderRadius: '8px', fontSize: '11px', marginTop: '20px', border: '1px solid #334155', color: '#cbd5e1', fontFamily: 'monospace' }}>
                {selectedNode.data.code ? selectedNode.data.code.substring(0, 200) + "..." : "// No artifacts."}
              </div>
              <hr style={{ borderColor: '#334155', margin: '20px 0' }} />
              <div style={{ whiteSpace: 'pre-wrap', fontSize: '13px', lineHeight: '1.6' }}>{aiAnalysis}</div>
            </div>
          )}
          {refactorReport.length > 0 && !selectedNode && (
            <div>
              <h2 style={{ color: '#fbbf24' }}>Architectural Audit</h2>
              {refactorReport.map((r, i) => (
                <div key={i} style={{ background: '#0f172a', padding: '15px', marginBottom: '15px', borderRadius: '8px', borderLeft: '4px solid #fbbf24' }}>
                  <strong style={{ color: '#fbbf24' }}>{r.file}</strong>
                  <p style={{ margin: '10px 0 0 0', fontSize: '13px' }}>{r.suggestion}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}