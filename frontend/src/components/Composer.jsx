import { useState } from 'react';

export default function Composer({ onSubmit, isLoading }) {
  const [value, setValue] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    const q = value.trim();
    if (!q || isLoading) return;
    onSubmit(q);
    setValue('');
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-3">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Ask a question about your data..."
        disabled={isLoading}
        className="flex-1 px-4 py-3 rounded-xl text-sm outline-none transition-colors"
        style={{
          backgroundColor: 'var(--color-bg)',
          border: '1px solid var(--color-border)',
          color: 'var(--color-text)',
        }}
        onFocus={(e) => (e.target.style.borderColor = 'var(--color-accent)')}
        onBlur={(e) => (e.target.style.borderColor = 'var(--color-border)')}
      />
      <button
        type="submit"
        disabled={isLoading || !value.trim()}
        className="px-6 py-3 rounded-xl text-sm font-medium text-white transition-colors disabled:opacity-40"
        style={{ backgroundColor: 'var(--color-accent)' }}
      >
        {isLoading ? 'Running...' : 'Ask'}
      </button>
    </form>
  );
}
