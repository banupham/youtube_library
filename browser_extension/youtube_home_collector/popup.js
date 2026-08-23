const statusEl = document.getElementById('status');
const collectBtn = document.getElementById('collect');
const profileLabelEl = document.getElementById('profileLabel');
const profileIdEl = document.getElementById('profileId');

function setStatus(text) {
  statusEl.textContent = text;
}

function filenameTimestamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}_${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}${pad(d.getUTCSeconds())}`;
}

function createProfileId() {
  if (globalThis.crypto?.randomUUID) return `browser-${crypto.randomUUID()}`;
  return `browser-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

function shortProfileId(profileId) {
  return String(profileId || '').replace(/^browser-/, '').slice(0, 8) || 'unknown';
}

function safeFolderName(value) {
  const normalized = String(value || '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9._-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40);
  return normalized || 'profile';
}

async function loadCollectorProfile() {
  const stored = await chrome.storage.local.get(['collectorProfileId', 'collectorProfileLabel']);
  let profileId = stored.collectorProfileId;
  if (!profileId) {
    profileId = createProfileId();
    await chrome.storage.local.set({ collectorProfileId: profileId });
  }

  const profileLabel = String(stored.collectorProfileLabel || '').trim();
  profileIdEl.textContent = profileId;
  if (document.activeElement !== profileLabelEl) profileLabelEl.value = profileLabel;

  return {
    profile_id: profileId,
    profile_label: profileLabel || `Profile ${shortProfileId(profileId)}`,
    identity_source: 'browser_extension_local_storage'
  };
}

async function saveProfileLabel() {
  const value = String(profileLabelEl.value || '').trim().slice(0, 60);
  await chrome.storage.local.set({ collectorProfileLabel: value });
  return value;
}

profileLabelEl.addEventListener('change', async () => {
  await saveProfileLabel();
  const profile = await loadCollectorProfile();
  setStatus(`Profile: ${profile.profile_label} (${shortProfileId(profile.profile_id)})\nBridge cần chạy tại 127.0.0.1:8765.`);
});

async function collectHomepage(scrolls, delayMs) {
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  const CARD_SELECTORS = [
    'ytd-rich-item-renderer',
    'ytd-video-renderer',
    'ytd-grid-video-renderer',
    'yt-lockup-view-model'
  ];

  const TITLE_SELECTORS = [
    'a#video-title-link[href*="/watch?v="]',
    'a#video-title[href*="/watch?v="]',
    'h3 a[href*="/watch?v="]',
    '.yt-lockup-metadata-view-model-wiz__title a[href*="/watch?v="]',
    'a.yt-lockup-metadata-view-model-wiz__title[href*="/watch?v="]'
  ];

  const CHANNEL_SELECTORS = [
    'ytd-channel-name a',
    '#channel-name a',
    '#text.ytd-channel-name',
    'a[href^="/@"]',
    '.yt-lockup-metadata-view-model-wiz__metadata a[href^="/@"]'
  ];

  const METADATA_SELECTORS = [
    '#metadata-line',
    '#metadata',
    '.yt-content-metadata-view-model-wiz__metadata-text',
    '.yt-lockup-metadata-view-model-wiz__metadata'
  ];

  const DURATION_SELECTORS = [
    'ytd-thumbnail-overlay-time-status-renderer span',
    '#time-status span',
    '.badge-shape-wiz__text'
  ];

  const isVisible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
  };

  const firstText = (root, selectors) => {
    for (const selector of selectors) {
      const el = root?.querySelector?.(selector);
      const value = el?.textContent?.trim();
      if (value) return value;
    }
    return '';
  };

  const validTitle = (value) => {
    const title = (value || '').trim();
    if (!title) return '';
    if (/^(xem|trực tiếp|live|watch)$/i.test(title)) return '';
    if (/^\d{1,2}:\d{2}(?::\d{2})?$/.test(title)) return '';
    return title;
  };

  const extract = () => {
    const items = [];
    const cards = Array.from(document.querySelectorAll(CARD_SELECTORS.join(',')));

    for (const card of cards) {
      if (!isVisible(card)) continue;

      let titleAnchor = null;
      for (const selector of TITLE_SELECTORS) {
        const candidate = card.querySelector(selector);
        if (candidate && isVisible(candidate)) {
          titleAnchor = candidate;
          break;
        }
      }
      if (!titleAnchor) continue;

      let url;
      try {
        url = new URL(titleAnchor.href, location.origin);
      } catch {
        continue;
      }

      const videoId = url.searchParams.get('v');
      if (!videoId) continue;

      let title = validTitle(titleAnchor.getAttribute('title'));
      if (!title) title = validTitle(titleAnchor.textContent);

      if (!title) {
        const heading = card.querySelector('h3, #video-title, yt-formatted-string#video-title');
        title = validTitle(heading?.textContent);
      }

      if (!title) {
        for (const anchor of card.querySelectorAll('a[href*="/watch?v="]')) {
          const candidate = validTitle(anchor.getAttribute('title')) || validTitle(anchor.textContent);
          if (candidate && candidate.length > 5) {
            title = candidate;
            break;
          }
        }
      }

      if (!title) continue;

      items.push({
        video_id: videoId,
        title,
        channel: firstText(card, CHANNEL_SELECTORS),
        url: `https://www.youtube.com/watch?v=${videoId}`,
        metadata_text: firstText(card, METADATA_SELECTORS),
        duration_text: firstText(card, DURATION_SELECTORS)
      });
    }

    return items;
  };

  const collected = new Map();
  const merge = () => {
    for (const item of extract()) {
      if (!collected.has(item.video_id)) collected.set(item.video_id, item);
    }
  };

  merge();
  for (let i = 0; i < scrolls; i += 1) {
    window.scrollBy(0, Math.floor(window.innerHeight * 0.90));
    await sleep(delayMs);
    merge();
  }

  const items = Array.from(collected.values()).map((item, index) => ({
    position: index + 1,
    ...item
  }));

  return {
    source: 'youtube_home',
    captured_at: new Date().toISOString(),
    page_url: location.href,
    item_count: items.length,
    items
  };
}

