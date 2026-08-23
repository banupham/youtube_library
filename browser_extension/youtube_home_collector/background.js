const DEFAULT_CENTRAL_BASE = 'http://127.0.0.1:8770';
const COLLECTOR_VERSION = '0.7.0';
const SCORE_MODEL = 'natural_interaction_v1';
const EVENT_SCORES = {
  video_open: 0.25,
  like: 1.0,
  unlike: -1.0,
  dislike: -1.0,
  undislike: 0.0,
  comment_submit: 1.0
};

function randomId(prefix) {
  if (globalThis.crypto?.randomUUID) return `${prefix}-${crypto.randomUUID()}`;
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}
function shortProfileId(profileId) { return String(profileId || '').replace(/^browser-/, '').slice(0, 8) || 'unknown'; }
function localDayKey(date = new Date()) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}
function normalizeChannel(value) {
  return String(value || '').toLowerCase().replace(/\s+/g, ' ').trim();
}

async function ensureDefaults() {
  const stored = await chrome.storage.local.get([
    'passiveAutoEnabled', 'participationInitializedAt', 'collectorParticipantId',
    'collectorDeviceId', 'communityServerUrl'
  ]);
  const updates = {};
  if (typeof stored.passiveAutoEnabled === 'undefined') updates.passiveAutoEnabled = true;
  if (!stored.participationInitializedAt) updates.participationInitializedAt = new Date().toISOString();
  if (!stored.collectorParticipantId) updates.collectorParticipantId = randomId('participant');
  if (!stored.collectorDeviceId) updates.collectorDeviceId = randomId('browser-device');
  if (!stored.communityServerUrl) updates.communityServerUrl = DEFAULT_CENTRAL_BASE;
  if (Object.keys(updates).length) await chrome.storage.local.set(updates);
}

async function passiveEnabled() {
  const stored = await chrome.storage.local.get(['passiveAutoEnabled']);
  return stored.passiveAutoEnabled !== false;
}

async function ensureCollectorIdentity() {
  await ensureDefaults();
  const stored = await chrome.storage.local.get([
    'collectorProfileId', 'collectorProfileLabel', 'collectorParticipantId', 'collectorDeviceId'
  ]);
  let profileId = stored.collectorProfileId;
  if (!profileId) {
    profileId = randomId('browser');
    await chrome.storage.local.set({ collectorProfileId: profileId });
  }
  const label = String(stored.collectorProfileLabel || '').trim();
  return {
    profile_id: profileId,
    profile_label: label || `Profile ${shortProfileId(profileId)}`,
    participant_id: stored.collectorParticipantId,
    device_id: stored.collectorDeviceId,
    identity_source: 'browser_extension_local_storage'
  };
}

async function serverConfig() {
  await ensureDefaults();
  const stored = await chrome.storage.local.get(['communityServerUrl', 'communityServerToken']);
  return {
    base: String(stored.communityServerUrl || DEFAULT_CENTRAL_BASE).trim().replace(/\/+$/, ''),
    token: String(stored.communityServerToken || '')
  };
}

async function postCentral(endpoint, payload) {
  const config = await serverConfig();
  const headers = { 'Content-Type': 'application/json' };
  if (config.token) headers.Authorization = `Bearer ${config.token}`;
  const response = await fetch(`${config.base}${endpoint}`, {
    method: 'POST', headers, body: JSON.stringify(payload)
  });
  if (!response.ok) {
    let detail = '';
    try { detail = await response.text(); } catch { detail = ''; }
    throw new Error(`Central HTTP ${response.status}${detail ? `: ${detail.slice(0, 180)}` : ''}`);
  }
  return response.json();
}

async function annotateSubscriptionState(payload) {
  if (Array.isArray(payload.subscription_channels) && payload.subscription_channels.length) {
    const names = payload.subscription_channels.map((x) => normalizeChannel(x?.name)).filter(Boolean);
    await chrome.storage.local.set({ subscribedChannelNames: names, subscribedChannelCacheAt: new Date().toISOString() });
  }
  if (!Array.isArray(payload.items) || !payload.items.length) return;
  const stored = await chrome.storage.local.get(['subscribedChannelNames']);
  const known = new Set(Array.isArray(stored.subscribedChannelNames) ? stored.subscribedChannelNames : []);
  payload.items = payload.items.map((item) => {
    const channel = normalizeChannel(item?.channel);
    return {
      ...item,
      subscription_state: channel && known.has(channel) ? 'subscribed' : (item?.subscription_state || 'unknown')
    };
  });
}

async function recordLocalInteraction(event) {
  const day = localDayKey();
  const key = `interactionDaily_${day}`;
  const stored = await chrome.storage.local.get([key]);
  const daily = stored[key] || { date: day, score_model: SCORE_MODEL, score_total: 0, event_count: 0, event_counts: {} };
  daily.event_count = Number(daily.event_count || 0) + 1;
  daily.score_total = Number((Number(daily.score_total || 0) + Number(event.engagement_score || 0)).toFixed(4));
  daily.event_counts[event.event_type] = Number(daily.event_counts[event.event_type] || 0) + 1;
  await chrome.storage.local.set({ [key]: daily });
}

