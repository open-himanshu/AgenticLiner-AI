"""
Module 4: Personalized Participant Experience & Networking Engine
Implements:
1. TF-IDF + Cosine Similarity matching for session recommendations.
2. Clash-pruning: ensures recommended agenda has no overlapping sessions.
3. Peer & Speaker Networking recommendations.
4. Cold-start popularity fallback.
"""

import json
from typing import List, Dict, Any, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from backend.core.database.connection import get_connection

class ParticipantExperienceEngine:
    def __init__(self):
        pass

    def recommend_sessions(self, participant_interests: List[str], sessions: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Calculates content similarity between student's interests and available sessions.
        Ensures the final recommended agenda has NO clashing time slots.
        """
        if not sessions:
            return []

        # Cold start fallback if student provided no interests
        if not participant_interests:
            sorted_by_attendance = sorted(sessions, key=lambda s: s.get("expected_attendance", 0), reverse=True)
            return sorted_by_attendance[:top_k]

        # Prepare corpus: participant query vs all session texts
        query_text = " ".join(participant_interests)
        corpus = [query_text]
        
        session_docs = []
        for s in sessions:
            doc = f"{s.get('title', '')} {s.get('track', '')} {s.get('description', '')}"
            session_docs.append(doc)
            corpus.append(doc)

        vectorizer = TfidfVectorizer(stop_words="english")
        tfidf_matrix = vectorizer.fit_transform(corpus)

        query_vec = tfidf_matrix[0:1]
        session_vecs = tfidf_matrix[1:]

        similarities = cosine_similarity(query_vec, session_vecs).flatten()

        # Pair sessions with similarity scores
        scored_sessions = []
        for idx, score in enumerate(similarities):
            sess = dict(sessions[idx])
            sess["match_score"] = float(round(score, 4))
            scored_sessions.append(sess)

        # Sort descending by match score
        scored_sessions.sort(key=lambda s: s["match_score"], reverse=True)

        # Clash-pruning: Do not recommend two sessions that happen at the exact same start_time or slot
        recommended = []
        occupied_slots = set()

        for s in scored_sessions:
            slot_id = None
            for key in ("start_time", "slot_index", "slot_time"):
                if key in s and s[key] is not None:
                    slot_id = s[key]
                    break

            if slot_id is not None:
                if slot_id in occupied_slots:
                    continue # Skip clashing session to give feasible agenda
                occupied_slots.add(slot_id)
            recommended.append(s)
            if len(recommended) >= top_k:
                break

        return recommended

    def recommend_networking(self, student_id: str, conn=None) -> Dict[str, Any]:
        """
        Recommends peers (students) and speakers with matching academic interests.
        """
        close_conn = False
        if conn is None:
            conn = get_connection()
            close_conn = True

        try:
            cur = conn.cursor()
            cur.execute("SELECT id, name, department, interests FROM students WHERE id = ?", (student_id,))
            target = cur.fetchone()
            if not target:
                return {"peers": [], "speakers": []}

            target_interests = json.loads(target["interests"]) if target["interests"] else []
            target_str = " ".join(target_interests) + " " + target["department"]

            # 1. Fetch other students
            cur.execute("SELECT id, name, department, year, interests FROM students WHERE id != ? LIMIT 30", (student_id,))
            other_students = [dict(r) for r in cur.fetchall()]

            peer_recs = []
            if other_students:
                student_docs = [target_str]
                for s in other_students:
                    ints = json.loads(s["interests"]) if s.get("interests") else []
                    student_docs.append(" ".join(ints) + " " + s["department"])

                vec = TfidfVectorizer(stop_words="english")
                mat = vec.fit_transform(student_docs)
                sims = cosine_similarity(mat[0:1], mat[1:]).flatten()

                for idx, sim in enumerate(sims):
                    if sim > 0.1:
                        s_data = dict(other_students[idx])
                        s_data["match_score"] = float(round(sim, 3))
                        peer_recs.append(s_data)

                peer_recs.sort(key=lambda x: x["match_score"], reverse=True)

            # 2. Match with speakers
            cur.execute("SELECT id, name, department, topics, email FROM speakers")
            speakers = [dict(r) for r in cur.fetchall()]
            speaker_recs = []
            if speakers:
                spk_docs = [target_str]
                for sp in speakers:
                    spk_docs.append(sp.get("topics", "") + " " + sp.get("department", ""))

                vec_spk = TfidfVectorizer(stop_words="english")
                mat_spk = vec_spk.fit_transform(spk_docs)
                sims_spk = cosine_similarity(mat_spk[0:1], mat_spk[1:]).flatten()

                for idx, sim in enumerate(sims_spk):
                    if sim > 0.05:
                        sp_data = dict(speakers[idx])
                        sp_data["match_score"] = float(round(sim, 3))
                        speaker_recs.append(sp_data)

                speaker_recs.sort(key=lambda x: x["match_score"], reverse=True)

            return {
                "student_id": student_id,
                "peer_matches": peer_recs[:4],
                "mentor_matches": speaker_recs[:3]
            }
        finally:
            if close_conn:
                conn.close()
