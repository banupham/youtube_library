// YouTube homepage snapshot exporter (read-only).
//
// Usage:
// 1. Open https://www.youtube.com/ and stay on Home.
// 2. Scroll enough to load the cards you want to sample.
// 3. Open DevTools Console and paste this file's contents.
// 4. The JSON result is copied to the clipboard and printed to the console.
//
// This script only reads the currently rendered DOM. It does not click, play,
// like, subscribe, or otherwise interact with videos.

(() => {
  const anchors = Array.from(
    document.querySelectorAll(
      'a#video-title-link[href*="/watch?v="], a#video-title[href*="/watch?v="], a[href*="/watch?v="]'
    )
  );

  const seen = new Set();
  const items = [];

  const isVisible = (el) => {
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return (
      rect.width > 0 &&
      rect.height > 0 &&
      style.visibility !== 'hidden' &&
      style.display !== 'none'
    );
  };

  const text = (root, selectors) => {
    for (const selector of selectors) {
      const el = root?.querySelector?.(selector);
      const value = el?.textContent?.trim();
      if (value) return value;
    }
    return '';
  };

  for (const anchor of anchors) {
    if (!isVisible(anchor)) continue;

    let url;
    try {
      url = new URL(anchor.href, location.origin);
    } catch {
      continue;
    }

    const videoId = url.searchParams.get('v');
    if (!videoId || seen.has(videoId)) continue;

    const card =
      anchor.closest('ytd-rich-item-renderer') ||
      anchor.closest('ytd-video-renderer') ||
      anchor.closest('ytd-grid-video-renderer') ||
      anchor.closest('yt-lockup-view-model') ||
      anchor.parentElement?.parentElement ||
      document;

    const title =
      anchor.getAttribute('title')?.trim() ||
      anchor.getAttribute('aria-label')?.trim() ||
      anchor.textContent?.trim() ||
      '';

    if (!title) continue;

    const channel = text(card, [
      'ytd-channel-name a',
      '#channel-name a',
      '#text.ytd-channel-name',
      'a[href^="/@"]',
    ]);

    const metadata = text(card, [
      '#metadata-line',
      '#metadata',
      '.yt-content-metadata-view-model-wiz__metadata-text',
    ]);

    const duration = text(card, [
      'ytd-thumbnail-overlay-time-status-renderer span',
      '#time-status span',
      '.badge-shape-wiz__text',
    ]);

    seen.add(videoId);
    items.push({
      position: items.length + 1,
      video_id: videoId,
      title,
      channel,
      url: `https://www.youtube.com/watch?v=${videoId}`,
      metadata_text: metadata,
      duration_text: duration,
    });
  }

  const payload = {
    source: 'youtube_home',
    captured_at: new Date().toISOString(),
    page_url: location.href,
    item_count: items.length,
    items,
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
