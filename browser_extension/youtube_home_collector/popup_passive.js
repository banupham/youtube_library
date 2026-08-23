const passiveStateEl = document.getElementById('passiveState');
const passiveToggleEl = document.getElementById('passivePauseToggle');
const passiveLastEl = document.getElementById('passiveLastCapture');

function formatPassiveStatus(enabled, lastCapture) {
  passiveStateEl.textContent = enabled
    ? 'Đang hoạt động tự động khi bạn truy cập YouTube.'
    : 'Đang tạm dừng. Không thu thập passive snapshot.';
  passiveToggleEl.textContent = enabled ? 'Tạm dừng thu thập' : 'Tiếp tục thu thập';
  passiveToggleEl.dataset.enabled = enabled ? 'true' : 'false';
  passiveLastEl.textContent = lastCapture
    ? `Lần passive capture gần nhất: ${lastCapture}`
    : 'Chưa có passive capture nào trên profile này.';
}

async function loadPassiveSetting() {
  const stored = await chrome.storage.local.get([
    'passiveAutoEnabled',
    'lastPassiveCollectionAt'
  ]);
  const enabled = stored.passiveAutoEnabled !== false;
  formatPassiveStatus(enabled, stored.lastPassiveCollectionAt || null);
}

passiveToggleEl.addEventListener('click', async () => {
  const currentlyEnabled = passiveToggleEl.dataset.enabled !== 'false';
  const nextEnabled = !currentlyEnabled;
  await chrome.storage.local.set({ passiveAutoEnabled: nextEnabled });
  const stored = await chrome.storage.local.get(['lastPassiveCollectionAt']);
  formatPassiveStatus(nextEnabled, stored.lastPassiveCollectionAt || null);
});

loadPassiveSetting().catch((error) => console.warn('Cannot load passive collector setting', error));
