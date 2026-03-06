import ReactMarkdown from 'react-markdown';

const styles = {
  user: {
    container: 'flex justify-end',
    bubble: {
      backgroundColor: 'var(--color-accent)',
      color: 'white',
      borderRadius: '16px 16px 4px 16px',
      padding: '10px 16px',
      maxWidth: '80%',
    },
  },
  ai: {
    container: 'flex justify-start',
    bubble: {
      backgroundColor: 'var(--color-surface)',
      color: 'var(--color-text)',
      borderRadius: '16px 16px 16px 4px',
      padding: '12px 16px',
      maxWidth: '100%',
      border: '1px solid var(--color-border)',
    },
  },
  error: {
    container: 'flex justify-start',
    bubble: {
      backgroundColor: '#1a0a0a',
      color: 'var(--color-error)',
      borderRadius: '16px 16px 16px 4px',
      padding: '12px 16px',
      maxWidth: '100%',
      border: '1px solid #7f1d1d',
    },
  },
};

export default function MessageBubble({ type = 'ai', children }) {
  const s = styles[type] || styles.ai;

  return (
    <div className={s.container}>
      <div style={s.bubble} className="text-sm leading-relaxed">
        {type === 'ai' && typeof children === 'string' ? (
          <ReactMarkdown>{children}</ReactMarkdown>
        ) : (
          children
        )}
      </div>
    </div>
  );
}
