import { useState } from 'react';

export default function AgentSteps({ steps, executionTime, complexity, traceId }) {
  const [isOpen, setIsOpen] = useState(false);

  if (!steps || steps.length === 0) return null;

  return (
    <div
      className="rounded-lg overflow-hidden text-sm"
      style={{ border: '1px solid var(--color-border)' }}
    >
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-2 text-left transition-colors"
        style={{
          backgroundColor: 'var(--color-surface)',
          color: 'var(--color-text-secondary)',
        }}
      >
        <span className="flex items-center gap-2">
          <span className="font-mono text-xs px-1.5 py-0.5 rounded"
            style={{ backgroundColor: '#22c55e', color: 'white' }}>
            TRACE
          </span>
          Agent Pipeline ({steps.length} steps, {executionTime}ms)
          {complexity && (
            <span className="text-xs opacity-60">
              K={complexity.k_threshold}
            </span>
          )}
        </span>
        <span className="text-xs">{isOpen ? '▲' : '▼'}</span>
      </button>
      {isOpen && (
        <div className="px-4 py-3 space-y-1" style={{ backgroundColor: 'var(--color-bg)' }}>
          {traceId && (
            <div className="text-xs mb-2 font-mono" style={{ color: 'var(--color-text-secondary)' }}>
              trace_id: {traceId}
            </div>
          )}
          {steps.map((step, i) => (
            <div key={i} className="flex gap-3 text-xs py-1">
              <span
                className="shrink-0 font-medium w-40 truncate"
                style={{ color: 'var(--color-accent)' }}
              >
                {step.agent}
              </span>
              <span style={{ color: 'var(--color-text-secondary)' }}>
                {step.detail}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
