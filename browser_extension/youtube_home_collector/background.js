const BRIDGE_BASE = 'http://127.0.0.1:8765';

function createProfileId() {
  if (globalThis.crypto?.randomUUID) return `browser-${crypto.randomUUID()}`;
  return `browser-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

function shortProfileId(profileId) {
  return String(profileId || '').replace(/^browser-/, '').slice(0, 8) || 'unknown';
}

function localDayKey(date = new Date()) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

async function ensureCollectorProfile() {
  const stored = await chrome.storage.local.get(['collectorProfileId', 'collectorProfileLabel']);
  let profileId = stored.collectorProfileId;
  if (!profileId) {
    profileId = createProfileId();
    await chrome.storage.local.set({ collectorProfileId: profileId });
  }
  const label = String(stored.collectorProfileLabel || '').trim();
  return {
    profile_id: profileId,
    profile_label: label || `Profile ${shortProfileId(profileId)}`,
    identity_source: 'browser_extension_local_storage'
  };
}

async function postBridge(endpoint, payload) {
  const response = await fetch(`${BRIDGE_BASE}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    let detail = '';
    try { detail = await response.text(); } catch { detail = ''; }
    throw new Error(`Bridge HTTP ${response.status}${detail ? `: ${detail.slice(0, 180)}` : ''}`);
  }
  return response.json();
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== 'youtube_library_passive_snapshot') return false;

  (async () => {
    const stored = await chrome.storage.local.get(['passiveAutoEnabled']);
    if (!stored.passiveAutoEnabled) {
      sendResponse({ ok: false, skipped: 'passive_auto_disabled' });
      return;
    }

    const payload = message.payload;
    if (!payload || !Array.isArray(payload.items)) {
      sendResponse({ ok: false, error: 'invalid_payload' });
      return;
    }

    const profile = await ensureCollectorProfile();
    const day = localDayKey();
    const sessionId = `passive-${day}-${shortProfileId(profile.profile_id)}`;
    payload.collector_profile = profile;
    payload.collection_session_id = sessionId;
    payload.capture_context = {
      mode: 'passive_natural_navigation',
      collector_version: '0.6.0',
      tab_url: sender?.tab?.url || payload.page_url || null
    };

    try {
      const collectResult = await postBridge('/collect', payload);
      const finalResult = await postBridge('/finalize', {
        collector_profile: profile,
        collection_session_id: sessionId
      });
      await chrome.storage.local.set({
        lastPassiveCollectionAt: new Date().toISOString(),
        lastDailyCollectionAt: new Date().toISOString()
      });
      sendResponse({ ok: true, collect: collectResult, finalize: finalResult });
    } catch (error) {
      console.warn('Passive collector bridge sync failed', error);
      sendResponse({ ok: false, error: String(error?.message || error) });
    }
  })();

  return true;
});
