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

// Runs inside the active youtube.com tab. It fetches watch-page HTML only;
// it does not navigate, click, instantiate a player, or request media streams.
async function collectUpNextFromWatchHtml(parentVideoId, limit) {
  function textValue(value) {
    if (!value) return '';
    if (typeof value === 'string') return value.trim();
    if (typeof value.simpleText === 'string') return value.simpleText.trim();
    if (Array.isArray(value.runs)) {
      return value.runs.map((run) => run?.text || '').join('').trim();
    }
    if (typeof value.content === 'string') return value.content.trim();
    return '';
  }

  function parseBalancedJson(source, startIndex) {
    const start = source.indexOf('{', startIndex);
    if (start < 0) return null;
    let depth = 0;
    let inString = false;
    let escaped = false;
    for (let i = start; i < source.length; i += 1) {
      const ch = source[i];
      if (inString) {
        if (escaped) {
          escaped = false;
        } else if (ch === '\\') {
          escaped = true;
        } else if (ch === '"') {
          inString = false;
        }
        continue;
      }
      if (ch === '"') {
        inString = true;
      } else if (ch === '{') {
        depth += 1;
      } else if (ch === '}') {
        depth -= 1;
        if (depth === 0) {
          try {
            return JSON.parse(source.slice(start, i + 1));
          } catch {
            return null;
          }
        }
      }
    }
    return null;
  }

  function parseInitialData(htmlText) {
    const markers = [
      'var ytInitialData =',
      'window["ytInitialData"] =',
      "window['ytInitialData'] =",
      'ytInitialData ='
    ];
    for (const marker of markers) {
      const index = htmlText.indexOf(marker);
      if (index >= 0) {
        const parsed = parseBalancedJson(htmlText, index + marker.length);
        if (parsed) return parsed;
      }
    }
    return null;
  }

  function findSecondaryResults(node, depth = 0) {
    if (!node || typeof node !== 'object' || depth > 18) return null;
    if (node.secondaryResults && typeof node.secondaryResults === 'object') {
      return node.secondaryResults;
    }
    if (Array.isArray(node)) {
      for (const child of node) {
        const found = findSecondaryResults(child, depth + 1);
        if (found) return found;
      }
      return null;
    }
    for (const value of Object.values(node)) {
      const found = findSecondaryResults(value, depth + 1);
      if (found) return found;
    }
    return null;
  }

  function rendererToItem(renderer) {
    if (!renderer || typeof renderer !== 'object') return null;
    const videoId = renderer.videoId || renderer.contentId || renderer.video_id || '';
    if (!videoId || videoId === parentVideoId) return null;

    const title = textValue(renderer.title)
      || textValue(renderer.headline)
      || textValue(renderer.metadata?.lockupMetadataViewModel?.title)
      || textValue(renderer.lockupMetadataViewModel?.title);
    if (!title) return null;

    const channel = textValue(renderer.shortBylineText)
      || textValue(renderer.longBylineText)
      || textValue(renderer.ownerText)
      || textValue(renderer.metadata?.lockupMetadataViewModel?.metadata?.contentMetadataViewModel?.metadataRows?.[0]?.metadataParts?.[0]?.text);

    const metadataParts = [
      textValue(renderer.viewCountText),
      textValue(renderer.shortViewCountText),
      textValue(renderer.publishedTimeText)
    ].filter(Boolean);

    return {
      video_id: videoId,
      title,
      channel,
      url: `https://www.youtube.com/watch?v=${videoId}`,
      metadata_text: metadataParts.join(' · '),
      duration_text: textValue(renderer.lengthText)
    };
  }

  function collectRenderers(node, output, depth = 0) {
    if (!node || typeof node !== 'object' || depth > 24 || output.length >= limit * 4) return;

    const rendererKeys = ['compactVideoRenderer', 'videoRenderer', 'gridVideoRenderer', 'lockupViewModel'];
    for (const key of rendererKeys) {
      if (node[key]) {
        const item = rendererToItem(node[key]);
        if (item) output.push(item);
      }
    }

    if (node.videoId && node.title) {
      const item = rendererToItem(node);
      if (item) output.push(item);
    }

    if (Array.isArray(node)) {
      for (const child of node) collectRenderers(child, output, depth + 1);
      return;
    }
    for (const value of Object.values(node)) collectRenderers(value, output, depth + 1);
  }

  const watchUrl = `/watch?v=${encodeURIComponent(parentVideoId)}&autoplay=0`;
  const response = await fetch(watchUrl, {
    method: 'GET',
    credentials: 'include',
    cache: 'no-store',
    redirect: 'follow'
  });
  if (!response.ok) throw new Error(`Watch HTML HTTP ${response.status}`);

  const htmlText = await response.text();
  const initialData = parseInitialData(htmlText);
  if (!initialData) throw new Error('Không tìm thấy ytInitialData trong watch HTML.');

  const secondary = findSecondaryResults(initialData);
  if (!secondary) throw new Error('Không tìm thấy secondaryResults/Up Next.');

  const raw = [];
  collectRenderers(secondary, raw);

  const seen = new Set();
  const items = [];
  for (const item of raw) {
    if (!item.video_id || seen.has(item.video_id)) continue;
    seen.add(item.video_id);
    items.push({ position: items.length + 1, ...item });
    if (items.length >= limit) break;
  }

  return {
    source: 'youtube_up_next',
    captured_at: new Date().toISOString(),
    extraction_mode: 'same_origin_watch_html_no_player',
    parent_video_id: parentVideoId,
    page_url: `https://www.youtube.com/watch?v=${parentVideoId}`,
    item_count: items.length,
    items
  };
}

