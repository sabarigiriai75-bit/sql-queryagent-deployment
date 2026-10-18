import React, { useState, useEffect } from 'react';
import axios from 'axios';
import VisualFlow from '../components/VisualFlow';

export default function QueryInterface({ selectedDbId, onSelectDb }) {
  const [databases, setDatabases] = useState([]);
  const [selectedDb, setSelectedDb] = useState(() => {
    return selectedDbId || localStorage.getItem('sql_agent_selected_db_id') || '';
  });
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [copiedSql, setCopiedSql] = useState(false);
  const [activeTab, setActiveTab] = useState('table'); // 'table' | 'text'

  useEffect(() => {
    fetchDatabases();
    fetchHistory();
  }, []);

  useEffect(() => {
    if (selectedDbId && selectedDbId !== selectedDb) {
      setSelectedDb(selectedDbId);
      localStorage.setItem('sql_agent_selected_db_id', selectedDbId);
    }
  }, [selectedDbId]);

  const fetchDatabases = async () => {
    try {
      const res = await axios.get('http://localhost:8000/api/databases/list');
      if (res.data && Array.isArray(res.data.databases)) {
        const list = res.data.databases;
        setDatabases(list);

        // Determine correct database selection without silent fallback to sample DB
        const targetId = selectedDb || selectedDbId || localStorage.getItem('sql_agent_selected_db_id');
        const found = list.find((d) => d.id === targetId);

        if (found) {
          setSelectedDb(found.id);
        } else if (list.length > 0) {
          // If no previous selection, prioritize college_database or first MySQL database
          const preferred =
            list.find((d) => d.database === 'college_database') ||
            list.find((d) => d.type === 'mysql') ||
            list[0];
          setSelectedDb(preferred.id);
          localStorage.setItem('sql_agent_selected_db_id', preferred.id);
          if (onSelectDb) onSelectDb(preferred.id);
        }
      }
    } catch (err) {
      console.error('Failed to load database list', err);
    }
  };

  const fetchHistory = async () => {
    try {
      const res = await axios.get('http://localhost:8000/api/query-history');
      if (res.data && Array.isArray(res.data.history)) {
        setHistory(res.data.history);
      }
    } catch (err) {
      console.error('Failed to load query history', err);
    }
  };

  const handleDatabaseChange = (e) => {
    const newId = e.target.value;
    setSelectedDb(newId);
    localStorage.setItem('sql_agent_selected_db_id', newId);
    if (onSelectDb) onSelectDb(newId);
  };

  const handleQuery = async (customQuery) => {
    const qToRun = (customQuery || query).trim();
    if (!selectedDb) {
      alert('Please select a database connection first.');
      return;
    }
    if (!qToRun) {
      alert('Please enter a natural language question.');
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const res = await axios.post('http://localhost:8000/api/query', {
        query: qToRun,
        connection_id: selectedDb,
        user_id: 'user1',
      });
      setResult(res.data);
      fetchHistory();
    } catch (err) {
      const errorDetail =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        'Failed to execute query on backend';
      setResult({
        success: false,
        result: errorDetail,
        error: errorDetail,
        query: qToRun,
        timestamp: new Date().toISOString(),
      });
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedSql(true);
    setTimeout(() => setCopiedSql(false), 2000);
  };

  const exampleQuestions = [
    'Show the total number of students in each department, sorted from highest to lowest.',
    'List CSE students with CGPA above 8.5',
    'How many students are in the database?',
    'Show top 5 students ordered by CGPA descending',
    'How many employees are in each department?',
    'Show all employees in the Finance department',
    'Show employees earning more than 70000',
  ];

  const currentDbObj = databases.find((d) => d.id === selectedDb);

  return (
    <div style={styles.container} className="animate-fade-in">
      {/* Heading */}
      <div style={styles.header}>
        <div>
          <h1 style={{ marginBottom: '8px', fontSize: '34px', fontWeight: '700', letterSpacing: '-0.01em', color: '#FFFFFF' }}>
            SQL QueryAgent
          </h1>
          <p style={styles.subtitle}>
            Ask questions in natural language. Let SQL QueryAgent inspect your real schema and
            execute accurate queries.
          </p>
        </div>

        {/* AI Status Indicators */}
        <div style={styles.statusPillsRow}>
          <span style={styles.statusPill}>
            <span style={styles.greenDot}></span> AI Agent Ready
          </span>
          <span style={styles.statusPill}>
            <span style={styles.blueDot}></span> Connected Target:{' '}
            {currentDbObj ? currentDbObj.name : 'None'}
          </span>
        </div>
      </div>

      {/* Main Grid */}
      <div style={styles.mainGrid}>
        {/* LEFT COLUMN: Input & Result Flow */}
        <div style={styles.column}>
          {/* Database Selector Card */}
          <div style={styles.card}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '8px',
              }}
            >
              <label style={styles.cardLabel}>Select Database Target</label>
              {currentDbObj && (
                <span style={{ fontSize: '13px', color: '#10B981', fontWeight: '600' }}>
                  ● Active Target ID: {currentDbObj.id.slice(0, 8)}...
                </span>
              )}
            </div>

            {databases.length === 0 ? (
              <div style={styles.noDbWarning}>
                <span>⚠️ No active databases connected. Please connect a database first.</span>
              </div>
            ) : (
              <select value={selectedDb} onChange={handleDatabaseChange} style={styles.selectInput}>
                {databases.map((db) => (
                  <option key={db.id} value={db.id}>
                    {db.name} — [{db.type?.toUpperCase()}] {db.host}:
                    {db.port || (db.type === 'mysql' ? 3306 : '')}/{db.database}
                  </option>
                ))}
              </select>
            )}

            {/* Target Details Badge */}
            {currentDbObj && (
              <div style={styles.activeTargetCard}>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '8px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span
                      style={{
                        fontSize: '13px',
                        fontWeight: '700',
                        color: '#10B981',
                        letterSpacing: '0.05em',
                      }}
                    >
                      ● ACTIVE TARGET
                    </span>
                    <strong style={{ color: '#FFFFFF', fontSize: '16px' }}>
                      {currentDbObj.name}
                    </strong>
                    <span style={styles.engineBadge}>{currentDbObj.type?.toUpperCase()}</span>
                  </div>
                  <div style={{ fontSize: '14px', color: '#38BDF8', fontFamily: 'monospace' }}>
                    {currentDbObj.host}:
                    {currentDbObj.port || (currentDbObj.type === 'mysql' ? 3306 : '')}/
                    {currentDbObj.database}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Question Input Textarea */}
          <div style={styles.card}>
            <label style={styles.cardLabel}>What would you like to know?</label>
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={databases.length === 0}
              placeholder="e.g. Show the total number of students in each department, sorted from highest to lowest..."
              rows={5}
              style={styles.textarea}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleQuery();
                }
              }}
            />

            <div style={styles.inputFooterRow}>
              <span style={{ fontSize: '14px', color: '#888888' }}>
                Press Enter to execute query on the selected database
              </span>

              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => handleQuery()}
                  disabled={loading || databases.length === 0}
                  style={styles.btnPrimary}
                >
                  {loading ? 'Executing on Target DB...' : 'Run Query'}
                </button>
              </div>
            </div>
          </div>

          {/* Visual AI Node Flow Banner */}
          <VisualFlow />

          {/* STEP-BY-STEP AI RESULT DISPLAY */}
          {result && (
            <div style={styles.resultContainer} className="animate-fade-in">
              {/* Step 1: User Question */}
              <div style={styles.stepBox}>
                <div
                  style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                >
                  <span style={styles.stepTag}>USER QUESTION</span>
                  {result.database_name && (
                    <span style={{ fontSize: '13px', color: '#10B981', fontFamily: 'monospace' }}>
                      Target: {result.database_name}
                    </span>
                  )}
                </div>
                <p style={styles.stepQuestionText}>"{result.query || query}"</p>
              </div>

              <div style={styles.stepArrow}>↓</div>

              {/* Step 2: AI Understanding & Database Verification */}
              <div style={styles.stepBox}>
                <span style={styles.stepTag}>DATABASE & INTENT VERIFICATION</span>
                <p style={styles.stepDetailText}>
                  {result.success
                    ? `Verified connection to database "${
                        result.database_name || currentDbObj?.database
                      }". Natural language question translated into valid read-only SQL matching real schema.`
                    : `Database or schema validation stopped execution: ${
                        result.error || 'Execution halted.'
                      }`}
                </p>
              </div>

              <div style={styles.stepArrow}>↓</div>

              {/* Step 3: Generated SQL Block */}
              <div style={styles.stepBox}>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '8px',
                  }}
                >
                  <span style={styles.stepTag}>GENERATED SQL</span>
                  {result.executed_sql && (
                    <button
                      onClick={() => copyToClipboard(result.executed_sql)}
                      style={styles.copyBtn}
                    >
                      {copiedSql ? '✓ Copied' : 'Copy SQL'}
                    </button>
                  )}
                </div>

                <div style={styles.sqlCodeBlock}>
                  <code>
                    {result.executed_sql ||
                      (result.success
                        ? '-- SQL not available'
                        : '-- No SQL generated (query generation or validation stopped)')}
                  </code>
                </div>
              </div>

              <div style={styles.stepArrow}>↓</div>

              {/* Step 4: Query Execution Results */}
              <div style={styles.stepBox}>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: '8px',
                    marginBottom: '12px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span style={styles.stepTag}>QUERY RESULT</span>
                    {result.success && result.row_count !== undefined && (
                      <span
                        style={{
                          fontSize: '13px',
                          color: '#38BDF8',
                          background: 'rgba(56, 189, 248, 0.1)',
                          padding: '3px 10px',
                          borderRadius: '4px',
                          fontWeight: '500',
                        }}
                      >
                        {result.row_count} records returned
                      </span>
                    )}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {result.rows && result.rows.length > 0 && (
                      <div
                        style={{
                          display: 'flex',
                          gap: '4px',
                          background: '#080808',
                          padding: '2px',
                          borderRadius: '4px',
                          border: '1px solid rgba(255,255,255,0.1)',
                        }}
                      >
                        <button
                          onClick={() => setActiveTab('table')}
                          style={{
                            ...styles.viewTabBtn,
                            background: activeTab === 'table' ? '#222' : 'transparent',
                            color: activeTab === 'table' ? '#FFF' : '#888',
                          }}
                        >
                          Table
                        </button>
                        <button
                          onClick={() => setActiveTab('text')}
                          style={{
                            ...styles.viewTabBtn,
                            background: activeTab === 'text' ? '#222' : 'transparent',
                            color: activeTab === 'text' ? '#FFF' : '#888',
                          }}
                        >
                          Raw
                        </button>
                      </div>
                    )}
                    <span style={{ fontSize: '13px', color: '#888888' }}>
                      {new Date(result.timestamp || Date.now()).toLocaleTimeString()}
                    </span>
                  </div>
                </div>

                <div
                  style={{
                    background: result.success ? '#0D0D0D' : '#1A0808',
                    border: `1px solid ${
                      result.success ? 'rgba(255,255,255,0.1)' : 'rgba(239, 68, 68, 0.3)'
                    }`,
                    borderRadius: '8px',
                    padding: '16px',
                    minWidth: 0,
                  }}
                >
                  {result.success ? (
                    activeTab === 'table' && result.rows && result.rows.length > 0 ? (
                      // Wrapper scrolls horizontally; table keeps its natural width
                      <div style={styles.tableScrollWrapper}>
                        <table style={styles.resultTable}>
                          <thead>
                            <tr>
                              {result.columns.map((col) => (
                                <th key={col} style={styles.tableHeader}>
                                  {col}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {result.rows.map((row, rIdx) => (
                              <tr key={rIdx} style={styles.tableRow}>
                                {result.columns.map((col) => (
                                  <td key={col} style={styles.tableCell}>
                                    {row[col] !== null && row[col] !== undefined
                                      ? String(row[col])
                                      : 'NULL'}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <pre style={styles.rawOutputCode}>{result.result}</pre>
                    )
                  ) : (
                    <div style={{ color: '#F87171', fontSize: '15px', lineHeight: '1.6' }}>
                      <strong>❌ Error:</strong> {result.result || result.error}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* RIGHT COLUMN: Examples & Stats */}
        <div style={styles.column}>
          {/* Example Prompts */}
          <div style={styles.card}>
            <h3 style={styles.sidebarHeading}>Example Questions</h3>
            <p style={{ fontSize: '14px', color: '#888888', marginTop: '4px', marginBottom: '10px' }}>
              Click any question to load and execute on the active target database:
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {exampleQuestions.map((ex, idx) => (
                <div
                  key={idx}
                  onClick={() => {
                    setQuery(ex);
                    handleQuery(ex);
                  }}
                  style={styles.exampleChip}
                >
                  <span style={{ fontSize: '16px' }}>💬</span>
                  <span style={{ flex: 1, fontSize: '14.5px', lineHeight: '1.5' }}>{ex}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Stats Card */}
          <div style={styles.card}>
            <h3 style={styles.sidebarHeading}>System Stats</h3>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '12px',
                marginTop: '12px',
              }}
            >
              <div style={styles.miniStatBox}>
                <div style={styles.miniStatValue}>{databases.length}</div>
                <div style={styles.miniStatLabel}>DATABASES</div>
              </div>
              <div style={styles.miniStatBox}>
                <div style={styles.miniStatValue}>{history.length}</div>
                <div style={styles.miniStatLabel}>QUERIES</div>
              </div>
            </div>
          </div>

          {/* Recent Query History */}
          <div style={styles.card}>
            <h3 style={styles.sidebarHeading}>Recent Query History</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '12px' }}>
              {history.length === 0 ? (
                <p style={{ fontSize: '14px', color: '#888888' }}>No queries executed yet.</p>
              ) : (
                history.slice(0, 6).map((item, idx) => (
                  <div
                    key={idx}
                    onClick={() => {
                      setQuery(item.query);
                      handleQuery(item.query);
                    }}
                    style={styles.historyItem}
                  >
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: '8px',
                      }}
                    >
                      <span style={{ fontSize: '14px', fontWeight: '500', color: '#E5E5E5' }}>
                        {item.query.length > 36 ? item.query.substring(0, 36) + '...' : item.query}
                      </span>
                      <span
                        style={{
                          fontSize: '12px',
                          color: item.success ? '#10B981' : '#EF4444',
                          fontWeight: '700',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {item.success ? '✓ SUCCESS' : '✕ FAIL'}
                      </span>
                    </div>
                    {item.database_name && (
                      <div style={{ fontSize: '12px', color: '#888888', marginTop: '4px' }}>
                        DB: {item.database_name}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Styling definitions
const styles = {
  container: {
    width: '100%',
    maxWidth: 'none',
    margin: 0,
    padding: '32px 0',
    boxSizing: 'border-box',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '28px',
    flexWrap: 'wrap',
    gap: '16px',
  },
  title: {
    fontSize: '34px',
    fontWeight: '700',
    letterSpacing: '-0.01em',
    color: '#FFFFFF',
    margin: 0,
  },
  subtitle: {
    fontSize: '15px',
    color: '#A0A0A0',
    marginTop: '6px',
    lineHeight: '1.5',
  },
  statusPillsRow: {
    display: 'flex',
    gap: '10px',
    flexWrap: 'wrap',
  },
  statusPill: {
    background: '#0D0D0D',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '20px',
    padding: '7px 14px',
    fontSize: '14px',
    color: '#A0A0A0',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontWeight: '500',
  },
  greenDot: {
    width: '7px',
    height: '7px',
    borderRadius: '50%',
    backgroundColor: '#10B981',
  },
  blueDot: {
    width: '7px',
    height: '7px',
    borderRadius: '50%',
    backgroundColor: '#3B82F6',
  },
  // minmax(0, 1fr) stops a wide table from pushing the grid off-centre
  mainGrid: {
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) 340px',
    gap: '24px',
    width: '100%',
    alignItems: 'start',
  },
  column: {
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
    minWidth: 0,
  },
  card: {
    background: '#101010',
    border: '1px solid rgba(255, 255, 255, 0.10)',
    borderRadius: '12px',
    padding: '22px',
    minWidth: 0,
    boxSizing: 'border-box',
  },
  cardLabel: {
    fontSize: '16px',
    fontWeight: '600',
    color: '#A0A0A0',
    display: 'block',
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
  },
  selectInput: {
    width: '100%',
    padding: '12px 14px',
    background: '#080808',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '8px',
    color: '#FFFFFF',
    fontSize: '15px',
    outline: 'none',
    boxSizing: 'border-box',
  },
  activeTargetCard: {
    marginTop: '12px',
    padding: '12px 14px',
    background: '#080808',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    borderRadius: '8px',
  },
  engineBadge: {
    fontSize: '12px',
    fontWeight: '700',
    letterSpacing: '0.05em',
    padding: '3px 8px',
    background: 'rgba(255, 255, 255, 0.08)',
    color: '#A0A0A0',
    borderRadius: '4px',
  },
  textarea: {
    width: '100%',
    minHeight: '140px',
    background: '#080808',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '8px',
    padding: '16px',
    color: '#FFFFFF',
    fontSize: '17px',
    lineHeight: '1.6',
    outline: 'none',
    resize: 'vertical',
    boxSizing: 'border-box',
    fontFamily: 'inherit',
  },
  inputFooterRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: '10px',
    marginTop: '12px',
  },
  btnPrimary: {
    background: '#FFFFFF',
    color: '#000000',
    border: 'none',
    borderRadius: '8px',
    padding: '12px 28px',
    fontSize: '16px',
    fontWeight: '600',
    cursor: 'pointer',
  },
  noDbWarning: {
    background: '#1A1208',
    border: '1px solid rgba(245, 158, 11, 0.3)',
    borderRadius: '8px',
    padding: '14px',
    color: '#FBBF24',
    fontSize: '15px',
  },

  /* Step-by-Step AI Result Styling */
  resultContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    marginTop: '12px',
    minWidth: 0,
  },
  stepBox: {
    background: '#101010',
    border: '1px solid rgba(255, 255, 255, 0.10)',
    borderRadius: '12px',
    padding: '18px',
    minWidth: 0,
    boxSizing: 'border-box',
  },
  stepTag: {
    fontSize: '14px',
    fontWeight: '700',
    letterSpacing: '0.06em',
    color: '#38BDF8',
    textTransform: 'uppercase',
  },
  stepQuestionText: {
    fontSize: '18px',
    fontWeight: '600',
    color: '#FFFFFF',
    marginTop: '6px',
  },
  stepDetailText: {
    fontSize: '15px',
    color: '#A0A0A0',
    marginTop: '6px',
    lineHeight: '1.6',
  },
  stepArrow: {
    textAlign: 'center',
    color: '#444444',
    fontSize: '16px',
    margin: '2px 0',
  },
  sqlCodeBlock: {
    background: '#080808',
    padding: '14px',
    borderRadius: '8px',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    color: '#A7F3D0',
    fontSize: '14.5px',
    lineHeight: '1.6',
    marginTop: '6px',
    overflowX: 'auto',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
  },
  copyBtn: {
    background: 'transparent',
    border: '1px solid rgba(255,255,255,0.12)',
    color: '#A0A0A0',
    borderRadius: '4px',
    padding: '6px 12px',
    fontSize: '13px',
    cursor: 'pointer',
  },
  viewTabBtn: {
    border: 'none',
    padding: '5px 12px',
    borderRadius: '4px',
    fontSize: '13px',
    cursor: 'pointer',
    fontWeight: '500',
  },
  tableScrollWrapper: {
    width: '100%',
    maxWidth: '100%',
    overflowX: 'auto',
    overflowY: 'auto',
    maxHeight: '450px',
    boxSizing: 'border-box',
  },
  resultTable: {
    width: '100%',
    minWidth: 'max-content',
    borderCollapse: 'collapse',
    fontSize: '14px',
  },
  tableHeader: {
    background: '#181818',
    color: '#A0A0A0',
    padding: '12px 16px',
    textAlign: 'left',
    fontWeight: '600',
    borderBottom: '1px solid rgba(255, 255, 255, 0.12)',
    position: 'sticky',
    top: 0,
    whiteSpace: 'nowrap',
    fontSize: '14px',
  },
  tableRow: {
    borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
  },
  tableCell: {
    padding: '11px 16px',
    color: '#FFFFFF',
    whiteSpace: 'nowrap',
    fontSize: '14px',
  },
  rawOutputCode: {
    fontFamily: 'monospace',
    fontSize: '14px',
    lineHeight: '1.6',
    color: '#E0E0E0',
    whiteSpace: 'pre-wrap',
    margin: 0,
  },

  /* Sidebar */
  sidebarHeading: {
    fontSize: '17px',
    fontWeight: '600',
    color: '#FFFFFF',
    margin: 0,
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
  },
  exampleChip: {
    background: '#080808',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '8px',
    padding: '12px 14px',
    fontSize: '14.5px',
    color: '#CCCCCC',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    transition: 'all 0.15s ease',
  },
  miniStatBox: {
    background: '#080808',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    borderRadius: '8px',
    padding: '14px',
    textAlign: 'center',
  },
  miniStatValue: {
    fontSize: '26px',
    fontWeight: '700',
    color: '#FFFFFF',
  },
  miniStatLabel: {
    fontSize: '13px',
    fontWeight: '600',
    color: '#888888',
    letterSpacing: '0.05em',
  },
  historyItem: {
    background: '#080808',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    borderRadius: '6px',
    padding: '12px 14px',
    cursor: 'pointer',
  },
};