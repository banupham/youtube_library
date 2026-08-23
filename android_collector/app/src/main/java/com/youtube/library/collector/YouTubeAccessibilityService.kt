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

    private val captureRunnable = Runnable {
        captureCurrentYouTubeTree(pendingEventType)
        pendingEventType = null
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        snapshotStore = LocalSnapshotStore(this)

        serviceInfo = serviceInfo.apply {
            packageNames = arrayOf(YOUTUBE_PACKAGE)
            eventTypes = AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED or
                AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED or
                AccessibilityEvent.TYPE_VIEW_SCROLLED
            feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC
            notificationTimeout = 750
            flags = flags or AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS
        }
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event?.packageName?.toString() != YOUTUBE_PACKAGE) return
        val prefs = getSharedPreferences(MainActivity.PREFS, MODE_PRIVATE)
        if (!prefs.getBoolean(MainActivity.KEY_DISCLOSURE_ACCEPTED, false)) return
        if (prefs.getBoolean(MainActivity.KEY_PAUSED, false)) return

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
        snapshotStore.appendIfAllowed(
            AccessibilitySnapshot(
                capturedAt = Instant.now().toString(),
                eventType = eventType,
                surfaceGuess = surface,
                treeSignature = signature,
                nodes = nodes
            )
        )
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
        private const val CAPTURE_DEBOUNCE_MS = 1_500L
    }
}
