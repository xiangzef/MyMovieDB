"""
数据模型定义
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class MovieBase(BaseModel):
    """影片基础模型"""
    code: str                    # 影片编号，如 MIUM-1211
    title: str                   # 影片标题
    title_jp: Optional[str] = None  # 日文标题
    release_date: Optional[str] = None  # 发布日期
    duration: Optional[int] = None  # 时长（分钟）
    studio: Optional[str] = None  # 制作商
    maker: Optional[str] = None  # 片商
    director: Optional[str] = None  # 导演
    cover_url: Optional[str] = None  # 封面图 URL
    preview_url: Optional[str] = None  # 预览图 URL
    genres: List[str] = []       # 类别标签
    actors: List[str] = []       # 演员（女优）
    actors_male: List[str] = []  # 男优


class MovieCreate(MovieBase):
    """创建影片时的输入模型"""
    pass


class MovieResponse(MovieBase):
    """影片响应模型"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScrapeRequest(BaseModel):
    """刮削请求"""
    keyword: str  # 搜索关键词，如影片编号 MIUM-1211
    save_cover: bool = True  # 是否保存封面图到本地


class ScrapeResponse(BaseModel):
    """刮削响应"""
    success: bool
    message: str
    movie: Optional[MovieResponse] = None


class MovieListResponse(BaseModel):
    """影片列表响应"""
    total: int
    page: int
    page_size: int
    items: List[MovieResponse]
