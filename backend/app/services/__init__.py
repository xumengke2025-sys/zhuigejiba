"""
业务服务模块
"""

from .fortune_service import FortuneService
from .fortune_aggregator import FortuneAggregator

__all__ = [
    'FortuneService',
    'FortuneAggregator'
]
