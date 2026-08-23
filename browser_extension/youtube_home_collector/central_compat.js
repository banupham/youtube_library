const CENTRAL_UI_BASE = 'http://127.0.0.1:8770';

if (typeof postBridge === 'function') {
  postBridge = async function postCentralCompat(endpoint, payload) {
    const response = await fetch(`${CENTRAL_UI_BASE}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      let detail = '';
      try { detail = await response.text(); } catch { detail = ''; }
      throw new Error(`Central HTTP ${response.status}${detail ? `: ${detail.slice(0, 180)}` : ''}`);
    }
    return response.json();
  };
}

if (typeof setStatus === 'function') {
  const originalSetStatus = setStatus;
  setStatus = function setCentralStatus(text) {
    const normalized = String(text || '')
      .replaceAll('Bridge cần chạy tại 127.0.0.1:8765.', 'Central server: 127.0.0.1:8770.')
      .replaceAll('Bridge: 127.0.0.1:8765', 'Central server: 127.0.0.1:8770');
    originalSetStatus(normalized);
  };
}

const initialStatus = document.getElementById('status');
if (initialStatus && initialStatus.textContent.includes('8765')) {
  initialStatus.textContent = 'Central server cần chạy tại 127.0.0.1:8770.';
}
