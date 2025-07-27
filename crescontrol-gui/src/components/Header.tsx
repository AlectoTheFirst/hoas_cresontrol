import React from 'react';
import { CresControlData } from '../hooks/useWebSocket';

interface HeaderProps {
  isConnected: boolean;
  error: string | null;
  onReconnect: () => void;
  deviceData: CresControlData;
}

const Header: React.FC<HeaderProps> = ({ isConnected, error, onReconnect, deviceData }) => {
  const getConnectionStatus = () => {
    if (error) return { text: 'Error', class: 'status-warning' };
    if (isConnected) return { text: 'Connected', class: 'status-connected' };
    return { text: 'Disconnected', class: 'status-disconnected' };
  };

  const status = getConnectionStatus();

  return (
    <header style={{
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      color: 'white',
      padding: '20px',
      boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
    }}>
      <div style={{
        maxWidth: '1400px',
        margin: '0 auto',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div>
          <h1 style={{ fontSize: '28px', fontWeight: '700', marginBottom: '4px' }}>
            CresControl Dashboard
          </h1>
          <p style={{ fontSize: '16px', opacity: 0.9 }}>
            Device: 192.168.105.15:81
          </p>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>Status:</span>
            <span style={{ fontWeight: '600' }}>{status.text}</span>
            <div className={`status-indicator ${status.class}`}></div>
          </div>
          
          {!isConnected && (
            <button 
              className="button button-secondary"
              onClick={onReconnect}
              style={{ 
                backgroundColor: 'rgba(255,255,255,0.2)', 
                color: 'white',
                border: '1px solid rgba(255,255,255,0.3)'
              }}
            >
              Reconnect
            </button>
          )}
          
          {deviceData.type && (
            <div style={{ textAlign: 'right', fontSize: '14px', opacity: 0.9 }}>
              <div>Type: {deviceData.type}</div>
              {deviceData.serial && <div>Serial: {deviceData.serial}</div>}
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

export default Header;