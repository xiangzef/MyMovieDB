"""
数据模型定义
Python 3.7 兼容，所有可选字段均用 Optional[] 语法，extra='ignore' 防止意外字段报错
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


class MovieBase(BaseModel):
    """影片基础模型"""
    model_config = ConfigDict(extra='ignore')

    code: str
    title: str
    title_jp: Optional[str] = None
    release_date: Optional[str] = None
    duration: Optional[int] = None
    studio: Optional[str] = None
    maker: Optional[str] = None
    director: Optional[str] = None
    cover_url: Optional[str] = None
    preview_url: Optional[str] = None
    genres: Optional[List[str]] = None
    actors: Optional[List[str]] = None
    actors_male: Optional[List[str]] = None


class MovieCreate(MovieBase):
    """创建影片时的输入模型"""
    pass


class MovieResponse(MovieBase):
    """影片响应模型"""
    id: int
    created_at: datetime
    updated_at: datetime
    local_video_id: Optional[int] = None
    # 本地多图路径（来自 local_videos 表的 LEFT JOIN 关联）
    fanart_path: Optional[str] = None
    poster_path: Optional[str] = None
    thumb_path: Optional[str] = None
    local_video_path: Optional[str] = None  # 本地视频文件路径
    # 刮削状态（动态计算）
    scrape_status: Optional[str] = None


class ScrapeRequest(BaseModel):
    """刮削请求"""
    keyword: str
    save_cover: bool = True


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
