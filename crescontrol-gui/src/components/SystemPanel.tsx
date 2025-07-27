import React, { useState, useCallback } from 'react';
import { CresControlData } from '../hooks/useWebSocket';

interface SystemPanelProps {
  data: CresControlData;
  sendCommand: (command: string) => void;
}

const SystemPanel: React.FC<SystemPanelProps> = ({ data, sendCommand }) => {
  const [pendingCommands, setPendingCommands] = useState<Set<string>>(new Set());
  const [fanSpeed, setFanSpeed] = useState<number>(0);

  const isEnabled = (value: string | undefined) => {
    return value === 'true' || value === '1';
  };

  const formatPercentage = (value: string | undefined) => {
    if (!value) return 0;
    const num = parseFloat(value);
    return isNaN(num) ? 0 : num;
  };

  const handleSwitchToggle = useCallback((switchName: string, enabled: boolean) => {
    const command = `${switchName}:enabled=${enabled ? '1' : '0'}`;
    sendCommand(command);
    
    setPendingCommands(prev => new Set(prev).add(switchName));
    setTimeout(() => {
      setPendingCommands(prev => {
        const newSet = new Set(prev);
        newSet.delete(switchName);
        return newSet;
      });
    }, 1000);
  }, [sendCommand]);

  const handleFanSpeedChange = useCallback((speed: number) => {
    setFanSpeed(speed);
    const command = `fan:duty-cycle=${speed}`;
    sendCommand(command);
    
    // Also enable fan if speed > 0
    if (speed > 0 && !isEnabled(data['fan:enabled'])) {
      sendCommand('fan:enabled=1');
    }
    
    setPendingCommands(prev => new Set(prev).add('fan'));
    setTimeout(() => {
      setPendingCommands(prev => {
        const newSet = new Set(prev);
        newSet.delete('fan');
        return newSet;
      });
    }, 1000);
  }, [sendCommand, data]);

  const handleFanToggle = useCallback((enabled: boolean) => {
    const command = `fan:enabled=${enabled ? '1' : '0'}`;
    sendCommand(command);
    
    setPendingCommands(prev => new Set(prev).add('fan'));
    setTimeout(() => {
      setPendingCommands(prev => {
        const newSet = new Set(prev);
        newSet.delete('fan');
        return newSet;
      });
    }, 1000);
  }, [sendCommand]);

  const currentFanSpeed = formatPercentage(data['fan:duty-cycle']);
  const fanEnabled = isEnabled(data['fan:enabled']);
  const fanRPM = data['fan:rpm'] || '0';

  return (
    <div style={{ display: 'flex', gap: '20px' }}>
      {/* Fan Control */}
      <div className="card" style={{ flex: 1 }}>
        <div className="card-header">
          <h3 className="card-title">Fan Control</h3>
          <div className={`status-indicator ${fanEnabled ? 'status-connected' : 'status-disconnected'}`}></div>
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="metric-label">RPM</span>
            <span className="metric-value" style={{ fontSize: '20px' }}>
              {fanRPM}
              <span className="metric-unit">rpm</span>
            </span>
          </div>
          
          <div className="control-group">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <label className="control-label">Enabled</label>
              <label className="switch">
                <input
                  type="checkbox"
                  checked={fanEnabled}
                  onChange={(e) => handleFanToggle(e.target.checked)}
                  disabled={pendingCommands.has('fan')}
                />
                <span className="switch-slider"></span>
              </label>
            </div>
          </div>
          
          <div className="control-group">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <label className="control-label">Speed</label>
              <span style={{ 
                fontSize: '16px', 
                fontWeight: '600',
                color: pendingCommands.has('fan') ? '#ff9800' : '#333'
              }}>
                {Math.round(currentFanSpeed)}%
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              step="1"
              value={currentFanSpeed}
              onChange={(e) => handleFanSpeedChange(parseInt(e.target.value))}
              className="slider"
              disabled={!fanEnabled || pendingCommands.has('fan')}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#666', marginTop: '4px' }}>
              <span>0%</span>
              <span>100%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Power Switches */}
      <div className="card" style={{ flex: 1 }}>
        <div className="card-header">
          <h3 className="card-title">Power Switches</h3>
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div className="control-label">12V Switch</div>
              <div style={{ fontSize: '12px', color: '#666' }}>Main 12V power output</div>
            </div>
            <label className="switch">
              <input
                type="checkbox"
                checked={isEnabled(data['switch-12v:enabled'])}
                onChange={(e) => handleSwitchToggle('switch-12v', e.target.checked)}
                disabled={pendingCommands.has('switch-12v')}
              />
              <span className="switch-slider"></span>
            </label>
          </div>
          
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div className="control-label">24V Switch A</div>
              <div style={{ fontSize: '12px', color: '#666' }}>24V power output A</div>
            </div>
            <label className="switch">
              <input
                type="checkbox"
                checked={isEnabled(data['switch-24v-a:enabled'])}
                onChange={(e) => handleSwitchToggle('switch-24v-a', e.target.checked)}
                disabled={pendingCommands.has('switch-24v-a')}
              />
              <span className="switch-slider"></span>
            </label>
          </div>
          
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div className="control-label">24V Switch B</div>
              <div style={{ fontSize: '12px', color: '#666' }}>24V power output B</div>
            </div>
            <label className="switch">
              <input
                type="checkbox"
                checked={isEnabled(data['switch-24v-b:enabled'])}
                onChange={(e) => handleSwitchToggle('switch-24v-b', e.target.checked)}
                disabled={pendingCommands.has('switch-24v-b')}
              />
              <span className="switch-slider"></span>
            </label>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SystemPanel;