async function queueInteraction(payload) {
  const stored = await chrome.storage.local.get(['interactionPendingQueue']);
  const queue = Array.isArray(stored.interactionPendingQueue) ? stored.interactionPendingQueue : [];
  queue.push(payload);
  while (queue.length > 500) queue.shift();
  await chrome.storage.local.set({ interactionPendingQueue: queue });
}

async function flushInteractionQueue() {
  const stored = await chrome.storage.local.get(['interactionPendingQueue']);
  const queue = Array.isArray(stored.interactionPendingQueue) ? stored.interactionPendingQueue : [];
  if (!queue.length) return;
  let delivered = 0;
  for (const row of queue) {
    try {
      await postCentral('/v1/interaction', row);
      delivered += 1;
    } catch {
      break;
    }
  }
  if (delivered) await chrome.storage.local.set({ interactionPendingQueue: queue.slice(delivered) });
}

async function submitInteraction(raw, sender) {
  if (!(await passiveEnabled())) return { ok: false, skipped: 'collection_paused' };
  const identity = await ensureCollectorIdentity();
  const eventType = String(raw?.event_type || '');
  if (!(eventType in EVENT_SCORES)) return { ok: false, error: 'unsupported_event_type' };
  const event = {
    schema_version: '1.0.0',
    event_id: randomId('evt'),
    participant_id: identity.participant_id,
    device_id: identity.device_id,
    profile_id: identity.profile_id,
    profile_slot: 'browser-default',
    platform: 'browser',
    captured_at: raw?.captured_at || new Date().toISOString(),
    event_type: eventType,
    engagement_score: EVENT_SCORES[eventType],
    score_model: SCORE_MODEL,
    source: 'natural_user_action',
    video_id: raw?.video_id || null,
    video_title: raw?.video_title || null,
    channel: raw?.channel || null,
    channel_subscription_state: raw?.channel_subscription_state || 'unknown',
    surface: raw?.surface || null,
    confidence: Number(raw?.confidence ?? 1),
    context: {
      page_url: sender?.tab?.url || raw?.page_url || null,
      detection: raw?.detection || 'browser_dom_event'
    }
  };
  await recordLocalInteraction(event);
  try {
    const result = await postCentral('/v1/interaction', event);
    flushInteractionQueue().catch(() => {});
    return result;
  } catch (error) {
    await queueInteraction(event);
    return { ok: false, queued: true, error: String(error?.message || error) };
  }
}

async function submitSnapshot(payload, sender) {
  if (!(await passiveEnabled())) return { ok: false, skipped: 'passive_collection_paused' };
  if (!payload || !Array.isArray(payload.items)) return { ok: false, error: 'invalid_payload' };
  const identity = await ensureCollectorIdentity();
  await annotateSubscriptionState(payload);
  const day = localDayKey();
  const sessionId = `passive-${day}-${shortProfileId(identity.profile_id)}`;
  payload.collector_profile = {
    profile_id: identity.profile_id,
    profile_label: identity.profile_label,
    identity_source: identity.identity_source
  };
  payload.collection_session_id = sessionId;
  const config = await serverConfig();
  payload.capture_context = {
    mode: 'passive_natural_navigation',
    collector_version: COLLECTOR_VERSION,
    auto_start_policy: 'enabled_by_default_on_extension_install',
    central_server: config.base,
    tab_url: sender?.tab?.url || payload.page_url || null
  };
  const collectResult = await postCentral('/collect', payload);
  const finalResult = await postCentral('/finalize', {
    collector_profile: payload.collector_profile,
    collection_session_id: sessionId
  });
  await chrome.storage.local.set({ lastPassiveCollectionAt: new Date().toISOString(), lastDailyCollectionAt: new Date().toISOString() });
  return { ok: true, collect: collectResult, finalize: finalResult };
}

chrome.runtime.onInstalled.addListener(() => {
  ensureDefaults().then(() => flushInteractionQueue()).catch(console.warn);
});
chrome.runtime.onStartup.addListener(() => {
  ensureDefaults().then(() => flushInteractionQueue()).catch(console.warn);
});
ensureDefaults().then(() => flushInteractionQueue()).catch(console.warn);

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === 'youtube_library_passive_snapshot') {
    submitSnapshot(message.payload, sender)
      .then(sendResponse)
      .catch((error) => sendResponse({ ok: false, error: String(error?.message || error) }));
    return true;
  }
  if (message?.type === 'youtube_library_interaction') {
    submitInteraction(message.payload, sender)
      .then(sendResponse)
      .catch((error) => sendResponse({ ok: false, error: String(error?.message || error) }));
    return true;
  }
  return false;
});
