"""
Unit tests for Module 6: Automated Feedback Intelligence Engine.
"""
import pytest
from backend.modules.module6_feedback.analyzer import FeedbackAnalyzer

def test_sentiment_analysis():
    analyzer = FeedbackAnalyzer()

    pos_res = analyzer.analyze_sentiment("The PyTorch hands-on session was amazing and very informative!")
    assert pos_res["sentiment"] == "positive"
    assert pos_res["score"] > 0

    neg_res = analyzer.analyze_sentiment("The room was crowded, projector had an issue and AC was broken.")
    assert neg_res["sentiment"] == "negative"
    assert neg_res["score"] < 0

def test_thematic_detection():
    analyzer = FeedbackAnalyzer()

    themes_infra = analyzer.detect_themes("The AC was off and sound in the audi was too low.")
    assert "venue" in themes_infra

    themes_food = analyzer.detect_themes("Loved the lunch boxes and tea refreshments.")
    assert "hospitality" in themes_food

def test_batch_feedback_aggregation():
    analyzer = FeedbackAnalyzer()
    sample_comments = [
        {"id": 1, "comment": "Great session, learned a lot from Dr. Vartika!", "rating": 5},
        {"id": 2, "comment": "Food was delayed and water was not available.", "rating": 2},
        {"id": 3, "comment": "Excellent coding contest and well organized.", "rating": 5},
        {"id": 4, "comment": "Projector screen was blurry in the seminar hall.", "rating": 2}
    ]

    report = analyzer.analyze_batch(sample_comments)
    assert report["total_feedbacks"] == 4
    assert report["sentiment_distribution"]["positive"] == 2
    assert report["sentiment_distribution"]["negative"] == 2
    assert len(report["top_strengths"]) >= 1
    assert len(report["top_concerns"]) >= 1
    assert "venue" in report["theme_counts"]
    assert "hospitality" in report["theme_counts"]
