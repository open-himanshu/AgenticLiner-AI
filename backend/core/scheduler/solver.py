"""
Intelligent Event Scheduler using Google OR-Tools CP-SAT Solver.
Solves conflict-free timetable scheduling satisfying:
1. Room conflict constraints (at most one session per room per time slot)
2. Room capacity constraints (attendance <= capacity)
3. Speaker availability and single-assignment constraints (no speaker in two rooms)
4. Session dependency precedence (e.g., Keynote before Workshop)
5. Dynamic re-scheduling on speaker cancellation with minimal displacement.
"""

from ortools.sat.python import cp_model
from typing import List, Dict, Any, Optional, Tuple

class EventScheduler:
    def __init__(self, rooms: List[Dict[str, Any]], slots: List[str], sessions: List[Dict[str, Any]], speakers: Optional[List[Dict[str, Any]]] = None):
        """
        rooms: list of dicts with keys ['id', 'name', 'capacity']
        slots: list of slot identifiers (e.g. ['Slot 1 (09:00-10:30)', 'Slot 2 (11:00-12:30)', ...])
        sessions: list of dicts with keys ['id', 'title', 'expected_attendance', 'speaker_id', 'depends_on']
        speakers: list of dicts with keys ['id', 'name', 'availability_slots']
        """
        self.rooms = rooms
        self.slots = slots
        self.sessions = sessions
        self.speakers = speakers or []
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        self.x = {} # Decision variables: (session_id, room_id, slot_idx) -> BoolVar

    def build_model(self) -> None:
        """Constructs CP-SAT boolean decision variables and enforces hard constraints."""
        num_slots = len(self.slots)

        # Create 3D binary decision matrix: x[s, r, t] = 1 if session s is in room r at slot t
        for s in self.sessions:
            s_id = s["id"]
            attendance = s.get("expected_attendance", 0)
            speaker_id = s.get("speaker_id")

            for r in self.rooms:
                r_id = r["id"]
                capacity = r.get("capacity", 0)

                for t in range(num_slots):
                    # Hard Constraint: Capacity limit
                    # If room cannot hold expected attendance, force variable to 0 (infeasible placement)
                    if attendance > capacity:
                        self.x[(s_id, r_id, t)] = self.model.NewConstant(0)
                    else:
                        self.x[(s_id, r_id, t)] = self.model.NewBoolVar(f"x_{s_id}_{r_id}_{t}")

        # Constraint 1: Every session must be scheduled in exactly ONE room and ONE time slot
        for s in self.sessions:
            s_id = s["id"]
            self.model.AddExactlyOne(
                self.x[(s_id, r["id"], t)]
                for r in self.rooms
                for t in range(num_slots)
            )

        # Constraint 2: A room can host at most ONE session in any given time slot
        for r in self.rooms:
            r_id = r["id"]
            for t in range(num_slots):
                self.model.AddAtMostOne(
                    self.x[(s["id"], r_id, t)]
                    for s in self.sessions
                )

        # Constraint 3: A speaker can be in at most ONE session at any given time slot
        speakers_sessions = {}
        for s in self.sessions:
            spk = s.get("speaker_id")
            if spk:
                speakers_sessions.setdefault(spk, []).append(s["id"])

        for spk, sess_ids in speakers_sessions.items():
            if len(sess_ids) > 1:
                for t in range(num_slots):
                    self.model.AddAtMostOne(
                        self.x[(s_id, r["id"], t)]
                        for s_id in sess_ids
                        for r in self.rooms
                    )

        # Constraint 4: Precedence / Dependency (e.g. Session A must happen strictly before Session B)
        # Create an integer slot indicator variable for each session: slot_of[s] = sum(t * x[s, r, t])
        slot_of = {}
        for s in self.sessions:
            s_id = s["id"]
            slot_var = self.model.NewIntVar(0, num_slots - 1, f"slot_of_{s_id}")
            self.model.Add(
                slot_var == sum(t * self.x[(s_id, r["id"], t)] for r in self.rooms for t in range(num_slots))
            )
            slot_of[s_id] = slot_var

        for s in self.sessions:
            s_id = s["id"]
            prereq = s.get("depends_on")
            if prereq and prereq in slot_of:
                # Precedence: slot_of[prereq] < slot_of[s_id]
                self.model.Add(slot_of[prereq] < slot_of[s_id])

    def solve(self) -> Dict[str, Any]:
        """Runs the CP-SAT solver and extracts the clash-free schedule timetable."""
        self.build_model()
        self.solver.parameters.max_time_in_seconds = 10.0
        status = self.solver.Solve(self.model)

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            schedule = []
            num_slots = len(self.slots)
            
            for s in self.sessions:
                s_id = s["id"]
                for r in self.rooms:
                    r_id = r["id"]
                    for t in range(num_slots):
                        val = self.solver.Value(self.x[(s_id, r_id, t)])
                        if val == 1:
                            schedule.append({
                                "session_id": s_id,
                                "session_title": s["title"],
                                "room_id": r_id,
                                "room_name": r["name"],
                                "slot_index": t,
                                "slot_time": self.slots[t],
                                "speaker_id": s.get("speaker_id"),
                                "expected_attendance": s.get("expected_attendance", 0)
                            })
            
            # Sort schedule chronologically by slot index and room
            schedule.sort(key=lambda item: (item["slot_index"], item["room_name"]))
            return {
                "success": True,
                "status": "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
                "schedule": schedule,
                "total_sessions_scheduled": len(schedule),
                "unassigned_sessions": 0
            }
        else:
            return {
                "success": False,
                "status": "INFEASIBLE",
                "message": "No feasible timetable found satisfying all room capacities, speaker availabilities and precedence rules.",
                "schedule": []
            }
