const API_BASE = '/api';

export async function queryAgent(question) {
  const response = await fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

export async function getSchema() {
  const response = await fetch(`${API_BASE}/schema`);
  if (!response.ok) throw new Error('Failed to fetch schema');
  return response.json();
}
