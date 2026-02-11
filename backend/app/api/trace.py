"""
追迹分析 API
提供文本上传、分析启动、状态查询等接口
"""

from flask import request, jsonify

from . import trace_bp
from ..services.trace_service import TraceService
from ..utils.logger import get_logger

logger = get_logger('footprints.api.trace')

_trace_service = None


def get_trace_service() -> TraceService:
    global _trace_service
    if _trace_service is None:
        _trace_service = TraceService()
        logger.info("TraceService 初始化成功")
    return _trace_service


@trace_bp.route('/analyze', methods=['POST'])
def analyze_text():
    """
    启动文本分析
    支持 JSON {"text": "..."} 或 文件上传 multipart/form-data
    """
    logger.info(f"收到分析请求: {request.method} {request.path}, Content-Type: {request.content_type}")
    try:
        from ..config import Config

        import os
        mock_mode = (os.getenv("TRACE_MOCK") or "").strip().lower() in {"1", "true", "yes"}
        if not mock_mode:
            config_errors = Config.validate()
            if config_errors:
                return jsonify({
                    "success": False,
                    "error": "配置缺失",
                    "details": config_errors,
                    "hint": "请在项目根目录创建 .env 文件并配置 LLM_API_KEY。"
                }), 400

        text_content = ""

        if 'file' in request.files:
            file = request.files['file']
            if not file or not file.filename.endswith('.txt'):
                return jsonify({"success": False, "error": "仅支持 .txt 文件"}), 400

            try:
                content_bytes = file.read(Config.MAX_CONTENT_LENGTH)
                # 移除 latin-1，因为它会“成功”解码所有字节导致乱码，从而掩盖真正的 GBK/UTF-8 问题
                encodings = ['utf-8-sig', 'utf-8', 'gb18030', 'gbk', 'big5']
                for enc in encodings:
                    try:
                        text_content = content_bytes.decode(enc)
                        # 简单的启发式检查：如果解码后包含太多乱码字符（�），则认为失败
                        if text_content.count('�') > len(text_content) * 0.1:
                            continue
                        logger.info(f"成功使用 {enc} 编码读取文件: {file.filename}")
                        break
                    except UnicodeDecodeError:
                        continue
                
                if not text_content:
                    # 如果常见编码都失败了，再尝试使用 errors='replace' 的 utf-8，至少保证程序不崩
                    text_content = content_bytes.decode('utf-8', errors='replace')
                    logger.warning(f"所有指定编码均失败，使用 utf-8 (replace) 读取文件: {file.filename}")
            except Exception as e:
                logger.error(f"文件读取失败: {str(e)}")
                return jsonify({"success": False, "error": f"文件读取失败: {str(e)}"}), 400
        elif request.is_json:
            data = request.get_json() or {}
            text_content = data.get('text', '')

        if not text_content or len(text_content.strip()) == 0:
            return jsonify({"success": False, "error": "文本内容不能为空"}), 400

        if len(text_content) > 3000000:
            return jsonify({"success": False, "error": "文本过长，目前仅支持 300 万字以内的文本"}), 400

        service = get_trace_service()
        result = service.analyze_text(text_content)
        return jsonify(result)

    except Exception as e:
        logger.error(f"分析请求失败: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@trace_bp.route('/status/<session_id>', methods=['GET'])
def get_status(session_id: str):
    service = get_trace_service()
    result = service.get_session_status(session_id)
    return jsonify(result)


@trace_bp.route('/sample', methods=['GET'])
def get_sample_data():
    """
    获取样例数据（Demo）
    """
    try:
        import os
        import json
        
        # 假设 sample_trace.json 位于 backend/app/data/sample_trace.json
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sample_path = os.path.join(base_dir, 'data', 'sample_trace.json')
        
        if not os.path.exists(sample_path):
            return jsonify({"success": False, "error": "样例数据文件不存在"}), 404
            
        with open(sample_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        return jsonify({
            "success": True,
            "session_id": "sample_demo_session",
            "status": "completed",
            "result": data
        })
    except Exception as e:
        logger.error(f"获取样例数据失败: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