async function fallbackDownload(payload) {
  const json = JSON.stringify(payload, null, 2);
  const dataUrl = `data:application/json;charset=utf-8,${encodeURIComponent(json)}`;
  const profile = payload.collector_profile || {};
  const folder = `${safeFolderName(profile.profile_label)}__${shortProfileId(profile.profile_id)}`;
  const filename = `youtube_library/${folder}/home_${filenameTimestamp()}.json`;
  await chrome.downloads.download({ url: dataUrl, filename, saveAs: false });
  return filename;
}

collectBtn.addEventListener('click', async () => {
  collectBtn.disabled = true;
  setStatus('Đang đọc YouTube Home...');

  try {
    await saveProfileLabel();
    const collectorProfile = await loadCollectorProfile();

    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id || !tab.url?.startsWith('https://www.youtube.com/')) {
      throw new Error('Hãy mở YouTube Home trong tab hiện tại trước.');
    }

    const scrolls = Math.max(0, Math.min(50, Number(document.getElementById('scrolls').value || 8)));
    const delay = Math.max(200, Math.min(10000, Number(document.getElementById('delay').value || 1500)));

    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: collectHomepage,
      args: [scrolls, delay]
    });

    const payload = results?.[0]?.result;
    if (!payload || !Array.isArray(payload.items)) {
      throw new Error('Không lấy được dữ liệu Home.');
    }
    payload.collector_profile = collectorProfile;

    setStatus(
      `Profile: ${collectorProfile.profile_label} (${shortProfileId(collectorProfile.profile_id)})\n` +
      `Đã lấy ${payload.item_count} video. Đang gửi về local bridge...`
    );

    try {
      const response = await fetch('http://127.0.0.1:8765/collect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) throw new Error(`Bridge HTTP ${response.status}`);
      const result = await response.json();
      setStatus(
        `Xong · ${result.profile_label || collectorProfile.profile_label} (${result.profile_short_id || shortProfileId(collectorProfile.profile_id)})\n` +
        `${payload.item_count} video\n` +
        `Snapshot: ${result.snapshot_path}\n` +
        `Classified: ${result.classified_path || 'disabled'}\n` +
        `Report: ${result.profile_html_path || 'disabled'}`
      );
    } catch (bridgeError) {
      const file = await fallbackDownload(payload);
      setStatus(
        `Profile: ${collectorProfile.profile_label} (${shortProfileId(collectorProfile.profile_id)})\n` +
        `Đã lấy ${payload.item_count} video nhưng local bridge chưa chạy.\n` +
        `Đã tải fallback: Downloads/${file}\n` +
        `Lỗi bridge: ${bridgeError.message}`
      );
    }
  } catch (error) {
    setStatus(`Lỗi: ${error.message}`);
  } finally {
    collectBtn.disabled = false;
  }
});

loadCollectorProfile().then((profile) => {
  setStatus(`Profile: ${profile.profile_label} (${shortProfileId(profile.profile_id)})\nBridge cần chạy tại 127.0.0.1:8765.`);
}).catch((error) => {
  setStatus(`Không khởi tạo được profile ID: ${error.message}`);
});
