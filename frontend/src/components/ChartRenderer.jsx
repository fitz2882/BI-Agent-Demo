import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';

const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899', '#f97316'];

export default function ChartRenderer({ spec, results }) {
  if (!spec || !results || results.length === 0) return null;

  // Use chart data or fall back to results
  const data = (spec.data && spec.data.length > 0) ? spec.data : results.filter(r => !r._summary);
  const { type, xKey, yKey, title } = spec;

  return (
    <div
      className="rounded-lg p-4"
      style={{ backgroundColor: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
    >
      {title && (
        <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--color-text-secondary)' }}>
          {title}
        </h3>
      )}
      <ResponsiveContainer width="100%" height={300}>
        {type === 'bar' && (
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis dataKey={xKey} tick={{ fill: 'var(--color-text-secondary)', fontSize: 11 }} />
            <YAxis tick={{ fill: 'var(--color-text-secondary)', fontSize: 11 }} />
            <Tooltip contentStyle={{ backgroundColor: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8 }} />
            <Bar dataKey={yKey} fill={COLORS[0]} radius={[4, 4, 0, 0]} />
          </BarChart>
        )}
        {type === 'line' && (
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis dataKey={xKey} tick={{ fill: 'var(--color-text-secondary)', fontSize: 11 }} />
            <YAxis tick={{ fill: 'var(--color-text-secondary)', fontSize: 11 }} />
            <Tooltip contentStyle={{ backgroundColor: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8 }} />
            <Line type="monotone" dataKey={yKey} stroke={COLORS[0]} strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        )}
        {type === 'pie' && (
          <PieChart>
            <Pie data={data} dataKey={yKey} nameKey={xKey} cx="50%" cy="50%" outerRadius={100} label>
              {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
            </Pie>
            <Tooltip contentStyle={{ backgroundColor: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8 }} />
            <Legend />
          </PieChart>
        )}
        {type === 'scatter' && (
          <ScatterChart>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis dataKey={xKey} tick={{ fill: 'var(--color-text-secondary)', fontSize: 11 }} />
            <YAxis dataKey={yKey} tick={{ fill: 'var(--color-text-secondary)', fontSize: 11 }} />
            <Tooltip contentStyle={{ backgroundColor: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8 }} />
            <Scatter data={data} fill={COLORS[0]} />
          </ScatterChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
