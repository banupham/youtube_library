package com.youtube.library.collector

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.os.Handler
import android.os.Looper
import android.view.accessibility.AccessibilityEvent
import java.time.Instant

class YouTubeAccessibilityService : AccessibilityService() {
    private val handler = Handler(Looper.getMainLooper())
    private lateinit var snapshotStore: LocalSnapshotStore
    private var pendingEventType: Int? = null
    private var lastSurface: String? = null
    private var lastWatchOpenAtMs: Long = 0L

    private val captureRunnable = Runnable {
        captureCurrentYouTubeTree(pendingEventType)
        pendingEventType = null
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        CollectorSettings.ensureIdentity(this)
        snapshotStore = LocalSnapshotStore(this)
        serviceInfo = serviceInfo.apply {
            packageNames = arrayOf(YOUTUBE_PACKAGE)
            eventTypes = AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED or
                AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED or
                AccessibilityEvent.TYPE_VIEW_SCROLLED or
                AccessibilityEvent.TYPE_VIEW_CLICKED
            feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC
            notificationTimeout = 500
            flags = flags or AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS
        }
        AndroidAutoSync.flushAsync(this)
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event?.packageName?.toString() != YOUTUBE_PACKAGE) return
        val prefs = getSharedPreferences(CollectorSettings.PREFS, MODE_PRIVATE)
        if (!prefs.getBoolean(CollectorSettings.KEY_DISCLOSURE_ACCEPTED, false)) return
        if (prefs.getBoolean(CollectorSettings.KEY_PAUSED, false)) return

        if (event.eventType == AccessibilityEvent.TYPE_VIEW_CLICKED) {
            InteractionDetector.detect(event)?.let { detected ->
                AndroidAutoSync.enqueueInteraction(
                    context = this,
                    eventType = detected.eventType,
                    score = detected.score,
                    confidence = detected.confidence,
                    surface = lastSurface,
                    treeSignature = null,
                    eventClass = detected.eventClass
                )
            }
        }

        pendingEventType = event.eventType
        handler.removeCallbacks(captureRunnable)
        handler.postDelayed(captureRunnable, CAPTURE_DEBOUNCE_MS)
    }

    private fun captureCurrentYouTubeTree(eventType: Int?) {
        val root = rootInActiveWindow ?: return
        if (root.packageName?.toString() != YOUTUBE_PACKAGE) return
        val (nodes, signature) = NodeTreeExtractor.extract(root)
        if (nodes.isEmpty()) return
        val surface = SurfaceDetector.guess(nodes)
        val stored = snapshotStore.appendIfAllowed(
            AccessibilitySnapshot(
                capturedAt = Instant.now().toString(),
                eventType = eventType,
                surfaceGuess = surface,
                treeSignature = signature,
                nodes = nodes
            )
        )

        val now = System.currentTimeMillis()
        val enteredWatch = surface.surface == "watch" && lastSurface != "watch"
        val watchWindowChange = surface.surface == "watch" &&
            eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED &&
            now - lastWatchOpenAtMs > VIDEO_OPEN_DEDUPE_MS
        if (stored && (enteredWatch || watchWindowChange)) {
            AndroidAutoSync.enqueueInteraction(
                context = this,
                eventType = "video_open",
                score = 0.25,
                confidence = if (enteredWatch) 0.7 else 0.55,
                surface = "watch",
                treeSignature = signature,
                eventClass = "accessibility_watch_transition"
            )
            lastWatchOpenAtMs = now
        }
        lastSurface = surface.surface
    }

    override fun onInterrupt() {
        handler.removeCallbacks(captureRunnable)
    }

    override fun onDestroy() {
        handler.removeCallbacks(captureRunnable)
        super.onDestroy()
    }

    companion object {
        const val YOUTUBE_PACKAGE = "com.google.android.youtube"
        private const val CAPTURE_DEBOUNCE_MS = 1_200L
        private const val VIDEO_OPEN_DEDUPE_MS = 4_000L
    }
}
