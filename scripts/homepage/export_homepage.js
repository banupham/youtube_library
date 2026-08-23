// YouTube homepage snapshot exporter (read-only).
//
// Usage in DevTools Console or Snippets:
// 1. Open https://www.youtube.com/ and stay on Home.
// 2. Scroll enough to load the cards you want to sample.
// 3. Run this script.
// 4. The JSON result is copied to the clipboard and printed to the console.
//
// This script only reads the currently rendered DOM. It does not click, play,
// like, subscribe, or otherwise interact with videos.

(() => {
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

  const cards = Array.from(document.querySelectorAll(CARD_SELECTORS.join(',')));
  const seen = new Set();
  const items = [];

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
    if (!videoId || seen.has(videoId)) continue;

    const title =
      titleAnchor.getAttribute('title')?.trim() ||
      titleAnchor.textContent?.trim() ||
      '';

    // Guard against accidentally capturing overlay labels or duration text.
    if (!title || /^(xem|trực tiếp|live)$/i.test(title) || /^\d{1,2}:\d{2}(?::\d{2})?$/.test(title)) {
      continue;
    }

    const channel = firstText(card, CHANNEL_SELECTORS);
    const metadata = firstText(card, METADATA_SELECTORS);
    const duration = firstText(card, DURATION_SELECTORS);

    seen.add(videoId);
    items.push({
      position: items.length + 1,
      video_id: videoId,
      title,
      channel,
      url: `https://www.youtube.com/watch?v=${videoId}`,
      metadata_text: metadata,
      duration_text: duration
    });
  }

  const payload = {
    source: 'youtube_home',
    captured_at: new Date().toISOString(),
    page_url: location.href,
    item_count: items.length,
    items
  };

  const output = JSON.stringify(payload, null, 2);
  console.log(output);

  if (typeof copy === 'function') {
    copy(output);
    console.log(`Copied ${items.length} homepage video cards to clipboard.`);
  } else if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(output)
      .then(() => console.log(`Copied ${items.length} homepage video cards to clipboard.`))
      .catch(() => console.log('Clipboard copy failed; copy the JSON from the console output.'));
  }

  return payload;
})();
