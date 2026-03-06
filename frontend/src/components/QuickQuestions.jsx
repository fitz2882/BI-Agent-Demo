const QUESTIONS = [
  "What are the top 5 customers by lifetime value?",
  "Show me total revenue by product category",
  "How many orders were placed each month in 2024?",
  "What is the average order value?",
  "Which products have the highest profit margin?",
  "How many employees are in each department?",
];

export default function QuickQuestions({ onSelect }) {
  return (
    <div className="flex flex-wrap justify-center gap-2 max-w-2xl mx-auto">
      {QUESTIONS.map((q) => (
        <button
          key={q}
          onClick={() => onSelect(q)}
          className="px-4 py-2 text-sm rounded-full transition-colors cursor-pointer"
          style={{
            backgroundColor: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            color: 'var(--color-text-secondary)',
          }}
          onMouseEnter={(e) => {
            e.target.style.borderColor = 'var(--color-accent)';
            e.target.style.color = 'var(--color-text)';
          }}
          onMouseLeave={(e) => {
            e.target.style.borderColor = 'var(--color-border)';
            e.target.style.color = 'var(--color-text-secondary)';
          }}
        >
          {q}
        </button>
      ))}
    </div>
  );
}
