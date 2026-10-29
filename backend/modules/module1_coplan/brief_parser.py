"""
Module 1: AI Event Planning Copilot - Event Brief Parser & Adaptive Intake Engine.
Parses natural language event briefs, extracts structured operational requirements,
and prompts clarifying questions when critical campus details are missing.
"""

import re
from typing import Dict, Any, List

def adaptive_intake(raw_text: str) -> Dict[str, Any]:
    """
    Analyzes an organizer's brief to identify missing parameters.
    Returns completeness status and targeted clarification questions.
    """
    text_lower = raw_text.lower()
    missing_fields = []
    clarification_questions = []

    # Check for attendance / headcount
    headcount_match = re.search(r'(\d+)\s*(?:students?|participants?|attendees?|people|members?)', text_lower)
    attendance = int(headcount_match.group(1)) if headcount_match else None
    if not attendance:
        # Also check for simple 3-digit numbers
        num_matches = re.findall(r'\b\d{2,4}\b', text_lower)
        if num_matches:
            attendance = int(num_matches[0])
        else:
            missing_fields.append("headcount")
            clarification_questions.append("What is the expected student/participant attendance?")

    # Check for date / time / duration
    has_timing = any(k in text_lower for k in [
        "day", "hour", "morning", "afternoon", "friday", "monday", "tuesday", "wednesday",
        "thursday", "saturday", "sunday", "tomorrow", "next week", "december", "nov", "oct", "202"
    ])
    if not has_timing:
        missing_fields.append("timeline")
        clarification_questions.append("When will the event take place (target date and start/end time)?")

    # Check for event type
    event_type = "general"
    if any(k in text_lower for k in ["hackathon", "coding", "hack", "ctf", "sprint"]):
        event_type = "hackathon"
    elif any(k in text_lower for k in ["workshop", "bootcamp", "training", "hands-on"]):
        event_type = "workshop"
    elif any(k in text_lower for k in ["cultural", "dance", "drama", "music", "fest"]):
        event_type = "cultural"
    elif any(k in text_lower for k in ["seminar", "talk", "panel", "lecture", "keynote"]):
        event_type = "seminar"
    else:
        if len(text_lower.split()) < 7:
            missing_fields.append("event_nature")
            clarification_questions.append("Is this a hands-on technical workshop, hackathon, academic seminar, or cultural fest?")

    is_complete = len(missing_fields) == 0

    return {
        "is_complete": is_complete,
        "event_type": event_type,
        "extracted_headcount": attendance,
        "missing_fields": missing_fields,
        "clarification_questions": clarification_questions,
        "recommendation": "Ready to execute venue lock and logistics requisition." if is_complete else "Need organizer clarification before reserving campus inventory."
    }

def parse_event_brief(raw_text: str) -> Dict[str, Any]:
    """
    Parses unstructured text into a fully qualified campus event specification.
    """
    intake = adaptive_intake(raw_text)
    text_lower = raw_text.lower()

    # Determine venue requirement
    venue_type = "Seminar Hall"
    attendance = intake.get("extracted_headcount") or 100
    if attendance > 200:
        venue_type = "Main Auditorium"
    elif "lab" in text_lower or intake["event_type"] in ["hackathon", "workshop"]:
        venue_type = "AI Specialized Lab / Computing Lab"

    # Logistics detection
    logistics = []
    if "mic" in text_lower:
        logistics.append("Cordless Handheld / Collar Microphones")
    if "sound" in text_lower or "audio" in text_lower:
        logistics.append("JBL High-Power Audio System")
    if "light" in text_lower:
        logistics.append("Stage LED Par Lights")
    if "strip" in text_lower or "power" in text_lower or "extension" in text_lower:
        logistics.append("Extension Power Strips")
    if "lunch" in text_lower or "refreshment" in text_lower:
        logistics.append("Refreshment / Lunch Packet Quota")
    if "bus" in text_lower or "shuttle" in text_lower:
        logistics.append("Campus Shuttle Transport")

    # Suggested Title
    title = "Galgotias Campus Innovation Event"
    if "hackathon" in text_lower:
        title = "Galgotias AI & Innovation Hackathon"
    elif "dance" in text_lower:
        title = "Galgotias Annual Cultural & Dance Showcase"
    elif "workshop" in text_lower or "bootcamp" in text_lower:
        title = "Technical Skill-Building Hands-On Workshop"

    return {
        "title": title,
        "event_type": intake["event_type"],
        "headcount": attendance,
        "venue_needed": venue_type,
        "logistics": logistics,
        "is_complete": intake["is_complete"],
        "clarification_questions": intake["clarification_questions"]
    }
