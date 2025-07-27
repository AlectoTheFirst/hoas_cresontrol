import React from 'react';
import './App.css';
import { useWebSocket } from './hooks/useWebSocket';
import Header from './components/Header';
import InputsPanel from './components/InputsPanel';
import OutputsPanel from './components/OutputsPanel';
import SystemPanel from './components/SystemPanel';

const WEBSOCKET_URL = 'ws://192.168.105.15:81/websocket';

function App() {
  const { isConnected, data, error, sendCommand, reconnect } = useWebSocket(WEBSOCKET_URL);

  return (
    <div className="App">
      <Header 
        isConnected={isConnected} 
        error={error} 
        onReconnect={reconnect}
        deviceData={data}
      />
      
      <div className="main-content">
        <div className="sidebar">
          <InputsPanel data={data} />
        </div>
        
        <div className="content">
          <OutputsPanel data={data} sendCommand={sendCommand} />
          <SystemPanel data={data} sendCommand={sendCommand} />
        </div>
      </div>
    </div>
  );
}

export default App;
