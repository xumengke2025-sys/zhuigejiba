"""
人物关系梳理服务
负责文本分块、并行提取与结果聚合
"""

import threading
import concurrent.futures
import json
import uuid
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .relationship_agents import get_extractor_prompt, get_aggregator_prompt

logger = get_logger('silverfish.relationship_service')

class RelationshipService:
    """关系梳理服务调度器"""
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()
        # 简单的内存存储，生产环境应使用 Redis
        self.sessions: Dict[str, Dict[str, Any]] = {}
        
    def _chunk_text(self, text: str, chunk_size: int = 2000, overlap: int = 400) -> List[str]:
        """
        参考“参商”优化的文本分块策略
        1. 寻找句子结束符
        2. 减小 chunk_size 以提升单次提取的召回率（对标“参商”的 1500-2000 字）
        3. 增加重叠以保持上下文连贯
        4. 优化查找效率，避免重复切片
        """
        if len(text) <= chunk_size:
            return [text] if text.strip() else []

        chunks = []
        start = 0
        text_len = len(text)
        
        separators = ['\n\n', '。', '！', '？', '.\n', '!\n', '?\n', '. ', '! ', '? ']
        
        while start < text_len:
            end = start + chunk_size
            
            # 尝试在句子边界处分割
            if end < text_len:
                # 优化：限制搜索范围，只在最后 50% 区域查找，且倒序查找
                # 使用 rfind 查找最近的句子结束符
                search_text = text[start:end]
                found_sep = False
                
                # 优先查找段落分隔符
                last_sep = search_text.rfind('\n\n')
                if last_sep != -1 and last_sep > chunk_size * 0.5:
                     end = start + last_sep + 2
                     found_sep = True
                else:
                    # 其次查找句子分隔符
                    for sep in separators[1:]:
                        last_sep = search_text.rfind(sep)
                        if last_sep != -1 and last_sep > chunk_size * 0.5:
                            end = start + last_sep + len(sep)
                            found_sep = True
                            break
            
            chunk = text[start:end].strip()
            # 过滤过短的垃圾块（如仅包含页码或空字符）
            if chunk and len(chunk) > 10:
                chunks.append(chunk)
            
            # 下一个块从重叠位置开始
            if end >= text_len:
                break
            start = end - overlap
            
        return chunks

    def _normalize_result(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not data:
            return {"entities": [], "relationships": []}

        entities = data.get('entities') or []
        relationships = data.get('relationships') or []

        def norm_name(value: Any) -> Optional[str]:
            if not isinstance(value, str):
                return None
            name = value.strip()
            return name if name else None

        entity_map: Dict[str, Dict[str, Any]] = {}
        for e in entities:
            if not isinstance(e, dict):
                continue
            eid = norm_name(e.get('id'))
            if not eid:
                continue
            aliases_raw = e.get('aliases') or []
            if isinstance(aliases_raw, str):
                aliases_raw = [aliases_raw]
            aliases: List[str] = []
            for a in aliases_raw:
                alias = norm_name(a)
                if alias and alias != eid:
                    aliases.append(alias)
            desc = e.get('description')
            desc = desc.strip() if isinstance(desc, str) else ''
            etype = e.get('type') or 'person'
            if eid not in entity_map:
                entity_map[eid] = {
                    "id": eid,
                    "type": etype,
                    "aliases": aliases,
                    "description": desc
                }
            else:
                existing = entity_map[eid]
                if aliases:
                    merged_aliases = existing.get('aliases', [])
                    for a in aliases:
                        if a not in merged_aliases and a != eid:
                            merged_aliases.append(a)
                    existing['aliases'] = merged_aliases
                if not existing.get('description') and desc:
                    existing['description'] = desc

        normalized_relationships: List[Dict[str, Any]] = []
        for r in relationships:
            if not isinstance(r, dict):
                continue
            src = norm_name(r.get('source'))
            tgt = norm_name(r.get('target'))
            if not src or not tgt or src == tgt:
                continue
            relation = r.get('relation')
            relation = relation.strip() if isinstance(relation, str) else None
            rtype = r.get('type')
            rtype = rtype.strip().lower() if isinstance(rtype, str) else None
            evidence = r.get('evidence')
            evidence = evidence.strip() if isinstance(evidence, str) else None
            if not evidence:
                continue
            weight = r.get('weight') or 1
            try:
                weight = int(weight)
            except Exception:
                weight = 1
            if weight < 1:
                weight = 1
            if weight > 10:
                weight = 10

            normalized_relationships.append({
                "source": src,
                "target": tgt,
                "relation": relation,
                "type": rtype,
                "weight": weight,
                "evidence": evidence
            })

            if src not in entity_map:
                entity_map[src] = {"id": src, "type": "person", "aliases": [], "description": ""}
            if tgt not in entity_map:
                entity_map[tgt] = {"id": tgt, "type": "person", "aliases": [], "description": ""}

        return {
            "entities": list(entity_map.values()),
            "relationships": normalized_relationships
        }

    def preprocess_text(self, text: str) -> str:
        """
        预处理文本
        - 移除多余空白
        - 标准化换行
        """
        import re
        # 标准化换行
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        # 移除连续空行（保留最多两个换行）
        text = re.sub(r'\n{3,}', '\n\n', text)
        # 移除行首行尾空白
        lines = [line.strip() for line in text.split('\n')]
        return '\n'.join(lines).strip()

    def analyze_text(self, text: str, session_id: Optional[str] = None, run_async: bool = True) -> Dict[str, Any]:
        """
        启动文本分析任务
        """
        logger.info(f"收到分析请求，文本长度: {len(text)}")
        if not session_id:
            session_id = f"rel_{uuid.uuid4().hex[:12]}"
            
        # 初始化会话
        self.sessions[session_id] = {
            "status": "processing",
            "status_msg": "正在解析文本...",
            "progress": 0,
            "created_at": datetime.now().isoformat(),
            "result": None,
            "error": None
        }
        
        if run_async:
            # 异步启动分析
            threading.Thread(target=self._run_analysis, args=(session_id, text)).start()
        else:
            # 同步执行 (用于测试)
            self._run_analysis(session_id, text)
        
        return {
            "success": True,
            "session_id": session_id,
            "status_url": f"/api/fortune/status/{session_id}"  # 保持 API 路径一致性，或稍后修改路由
        }

    def _post_process_roles(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        后处理：确保主角和反派存在
        如果 LLM 未能识别，则根据中心度（连接数）进行推断
        """
        if not data or 'entities' not in data or 'relationships' not in data:
            return data

        entities = data['entities']
        relationships = data['relationships']
        
        # 1. 计算每个节点的度 (Degree) 和 冲突关系数
        node_degrees = {e['id']: 0 for e in entities}
        node_conflicts = {e['id']: 0 for e in entities}
        
        for r in relationships:
            src, tgt = r.get('source'), r.get('target')
            rtype = r.get('type')
            
            if src in node_degrees: node_degrees[src] += 1
            if tgt in node_degrees: node_degrees[tgt] += 1
            
            if rtype == 'conflict':
                if src in node_conflicts: node_conflicts[src] += 1
                if tgt in node_conflicts: node_conflicts[tgt] += 1

        # 2. 检查是否存在主角
        protagonists = [e for e in entities if e.get('type') == 'protagonist']
        
        if not protagonists:
            # 策略：选择度最大的节点晋升为主角
            if entities:
                sorted_by_degree = sorted(entities, key=lambda e: node_degrees.get(e['id'], 0), reverse=True)
                new_protagonist = sorted_by_degree[0]
                new_protagonist['type'] = 'protagonist'
                logger.info(f"自动晋升主角: {new_protagonist['id']} (Degree: {node_degrees.get(new_protagonist['id'], 0)})")
                protagonists = [new_protagonist]

        # 3. 检查是否存在反派
        antagonists = [e for e in entities if e.get('type') == 'antagonist']
        
        if not antagonists and protagonists:
            main_protagonist_id = protagonists[0]['id']
            # 策略：在与主角有连接的节点中，寻找度最高 或 明确有 conflict 关系的
            # 优先找与主角有 conflict 关系的
            candidates = []
            for r in relationships:
                if r.get('type') == 'conflict':
                    if r['source'] == main_protagonist_id:
                        candidates.append(r['target'])
                    elif r['target'] == main_protagonist_id:
                        candidates.append(r['source'])
            
            target_antagonist_id = None
            
            if candidates:
                # 选冲突候选人中度最大的
                candidates.sort(key=lambda x: node_degrees.get(x, 0), reverse=True)
                target_antagonist_id = candidates[0]
            else:
                # 如果没有直接冲突，选除了主角外度最大的节点（大概率是反派或男二）
                # 排除已有的主角
                other_nodes = [e for e in entities if e['id'] != main_protagonist_id]
                if other_nodes:
                    sorted_others = sorted(other_nodes, key=lambda e: node_degrees.get(e['id'], 0), reverse=True)
                    target_antagonist_id = sorted_others[0]['id']
            
            if target_antagonist_id:
                for e in entities:
                    if e['id'] == target_antagonist_id:
                        e['type'] = 'antagonist'
                        logger.info(f"自动晋升反派: {e['id']}")
                        break

        return data

    def _build_overview(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not data or 'entities' not in data or 'relationships' not in data:
            return {}

        entities = data.get('entities', [])
        relationships = data.get('relationships', [])

        if not entities:
            return {}

        node_degrees = {e.get('id'): 0 for e in entities}
        relation_type_counts: Dict[str, int] = {}

        for r in relationships:
            src, tgt = r.get('source'), r.get('target')
            if src in node_degrees:
                node_degrees[src] += 1
            if tgt in node_degrees:
                node_degrees[tgt] += 1

            rtype = (r.get('type') or 'other').lower()
            relation_type_counts[rtype] = relation_type_counts.get(rtype, 0) + 1

        def rel_weight(rel: Dict[str, Any]) -> int:
            try:
                return int(rel.get('weight') or 1)
            except Exception:
                return 1

        def short_text(text: Optional[str], max_len: int = 70) -> Optional[str]:
            if not isinstance(text, str):
                return None
            text = text.strip()
            if not text:
                return None
            return text[:max_len]

        top_entities = sorted(entities, key=lambda e: node_degrees.get(e.get('id'), 0), reverse=True)[:50]
        top_entities_payload = [
            {
                "id": e.get('id'),
                "type": e.get('type', ''),
                "description": e.get('description', ''),
                "degree": node_degrees.get(e.get('id'), 0)
            }
            for e in top_entities
        ]

        sorted_relationships = sorted(
            relationships,
            key=lambda r: (rel_weight(r), len((r.get('evidence') or ''))),
            reverse=True
        )
        key_relationships = [
            {
                "source": r.get('source'),
                "target": r.get('target'),
                "relation": r.get('relation'),
                "type": r.get('type'),
                "weight": rel_weight(r),
                "evidence": r.get('evidence')
            }
            for r in sorted_relationships[:50]
        ]

        protagonists = [e.get('id') for e in entities if e.get('type') == 'protagonist']
        antagonists = [e.get('id') for e in entities if e.get('type') == 'antagonist']

        type_label = {
            "family": "亲属",
            "social": "社交",
            "romance": "情感",
            "conflict": "冲突",
            "work": "工作",
            "other": "其他"
        }
        top_types = sorted(relation_type_counts.items(), key=lambda x: x[1], reverse=True)[:2]
        top_type_labels = [type_label.get(k, k) for k, _ in top_types]

        overview_text = f"共识别 {len(entities)} 人物，{len(relationships)} 条关系。"
        if protagonists:
            overview_text += f" 核心人物为 { '、'.join(protagonists[:2]) }。"
        if antagonists:
            overview_text += f" 主要对立角色包括 { '、'.join(antagonists[:2]) }。"
        if top_type_labels:
            overview_text += f" 关系以 { '、'.join(top_type_labels) } 为主。"

        conflict_pairs = [r for r in relationships if (r.get('type') or '').lower() == 'conflict']
        if conflict_pairs:
            conflict_pairs = sorted(conflict_pairs, key=lambda r: rel_weight(r), reverse=True)[:2]
            conflict_names = [f"{r.get('source')} vs {r.get('target')}" for r in conflict_pairs]
            overview_text += f" 冲突集中在 { '、'.join(conflict_names) }。"

        protagonist_id = protagonists[0] if protagonists else (top_entities[0].get('id') if top_entities else None)
        adjacency: Dict[str, List[Dict[str, Any]]] = {e.get('id'): [] for e in entities}
        for r in relationships:
            src, tgt = r.get('source'), r.get('target')
            if not src or not tgt:
                continue
            if src not in adjacency or tgt not in adjacency:
                continue
            weight = rel_weight(r)
            rtype = (r.get('type') or 'other').lower()
            relation_label = r.get('relation') or type_label.get(rtype, '关系')
            evidence = short_text(r.get('evidence'))
            adjacency[src].append({
                "target": tgt,
                "relation": relation_label,
                "type": rtype,
                "weight": weight,
                "evidence": evidence
            })
            adjacency[tgt].append({
                "target": src,
                "relation": relation_label,
                "type": rtype,
                "weight": weight,
                "evidence": evidence
            })

        protagonist_connections = []
        if protagonist_id and protagonist_id in adjacency:
            connections = sorted(adjacency[protagonist_id], key=lambda x: (x.get("weight", 1), len((x.get("evidence") or ""))), reverse=True)
            seen = set()
            for c in connections:
                key = (c.get("target"), c.get("relation"), c.get("type"))
                if key in seen:
                    continue
                seen.add(key)
                protagonist_connections.append(c)
                if len(protagonist_connections) >= 6:
                    break

        storyline_lines = []
        for r in key_relationships[:6]:
            relation_label = r.get('relation') or type_label.get((r.get('type') or 'other').lower(), '关系')
            line = f"{r.get('source')} 与 {r.get('target')} 形成{relation_label}关系"
            evidence = short_text(r.get('evidence'))
            if evidence:
                line += f"，文本证据：“{evidence}”"
            storyline_lines.append(line)

        conflict_focus = []
        alliance_focus = []
        for r in sorted_relationships:
            rtype = (r.get('type') or 'other').lower()
            payload = {
                "source": r.get('source'),
                "target": r.get('target'),
                "relation": r.get('relation') or type_label.get(rtype, '关系'),
                "type": rtype,
                "weight": rel_weight(r),
                "evidence": short_text(r.get('evidence'))
            }
            if rtype == 'conflict' and len(conflict_focus) < 5:
                conflict_focus.append(payload)
            if rtype in {"family", "social", "romance", "work"} and len(alliance_focus) < 5:
                alliance_focus.append(payload)
            if len(conflict_focus) >= 5 and len(alliance_focus) >= 5:
                break

        parents = {e.get('id'): e.get('id') for e in entities}

        def find(x: str) -> str:
            while parents.get(x) != x:
                parents[x] = parents.get(parents.get(x))
                x = parents.get(x)
            return x

        def union(a: str, b: str):
            ra, rb = find(a), find(b)
            if ra and rb and ra != rb:
                parents[rb] = ra

        for r in relationships:
            src, tgt = r.get('source'), r.get('target')
            rtype = (r.get('type') or 'other').lower()
            if not src or not tgt:
                continue
            if rtype in {"family", "social", "romance", "work"}:
                union(src, tgt)

        groups: Dict[str, List[str]] = {}
        for eid in parents.keys():
            root = find(eid)
            groups.setdefault(root, []).append(eid)

        clusters = []
        for members in groups.values():
            if len(members) < 3:
                continue
            member_set = set(members)
            type_counts: Dict[str, int] = {}
            for r in relationships:
                src, tgt = r.get('source'), r.get('target')
                if src in member_set and tgt in member_set:
                    rtype = (r.get('type') or 'other').lower()
                    if rtype == 'conflict':
                        continue
                    type_counts[rtype] = type_counts.get(rtype, 0) + 1
            dominant_type = max(type_counts.items(), key=lambda x: x[1])[0] if type_counts else 'social'
            sorted_members = sorted(members, key=lambda m: node_degrees.get(m, 0), reverse=True)
            clusters.append({
                "dominant_type": dominant_type,
                "dominant_label": type_label.get(dominant_type, dominant_type),
                "members": sorted_members[:6],
                "size": len(members)
            })
        clusters = sorted(clusters, key=lambda c: c.get("size", 0), reverse=True)[:4]

        role_label = {
            "protagonist": "主角",
            "antagonist": "反派",
            "supporting": "配角",
            "neutral": "人物",
            "person": "人物"
        }

        main_cast = []
        for e in top_entities_payload[:4]:
            name = e.get("id")
            label = role_label.get(e.get("type") or "neutral", "人物")
            if label in {"主角", "反派"}:
                main_cast.append(f"{label}{name}")
            else:
                main_cast.append(f"{name}")

        reader_takeaways = []
        if main_cast:
            reader_takeaways.append(f"核心人物：{'、'.join(main_cast)}")
        if top_type_labels:
            reader_takeaways.append(f"关系侧重：{'、'.join(top_type_labels)}")
        if conflict_focus:
            conflict_items = []
            for r in conflict_focus[:2]:
                relation_label = r.get('relation') or type_label.get((r.get('type') or 'other').lower(), '关系')
                conflict_items.append(f"{r.get('source')}—{r.get('target')}（{relation_label}）")
            if conflict_items:
                reader_takeaways.append(f"主要对立：{'；'.join(conflict_items)}")
        if alliance_focus:
            alliance_items = []
            for r in alliance_focus[:2]:
                relation_label = r.get('relation') or type_label.get((r.get('type') or 'other').lower(), '关系')
                alliance_items.append(f"{r.get('source')}—{r.get('target')}（{relation_label}）")
            if alliance_items:
                reader_takeaways.append(f"关系纽带：{'；'.join(alliance_items)}")
        if storyline_lines:
            reader_takeaways.append(f"情节线索：{'；'.join(storyline_lines[:2])}")

        reader_questions = []
        if protagonists:
            reader_questions.append(f"主角 {protagonists[0]} 的目标与立场是什么？")
        else:
            reader_questions.append("故事核心人物是谁？他们想要什么？")
        if antagonists or conflict_focus:
            reader_questions.append("主要对立/冲突集中在哪些人物之间？")
        if relation_type_counts.get("romance"):
            reader_questions.append("情感线由哪些人物推动？")
        if relation_type_counts.get("family"):
            reader_questions.append("家族/血缘线牵动了哪些人物？")
        if relation_type_counts.get("work"):
            reader_questions.append("权力/组织关系如何改变人物走向？")
        if clusters:
            reader_questions.append("是否存在阵营或小团体？核心成员是谁？")
        if storyline_lines:
            reader_questions.append("关键事件或转折节点有哪些？")

        return {
            "overview_text": overview_text,
            "entity_count": len(entities),
            "relationship_count": len(relationships),
            "relation_type_counts": relation_type_counts,
            "top_entities": top_entities_payload,
            "key_relationships": key_relationships,
            "protagonists": protagonists,
            "antagonists": antagonists,
            "storyline_lines": storyline_lines,
            "conflict_focus": conflict_focus,
            "alliance_focus": alliance_focus,
            "protagonist_connections": protagonist_connections,
            "clusters": clusters,
            "reader_questions": reader_questions,
            "reader_takeaways": reader_takeaways
        }

    def _compact_result(
        self,
        data: Dict[str, Any],
        max_entities: int = 2000,
        max_relationships: int = 5000,
        max_evidence_chars: int = 300
    ) -> Dict[str, Any]:
        if not data:
            return {"entities": [], "relationships": []}

        data = self._normalize_result(data)
        entities = data.get('entities', []) or []
        relationships = data.get('relationships', []) or []

        seen_entities = {}
        for e in entities:
            eid = e.get('id')
            if not eid or eid in seen_entities:
                continue
            seen_entities[eid] = {
                "id": eid,
                "type": e.get('type', 'person'),
                "aliases": e.get('aliases', []),
                "description": e.get('description', '')
            }

        def rel_weight(rel: Dict[str, Any]) -> int:
            try:
                return int(rel.get('weight') or 1)
            except Exception:
                return 1

        compact_rels = []
        for r in relationships:
            src, tgt = r.get('source'), r.get('target')
            if not src or not tgt:
                continue
            evidence = r.get('evidence')
            if isinstance(evidence, str) and max_evidence_chars > 0:
                evidence = evidence[:max_evidence_chars]
            compact_rels.append({
                "source": src,
                "target": tgt,
                "relation": r.get('relation'),
                "type": r.get('type'),
                "weight": rel_weight(r),
                "evidence": evidence
            })

        # 彻底解决节点缺失问题：取消压缩环节的切片限制，确保所有实体和关系都进入聚合环节
        # 即使是权重为 1 的关系也要保留
        return {
            "entities": list(seen_entities.values()),
            "relationships": compact_rels
        }

    def _fast_merge_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        强化版内存合并逻辑：
        1. 模拟 Neo4j 的 MERGE 机制进行实体对齐
        2. 智能合并别名与描述，保留所有细节
        3. 权重累加与证据去重
        """
        merged_entities: Dict[str, Dict[str, Any]] = {}
        # 建立别名反向索引，用于实体对齐
        alias_to_id: Dict[str, str] = {}
        
        merged_relationships: Dict[tuple, Dict[str, Any]] = {}

        # 第一步：初步合并实体，建立 ID 映射
        for r in results:
            for e in r.get('entities', []) or []:
                eid = e.get('id')
                if not eid:
                    continue
                
                # 检查是否已存在（通过 ID 或别名）
                target_id = eid
                if eid in alias_to_id:
                    target_id = alias_to_id[eid]
                
                if target_id not in merged_entities:
                    merged_entities[target_id] = {
                        "id": target_id,
                        "type": e.get('type', 'person'),
                        "aliases": set(e.get('aliases', []) or []),
                        "description": e.get('description', '')
                    }
                else:
                    existing = merged_entities[target_id]
                    # 更新描述
                    if e.get('description') and e.get('description') not in existing['description']:
                        if existing['description']:
                            existing['description'] += " " + e.get('description')
                        else:
                            existing['description'] = e.get('description')
                    # 更新别名
                    if e.get('aliases'):
                        existing['aliases'].update(e.get('aliases'))
                
                # 注册所有别名到索引
                for alias in merged_entities[target_id]['aliases']:
                    if alias not in alias_to_id:
                        alias_to_id[alias] = target_id
                if eid not in alias_to_id:
                    alias_to_id[eid] = target_id

        # 第二步：合并关系
        for r in results:
            for rel in r.get('relationships', []) or []:
                src, tgt = rel.get('source'), rel.get('target')
                if not src or not tgt:
                    continue
                
                # 使用映射后的 ID 确保关系对齐
                src = alias_to_id.get(src, src)
                tgt = alias_to_id.get(tgt, tgt)
                
                if src == tgt: continue # 忽略自环
                
                rtype = (rel.get('type') or 'social').lower()
                rname = rel.get('relation') or '互动'
                key = tuple(sorted([src, tgt])) + (rtype,) # 无向图处理，确保 (A,B) 和 (B,A) 合并
                
                weight = rel.get('weight') or 1
                try:
                    weight = int(weight)
                except Exception:
                    weight = 1
                    
                if key not in merged_relationships:
                    merged_relationships[key] = {
                        "source": src,
                        "target": tgt,
                        "relation": rname,
                        "type": rtype,
                        "weight": min(weight, 10),
                        "evidence": [rel.get('evidence')] if rel.get('evidence') else []
                    }
                else:
                    merged = merged_relationships[key]
                    merged["weight"] = min((merged.get("weight") or 1) + weight, 10)
                    if rel.get('evidence') and rel.get('evidence') not in merged["evidence"]:
                        merged["evidence"].append(rel.get('evidence'))
                    if rname != merged["relation"] and rname not in merged["relation"]:
                        merged["relation"] += "、" + rname

        # 格式化输出
        final_entities = []
        for e in merged_entities.values():
            e['aliases'] = list(e['aliases'])
            final_entities.append(e)
            
        final_relationships = []
        for rel in merged_relationships.values():
            # 将证据列表转回字符串，取前 3 条以防过长
            rel['evidence'] = " | ".join(rel['evidence'][:3])
            final_relationships.append(rel)

        return {
            "entities": final_entities,
            "relationships": final_relationships
        }

    def _single_pass_aggregate(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """单次聚合：调用 LLM 合并结果"""
        if not results:
            return {"entities": [], "relationships": []}
        if len(results) == 1:
            return results[0]

        results = [self._compact_result(r) for r in results if r]
        results = [r for r in results if r.get('entities') or r.get('relationships')]
        if not results:
            return {"entities": [], "relationships": []}
        if len(results) == 1:
            return results[0]
            
        aggregator_prompt = get_aggregator_prompt()
        combined_input = json.dumps(results, ensure_ascii=False)
        
        messages = [
            {"role": "system", "content": aggregator_prompt},
            {"role": "user", "content": f"请合并以下提取结果：\n{combined_input}"}
        ]
        
        try:
            return self.llm.chat_json(messages, temperature=0.1, use_boost=True)
        except Exception as e:
            logger.error(f"Aggregation failed: {e}")
            # 如果聚合失败，返回第一个结果作为保底，避免崩溃
            return results[0] if results else {}

    def _recursive_aggregate(self, results: List[Dict[str, Any]], session_id: Optional[str] = None, level: int = 0) -> Dict[str, Any]:
        """递归分层聚合"""
        if not results:
            return {"entities": [], "relationships": []}

        # 使用更宽松的压缩参数，避免过早丢弃
        results = [self._compact_result(r, max_entities=3000, max_relationships=6000) for r in results if r]
        results = [r for r in results if r.get('entities') or r.get('relationships')]
        if not results:
            return {"entities": [], "relationships": []}
        if len(results) == 1:
            return results[0]
            
        # 进度反馈
        if session_id and session_id in self.sessions:
             self.sessions[session_id]["status_msg"] = f"正在进行第 {level + 1} 轮关系合并..."
             # 聚合阶段从 90% 开始，根据层级缓慢推进
             current_prog = 90 + min(level * 2, 8)
             self.sessions[session_id]["progress"] = current_prog

        # 策略调整：对于大量结果，优先使用代码快速合并，减少 LLM 的遗忘风险
        # 当结果数量 > 40 时，先进行一轮快速合并
        if len(results) > 40:
            merged_batches = []
            # 每 8 个合并为一个，纯代码合并，零损耗
            for i in range(0, len(results), 8):
                merged_batches.append(self._fast_merge_results(results[i:i + 8]))
            results = merged_batches
            logger.info(f"Level {level} pre-merge: reduced to {len(results)} items using fast_merge")

        # 估算字符数
        total_chars = sum(len(json.dumps(r, ensure_ascii=False)) for r in results)
        
        # 再次检查：如果还是太大，继续代码合并
        # 目标是将 total_chars 降到 LLM 可以舒适处理的范围内 (e.g. < 100k chars)
        if total_chars > 100000 and len(results) > 5:
            merged_batches = []
            for i in range(0, len(results), 5):
                merged_batches.append(self._fast_merge_results(results[i:i + 5]))
            results = merged_batches
            total_chars = sum(len(json.dumps(r, ensure_ascii=False)) for r in results)
        
        # 阈值：如果总字符数小于 80,000 (约 20k tokens) 且条目数不多，则直接聚合
        # 降低阈值以确保 LLM 不会因为输入过长而忽略细节
        if total_chars < 80000 and len(results) <= 8:
            logger.info(f"Level {level} aggregation: {len(results)} items, {total_chars} chars -> Direct LLM Aggregate")
            return self._single_pass_aggregate(results)
            
        # 否则，分批处理
        # 增大 batch_size，减少递归深度，防止在每一层都丢失细节
        batch_size = 8
        batches = [results[i:i + batch_size] for i in range(0, len(results), batch_size)]
        logger.info(f"Level {level} aggregation: {len(results)} items -> {len(batches)} batches (size {batch_size})")
        
        intermediate_results = []
        completed_batches = 0
        
        # 并行执行中间聚合
        # 降低并发数，避免 API 速率限制
        max_workers_env = os.getenv("RELATION_AGG_MAX_WORKERS")
        try:
            max_workers = int(max_workers_env) if max_workers_env else 5
        except ValueError:
            max_workers = 5
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self._single_pass_aggregate, batch) for batch in batches]
            for future in concurrent.futures.as_completed(futures):
                try:
                    res = future.result()
                    if res and (res.get('entities') or res.get('relationships')):
                        intermediate_results.append(res)
                except Exception as e:
                    logger.error(f"Intermediate aggregation failed: {e}")
                
                completed_batches += 1
                if session_id and session_id in self.sessions:
                    self.sessions[session_id]["status_msg"] = f"第 {level + 1} 轮聚合中: 已完成 {completed_batches}/{len(batches)} 批次..."
        
        # 递归下一层
        return self._recursive_aggregate(intermediate_results, session_id, level + 1)

    def _run_analysis(self, session_id: str, text: str):
        """后台执行分析逻辑"""
        try:
            # 0. 预处理
            text = self.preprocess_text(text)
            
            # 并行提取
            # 进一步降低 chunk_size 以获取极致的召回率
            chunk_size_env = os.getenv("RELATION_CHUNK_SIZE")
            overlap_env = os.getenv("RELATION_CHUNK_OVERLAP")
            try:
                # 默认使用 2000 字的小块，对标参商，AI 更容易抓取细节
                chunk_size = int(chunk_size_env) if chunk_size_env else 2000
            except ValueError:
                chunk_size = 2000
            try:
                overlap = int(overlap_env) if overlap_env else 400
            except ValueError:
                overlap = 400
            
            chunks = self._chunk_text(text, chunk_size=chunk_size, overlap=overlap)
            total_chunks = len(chunks)
            self.sessions[session_id]["status_msg"] = f"文本已切分为 {total_chunks} 个片段，准备并行提取..."
            logger.info(f"Session {session_id}: Split text into {total_chunks} chunks")
            
            if total_chunks == 0:
                raise ValueError("文本内容为空或无法分割")

            extracted_results = []
            completed_chunks = 0
            
            # 2. 并行提取
            def process_chunk(index, chunk_text):
                prompt = get_extractor_prompt()
                messages = [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"请深度分析以下文本片段（片段 {index+1}/{total_chunks}），不放过任何一个有名字的人物：\n\n{chunk_text}"}
                ]
                # 使用 boost 模型加速并行提取，并设置超时保护
                return self.llm.chat_json(messages, temperature=0.1, use_boost=True)

            # 并行提取
            # 动态调整并发数：
            # 1. 小文本（<20块）：max_workers = total_chunks（全力加速）
            # 2. 中等文本（20-50块）：max_workers = 20（平衡速度与稳定）
            # 3. 大文本（>50块）：max_workers = 25（压榨性能，但不超过 API 限制）
            max_workers_env = os.getenv("RELATION_EXTRACT_MAX_WORKERS")
            try:
                env_workers = int(max_workers_env) if max_workers_env else 0
            except ValueError:
                env_workers = 0

            if env_workers > 0:
                max_workers = env_workers
            else:
                if total_chunks <= 20:
                    max_workers = total_chunks
                elif total_chunks <= 50:
                    max_workers = 20
                else:
                    max_workers = 25
            
            # 兜底：至少 1 个 worker
            max_workers = max(1, max_workers)
            
            logger.info(f"Session {session_id}: Starting parallel extraction with {max_workers} workers for {total_chunks} chunks")

            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(process_chunk, i, chunk): i for i, chunk in enumerate(chunks)}
                
                for future in concurrent.futures.as_completed(futures):
                    index = futures.get(future)
                    try:
                        result = future.result()
                        normalized = self._normalize_result(result)
                        if normalized.get('entities') or normalized.get('relationships'):
                            extracted_results.append(normalized)
                        
                        completed_chunks += 1
                        # 确保进度能稳步推进，即使卡在提取阶段也能看到变化
                        progress = min(int((completed_chunks / total_chunks) * 90), 89)
                        self.sessions[session_id]["progress"] = progress
                        self.sessions[session_id]["status_msg"] = f"正在提取关系: 已完成 {completed_chunks}/{total_chunks} 个片段..."
                        
                        # 每完成 5 个片段打印一次日志
                        if completed_chunks % 5 == 0:
                            logger.info(f"Session {session_id}: Progress {progress}%, {completed_chunks}/{total_chunks} chunks")
                    except Exception as e:
                        logger.error(f"Chunk {index} processing failed: {e}")
                        # 即使失败也增加计数，防止进度条卡死
                        completed_chunks += 1
            
            if not extracted_results:
                raise Exception("未能从文本中提取出有效信息")

            # 3. 结果聚合
            self.sessions[session_id]["status"] = "aggregating"
            self.sessions[session_id]["status_msg"] = "正在整合所有专家发现（可能需要多轮聚合）..."
            self.sessions[session_id]["progress"] = 90
            
            # 使用新的递归聚合替代旧的单次聚合
            final_result = self._recursive_aggregate(extracted_results, session_id)
            final_result = self._normalize_result(final_result)
            
            # 3.5 后处理：确保角色完整性
            final_result = self._post_process_roles(final_result)
            
            # 4. 完成
            final_result["overview"] = self._build_overview(final_result)
            self.sessions[session_id]["result"] = final_result
            self.sessions[session_id]["status"] = "completed"
            self.sessions[session_id]["progress"] = 100
            self.sessions[session_id]["status_msg"] = "梳理完成"
            
        except Exception as e:
            logger.error(f"Analysis failed for session {session_id}: {str(e)}")
            self.sessions[session_id]["status"] = "failed"
            self.sessions[session_id]["error"] = str(e)
            self.sessions[session_id]["status_msg"] = "分析过程中发生错误"

    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """查询任务状态"""
        session = self.sessions.get(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}
        
        response = {
            "success": True,
            "status": session["status"],
            "progress": session["progress"],
            "message": session["status_msg"]
        }
        
        if session["status"] == "completed":
            response["data"] = session["result"]
            
        if session["status"] == "failed":
            response["error"] = session["error"]
            
        return response
