import React, { useState, useCallback } from 'react';
import { CresControlData } from '../hooks/useWebSocket';

interface OutputsPanelProps {
  data: CresControlData;
  sendCommand: (command: string) => void;
}

const OutputsPanel: React.FC<OutputsPanelProps> = ({ data, sendCommand }) => {
  const [pendingCommands, setPendingCommands] = useState<Set<string>>(new Set());

  const formatVoltage = (value: string | undefined) => {
    if (!value) return '0.00';
    const num = parseFloat(value);
    return isNaN(num) ? '0.00' : num.toFixed(2);
  };

  const isEnabled = (value: string | undefined) => {
    return value === 'true' || value === '1';
  };

  const handleVoltageChange = useCallback((output: string, voltage: number) => {
    const command = `${output}:voltage=${voltage.toFixed(2)}`;
    sendCommand(command);
    
    // Track pending command
    setPendingCommands(prev => new Set(prev).add(`${output}:voltage`));
    setTimeout(() => {
      setPendingCommands(prev => {
        const newSet = new Set(prev);
        newSet.delete(`${output}:voltage`);
        return newSet;
      });
    }, 1000);
  }, [sendCommand]);

  const handleEnabledToggle = useCallback((output: string, enabled: boolean) => {
    const command = `${output}:enabled=${enabled ? '1' : '0'}`;
    sendCommand(command);
    
    // Track pending command
    setPendingCommands(prev => new Set(prev).add(`${output}:enabled`));
    setTimeout(() => {
      setPendingCommands(prev => {
        const newSet = new Set(prev);
        newSet.delete(`${output}:enabled`);
        return newSet;
      });
    }, 1000);
  }, [sendCommand]);

  const OutputControl: React.FC<{ 
    output: string; 
    label: string; 
  }> = ({ output, label }) => {
    const voltage = parseFloat(data[`${output}:voltage`] || '0');
    const enabled = isEnabled(data[`${output}:enabled`]);
    const isPendingVoltage = pendingCommands.has(`${output}:voltage`);
    const isPendingEnabled = pendingCommands.has(`${output}:enabled`);

    return (
      <div className="card">
        <div className="card-header">
          <h4 className="card-title">{label}</h4>
          <div className={`status-indicator ${enabled ? 'status-connected' : 'status-disconnected'}`}></div>
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="control-group">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <label className="control-label">Enabled</label>
              <label className="switch">
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={(e) => handleEnabledToggle(output, e.target.checked)}
                  disabled={isPendingEnabled}
                />
                <span className="switch-slider"></span>
              </label>
            </div>
          </div>
          
          <div className="control-group">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <label className="control-label">Voltage</label>
              <span style={{ 
                fontSize: '16px', 
                fontWeight: '600',
                color: isPendingVoltage ? '#ff9800' : '#333'
              }}>
                {voltage.toFixed(2)}V
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="10"
              step="0.1"
              value={voltage}
              onChange={(e) => handleVoltageChange(output, parseFloat(e.target.value))}
              className="slider"
              disabled={!enabled || isPendingVoltage}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#666', marginTop: '4px' }}>
              <span>0V</span>
              <span>10V</span>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title">Analog Outputs</h3>
      </div>
      
      <div className="grid grid-3">
        <OutputControl output="out-a" label="Output A" />
        <OutputControl output="out-b" label="Output B" />
        <OutputControl output="out-c" label="Output C" />
        <OutputControl output="out-d" label="Output D" />
        <OutputControl output="out-e" label="Output E" />
        <OutputControl output="out-f" label="Output F" />
      </div>
    </div>
  );
};

export default OutputsPanel;