function cryptoRandomInt(maxExclusive) {
  if (maxExclusive <= 1) return 0;
  const maxUint = 0x100000000;
  const limit = maxUint - (maxUint % maxExclusive);
  const bucket = new Uint32Array(1);
  do {
    crypto.getRandomValues(bucket);
  } while (bucket[0] >= limit);
  return bucket[0] % maxExclusive;
}

function sampleWithoutReplacement(items, count) {
  const copy = items.slice();
  const wanted = Math.max(0, Math.min(count, copy.length));
  for (let i = 0; i < wanted; i += 1) {
    const j = i + cryptoRandomInt(copy.length - i);
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy.slice(0, wanted);
}

async function postToBridge(payload) {
  const response = await fetch('http://127.0.0.1:8765/collect', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    let detail = '';
    try {
      detail = await response.text();
    } catch {
      detail = '';
    }
    throw new Error(`Bridge HTTP ${response.status}${detail ? `: ${detail.slice(0, 180)}` : ''}`);
  }
  return response.json();
}

async function fallbackDownload(payload) {
  const json = JSON.stringify(payload, null, 2);
  const dataUrl = `data:application/json;charset=utf-8,${encodeURIComponent(json)}`;
  const profile = payload.collector_profile || {};
  const folder = `${safeFolderName(profile.profile_label)}__${shortProfileId(profile.profile_id)}`;
  const prefix = payload.source === 'youtube_up_next'
    ? `upnext_${String(payload.parent_video_id || 'unknown').replace(/[^a-zA-Z0-9_-]/g, '')}_`
    : 'home_';
  const filename = `youtube_library/${folder}/${prefix}${filenameTimestamp()}.json`;
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
      throw new Error('Hãy mở YouTube trong tab hiện tại trước.');
    }

    const scrolls = Math.max(0, Math.min(50, Number(document.getElementById('scrolls').value || 8)));
    const delay = Math.max(200, Math.min(10000, Number(document.getElementById('delay').value || 1500)));
    const upNextSamples = Math.max(0, Math.min(10, Number(document.getElementById('upNextSamples').value || 3)));
    const upNextLimit = Math.max(5, Math.min(40, Number(document.getElementById('upNextLimit').value || 20)));

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
      `Home: ${payload.item_count} video. Đang gửi về local bridge...`
    );

    let homeResult;
    try {
      homeResult = await postToBridge(payload);
    } catch (bridgeError) {
      const file = await fallbackDownload(payload);
      throw new Error(`Bridge chưa chạy; Home đã fallback Downloads/${file}. ${bridgeError.message}`);
    }

    const sampled = sampleWithoutReplacement(
      payload.items.filter((item) => item?.video_id),
      upNextSamples
    );

    const upNextResults = [];
    const upNextFailures = [];
    let totalUpNext = 0;

    for (let index = 0; index < sampled.length; index += 1) {
      const parent = sampled[index];
      setStatus(
        `Profile: ${collectorProfile.profile_label} (${shortProfileId(collectorProfile.profile_id)})\n` +
        `Home xong: ${payload.item_count} video\n` +
        `Up Next ${index + 1}/${sampled.length}: đang đọc HTML cho #${parent.position} ${parent.title}`
      );

      try {
        const scriptResult = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: collectUpNextFromWatchHtml,
          args: [parent.video_id, upNextLimit]
        });
        const upPayload = scriptResult?.[0]?.result;
        if (!upPayload || !Array.isArray(upPayload.items)) {
          throw new Error('Watch HTML không trả về danh sách Up Next.');
        }

        upPayload.collector_profile = collectorProfile;
        upPayload.parent_title = parent.title || '';
        upPayload.parent_channel = parent.channel || '';
        upPayload.parent_home_position = parent.position || null;
        upPayload.source_home_captured_at = payload.captured_at;
        upPayload.sample_context = {
          method: 'crypto_random_without_replacement',
          sample_index: index + 1,
          sample_size: sampled.length,
          home_item_count: payload.item_count
        };

        const result = await postToBridge(upPayload);
        upNextResults.push(result);
        totalUpNext += upPayload.item_count;
      } catch (error) {
        upNextFailures.push({
          video_id: parent.video_id,
          title: parent.title,
          error: error.message
        });
      }

      await new Promise((resolve) => setTimeout(resolve, 500));
    }

    const upNextSummary = sampled.length
      ? `${upNextResults.length}/${sampled.length} seed thành công · ${totalUpNext} gợi ý Up Next`
      : 'đã tắt';
    const failText = upNextFailures.length ? `\nUp Next lỗi: ${upNextFailures.length}` : '';

    setStatus(
      `Xong · ${homeResult.profile_label || collectorProfile.profile_label} (${homeResult.profile_short_id || shortProfileId(collectorProfile.profile_id)})\n` +
      `Home: ${payload.item_count} video\n` +
      `Home report: ${homeResult.profile_html_path || 'disabled'}\n` +
      `Up Next: ${upNextSummary}${failText}\n` +
      `Reports: data/profile_reports`
    );
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
