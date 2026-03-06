import { useState, useRef, useEffect } from 'react';
import { queryAgentStream } from './services/api';
import Composer from './components/Composer';
import MessageBubble from './components/MessageBubble';
import AgentSteps from './components/AgentSteps';
import SQLDisplay from './components/SQLDisplay';
import ChartRenderer from './components/ChartRenderer';
import QuickQuestions from './components/QuickQuestions';

function App() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [liveSteps, setLiveSteps] = useState([]);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, liveSteps]);

  const handleSubmit = async (question) => {
    setMessages((prev) => [...prev, { type: 'user', content: question }]);
    setIsLoading(true);
    setLiveSteps([]);

    try {
      const result = await queryAgentStream(question, (step) => {
        setLiveSteps((prev) => [...prev, step]);
      });
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
      setLiveSteps([]);
    }
  };

  const showWelcome = messages.length === 0 && !isLoading;

  return (
    <div className="flex flex-col h-screen" style={{ backgroundColor: 'var(--color-bg)' }}>
      {/* Header */}
      <header
        className="flex items-center justify-between px-6 py-4 border-b"
        style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-surface)' }}
      >
        <div className="flex items-center gap-3">
          <span className="text-2xl">📊</span>
          <div>
            <h1 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
              Acme Analytics
            </h1>
            <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              BI Agent Demo
            </p>
          </div>
        </div>
        {messages.length > 0 && (
          <button
            onClick={() => { setMessages([]); setIsLoading(false); }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border transition-colors hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer"
            style={{ color: 'var(--color-text-secondary)', borderColor: 'var(--color-border)' }}
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 20h9" /><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
            </svg>
            New Chat
          </button>
        )}
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
              <div className="space-y-1.5">
                {liveSteps.map((step, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                    <span className="font-medium" style={{ color: '#22c55e' }}>✓</span>
                    <span className="font-medium" style={{ color: 'var(--color-text)' }}>{step.agent}</span>
                    <span>{step.detail}</span>
                  </div>
                ))}
                <div className="flex items-center gap-2">
                  <div className="flex gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                  <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                    {liveSteps.length === 0 ? 'Starting pipeline...' : 'Processing...'}
                  </span>
                </div>
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
