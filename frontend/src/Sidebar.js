const RefactorPanel = () => {
  const [report, setReport] = useState([]);
  const [loading, setLoading] = useState(false);

  const runRefactorAudit = async () => {
    setLoading(true);
    try {
      const res = await axios.get('http://localhost:8000/ai/refactor-analysis');
      setReport(res.data.refactor_report);
    } catch (err) {
      console.error("Audit failed", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="refactor-sidebar">
      <button onClick={runRefactorAudit} disabled={loading}>
        {loading ? "Analyzing Architecture..." : "🚀 Run Refactor Audit"}
      </button>
      
      {report.map((item, i) => (
        <div key={i} className="refactor-card">
          <h4>{item.file}</h4>
          <p className="issue-tag">{item.issue}</p>
          <div className="suggestion-text">{item.suggestion}</div>
        </div>
      ))}
    </div>
  );
};