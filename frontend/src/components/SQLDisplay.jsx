import { useState } from 'react';
import { format } from 'sql-formatter';

export default function SQLDisplay({ sql }) {
  const [isOpen, setIsOpen] = useState(false);

  if (!sql) return null;

  let formatted = sql;
  try {
    formatted = format(sql, { language: 'sqlite' });
  } catch {
    // Use raw SQL if formatting fails
  }

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
            style={{ backgroundColor: 'var(--color-accent)', color: 'white' }}>
            SQL
          </span>
          Generated Query
        </span>
        <span className="text-xs">{isOpen ? '▲' : '▼'}</span>
      </button>
      {isOpen && (
        <pre
          className="px-4 py-3 overflow-x-auto"
          style={{
            backgroundColor: 'var(--color-bg)',
            color: '#93c5fd',
            fontSize: '12px',
            lineHeight: '1.6',
            margin: 0,
            border: 'none',
          }}
        >
          {formatted}
        </pre>
      )}
    </div>
  );
}
