"""
Module 6: Automated Feedback Intelligence Engine
Implements:
1. Sentiment analysis (Positive, Neutral, Negative)
2. Thematic classification (Venue/Infra, Speaker/Content, Food/Hospitality, Organization)
3. Actionable executive insights summary (Strengths, Weaknesses, Improvements)
"""

from typing import List, Dict, Any, Optional
import re

THEME_KEYWORDS = {
    "venue": ["room", "audi", "hall", "seat", "ac", "air conditioning", "projector", "screen", "mic", "sound", "speaker system", "stage", "lighting"],
    "content": ["topic", "workshop", "pytorch", "code", "lecture", "presentation", "hands-on", "learning", "knowledge", "session", "tutorial", "depth"],
    "hospitality": ["food", "lunch", "refreshment", "snack", "tea", "coffee", "water", "juice", "buffet", "meal"],
    "organization": ["time", "delay", "registration", "queue", "volunteer", "management", "coordinator", "schedule", "certificate", "start", "end"]
}

POSITIVE_WORDS = {
    "great", "excellent", "awesome", "good", "loved", "enjoyed", "smooth", "informative", "helpful", "amazing",
    "clear", "insightful", "best", "satisfied", "well", "fantastic", "superb", "brilliant", "outstanding", "impressive"
}

NEGATIVE_WORDS = {
    "bad", "terrible", "poor", "issue", "problem", "broken", "delay", "delayed", "late", "crowded", "suffocating",
    "inaudible", "cold", "hot", "waste", "disappointed", "low", "worst", "mess", "slow", "fail", "failed", "shortage",
    "blurry", "unclear", "noisy", "glitch", "confusing", "horrible", "difficult"
}

class FeedbackAnalyzer:
    def __init__(self):
        pass

    def analyze_sentiment(self, text: str, rating: Optional[int] = None) -> Dict[str, Any]:
        """Classifies text sentiment into positive, neutral, or negative."""
        words = set(re.findall(r'\b[a-z]+\b', text.lower()))
        pos_hits = len(words.intersection(POSITIVE_WORDS))
        neg_hits = len(words.intersection(NEGATIVE_WORDS))

        score = pos_hits - neg_hits
        if rating is not None:
            if rating >= 4:
                score += 1
            elif rating <= 2:
                score -= 1

        if score > 0:
            sentiment = "positive"
        elif score < 0:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        normalized_score = max(-1.0, min(1.0, score / max(1, (pos_hits + neg_hits + (1 if rating else 0)))))

        return {
            "sentiment": sentiment,
            "score": float(round(normalized_score, 2)),
            "positive_hits": pos_hits,
            "negative_hits": neg_hits
        }

    def detect_themes(self, text: str) -> List[str]:
        """Detects operational event themes mentioned in the feedback comment."""
        text_lower = text.lower()
        matched_themes = []
        for theme, kws in THEME_KEYWORDS.items():
            for kw in kws:
                if kw in text_lower:
                    matched_themes.append(theme)
                    break
        return matched_themes or ["general"]

    def analyze_batch(self, comments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyzes a batch of feedback comments and compiles comprehensive metrics:
        - Sentiment distribution
        - Theme breakdowns
        - Key strengths & critical concerns
        """
        total = len(comments)
        if total == 0:
            return {
                "total_feedbacks": 0,
                "sentiment_distribution": {"positive": 0, "neutral": 0, "negative": 0},
                "theme_counts": {},
                "strengths": [],
                "concerns": []
            }

        sent_counts = {"positive": 0, "neutral": 0, "negative": 0}
        theme_counts = {}
        analyzed_items = []

        for c in comments:
            raw_text = c.get("comment", "")
            rating = c.get("rating")
            sent = self.analyze_sentiment(raw_text, rating=rating)
            themes = self.detect_themes(raw_text)

            sent_counts[sent["sentiment"]] += 1
            for t in themes:
                theme_counts[t] = theme_counts.get(t, 0) + 1

            analyzed_items.append({
                "id": c.get("id"),
                "rating": c.get("rating"),
                "comment": raw_text,
                "sentiment": sent["sentiment"],
                "score": sent["score"],
                "themes": themes
            })

        # Synthesize Strengths and Concerns
        strengths = []
        concerns = []

        for item in analyzed_items:
            if item["sentiment"] == "positive" and item.get("rating", 3) >= 4:
                strengths.append(item["comment"])
            elif item["sentiment"] == "negative" or item.get("rating", 3) <= 2:
                concerns.append(item["comment"])

        return {
            "total_feedbacks": total,
            "sentiment_distribution": sent_counts,
            "positive_ratio": round(sent_counts["positive"] / total, 2),
            "theme_counts": theme_counts,
            "top_strengths": strengths[:4],
            "top_concerns": concerns[:4],
            "analyzed_items": analyzed_items
        }
