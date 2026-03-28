"""
数据模型定义
Pydantic v2 兼容，所有可选字段均用 | None 语法，extra='ignore' 防止意外字段报错
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


class MovieBase(BaseModel):
    """影片基础模型"""
    model_config = ConfigDict(extra='ignore')

    code: str
    title: str
    title_jp: str | None = None
    release_date: str | None = None
    duration: int | None = None
    studio: str | None = None
    maker: str | None = None
    director: str | None = None
    cover_url: str | None = None
    preview_url: str | None = None
    genres: List[str] | None = None
    actors: List[str] | None = None
    actors_male: List[str] | None = None


class MovieCreate(MovieBase):
    """创建影片时的输入模型"""
    pass


class MovieResponse(MovieBase):
    """影片响应模型"""
    id: int
    created_at: datetime
    updated_at: datetime
    local_video_id: int | None = None
    # 本地多图路径（来自 local_videos 表的 LEFT JOIN 关联）
    fanart_path: str | None = None
    poster_path: str | None = None
    thumb_path: str | None = None


class ScrapeRequest(BaseModel):
    """刮削请求"""
    keyword: str
    save_cover: bool = True


class ScrapeResponse(BaseModel):
    """刮削响应"""
    success: bool
    message: str
    movie: MovieResponse | None = None


class MovieListResponse(BaseModel):
    """影片列表响应"""
    total: int
    page: int
    page_size: int
    items: List[MovieResponse]
