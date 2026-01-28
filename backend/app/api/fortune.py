"""
命理推演 API
提供推演启动、状态查询、报告获取等接口
"""

from flask import request, jsonify
from . import fortune_bp
from ..services.fortune_service import FortuneService
from ..utils.logger import get_logger

logger = get_logger('wannian.api.fortune')
print("DEBUG: Fortune API is being loaded!")
fortune_service = FortuneService()

@fortune_bp.route('/analyze', methods=['POST'])
def analyze_fate():
    """
    启动命理分析
    请求体: {name, birthday, birth_time, birth_location, gender}
    """
    try:
        data = request.get_json()
        required = ['name', 'birthday', 'birth_time', 'birth_location', 'gender']
        if not all(k in data for k in required):
            return jsonify({"success": False, "error": f"缺少必要参数: {required}"}), 400
            
        result = fortune_service.analyze_fate(
            name=data['name'],
            birthday=data['birthday'],
            birth_time=data['birth_time'],
            birth_location=data['birth_location'],
            gender=data['gender'],
            future_years=int(data.get('future_years', 3))
        )
        return jsonify(result)
    except Exception as e:
        logger.error(f"分析请求失败: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@fortune_bp.route('/status/<session_id>', methods=['GET'])
def get_status(session_id):
    """查询分析进度"""
    result = fortune_service.get_session_status(session_id)
    return jsonify(result)

@fortune_bp.route('/report/<session_id>', methods=['GET'])
def get_report(session_id):
    """获取完整报告内容"""
    result = fortune_service.get_full_report(session_id)
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
