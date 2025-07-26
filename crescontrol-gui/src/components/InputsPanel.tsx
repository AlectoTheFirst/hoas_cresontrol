import React from 'react';
import { CresControlData } from '../hooks/useWebSocket';

interface InputsPanelProps {
  data: CresControlData;
}

const InputsPanel: React.FC<InputsPanelProps> = ({ data }) => {
  const formatVoltage = (value: string | undefined) => {
    if (!value) return '0.00';
    const num = parseFloat(value);
    return isNaN(num) ? '0.00' : num.toFixed(2);
  };

  const formatRPM = (value: string | undefined) => {
    if (!value) return '0';
    const num = parseInt(value);
    return isNaN(num) ? '0' : num.toString();
  };

  const formatPercentage = (value: string | undefined) => {
    if (!value) return '0';
    const num = parseFloat(value);
    return isNaN(num) ? '0' : Math.round(num).toString();
  };

  const isEnabled = (value: string | undefined) => {
    return value === 'true' || value === '1';
  };

  return (
    <>
      {/* Analog Inputs */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Analog Inputs</h3>
          <div className={`status-indicator ${data['in-a:voltage'] || data['in-b:voltage'] ? 'status-connected' : 'status-disconnected'}`}></div>
        </div>
        
        <div className="grid grid-2">
          <div className="metric">
            <div className="metric-label">Input A</div>
            <div className="metric-value">
              {formatVoltage(data['in-a:voltage'])}
              <span className="metric-unit">V</span>
            </div>
          </div>
          
          <div className="metric">
            <div className="metric-label">Input B</div>
            <div className="metric-value">
              {formatVoltage(data['in-b:voltage'])}
              <span className="metric-unit">V</span>
            </div>
          </div>
        </div>
      </div>

      {/* Fan Status */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Fan Status</h3>
          <div className={`status-indicator ${isEnabled(data['fan:enabled']) ? 'status-connected' : 'status-disconnected'}`}></div>
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="metric">
            <div className="metric-label">RPM</div>
            <div className="metric-value">
              {formatRPM(data['fan:rpm'])}
              <span className="metric-unit">rpm</span>
            </div>
          </div>
          
          <div className="metric">
            <div className="metric-label">Duty Cycle</div>
            <div className="metric-value">
              {formatPercentage(data['fan:duty-cycle'])}
              <span className="metric-unit">%</span>
            </div>
          </div>
          
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="metric-label">Enabled</span>
            <div className={`status-indicator ${isEnabled(data['fan:enabled']) ? 'status-connected' : 'status-disconnected'}`}></div>
          </div>
        </div>
      </div>

      {/* System Info */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">System Info</h3>
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '14px' }}>
          {data['wifi:client:ip'] && (
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#666' }}>IP Address:</span>
              <span style={{ fontWeight: '500' }}>{data['wifi:client:ip']}</span>
            </div>
          )}
          
          {data['firmware:version'] && (
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#666' }}>Firmware:</span>
              <span style={{ fontWeight: '500' }}>{data['firmware:version']}</span>
            </div>
          )}
          
          {data['system:frequency'] && (
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#666' }}>Frequency:</span>
              <span style={{ fontWeight: '500' }}>{data['system:frequency']} Hz</span>
            </div>
          )}
          
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#666' }}>Connection:</span>
            <span style={{ fontWeight: '500', color: '#4caf50' }}>WebSocket</span>
          </div>
        </div>
      </div>
    </>
  );
};

export default InputsPanel;