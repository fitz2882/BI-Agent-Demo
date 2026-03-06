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

/**
 * Stream pipeline execution via SSE.
 * @param {string} question
 * @param {(step: {agent: string, detail: string}) => void} onStep - called for each pipeline step
 * @returns {Promise<object>} - the final result
 */
export async function queryAgentStream(question, onStep) {
  const response = await fetch(`${API_BASE}/query/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let result = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop(); // keep incomplete line in buffer

    let eventType = null;
    for (const line of lines) {
      if (line.startsWith('event: ')) {
        eventType = line.slice(7).trim();
      } else if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        if (eventType === 'step') {
          onStep(data);
        } else if (eventType === 'result') {
          result = data;
        } else if (eventType === 'error') {
          throw new Error(data.detail || 'Pipeline error');
        }
        eventType = null;
      }
    }
  }

  if (!result) throw new Error('No result received from pipeline');
  return result;
}

export async function getSchema() {
  const response = await fetch(`${API_BASE}/schema`);
  if (!response.ok) throw new Error('Failed to fetch schema');
  return response.json();
}
