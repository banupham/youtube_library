const passiveAutoEl = document.getElementById('passiveAutoEnabled');

async function loadPassiveSetting() {
  const stored = await chrome.storage.local.get([
    'passiveAutoEnabled',
    'lastPassiveCollectionAt',
    'passiveDailyQuota'
  ]);
  passiveAutoEl.checked = Boolean(stored.passiveAutoEnabled);
  passiveAutoEl.title = stored.lastPassiveCollectionAt
    ? `Last passive capture: ${stored.lastPassiveCollectionAt}`
    : 'Passive capture has not run yet.';
}

passiveAutoEl.addEventListener('change', async () => {
  await chrome.storage.local.set({ passiveAutoEnabled: Boolean(passiveAutoEl.checked) });
  if (!passiveAutoEl.checked) {
    await chrome.storage.local.remove(['passiveDailyQuota']);
  }
});

loadPassiveSetting().catch((error) => console.warn('Cannot load passive collector setting', error));
