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
    # 字幕类型（整理功能）
    subtitle_type: Optional[str] = "none"
    # 整理路径
    organized_path: Optional[str] = None
    last_organized_at: Optional[datetime] = None
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
    local_url: Optional[str] = None  # 头像 URL，直接返回给前端


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


# ========== 整理功能（Phase 0.5）============

from enum import Enum


class SubtitleType(str, Enum):
    """字幕类型枚举"""
    NONE = "none"        # 无字幕
    CHINESE = "chinese"  # 中文字幕
    ENGLISH = "english"  # 英文字幕
    BILINGUAL = "bilingual"  # 双语字幕


# 字幕类型中文标签映射（供前端展示）
SUBTITLE_LABELS = {
    "none": "无字幕",
    "chinese": "中文字幕 🇨🇳",
    "english": "英文字幕 🇺🇸",
    "bilingual": "双语字幕 🌐",
}


class OrganizeMode(str, Enum):
    """整理模式"""
    PREVIEW = "preview"  # 仅预览
    COPY = "copy"        # 复制
    MOVE = "move"        # 移动


class OrganizeRequest(BaseModel):
    """整理请求"""
    source_paths: List[str]          # 源目录列表（可多选）
    target_root: str                 # 目标根目录，如 "E:/jellyfin"
    mode: OrganizeMode = OrganizeMode.PREVIEW  # 默认为预览模式
    auto_scrape: bool = False        # 整理时自动刮削未收录的影片


class OrganizePreviewItem(BaseModel):
    """预览项：单个文件的整理计划"""
    source_path: str       # 原始文件路径
    code: str              # 番号（不含字幕后缀）
    subtitle_type: str     # none/chinese/english/bilingual
    subtitle_label: str    # 显示用标签
    target_dir: str        # 目标文件夹
    target_file: str       # 目标文件（含后缀）
    actor_name: str        # 女演员名
    status: str            # new/exists/skip/error
    reason: Optional[str] = None  # 原因（如已存在/找不到番号）
    file_size: Optional[int] = None  # 文件大小（字节）


class OrganizeProgress(BaseModel):
    """整理进度（SSE 流式推送）

    event 类型:
      - found       : 预览找到文件
      - summary     : 预览汇总
      - scrape_start: 正在自动刮削（auto_scrape 模式）
      - copied/moved: 文件复制/移动成功
      - skipped     : 目标文件已存在
      - error       : 处理出错
      - done        : 全部完成
    """
    event: str
    # found 事件
    source_path: Optional[str] = None
    code: Optional[str] = None
    subtitle_type: Optional[str] = None
    subtitle_label: Optional[str] = None
    target_dir: Optional[str] = None
    target_file: Optional[str] = None
    actor_name: Optional[str] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    file_size: Optional[int] = None
    # summary 事件
    total: Optional[int] = None
    new_count: Optional[int] = None
    exists_count: Optional[int] = None
    error_count: Optional[int] = None
    estimated_size: Optional[str] = None
    # copied/moved/skipped 事件
    elapsed: Optional[str] = None
    # done 事件
    success_count: Optional[int] = None
    fail_count: Optional[int] = None
    message: Optional[str] = None


# ===============================================================================
# Phase 1 新增：统一 API 响应模型（安全/规范化）
# ===============================================================================

class ApiSuccess(BaseModel):
    """通用成功响应"""
    success: bool = True
    message: Optional[str] = None


class ApiList(BaseModel):
    """通用列表响应"""
    total: int
    page: int
    page_size: int
    items: List[dict]


class UserListResponse(BaseModel):
    """用户列表响应"""
    users: List[dict]


class MovieStatsResponse(BaseModel):
    """影片统计响应"""
    total: int
    scraped: int
    unscraped: int
    actors: int
    series: int


