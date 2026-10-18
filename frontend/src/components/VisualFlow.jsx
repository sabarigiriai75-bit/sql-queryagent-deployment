import React from 'react';

export default function VisualFlow() {
  return (
    <div style={{
      width: '100%',
      padding: '24px 20px',
      background: '#080808',
      borderRadius: '12px',
      border: '1px solid rgba(255, 255, 255, 0.08)',
      margin: '20px 0 28px 0',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: '16px'
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justify: 'center',
        width: '100%',
        maxWidth: '720px',
        gap: '8px',
        flexWrap: 'wrap'
      }}>
        {/* Node 1: Database */}
        <div style={nodeStyle}>
          <div style={iconBadgeStyle}>🗄️</div>
          <div style={nodeTextStyle}>
            <span style={nodeTitleStyle}>Database Node</span>
            <span style={nodeSubStyle}>MySQL / Postgres / MSSQL</span>
          </div>
        </div>

        {/* Flow Line 1 */}
        <div style={arrowWrapperStyle}>
          <div style={arrowLineStyle}></div>
          <span style={arrowBadgeStyle}>SCHEMA & METADATA</span>
        </div>

        {/* Node 2: AI Agent */}
        <div style={{ ...nodeStyle, borderColor: 'rgba(59, 130, 246, 0.4)', background: '#0E1726' }}>
          <div style={{ ...iconBadgeStyle, background: 'rgba(59, 130, 246, 0.2)', color: '#60A5FA' }}>🤖</div>
          <div style={nodeTextStyle}>
            <span style={{ ...nodeTitleStyle, color: '#FFFFFF' }}>SQL AI Agent</span>
            <span style={{ ...nodeSubStyle, color: '#93C5FD' }}>NL ➔ SQL Translation</span>
          </div>
        </div>

        {/* Flow Line 2 */}
        <div style={arrowWrapperStyle}>
          <div style={arrowLineStyle}></div>
          <span style={arrowBadgeStyle}>SQL EXECUTION</span>
        </div>

        {/* Node 3: Results */}
        <div style={nodeStyle}>
          <div style={iconBadgeStyle}>⚡</div>
          <div style={nodeTextStyle}>
            <span style={nodeTitleStyle}>Query Results</span>
            <span style={nodeSubStyle}>Real-time Table / JSON</span>
          </div>
        </div>
      </div>
    </div>
  );
}

const nodeStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: '12px',
  padding: '12px 16px',
  background: '#121212',
  border: '1px solid rgba(255, 255, 255, 0.1)',
  borderRadius: '10px',
  minWidth: '200px'
};

const iconBadgeStyle = {
  width: '36px',
  height: '36px',
  borderRadius: '8px',
  background: 'rgba(255, 255, 255, 0.05)',
  display: 'flex',
  alignItems: 'center',
  justify: 'center',
  fontSize: '18px'
};

const nodeTextStyle = {
  display: 'flex',
  flexDirection: 'column'
};

const nodeTitleStyle = {
  fontSize: '14px',
  fontWeight: '600',
  color: '#E5E5E5'
};

const nodeSubStyle = {
  fontSize: '12px',
  color: '#888888'
};

const arrowWrapperStyle = {
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  padding: '0 4px',
  minWidth: '110px'
};

const arrowLineStyle = {
  width: '100%',
  height: '1px',
  background: 'linear-gradient(90deg, rgba(255,255,255,0.05) 0%, rgba(59,130,246,0.6) 50%, rgba(255,255,255,0.05) 100%)',
  position: 'relative',
  margin: '4px 0'
};

const arrowBadgeStyle = {
  fontSize: '11px',
  fontWeight: '600',
  letterSpacing: '0.05em',
  color: '#888888',
  textTransform: 'uppercase'
};
