import { useState, useRef, useEffect } from 'react';
import { queryAgent } from './services/api';
import Composer from './components/Composer';
import MessageBubble from './components/MessageBubble';
import AgentSteps from './components/AgentSteps';
import SQLDisplay from './components/SQLDisplay';
import ChartRenderer from './components/ChartRenderer';
import QuickQuestions from './components/QuickQuestions';

function App() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (question) => {
    // Add user message
    setMessages((prev) => [...prev, { type: 'user', content: question }]);
    setIsLoading(true);

    try {
      const result = await queryAgent(question);
      setMessages((prev) => [
        ...prev,
        {
          type: 'ai',
          content: result.answer,
          sql: result.sql,
          results: result.results,
          chart: result.chart,
          steps: result.steps,
          execution_time_ms: result.execution_time_ms,
          complexity: result.complexity,
          trace_id: result.trace_id,
        },
      ]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { type: 'error', content: error.message },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const showWelcome = messages.length === 0 && !isLoading;

  return (
    <div className="flex flex-col h-screen" style={{ backgroundColor: 'var(--color-bg)' }}>
      {/* Header */}
      <header
        className="flex items-center gap-3 px-6 py-4 border-b"
        style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-surface)' }}
      >
        <span className="text-2xl">📊</span>
        <div>
          <h1 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
            Acme Analytics
          </h1>
          <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
            BI Agent Demo
          </p>
        </div>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-4xl mx-auto space-y-6">
          {showWelcome && (
            <div className="text-center py-16">
              <h2 className="text-3xl font-bold mb-3" style={{ color: 'var(--color-text)' }}>
                Ask anything about your data
              </h2>
              <p className="text-base mb-8" style={{ color: 'var(--color-text-secondary)' }}>
                I'll generate SQL, execute it, and explain the results using multi-agent voting consensus.
              </p>
              <QuickQuestions onSelect={handleSubmit} />
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i}>
              {msg.type === 'user' && (
                <MessageBubble type="user">{msg.content}</MessageBubble>
              )}
              {msg.type === 'ai' && (
                <div className="space-y-3">
                  <MessageBubble type="ai">{msg.content}</MessageBubble>
                  {msg.sql && <SQLDisplay sql={msg.sql} />}
                  {msg.chart && <ChartRenderer spec={msg.chart} results={msg.results} />}
                  {msg.steps && msg.steps.length > 0 && (
                    <AgentSteps
                      steps={msg.steps}
                      executionTime={msg.execution_time_ms}
                      complexity={msg.complexity}
                      traceId={msg.trace_id}
                    />
                  )}
                </div>
              )}
              {msg.type === 'error' && (
                <MessageBubble type="error">{msg.content}</MessageBubble>
              )}
            </div>
          ))}

          {isLoading && (
            <MessageBubble type="ai">
              <div className="flex items-center gap-2">
                <div className="flex gap-1">
                  <span className="w-2 h-2 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-2 h-2 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-2 h-2 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
                <span style={{ color: 'var(--color-text-secondary)' }}>Running agent pipeline...</span>
              </div>
            </MessageBubble>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Composer */}
      <div className="border-t px-4 py-4" style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-surface)' }}>
        <div className="max-w-4xl mx-auto">
          <Composer onSubmit={handleSubmit} isLoading={isLoading} />
        </div>
      </div>
    </div>
  );
}

export default App;
