import React, { useState } from 'react';
import axios from 'axios';

const ENGINE_CONFIGS = {
  mysql: { name: 'MySQL', defaultPort: 3306, icon: '🐬' },
  postgresql: { name: 'PostgreSQL', defaultPort: 5432, icon: '🐘' },
  mssql: { name: 'SQL Server', defaultPort: 1433, icon: '⚡' },
  sqlite: { name: 'SQLite', defaultPort: 0, icon: '📁' }
};

export default function AddDatabase({ onSuccessRedirect, onCancel }) {
  const [formData, setFormData] = useState({
    db_name: '',
    db_type: 'mysql',
    host: 'localhost',
    port: 3306,
    username: 'root',
    password: '',
    database: ''
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: name === 'port' ? parseInt(value) || 0 : value
    }));
  };

  const handleEngineChange = (type) => {
    setFormData(prev => ({
      ...prev,
      db_type: type,
      port: ENGINE_CONFIGS[type]?.defaultPort || 3306
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage(null);
    try {
      const response = await axios.post(
        'http://localhost:8000/api/databases/add',
        formData
      );
      setMessage({ type: 'success', text: 'Connected: ' + response.data.message });
      if (onSuccessRedirect) {
        setTimeout(onSuccessRedirect, 1000);
      }
    } catch (error) {
      const errorMsg = error.response?.data?.message
        || error.response?.data?.detail
        || 'Connection failed. Please check host, credentials and port.';
      setMessage({
        type: 'error',
        text: '❌ ' + errorMsg
      });
    }
    setLoading(false);
  };

  const isSqlite = formData.db_type === 'sqlite';

  return (
    <div style={styles.container} className="animate-fade-in">
      <div style={styles.card}>
        <div style={styles.header}>
          <h1 style={{ marginBottom: '8px', fontSize: '34px', fontWeight: '700', letterSpacing: '-0.01em', color: '#FFFFFF' }}>
            SQL QueryAgent — Connect Database
          </h1>
          <p style={styles.subtitle}>Connect a database to your SQL QueryAgent.</p>
        </div>

        {message && (
          <div style={{
            ...styles.messageBox,
            borderColor: message.type === 'success' ? '#10B981' : '#EF4444',
            background: message.type === 'success' ? '#081810' : '#1A0808',
            color: message.type === 'success' ? '#10B981' : '#F87171'
          }}>
            {message.text}
          </div>
        )}

        <form onSubmit={handleSubmit} style={styles.form}>
          {/* Selectable Engine Cards */}
          <div>
            <label style={styles.fieldLabel}>Database Engine</label>
            <div style={styles.engineChoiceGrid}>
              {['mysql', 'postgresql', 'mssql'].map(engKey => {
                const cfg = ENGINE_CONFIGS[engKey];
                const isSelected = formData.db_type === engKey;
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

          <div>
            <label style={styles.fieldLabel}>Connection Display Name *</label>
            <input
              type="text"
              name="db_name"
              value={formData.db_name}
              onChange={handleChange}
              placeholder="e.g. Office Management Database"
              required
              style={styles.formInput}
            />
          </div>

          {!isSqlite && (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '12px' }}>
                <div>
                  <label style={styles.fieldLabel}>Host / Server Address *</label>
                  <input
                    type="text"
                    name="host"
                    value={formData.host}
                    onChange={handleChange}
                    placeholder="localhost"
                    required
                    style={styles.formInput}
                  />
                </div>
                <div>
                  <label style={styles.fieldLabel}>Port *</label>
                  <input
                    type="number"
                    name="port"
                    value={formData.port}
                    onChange={handleChange}
                    required
                    style={styles.formInput}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={styles.fieldLabel}>Username *</label>
                  <input
                    type="text"
                    name="username"
                    value={formData.username}
                    onChange={handleChange}
                    placeholder="root"
                    required
                    style={styles.formInput}
                  />
                </div>
                <div>
                  <label style={styles.fieldLabel}>Password</label>
                  <input
                    type="password"
                    name="password"
                    value={formData.password}
                    onChange={handleChange}
                    placeholder="••••••••"
                    style={styles.formInput}
                  />
                </div>
              </div>
            </>
          )}

          <div>
            <label style={styles.fieldLabel}>
              {isSqlite ? 'SQLite File Path / Name *' : 'Database Name *'}
            </label>
            <input
              type="text"
              name="database"
              value={formData.database}
              onChange={handleChange}
              placeholder={isSqlite ? 'e.g., college.db' : 'e.g., office_management_db'}
              required
              style={styles.formInput}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '12px' }}>
            {onCancel && (
              <button
                type="button"
                onClick={onCancel}
                style={styles.btnSecondary}
              >
                Cancel
              </button>
            )}
            <button
              type="submit"
              disabled={loading}
              style={styles.btnPrimary}
            >
              {loading ? 'Testing Connection...' : 'Test & Add Database'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const styles = {
  container: {
    width: '100%',
    maxWidth: 'none',
    margin: 0,
    padding: '30px 0',
    display: 'flex',
    justifyContent: 'center'
  },
  card: {
    width: '100%',
    maxWidth: '680px',
    background: '#0D0D0D',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '16px',
    padding: '32px',
    boxShadow: '0 20px 40px rgba(0,0,0,0.8)'
  },
  header: {
    marginBottom: '24px'
  },
  title: {
    fontSize: '34px',
    fontWeight: '700',
    letterSpacing: '-0.01em',
    color: '#FFFFFF',
    margin: 0
  },
  subtitle: {
    fontSize: '15px',
    color: '#A0A0A0',
    marginTop: '6px',
    lineHeight: '1.5'
  },
  messageBox: {
    padding: '12px 16px',
    borderRadius: '8px',
    border: '1px solid',
    fontSize: '15px',
    marginBottom: '16px'
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px'
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
    gap: '6px'
  },
  btnPrimary: {
    background: '#FFFFFF',
    color: '#000000',
    border: 'none',
    borderRadius: '8px',
    padding: '12px 24px',
    fontSize: '15px',
    fontWeight: '600',
    cursor: 'pointer'
  },
  btnSecondary: {
    background: '#0D0D0D',
    color: '#FFFFFF',
    border: '1px solid rgba(255, 255, 255, 0.15)',
    borderRadius: '8px',
    padding: '12px 20px',
    fontSize: '15px',
    fontWeight: '500',
    cursor: 'pointer'
  }
};