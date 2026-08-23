async function collectSubscriptionsReadOnly(limit = 60) {
  const diagnostics = {
    feed_video_candidates: 0,
    feed_videos_accepted: 0,
    feed_non_video_rejected: 0,
    channel_candidates: 0,
    channels_accepted: 0,
    feed_http_status: null,
    channels_http_status: null
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

  function isChannelId(value) {
    return /^UC[A-Za-z0-9_-]{22}$/.test(String(value || ''));
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

  function watchEndpoint(renderer) {
    return renderer?.navigationEndpoint?.watchEndpoint
      || renderer?.endpoint?.watchEndpoint
      || renderer?.rendererContext?.commandContext?.onTap?.innertubeCommand?.watchEndpoint
      || renderer?.onTap?.innertubeCommand?.watchEndpoint
      || renderer?.command?.watchEndpoint
      || null;
  }

  function videoFromRenderer(renderer, rendererType) {
    if (!renderer || typeof renderer !== 'object') return null;
    diagnostics.feed_video_candidates += 1;
    const endpoint = watchEndpoint(renderer);
    const contentType = String(renderer?.contentType || '').toUpperCase();
    if (/PLAYLIST|RADIO|MIX/.test(contentType) || renderer?.playlistId || endpoint?.playlistId) {
      diagnostics.feed_non_video_rejected += 1;
      return null;
    }

    let videoId = renderer.videoId || endpoint?.videoId || '';
    if (!videoId && rendererType === 'lockupViewModel' && contentType === 'LOCKUP_CONTENT_TYPE_VIDEO') {
      videoId = renderer.contentId || '';
    }
    if (!isVideoId(videoId)) {
      diagnostics.feed_non_video_rejected += 1;
      return null;
    }

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

    diagnostics.feed_videos_accepted += 1;
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

  function collectVideos(node, output, depth = 0) {
    if (!node || typeof node !== 'object' || depth > 26 || output.length >= limit * 6) return;
    for (const key of ['compactVideoRenderer', 'videoRenderer', 'gridVideoRenderer']) {
      if (node[key]) {
        const item = videoFromRenderer(node[key], key);
        if (item) output.push(item);
      }
    }
    if (node.lockupViewModel) {
      const item = videoFromRenderer(node.lockupViewModel, 'lockupViewModel');
      if (item) output.push(item);
    }
    if (Array.isArray(node)) {
      for (const child of node) collectVideos(child, output, depth + 1);
    } else {
      for (const value of Object.values(node)) collectVideos(value, output, depth + 1);
    }
  }

  function browseEndpoint(renderer) {
    return renderer?.navigationEndpoint?.browseEndpoint
      || renderer?.endpoint?.browseEndpoint
      || renderer?.rendererContext?.commandContext?.onTap?.innertubeCommand?.browseEndpoint
      || renderer?.onTap?.innertubeCommand?.browseEndpoint
      || null;
  }

  function channelFromRenderer(renderer, rendererType) {
    if (!renderer || typeof renderer !== 'object') return null;
    diagnostics.channel_candidates += 1;
    const endpoint = browseEndpoint(renderer);
    const contentType = String(renderer?.contentType || '').toUpperCase();
    let channelId = renderer.channelId || endpoint?.browseId || '';
    if (!channelId && rendererType === 'lockupViewModel' && /CHANNEL/.test(contentType)) {
      channelId = renderer.contentId || '';
    }
    if (channelId && !isChannelId(channelId)) channelId = '';

    const name = textValue(renderer.title)
      || textValue(renderer.headline)
      || textValue(renderer.metadata?.lockupMetadataViewModel?.title)
      || textValue(renderer.lockupMetadataViewModel?.title);
    if (!name && !channelId) return null;
    if (rendererType === 'lockupViewModel' && contentType && !/CHANNEL/.test(contentType)) return null;

    const canonical = endpoint?.canonicalBaseUrl
      || renderer?.navigationEndpoint?.commandMetadata?.webCommandMetadata?.url
      || renderer?.endpoint?.commandMetadata?.webCommandMetadata?.url
      || '';
    const url = canonical
      ? new URL(canonical, 'https://www.youtube.com').href
      : channelId
        ? `https://www.youtube.com/channel/${channelId}`
        : null;

    diagnostics.channels_accepted += 1;
    return {
      channel_id: channelId || null,
      name: name || channelId || 'Unknown channel',
      url,
      subscriber_text: textValue(renderer.subscriberCountText),
      video_count_text: textValue(renderer.videoCountText),
      renderer_type: rendererType
    };
  }

  function collectChannels(node, output, depth = 0) {
    if (!node || typeof node !== 'object' || depth > 26 || output.length >= 500) return;
    for (const key of ['channelRenderer', 'gridChannelRenderer']) {
      if (node[key]) {
        const item = channelFromRenderer(node[key], key);
        if (item) output.push(item);
      }
    }
    if (node.lockupViewModel) {
      const item = channelFromRenderer(node.lockupViewModel, 'lockupViewModel');
      if (item) output.push(item);
    }
    if (Array.isArray(node)) {
      for (const child of node) collectChannels(child, output, depth + 1);
    } else {
      for (const value of Object.values(node)) collectChannels(value, output, depth + 1);
    }
  }

  const feedResponse = await fetch('/feed/subscriptions', {
    method: 'GET', credentials: 'include', cache: 'no-store', redirect: 'follow'
  });
  diagnostics.feed_http_status = feedResponse.status;
  if (!feedResponse.ok) throw new Error(`Subscriptions feed HTTP ${feedResponse.status}`);
  const feedHtml = await feedResponse.text();
  const feedData = parseInitialData(feedHtml);
  if (!feedData) throw new Error('Không tìm thấy ytInitialData của Subscriptions feed.');

  const rawVideos = [];
  collectVideos(feedData, rawVideos);
  const seenVideos = new Set();
  const items = [];
  for (const item of rawVideos) {
    if (!isVideoId(item.video_id) || seenVideos.has(item.video_id)) continue;
    seenVideos.add(item.video_id);
    items.push({ position: items.length + 1, ...item });
    if (items.length >= limit) break;
  }

  let subscriptionChannels = [];
  try {
    const channelsResponse = await fetch('/feed/channels', {
      method: 'GET', credentials: 'include', cache: 'no-store', redirect: 'follow'
    });
    diagnostics.channels_http_status = channelsResponse.status;
    if (channelsResponse.ok) {
      const channelsHtml = await channelsResponse.text();
      const channelsData = parseInitialData(channelsHtml);
      if (channelsData) {
        const rawChannels = [];
        collectChannels(channelsData, rawChannels);
        const seen = new Set();
        subscriptionChannels = rawChannels.filter((row) => {
          const key = row.channel_id || String(row.name || '').toLowerCase();
          if (!key || seen.has(key)) return false;
          seen.add(key);
          return true;
        });
      }
    }
  } catch (error) {
    console.warn('Subscribed channels page collection failed', error);
  }

  return {
    source: 'youtube_subscriptions',
    captured_at: new Date().toISOString(),
    extraction_mode: 'same_origin_subscriptions_html_read_only',
    extraction_version: 'subscriptions_v1',
    page_url: 'https://www.youtube.com/feed/subscriptions',
    item_count: items.length,
    subscription_channels: subscriptionChannels,
    extraction_diagnostics: diagnostics,
    items
  };
}
