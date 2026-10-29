"""
Unit tests for Module 4: Personalized Participant Experience & Networking Engine.
"""
import pytest
from backend.modules.module4_participant_xp.recommender import ParticipantExperienceEngine

def test_recommend_sessions_relevance_and_clash_pruning():
    engine = ParticipantExperienceEngine()
    
    interests = ["Machine Learning", "Neural Networks", "Python"]
    sessions = [
        {"id": "sess_1", "title": "Hands-on PyTorch & Deep Learning", "track": "AI/ML", "slot_index": 0, "description": "Training neural networks in Python"},
        {"id": "sess_2", "title": "Advanced Web3 & Smart Contracts", "track": "Blockchain", "slot_index": 0, "description": "Solidity and Ethereum"}, # Clashing slot with sess_1!
        {"id": "sess_3", "title": "Machine Learning in Production", "track": "AI/ML", "slot_index": 1, "description": "Deploying ML models with FastAPI"},
        {"id": "sess_4", "title": "Intro to Figma UI/UX", "track": "Design", "slot_index": 2, "description": "Design systems and wireframing"}
    ]

    recs = engine.recommend_sessions(interests, sessions, top_k=3)
    assert len(recs) >= 2
    # The top recommendation should be the PyTorch session
    assert recs[0]["id"] == "sess_1"
    
    # Clash-pruning check: both sess_1 and sess_2 are at slot_index 0. Only sess_1 should be in recs!
    slot_indices = [r["slot_index"] for r in recs]
    assert len(slot_indices) == len(set(slot_indices)), "No overlapping slots should be recommended"

def test_cold_start_fallback():
    engine = ParticipantExperienceEngine()
    sessions = [
        {"id": "s1", "title": "Keynote", "expected_attendance": 300},
        {"id": "s2", "title": "Small Workshop", "expected_attendance": 20}
    ]
    # No interests supplied
    recs = engine.recommend_sessions([], sessions, top_k=2)
    assert recs[0]["id"] == "s1"
