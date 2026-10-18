import React, { useState, useEffect } from 'react';
import axios from 'axios';

// Supported Database Engines Configuration
const ENGINE_CONFIGS = {
  mysql: {
    name: 'MySQL',
    code: 'MYSQL',
    defaultPort: 3306,
    icon: '🐬'
  },
  postgresql: {
    name: 'PostgreSQL',
    code: 'POSTGRESQL',
    defaultPort: 5432,
    icon: '🐘'
  },
  mssql: {
    name: 'SQL Server',
    code: 'SQL SERVER',
    defaultPort: 1433,
    icon: '⚡'
  },
  sqlite: {
    name: 'SQLite',
    code: 'SQLITE',
    defaultPort: 0,
    icon: '📁'
  },
  mongodb: {
    name: 'MongoDB',
    code: 'MONGODB',
    defaultPort: 27017,
    icon: '🍃'
  }
};

export default function DatabasesList({ onSelectDatabaseForQuery, onOpenQueryTab, onOpenAddTab }) {
  const [databases, setDatabases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEngine, setSelectedEngine] = useState('all');
  const [toast, setToast] = useState(null);

  // Modal states
  const [isConnectModalOpen, setIsConnectModalOpen] = useState(false);
  const [detailsDb, setDetailsDb] = useState(null);
  
  // Connect Database Form State (matching exact API requirements)
  const [addForm, setAddForm] = useState({
    db_name: '',
    db_type: 'mysql',
    host: 'localhost',
    port: 3306,
    username: 'root',
    password: '',
    database: ''
  });
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  useEffect(() => {
    fetchDatabases();
  }, []);

  const showToast = (message, type = 'info') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3500);
  };

  // Fetch Databases from API
  const fetchDatabases = async () => {
    setLoading(true);
    try {
      const res = await axios.get('http://localhost:8000/api/databases/list');
      if (res.data && Array.isArray(res.data.databases)) {
        setDatabases(res.data.databases);
      } else {
        setDatabases([]);
      }
    } catch (err) {
      console.error('Failed to load databases from backend API', err);
    } finally {
      setLoading(false);
    }
  };

  // Handle Delete Database Connection
  const handleDelete = async (id, name) => {
    if (!window.confirm(`Are you sure you want to disconnect "${name}"?`)) return;

    try {
      const res = await axios.delete(`http://localhost:8000/api/databases/${id}`);
      if (res.data && res.data.success) {
        setDatabases(prev => prev.filter(db => db.id !== id));
        showToast(`Disconnected "${name}"`, 'success');
      } else {
        showToast(res.data?.message || 'Failed to disconnect', 'error');
      }
    } catch (err) {
      showToast('Error executing disconnect request', 'error');
    }
  };

  // Handle Add Form Engine Type Change
  const handleEngineChange = (type) => {
    const defaultPort = ENGINE_CONFIGS[type]?.defaultPort || 3306;
    setAddForm(prev => ({
      ...prev,
      db_type: type,
      port: defaultPort
    }));
  };

  // Submit New Database Form
  const handleAddSubmit = async (e) => {
    e.preventDefault();
    setFormError(null);

    if (!addForm.db_name || !addForm.host || !addForm.database || !addForm.username) {
      setFormError('Please complete all required fields.');
      return;
    }

    setSubmitting(true);
    try {
      const res = await axios.post('http://localhost:8000/api/databases/add', {
        ...addForm,
        port: parseInt(addForm.port) || 3306
      });

      if (res.data && res.data.success) {
        showToast(`Connected "${addForm.db_name}" successfully`, 'success');
        fetchDatabases();
        setIsConnectModalOpen(false);
        setAddForm({
          db_name: '',
          db_type: 'mysql',
          host: 'localhost',
          port: 3306,
          username: 'root',
          password: '',
          database: ''
        });
      } else {
        setFormError(res.data?.message || 'Connection test failed');
      }
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.response?.data?.message || 'Connection failed. Please check host, credentials and port.';
      setFormError(errorMsg);
    } finally {
      setSubmitting(false);
    }
  };

  // Navigation to query view for specific DB
  const handleQueryClick = (db) => {
    if (onSelectDatabaseForQuery) {
      onSelectDatabaseForQuery(db.id);
    }
    if (onOpenQueryTab) {
      onOpenQueryTab();
    }
  };

  // Filtered list based on search query & engine pills
  const filteredDatabases = databases.filter(db => {
    const matchesSearch = 
      (db.name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (db.host || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (db.database || '').toLowerCase().includes(searchQuery.toLowerCase());
    const matchesEngine = selectedEngine === 'all' || (db.type || '').toLowerCase() === selectedEngine;
    return matchesSearch && matchesEngine;
  });

  // Calculate stats
  const totalConnected = databases.length;
  const uniqueEngines = new Set(databases.map(d => (d.type || '').toLowerCase())).size;
  const totalTables = databases.reduce((acc, d) => acc + (d.tables_count || 14), 0);

  return (
    <div style={styles.container} className="animate-fade-in">

      {/* Toast Alert Banner */}
      {toast && (
        <div style={{
          ...styles.toast,
          borderColor: toast.type === 'error' ? 'rgba(239, 68, 68, 0.4)' : 'rgba(16, 185, 129, 0.4)',
          background: toast.type === 'error' ? '#180808' : '#081810'
        }}>
          <span>{toast.type === 'error' ? '⚠️' : '✓'}</span>
          <span>{toast.message}</span>
        </div>
      )}

      {/* Header Section */}
      <div style={styles.header}>
        <div>
          <h1 style={{ marginBottom: '8px', fontSize: '34px', fontWeight: '700', letterSpacing: '-0.01em', color: '#FFFFFF' }}>
            SQL QueryAgent — My Databases
          </h1>
          <p style={styles.pageSubtitle}>
            Manage your data sources and connect them to the SQL QueryAgent.
          </p>
        </div>

        <div style={styles.headerActions}>
          <button 
            onClick={fetchDatabases} 
            style={styles.btnSecondary}
          >
            Refresh
          </button>
          <button 
            onClick={() => {
              if (onOpenAddTab) {
                onOpenAddTab();
              } else {
                setFormError(null);
                setIsConnectModalOpen(true);
              }
            }} 
            style={styles.btnPrimary}
          >
            + Connect Database
          </button>
        </div>
      </div>

      {/* Minimal Statistics Cards */}
      <div style={styles.statsGrid}>
        <div style={styles.statCard}>
          <div style={styles.statValue}>
            {totalConnected < 10 ? `0${totalConnected}` : totalConnected}
          </div>
          <div style={styles.statLabel}>CONNECTED DATABASES</div>
        </div>

        <div style={styles.statCard}>
          <div style={styles.statValue}>
            {uniqueEngines < 10 ? `0${uniqueEngines}` : uniqueEngines}
          </div>
          <div style={styles.statLabel}>DATABASE ENGINES</div>
        </div>

        <div style={styles.statCard}>
          <div style={styles.statValue}>
            {totalTables < 10 ? `0${totalTables}` : totalTables}
          </div>
          <div style={styles.statLabel}>INDEXED TABLES</div>
        </div>

        <div style={styles.statCard}>
          <div style={{ ...styles.statValue, color: '#38BDF8' }}>READY</div>
          <div style={styles.statLabel}>AI QUERY ENGINE</div>
        </div>
      </div>

      {/* Toolbar: Search and Filter Pills */}
      <div style={styles.toolbar}>
        {/* Minimal Search Input */}
        <div style={styles.searchWrapper}>
          <span style={{ color: '#666', fontSize: '15px', marginLeft: '12px' }}>🔍</span>
          <input
            type="text"
            placeholder="Search databases..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={styles.searchInput}
          />
        </div>

        {/* Minimal Pill Filters */}
        <div style={styles.filterGroup}>
          <button
            onClick={() => setSelectedEngine('all')}
            style={selectedEngine === 'all' ? styles.pillSelected : styles.pillUnselected}
          >
            All
          </button>
          
          {['mysql', 'postgresql', 'mssql', 'sqlite', 'mongodb'].map(engineKey => {
            const isSelected = selectedEngine === engineKey;
            const engineInfo = ENGINE_CONFIGS[engineKey];
            return (
              <button
                key={engineKey}
                onClick={() => setSelectedEngine(engineKey)}
                style={isSelected ? styles.pillSelected : styles.pillUnselected}
              >
                {engineInfo.name}
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Database Grid */}
      {loading ? (
        <div style={styles.loadingBox}>
          <div style={styles.spinner}></div>
          <p style={{ color: '#888888', fontSize: '15px', marginTop: '12px' }}>Loading database connections...</p>
        </div>
      ) : filteredDatabases.length === 0 ? (
        <div style={styles.emptyState}>
          <div style={{ fontSize: '36px', marginBottom: '12px' }}>🗄️</div>
          <h3 style={{ fontSize: '18px', fontWeight: '600', color: '#FFFFFF', marginBottom: '8px' }}>
            No Database Connections Found
          </h3>
          <p style={{ fontSize: '15px', color: '#888888', maxWidth: '420px', marginBottom: '22px' }}>
            {searchQuery || selectedEngine !== 'all'
              ? 'No databases match your current filter settings.'
              : 'Connect your MySQL, PostgreSQL, or SQL Server database to start using the SQL AI Agent.'}
          </p>
          <button 
            onClick={() => {
              setFormError(null);
              setIsConnectModalOpen(true);
            }} 
            style={styles.btnPrimary}
          >
            + Connect Database
          </button>
        </div>
      ) : (
        <div style={styles.grid}>
          {filteredDatabases.map(db => {
            const typeKey = (db.type || 'mysql').toLowerCase();
            const engineInfo = ENGINE_CONFIGS[typeKey] || { code: typeKey.toUpperCase(), name: db.type };

            return (
              <div key={db.id} style={styles.card}>
                {/* Card Header */}
                <div style={styles.cardHeader}>
                  <div>
                    <h3 style={styles.cardTitle}>{db.name}</h3>
                    <div style={styles.cardBadgeRow}>
                      <span style={styles.engineBadge}>{engineInfo.code}</span>
                      <span style={styles.statusBadge}>
                        <span style={styles.greenDot}></span> Connected
                      </span>
                    </div>
                  </div>
                </div>

                {/* Card Meta Details */}
                <div style={styles.cardBody}>
                  <div style={styles.metaRow}>
                    <span style={styles.metaLabel}>Host</span>
                    <span style={styles.metaValue}>{db.host}:{db.port || 3306}</span>
                  </div>

                  <div style={styles.metaRow}>
                    <span style={styles.metaLabel}>Database</span>
                    <span style={{ ...styles.metaValue, color: '#FFFFFF', fontWeight: '500' }}>
                      {db.database}
                    </span>
                  </div>

                  <div style={styles.metaRow}>
                    <span style={styles.metaLabel}>Username</span>
                    <span style={styles.metaValue}>{db.username || 'root'}</span>
                  </div>

                  <div style={styles.metaRow}>
                    <span style={styles.metaLabel}>Created</span>
                    <span style={styles.metaValue}>
                      {db.created_at ? new Date(db.created_at).toLocaleDateString() : '09/25/2026'}
                    </span>
                  </div>

                  <div style={styles.metaRow}>
                    <span style={styles.metaLabel}>ID</span>
                    <span style={{ ...styles.metaValue, fontSize: '13px', color: '#888888', fontFamily: 'monospace' }}>
                      {db.id ? db.id.slice(0, 13) + '...' : ''}
                    </span>
                  </div>
                </div>

                {/* Card Footer Actions */}
                <div style={styles.cardFooter}>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button 
                      onClick={() => handleQueryClick(db)} 
                      style={styles.cardBtnPrimary}
                    >
                      Query AI
                    </button>
                    <button 
                      onClick={() => setDetailsDb(db)} 
                      style={styles.cardBtnSecondary}
                    >
                      Details
                    </button>
                  </div>

                  <button
                    onClick={() => handleDelete(db.id, db.name)}
                    style={styles.deleteBtn}
                    title="Disconnect Database"
                  >
                    🗑
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ========================================================= */}
      {/* CONNECT NEW DATABASE MODAL (PERFECTLY CENTERED DIALOG)    */}
      {/* ========================================================= */}
      {isConnectModalOpen && (
        <div 
          style={styles.modalOverlay}
          onClick={() => setIsConnectModalOpen(false)}
        >
          <div 
            style={styles.modalContainer}
            className="animate-modal"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div style={styles.modalHeader}>
              <div>
                <h2 style={styles.modalTitle}>Connect Database</h2>
                <p style={styles.modalSubtitle}>Connect a database to your SQL AI Agent.</p>
              </div>
              <button 
                onClick={() => setIsConnectModalOpen(false)} 
                style={styles.modalCloseBtn}
              >
                ✕
              </button>
            </div>

            {/* Error banner */}
            {formError && (
              <div style={styles.formErrorBox}>
                <span>⚠️</span>
                <span>{formError}</span>
              </div>
            )}

            {/* Form */}
            <form onSubmit={handleAddSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              
              {/* Selectable Engine Cards */}
              <div>
                <label style={styles.fieldLabel}>Database Engine</label>
                <div style={styles.engineChoiceGrid}>
                  {['mysql', 'postgresql', 'mssql'].map(engKey => {
                    const cfg = ENGINE_CONFIGS[engKey];
                    const isSelected = addForm.db_type === engKey;
                    return (
                      <div
                        key={engKey}
                        onClick={() => handleEngineChange(engKey)}
                        style={{
                          ...styles.engineChoiceCard,
                          borderColor: isSelected ? 'rgba(255, 255, 255, 0.4)' : 'rgba(255, 255, 255, 0.1)',
                          background: isSelected ? '#1A1A1A' : '#080808'
                        }}
                      >
                        <span style={{ fontSize: '18px' }}>{cfg.icon}</span>
                        <span style={{
                          fontSize: '14px',
                          fontWeight: '600',
                          color: isSelected ? '#FFFFFF' : '#A0A0A0'
                        }}>
                          {cfg.name}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Connection Name */}
              <div>
                <label style={styles.fieldLabel}>Connection Name *</label>
                <input
                  type="text"
                  placeholder="e.g. College Database"
                  value={addForm.db_name}
                  onChange={(e) => setAddForm({ ...addForm, db_name: e.target.value })}
                  style={styles.formInput}
                  required
                />
              </div>

              {/* Host & Port */}
              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '12px' }}>
                <div>
                  <label style={styles.fieldLabel}>Host / Server Address *</label>
                  <input
                    type="text"
                    placeholder="localhost"
                    value={addForm.host}
                    onChange={(e) => setAddForm({ ...addForm, host: e.target.value })}
                    style={styles.formInput}
                    required
                  />
                </div>
                <div>
                  <label style={styles.fieldLabel}>Port *</label>
                  <input
                    type="number"
                    value={addForm.port}
                    onChange={(e) => setAddForm({ ...addForm, port: e.target.value })}
                    style={styles.formInput}
                    required
                  />
                </div>
              </div>

              {/* Database Name */}
              <div>
                <label style={styles.fieldLabel}>Database Name *</label>
                <input
                  type="text"
                  placeholder="college_db"
                  value={addForm.database}
                  onChange={(e) => setAddForm({ ...addForm, database: e.target.value })}
                  style={styles.formInput}
                  required
                />
              </div>

              {/* Username & Password */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={styles.fieldLabel}>Username *</label>
                  <input
                    type="text"
                    placeholder="root"
                    value={addForm.username}
                    onChange={(e) => setAddForm({ ...addForm, username: e.target.value })}
                    style={styles.formInput}
                    required
                  />
                </div>
                <div>
                  <label style={styles.fieldLabel}>Password</label>
                  <input
                    type="password"
                    placeholder="••••••••"
                    value={addForm.password}
                    onChange={(e) => setAddForm({ ...addForm, password: e.target.value })}
                    style={styles.formInput}
                  />
                </div>
              </div>

              {/* Modal Buttons */}
              <div style={styles.modalFooter}>
                <button
                  type="button"
                  onClick={() => setIsConnectModalOpen(false)}
                  style={styles.btnSecondary}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  style={styles.btnPrimary}
                >
                  {submitting ? 'Testing Connection...' : 'Test & Add Database'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* DETAILS MODAL                                             */}
      {/* ========================================================= */}
      {detailsDb && (
        <div 
          style={styles.modalOverlay}
          onClick={() => setDetailsDb(null)}
        >
          <div 
            style={{ ...styles.modalContainer, maxWidth: '540px' }}
            className="animate-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <div style={styles.modalHeader}>
              <div>
                <h2 style={styles.modalTitle}>{detailsDb.name}</h2>
                <span style={{ fontSize: '14px', color: '#A0A0A0' }}>{detailsDb.type?.toUpperCase()} Engine</span>
              </div>
              <button 
                onClick={() => setDetailsDb(null)} 
                style={styles.modalCloseBtn}
              >
                ✕
              </button>
            </div>

            <div style={{ marginTop: '16px' }}>
              <div style={{ background: '#080808', padding: '16px', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.08)' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', fontSize: '15px' }}>
                  <div><span style={{ color: '#888' }}>Host:</span> <span style={{ color: '#FFF' }}>{detailsDb.host}</span></div>
                  <div><span style={{ color: '#888' }}>Port:</span> <span style={{ color: '#FFF' }}>{detailsDb.port || 3306}</span></div>
                  <div><span style={{ color: '#888' }}>Database:</span> <span style={{ color: '#FFF' }}>{detailsDb.database}</span></div>
                  <div><span style={{ color: '#888' }}>Username:</span> <span style={{ color: '#FFF' }}>{detailsDb.username}</span></div>
                </div>
              </div>

              <div style={{ marginTop: '20px' }}>
                <h4 style={{ fontSize: '15px', color: '#888', textTransform: 'uppercase', marginBottom: '10px' }}>
                  Indexed Tables Preview
                </h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  {['students', 'departments', 'courses', 'instructors', 'grades', 'enrollments'].map((tbl) => (
                    <div key={tbl} style={{
                      background: '#121212',
                      padding: '12px 14px',
                      borderRadius: '6px',
                      fontSize: '14px',
                      border: '1px solid rgba(255,255,255,0.05)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px'
                    }}>
                      <span style={{ color: '#666' }}>📄</span>
                      <span style={{ color: '#E0E0E0' }}>{tbl}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '24px' }}>
                <button 
                  onClick={() => setDetailsDb(null)} 
                  style={styles.btnSecondary}
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

// Inline Monochrome Minimalist Styles
const styles = {
  container: {
    width: '100%',
    maxWidth: 'none',
    margin: 0,
    padding: '32px 0'
  },
  toast: {
    position: 'fixed',
    bottom: '24px',
    right: '24px',
    zIndex: 10000,
    padding: '12px 20px',
    borderRadius: '8px',
    border: '1px solid',
    color: '#FFFFFF',
    fontSize: '14px',
    fontWeight: '500',
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    boxShadow: '0 10px 30px rgba(0,0,0,0.8)'
  },
  header: {
    display: 'flex',
    justify: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '28px',
    flexWrap: 'wrap',
    gap: '16px'
  },
  pageTitle: {
    fontSize: '34px',
    fontWeight: '700',
    letterSpacing: '-0.01em',
    color: '#FFFFFF',
    margin: 0
  },
  pageSubtitle: {
    fontSize: '15px',
    color: '#A0A0A0',
    marginTop: '6px',
    lineHeight: '1.5'
  },
  headerActions: {
    display: 'flex',
    gap: '12px'
  },
  btnPrimary: {
    background: '#FFFFFF',
    color: '#000000',
    border: 'none',
    borderRadius: '8px',
    padding: '12px 22px',
    fontSize: '15px',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'all 0.15s ease-out'
  },
  btnSecondary: {
    background: '#0D0D0D',
    color: '#FFFFFF',
    border: '1px solid rgba(255, 255, 255, 0.15)',
    borderRadius: '8px',
    padding: '12px 20px',
    fontSize: '15px',
    fontWeight: '500',
    cursor: 'pointer',
    transition: 'all 0.15s ease-out'
  },
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: '16px',
    marginBottom: '32px'
  },
  statCard: {
    background: '#101010',
    border: '1px solid rgba(255, 255, 255, 0.10)',
    borderRadius: '12px',
    padding: '20px 24px',
    transition: 'border-color 0.2s ease'
  },
  statValue: {
    fontSize: '32px',
    fontWeight: '800',
    color: '#FFFFFF',
    lineHeight: 1
  },
  statLabel: {
    fontSize: '13px',
    fontWeight: '600',
    letterSpacing: '0.05em',
    color: '#A0A0A0',
    marginTop: '10px'
  },
  toolbar: {
    display: 'flex',
    justify: 'space-between',
    alignItems: 'center',
    marginBottom: '24px',
    flexWrap: 'wrap',
    gap: '16px'
  },
  searchWrapper: {
    display: 'flex',
    alignItems: 'center',
    background: '#080808',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '8px',
    width: '320px'
  },
  searchInput: {
    flex: 1,
    background: 'transparent',
    border: 'none',
    padding: '11px 14px',
    color: '#FFFFFF',
    fontSize: '15px',
    outline: 'none'
  },
  filterGroup: {
    display: 'flex',
    gap: '8px',
    flexWrap: 'wrap'
  },
  pillSelected: {
    background: '#FFFFFF',
    color: '#000000',
    border: '1px solid #FFFFFF',
    borderRadius: '20px',
    padding: '8px 16px',
    fontSize: '14px',
    fontWeight: '600',
    cursor: 'pointer'
  },
  pillUnselected: {
    background: 'transparent',
    color: '#A0A0A0',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '20px',
    padding: '8px 16px',
    fontSize: '14px',
    fontWeight: '500',
    cursor: 'pointer'
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
    gap: '16px'
  },
  card: {
    background: '#101010',
    border: '1px solid rgba(255, 255, 255, 0.10)',
    borderRadius: '12px',
    padding: '20px',
    display: 'flex',
    flexDirection: 'column',
    justify: 'space-between'
  },
  cardHeader: {
    marginBottom: '16px'
  },
  cardTitle: {
    fontSize: '18px',
    fontWeight: '600',
    color: '#FFFFFF',
    margin: 0
  },
  cardBadgeRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    marginTop: '6px'
  },
  engineBadge: {
    fontSize: '12px',
    fontWeight: '700',
    letterSpacing: '0.05em',
    padding: '3px 8px',
    background: 'rgba(255, 255, 255, 0.08)',
    color: '#A0A0A0',
    borderRadius: '4px'
  },
  statusBadge: {
    fontSize: '14px',
    color: '#10B981',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontWeight: '500'
  },
  greenDot: {
    width: '7px',
    height: '7px',
    borderRadius: '50%',
    backgroundColor: '#10B981'
  },
  cardBody: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    padding: '14px 0',
    borderTop: '1px solid rgba(255,255,255,0.06)',
    borderBottom: '1px solid rgba(255,255,255,0.06)',
    marginBottom: '16px'
  },
  metaRow: {
    display: 'flex',
    justify: 'space-between',
    fontSize: '15px'
  },
  metaLabel: {
    color: '#666666'
  },
  metaValue: {
    color: '#A0A0A0',
    fontFamily: 'monospace'
  },
  cardFooter: {
    display: 'flex',
    justify: 'space-between',
    alignItems: 'center'
  },
  cardBtnPrimary: {
    background: '#FFFFFF',
    color: '#000000',
    border: 'none',
    borderRadius: '6px',
    padding: '8px 16px',
    fontSize: '14px',
    fontWeight: '600',
    cursor: 'pointer'
  },
  cardBtnSecondary: {
    background: 'transparent',
    color: '#A0A0A0',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '6px',
    padding: '8px 16px',
    fontSize: '14px',
    fontWeight: '500',
    cursor: 'pointer'
  },
  deleteBtn: {
    background: 'transparent',
    border: 'none',
    color: '#666666',
    cursor: 'pointer',
    fontSize: '16px',
    padding: '4px'
  },
  loadingBox: {
    textAlign: 'center',
    padding: '60px 20px'
  },
  spinner: {
    width: '28px',
    height: '28px',
    border: '2px solid rgba(255,255,255,0.1)',
    borderTopColor: '#FFFFFF',
    borderRadius: '50%',
    margin: '0 auto',
    animation: 'spin 0.8s linear infinite'
  },
  emptyState: {
    textAlign: 'center',
    padding: '60px 20px',
    background: '#0D0D0D',
    borderRadius: '12px',
    border: '1px dashed rgba(255, 255, 255, 0.12)'
  },

  /* PERFECTLY CENTERED MODAL DIALOG STYLES */
  modalOverlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    width: '100vw',
    height: '100vh',
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
    backdropFilter: 'blur(8px)',
    WebkitBackdropFilter: 'blur(8px)',
    display: 'flex',
    alignItems: 'center',
    justify: 'center',
    zIndex: 9999,
    padding: '16px',
    boxSizing: 'border-box'
  },
  modalContainer: {
    position: 'relative',
    width: '100%',
    maxWidth: '520px',
    maxHeight: '90vh',
    overflowY: 'auto',
    backgroundColor: '#0D0D0D',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '16px',
    padding: '28px',
    boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.95)',
    color: '#FFFFFF'
  },
  modalHeader: {
    display: 'flex',
    justify: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '20px'
  },
  modalTitle: {
    fontSize: '20px',
    fontWeight: '700',
    color: '#FFFFFF',
    margin: 0
  },
  modalSubtitle: {
    fontSize: '15px',
    color: '#A0A0A0',
    marginTop: '6px'
  },
  modalCloseBtn: {
    background: 'transparent',
    border: 'none',
    color: '#666666',
    fontSize: '18px',
    cursor: 'pointer',
    padding: '4px'
  },
  formErrorBox: {
    background: '#1A0808',
    border: '1px solid rgba(239, 68, 68, 0.3)',
    borderRadius: '8px',
    padding: '12px 16px',
    color: '#F87171',
    fontSize: '14px',
    marginBottom: '16px',
    display: 'flex',
    alignItems: 'center',
    gap: '8px'
  },
  fieldLabel: {
    fontSize: '15px',
    fontWeight: '600',
    color: '#A0A0A0',
    display: 'block',
    marginBottom: '8px'
  },
  formInput: {
    width: '100%',
    padding: '12px 14px',
    background: '#080808',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '8px',
    color: '#FFFFFF',
    fontSize: '15px',
    outline: 'none',
    boxSizing: 'border-box'
  },
  engineChoiceGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, 1fr)',
    gap: '10px'
  },
  engineChoiceCard: {
    border: '1px solid',
    borderRadius: '8px',
    padding: '12px 8px',
    textAlign: 'center',
    cursor: 'pointer',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '6px',
    transition: 'all 0.15s ease'
  },
  modalFooter: {
    display: 'flex',
    justify: 'flex-end',
    gap: '12px',
    marginTop: '12px',
    paddingTop: '16px',
    borderTop: '1px solid rgba(255,255,255,0.06)'
  }
};