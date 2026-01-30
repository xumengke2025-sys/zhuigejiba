
import sys
import os
import random
import logging

# 添加项目根目录到 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.services.fortune_aggregator import FortuneAggregator

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_verify_and_supplement():
    print("\n=== Testing Verify and Supplement Logic ===")
    aggregator = FortuneAggregator()
    
    # 模拟数据：共识缺失，unique 过少
    # 增加维度关键词，确保 _extract_all_relevant_paragraphs 能提取到
    preprocessed_reports = [
        {"name": "填充大师1", "paragraphs": ["事业 2026年 运势一般般。"]},
        {"name": "填充大师2", "paragraphs": ["事业 2026年 运势还行。"]},
        {"name": "填充大师3", "paragraphs": ["事业 2026年 运势不错。"]},
        {"name": "填充大师4", "paragraphs": ["事业 2026年 运势很好。"]},
    ]
    
    # 构造一个空的节点列表
    nodes = []
    
    # 运行验证逻辑
    supplemented_nodes = aggregator._verify_and_supplement_nodes(nodes, 1, preprocessed_reports)
    
    # 检查结果
    # 应该至少补充 1 个共识 + 2 个 unique (补齐到3个)
    career_nodes = [n for n in supplemented_nodes if n["properties"]["dimension"] == "career"]
    
    consensus = [n for n in career_nodes if n["properties"]["type"] == "consensus"]
    unique = [n for n in career_nodes if n["properties"]["type"] == "unique"]
    variable = [n for n in career_nodes if n["properties"]["type"] == "variable"]
    
    print(f"Total Career Nodes: {len(career_nodes)}")
    print(f"Consensus: {len(consensus)}")
    print(f"Unique: {len(unique)}")
    print(f"Variable: {len(variable)}")
    
    if len(consensus) == 1:
        print("PASSED: Supplemented consensus node")
    else:
        print("FAILED: Missing consensus node")
        
    if len(unique) >= 2:
        print("PASSED: Supplemented unique nodes (to meet min count)")
    else:
        print(f"FAILED: Unique nodes count {len(unique)} < 2")
        
    # 模拟数据充足的情况
    print("\n=== Testing Sufficient Data ===")
    nodes_sufficient = []
    # 预先加入足够的节点
    for i in range(10):
        nodes_sufficient.append({
            "id": f"n{i}",
            "properties": {
                "name": f"节点{i}",
                "time": "2026年",
                "description": "描述",
                "master_name": f"大师{i}",
                "source_master": f"大师{i}",
                "type": "unique",
                "dimension": "career"
            }
        })
    # 加入一个共识
    nodes_sufficient.append({
        "id": "nc",
        "properties": {
            "name": "共识",
            "time": "2026年",
            "description": "描述",
            "master_name": "共识",
            "source_master": "共识",
            "type": "consensus",
            "dimension": "career"
        }
    })
    
    supplemented_nodes_2 = aggregator._verify_and_supplement_nodes(nodes_sufficient, 1, preprocessed_reports)
    career_nodes_2 = [n for n in supplemented_nodes_2 if n["properties"]["dimension"] == "career"]
    
    print(f"Original Count: {len(nodes_sufficient)}")
    print(f"New Count: {len(career_nodes_2)}")
    
    if len(career_nodes_2) == len(nodes_sufficient):
        print("PASSED: Did not add unnecessary nodes when count is sufficient")
    else:
        print(f"FAILED: Added nodes unnecessarily. Old: {len(nodes_sufficient)}, New: {len(career_nodes_2)}")

if __name__ == "__main__":
    test_verify_and_supplement()
