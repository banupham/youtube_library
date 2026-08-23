const statusEl = document.getElementById('status');
const collectBtn = document.getElementById('collect');
const profileLabelEl = document.getElementById('profileLabel');
const profileIdEl = document.getElementById('profileId');
const CENTRAL_BASE = 'http://127.0.0.1:8770';

function setStatus(text) { statusEl.textContent = text; }
function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

function createProfileId() {
  if (globalThis.crypto?.randomUUID) return `browser-${crypto.randomUUID()}`;
  return `browser-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}
function shortProfileId(profileId) { return String(profileId || '').replace(/^browser-/, '').slice(0, 8) || 'unknown'; }
function createSessionId() {
  if (globalThis.crypto?.randomUUID) return `session-${crypto.randomUUID()}`;
  return `session-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
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
}

profileLabelEl.addEventListener('change', async () => {
  await saveProfileLabel();
  const profile = await loadCollectorProfile();
  setStatus(`Profile: ${profile.profile_label} (${shortProfileId(profile.profile_id)})\nCentral Server: 127.0.0.1:8770`);
});

async function collectHomepage(scrolls, delayMs) {
  const sleepLocal = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const CARD_SELECTORS = ['ytd-rich-item-renderer', 'ytd-video-renderer', 'ytd-grid-video-renderer', 'yt-lockup-view-model'];
  const TITLE_SELECTORS = [
    'a#video-title-link[href*="/watch?v="]', 'a#video-title[href*="/watch?v="]', 'h3 a[href*="/watch?v="]',
    '.yt-lockup-metadata-view-model-wiz__title a[href*="/watch?v="]', 'a.yt-lockup-metadata-view-model-wiz__title[href*="/watch?v="]'
  ];
  const CHANNEL_SELECTORS = ['ytd-channel-name a', '#channel-name a', '#text.ytd-channel-name', 'a[href^="/@"]', '.yt-lockup-metadata-view-model-wiz__metadata a[href^="/@"]'];
  const METADATA_SELECTORS = ['#metadata-line', '#metadata', '.yt-content-metadata-view-model-wiz__metadata-text', '.yt-lockup-metadata-view-model-wiz__metadata'];
  const DURATION_SELECTORS = ['ytd-thumbnail-overlay-time-status-renderer span', '#time-status span', '.badge-shape-wiz__text'];

  const isVisible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
  };
  const firstText = (root, selectors) => {
    for (const selector of selectors) {
      const value = root?.querySelector?.(selector)?.textContent?.trim();
      if (value) return value;
    }
    return '';
  };
  const validTitle = (value) => {
    const title = (value || '').trim();
    if (!title || /^(xem|trực tiếp|live|watch)$/i.test(title) || /^\d{1,2}:\d{2}(?::\d{2})?$/.test(title)) return '';
    return title;
  };
  const extract = () => {
    const items = [];
    for (const card of document.querySelectorAll(CARD_SELECTORS.join(','))) {
      if (!isVisible(card)) continue;
      let titleAnchor = null;
      for (const selector of TITLE_SELECTORS) {
        const candidate = card.querySelector(selector);
        if (candidate && isVisible(candidate)) { titleAnchor = candidate; break; }
      }
      if (!titleAnchor) continue;
      let url;
      try { url = new URL(titleAnchor.href, location.origin); } catch { continue; }
      const videoId = url.searchParams.get('v');
      if (!videoId) continue;
      let title = validTitle(titleAnchor.getAttribute('title')) || validTitle(titleAnchor.textContent);
      if (!title) title = validTitle(card.querySelector('h3, #video-title, yt-formatted-string#video-title')?.textContent);
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
  const merge = () => { for (const item of extract()) if (!collected.has(item.video_id)) collected.set(item.video_id, item); };
  merge();
  for (let i = 0; i < scrolls; i += 1) {
    window.scrollBy(0, Math.floor(window.innerHeight * 0.90));
    await sleepLocal(delayMs);
    merge();
  }
  const items = Array.from(collected.values()).map((item, index) => ({ position: index + 1, ...item }));
  return { source: 'youtube_home', captured_at: new Date().toISOString(), page_url: location.href, item_count: items.length, items };
}

async function collectUpNextFromWatchHtml(parentVideoId, limit, replayToken) {
  const diagnostics = {
    renderer_candidates: 0,
    accepted_video_renderers: 0,
    rejected_non_video_id: 0,
    rejected_playlist_or_mix: 0,
    rejected_parent_video: 0,
    rejected_missing_title: 0
  };

  function textValue(value) {
    if (!value) return '';
    if (typeof value === 'string') return value.trim();
    if (typeof value.simpleText === 'string') return value.simpleText.trim();
    if (Array.isArray(value.runs)) return value.runs.map((run) => run?.text || '').join('').trim();
    if (typeof value.content === 'string') return value.content.trim();
    return '';
  }
  function isVideoId(value) {
    return /^[A-Za-z0-9_-]{11}$/.test(String(value || ''));
  }
  function parseBalancedJson(source, startIndex) {
    const start = source.indexOf('{', startIndex);
    if (start < 0) return null;
    let depth = 0, inString = false, escaped = false;
    for (let i = start; i < source.length; i += 1) {
      const ch = source[i];
      if (inString) {
        if (escaped) escaped = false;
        else if (ch === '\\') escaped = true;
        else if (ch === '"') inString = false;
        continue;
      }
      if (ch === '"') inString = true;
      else if (ch === '{') depth += 1;
      else if (ch === '}') {
        depth -= 1;
        if (depth === 0) {
          try { return JSON.parse(source.slice(start, i + 1)); } catch { return null; }
        }
      }
    }
    return null;
  }
  function parseInitialData(htmlText) {
    for (const marker of ['var ytInitialData =', 'window["ytInitialData"] =', "window['ytInitialData'] =", 'ytInitialData =']) {
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
    if (node.secondaryResults && typeof node.secondaryResults === 'object') return node.secondaryResults;
    if (Array.isArray(node)) {
      for (const child of node) { const found = findSecondaryResults(child, depth + 1); if (found) return found; }
      return null;
    }
    for (const value of Object.values(node)) { const found = findSecondaryResults(value, depth + 1); if (found) return found; }
    return null;
  }
  function findWatchEndpoint(renderer) {
    return renderer?.navigationEndpoint?.watchEndpoint
      || renderer?.endpoint?.watchEndpoint
      || renderer?.rendererContext?.commandContext?.onTap?.innertubeCommand?.watchEndpoint
      || renderer?.onTap?.innertubeCommand?.watchEndpoint
      || renderer?.command?.watchEndpoint
      || null;
  }
  function isPlaylistLike(renderer, rendererType, watchEndpoint) {
    const contentType = String(renderer?.contentType || '').toUpperCase();
    if (contentType && contentType !== 'LOCKUP_CONTENT_TYPE_VIDEO' && rendererType === 'lockupViewModel') return true;
    if (/PLAYLIST|RADIO|MIX/.test(contentType)) return true;
    if (renderer?.playlistId || renderer?.radioRenderer || renderer?.compactRadioRenderer) return true;
    if (rendererType === 'lockupViewModel' && watchEndpoint?.playlistId) return true;
    return false;
  }
  function rendererToItem(renderer, rendererType = 'generic') {
    if (!renderer || typeof renderer !== 'object') return null;
    diagnostics.renderer_candidates += 1;

    const watchEndpoint = findWatchEndpoint(renderer);
    if (isPlaylistLike(renderer, rendererType, watchEndpoint)) {
      diagnostics.rejected_playlist_or_mix += 1;
      return null;
    }

    let videoId = '';
    if (rendererType === 'lockupViewModel') {
      videoId = watchEndpoint?.videoId || '';
      if (!videoId && String(renderer?.contentType || '').toUpperCase() === 'LOCKUP_CONTENT_TYPE_VIDEO') {
        videoId = renderer.contentId || '';
      }
    } else {
      videoId = renderer.videoId || watchEndpoint?.videoId || renderer.video_id || '';
    }

    if (!isVideoId(videoId)) {
      diagnostics.rejected_non_video_id += 1;
      return null;
    }
    if (videoId === parentVideoId) {
      diagnostics.rejected_parent_video += 1;
      return null;
    }

    const title = textValue(renderer.title)
      || textValue(renderer.headline)
      || textValue(renderer.metadata?.lockupMetadataViewModel?.title)
      || textValue(renderer.lockupMetadataViewModel?.title);
    if (!title) {
      diagnostics.rejected_missing_title += 1;
      return null;
    }

    const channel = textValue(renderer.shortBylineText)
      || textValue(renderer.longBylineText)
      || textValue(renderer.ownerText)
      || textValue(renderer.metadata?.lockupMetadataViewModel?.metadata?.contentMetadataViewModel?.metadataRows?.[0]?.metadataParts?.[0]?.text);
    const metadataParts = [
      textValue(renderer.viewCountText), textValue(renderer.shortViewCountText), textValue(renderer.publishedTimeText)
    ].filter(Boolean);

    diagnostics.accepted_video_renderers += 1;
    return {
      video_id: videoId,
      title,
      channel,
      url: `https://www.youtube.com/watch?v=${videoId}`,
      metadata_text: metadataParts.join(' · '),
      duration_text: textValue(renderer.lengthText),
      renderer_type: rendererType
    };
  }
  function collectRenderers(node, output, depth = 0) {
    if (!node || typeof node !== 'object' || depth > 24 || output.length >= limit * 5) return;

    for (const key of ['compactVideoRenderer', 'videoRenderer', 'gridVideoRenderer']) {
      if (node[key]) {
        const item = rendererToItem(node[key], key);
        if (item) output.push(item);
      }
    }

    if (node.lockupViewModel) {
      const item = rendererToItem(node.lockupViewModel, 'lockupViewModel');
      if (item) output.push(item);
    }

    if (node.videoId && node.title) {
      const item = rendererToItem(node, 'directVideoRenderer');
      if (item) output.push(item);
    }

    if (Array.isArray(node)) {
      for (const child of node) collectRenderers(child, output, depth + 1);
    } else {
      for (const value of Object.values(node)) collectRenderers(value, output, depth + 1);
    }
  }

  const nonce = encodeURIComponent(String(replayToken || Date.now()));
  const response = await fetch(`/watch?v=${encodeURIComponent(parentVideoId)}&autoplay=0&_ytlib_replay=${nonce}`, {
    method: 'GET', credentials: 'include', cache: 'no-store', redirect: 'follow'
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
    if (!isVideoId(item.video_id) || seen.has(item.video_id)) continue;
    seen.add(item.video_id);
    items.push({ position: items.length + 1, ...item });
    if (items.length >= limit) break;
  }

  return {
    source: 'youtube_up_next',
    captured_at: new Date().toISOString(),
    extraction_mode: 'same_origin_watch_html_video_only_no_player',
    extraction_version: 'up_next_video_only_v2',
    parent_video_id: parentVideoId,
    page_url: `https://www.youtube.com/watch?v=${parentVideoId}`,
    item_count: items.length,
    extraction_diagnostics: diagnostics,
    items
  };
}

function cryptoRandomInt(maxExclusive) {
  if (maxExclusive <= 1) return 0;
  const maxUint = 0x100000000, limit = maxUint - (maxUint % maxExclusive), bucket = new Uint32Array(1);
  do { crypto.getRandomValues(bucket); } while (bucket[0] >= limit);
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

async function postCentral(endpoint, payload) {
  const response = await fetch(`${CENTRAL_BASE}${endpoint}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
  });
  if (!response.ok) {
    let detail = '';
    try { detail = await response.text(); } catch { detail = ''; }
    throw new Error(`Central HTTP ${response.status}${detail ? `: ${detail.slice(0, 180)}` : ''}`);
  }
  return response.json();
}

collectBtn.addEventListener('click', async () => {
  collectBtn.disabled = true;
  setStatus('Đang đọc YouTube Home...');
  try {
    await saveProfileLabel();
    const collectorProfile = await loadCollectorProfile();
    const collectionSessionId = createSessionId();
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id || !tab.url?.startsWith('https://www.youtube.com/')) throw new Error('Hãy mở YouTube trong tab hiện tại trước.');

    const scrolls = Math.max(0, Math.min(50, Number(document.getElementById('scrolls').value || 8)));
    const delay = Math.max(200, Math.min(10000, Number(document.getElementById('delay').value || 1500)));
    const upNextSamples = Math.max(0, Math.min(10, Number(document.getElementById('upNextSamples').value || 3)));
    const upNextReplays = Math.max(1, Math.min(10, Number(document.getElementById('upNextReplays').value || 3)));
    const upNextLimit = Math.max(5, Math.min(40, Number(document.getElementById('upNextLimit').value || 20)));
    const shouldCollectSubscriptions = Boolean(document.getElementById('collectSubscriptions')?.checked);
    const subscriptionLimit = Math.max(10, Math.min(100, Number(document.getElementById('subscriptionLimit')?.value || 60)));

    const homeExec = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: collectHomepage, args: [scrolls, delay] });
    const home = homeExec?.[0]?.result;
    if (!home || !Array.isArray(home.items)) throw new Error('Không lấy được dữ liệu Home.');
    home.collector_profile = collectorProfile;
    home.collection_session_id = collectionSessionId;
    await postCentral('/collect', home);

    let subscriptionVideos = 0;
    let subscriptionChannels = 0;
    let subscriptionError = null;
    if (shouldCollectSubscriptions) {
      setStatus(
        `Profile: ${collectorProfile.profile_label} (${shortProfileId(collectorProfile.profile_id)})\n` +
        `Home: ${home.item_count} video\nĐang đọc Subscriptions read-only...`
      );
      try {
        const subExec = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: collectSubscriptionsReadOnly,
          args: [subscriptionLimit]
        });
        const subscriptions = subExec?.[0]?.result;
        if (!subscriptions || !Array.isArray(subscriptions.items)) throw new Error('Không lấy được Subscriptions payload.');
        subscriptions.collector_profile = collectorProfile;
        subscriptions.collection_session_id = collectionSessionId;
        await postCentral('/collect', subscriptions);
        subscriptionVideos = subscriptions.item_count || subscriptions.items.length;
        subscriptionChannels = Array.isArray(subscriptions.subscription_channels)
          ? subscriptions.subscription_channels.length
          : 0;
      } catch (error) {
        subscriptionError = error;
        console.warn('Subscriptions collection failed', error);
      }
    }

    const sampled = sampleWithoutReplacement(home.items.filter((x) => x?.video_id), upNextSamples);
    const totalRequests = sampled.length * upNextReplays;
    let requestSequence = 0, success = 0, failures = 0, totalUpNext = 0;

    for (let seedIndex = 0; seedIndex < sampled.length; seedIndex += 1) {
      const parent = sampled[seedIndex];
      for (let replayIndex = 1; replayIndex <= upNextReplays; replayIndex += 1) {
        requestSequence += 1;
        setStatus(
          `Profile: ${collectorProfile.profile_label} (${shortProfileId(collectorProfile.profile_id)})\n` +
          `Home: ${home.item_count} · Sub: ${subscriptionVideos}/${subscriptionChannels} channels\n` +
          `Seed ${seedIndex + 1}/${sampled.length} · replay ${replayIndex}/${upNextReplays}\n` +
          `Up Next request ${requestSequence}/${totalRequests}: ${parent.title}`
        );
        try {
          const replayToken = `${Date.now()}-${seedIndex + 1}-${replayIndex}-${cryptoRandomInt(1000000)}`;
          const exec = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: collectUpNextFromWatchHtml, args: [parent.video_id, upNextLimit, replayToken] });
          const up = exec?.[0]?.result;
          if (!up || !Array.isArray(up.items)) throw new Error('Watch HTML không trả về Up Next.');
          Object.assign(up, {
            collector_profile: collectorProfile,
            collection_session_id: collectionSessionId,
            parent_title: parent.title || '',
            parent_channel: parent.channel || '',
            parent_home_position: parent.position || null,
            source_home_captured_at: home.captured_at,
            sample_context: {
              method: 'crypto_random_without_replacement', sample_index: seedIndex + 1, sample_size: sampled.length, home_item_count: home.item_count
            },
            replay_context: {
              replay_index: replayIndex, replay_count: upNextReplays, request_sequence: requestSequence, total_requests: totalRequests, replay_token: replayToken
            }
          });
          await postCentral('/collect', up);
          success += 1;
          totalUpNext += up.item_count;
        } catch (error) {
          failures += 1;
          console.warn('Up Next replay failed', parent.video_id, replayIndex, error);
        }
        await sleep(500);
      }
    }

    setStatus('Đang cập nhật daily history + temporal profile...');
    const finalResult = await postCentral('/finalize', {
      collector_profile: collectorProfile,
      collection_session_id: collectionSessionId
    });
    await chrome.storage.local.set({ lastDailyCollectionAt: new Date().toISOString() });

    setStatus(
      `Xong · ${collectorProfile.profile_label} (${shortProfileId(collectorProfile.profile_id)})\n` +
      `Hồ sơ: ${finalResult.behavior_profile_name || 'đang hình thành'}\n` +
      `Daily history: ${finalResult.daily_observation_count || 1} ngày\n` +
      `Home: ${home.item_count} · Sub videos/channels: ${subscriptionVideos}/${subscriptionChannels}\n` +
      `Up Next replay: ${success}/${totalRequests} · observations: ${totalUpNext}\n` +
      (subscriptionError ? `Subscriptions cảnh báo: ${subscriptionError.message}\n` : '') +
      (failures ? `Replay lỗi: ${failures}\n` : '') +
      `Kết quả profile đã mở trên trình duyệt.`
    );

    if (finalResult.profile_url) {
      await chrome.tabs.create({ url: finalResult.profile_url });
    }
  } catch (error) {
    setStatus(`Lỗi: ${error.message}`);
  } finally {
    collectBtn.disabled = false;
  }
});

loadCollectorProfile().then(async (profile) => {
  const stored = await chrome.storage.local.get(['lastDailyCollectionAt']);
  const last = stored.lastDailyCollectionAt ? `\nLần cập nhật gần nhất: ${stored.lastDailyCollectionAt}` : '';
  setStatus(`Profile: ${profile.profile_label} (${shortProfileId(profile.profile_id)})\nCentral Server: 127.0.0.1:8770.${last}`);
}).catch((error) => setStatus(`Không khởi tạo được profile ID: ${error.message}`));
