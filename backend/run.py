"""
万年 Backend 启动入口
"""

import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.config import Config


def main():
    """主函数"""
    # 验证配置
    errors = Config.validate()
    if errors:
        print("\n" + "="*50)
        print("❌ 启动失败: 配置缺失")
        for err in errors:
            print(f"  - {err}")
        print("\n请确保根目录下的 .env 文件已正确配置。")
        print("可以参考 .env.example 文件进行创建。")
        print("="*50 + "\n")
        sys.exit(1)
    
    # 创建应用
    app = create_app()
    
    # 获取运行配置
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5002))
    debug = Config.DEBUG
    
    # 启动服务
    # 禁用 reloader，因为后台线程会在 reloader 重启时丢失
    app.run(host=host, port=port, debug=debug, threaded=True, use_reloader=False)


if __name__ == '__main__':
    main()

