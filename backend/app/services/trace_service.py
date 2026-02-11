"""
追迹分析服务
负责文本分块、并行提取、结果聚合与轨迹生成
"""

import concurrent.futures
import json
import math
import os
import random
import re
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx
from networkx.algorithms import community

from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from ..utils.geocoder import NominatimGeocoder
from .trace_agents import get_trace_extractor_prompt, get_trace_aggregator_prompt, get_fictional_relation_prompt

logger = get_logger('footprints.trace_service')


class TraceService:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self._geocoder: Optional[NominatimGeocoder] = None

    def _get_geocoder(self) -> Optional[NominatimGeocoder]:
        disable = (os.getenv("GEOCODE_DISABLE") or "").strip().lower() in {"1", "true", "yes"}
        if disable:
            return None
        if self._geocoder is not None:
            return self._geocoder
        cache_path = os.getenv("GEOCODE_CACHE_PATH")
        if not cache_path:
            cache_path = os.path.join(os.path.dirname(__file__), "../../../.cache/geocode_cache.json")
        self._geocoder = NominatimGeocoder(cache_path=cache_path, min_interval_sec=1.0)
        return self._geocoder

    def _heuristic_place_type(self, name: str) -> Optional[str]:
        name = (name or '').strip()
        if not name:
            return None
        # Removed common wuxia/fantasy suffixes like 镇, 乡, 街, 路, 桥 to avoid false positives
        if re.search(r'(省|市|县|区|街道|站|机场|港|大学|学院|医院|公园|广场)$', name):
            return "real"
        return None

    def _geocode_locations(self, locations: List[Dict[str, Any]], session_id: Optional[str] = None) -> None:
        geocoder = self._get_geocoder()
        if not geocoder:
            return

        targets = []
        for loc in locations:
            if not isinstance(loc, dict):
                continue
            if loc.get("place_type") == "fictional":
                continue
            if isinstance(loc.get("geo"), dict):
                continue
            targets.append(loc)

        total = len(targets)
        if total == 0:
            return

        for idx, loc in enumerate(targets, start=1):
            if session_id and session_id in self.sessions:
                self.sessions[session_id]["status_msg"] = f"正在定位现实地名: {idx}/{total}..."
                self.sessions[session_id]["progress"] = 90 + min(int((idx / total) * 5), 5)

            name = loc.get("id") or ""
            geo = geocoder.geocode(name)
            if geo:
                loc["geo"] = geo
                if loc.get("place_type") == "uncertain":
                    loc["place_type"] = "real"

    def _compute_location_context(self, locations: List[Dict[str, Any]], extracted_results: List[Dict[str, Any]], alias_to_id: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
        context: Dict[str, Dict[str, Any]] = {}
        for loc in locations:
            context[loc["id"]] = {"related": set(), "chars": set()}

        for res in extracted_results:
            events = res.get("events") or []
            chunk_locs = set()
            
            # Resolve locations in this chunk
            for evt in events:
                raw = evt.get("location")
                lid = alias_to_id.get(raw, raw)
                if lid and lid in context:
                    chunk_locs.add(lid)
                    for c in (evt.get("characters") or []):
                        if c:
                            context[lid]["chars"].add(c)
            
            # Add co-occurrences
            for lid in chunk_locs:
                for other in chunk_locs:
                    if lid != other:
                        context[lid]["related"].add(other)

        final_context = {}
        for lid, data in context.items():
            related = sorted(list(data["related"]))[:6]
            chars = sorted(list(data["chars"]))[:4]
            if related or chars:
                final_context[lid] = {
                    "related_locations": related,
                    "common_characters": chars
                }
        return final_context

    def _enforce_scope_rules(self, loc: Dict[str, Any]) -> None:
        kind = (loc.get("kind") or "").strip().lower()
        scope = (loc.get("scope") or "").strip().lower()
        name = (loc.get("id") or "").strip()
        
        # Rule 1: Exhaustive list of Sub-location Kinds
        sub_kinds = {
            # Basic & Residential
            "room", "hall", "courtyard", "corridor", "path", "gate", "wall", "floor", "window", 
            "kitchen", "bedroom", "bathroom", "toilet", "restroom", "stairs", "elevator", 
            "balcony", "terrace", "lobby", "reception", "pantry", "basement", "attic", 
            "apartment", "dormitory", "studio", "suite",
            
            # Commercial & Entertainment (Modern)
            "mall", "market", "shop", "store", "supermarket", "convenience_store",
            "restaurant", "cafe", "bar", "pub", "club", "karaoke", "cinema", "theater", "gym",
            "hotel", "inn", "motel", "hostel", "resort", "spa", "casino",
            
            # Office & Institutional (Modern)
            "office", "meeting_room", "conference_room", "workspace", "cubicle",
            "classroom", "library", "laboratory", "auditorium", "cafeteria", "canteen",
            "hospital", "clinic", "ward", "surgery", "pharmacy", "police_station", "fire_station",
            "post_office", "bank", "museum", "gallery",
            
            # Transport & Infrastructure (Modern)
            "station", "stop", "platform", "dock", "pier", "wharf", "airport", "terminal",
            "parking", "garage", "tunnel", "bridge", "factory", "warehouse", "plant", "workshop",
            
            # Ancient & Fantasy
            "palace", "temple", "shrine", "altar", "pagoda", "tower", "pavilion", "gazebo",
            "cave", "grotto", "dungeon", "cell", "prison", "jail", "crypt", "tomb", "grave",
            "arena", "stadium", "ring", "field", "formation", "array",
            "sect_gate", "main_hall", "side_hall", "scripture_library", "pill_room", "weapon_room",
            "secret_chamber", "treasure_room", "spirit_field", "medicine_garden",
            
            # Objects/Vehicles (treated as POI/Sub)
            "vehicle", "car", "bus", "train", "plane", "ship", "boat", "carriage", "sedan_chair",
            "tent", "camp", "cabin"
        }
        
        if kind in sub_kinds:
            if scope == "world":
                loc["scope"] = "sub"
        
        if kind in {"item", "furniture", "decoration", "device", "weapon", "tool"}:
            loc["scope"] = "poi"
            
        # Rule 2: Large administrative/geographical units are typically WORLD
        if kind in {"country", "state", "province", "continent", "ocean", "planet", "galaxy", "universe"}:
            if scope != "world":
                loc["scope"] = "world"

        if name:
            # Rule 3: Fuzzy Keyword Recognition (Suffixes & Keywords)
            
            # 1. Suffixes (Characters that typically end a sub-location name)
            sub_suffixes = [
                # Generic Building Parts
                "室", "厅", "房", "廊", "厕", "厨", "卫", "梯", "台", "壁", "窗", "门", "柱", "底", "顶",
                
                # Residential/Living
                "寓", "舍", "宅", "邸", "窟", "洞",
                
                # Ancient Architecture
                "阁", "轩", "斋", "榭", "亭", "楼", "塔", "阙", "坛", "座", "池", "井", "墓", "冢",
                "庵", "观", "寺", "庙", "祠", "堂", "署", "监", "狱", "牢",
                
                # Commercial/Functional
                "馆", "店", "铺", "厂", "仓", "所", "处", "局", "科", "部", "行", "社",
                
                # Modern
                "站", "港", "院", "园", "场" # Be careful with 场 (Field/Square) and 院 (Courtyard/Institute)
            ]
            
            # 2. Keywords (Substrings that imply sub-location)
            sub_keywords = [
                # --- Modern ---
                "花园", "庭院", "别院", "小院", "园子", "公园", "植物园", "动物园", "游乐园",
                "商场", "商城", "商厦", "市场", "集市", "商铺", "店铺", "超市", "便利店", "百货",
                "房间", "卧室", "客房", "书房", "厨房", "餐厅", "卫生间", "浴室", "厕所", "洗手间", "淋浴间",
                "大厅", "前厅", "后厅", "客厅", "饭厅", "走廊", "过道", "通道", "楼梯", "电梯",
                "大楼", "写字楼", "办公楼", "教学楼", "实验楼", "宿舍楼", "住院部", "门诊部",
                "小区", "社区", "别墅", "公寓", "宿舍", "客栈", "酒店", "饭店", "酒楼", "旅馆", "招待所",
                "网吧", "酒吧", "咖啡", "茶馆", "电影院", "剧院", "体育馆", "健身房", "游泳池",
                "地铁", "公交", "火车站", "机场", "航站楼", "候机", "候车", "停车场", "车库",
                "内部", "里面", "之中", "地下室", "天台", "阳台",
                
                # --- Ancient / Wuxia ---
                "皇宫", "王府", "侯府", "官邸", "府邸", "私宅", "别苑",
                "大门", "侧门", "后门", "山门", "城门", # Gates are usually sub/poi
                "正殿", "偏殿", "主殿", "寝殿", "大殿", "议事厅", "聚义厅",
                "书斋", "书库", "藏书", "经阁", "丹房", "器房", "兵器库", "库房", "仓库",
                "牢房", "地牢", "水牢", "天牢", "刑房", "密室", "暗道", "地宫",
                "客栈", "酒肆", "青楼", "画舫", "赌坊", "当铺", "钱庄", "镖局", "驿站",
                "擂台", "校场", "演武", "练功",
                
                # --- Xuanhuan / Fantasy ---
                "洞府", "石室", "闭关", "修炼室",
                "炼丹", "炼器", "制符", "阵法", "传送阵", "聚灵阵", "护山大阵",
                "秘境入口", "禁地", "后山", "灵田", "药园", "兽栏",
                "试炼塔", "通天塔", "藏经阁", "任务堂", "执法堂", "外门", "内门", "杂役处"
            ]
            
            # Exclusions (If name contains these, do NOT force to sub based on suffixes/keywords alone, unless very sure)
            # e.g. "天剑门" (Sect) ends with "门", but shouldn't be sub.
            # e.g. "青云山" ends with "山", not in suffix list, but good to be safe.
            # e.g. "凤凰城" ends with "城".
            exclusion_suffixes = ["城", "镇", "村", "国", "洲", "界", "大陆", "山", "河", "江", "湖", "海", "洋", "岛", "峰", "谷", "林", "原", "宗", "派", "门", "帮", "教"]
            
            # Specific logic for single-character suffixes that might be ambiguous
            # "门" (Gate vs Sect): If "天剑门", likely Sect. If "大门", Gate.
            # "殿" (Hall): Almost always sub.
            # "宫" (Palace): "移花宫" (Sect) vs "储秀宫" (Room).
            
            is_sub = False
            
            # Check Suffixes
            for s in sub_suffixes:
                if name.endswith(s):
                    # Ambiguity check
                    if s == "门" and len(name) > 2: # e.g. "天剑门"
                         continue # Skip, likely a sect
                    if s == "院" and ("书院" in name or "学院" in name or "研究院" in name):
                         continue # Institutes might be large
                    if s == "场" and ("广场" not in name and "市场" not in name and "操场" not in name):
                         # "战场" (Battlefield) -> World?
                         continue
                    is_sub = True
                    break
            
            if not is_sub:
                 if any(k in name for k in sub_keywords):
                     is_sub = True
                     
            if is_sub:
                # Double check exclusions
                # If it ends with an exclusion suffix, override strict sub (unless it's in the keyword whitelist)
                # e.g. "药园" (Garden) ends with "园" (Sub), but "桃源" (Place)?
                # Actually, exclusion_suffixes are for things like "City", "Mountain".
                if any(name.endswith(ex) for ex in exclusion_suffixes):
                    # But wait, "山门" (Gate) ends with "门" (Exclusion).
                    # "后山" (Back Mountain) ends with "山".
                    # If the Keyword match was strong (e.g. "山门" is in sub_keywords), we keep it as sub.
                    # If it was only a Suffix match, we might revert.
                    
                    # Let's trust Keywords more than Suffixes.
                    # If matched via Keyword, keep as Sub.
                    # If matched via Suffix ONLY, and also ends with Exclusion, then ignore.
                    pass 
                
                if scope == "world":
                    loc["scope"] = "sub"

    def _classify_locations_with_llm(
        self, 
        locations: List[Dict[str, Any]], 
        session_id: Optional[str] = None,
        context_map: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        # Allow all locations to be classified (including real ones, for scope/kind)
        targets = locations
        if not targets:
            return locations
            
        # Increase limit for DeepSeek/modern LLMs
        targets_slice = targets[:300]
        
        payload_items = []
        for l in targets_slice:
            item = {
                "id": l["id"],
                "place_type": l.get("place_type", "uncertain"),
                "description": l.get("description", "")[:100],
                "evidence": l.get("evidence", "")[:100],
                "parent_location_hint": l.get("parent_id")  # Pass existing parent hint to LLM
            }
            # Add context if available
            if context_map and l["id"] in context_map:
                ctx = context_map[l["id"]]
                if ctx.get("related_locations"):
                    item["related"] = ctx["related_locations"]
                if ctx.get("common_characters"):
                    item["chars"] = ctx["common_characters"]
            payload_items.append(item)

        payload = {"locations": payload_items}
        
        prompt = get_trace_aggregator_prompt()
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"请对以下地点列表进行分类（scope, kind, parent_id），并修正 place_type，仅返回 JSON：\n{json.dumps(payload, ensure_ascii=False)}"}
        ]
        
        try:
            if session_id and session_id in self.sessions:
                self.sessions[session_id]["status_msg"] = "正在智能构建地点层级..."
                logger.info(f"Session {session_id}: Starting LLM classification for {len(targets_slice)} locations")
                
            resp = self.llm.chat_json(messages, temperature=0.1)
            logger.info(f"Session {session_id}: LLM classification response received")
            classified_list = resp.get("locations") or []
            
            c_map = {c["id"]: c for c in classified_list if c.get("id")}
            
            # 2024-05: LLM Alias Resolution
            # If LLM suggests that 'A' is actually 'B' (via aliases), we should note it.
            # However, for now we just trust the prompt's `aliases` output in the extraction phase more.
            # But we can look at if LLM changed the ID in the response (though prompt didn't explicitly ask for ID change).
            
            for loc in locations:
                if loc["id"] in c_map:
                    c = c_map[loc["id"]]
                    loc["scope"] = c.get("scope")
                    loc["kind"] = c.get("kind")
                    loc["parent_id"] = c.get("parent_id")
                    
                    # Update place_type if LLM provides a better one
                    if c.get("place_type") and c.get("place_type") in {"real", "fictional"}:
                        loc["place_type"] = c.get("place_type")
                    
                    # If LLM returns aliases here (though aggregation prompt doesn't explicitly emphasize it, but we can add it)
                    if c.get("aliases"):
                         current_aliases = set(loc.get("aliases") or [])
                         current_aliases.update(c.get("aliases"))
                         loc["aliases"] = list(current_aliases)
                
                # Apply rules
                self._enforce_scope_rules(loc)
                
                if loc.get("parent_id") and loc.get("scope") == "world":
                     loc["scope"] = "sub"
            
            return locations
        except Exception as e:
            logger.error(f"Classification error: {e}")
            return locations

    def _assign_parent_fallback(
        self,
        locations: List[Dict[str, Any]],
        context_map: Optional[Dict[str, Any]],
        alias_to_id: Dict[str, str]
    ) -> None:
        loc_map = {l["id"]: l for l in locations if l.get("id")}
        
        # Identify potential parents (Rank 2+)
        # We sort by length descending to ensure "Tianjian Sect Main Hall" matches "Tianjian Sect" not "Tianjian" (if both exist)
        potential_parents = [l for l in locations if self._get_rank(l) >= 2 or (l.get("scope") == "world" and self._get_rank(l) >= 1)]
        potential_parents.sort(key=lambda x: len(x["id"]), reverse=True)
        parent_ids = {p["id"] for p in potential_parents}

        for loc in locations:
            # Skip if already has parent
            if loc.get("parent_id"):
                loc["parent_id"] = alias_to_id.get(loc["parent_id"], loc["parent_id"])
                continue
            
            # Rank 3 entities usually don't have parents (unless inside another Rank 3, e.g. Country in Continent)
            # But let's allow it if evidence is strong.

            loc_id = loc.get("id")
            text = f"{loc_id} {loc.get('description','')} {loc.get('evidence','')}"
            sub_like = False
            # Exhaustive Sub-location Kinds (synced with _enforce_scope_rules)
            sub_kinds = {
                # Basic & Residential
                "room", "hall", "courtyard", "corridor", "path", "gate", "wall", "floor", "window", 
                "kitchen", "bedroom", "bathroom", "toilet", "restroom", "stairs", "elevator", 
                "balcony", "terrace", "lobby", "reception", "pantry", "basement", "attic", 
                "apartment", "dormitory", "studio", "suite",
                
                # Commercial & Entertainment (Modern)
                "mall", "market", "shop", "store", "supermarket", "convenience_store",
                "restaurant", "cafe", "bar", "pub", "club", "karaoke", "cinema", "theater", "gym",
                "hotel", "inn", "motel", "hostel", "resort", "spa", "casino",
                
                # Office & Institutional (Modern)
                "office", "meeting_room", "conference_room", "workspace", "cubicle",
                "classroom", "library", "laboratory", "auditorium", "cafeteria", "canteen",
                "hospital", "clinic", "ward", "surgery", "pharmacy", "police_station", "fire_station",
                "post_office", "bank", "museum", "gallery",
                
                # Transport & Infrastructure (Modern)
                "station", "stop", "platform", "dock", "pier", "wharf", "airport", "terminal",
                "parking", "garage", "tunnel", "bridge", "factory", "warehouse", "plant", "workshop",
                
                # Ancient & Fantasy
                "palace", "temple", "shrine", "altar", "pagoda", "tower", "pavilion", "gazebo",
                "cave", "grotto", "dungeon", "cell", "prison", "jail", "crypt", "tomb", "grave",
                "arena", "stadium", "ring", "field", "formation", "array",
                "sect_gate", "main_hall", "side_hall", "scripture_library", "pill_room", "weapon_room",
                "secret_chamber", "treasure_room", "spirit_field", "medicine_garden",
                
                # Objects/Vehicles (treated as POI/Sub)
                "vehicle", "car", "bus", "train", "plane", "ship", "boat", "carriage", "sedan_chair",
                "tent", "camp", "cabin"
            }
            if (loc.get("kind") or "").lower() in sub_kinds:
                sub_like = True
            
            if not sub_like:
                # Fuzzy Keyword Recognition (Suffixes & Keywords)
                sub_suffixes = [
                    # Generic Building Parts
                    "室", "厅", "房", "廊", "厕", "厨", "卫", "梯", "台", "壁", "窗", "门", "柱", "底", "顶",
                    # Residential/Living
                    "寓", "舍", "宅", "邸", "窟", "洞",
                    # Ancient Architecture
                    "阁", "轩", "斋", "榭", "亭", "楼", "塔", "阙", "坛", "座", "池", "井", "墓", "冢",
                    "庵", "观", "寺", "庙", "祠", "堂", "署", "监", "狱", "牢",
                    # Commercial/Functional
                    "馆", "店", "铺", "厂", "仓", "所", "处", "局", "科", "部", "行", "社",
                    # Modern
                    "站", "港", "院", "园", "场" 
                ]
                sub_keywords = [
                    # --- Modern ---
                    "花园", "庭院", "别院", "小院", "园子", "公园", "植物园", "动物园", "游乐园",
                    "商场", "商城", "商厦", "市场", "集市", "商铺", "店铺", "超市", "便利店", "百货",
                    "房间", "卧室", "客房", "书房", "厨房", "餐厅", "卫生间", "浴室", "厕所", "洗手间", "淋浴间",
                    "大厅", "前厅", "后厅", "客厅", "饭厅", "走廊", "过道", "通道", "楼梯", "电梯",
                    "大楼", "写字楼", "办公楼", "教学楼", "实验楼", "宿舍楼", "住院部", "门诊部",
                    "小区", "社区", "别墅", "公寓", "宿舍", "客栈", "酒店", "饭店", "酒楼", "旅馆", "招待所",
                    "网吧", "酒吧", "咖啡", "茶馆", "电影院", "剧院", "体育馆", "健身房", "游泳池",
                    "地铁", "公交", "火车站", "机场", "航站楼", "候机", "候车", "停车场", "车库",
                    "内部", "里面", "之中", "地下室", "天台", "阳台",
                    # --- Ancient / Wuxia ---
                    "皇宫", "王府", "侯府", "官邸", "府邸", "私宅", "别苑",
                    "大门", "侧门", "后门", "山门", "城门", 
                    "正殿", "偏殿", "主殿", "寝殿", "大殿", "议事厅", "聚义厅",
                    "书斋", "书库", "藏书", "经阁", "丹房", "器房", "兵器库", "库房", "仓库",
                    "牢房", "地牢", "水牢", "天牢", "刑房", "密室", "暗道", "地宫",
                    "客栈", "酒肆", "青楼", "画舫", "赌坊", "当铺", "钱庄", "镖局", "驿站",
                    "擂台", "校场", "演武", "练功",
                    # --- Xuanhuan / Fantasy ---
                    "洞府", "石室", "闭关", "修炼室",
                    "炼丹", "炼器", "制符", "阵法", "传送阵", "聚灵阵", "护山大阵",
                    "秘境入口", "禁地", "后山", "灵田", "药园", "兽栏",
                    "试炼塔", "通天塔", "藏经阁", "任务堂", "执法堂", "外门", "内门", "杂役处"
                ]
                
                # Exclusions
                exclusion_suffixes = ["城", "镇", "村", "国", "洲", "界", "大陆", "山", "河", "江", "湖", "海", "洋", "岛", "峰", "谷", "林", "原", "宗", "派", "门", "帮", "教"]

                is_sub = False
                for s in sub_suffixes:
                    if loc_id.endswith(s):
                        if s == "门" and len(loc_id) > 2: continue
                        if s == "院" and ("书院" in loc_id or "学院" in loc_id or "研究院" in loc_id): continue
                        if s == "场" and ("广场" not in loc_id and "市场" not in loc_id and "操场" not in loc_id): continue
                        is_sub = True
                        break
                
                if not is_sub:
                    if any(k in loc_id for k in sub_keywords):
                        is_sub = True
                
                if is_sub:
                     if any(loc_id.endswith(ex) for ex in exclusion_suffixes):
                         # Trust keyword whitelist over exclusion suffix
                         # But since we don't know which matched, we only revert if it was a weak match?
                         # For now, just keep simple: if exclusion matches, we are cautious.
                         pass
                     else:
                         sub_like = True
            
            best_parent = None
            best_score = 0
            
            # Candidates: Related locations + Locations mentioned in text + Name containment
            candidates = set()
            
            # 1. From Context/Related
            related_ids = []
            if context_map and loc_id in context_map:
                related_ids = context_map[loc_id].get("related_locations") or []
            
            for rid in related_ids:
                rid = alias_to_id.get(rid, rid)
                if rid in loc_map and rid in parent_ids and rid != loc_id:
                    candidates.add(rid)
            
            # 2. From Name Containment (Prefix/Suffix)
            for p in potential_parents:
                pid = p["id"]
                if pid == loc_id: continue
                if pid in loc_id: # e.g. "Tianjian Sect" in "Tianjian Sect Side Hall"
                    candidates.add(pid)
                if loc_id in pid: # e.g. "Side Hall" in "Tianjian Sect Side Hall" (Unlikely parent)
                    pass
            
            # 3. From Text Mention
            for p in potential_parents:
                if p["id"] in text and p["id"] != loc_id:
                    candidates.add(p["id"])

            # Evaluate Candidates
            for cid in candidates:
                cand = loc_map[cid]
                score = 0
                
                # Rule A: Name Containment (Very Strong)
                # "Tianjian Sect Side Hall" (loc) contains "Tianjian Sect" (cand) -> Parent is Cand
                if cid in loc_id:
                    score += 20
                
                # Rule B: Explicit Evidence
                if f"位于{cid}" in text or f"在{cid}" in text: score += 15
                if f"属于{cid}" in text or f"inside {cid}" in text: score += 15
                if f"{cid}的" in text: score += 10
                if f"位于{cid}内" in text or f"在{cid}内" in text: score += 15
                if f"在{cid}之中" in text or f"在{cid}里面" in text or f"在{cid}内部" in text: score += 15
                if f"{cid}内" in text or f"{cid}中" in text: score += 8
                
                # Rule C: Co-occurrence
                if cid in related_ids: score += 2
                
                # Rule D: Rank Hierarchy
                # Parent should ideally have higher or equal rank
                p_rank = self._get_rank(cand)
                c_rank = self._get_rank(loc)
                if p_rank > c_rank: score += 5
                if p_rank < c_rank: score -= 10 # Unlikely child has higher rank than parent

                # Thresholds
                required_score = 3
                if c_rank >= 2: # Major entities (Cities, Sects) need strong evidence to be nested
                    required_score = 12 
                
                if score > best_score and score >= required_score:
                    best_score = score
                    best_parent = cand

            # Strategy 4: "Dangling Sub-location" (Generic names like "Side Hall")
            # If it's a generic low-rank place and appears with ONLY ONE major location, assume ownership.
            if not best_parent and self._get_rank(loc) == 1 and best_score == 0:
                # Filter related_ids to only potential parents
                valid_related = [rid for rid in related_ids if rid in loc_map and rid in parent_ids]
                if len(valid_related) == 1:
                    best_parent = loc_map[valid_related[0]]
                    # Low confidence, but better than floating on world map
            if not best_parent and sub_like:
                valid_related = [rid for rid in related_ids if rid in loc_map and rid in parent_ids]
                if valid_related:
                    valid_related.sort(key=lambda rid: (self._get_rank(loc_map[rid]), len(rid)), reverse=True)
                    best_parent = loc_map[valid_related[0]]
            
            # Apply
            if best_parent:
                loc["parent_id"] = best_parent["id"]
                if loc.get("scope") == "world":
                    loc["scope"] = "sub"

    def _build_real_map(self, locations: List[Dict[str, Any]], tracks: List[Dict[str, Any]]) -> Dict[str, Any]:
        loc_geo: Dict[str, Dict[str, Any]] = {}
        markers = []
        for loc in locations:
            geo = loc.get("geo")
            if isinstance(geo, dict) and isinstance(geo.get("lat"), (int, float)) and isinstance(geo.get("lon"), (int, float)):
                loc_geo[loc["id"]] = geo
                markers.append({
                    "location_id": loc["id"],
                    "label": loc["id"],
                    "lat": geo["lat"],
                    "lon": geo["lon"],
                    "place_type": loc.get("place_type", "uncertain")
                })

        polylines = []
        for track in tracks:
            character = track.get("character")
            for seg in track.get("segments") or []:
                a = seg.get("from_location")
                b = seg.get("to_location")
                if a not in loc_geo or b not in loc_geo:
                    continue
                polylines.append({
                    "character": character,
                    "from_location": a,
                    "to_location": b,
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [loc_geo[a]["lon"], loc_geo[a]["lat"]],
                            [loc_geo[b]["lon"], loc_geo[b]["lat"]]
                        ]
                    }
                })

        return {"markers": markers, "polylines": polylines}

    def _layout_nodes(self, node_ids: List[str], constraints: List[Dict[str, Any]], width: int, height: int) -> Dict[str, Dict[str, float]]:
        if not node_ids:
            return {}
        
        coords = {lid: [random.random(), random.random()] for lid in node_ids}
        
        def target_dist(t: str) -> float:
            return {
                "near": 0.18, "inside": 0.14, "connected": 0.22, "route_to": 0.26, "far": 0.55
            }.get(t, 0.3)
            
        directional_delta = 0.18
        step = 0.08
        
        relevant_rels = []
        node_set = set(node_ids)
        for r in constraints:
            if r["a"] in node_set and r["b"] in node_set and r["a"] != r["b"]:
                relevant_rels.append(r)
        
        for _ in range(500):
            for r in relevant_rels:
                a, b = r["a"], r["b"]
                xa, ya = coords[a]
                xb, yb = coords[b]
                rtype = r.get("type")
                
                # Coordinate System: (0,0) is Top-Left. 
                # North = Smaller Y, South = Larger Y.
                # East = Larger X, West = Smaller X.
                
                if rtype == "north_of": # A is North of B -> ya < yb
                    target_y = yb - directional_delta
                    if ya > target_y:
                        delta = ya - target_y
                        ya -= delta * 0.5
                        yb += delta * 0.5
                elif rtype == "south_of": # A is South of B -> ya > yb
                    target_y = yb + directional_delta
                    if ya < target_y:
                        delta = target_y - ya
                        ya += delta * 0.5
                        yb -= delta * 0.5
                elif rtype == "east_of": # A is East of B -> xa > xb
                    target_x = xb + directional_delta
                    if xa < target_x:
                        delta = target_x - xa
                        xa += delta * 0.5
                        xb -= delta * 0.5
                elif rtype == "west_of": # A is West of B -> xa < xb
                    target_x = xb - directional_delta
                    if xa > target_x:
                        delta = xa - target_x
                        xa -= delta * 0.5
                        xb += delta * 0.5
                else:
                    dist = math.sqrt((xa - xb) ** 2 + (ya - yb) ** 2) + 1e-6
                    td = target_dist(rtype)
                    force = (dist - td) * step
                    dx = (xa - xb) / dist
                    dy = (ya - yb) / dist
                    xa -= force * dx
                    ya -= force * dy
                    xb += force * dx
                    yb += force * dy
                
                coords[a] = [xa, ya]
                coords[b] = [xb, yb]
                
        xs = [coords[l][0] for l in node_ids]
        ys = [coords[l][1] for l in node_ids]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = (max_x - min_x) or 1.0
        span_y = (max_y - min_y) or 1.0
        
        margin = 50
        result = {}
        for lid in node_ids:
            x = (coords[lid][0] - min_x) / span_x
            y = (coords[lid][1] - min_y) / span_y
            result[lid] = {
                "x": margin + x * max(1, width - 2 * margin),
                "y": margin + y * max(1, height - 2 * margin)
            }
        return result

    def _get_rank(self, loc: Dict[str, Any]) -> int:
        k = (loc.get("kind") or "").lower()
        if k in {"country", "continent", "planet", "empire"}: return 3
        if k in {"city", "town", "sect", "mountain", "forest", "island", "valley", "plain", "desert", "swamp", "palace_group", "estate", "fortress"}: return 2
        return 1

    def _refine_hierarchy_with_communities(self, locations: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> None:
        try:
            G = nx.Graph()
            loc_map = {l["id"]: l for l in locations}
            
            for l in locations:
                G.add_node(l["id"], rank=self._get_rank(l))
                
            for e in edges:
                if e["a"] in loc_map and e["b"] in loc_map:
                    G.add_edge(e["a"], e["b"])
                
            # Detect communities
            communities = community.greedy_modularity_communities(G)
            
            for comm in communities:
                comm_list = list(comm)
                # Find potential parents (Rank >= 1, prioritized by Rank then Degree)
                # Previously we filtered Rank >= 2, which prevented Rank 1 hubs (like Courtyards) from being parents.
                parents = list(comm_list)
                
                if not parents:
                    continue
                    
                # Sort parents by Rank desc, then Degree desc
                parents.sort(key=lambda n: (G.nodes[n].get("rank", 0), G.degree[n]), reverse=True)
                best_parent_id = parents[0]
                parent_rank = G.nodes[best_parent_id]["rank"]
                
                for node_id in comm_list:
                    if node_id == best_parent_id: continue
                    
                    node = loc_map.get(node_id)
                    if not node: continue
                    
                    # If node already has a parent, skip
                    if node.get("parent_id"): continue
                    
                    # Only assign if child rank <= parent rank (Relaxed)
                    # Allow Rank 1 inside Rank 1 if it's a stronger entity
                    child_rank = self._get_rank(node)
                    
                    if child_rank <= parent_rank:
                        node["parent_id"] = best_parent_id
                        if node.get("scope") == "world":
                            node["scope"] = "sub"
        except Exception as e:
            logger.warning(f"Community hierarchy refinement failed: {e}")

    def _build_fictional_map(
        self,
        locations: List[Dict[str, Any]],
        tracks: List[Dict[str, Any]],
        events: List[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        locs_all = [l for l in locations if l.get("id")]
        if not locs_all:
            return None

        loc_map_all = {l["id"]: l for l in locs_all}

        event_counts: Dict[str, int] = {}
        if events:
            for ev in events:
                lid = ev.get("location_id")
                if lid in loc_map_all:
                    event_counts[lid] = event_counts.get(lid, 0) + 1

        degree_counts: Dict[str, int] = {}
        for track in tracks:
            for seg in track.get("segments") or []:
                a = seg.get("from_location")
                b = seg.get("to_location")
                if a in loc_map_all and b in loc_map_all and a != b:
                    degree_counts[a] = degree_counts.get(a, 0) + 1
                    degree_counts[b] = degree_counts.get(b, 0) + 1

        children_by_parent: Dict[str, List[str]] = {}
        for l in locs_all:
            pid = l.get("parent_id")
            if pid and pid in loc_map_all and pid != l["id"]:
                children_by_parent.setdefault(pid, []).append(l["id"])

        def is_world_anchor(lid: str) -> bool:
            loc = loc_map_all.get(lid) or {}
            if (loc.get("scope") or "").lower() == "world":
                return True
            if self._get_rank(loc) >= 2:
                return True
            return False

        def is_high_traffic(lid: str) -> bool:
            if degree_counts.get(lid, 0) >= 3:
                return True
            if event_counts.get(lid, 0) >= 2:
                return True
            if len(children_by_parent.get(lid, [])) >= 2:
                return True
            return False

        world_anchor_ids = {lid for lid in loc_map_all.keys() if is_world_anchor(lid)}
        high_traffic_ids = {lid for lid in loc_map_all.keys() if is_high_traffic(lid)}

        # If no world anchors found (e.g. short story with only rooms), pick the most important one as anchor
        if not world_anchor_ids:
            fallback = sorted(
                loc_map_all.keys(),
                key=lambda lid: (
                    degree_counts.get(lid, 0),
                    event_counts.get(lid, 0),
                    self._get_rank(loc_map_all.get(lid) or {}),
                    len(lid)
                ),
                reverse=True
            )
            if fallback:
                world_anchor_ids.add(fallback[0])

        keep_ids = set(world_anchor_ids) | high_traffic_ids
        keep_ids.update(children_by_parent.keys())

        def add_ancestors(lid: str) -> None:
            seen: set = set()
            cur = lid
            while True:
                loc = loc_map_all.get(cur) or {}
                pid = loc.get("parent_id")
                if not pid or pid == cur or pid in seen or pid not in loc_map_all:
                    return
                keep_ids.add(pid)
                seen.add(pid)
                cur = pid

        for lid in list(keep_ids):
            add_ancestors(lid)

        neighbors: Dict[str, set] = {}
        for track in tracks:
            for seg in track.get("segments") or []:
                a = seg.get("from_location")
                b = seg.get("to_location")
                if a in loc_map_all and b in loc_map_all and a != b:
                    neighbors.setdefault(a, set()).add(b)
                    neighbors.setdefault(b, set()).add(a)

        frontier = list(keep_ids)
        for _ in range(2):
            nxt = []
            for lid in frontier:
                for nb in neighbors.get(lid, set()):
                    if nb not in keep_ids:
                        keep_ids.add(nb)
                        nxt.append(nb)
            frontier = nxt
            if not frontier:
                break

        queue = list(keep_ids)
        while queue:
            pid = queue.pop()
            for cid in children_by_parent.get(pid, []):
                if cid not in keep_ids:
                    keep_ids.add(cid)
                    queue.append(cid)

        def importance_score(lid: str) -> Tuple[int, int, int, int, int]:
            loc = loc_map_all.get(lid) or {}
            rank = self._get_rank(loc)
            is_world = 1 if (loc.get("scope") or "").lower() == "world" else 0
            deg = degree_counts.get(lid, 0)
            evc = event_counts.get(lid, 0)
            childc = len(children_by_parent.get(lid, []))
            return (is_world, rank, deg, evc, childc)

        map_locs = [loc_map_all[lid] for lid in sorted(keep_ids, key=importance_score, reverse=True)]

        loc_ids = [l["id"] for l in map_locs if l.get("id")]
        loc_set = set(loc_ids)
        if not loc_ids:
            return None
            
        loc_map = {l["id"]: l for l in map_locs}

        # Route edges (raw connectivity from tracks)
        route_edges = []
        for track in tracks:
            for seg in track.get("segments") or []:
                a = seg.get("from_location")
                b = seg.get("to_location")
                if a in loc_set and b in loc_set and a != b:
                    route_edges.append({"a": a, "b": b, "type": "route_to", "evidence": seg.get("evidence") or ""})

        # LLM Relation Inference
        relations = []
        mock_mode = (os.getenv("TRACE_MOCK") or "").strip().lower() in {"1", "true", "yes"}
        resp: Dict[str, Any] = {}
        if mock_mode:
            relations = route_edges[:]
        else:
            prompt = get_fictional_relation_prompt()
            # Limit payload size
            payload = {
                "locations": [
                    {
                        "id": l.get("id"),
                        "aliases": l.get("aliases") or [],
                        "description": (l.get("description") or "")[:200],
                        "evidence": (l.get("evidence") or "")[:200],
                        "kind": l.get("kind")
                    }
                    for l in map_locs[:150]
                ],
                "route_edges": route_edges[:200]
            }
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"请根据以下信息推断虚构地点的空间关系：\n{json.dumps(payload, ensure_ascii=False)}"}
            ]
            try:
                if session_id and session_id in self.sessions:
                    self.sessions[session_id]["status_msg"] = "正在推断虚构地点空间关系..."
                    self.sessions[session_id]["progress"] = 96
                    logger.info(f"Session {session_id}: Starting LLM relation inference for {len(payload['locations'])} locations")
                resp = self.llm.chat_json(messages, temperature=0.1, use_boost=False)
                logger.info(f"Session {session_id}: LLM relation inference response received")
                raw_relations = resp.get("relations") if isinstance(resp, dict) else None
                if isinstance(raw_relations, list):
                    for r in raw_relations:
                        if not isinstance(r, dict): continue
                        a = r.get("a")
                        b = r.get("b")
                        if a not in loc_set or b not in loc_set or a == b: continue
                        rtype = (r.get("type") or "").strip().lower()
                        if rtype not in {"north_of", "south_of", "east_of", "west_of", "near", "far", "inside", "connected", "route_to"}:
                            continue
                        evidence = r.get("evidence")
                        evidence = evidence.strip() if isinstance(evidence, str) else ""
                        relations.append({"a": a, "b": b, "type": rtype, "evidence": evidence})
            except Exception as e:
                logger.warning(f"Fictional relation inference failed, fallback to routes: {e}")

        if not relations:
            relations = route_edges

        width = 1000
        height = 1000
        world_name = "虚拟地图"
        try:
            if isinstance(resp, dict) and isinstance(resp.get("world"), dict):
                world = resp.get("world")
                width = int(world.get("width") or width)
                height = int(world.get("height") or height)
                world_name = world.get("name") or world_name
        except Exception:
            pass

        # --- Refine Hierarchy using Communities (Graph Theory) ---
        # This catches "orphaned" small locations and assigns them to the cluster leader
        all_edges = relations + route_edges
        self._refine_hierarchy_with_communities(map_locs, all_edges)

        post_children_by_parent: Dict[str, List[str]] = {}
        for l in map_locs:
            pid = l.get("parent_id")
            if pid and pid in loc_set and pid != l["id"]:
                post_children_by_parent.setdefault(pid, []).append(l["id"])
        
        # REMOVED: Do not force parents to be world anchors. 
        # Hierarchy flattening will handle them.
        # If they are top-level, they will be world nodes anyway.
        # If they are nested, they should be sub-nodes.

        # 3. Build initial parent map
        parent_map = {}
        for l in map_locs:
            pid = l.get("parent_id")
            if pid and pid in loc_set and pid != l["id"]:
                parent_map[l["id"]] = pid

        for r in relations:
            if r["type"] != "inside":
                continue
            child, parent = r["a"], r["b"]
            if parent in loc_set and parent != child:
                parent_map[child] = parent
                if child in loc_map:
                    loc_map[child]["parent_id"] = parent
                    loc_map[child]["scope"] = "sub"

        for child, pid in list(parent_map.items()):
            if pid not in loc_set or pid == child:
                del parent_map[child]

        for child in list(parent_map.keys()):
            seen = {child}
            cur = child
            while cur in parent_map:
                cur = parent_map[cur]
                if cur in seen:
                    del parent_map[child]
                    break
                seen.add(cur)

        flattened: Dict[str, str] = {}
        for child, pid in parent_map.items():
            if child in world_anchor_ids:
                continue
            if pid in world_anchor_ids:
                flattened[child] = pid
                continue
            cur = pid
            seen = {child, pid}
            root = None
            while cur in parent_map:
                cur = parent_map[cur]
                if cur in seen:
                    root = None
                    break
                seen.add(cur)
                if cur in world_anchor_ids:
                    root = cur
                    break
            if root and root != child:
                flattened[child] = root

        parent_map = flattened
        for child, pid in parent_map.items():
            if child in loc_map:
                loc_map[child]["parent_id"] = pid
                if (loc_map[child].get("scope") or "").lower() == "world":
                    loc_map[child]["scope"] = "sub"

        for lid in world_anchor_ids:
            if lid in loc_map:
                loc_map[lid]["scope"] = "world"
                loc_map[lid]["parent_id"] = None

        world_ids = []
        sub_groups: Dict[str, List[str]] = {}
        for l in map_locs:
            lid = l["id"]
            if lid in parent_map:
                pid = parent_map[lid]
                sub_groups.setdefault(pid, []).append(lid)
            else:
                # FIX: If scope is sub/poi, do NOT put on world map even if no parent found.
                # This guarantees "small map locations" do not appear on "big map".
                # They will be hidden if they have no parent.
                scope = (loc_map[lid].get("scope") or "").lower()
                if scope in {"sub", "poi"}:
                    continue
                world_ids.append(lid)

        # Layout World
        world_constraints = [r for r in relations + route_edges if r["a"] in world_ids and r["b"] in world_ids]
        world_layout = self._layout_nodes(world_ids, world_constraints, width, height)
        
        final_nodes = []
        for lid in world_ids:
            layout = world_layout.get(lid, {"x": width/2, "y": height/2})
            node = {
                "location_id": lid,
                "label": lid,
                "x": layout["x"],
                "y": layout["y"],
                "scope": loc_map[lid].get("scope"),
                "kind": loc_map[lid].get("kind"),
                "type": loc_map[lid].get("kind"),
                "parent_id": loc_map[lid].get("parent_id"),
                "description": loc_map[lid].get("description"),
                "desc": loc_map[lid].get("description")
            }
            
            # Sub-map
            children = sub_groups.get(lid, [])
            if children:
                child_set = set(children)
                child_constraints = [r for r in relations + route_edges if r["a"] in child_set and r["b"] in child_set]
                child_layout = self._layout_nodes(children, child_constraints, 1000, 1000)
                
                sub_nodes = []
                for child_id in children:
                    cl = child_layout.get(child_id, {"x": 500, "y": 500})
                    sub_nodes.append({
                        "id": child_id,
                        "location_id": child_id,
                        "label": child_id,
                        "x": cl["x"],
                        "y": cl["y"],
                        "scope": loc_map[child_id].get("scope"),
                        "kind": loc_map[child_id].get("kind"),
                        "type": loc_map[child_id].get("kind"),
                        "parent_id": loc_map[child_id].get("parent_id"),
                        "description": loc_map[child_id].get("description"),
                        "desc": loc_map[child_id].get("description")
                    })
                
                sub_edges = [{"source": r["a"], "target": r["b"], "type": r["type"]} for r in child_constraints]
                
                # Collect events for this sub-map
                sub_events = []
                if events:
                    for ev in events:
                        if ev.get("location_id") in child_set:
                            # Ensure description field exists for frontend compatibility
                            ev_copy = ev.copy()
                            if "summary" in ev_copy and "description" not in ev_copy:
                                ev_copy["description"] = ev_copy["summary"]
                            sub_events.append(ev_copy)

                node["sub_map"] = {
                    "nodes": sub_nodes,
                    "edges": sub_edges,
                    "events": sub_events,
                    "width": 1000,
                    "height": 1000
                }
                node["has_sub_map"] = True
            final_nodes.append(node)

        # Polylines
        node_xy = {n["location_id"]: (n["x"], n["y"]) for n in final_nodes}
        def get_world_pos(lid):
            if lid in node_xy: return node_xy[lid]
            pid = parent_map.get(lid)
            if pid and pid in node_xy: return node_xy[pid]
            return None

        polylines = []
        for track in tracks:
            character = track.get("character")
            for seg in track.get("segments") or []:
                a = seg.get("from_location")
                b = seg.get("to_location")
                pos_a = get_world_pos(a)
                pos_b = get_world_pos(b)
                if pos_a and pos_b and pos_a != pos_b:
                    polylines.append({
                        "character": character,
                        "from_location": a,
                        "to_location": b,
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [[pos_a[0], pos_a[1]], [pos_b[0], pos_b[1]]]
                        }
                    })

        return {
            "world": {"name": world_name, "width": width, "height": height},
            "nodes": final_nodes,
            "edges": [r for r in relations if r["a"] in world_ids and r["b"] in world_ids],
            "polylines": polylines
        }

    def preprocess_text(self, text: str) -> str:
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = re.sub(r'\n{3,}', '\n\n', text)
        lines = [line.strip() for line in text.split('\n')]
        return '\n'.join(lines).strip()

    def _chunk_text(self, text: str, chunk_size: int = 2000, overlap: int = 400) -> List[str]:
        if len(text) <= chunk_size:
            return [text] if text.strip() else []

        chunks: List[str] = []
        start = 0
        text_len = len(text)
        separators = ['\n\n', '。', '！', '？', '.\n', '!\n', '?\n', '. ', '! ', '? ']

        while start < text_len:
            end = min(start + chunk_size, text_len)
            if end < text_len:
                search_text = text[start:end]
                last_sep = search_text.rfind('\n\n')
                if last_sep != -1 and last_sep > chunk_size * 0.5:
                    end = start + last_sep + 2
                else:
                    for sep in separators[1:]:
                        last_sep = search_text.rfind(sep)
                        if last_sep != -1 and last_sep > chunk_size * 0.5:
                            end = start + last_sep + len(sep)
                            break

            chunk = text[start:end].strip()
            if chunk and len(chunk) > 10:
                chunks.append(chunk)

            if end >= text_len:
                break
            start = max(0, end - overlap)

        return chunks

    def _split_chapters(self, text: str) -> List[Tuple[str, str]]:
        lines = text.split('\n')
        chapter_header = re.compile(r'^\s*(第[0-9零一二三四五六七八九十百千万]+[章节卷回部].*|Chapter\s+\d+.*)\s*$',
                                   re.IGNORECASE)

        positions: List[Tuple[int, str]] = []
        for idx, line in enumerate(lines):
            if chapter_header.match(line):
                positions.append((idx, line.strip()))

        if len(positions) < 2:
            return [("全文", text)]

        chapters: List[Tuple[str, str]] = []
        for i, (start_idx, title) in enumerate(positions):
            end_idx = positions[i + 1][0] if i + 1 < len(positions) else len(lines)
            body = '\n'.join(lines[start_idx + 1:end_idx]).strip()
            if body:
                chapters.append((title, body))

        return chapters if chapters else [("全文", text)]

    def _normalize_location_name(self, value: Any) -> Optional[str]:
        if not isinstance(value, str):
            return None
        name = value.strip().strip('“”"\'')
        return name if name else None

    def _normalize_extraction_result(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return {"locations": [], "events": []}

        locations = data.get('locations') or []
        events = data.get('events') or []
        if not isinstance(locations, list):
            locations = []
        if not isinstance(events, list):
            events = []

        norm_locations: List[Dict[str, Any]] = []
        for loc in locations:
            if not isinstance(loc, dict):
                continue
            lid = self._normalize_location_name(loc.get('id')) or self._normalize_location_name(loc.get('name'))
            if not lid:
                continue
            aliases_raw = loc.get('aliases') or []
            if isinstance(aliases_raw, str):
                aliases_raw = [aliases_raw]
            aliases: List[str] = []
            for a in aliases_raw:
                an = self._normalize_location_name(a)
                if an and an != lid and an not in aliases:
                    aliases.append(an)
            place_type = (loc.get('place_type') or 'uncertain').strip().lower()
            if place_type not in {'real', 'fictional', 'uncertain'}:
                place_type = 'uncertain'
            desc = loc.get('description')
            desc = desc.strip() if isinstance(desc, str) else ''
            evidence = loc.get('evidence')
            evidence = evidence.strip() if isinstance(evidence, str) else ''
            
            scope = loc.get('scope')
            kind = loc.get('kind')
            parent_id = loc.get('parent_id')

            norm_locations.append({
                "id": lid,
                "aliases": aliases,
                "place_type": place_type,
                "scope": scope,
                "kind": kind,
                "parent_id": parent_id,
                "description": desc,
                "evidence": evidence
            })

        norm_events: List[Dict[str, Any]] = []
        for evt in events:
            if not isinstance(evt, dict):
                continue
            location = self._normalize_location_name(evt.get('location'))
            if not location:
                continue
            characters_raw = evt.get('characters') or []
            if isinstance(characters_raw, str):
                characters_raw = [characters_raw]
            characters: List[str] = []
            for c in characters_raw:
                cn = self._normalize_location_name(c)
                if cn and cn not in characters:
                    characters.append(cn)
            summary = evt.get('summary')
            summary = summary.strip() if isinstance(summary, str) else ''
            evidence = evt.get('evidence')
            evidence = evidence.strip() if isinstance(evidence, str) else ''
            if not summary and not evidence:
                continue

            try:
                order_in_chunk = int(evt.get('order_in_chunk') or 0)
            except Exception:
                order_in_chunk = 0
            chapter_hint = evt.get('chapter_hint')
            chapter_hint = chapter_hint.strip() if isinstance(chapter_hint, str) else ''

            norm_events.append({
                "order_in_chunk": order_in_chunk,
                "chapter_hint": chapter_hint,
                "location": location,
                "characters": characters,
                "summary": summary,
                "evidence": evidence
            })

        return {"locations": norm_locations, "events": norm_events}

    def _mock_extract_chunk(self, chapter_title: str, text: str) -> Dict[str, Any]:
        # Optimized regex patterns for richer extraction
        real_suffixes = r"(?:省|市|县|区|镇|乡|路|街|道|站|机场|港|口岸|大学|学院|医院|公园|广场|桥|大厦|中心|村|胡同|里|弄)"
        real_pat = re.compile(rf'([\u4e00-\u9fff]{2,12}{real_suffixes})')
        
        fictional_suffixes = r"(?:山|宗|门|派|城|谷|殿|宫|岛|界|国|林|洞|峰|海|原|域|府|寨|庄|阁|塔|观|寺|庙|祠|墓|陵|关|隘)"
        fictional_pat = re.compile(rf'([\u4e00-\u9fff]{2,12}{fictional_suffixes})')

        real_hits = real_pat.findall(text)

        fic_hits = fictional_pat.findall(text)
        
        # 简单的人名提取正则：匹配“xx说”、“xx道”、“xx想”前面的2-4字中文
        char_pat = re.compile(r'([\u4e00-\u9fff]{2,4})(?:说|道|想|看|听|问|答|笑|哭|叫|喊|走|跑|飞|跳)')
        char_hits = char_pat.findall(text)
        
        # 过滤掉常见非人名（可以是停用词表，这里简单过滤）
        stopwords = {"自己", "什么", "怎么", "哪里", "虽然", "但是", "因为", "所以", "如果", "突然", "只见", "听见", "看见", "感觉", "觉得", "以为", "正在", "已经", "开始"}
        char_set = []
        for c in char_hits:
            if c not in stopwords and c not in char_set:
                char_set.append(c)
        if not char_set:
            char_set = ["主角"]

        real_set = []
        fic_set = []
        for x in real_hits:
            if x not in real_set:
                real_set.append(x)
        for x in fic_hits:
            if x not in fic_set and x not in real_set:
                fic_set.append(x)

        locations = []
        for name in real_set[:15]:
            locations.append({"id": name, "aliases": [], "place_type": "real", "description": "", "evidence": ""})
        for name in fic_set[:25]:
            locations.append({"id": name, "aliases": [], "place_type": "fictional", "description": "", "evidence": ""})

        events = []
        paras = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
        order = 0
        for p in paras:
            m = real_pat.search(p) or fictional_pat.search(p)
            if not m:
                continue
            order += 1
            loc = m.group(1)
            
            # 尝试从段落中找到角色，如果找不到则随机选一个（为了演示轨迹）
            paragraph_chars = [c for c in char_set if c in p]
            if not paragraph_chars:
                # Mock模式下，为了保证有轨迹，如果段落没提到人，就随机分配给前几个主要角色
                paragraph_chars = [random.choice(char_set[:3])]
                
            events.append({
                "order_in_chunk": order,
                "chapter_hint": chapter_title,
                "location": loc,
                "characters": paragraph_chars,
                "summary": p[:80],
                "evidence": p[:160]
            })
            if order >= 30:
                break

        return self._normalize_extraction_result({"locations": locations, "events": events})

    def _merge_locations(self, results: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
        # 1. Flatten results
        raw_locations = []
        for r in results:
            for loc in r.get('locations') or []:
                if loc.get('id'):
                    raw_locations.append(loc)

        # 2. Union-Find for Aliases
        parent = {}
        def find(i):
            if i not in parent: parent[i] = i
            if parent[i] != i: parent[i] = find(parent[i])
            return parent[i]
        def union(i, j):
            root_i = find(i)
            root_j = find(j)
            if root_i != root_j: parent[root_i] = root_j

        # Register all IDs and aliases
        for loc in raw_locations:
            lid = loc['id']
            find(lid)
            # Normalization check
            if not loc.get('parent_id') and loc.get('parent_location'):
                loc['parent_id'] = self._normalize_location_name(loc.get('parent_location'))
            
            for alias in (loc.get('aliases') or []):
                if alias:
                    union(lid, alias)

        # 3. Group by Root
        groups = {}
        for loc in raw_locations:
            lid = loc['id']
            root = find(lid)
            groups.setdefault(root, []).append(loc)

        # 4. Merge Groups
        merged_locations = []
        alias_to_id = {} # map every alias/original_id to canonical_id

        def type_priority(t: str) -> int:
            return {"fictional": 3, "real": 2, "uncertain": 1}.get(t, 1)

        for root, locs in groups.items():
            # Determine canonical ID: 
            # Prefer the one that appears as 'id' in the most records? 
            # Or the longest name?
            # Or simply the root?
            # Let's count occurrences of IDs
            id_counts = {}
            for l in locs:
                id_counts[l['id']] = id_counts.get(l['id'], 0) + 1
            
            # Sort candidates: frequent first, then length descending
            candidates = sorted(id_counts.keys(), key=lambda x: (-id_counts[x], -len(x)))
            canonical_id = candidates[0]

            # Merge data
            merged = {
                "id": canonical_id,
                "aliases": set(),
                "place_type": "uncertain",
                "scope": None,
                "kind": None,
                "parent_id": None,
                "description": "",
                "evidence": ""
            }

            all_aliases = set()
            
            for l in locs:
                # Add self id as alias if not canonical
                if l['id'] != canonical_id:
                    all_aliases.add(l['id'])
                if l.get('aliases'):
                    all_aliases.update(l.get('aliases'))
                
                # Merge attributes
                if type_priority(l.get('place_type') or 'uncertain') > type_priority(merged['place_type']):
                    merged['place_type'] = l.get('place_type') or 'uncertain'
                
                if not merged['scope'] and l.get('scope'): merged['scope'] = l.get('scope')
                if not merged['kind'] and l.get('kind'): merged['kind'] = l.get('kind')
                if not merged['parent_id'] and l.get('parent_id'): merged['parent_id'] = l.get('parent_id')
                
                if l.get('description'):
                    desc = l.get('description')
                    if desc not in merged['description']:
                         merged['description'] = (merged['description'] + " " + desc).strip()
                
                if l.get('evidence') and not merged['evidence']: merged['evidence'] = l.get('evidence')

            # Clean aliases
            if canonical_id in all_aliases: all_aliases.remove(canonical_id)
            merged['aliases'] = sorted(list(all_aliases))
            
            # Populate alias_to_id
            alias_to_id[canonical_id] = canonical_id
            for a in all_aliases:
                alias_to_id[a] = canonical_id
            # Also map all original IDs in this group to canonical_id
            for l in locs:
                alias_to_id[l['id']] = canonical_id

            merged_locations.append(merged)

        # Sort
        merged_locations.sort(key=lambda x: (x.get("place_type") != "fictional", x.get("id")))

        for loc in merged_locations:
            pid = loc.get("parent_id")
            if not pid:
                continue
            pid = alias_to_id.get(pid, pid)
            if pid == loc.get("id"):
                loc["parent_id"] = None
            else:
                loc["parent_id"] = pid

        return merged_locations, alias_to_id

    def _merge_events(self, results: List[Dict[str, Any]], alias_to_id: Dict[str, str], chunk_order: List[str]) -> List[Dict[str, Any]]:
        merged_events: List[Dict[str, Any]] = []
        seen_keys: set = set()

        def norm_text(s: str) -> str:
            s = (s or '').strip().lower()
            s = re.sub(r'\s+', ' ', s)
            return s

        for chunk_id in chunk_order:
            r = next((x for x in results if x.get("_chunk_id") == chunk_id), None)
            if not r:
                continue
            for evt in r.get("events") or []:
                loc_raw = evt.get("location")
                loc_id = alias_to_id.get(loc_raw, loc_raw)
                chars = evt.get("characters") or []
                chars_key = '|'.join(sorted([norm_text(c) for c in chars if c]))
                summary_key = norm_text(evt.get("summary") or '')[:60]
                key = (loc_id, chars_key, summary_key, norm_text(evt.get("evidence") or '')[:60])
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                merged_events.append({
                    "id": f"evt_{uuid.uuid4().hex[:12]}",
                    "order_in_chunk": evt.get("order_in_chunk") or 0,
                    "chapter_hint": evt.get("chapter_hint") or '',
                    "location_id": loc_id,
                    "location_raw": loc_raw,
                    "characters": chars,
                    "summary": evt.get("summary") or '',
                    "evidence": evt.get("evidence") or '',
                    "_chunk_id": chunk_id
                })

        merged_events.sort(key=lambda e: (chunk_order.index(e["_chunk_id"]), int(e.get("order_in_chunk") or 0)))
        for idx, e in enumerate(merged_events, start=1):
            e["order"] = idx
        return merged_events

    def _build_tracks(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_character: Dict[str, List[Dict[str, Any]]] = {}
        for e in events:
            for c in e.get("characters") or []:
                by_character.setdefault(c, []).append(e)

        tracks = []
        for character, evts in by_character.items():
            evts = sorted(evts, key=lambda x: x.get("order") or 0)
            segments = []
            prev = None
            for e in evts:
                if prev is None:
                    prev = e
                    continue
                if prev.get("location_id") != e.get("location_id"):
                    segments.append({
                        "from_location": prev.get("location_id"),
                        "to_location": e.get("location_id"),
                        "from_event": prev.get("id"),
                        "to_event": e.get("id"),
                        "chapter_range": f"{prev.get('chapter_hint','')}".strip() or None,
                        "summary": (e.get("summary") or '').strip(),
                        "evidence": (e.get("evidence") or '').strip()
                    })
                prev = e

            tracks.append({"character": character, "segments": segments})

        tracks.sort(key=lambda t: (-len(t.get("segments") or []), t.get("character") or ''))
        
        # 简单的主角判定逻辑：轨迹段数最多的前 1-3 名通常是主角
        # 为前端增加一个 is_main_char 标记，方便展示
        if tracks:
            max_segs = len(tracks[0].get("segments") or [])
            for t in tracks:
                seg_count = len(t.get("segments") or [])
                # 如果段数超过最大段数的 50%，或者绝对段数超过 10，或者是第一名，都算主要角色
                is_main = (seg_count == max_segs) or (seg_count > max_segs * 0.5 and seg_count >= 5)
                t["is_main_char"] = is_main

        return tracks

    def analyze_text(self, text: str, session_id: Optional[str] = None, run_async: bool = True) -> Dict[str, Any]:
        if not session_id:
            session_id = f"trace_{uuid.uuid4().hex[:12]}"

        self.sessions[session_id] = {
            "status": "processing",
            "status_msg": "正在解析文本...",
            "progress": 0,
            "created_at": datetime.now().isoformat(),
            "result": None,
            "error": None
        }

        if run_async:
            threading.Thread(target=self._run_analysis, args=(session_id, text), daemon=True).start()
        else:
            self._run_analysis(session_id, text)

        return {
            "success": True,
            "session_id": session_id,
            "status_url": f"/api/trace/status/{session_id}"
        }

    def _run_analysis(self, session_id: str, text: str) -> None:
        try:
            mock_mode = (os.getenv("TRACE_MOCK") or "").strip().lower() in {"1", "true", "yes"}
            text = self.preprocess_text(text)
            chapters = self._split_chapters(text)

            chunk_size_env = os.getenv("TRACE_CHUNK_SIZE")
            overlap_env = os.getenv("TRACE_CHUNK_OVERLAP")
            try:
                chunk_size = int(chunk_size_env) if chunk_size_env else 2000
            except Exception:
                chunk_size = 2000
            try:
                overlap = int(overlap_env) if overlap_env else 200
            except Exception:
                overlap = 200

            chunks: List[Dict[str, Any]] = []
            for chapter_idx, (title, body) in enumerate(chapters, start=1):
                sub_chunks = self._chunk_text(body, chunk_size=chunk_size, overlap=overlap)
                for part_idx, sub in enumerate(sub_chunks, start=1):
                    chunks.append({
                        "chunk_id": f"ch{chapter_idx:04d}_p{part_idx:03d}",
                        "chapter_title": title,
                        "text": sub
                    })

            total_chunks = len(chunks)
            if total_chunks == 0:
                raise ValueError("文本内容为空或无法分割")

            self.sessions[session_id]["status_msg"] = f"文本已切分为 {total_chunks} 个片段，准备并行提取..."
            logger.info(f"Session {session_id}: Split into {total_chunks} chunks")

            extractor_prompt = get_trace_extractor_prompt()

            def process_chunk(chunk: Dict[str, Any]) -> Dict[str, Any]:
                if mock_mode:
                    normalized = self._mock_extract_chunk(chunk.get("chapter_title") or "", chunk.get("text") or "")
                    normalized["_chunk_id"] = chunk["chunk_id"]
                    return normalized
                messages = [
                    {"role": "system", "content": extractor_prompt},
                    {"role": "user", "content": f"章节信息：{chunk['chapter_title']}\n\n请分析以下文本片段（{chunk['chunk_id']}）：\n\n{chunk['text']}"}
                ]
                raw = self.llm.chat_json(messages, temperature=0.1, use_boost=True)
                normalized = self._normalize_extraction_result(raw)
                normalized["_chunk_id"] = chunk["chunk_id"]
                return normalized

            extracted_results: List[Dict[str, Any]] = []
            completed = 0

            max_workers_env = os.getenv("TRACE_EXTRACT_MAX_WORKERS")
            try:
                env_workers = int(max_workers_env) if max_workers_env else 0
            except Exception:
                env_workers = 0
            if env_workers > 0:
                max_workers = env_workers
            else:
                # 激进并发策略，适配高性能 API (如 DeepSeek)
                if total_chunks <= 50:
                    max_workers = total_chunks
                elif total_chunks <= 200:
                    max_workers = 50
                else:
                    max_workers = 64  # 避免过高导致系统资源耗尽或严重的 429
            max_workers = max(1, max_workers)

            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(process_chunk, c): c for c in chunks}
                for future in concurrent.futures.as_completed(futures):
                    try:
                        res = future.result()
                        if (res.get("locations") or []) or (res.get("events") or []):
                            extracted_results.append(res)
                    except Exception as e:
                        logger.error(f"Chunk processing failed: {e}")
                    finally:
                        completed += 1
                        progress = min(int((completed / total_chunks) * 90), 89)
                        self.sessions[session_id]["progress"] = progress
                        self.sessions[session_id]["status_msg"] = f"正在提取足迹: 已完成 {completed}/{total_chunks} 个片段..."

            if not extracted_results:
                raise RuntimeError("未能从文本中提取出有效信息")

            self.sessions[session_id]["status"] = "aggregating"
            self.sessions[session_id]["status_msg"] = "正在合并地点与事件..."
            self.sessions[session_id]["progress"] = 90

            chunk_order = [c["chunk_id"] for c in chunks]

            merged_locations, alias_to_id = self._merge_locations(extracted_results)
            for loc in merged_locations:
                if loc.get("place_type") == "uncertain":
                    heuristic = self._heuristic_place_type(loc.get("id") or "")
                    if heuristic:
                        loc["place_type"] = heuristic

            # LLM Classification for Scope/Kind/Parent
            context_map = self._compute_location_context(merged_locations, extracted_results, alias_to_id)
            merged_locations = self._classify_locations_with_llm(merged_locations, session_id=session_id, context_map=context_map)
            self._assign_parent_fallback(merged_locations, context_map, alias_to_id)

            merged_events = self._merge_events(extracted_results, alias_to_id, chunk_order)
            tracks = self._build_tracks(merged_events)

            self._geocode_locations(merged_locations, session_id=session_id)
            # Flush geocoding cache to disk
            if self._geocoder:
                self._geocoder.flush()

            real_map = self._build_real_map(merged_locations, tracks)
            
            # Pass merged_events to include event data in sub-maps
            fictional_map = self._build_fictional_map(merged_locations, tracks, events=merged_events, session_id=session_id)

            result = {
                "locations": merged_locations,
                "events": [
                    {k: v for k, v in e.items() if not k.startswith("_")}
                    for e in merged_events
                ],
                "tracks": tracks,
                "maps": {
                    "real_map": real_map,
                    "fictional_map": fictional_map
                },
                "overview": {
                    "location_count": len(merged_locations),
                    "event_count": len(merged_events),
                    "character_count": len({c for e in merged_events for c in (e.get("characters") or [])})
                }
            }

            self.sessions[session_id]["result"] = result
            self.sessions[session_id]["status"] = "completed"
            self.sessions[session_id]["progress"] = 100
            self.sessions[session_id]["status_msg"] = "分析完成"

        except Exception as e:
            logger.error(f"Analysis failed for session {session_id}: {str(e)}")
            self.sessions[session_id]["status"] = "failed"
            self.sessions[session_id]["error"] = str(e)
            self.sessions[session_id]["status_msg"] = "分析过程中发生错误"

    def get_session_status(self, session_id: str) -> Dict[str, Any]:
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
