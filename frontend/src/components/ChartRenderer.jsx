import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';

const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899', '#f97316'];

const formatNumber = (value) => {
  if (typeof value !== 'number') return value;
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return Number.isInteger(value) ? value.toString() : value.toFixed(2);
};

const prettifyLabel = (name) =>
  name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

const formatTooltipValue = (value, name) => {
  const formatted = typeof value === 'number'
    ? value.toLocaleString(undefined, { maximumFractionDigits: 2 })
    : value;
  return [formatted, prettifyLabel(name)];
};

const tooltipStyle = { backgroundColor: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8 };
const tickStyle = { fill: 'var(--color-text-secondary)', fontSize: 11 };

export default function ChartRenderer({ spec, results }) {
  if (!spec || !results || results.length === 0) return null;

  // Use chart data or fall back to results
  const data = (spec.data && spec.data.length > 0) ? spec.data : results.filter(r => !r._summary);
  const { type, xKey, yKey, yKeys, title } = spec;

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
      <ResponsiveContainer width="100%" height={type === 'horizontal_bar' ? Math.max(200, data.length * 40) : 300}>
        {type === 'bar' && (
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis dataKey={xKey} tick={tickStyle} />
            <YAxis tick={tickStyle} tickFormatter={formatNumber} />
            <Tooltip contentStyle={tooltipStyle} formatter={formatTooltipValue} />
            <Bar dataKey={yKey} fill={COLORS[0]} radius={[4, 4, 0, 0]} />
          </BarChart>
        )}
        {type === 'horizontal_bar' && (
          <BarChart data={data} layout="vertical" margin={{ left: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis type="number" tick={tickStyle} tickFormatter={formatNumber} />
            <YAxis type="category" dataKey={yKey} tick={tickStyle} width={120} />
            <Tooltip contentStyle={tooltipStyle} formatter={formatTooltipValue} />
            <Bar dataKey={xKey} fill={COLORS[0]} radius={[0, 4, 4, 0]} />
          </BarChart>
        )}
        {type === 'line' && (
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis dataKey={xKey} tick={tickStyle} />
            <YAxis tick={tickStyle} tickFormatter={formatNumber} />
            <Tooltip contentStyle={tooltipStyle} formatter={formatTooltipValue} />
            <Line type="monotone" dataKey={yKey} stroke={COLORS[0]} strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        )}
        {type === 'multi_line' && yKeys && (
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis dataKey={xKey} tick={tickStyle} />
            <YAxis tick={tickStyle} tickFormatter={formatNumber} />
            <Tooltip contentStyle={tooltipStyle} formatter={formatTooltipValue} />
            <Legend />
            {yKeys.map((key, i) => (
              <Line key={key} type="monotone" dataKey={key} stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={{ r: 3 }} />
            ))}
          </LineChart>
        )}
        {type === 'stacked_bar' && yKeys && (
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis dataKey={xKey} tick={tickStyle} />
            <YAxis tick={tickStyle} tickFormatter={formatNumber} />
            <Tooltip contentStyle={tooltipStyle} formatter={formatTooltipValue} />
            <Legend />
            {yKeys.map((key, i) => (
              <Bar key={key} dataKey={key} stackId="stack" fill={COLORS[i % COLORS.length]} />
            ))}
          </BarChart>
        )}
        {type === 'pie' && (
          <PieChart>
            <Pie data={data} dataKey={yKey} nameKey={xKey} cx="50%" cy="50%" outerRadius={100} label>
              {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} formatter={formatTooltipValue} />
            <Legend />
          </PieChart>
        )}
        {type === 'scatter' && (
          <ScatterChart>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis dataKey={xKey} tick={tickStyle} tickFormatter={formatNumber} />
            <YAxis dataKey={yKey} tick={tickStyle} tickFormatter={formatNumber} />
            <Tooltip contentStyle={tooltipStyle} formatter={formatTooltipValue} />
            <Scatter data={data} fill={COLORS[0]} />
          </ScatterChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
