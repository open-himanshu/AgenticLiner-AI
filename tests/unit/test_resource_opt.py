"""
Unit tests for Module 3: Resource Optimizer & Recommendation Engine (Campus Edition).
"""
import pytest
from backend.modules.module3_resource_opt.engine import ResourceOptimizer

def test_resource_estimation():
    optimizer = ResourceOptimizer()
    res = optimizer.estimate_resources(headcount=150, duration_hours=6.0, event_type="hackathon")
    
    needs = res["predicted_needs"]
    assert needs["rooms"] >= 1
    assert needs["volunteers"] >= 5
    assert needs["food_packs"] >= 150
    assert needs["extension_boards"] >= 6
    assert needs["first_aid_kits"] >= 1

def test_smart_recommendations():
    optimizer = ResourceOptimizer()
    recs = optimizer.get_smart_recommendations("dance and cultural event", headcount=200)
    
    rec_names = [r["item_name"] for r in recs]
    assert any("Sound" in name for name in rec_names)
    assert any("Lights" in name for name in rec_names)
    assert any("Lunch Box" in name or "Snack Box" in name for name in rec_names)

def test_campus_requisition_plan():
    from backend.core.database.connection import execute_query
    execute_query("INSERT OR IGNORE INTO resources (id, name, category, stock, allocated_stock, unit) VALUES ('res_mic_cordless', 'Cordless Mics', 'equipment', 10, 0, 'unit')")
    execute_query("INSERT OR IGNORE INTO resources (id, name, category, stock, allocated_stock, unit) VALUES ('res_food_lunch', 'Packed Lunch', 'food', 500, 0, 'pack')")
    optimizer = ResourceOptimizer()
    preds = optimizer.estimate_resources(headcount=120, duration_hours=4.0, event_type="seminar")
    plan = optimizer.build_requisition_plan(preds)
    
    assert len(plan["requisitions"]) > 0
    assert plan["total_items_requested"] > 0
    assert plan["status"] == "ready_for_dispatch"
