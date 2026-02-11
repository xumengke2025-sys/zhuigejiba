"""
API路由模块
"""

from flask import Blueprint

trace_bp = Blueprint('trace', __name__)

from . import trace  # noqa: E402, F401
