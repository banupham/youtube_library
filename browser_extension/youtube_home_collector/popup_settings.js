const serverUrlEl = document.getElementById('communityServerUrl');
const serverTokenEl = document.getElementById('communityServerToken');
const participantIdEl = document.getElementById('collectorParticipantId');
const saveServerEl = document.getElementById('saveServerSettings');
const serverStatusEl = document.getElementById('serverStatus');

function normalizeServerUrl(value) {
  return String(value || '').trim().replace(/\/+$/, '');
}

async function ensureParticipantId() {
  const stored = await chrome.storage.local.get(['collectorParticipantId']);
  if (stored.collectorParticipantId) return stored.collectorParticipantId;
  const value = globalThis.crypto?.randomUUID
    ? `participant-${crypto.randomUUID()}`
    : `participant-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  await chrome.storage.local.set({ collectorParticipantId: value });
  return value;
}

async function loadServerSettings() {
  const participantId = await ensureParticipantId();
  const stored = await chrome.storage.local.get(['communityServerUrl', 'communityServerToken']);
  serverUrlEl.value = stored.communityServerUrl || 'http://127.0.0.1:8770';
  serverTokenEl.value = stored.communityServerToken || '';
  participantIdEl.value = participantId;
  serverStatusEl.textContent = `Đang dùng: ${serverUrlEl.value}`;
}

async function requestOriginPermission(url) {
  const parsed = new URL(url);
  if (parsed.hostname === '127.0.0.1' || parsed.hostname === 'localhost') return true;
  const originPattern = `${parsed.protocol}//${parsed.host}/*`;
  return chrome.permissions.request({ origins: [originPattern] });
}

saveServerEl.addEventListener('click', async () => {
  try {
    const url = normalizeServerUrl(serverUrlEl.value);
    if (!/^https?:\/\//i.test(url)) throw new Error('Server URL phải bắt đầu bằng http:// hoặc https://');
    const allowed = await requestOriginPermission(url);
    if (!allowed) throw new Error('Chưa cấp quyền kết nối tới server này.');
    const participantId = String(participantIdEl.value || '').trim();
    if (participantId.length < 4) throw new Error('Participant ID quá ngắn.');
    await chrome.storage.local.set({
      communityServerUrl: url,
      communityServerToken: String(serverTokenEl.value || ''),
      collectorParticipantId: participantId
    });
    serverStatusEl.textContent = `Đã lưu · ${url}`;
  } catch (error) {
    serverStatusEl.textContent = `Lỗi: ${error.message || error}`;
  }
});

loadServerSettings().catch((error) => {
  serverStatusEl.textContent = `Không đọc được cấu hình: ${error.message || error}`;
});
