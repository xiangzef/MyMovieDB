# 信息库目录说明

本目录用于存放 MyMovieDB 的刮削信息、备份和静态资源。

```
info/
├── movies/      # 影片元数据 JSON（可选，用于备份或离线查看）
├── backup/      # 数据库备份，定时自动备份存放位置
├── covers/      # 封面图缓存（由爬虫下载的封面图）
└── logs/        # 运行日志
```

## 数据存放位置

| 数据类型 | 存放位置 | 说明 |
|---------|---------|------|
| 数据库主文件 | `data/movies.db` | SQLite 数据库，包含所有影片和本地视频记录 |
| 刮削元数据 | `data/movies.db` → `movies` 表 | 手动刮削和本地视频刮削的数据统一存储在 `movies` 表 |
| 本地视频记录 | `data/movies.db` → `local_videos` 表 | 扫描目录后的视频文件记录 |
| 本地图片路径 | `data/movies.db` → `local_videos` 表 | fanart_path, poster_path, thumb_path 字段 |
| 封面图文件 | `backend/covers/` | 刮削下载的封面图，按番号命名 |
| 爬虫配置 | `backend/config.py` | 数据源启用/禁用和 URL 格式 |

## 表结构速查

**movies 表**（影片信息库）
- `id`, `code`, `title`, `title_jp` - 基本信息
- `release_date`, `duration`, `studio`, `maker`, `director` - 详细信息
- `genres`, `actors`, `actors_male` - JSON 格式数组
- `local_video_id` - 关联的本地视频记录 ID（来自本地视频库）
- `local_cover_path`, `cover_url`, `preview_url` - 封面和预览图

**local_videos 表**（本地视频库）
- `id`, `code`, `file_path`, `file_size`, `source_id` - 基本信息
- `scraped` - 是否已刮削（0/1）
- `movie_id` - 关联的 movies 表 ID
- `fanart_path`, `poster_path`, `thumb_path` - 本地多图路径
