"""
命理推演 API
提供推演启动、状态查询、报告获取等接口
"""

from flask import request, jsonify
from . import fortune_bp
from ..services.fortune_service import FortuneService
from ..utils.logger import get_logger

logger = get_logger('wannian.api.fortune')

# 延迟初始化 Service，以便在请求时检查配置
_fortune_service = None

def get_fortune_service():
    global _fortune_service
    if _fortune_service is None:
        _fortune_service = FortuneService()
    return _fortune_service

@fortune_bp.route('/analyze', methods=['POST'])
def analyze_fate():
    """
    启动命理分析
    请求体: {name, birthday, birth_time, birth_location, gender}
    """
    try:
        # 1. 检查 API Key 配置
        from ..config import Config
        config_errors = Config.validate()
        if config_errors:
            return jsonify({
                "success": False, 
                "error": "配置缺失", 
                "details": config_errors,
                "hint": "请在项目根目录创建 .env 文件并配置 LLM_API_KEY。具体参考 .env.example 文件。"
            }), 400

        data = request.get_json()
        required = ['name', 'birthday', 'birth_time', 'birth_location', 'gender']
        if not all(k in data for k in required):
            return jsonify({"success": False, "error": f"缺少必要参数: {required}"}), 400
            
        service = get_fortune_service()
        result = service.analyze_fate(
            name=data['name'],
            birthday=data['birthday'],
            birth_time=data['birth_time'],
            birth_location=data['birth_location'],
            gender=data['gender'],
            future_years=int(data.get('future_years', 3))
        )
        return jsonify(result)
    except ValueError as ve:
        # 捕获 LLMClient 初始化时的 ValueError (如 API Key 缺失)
        logger.error(f"配置错误: {str(ve)}")
        return jsonify({
            "success": False, 
            "error": str(ve),
            "hint": "请检查 .env 文件中的 LLM_API_KEY 配置"
        }), 400
    except Exception as e:
        logger.error(f"分析请求失败: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@fortune_bp.route('/status/<session_id>', methods=['GET'])
def get_status(session_id):
    """查询分析进度"""
    service = get_fortune_service()
    result = service.get_session_status(session_id)
    return jsonify(result)

@fortune_bp.route('/report/<session_id>', methods=['GET'])
def get_report(session_id):
    """获取完整报告内容"""
    service = get_fortune_service()
    result = service.get_full_report(session_id)
    return jsonify(result)

@fortune_bp.route('/masters', methods=['GET'])
def list_masters():
    """获取大师列表（前端展示用）"""
    from ..services.fortune_agents import MASTER_PERSONAS
    return jsonify({
        "success": True,
        "data": [
            {
                "id": p["id"],
                "name": p["name"],
                "camp": p["camp"],
                "role": p["role"],
                "description": p.get("description", ""),
                "methodology": p.get("methodology", "")
            } for p in MASTER_PERSONAS
        ]
    })
