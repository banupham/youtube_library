package com.youtube.library.collector

import org.json.JSONArray
import org.json.JSONObject

data class NodeRecord(
    val depth: Int,
    val text: String?,
    val contentDescription: String?,
    val viewId: String?,
    val className: String,
    val clickable: Boolean,
    val selected: Boolean,
    val scrollable: Boolean,
    val childCount: Int,
    val left: Int,
    val top: Int,
    val right: Int,
    val bottom: Int
) {
    fun searchableText(): String = listOfNotNull(text, contentDescription, viewId)
        .joinToString(" ")
        .lowercase()

    fun toJson(): JSONObject = JSONObject().apply {
        put("depth", depth)
        put("text", text ?: JSONObject.NULL)
        put("content_description", contentDescription ?: JSONObject.NULL)
        put("view_id", viewId ?: JSONObject.NULL)
        put("class_name", className)
        put("clickable", clickable)
        put("selected", selected)
        put("scrollable", scrollable)
        put("child_count", childCount)
        put("bounds", JSONObject().apply {
            put("left", left)
            put("top", top)
            put("right", right)
            put("bottom", bottom)
        })
    }
}

data class SurfaceGuess(
    val surface: String,
    val confidence: Double,
    val evidence: List<String>
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("surface", surface)
        put("confidence", confidence)
        put("evidence", JSONArray(evidence))
    }
}

data class AccessibilitySnapshot(
    val capturedAt: String,
    val eventType: Int?,
    val surfaceGuess: SurfaceGuess,
    val treeSignature: String,
    val nodes: List<NodeRecord>
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("schema_version", "1.0.0")
        put("platform", "android")
        put("source_package", YouTubeAccessibilityService.YOUTUBE_PACKAGE)
        put("captured_at", capturedAt)
        put("extraction_mode", "android_accessibility_node_tree_read_only")
        put("event_type", eventType ?: JSONObject.NULL)
        put("surface_guess", surfaceGuess.toJson())
        put("tree_signature", treeSignature)
        put("node_count", nodes.size)
        put("nodes", JSONArray().apply { nodes.forEach { put(it.toJson()) } })
    }
}
