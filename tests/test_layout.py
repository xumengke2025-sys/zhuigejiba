
import pytest
import sys
import os

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from app.services.trace_service import TraceService

def test_layout_directions():
    service = TraceService()
    width = 1000
    height = 1000
    
    # 1. Test North Of (A is North of B -> A.y < B.y)
    nodes = ["A", "B"]
    constraints = [{"a": "A", "b": "B", "type": "north_of"}]
    layout = service._layout_nodes(nodes, constraints, width, height)
    assert layout["A"]["y"] < layout["B"]["y"], "A should be north of (above) B"
    
    # 2. Test South Of (A is South of B -> A.y > B.y)
    nodes = ["A", "B"]
    constraints = [{"a": "A", "b": "B", "type": "south_of"}]
    layout = service._layout_nodes(nodes, constraints, width, height)
    assert layout["A"]["y"] > layout["B"]["y"], "A should be south of (below) B"

    # 3. Test East Of (A is East of B -> A.x > B.x)
    nodes = ["A", "B"]
    constraints = [{"a": "A", "b": "B", "type": "east_of"}]
    layout = service._layout_nodes(nodes, constraints, width, height)
    assert layout["A"]["x"] > layout["B"]["x"], "A should be east of (right of) B"

    # 4. Test West Of (A is West of B -> A.x < B.x)
    nodes = ["A", "B"]
    constraints = [{"a": "A", "b": "B", "type": "west_of"}]
    layout = service._layout_nodes(nodes, constraints, width, height)
    assert layout["A"]["x"] < layout["B"]["x"], "A should be west of (left of) B"

def test_layout_chain():
    service = TraceService()
    width = 1000
    height = 1000
    
    # A North of B, B North of C -> A < B < C (in Y)
    nodes = ["A", "B", "C"]
    constraints = [
        {"a": "A", "b": "B", "type": "north_of"},
        {"a": "B", "b": "C", "type": "north_of"}
    ]
    layout = service._layout_nodes(nodes, constraints, width, height)
    
    print(f"Chain Layout: A={layout['A']['y']}, B={layout['B']['y']}, C={layout['C']['y']}")
    assert layout["A"]["y"] < layout["B"]["y"]
    assert layout["B"]["y"] < layout["C"]["y"]
