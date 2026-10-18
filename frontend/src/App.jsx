import { useState } from 'react';
import DatabasesList from './pages/DatabasesList';
import QueryInterface from './pages/QueryInterface';
import AddDatabase from './pages/AddDatabase';

function App() {
  const [currentPage, setCurrentPage] = useState('databases');
  const [selectedDbId, setSelectedDbId] = useState(() => {
    return localStorage.getItem('sql_agent_selected_db_id') || '';
  });

  const handleSelectDbForQuery = (dbId) => {
    setSelectedDbId(dbId);
    if (dbId) {
      localStorage.setItem('sql_agent_selected_db_id', dbId);
    }
    setCurrentPage('query');
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        width: '100%',
        backgroundColor: '#000000',
        color: '#FFFFFF',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* TOP NAVIGATION BAR (full-width background, inner content uses page-container) */}
      <nav
        style={{
          backgroundColor: '#050505',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          padding: '14px 0', // CHANGED: side padding now comes from page-container
          position: 'sticky',
          top: 0,
          zIndex: 100,
          boxSizing: 'border-box',
          width: '100%',
        }}
      >
        <div
          className="page-container" // CHANGED: same width as main content
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          {/* Left: Branding */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <div
              style={{
                width: '38px',
                height: '38px',
                borderRadius: '8px',
                background: '#121212',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '18px',
              }}
            >
              ⚡
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h2 style={{ margin: 0, color: '#4CAF50', fontSize: '21px', fontWeight: '700' }}>
                  SQL QueryAgent
                </h2>
              </div>
              <div style={{ fontSize: '13px', color: '#888888', fontWeight: '500', marginTop: '2px' }}>
                Query Any Database in Plain English
              </div>
            </div>
          </div>

          {/* Center: Minimal Navigation */}
          <div
            style={{
              display: 'flex',
              gap: '8px',
              background: '#0A0A0A',
              padding: '5px',
              borderRadius: '10px',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <button
              onClick={() => setCurrentPage('databases')}
              style={{
                padding: '9px 18px',
                backgroundColor: currentPage === 'databases' ? '#1A1A1A' : 'transparent',
                color: currentPage === 'databases' ? '#FFFFFF' : '#A0A0A0',
                border:
                  currentPage === 'databases'
                    ? '1px solid rgba(255, 255, 255, 0.15)'
                    : '1px solid transparent',
                borderRadius: '7px',
                cursor: 'pointer',
                fontWeight: '500',
                fontSize: '15px',
                transition: 'all 0.15s ease-out',
              }}
            >
              Databases
            </button>

            <button
              onClick={() => setCurrentPage('query')}
              style={{
                padding: '9px 18px',
                backgroundColor: currentPage === 'query' ? '#1A1A1A' : 'transparent',
                color: currentPage === 'query' ? '#FFFFFF' : '#A0A0A0',
                border:
                  currentPage === 'query'
                    ? '1px solid rgba(255, 255, 255, 0.15)'
                    : '1px solid transparent',
                borderRadius: '7px',
                cursor: 'pointer',
                fontWeight: '500',
                fontSize: '15px',
                transition: 'all 0.15s ease-out',
              }}
            >
              Natural Language Query
            </button>
          </div>

          {/* Right: AI Connection Status */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                background: '#0D0D0D',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                padding: '7px 14px',
                borderRadius: '20px',
                fontSize: '14px',
                color: '#A0A0A0',
                fontWeight: '500',
              }}
            >
              <span
                style={{
                  width: '7px',
                  height: '7px',
                  borderRadius: '50%',
                  background: '#10B981',
                }}
              ></span>
              AI Agent Ready
            </div>
          </div>
        </div>
      </nav>

      {/* MAIN VIEWPORT CONTENT (centred) */}
      <main
        style={{
          flex: 1,
          width: '100%',
          backgroundColor: '#000000',
        }}
      >
        <div className="page-container">
          {currentPage === 'databases' && (
            <DatabasesList
              onSelectDatabaseForQuery={handleSelectDbForQuery}
              onOpenQueryTab={() => setCurrentPage('query')}
              onOpenAddTab={() => setCurrentPage('add')}
            />
          )}

          {currentPage === 'add' && (
            <AddDatabase
              onSuccessRedirect={(newConnId) => {
                if (newConnId) {
                  handleSelectDbForQuery(newConnId);
                } else {
                  setCurrentPage('databases');
                }
              }}
              onCancel={() => setCurrentPage('databases')}
            />
          )}

          {currentPage === 'query' && (
            <QueryInterface
              selectedDbId={selectedDbId}
              onSelectDb={(id) => {
                setSelectedDbId(id);
                if (id) {
                  localStorage.setItem('sql_agent_selected_db_id', id);
                }
              }}
            />
          )}
        </div>
      </main>

      {/* MINIMAL PRODUCT FOOTER (full-width background, inner content uses page-container) */}
      <footer
        style={{
          backgroundColor: '#050505',
          borderTop: '1px solid rgba(255, 255, 255, 0.08)',
          color: '#888888',
          padding: '22px 0', // CHANGED: side padding now comes from page-container
          fontSize: '14px',
          boxSizing: 'border-box',
          width: '100%',
        }}
      >
        <div
          className="page-container" // CHANGED: same width as main content
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '12px',
          }}
        >
          <div>
            SQL QueryAgent — Query Any Database in Plain English | Built by Sabari
          </div>
          <div>Powered by FastAPI + React + AI</div>
        </div>
      </footer>
    </div>
  );
}

export default App;