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
    title_cn: Optional[str] = None
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


class LocalVideoItem(BaseModel):
    """单个本地视频项"""
    id: int
    path: str
    size: Optional[int] = None
    duration: Optional[int] = None
    codec: Optional[str] = None
    is_scraped: Optional[int] = None


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
    # 来源信息
    source: Optional[str] = None  # scraped/jellyfin/manual
    source_type: Optional[str] = None  # web/jellyfin/local
    video_path: Optional[str] = None  # 实际视频文件路径
    # 刮削状态（动态计算）
    scrape_status: Optional[str] = None
    # 所有关联的本地视频（一对多）
    local_videos: Optional[List[LocalVideoItem]] = None


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


# ========== 认证相关模型 ==========

class UserLogin(BaseModel):
    """用户登录请求"""
    username: str
    password: str


class UserRegister(BaseModel):
    """用户注册请求"""
    username: str
    password: str
    email: Optional[str] = None


class UserResponse(BaseModel):
    """用户信息响应"""
    id: int
    username: str
    role: str
    email: Optional[str] = None
    created_at: str
    last_login: Optional[str] = None


class LoginResponse(BaseModel):
    """登录响应"""
    token: str
    user: UserResponse


class LocalVideoListResponse(BaseModel):
    """本地视频列表响应"""
    total: int
    page: int
    page_size: int
    items: List[dict]


class ActorItem(BaseModel):
    """女演员统计项"""
    name: str
    count: int
    has_avatar: bool = False


class SeriesItem(BaseModel):
    """番号系列统计项"""
    prefix: str
    count: int


class ActorListResponse(BaseModel):
    """女演员列表响应"""
    total: int
    page: int
    page_size: int
    items: List[ActorItem]


class SeriesListResponse(BaseModel):
    """番号系列列表响应"""
    total: int
    page: int
    page_size: int
    items: List[SeriesItem]


class CategoryMoviesResponse(BaseModel):
    """类别详情页影片列表"""
    total: int
    page: int
    page_size: int
    items: List[MovieResponse]
