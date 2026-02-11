"""
人物关系梳理 API
提供文本上传、分析启动、状态查询等接口
"""

from flask import request, jsonify
from . import fortune_bp
from ..services.relationship_service import RelationshipService
from ..utils.logger import get_logger

logger = get_logger('wannian.api.relationship')

# 延迟初始化 Service
_relationship_service = None

def get_relationship_service():
    global _relationship_service
    if _relationship_service is None:
        try:
            _relationship_service = RelationshipService()
            logger.info("RelationshipService 初始化成功")
        except Exception as e:
            logger.error(f"RelationshipService 初始化失败: {str(e)}")
            raise
    return _relationship_service

@fortune_bp.route('/analyze', methods=['POST'])
def analyze_text():
    """
    启动文本分析
    支持 JSON {"text": "..."} 或 文件上传 multipart/form-data
    """
    logger.info(f"收到分析请求: {request.method} {request.path}, Content-Type: {request.content_type}")
    try:
        # 1. 检查 API Key 配置
        from ..config import Config
        config_errors = Config.validate()
        if config_errors:
            return jsonify({
                "success": False, 
                "error": "配置缺失", 
                "details": config_errors,
                "hint": "请在项目根目录创建 .env 文件并配置 LLM_API_KEY。"
            }), 400

        text_content = ""
        
        # 处理文件上传
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename.endswith('.txt'):
                try:
                    # 参考“参商”优化的文件读取：支持多编码
                    content_bytes = file.read(Config.MAX_CONTENT_LENGTH)
                    text_content = ""
                    encodings = ['utf-8-sig', 'utf-8', 'gbk', 'gb18030', 'latin-1']
                    
                    for enc in encodings:
                        try:
                            text_content = content_bytes.decode(enc)
                            logger.info(f"成功使用 {enc} 编码读取文件: {file.filename}")
                            break
                        except UnicodeDecodeError:
                            continue
                    
                    if not text_content:
                        # 最后的保底方案
                        text_content = content_bytes.decode('utf-8', errors='ignore')
                        logger.warning(f"所有指定编码均失败，使用 utf-8 (ignore) 读取文件: {file.filename}")
                    
                    logger.info(f"文件读取完成, 长度: {len(text_content)}")
                except Exception as e:
                    logger.error(f"文件读取失败: {str(e)}")
                    return jsonify({"success": False, "error": f"文件读取失败: {str(e)}"}), 400
            else:
                return jsonify({"success": False, "error": "仅支持 .txt 文件"}), 400
        # 处理 JSON 文本
        elif request.is_json:
            data = request.get_json()
            text_content = data.get('text', '')
        
        if not text_content or len(text_content.strip()) == 0:
            return jsonify({"success": False, "error": "文本内容不能为空"}), 400

        # 限制文本长度（提升至 300 万字以支持长篇小说）
        if len(text_content) > 3000000:
             return jsonify({"success": False, "error": "文本过长，目前仅支持 300 万字以内的文本"}), 400

        service = get_relationship_service()
        result = service.analyze_text(text_content)
        return jsonify(result)

    except ValueError as ve:
        logger.error(f"配置错误: {str(ve)}")
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.error(f"分析请求失败: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@fortune_bp.route('/status/<session_id>', methods=['GET'])
def get_status(session_id):
    """查询分析进度"""
    service = get_relationship_service()
    result = service.get_session_status(session_id)
    return jsonify(result)
