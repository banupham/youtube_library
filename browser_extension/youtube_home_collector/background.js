const CENTRAL_BASE = 'http://127.0.0.1:8770';
const COLLECTOR_VERSION = '0.6.3';

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

async function ensureParticipationDefault() {
  const stored = await chrome.storage.local.get(['passiveAutoEnabled', 'participationInitializedAt']);
  const updates = {};
  if (typeof stored.passiveAutoEnabled === 'undefined') updates.passiveAutoEnabled = true;
  if (!stored.participationInitializedAt) updates.participationInitializedAt = new Date().toISOString();
  if (Object.keys(updates).length) await chrome.storage.local.set(updates);
  return typeof stored.passiveAutoEnabled === 'undefined' ? true : stored.passiveAutoEnabled !== false;
}

async function passiveEnabled() {
  const stored = await chrome.storage.local.get(['passiveAutoEnabled']);
  return stored.passiveAutoEnabled !== false;
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

async function postCentral(endpoint, payload) {
  const response = await fetch(`${CENTRAL_BASE}${endpoint}`, {
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
}

chrome.runtime.onInstalled.addListener(() => {
  ensureParticipationDefault().catch((error) => console.warn('Cannot initialize passive participation', error));
});

chrome.runtime.onStartup.addListener(() => {
  ensureParticipationDefault().catch((error) => console.warn('Cannot restore passive participation default', error));
});

ensureParticipationDefault().catch((error) => console.warn('Cannot initialize passive participation', error));

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== 'youtube_library_passive_snapshot') return false;

  (async () => {
    if (!(await passiveEnabled())) {
      sendResponse({ ok: false, skipped: 'passive_collection_paused' });
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
      collector_version: COLLECTOR_VERSION,
      auto_start_policy: 'enabled_by_default_on_extension_install',
      central_server: CENTRAL_BASE,
      tab_url: sender?.tab?.url || payload.page_url || null
    };

    try {
      const collectResult = await postCentral('/collect', payload);
      const finalResult = await postCentral('/finalize', {
        collector_profile: profile,
        collection_session_id: sessionId
      });
      await chrome.storage.local.set({
        lastPassiveCollectionAt: new Date().toISOString(),
        lastDailyCollectionAt: new Date().toISOString()
      });
      sendResponse({ ok: true, collect: collectResult, finalize: finalResult });
    } catch (error) {
      console.warn('Passive collector central sync failed', error);
      sendResponse({ ok: false, error: String(error?.message || error) });
    }
  })();

  return true;
});
