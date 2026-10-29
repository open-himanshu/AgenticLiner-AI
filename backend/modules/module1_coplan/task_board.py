"""
Module 1: AI Event Planning Copilot - Countdown Task Board & Checklist Engine.
Generates structured countdown timeline tasks (D-7, D-3, D-1, D-Day) with assignee roles.
"""

from typing import List, Dict, Any

DEFAULT_CHECKLISTS = {
    "hackathon": [
        {"day": "D-7 (1 Week Prior)", "task": "Lock Auditorium and AI Specialized Labs with Facility Head", "role": "Faculty Coordinator", "completed": True},
        {"day": "D-7 (1 Week Prior)", "task": "Deploy online student registration portal and waitlist rules", "role": "Tech Lead (Himanshu)", "completed": True},
        {"day": "D-3 (3 Days Prior)", "task": "Print official campus standees, banners, and participant badges", "role": "Design Lead (Diya)", "completed": True},
        {"day": "D-3 (3 Days Prior)", "task": "Reserve 35 extension spike power strips for student coding tables", "role": "Logistics Lead (Ashish)", "completed": True},
        {"day": "D-1 (Eve of Event)", "task": "Acoustics & Mic sound test in Main Auditorium A", "role": "Student Volunteer", "completed": False},
        {"day": "D-1 (Eve of Event)", "task": "Dispatch reminder announcements with gate entry QR instructions", "role": "AI Comm Agent", "completed": False},
        {"day": "D-Day (08:30 AM)", "task": "Open Registration & Check-in Desk; distribute refreshments", "role": "Volunteer Desk", "completed": False},
        {"day": "D-Day (09:30 AM)", "task": "Commence Keynote address and start hackathon problem statements", "role": "Dean & Faculty", "completed": False},
    ],
    "cultural": [
        {"day": "D-7 (1 Week Prior)", "task": "Reserve Main Auditorium stage and rehearsal green rooms", "role": "Faculty Coordinator", "completed": True},
        {"day": "D-3 (3 Days Prior)", "task": "Acoustics & stage lighting equipment test (JBL Sound, Stage LED Pars)", "role": "Stage Lead", "completed": True},
        {"day": "D-1 (Eve of Event)", "task": "Stage floor marking and performer sequence dry run", "role": "Anchor Team", "completed": False},
        {"day": "D-Day (04:00 PM)", "task": "Open gate check-in for audience and sound check", "role": "Student Volunteers", "completed": False},
    ],
    "general": [
        {"day": "D-7 (1 Week Prior)", "task": "Reserve seminar hall and invite key guest speakers", "role": "Coordinator", "completed": True},
        {"day": "D-3 (3 Days Prior)", "task": "Confirm catering buffer and print attendance QR codes", "role": "Logistics", "completed": True},
        {"day": "D-1 (Eve of Event)", "task": "Check projector, slide clicker, and collar microphones", "role": "Tech Support", "completed": False},
        {"day": "D-Day (09:00 AM)", "task": "Gate check-in and seminar commencement", "role": "Volunteers", "completed": False},
    ]
}

def get_event_task_board(event_type: str = "hackathon") -> List[Dict[str, Any]]:
    """Returns the milestone checklist for the given event type."""
    ev_type = event_type.lower()
    if "hack" in ev_type:
        return DEFAULT_CHECKLISTS["hackathon"]
    elif "dance" in ev_type or "cultural" in ev_type:
        return DEFAULT_CHECKLISTS["cultural"]
    return DEFAULT_CHECKLISTS["general"]
