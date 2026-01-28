"""
命理分析工具类
负责日期转换（公历到农历、干支）及数据归一化
"""

from datetime import datetime
from typing import Dict, Any, List

class FortuneUtils:
    """命理转换工具"""
    
    # 十天干
    GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
    # 十二地支
    ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
    # 十二生肖
    SHENGXIAO = ["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]
    
    @classmethod
    def get_year_gan_zhi(cls, year: int) -> str:
        """获取年份的干支"""
        # 公元4年是甲子年
        offset = (year - 4) % 60
        gan_index = offset % 10
        zhi_index = offset % 12
        return f"{cls.GAN[gan_index]}{cls.ZHI[zhi_index]}"

    @classmethod
    def get_shengxiao(cls, year: int) -> str:
        """获取生肖"""
        offset = (year - 4) % 12
        return cls.SHENGXIAO[offset]

    @classmethod
    def normalize_input(
        cls, 
        name: str,
        birthday: str, 
        birth_time: str, 
        birth_location: str, 
        gender: str
    ) -> Dict[str, Any]:
        """
        将原始输入归一化为多种命理格式
        
        Args:
            name: 用户姓名
            birthday: 公历生日 (YYYY-MM-DD)
            birth_time: 出生时间 (HH:mm)
            birth_location: 出生地点
            gender: 性别 (男/女)
            
        Returns:
            归一化后的数据字典
        """
        try:
            dt = datetime.strptime(f"{birthday} {birth_time}", "%Y-%m-%d %H:%M")
            year = dt.year
            
            # 基本干支计算（简化版，实际应考虑节气和月份）
            # 注意：这只是一个基础版本，复杂的转换建议使用 lunar-python 库
            year_gz = cls.get_year_gan_zhi(year)
            sx = cls.get_shengxiao(year)
            
            return {
                "name": name,
                "birthday": birthday,
                "birth_time": birth_time,
                "birth_location": birth_location,
                "gender": gender,
                "year_gan_zhi": year_gz,
                "shengxiao": sx,
                "solar_datetime": dt.isoformat(),
                # 占位符：在实际系统中应由专门的库计算
                "lunar_date": "（农历转换暂未集成，请以公历为准）",
                "stem_branch_month": "（月干支计算需节气信息）",
                "stem_branch_day": "（日干支计算需精确算法）",
                "stem_branch_hour": "（时干支由日干支推导）"
            }
        except Exception as e:
            return {
                "error": str(e),
                "name": name,
                "birthday": birthday,
                "birth_time": birth_time,
                "birth_location": birth_location,
                "gender": gender
            }
