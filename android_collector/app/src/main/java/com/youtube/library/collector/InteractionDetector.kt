package com.youtube.library.collector

import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

data class InteractionDetection(
    val eventType: String,
    val score: Double,
    val confidence: Double,
    val eventClass: String
)

object InteractionDetector {
    fun detect(event: AccessibilityEvent): InteractionDetection? {
        if (event.eventType != AccessibilityEvent.TYPE_VIEW_CLICKED) return null
        val source = event.source
        val label = buildLabel(event, source).lowercase()
        if (label.isBlank()) return null

        val className = source?.className?.toString().orEmpty().ifBlank { event.className?.toString().orEmpty() }

        val isDislike = label.contains("dislike") || label.contains("không thích")
        if (isDislike) {
            val selected = source?.isSelected == true || source?.isCheckedCompat() == true
            return InteractionDetection(
                eventType = if (selected) "dislike" else "undislike",
                score = if (selected) -1.0 else 0.0,
                confidence = 0.75,
                eventClass = className
            )
        }

        val isLike = Regex("(^|\\s)(like|thích)(\\s|$|video)").containsMatchIn(label)
        if (isLike) {
            val selected = source?.isSelected == true || source?.isCheckedCompat() == true
            return InteractionDetection(
                eventType = if (selected) "like" else "unlike",
                score = if (selected) 1.0 else -1.0,
                confidence = 0.75,
                eventClass = className
            )
        }

        val commentAction = listOf(
            "send comment", "post comment", "submit comment", "gửi bình luận", "đăng bình luận",
            "comment submit", "bình luận"
        ).any { label.contains(it) }
        if (commentAction) {
            return InteractionDetection(
                eventType = "comment_submit",
                score = 1.0,
                confidence = if (label.contains("gửi") || label.contains("send") || label.contains("post")) 0.9 else 0.6,
                eventClass = className
            )
        }
        return null
    }

    private fun buildLabel(event: AccessibilityEvent, source: AccessibilityNodeInfo?): String {
        val values = mutableListOf<String>()
        event.contentDescription?.toString()?.let(values::add)
        event.text.mapNotNullTo(values) { it?.toString() }
        source?.contentDescription?.toString()?.let(values::add)
        source?.text?.toString()?.let(values::add)
        source?.viewIdResourceName?.let(values::add)
        source?.parent?.let { parent ->
            parent.contentDescription?.toString()?.let(values::add)
            parent.text?.toString()?.let(values::add)
            parent.viewIdResourceName?.let(values::add)
        }
        return values.joinToString(" ").replace(Regex("\\s+"), " ").trim().take(500)
    }

    // AccessibilityNodeInfo does not expose one stable selected-state contract
    // across all YouTube UI implementations. This helper intentionally stays
    // conservative and does not perform any action on the node.
    private fun AccessibilityNodeInfo.isCheckedCompat(): Boolean = try {
        isCheckable && isChecked
    } catch (_: Exception) {
        false
    }
}
