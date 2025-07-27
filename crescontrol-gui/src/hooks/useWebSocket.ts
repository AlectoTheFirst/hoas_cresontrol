import { useState, useEffect, useRef, useCallback } from 'react';

export interface CresControlData {
  [key: string]: string;
}

export interface WebSocketState {
  isConnected: boolean;
  data: CresControlData;
  error: string | null;
  sendCommand: (command: string) => void;
  reconnect: () => void;
}

export const useWebSocket = (url: string): WebSocketState => {
  const [isConnected, setIsConnected] = useState(false);
  const [data, setData] = useState<CresControlData>({});
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        setError(null);
        
        // Send initial commands to get current state
        const initialCommands = [
          'in-a:voltage',
          'in-b:voltage',
          'fan:enabled',
          'fan:rpm',
          'fan:duty-cycle',
          'out-a:enabled',
          'out-a:voltage',
          'out-b:enabled',
          'out-b:voltage',
          'out-c:enabled',
          'out-c:voltage',
          'out-d:enabled',
          'out-d:voltage',
          'out-e:enabled',
          'out-e:voltage',
          'out-f:enabled',
          'out-f:voltage',
          'switch-12v:enabled',
          'switch-24v-a:enabled',
          'switch-24v-b:enabled'
        ];
        
        initialCommands.forEach(cmd => {
          setTimeout(() => ws.send(cmd), 100);
        });
      };

      ws.onmessage = (event) => {
        const message = event.data;
        console.log('Received:', message);
        
        // Parse CresControl format: "parameter::value"
        if (message.includes('::')) {
          const [param, value] = message.split('::', 2);
          setData(prev => ({
            ...prev,
            [param.trim()]: value.trim()
          }));
        }
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);
        
        // Auto-reconnect after 3 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          console.log('Attempting to reconnect...');
          connect();
        }, 3000);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setError('Connection error');
        setIsConnected(false);
      };

    } catch (err) {
      console.error('Failed to create WebSocket:', err);
      setError('Failed to connect');
    }
  }, [url]);

  const sendCommand = useCallback((command: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      console.log('Sending command:', command);
      wsRef.current.send(command);
    } else {
      console.warn('WebSocket not connected, cannot send command:', command);
    }
  }, []);

  const reconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    connect();
  }, [connect]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return {
    isConnected,
    data,
    error,
    sendCommand,
    reconnect
  };
};