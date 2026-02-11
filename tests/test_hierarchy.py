
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.services.trace_service import TraceService

os.environ["TRACE_MOCK"] = "1"

def test_assign_parent_fallback():
    service = TraceService()
    
    locations = [
        {"id": "Tianjian Sect", "scope": "world", "kind": "sect", "description": "A big sect."},
        {"id": "Tianjian Sect Side Hall", "scope": "world", "kind": "hall", "description": "A hall."},
        {"id": "Side Hall", "scope": "world", "kind": "hall", "description": "Located in Tianjian Sect.", "evidence": "位于Tianjian Sect"},
        {"id": "Bedroom", "scope": "world", "kind": "room", "description": "A quiet room."},
        {"id": "Kingdom", "scope": "world", "kind": "country", "description": "The big kingdom."},
    ]
    
    context_map = {
        "Bedroom": {"related_locations": ["Tianjian Sect"]},
        "Tianjian Sect": {"related_locations": ["Kingdom"]}
    }
    
    alias_to_id = {}
    
    print("Before:", [(l["id"], l.get("parent_id"), l.get("scope")) for l in locations])
    
    service._assign_parent_fallback(locations, context_map, alias_to_id)
    
    print("After:", [(l["id"], l.get("parent_id"), l.get("scope")) for l in locations])
    
    # Assertions
    loc_map = {l["id"]: l for l in locations}
    
    # 1. Name Containment
    assert loc_map["Tianjian Sect Side Hall"]["parent_id"] == "Tianjian Sect"
    assert loc_map["Tianjian Sect Side Hall"]["scope"] == "sub"
    
    # 2. Evidence
    assert loc_map["Side Hall"]["parent_id"] == "Tianjian Sect"
    assert loc_map["Side Hall"]["scope"] == "sub"
    
    # 3. Dangling
    assert loc_map["Bedroom"]["parent_id"] == "Tianjian Sect"
    assert loc_map["Bedroom"]["scope"] == "sub"
    
    # 4. Rank Check (Sect shouldn't easily go into Kingdom without strong evidence)
    assert loc_map["Tianjian Sect"].get("parent_id") is None
    
    print("All tests passed!")

def test_force_include_parents():
    service = TraceService()
    
    # Setup: 
    # - "Main City" (Rank 2) is a parent
    # - "Inn" (Rank 1) is a child of "Main City"
    # - "Inn" is selected for the map (e.g. has place_type != uncertain)
    # - "Main City" is initially EXCLUDED (e.g. marked as uncertain or filtered out)
    
    locations = [
        {"id": "Main City", "place_type": "uncertain", "scope": "world", "kind": "city"}, # Initially filtered out
        {"id": "Inn", "place_type": "fictional", "scope": "sub", "kind": "room", "parent_id": "Main City"}, # Selected
    ]
    
    # Execute _build_fictional_map logic part (mocking the function logic)
    # Since we can't easily mock the whole function, we test the logic block directly or call the function if possible.
    # _build_fictional_map is complex, let's just create a small wrapper or copy the logic to test it.
    
    # Or better, we can actually call _build_fictional_map with minimal data.
    tracks = []
    result = service._build_fictional_map(locations, tracks, events=[])
    
    # Result should include "Main City" because "Inn" needs it
    assert result is not None
    node_ids = {n["location_id"] for n in result["nodes"]}
    
    print("Nodes in map:", node_ids)
    assert "Main City" in node_ids
    assert "Inn" not in node_ids # Inn should be in sub_map of Main City, not top level
    
    # Check if Main City has sub_map
    main_city_node = next(n for n in result["nodes"] if n["location_id"] == "Main City")
    assert main_city_node["has_sub_map"] is True
    sub_nodes = {n["id"] for n in main_city_node["sub_map"]["nodes"]}
    assert "Inn" in sub_nodes

def test_flatten_nested_children_into_world_anchor():
    service = TraceService()

    locations = [
        {"id": "City", "place_type": "fictional", "scope": "world", "kind": "city"},
        {"id": "District", "place_type": "fictional", "scope": "sub", "kind": "courtyard", "parent_id": "City"},
        {"id": "Room", "place_type": "fictional", "scope": "sub", "kind": "room", "parent_id": "District"},
    ]

    result = service._build_fictional_map(locations, tracks=[], events=[])
    assert result is not None
    city_node = next(n for n in result["nodes"] if n["location_id"] == "City")
    assert city_node.get("has_sub_map") is True
    sub_ids = {n["id"] for n in city_node["sub_map"]["nodes"]}
    assert "District" in sub_ids
    assert "Room" in sub_ids

def test_break_parent_cycle():
    service = TraceService()

    locations = [
        {"id": "A", "place_type": "fictional", "scope": "world", "kind": "room", "parent_id": "B"},
        {"id": "B", "place_type": "fictional", "scope": "world", "kind": "room", "parent_id": "A"},
    ]

    result = service._build_fictional_map(locations, tracks=[], events=[])
    assert result is not None
    node_ids = {n["location_id"] for n in result["nodes"]}
    assert "A" in node_ids
    assert "B" in node_ids

def test_rank1_cluster_can_form_submap():
    service = TraceService()

    locations = [
        {"id": "A", "place_type": "fictional", "scope": None, "kind": "room"},
        {"id": "B", "place_type": "fictional", "scope": None, "kind": "room"},
        {"id": "C", "place_type": "fictional", "scope": None, "kind": "room"},
    ]
    tracks = [{
        "character": "X",
        "segments": [
            {"from_location": "A", "to_location": "B", "evidence": ""},
            {"from_location": "B", "to_location": "C", "evidence": ""},
            {"from_location": "B", "to_location": "A", "evidence": ""},
        ]
    }]

    result = service._build_fictional_map(locations, tracks=tracks, events=[])
    assert result is not None
    world_ids = {n["location_id"] for n in result["nodes"]}
    assert len(world_ids) >= 1
    any_has_sub = any(n.get("has_sub_map") for n in result["nodes"])
    assert any_has_sub

if __name__ == "__main__":
    test_assign_parent_fallback()
    test_force_include_parents()
    test_flatten_nested_children_into_world_anchor()
    test_break_parent_cycle()
    test_rank1_cluster_can_form_submap()
