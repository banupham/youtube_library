(() => {
  const DAILY_CAPS = { home: 2, up_next: 8, subscriptions: 1, channels: 1 };
  let routeGeneration = 0;
  let lastUrl = location.href;
  let lastVideoOpenId = '';

  function localDayKey(date = new Date()) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }
  async function passiveEnabled() {
    const stored = await chrome.storage.local.get(['passiveAutoEnabled']);
    return stored.passiveAutoEnabled !== false;
  }
  function text(root, selectors) {
    for (const selector of selectors) {
      const value = root?.querySelector?.(selector)?.textContent?.trim();
      if (value) return value;
    }
    return '';
  }
  function videoIdFromHref(href) {
    try {
      const url = new URL(href, location.origin);
      const id = url.searchParams.get('v') || '';
      return /^[A-Za-z0-9_-]{11}$/.test(id) ? id : '';
    } catch { return ''; }
  }
  function validTitle(value) {
    const title = String(value || '').trim();
    if (!title || /^(xem|watch|live|trực tiếp)$/i.test(title)) return '';
    if (/^\d{1,2}:\d{2}(?::\d{2})?$/.test(title)) return '';
    return title;
  }

  function currentSubscriptionState() {
    const roots = [
      document.querySelector('ytd-subscribe-button-renderer'),
      document.querySelector('yt-subscribe-button-view-model'),
      document.querySelector('#subscribe-button')
    ].filter(Boolean);
    for (const root of roots) {
      const label = [
        root.textContent,
        root.querySelector('button')?.getAttribute('aria-label'),
        root.querySelector('button')?.textContent
      ].filter(Boolean).join(' ').toLowerCase();
      if (/đã đăng ký|subscribed|unsubscribe|hủy đăng ký/.test(label)) return 'subscribed';
      if (/\bsubscribe\b|\bđăng ký\b/.test(label)) return 'not_subscribed';
    }
    return 'unknown';
  }

  function currentWatchContext() {
    if (location.pathname !== '/watch') return {};
    const videoId = new URL(location.href).searchParams.get('v') || '';
    return {
      video_id: /^[A-Za-z0-9_-]{11}$/.test(videoId) ? videoId : null,
      video_title: String(document.title || '').replace(/\s*-\s*YouTube\s*$/, '').trim() || null,
      channel: text(document, [
        'ytd-watch-metadata ytd-channel-name a',
        '#owner ytd-channel-name a',
        'ytd-video-owner-renderer ytd-channel-name a'
      ]) || null,
      channel_subscription_state: currentSubscriptionState(),
      surface: 'watch',
      page_url: location.href
    };
  }

  async function sendInteraction(eventType, extra = {}) {
    if (!(await passiveEnabled())) return;
    const payload = {
      event_type: eventType,
      captured_at: new Date().toISOString(),
      confidence: 1,
      detection: 'browser_dom_natural_action',
      ...currentWatchContext(),
      ...extra
    };
    try {
      await chrome.runtime.sendMessage({ type: 'youtube_library_interaction', payload });
    } catch (error) {
      console.debug('Interaction event queued/skipped', error);
    }
  }

  function extractVideoCards(root = document, limit = 120) {
    const cards = root.querySelectorAll([
      'ytd-rich-item-renderer', 'ytd-video-renderer', 'ytd-grid-video-renderer',
      'ytd-compact-video-renderer', 'yt-lockup-view-model'
    ].join(','));
    const output = [];
    const seen = new Set();
    for (const card of cards) {
      const anchor = card.querySelector([
        'a#video-title-link[href*="/watch?v="]', 'a#video-title[href*="/watch?v="]',
        'h3 a[href*="/watch?v="]', '.yt-lockup-metadata-view-model-wiz__title a[href*="/watch?v="]',
        'a.yt-lockup-metadata-view-model-wiz__title[href*="/watch?v="]'
      ].join(','));
      if (!anchor) continue;
      const videoId = videoIdFromHref(anchor.href);
      if (!videoId || seen.has(videoId)) continue;
      const title = validTitle(anchor.getAttribute('title')) || validTitle(anchor.textContent)
        || validTitle(card.querySelector('h3, #video-title, yt-formatted-string#video-title')?.textContent);
      if (!title) continue;
      seen.add(videoId);
      output.push({
        position: output.length + 1,
        video_id: videoId,
        title,
        channel: text(card, [
          'ytd-channel-name a', '#channel-name a', '#text.ytd-channel-name',
          'a[href^="/@"]', '.yt-lockup-metadata-view-model-wiz__metadata a[href^="/@"]'
        ]),
        url: `https://www.youtube.com/watch?v=${videoId}`,
        metadata_text: text(card, ['#metadata-line', '#metadata', '.yt-content-metadata-view-model-wiz__metadata-text', '.yt-lockup-metadata-view-model-wiz__metadata']),
        duration_text: text(card, ['ytd-thumbnail-overlay-time-status-renderer span', '#time-status span', '.badge-shape-wiz__text'])
      });
      if (output.length >= limit) break;
    }
    return output;
  }

  function extractWatchUpNext(limit = 30) {
    const secondary = document.querySelector('#secondary, ytd-watch-next-secondary-results-renderer');
    if (!secondary) return [];
    const parent = new URL(location.href).searchParams.get('v');
    return extractVideoCards(secondary, limit)
      .filter((item) => item.video_id !== parent)
      .map((item, index) => ({ ...item, position: index + 1 }));
  }

  function extractSubscribedChannels(limit = 200) {
    const roots = document.querySelectorAll('ytd-channel-renderer, ytd-grid-channel-renderer, yt-lockup-view-model');
    const output = [];
    const seen = new Set();
    for (const root of roots) {
      const anchor = root.querySelector('a[href^="/channel/"], a[href^="/@"]');
      if (!anchor) continue;
      let url;
      try { url = new URL(anchor.href, location.origin); } catch { continue; }
      const path = url.pathname;
      const channelId = path.startsWith('/channel/') ? path.split('/')[2] || '' : '';
      const name = validTitle(anchor.textContent)
        || validTitle(text(root, ['#channel-title', '#text.ytd-channel-name', 'h3', '.yt-lockup-metadata-view-model-wiz__title']));
      const key = channelId || path;
      if (!key || seen.has(key)) continue;
      seen.add(key);
      output.push({
        channel_id: channelId || null,
        name: name || path.replace(/^\/@?/, ''),
        url: `https://www.youtube.com${path}`,
        subscriber_text: text(root, ['#subscribers', '#subscriber-count', '.yt-content-metadata-view-model-wiz__metadata-text']),
        video_count_text: text(root, ['#video-count'])
      });
      if (output.length >= limit) break;
    }
    return output;
  }

  async function quotaAllows(kind) {
    const stored = await chrome.storage.local.get(['passiveDailyQuota']);
    const day = localDayKey();
    const quota = stored.passiveDailyQuota?.date === day ? stored.passiveDailyQuota : { date: day, counts: {} };
    const used = Number(quota.counts?.[kind] || 0);
    return { allowed: used < (DAILY_CAPS[kind] || 1), quota };
  }
  async function recordQuota(kind, quota) {
    const counts = { ...(quota.counts || {}) };
    counts[kind] = Number(counts[kind] || 0) + 1;
    await chrome.storage.local.set({ passiveDailyQuota: { date: quota.date, counts } });
  }
  async function sendSnapshot(kind, payload) {
    if (!(await passiveEnabled())) return;
    const quotaState = await quotaAllows(kind);
    if (!quotaState.allowed) return;
    try {
      const result = await chrome.runtime.sendMessage({ type: 'youtube_library_passive_snapshot', payload });
      if (result?.ok) await recordQuota(kind, quotaState.quota);
    } catch (error) {
      console.debug('YouTube Library passive snapshot skipped', error);
    }
  }

  async function captureHome(generation) {
    await new Promise((resolve) => setTimeout(resolve, 25000));
    if (generation !== routeGeneration || location.pathname !== '/' || !(await passiveEnabled())) return;
    const items = extractVideoCards(document, 100);
    if (!items.length) return;
    await sendSnapshot('home', {
      source: 'youtube_home', captured_at: new Date().toISOString(), page_url: location.href,
      extraction_mode: 'passive_dom_natural_home', extraction_version: 'passive_v2',
      item_count: items.length, items
    });
  }

  async function captureWatch(generation) {
    await new Promise((resolve) => setTimeout(resolve, 2000));
    if (generation !== routeGeneration || location.pathname !== '/watch' || !(await passiveEnabled())) return;
    const ctx = currentWatchContext();
    if (ctx.video_id && ctx.video_id !== lastVideoOpenId) {
      lastVideoOpenId = ctx.video_id;
      await sendInteraction('video_open', ctx);
    }
    await new Promise((resolve) => setTimeout(resolve, 8000));
    if (generation !== routeGeneration || location.pathname !== '/watch') return;
    const parentVideoId = new URL(location.href).searchParams.get('v');
    if (!/^[A-Za-z0-9_-]{11}$/.test(parentVideoId || '')) return;
    const items = extractWatchUpNext(30);
    if (!items.length) return;
    const watch = currentWatchContext();
    await sendSnapshot('up_next', {
      source: 'youtube_up_next', captured_at: new Date().toISOString(), page_url: location.href,
      extraction_mode: 'passive_dom_natural_watch_page', extraction_version: 'passive_v2',
      parent_video_id: parentVideoId, parent_title: watch.video_title || '', parent_channel: watch.channel || '',
      parent_subscription_state: watch.channel_subscription_state,
      sample_context: { method: 'natural_user_navigation', sample_size: 1 },
      replay_context: { replay_index: 1, replay_count: 1, request_sequence: 1, total_requests: 1 },
      item_count: items.length, items
    });
  }

  async function captureSubscriptions(generation) {
    await new Promise((resolve) => setTimeout(resolve, 18000));
    if (generation !== routeGeneration || location.pathname !== '/feed/subscriptions' || !(await passiveEnabled())) return;
    const items = extractVideoCards(document, 80);
    if (!items.length) return;
    await sendSnapshot('subscriptions', {
      source: 'youtube_subscriptions', captured_at: new Date().toISOString(), page_url: location.href,
      extraction_mode: 'passive_dom_natural_subscriptions', extraction_version: 'passive_v2',
      item_count: items.length, subscription_channels: [], items
    });
  }

  async function captureChannels(generation) {
    await new Promise((resolve) => setTimeout(resolve, 12000));
    if (generation !== routeGeneration || location.pathname !== '/feed/channels' || !(await passiveEnabled())) return;
    const channels = extractSubscribedChannels(200);
    if (!channels.length) return;
    await sendSnapshot('channels', {
      source: 'youtube_subscriptions', captured_at: new Date().toISOString(), page_url: location.href,
      extraction_mode: 'passive_dom_natural_subscribed_channels', extraction_version: 'passive_v2',
      item_count: 0, subscription_channels: channels, items: []
    });
  }

  async function scheduleForCurrentRoute() {
    if (!(await passiveEnabled())) return;
    routeGeneration += 1;
    const generation = routeGeneration;
    if (location.pathname === '/') captureHome(generation);
    else if (location.pathname === '/watch') captureWatch(generation);
    else if (location.pathname === '/feed/subscriptions') captureSubscriptions(generation);
    else if (location.pathname === '/feed/channels') captureChannels(generation);
  }

  document.addEventListener('click', (event) => {
    if (location.pathname !== '/watch') return;
    const target = event.target instanceof Element ? event.target : null;
    const button = target?.closest('button, tp-yt-paper-button, ytd-button-renderer, yt-button-shape');
    if (!button) return;
    const label = [button.getAttribute?.('aria-label'), button.getAttribute?.('title'), button.textContent]
      .filter(Boolean).join(' ').replace(/\s+/g, ' ').trim().toLowerCase();

    const commentBox = button.closest('ytd-comment-simplebox-renderer, ytd-comment-dialog-renderer');
    if (commentBox && /(comment|bình luận|post|gửi)/i.test(label)) {
      setTimeout(() => sendInteraction('comment_submit', { confidence: 0.95 }), 100);
      return;
    }

    const isDislike = /(dislike|không thích)/i.test(label);
    const isLike = !isDislike && /(^|\s)(like|thích)(\s|$|video)/i.test(label);
    if (!isLike && !isDislike) return;
    setTimeout(() => {
      const pressed = button.getAttribute?.('aria-pressed');
      if (isDislike) sendInteraction(pressed === 'false' ? 'undislike' : 'dislike', { confidence: pressed == null ? 0.7 : 0.95 });
      else sendInteraction(pressed === 'false' ? 'unlike' : 'like', { confidence: pressed == null ? 0.7 : 0.95 });
    }, 180);
  }, true);

  scheduleForCurrentRoute();
  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName !== 'local' || !changes.passiveAutoEnabled) return;
    if (changes.passiveAutoEnabled.newValue === false) { routeGeneration += 1; return; }
    scheduleForCurrentRoute();
  });
  setInterval(() => {
    if (location.href === lastUrl) return;
    lastUrl = location.href;
    scheduleForCurrentRoute();
  }, 1500);
})();
