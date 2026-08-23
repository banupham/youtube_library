package com.youtube.library.collector

object SurfaceDetector {
    private data class Rule(val surface: String, val tokens: List<String>, val weight: Double)

    private val rules = listOf(
        Rule("watch", listOf("comments", "bình luận", "share", "chia sẻ", "save", "lưu", "autoplay", "tự động phát"), 0.16),
        Rule("subscriptions", listOf("subscriptions", "kênh đăng ký", "đăng ký"), 0.34),
        Rule("home", listOf("home", "trang chủ"), 0.34),
        Rule("shorts", listOf("shorts"), 0.42),
        Rule("search", listOf("search", "tìm kiếm"), 0.38)
    )

    fun guess(nodes: List<NodeRecord>): SurfaceGuess {
        if (nodes.isEmpty()) return SurfaceGuess("unknown", 0.0, emptyList())

        val score = mutableMapOf<String, Double>()
        val evidence = mutableMapOf<String, MutableList<String>>()

        for (node in nodes) {
            val haystack = node.searchableText()
            if (haystack.isBlank()) continue

            for (rule in rules) {
                for (token in rule.tokens) {
                    if (!haystack.contains(token)) continue
                    var contribution = rule.weight
                    if (node.selected) contribution += 0.26
                    if (node.viewId?.contains("pivot", ignoreCase = true) == true) contribution += 0.08
                    score[rule.surface] = (score[rule.surface] ?: 0.0) + contribution
                    evidence.getOrPut(rule.surface) { mutableListOf() }
                        .add("$token${if (node.selected) "[selected]" else ""}")
                }
            }

            val viewId = node.viewId.orEmpty().lowercase()
            if (viewId.contains("player") || viewId.contains("watch")) {
                score["watch"] = (score["watch"] ?: 0.0) + 0.24
                evidence.getOrPut("watch") { mutableListOf() }.add("view_id:$viewId")
            }
        }

        val best = score.maxByOrNull { it.value } ?: return SurfaceGuess("unknown", 0.15, emptyList())
        val runnerUp = score.filterKeys { it != best.key }.maxOfOrNull { it.value } ?: 0.0
        val margin = (best.value - runnerUp).coerceAtLeast(0.0)
        val confidence = (0.30 + best.value * 0.35 + margin * 0.25).coerceIn(0.15, 0.95)

        return SurfaceGuess(
            surface = best.key,
            confidence = confidence,
            evidence = evidence[best.key].orEmpty().distinct().take(12)
        )
    }
}
