'use client';

import { useState, useEffect, useRef } from 'react';
import { authService } from '../lib/auth';
import { useRouter } from 'next/navigation';

interface Message {
  id: string;
  content: string;
  sender: 'user' | 'AAD Agent';
  timestamp: Date;
}

export default function Chat() {
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);

  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [pendingMessage, setPendingMessage] = useState<string>('');
  const [shouldSendMessage, setShouldSendMessage] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    checkAuthStatus();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Create thread when user is authenticated
  useEffect(() => {
    if (isAuthenticated && !threadId) { createThread(); }
  }, [isAuthenticated, threadId]);

  // Send message when thread is ready and message is pending
  useEffect(() => {
    if (threadId && shouldSendMessage && pendingMessage) {
      deliverMessage();
    }
  }, [threadId, shouldSendMessage, pendingMessage]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const checkAuthStatus = async () => {
    const authenticated = await authService.checkAuthStatus();
    setIsAuthenticated(authenticated);
  };

  const createThread = async () => {
    try {
      const threadResponse = await authService.authenticatedFetch('/api/threads', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({}),
      });

      if (!threadResponse.ok) {
        const errorText = await threadResponse.text();
        throw new Error(`Failed to create thread: ${threadResponse.status} - ${errorText}`);
      }
      const threadData = await threadResponse.json();
      setThreadId(threadData.thread_id);
    } catch (error) {
      console.error(error);
    }
  };

  const sendMessage = () => {
    if (!inputMessage.trim() || isLoading) return;
    const userMessage: Message = {
      id: Date.now().toString(), content: inputMessage,
      sender: 'user', timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setPendingMessage(inputMessage); // Set the pending message
    setInputMessage(''); // Clear the input
    setShouldSendMessage(true); // Trigger the send
  };

  const deliverMessage = async () => {
    if (!threadId || !pendingMessage) return;
    setIsLoading(true);
    setShouldSendMessage(false); // Reset the flag

    try {
      // Await the final result from the /wait endpoint
      const response = await authService.authenticatedFetch(`/api/threads/${threadId}/runs/wait`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          assistant_id: 'AAD Agent', // MUST ALIGN WITH AGENT NAME IN LANGGRAPH.JSON
          input: { messages: [pendingMessage] },
        }),
      });

      if (!response.ok) { throw new Error(`Failed to get agent response: ${response.status}`);}

      const data = await response.json();
      // Expecting data.messages to be an array of messages
      let agentContent = '';
      if (data.messages && Array.isArray(data.messages)) {
        const aiMessages = data.messages.filter((msg: any) => msg.type === 'ai');
        if (aiMessages.length > 0) {
          agentContent = aiMessages[aiMessages.length - 1].content;
        }
      }

      if (agentContent) {
        const agentMessage: Message = {
          id: (Date.now() + 1).toString(), content: agentContent,
          sender: 'AAD Agent', timestamp: new Date(),
        };
        setMessages(prev => [...prev, agentMessage]);
      } else {
        const agentMessage: Message = {
          id: (Date.now() + 1).toString(), content: 'No response received',
          sender: 'AAD Agent', timestamp: new Date(),
        };
        setMessages(prev => [...prev, agentMessage]);
      }
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: 'Sorry, there was an error processing your message. Error: ' + error,
        sender: 'AAD Agent', timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      setPendingMessage(''); // Clear the pending message
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleLogout = async () => {
    await authService.logout();
    setIsAuthenticated(false);
    setMessages([]);
    router.replace('/');
  };

  const handleLogin = async () => {
    try {
      const authUrl = await authService.getAuthUrl();
      window.location.href = authUrl;
    } catch (error) {
      console.error('Error starting auth flow:', error);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="auth-container">
        <h1>Welcome to LangGraph Chat</h1>
        <p>Please authenticate to start chatting with the agent.</p>
        <button 
          className="auth-button"
          onClick={handleLogin}
        >
          Sign in with Microsoft
        </button>
      </div>
    );
  }

  return (
    <div className="chat-container">
      <div className="status-indicator authenticated" style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 12 }}>
        <button 
          onClick={handleLogout}
          className="logout-button"
        >
          Logout
        </button>
      </div>

      <div className="chat-messages">
        {messages.length === 0 ? (
          <p style={{ textAlign: 'center', color: '#666', marginTop: '50px' }}>
            Start a conversation with the agent...
          </p>
        ) : (
          messages.map((message) => (
            <div key={message.id} className={`message ${message.sender}`}>
              <strong>{message.sender === 'user' ? 'You' : 'Agent'}:</strong>
              <div>{message.content}</div>
              <small style={{ color: '#666', fontSize: '12px' }}>
                {message.timestamp.toLocaleTimeString()}
              </small>
            </div>
          ))
        )}
        {isLoading && (
          <div className="message agent">
            <strong>Agent:</strong>
            <div>Thinking...</div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input">
        <input
          type="text"
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyDown={handleKeyPress}
          placeholder="Type your message..."
          disabled={isLoading}
        />
        <button onClick={sendMessage} disabled={isLoading || !inputMessage.trim()}>
          {isLoading ? 'Sending...' : 'Send'}
        </button>
      </div>
    </div>
  );
} 