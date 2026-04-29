# MyMovieDB 代码地图

> 本文件是项目所有后端模块、函数、数据表、API、前端模块的详细说明索引。
> 维护原则：每次新增/删除函数都要在此处同步更新。

---

## 一、项目目录结构

```
MyMovieDB/
├── backend/                   # FastAPI 后端（Python）
│   ├── main.py                # 主入口，所有 API 路由
│   ├── database.py            # SQLite 数据库操作
│   ├── models.py              # Pydantic 数据模型
│   ├── organizer.py           # 文件整理模块（Phase 0.5）
│   ├── scraper.py             # 多源刮削器
│   ├── jellyfin.py            # Jellyfin NFO 解析 & 扫描
│   ├── gfriends.py            # 演员头像下载（gfriends 仓库）
│   ├── config.py              # 配置读取（config.ini）
│   ├── translator.py          # 字幕翻译（Vosk日语识别 + Ollama qwen翻译 + ffmpeg）
│   ├── migrate.py             # 数据库迁移脚本
│   ├── models.py              # 所有 Pydantic 请求/响应模型
│   └── config.ini             # 运行配置
├── frontend/
│   └── index.html             # 单文件 Vue 3 SPA（~4000 行）
├── docs/
│   ├── PROJECT_PLAN.md        # 分阶段开发计划
│   ├── 技术手册.md             # 架构/数据库/API 完整文档
│   └── DEFECT_LOG.md          # 缺陷记录 & 代码习惯问题
├── data/                      # 运行时数据（图片/NFO/DB）
│   ├── covers/                # 封面图
│   ├── posters/               # Poster 图
│   ├── fanarts/               # Fanart 图
│   ├── thumbs/                # 缩略图
│   ├── avatars/               # 演员头像
│   └── movies.db              # SQLite 数据库
├── tests/                     # 单元测试
└── .workbuddy/
    └── skills/mymoviedb/      # 本 Skill 文件
```

---

## 二、数据库表结构（SQLite）

### `movies` 表（核心影片库）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| code | TEXT UNIQUE | 番号（大写标准化，如 CAWD-285） |
| title | TEXT | 原始标题（日文） |
| title_cn | TEXT | 中文标题 |
| title_jp | TEXT | 日文标题（冗余备用） |
| release_date | TEXT | 发行日期 |
| duration | INTEGER | 时长（分钟） |
| studio | TEXT | 制作商 |
| maker | TEXT | 发行商 |
| director | TEXT | 导演 |
| cover_url | TEXT | 封面图网络 URL |
| preview_url | TEXT | 预览视频 URL |
| detail_url | TEXT | 详情页 URL |
| genres | TEXT | 类别（JSON 数组字符串） |
| actors | TEXT | 演员列表（JSON 数组字符串） |
| actors_male | TEXT | 男优列表（JSON） |
| local_cover_path | TEXT | 本地封面图路径 |
| fanart_path | TEXT | 本地 Fanart 路径 |
| poster_path | TEXT | 本地 Poster 路径 |
| thumb_path | TEXT | 本地 Thumb 路径 |
| local_video_id | INTEGER | 关联 local_videos.id |
| scrape_status | TEXT | complete/partial/empty |
| scrape_source | TEXT | 刮削来源标识 |
| source | TEXT | scraped/jellyfin/manual |
| source_type | TEXT | web/jellyfin/local |
| video_path | TEXT | 本地视频路径 |
| plot | TEXT | 剧情简介 |
| subtitle_type | TEXT | none/chinese/english/bilingual |
| last_organized_at | TIMESTAMP | 最近整理时间 |
| organized_path | TEXT | 整理后目标文件夹路径 |
| scrape_count | INTEGER | 刮削次数 |
| last_scraped_at | TIMESTAMP | 最近刮削时间 |
| jellyfin_status | TEXT | complete/partial/broken/unknown |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 最近更新时间 |

---

### `local_sources` 表（本地视频源目录）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| path | TEXT UNIQUE | 源目录绝对路径 |
| name | TEXT | 显示名称 |
| enabled | INTEGER | 是否启用（0/1） |
| video_count | INTEGER | 上次扫描的视频数量 |
| last_scan_at | TEXT | 上次扫描时间 |
| is_jellyfin | INTEGER | 是否为 Jellyfin 目录（0/1） |
| created_at | TIMESTAMP | 添加时间 |

---

### `local_videos` 表（本地视频文件记录）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| source_id | INTEGER FK | 关联 local_sources.id |
| name | TEXT | 文件名（不含扩展名） |
| path | TEXT UNIQUE | 完整文件路径 |
| code | TEXT | 识别出的番号（大写） |
| extension | TEXT | 扩展名（不含点，如 mp4） |
| file_size | INTEGER | 文件大小（字节） |
| scraped | INTEGER | 是否已刮削（0/1） |
| movie_id | INTEGER FK | 关联 movies.id |
| is_jellyfin | INTEGER | 是否位于 Jellyfin 目录（0/1） |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 最近更新时间 |

---

### `users` 表（用户认证）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| username | TEXT UNIQUE | 用户名 |
| password_hash | TEXT | 密码哈希（SHA-256） |
| role | TEXT | admin/user |
| email | TEXT | 邮箱（可选） |
| created_at | TIMESTAMP | 注册时间 |
| last_login | TIMESTAMP | 最近登录时间 |

---

### `tokens` 表（登录令牌）

| 字段 | 类型 | 说明 |
|------|------|------|
| token | TEXT PK | Token 字符串 |
| user_id | INTEGER | 关联用户 |
| expires_at | TIMESTAMP | 过期时间 |
| created_at | TIMESTAMP | 创建时间 |

---

## 三、后端模块详解

### `config.py` — 配置读取

从 `backend/config.ini` 读取所有运行时配置，导出全局变量供其他模块使用。

| 导出变量/函数 | 说明 |
|---|---|
| `HOST`, `PORT` | 服务器监听地址和端口 |
| `DATA_DIR` | 数据目录（图片/DB 存储根目录） |
| `COVERS_DIR` | 封面图目录 = DATA_DIR/covers |
| `FRONTEND_DIR` | 前端静态文件目录 |
| `INFO_DIR` | 辅助信息目录 |
| `SCRAPE_TIMEOUT` | 刮削超时（秒） |
| `DEFAULT_HEADERS` | HTTP 请求头（User-Agent 等） |
| `SCRAPER_SOURCES` | 从 config.ini [sources] 加载的爬虫源列表 |
| `get(section, key)` | 读取字符串配置 |
| `getint/getfloat/getbool` | 类型化读取配置 |
| `resolve_path(rel)` | 将相对于 backend/ 的路径转为绝对路径 |
| `get_enabled_sources()` | 返回启用的数据源列表（按 priority 升序） |
| `get_source_by_id(id)` | 根据 id 查找数据源 |

---

### `models.py` — 数据模型

所有 Pydantic 模型，Python 3.7 兼容，`extra='ignore'` 防止意外字段报错。

| 模型 | 用途 |
|---|---|
| `MovieBase` | 影片基础字段（code/title/actors 等） |
| `MovieCreate` | 创建影片请求（继承 MovieBase） |
| `MovieResponse` | 影片完整响应（含 id/本地路径/source） |
| `MovieListResponse` | 影片列表分页响应 |
| `LocalVideoItem` | 单个本地视频项 |
| `ScrapeRequest/Response` | 刮削请求/响应 |
| `UserLogin/Register/Response` | 用户认证模型 |
| `LoginResponse` | 含 token 的登录响应 |
| `ActorItem/ActorListResponse` | 演员统计 |
| `SeriesItem/SeriesListResponse` | 番号系列统计 |
| `SubtitleType` (Enum) | none/chinese/english/bilingual |
| `OrganizeMode` (Enum) | preview/copy/move |
| `OrganizeRequest` | 整理请求（源路径/目标根/模式/是否自动刮削） |
| `OrganizePreviewItem` | 预览项（单文件整理计划） |
| `OrganizeProgress` | SSE 流式进度事件（见下方详细说明） |
| `ApiSuccess/ApiList` | Phase 1 统一响应模型 |
| `SUBTITLE_LABELS` | 字幕类型中文标签映射字典 |

**OrganizeProgress 事件类型（event 字段）**：

| event 值 | 含义 | 关键字段 |
|---|---|---|
| `found` | 扫描到一个文件（预览阶段） | source_path/code/subtitle_type/disc_label/target_dir |
| `summary` | 预览汇总 | total/new_count/exists_count/error_count |
| `item_progress` | 正在处理当前文件 | source_path/target_file |
| `scrape_start` | 自动刮削中（auto_scrape 模式） | code |
| `copied`/`moved` | 文件已复制/移动成功 | source_path/target_file/elapsed |
| `cleaned` | 源文件夹已清理 | folder_path/removed_size |
| `jellyfin_updated` | Jellyfin 记录已更新 | code/jellyfin_updated |
| `scrape_list_updated` | 刮削列表已清理 | code/scrape_list_updated |
| `skipped` | 目标文件已存在，跳过 | source_path/reason |
| `error` | 处理出错 | source_path/reason |
| `done` | 全部完成 | success_count/fail_count/cleanup_folders |

---

### `database.py` — 数据库操作

所有 SQLite 操作，直接连接（每次调用获取连接，用完关闭）。

**初始化与工具**

| 函数 | 说明 |
|---|---|
| `normalize_code(code)` | 标准化番号（大写、去空格）|
| `get_db()` | 获取 SQLite 连接（check_same_thread=False）|
| `init_db()` | 初始化 movies 表（含向后兼容 ALTER TABLE）|
| `init_local_sources_table()` | 初始化 local_sources 表 |
| `init_local_videos_table()` | 初始化 local_videos 表 |
| `init_all_tables()` | 调用上面三个 init + tokens + users 表 |

**认证**

| 函数 | 说明 |
|---|---|
| `create_token_db(user_id, token, expires_at)` | 创建登录 Token |
| `verify_token_db(token)` | 验证 Token 有效性，返回 user_id |
| `delete_token_db(token)` | 删除 Token（登出）|
| `clean_expired_tokens_db()` | 清理过期 Token（返回清理数量）|

**影片 CRUD**

| 函数 | 说明 |
|---|---|
| `create_movie(movie)` | 插入新影片 |
| `get_movie_by_code(code)` | 按番号查询影片 |
| `get_movie_by_id(id)` | 按 ID 查询影片 |
| `get_all_movies(page, page_size, filter...)` | 分页查询（含刮削状态/关键词过滤）|
| `get_all_movies_no_paging()` | 不分页获取全部（用于导出）|
| `search_movies(keyword, page, page_size)` | 关键词搜索 |
| `merge_movie_data(existing, new_data)` | 合并刮削数据（保留现有数据，补充缺失字段）|
| `update_movie(movie_id, data)` | 更新影片字段 |
| `upsert_movie(data)` | 插入或更新（按 code 唯一）|
| `delete_movie(movie_id)` | 删除影片记录 |
| `row_to_movie_response(row)` | 将数据库 Row 转为 MovieResponse 对象 |

**本地视频管理**

| 函数 | 说明 |
|---|---|
| `upsert_local_video(source_id, path, code, ...)` | 插入或更新本地视频记录 |
| `get_local_videos(page, page_size, filter...)` | 分页查询本地视频 |
| `get_local_video_by_id(id)` | 按 ID 查询 |
| `get_local_video_by_code(code)` | 按番号查询 |
| `mark_video_scraped(id)` | 标记为已刮削 |
| `delete_local_video(id)` | 删除记录 |
| `get_unscraped_local_videos()` | 获取未刮削视频列表 |
| `get_local_video_stats()` | 统计（总数/已刮削/未刮削/大小）|
| `cleanup_invalid_codes()` | 清理无效番号记录 |
| `_extract_code_from_filename(name)` | 从文件名提取番号（辅助函数）|

**本地源目录管理**

| 函数 | 说明 |
|---|---|
| `create_local_source(path, name, is_jellyfin)` | 添加本地源目录 |
| `get_local_sources()` | 获取所有源目录列表 |
| `get_local_source_by_id(id)` | 按 ID 查询源目录 |
| `delete_local_source(id)` | 删除源目录（CASCADE 删除关联视频）|
| `update_local_source_scan(id, video_count)` | 更新扫描统计 |
| `mark_source_as_jellyfin(path)` | 标记目录为 Jellyfin 源 |
| `get_local_sources_with_jellyfin()` | 获取所有 Jellyfin 目录 |

**Jellyfin 状态管理**

| 函数 | 说明 |
|---|---|
| `sync_local_videos_is_jellyfin()` | 同步 is_jellyfin 标志（启动时调用）|
| `fix_is_jellyfin_null_records()` | 修复 is_jellyfin=NULL 的孤立记录 |
| `import_jellyfin_movie(nfo_path, video_path)` | 从 NFO 导入 Jellyfin 影片 |
| `enrich_jellyfin_movie_from_nfo(movie_id, nfo_path)` | 从 NFO 补充影片信息 |
| `get_jellyfin_count()` | 获取 Jellyfin 影片总数 |
| `get_jellyfin_incomplete_codes()` | 获取 Jellyfin 中信息不完整的番号 |
| `calculate_jellyfin_status(movie_id)` | 计算单个影片的 Jellyfin 状态 |
| `verify_jellyfin_status(movie_id)` | 验证并更新 jellyfin_status |
| `batch_verify_jellyfin_status(limit)` | 批量验证 Jellyfin 状态 |
| `update_jellyfin_status(movie_id, status)` | 更新 jellyfin_status 字段 |

**刮削状态管理**

| 函数 | 说明 |
|---|---|
| `calculate_scrape_status(movie_id)` | 计算刮削完整度（complete/partial/empty）|
| `update_movie_scrape_status(movie_id)` | 更新 scrape_status 字段 |
| `check_and_fix_scrape_status(movie_id)` | 检查并修复单个影片刮削状态 |
| `batch_verify_scrape_status(limit)` | 批量验证刮削状态 |

**类别统计**

| 函数 | 说明 |
|---|---|
| `get_actor_stats(page, page_size)` | 按演员统计影片数量 |
| `get_series_stats(page, page_size)` | 按番号系列（前缀）统计 |
| `get_movies_by_actor(actor_name, page)` | 按演员名查询影片列表 |
| `get_movies_by_series(prefix, page)` | 按系列前缀查询影片列表 |
| `get_movies_by_codes(codes_list)` | 按番号列表批量查询影片（整理功能用）|
| `get_actors_without_avatars(page)` | 查找无头像的演员 |

**整理功能专用（Phase 0.5）**

| 函数 | 说明 |
|---|---|
| `update_movie_organize_info(movie_id, subtitle_type, organized_path)` | 更新整理结果（字幕类型+目标路径）|
| `sync_local_video_after_organize(movie_id, new_video_path, new_code, new_name, new_extension)` | 文件整理后同步 local_videos 记录 |
| `get_organized_movies_without_info(limit)` | 查找已整理但缺少整理信息的影片 |

---

### `organizer.py` — 文件整理模块

Phase 0.5 核心模块，负责按 Jellyfin 标准结构整理视频文件。

**全局状态**

| 变量/函数 | 说明 |
|---|---|
| `_abort_organize` | 全局中止标志（bool，线程安全）|
| `reset_abort()` | 重置中止标志 |
| `request_abort()` | 设置中止标志（前端停止按钮触发）|
| `VIDEO_EXTENSIONS` | 支持的视频扩展名集合 |
| `_CODE_PATTERNS` | 4 级番号识别正则列表（按优先级排序）|
| `_CODE_BLACKLIST` | 误判黑名单正则（X264/HD/WEB 等无效前缀）|

**番号识别**

| 函数 | 签名 | 说明 |
|---|---|---|
| `_strip_garbage_prefix(name)` | `(str) -> str` | 清洗文件名前缀（域名水印/中文括号）|
| `_extract_code(name)` | `(str) -> Optional[str]` | 从文件名提取番号（4级正则顺序匹配）|
| `_extract_code_with_suffix(name)` | `(str) -> (code, subtitle_type, display_name, disc_label)` | 提取番号+字幕类型+多盘标识（**顺序：先剥字幕后缀→再剥多盘标识→最后提取番号**）|

**_extract_code_with_suffix 处理逻辑（关键）**：
```
Step1: 剥字幕后缀（优先级 -UC > -U > -C，不区分大小写）
Step2: 剥多盘标识（-A/-B 明确；如 Step1 没消耗 -C，则末尾 -C 是多盘 C 盘）
Step3: 调用 _extract_code() 提取番号
```

**文件名/路径工具**

| 函数 | 说明 |
|---|---|
| `_safe_file_name(name)` | 替换文件名非法字符为下划线 |
| `_safe_dir_name(name)` | 生成合法文件夹名（去方括号、前后下划线）|
| `_human_size(n)` | 字节数转人类可读（1.2GB 等）|

**扫描**

| 函数 | 签名 | 说明 |
|---|---|---|
| `scan_video_files_gen(source_paths, callback)` | `Generator[dict]` | **流式扫描**（yield 每个文件，不等全部完成）|
| `scan_video_files(source_paths, callback)` | `List[dict]` | 批量扫描（内部调用 gen 版本收集列表）|

每个扫描项 dict 包含：`path`, `name`, `stem`, `extension`, `size`

**预览/目标路径**

| 函数 | 签名 | 说明 |
|---|---|---|
| `build_target_path(f, movies_map, target_root)` | `dict -> dict` | 计算单个文件的目标路径（含番号/演员/字幕后缀）|
| `_get_primary_actor(actors_list)` | `-> str` | 取第一个演员（女演员列表第一位）|
| `_target_exists(target_file)` | `-> bool` | 目标文件是否已存在 |
| `_emit_preview_item(f, movies_map, target_root, callback)` | 无返回 | 发送单个预览进度事件 |

**NFO 生成**

| 函数 | 签名 | 说明 |
|---|---|---|
| `_escape_xml(s)` | `str -> str` | XML 特殊字符转义 |
| `generate_organize_nfo(code, movie_data, target_dir)` | `-> bool` | 生成 Jellyfin 标准 NFO 文件 |
| `_copy_asset_files(code, target_dir)` | 无返回 | 复制封面/poster/fanart/thumb 到目标目录 |

**文件操作**

| 函数 | 签名 | 说明 |
|---|---|---|
| `_async_move_file(src, dst)` | `async` | 异步移动文件（run_in_executor + shutil.move）|
| `_async_copy_file(src, dst)` | `async` | 异步复制文件（run_in_executor + shutil.copy2）|
| `_sync_move(src, dst)` | 同步 | 内部移动（handle 重名）|
| `_sync_copy(src, dst)` | 同步 | 内部复制（handle 重名）|

**核心整理流程**

| 函数 | 签名 | 说明 |
|---|---|---|
| `organize_files_gen(request, progress_callback)` | `Generator[OrganizeProgress]` | **旧版 Generator**（已废弃，保留兼容）|
| `organize_files_sync(request, progress_callback)` | 同步 | **主整理函数**（被 SSE endpoint 用 run_in_executor 调用）|

`organize_files_sync` 执行流程：
```
1. reset_abort() 重置中止标志
2. scan_video_files_gen() 流式扫描（每发现一个文件立即 callback）
3. 批量查询 movies 表（get_movies_by_codes）
4. 如果是 PREVIEW 模式：发送 found 事件，最后发 summary 汇总
5. 如果是 COPY/MOVE 模式：
   - 生成目标路径
   - 执行复制/移动（asyncio.run 内调用 async 版本）
   - 生成 NFO + 复制 asset 文件
   - 更新 movies 表（update_movie_organize_info）
   - 同步 local_videos（sync_local_video_after_organize）
   - 发 jellyfin_updated 事件
   - 清理刮削列表（_remove_from_scrape_list）
   - 发 scrape_list_updated 事件
6. 清理源目录（_cleanup_source_folder）
7. 发 done 事件
```

**清理逻辑**

| 函数 | 签名 | 说明 |
|---|---|---|
| `_is_junk_file(file_path)` | `-> bool` | 是否为垃圾文件（按扩展名+文件名关键词，不按大小）|
| `_is_residual_only_folder(folder)` | `-> (bool, str)` | 文件夹是否只剩垃圾（空/只有种子/图片/nfo）|
| `_cleanup_source_folder(source_path, callback)` | `-> bool` | 清理源文件夹（含递归父目录清理）|

**Jellyfin & 刮削列表同步**

| 函数 | 签名 | 说明 |
|---|---|---|
| `_update_jellyfin_scan_record(target_dir, code, movie_id, new_video_path, new_name, new_extension, progress_callback)` | `-> None` | 检查 target_dir 是否在 Jellyfin 目录中，是则调用 db.sync_local_video_after_organize()，发 jellyfin_updated 事件 |
| `_remove_from_scrape_list(source_path, code, progress_callback)` | `-> None` | 按原路径精确匹配删除 local_videos 旧记录，发 scrape_list_updated 事件 |

---

### `scraper.py` — 多源刮削器

**工具函数**

| 函数 | 说明 |
|---|---|
| `_clean_actor_name(name)` | 清洗演员名（去特殊字符）|
| `translate_to_chinese(text)` | 调用翻译 API（标题中文化）|
| `download_and_crop_cover(url, code)` | 下载封面图，按 16:9 / 3:2 裁剪 |
| `regenerate_poster_from_fanart(code)` | 从 fanart 重新生成 poster（右侧裁剪）|
| `save_movie_assets(code, cover_url, ...)` | 保存封面/poster/fanart/thumb 到本地 |
| `generate_nfo(movie_data, save_dir)` | 生成 Jellyfin 标准 NFO XML 文件 |
| `set_stop_check(func)` / `should_stop()` | 外部注入停止回调 |
| `make_bilingual_title(jp_title, cn_title)` | 拼装双语标题 |
| `make_basic_data(code)` | 当所有源都失败时生成基础占位数据 |

**Scraper 基类接口（各数据源实现）**

每个数据源类都实现：
- `search(code) -> list` — 搜索番号，返回候选列表
- `get_detail(url) -> dict` — 获取详情页数据
- `scrape(code) -> dict` — 完整刮削流程（内部调用 search + get_detail）

**已实现的数据源**（按文件中出现顺序）：

| 类名 | 数据源 | 特点 |
|---|---|---|
| `JavDBScraper` | javdb.com | 主力数据源，信息最全 |
| `AvsoxScraper` | avsox.homepage.xxx | 备用源 |
| `AvwikiScraper` | avwiki.live | 备用源 |
| `JavcupScraper` | javcup.net | 返回基础信息，无详情 |
| `AvbaseScraper` | avbase.net | 返回基础信息 |
| `ScraperOrchestrator` | — | 编排多个 scraper，合并结果 |

| 函数 | 说明 |
|---|---|
| `ScraperOrchestrator.__init__()` | 按 config.ini 配置初始化所有 scraper |
| `ScraperOrchestrator._init_scrapers()` | 从 config 加载启用的数据源 |
| `ScraperOrchestrator.scrape(code)` | 按优先级尝试所有数据源，返回最佳结果 |
| `ScraperOrchestrator.scrape_movie_enhanced(code)` | 增强刮削（含封面下载/NFO 生成）|
| `ScraperOrchestrator.test_all_scrapers(code)` | 测试所有数据源，返回测试报告 |

---

### `jellyfin.py` — Jellyfin 集成

| 函数 | 说明 |
|---|---|
| `detect_encoding(file_path)` | 自动检测文件编码（UTF-8/GBK 等）|
| `parse_jellyfin_nfo(nfo_path)` | 解析 NFO XML 文件，返回影片数据字典 |
| `scan_jellyfin_directory(dir_path, callback)` | 扫描 Jellyfin 目录结构，yield 每个影片的 NFO+视频路径 |
| `get_jellyfin_stats(dir_path)` | 统计目录内影片/NFO/无封面数量 |

---

### `gfriends.py` — 演员头像下载

从 GitHub gfriends 仓库下载女演员头像（基于文件树 JSON 索引）。

| 函数 | 说明 |
|---|---|
| `_get_session()` | 获取带 UA 的 requests Session（单例）|
| `get_filetree()` | 获取 gfriends 仓库文件树（缓存 10 分钟）|
| `_name_to_url(name, tree)` | 将演员名映射到头像 CDN URL |
| `search_avatar_url(name)` | 搜索演员头像 URL（含名字变体查找）|
| `lookup_actor(name)` | 查找演员信息（调用 search_avatar_url）|
| `get_local_avatar_path(name)` | 获取本地头像文件路径（不存在返回 None）|
| `get_local_avatar_url(name, base_url)` | 获取头像访问 URL（供 API 返回前端）|
| `download_avatar(name, url)` | 下载并保存头像（真实名字文件名）|
| `batch_download_avatars(names)` | 批量下载演员头像 |
| `is_real_actress(name)` | 判断是否为真实女演员（排除男优/导演）|
| `get_avatar_dir()` | 获取头像存储目录路径 |

**重要规范**：头像文件名使用**演员真实名字**（如 `三上悠亜.jpg`），不使用 URL 编码，防止大小写不一致问题。

---

### `translator.py` — 日语语音翻译模块

离线日语视频翻译管道，使用本地模型。

**翻译管道**：
```
视频 → ffmpeg 音频提取(16kHz mono PCM) → Vosk 日语识别 → Ollama qwen2.5:7b 翻译 → SRT 字幕
```

| 类/函数 | 说明 |
|---|---|
| `JapaneseVideoTranslator` | 主翻译器类 |
| `JapaneseVideoTranslator.__init__(model_size)` | 初始化，默认 `base` |
| `JapaneseVideoTranslator.process_video(video_path, translate)` | 执行完整翻译流程 |
| `JapaneseVideoTranslator._extract_audio(video_path, audio_path)` | 用 ffmpeg 提取音频 |
| `JapaneseVideoTranslator.transcribe_audio(audio_path, language)` | 用 Vosk 转录音频 |
| `JapaneseVideoTranslator._translate_with_ollama(text)` | 用 Ollama qwen2.5:7b 翻译日文→中文 |
| `JapaneseVideoTranslator.translate_text(japanese_text)` | 翻译文本（对外接口） |
| `JapaneseVideoTranslator.translate_segments(segments)` | 翻译片段列表 |
| `format_time(seconds)` | 秒数转 SRT 时间戳 `HH:MM:SS,mmm` |
| `format_transcript(segments, include_translation)` | 格式化转录文本 |

**关键行为**：
- 音频持久化存储在视频同目录：`{video_name}_audio.wav`（下次跳过提取）
- Vosk 模型路径：`C:\vosk-model-ja-0.22`
- Ollama API：`http://localhost:11434/api/generate`，超时 120s
- `transcribe_audio()` 返回 `{ text, segments }`，segments 每个元素含 `start/end/text`

---

### `main.py` — API 路由

FastAPI 应用，所有 API 都在此文件定义。

**启动**

| 函数 | 说明 |
|---|---|
| `startup_event()` | 启动时同步 is_jellyfin 数据 + 修复 NULL 记录 + 清理过期 Token |

**认证 API**

| 路由 | 函数 | 说明 |
|---|---|---|
| POST `/auth/login` | `login()` | 用户登录，返回 Token |
| POST `/auth/register` | `register()` | 用户注册 |
| GET `/auth/me` | `get_current_user_info()` | 获取当前用户信息 |
| POST `/auth/logout` | `logout()` | 登出（删除 Token）|
| GET `/auth/users` | `get_all_users()` | 获取用户列表（管理员）|
| PUT `/auth/users/{id}` | `update_user()` | 更新用户信息 |
| DELETE `/auth/users/{id}` | `delete_user()` | 删除用户 |

**影片 API**

| 路由 | 函数 | 说明 |
|---|---|---|
| GET `/movies` | `get_movies()` | 分页获取影片列表（含过滤）|
| GET `/movies/{id}` | `get_movie()` | 按 ID 获取影片 |
| GET `/movies/code/{code}` | `get_movie_by_code()` | 按番号获取影片 |
| GET `/movies/search` | `search_movies()` | 关键词搜索 |
| POST `/scrape` | `scrape_movie_endpoint()` | 刮削单个番号 |
| DELETE `/movies/{id}` | `delete_movie()` | 删除影片 |
| GET `/movies/{id}/open-folder` | `open_folder()` | 打开影片所在文件夹 |
| GET `/movies/{id}/play` | `play_video()` | 播放视频 |

**批量刮削 API（SSE）**

| 路由 | 函数 | 说明 |
|---|---|---|
| POST `/scrape/batch` | `scrape_batch()` | SSE 流式批量刮削 |
| POST `/scrape/stop` | `stop_scrape()` | 停止刮削 |
| POST `/scrape/local-videos` | `scrape_local_videos()` | 刮削本地视频 |

**本地源管理 API**

| 路由 | 函数 | 说明 |
|---|---|---|
| POST `/local-sources` | `add_local_source()` | 添加本地源目录 |
| GET `/local-sources` | `list_local_sources()` | 列出所有源目录 |
| DELETE `/local-sources/{id}` | `remove_local_source()` | 删除源目录 |
| POST `/local-sources/{id}/scan` | `scan_single_source()` | 扫描单个源目录（SSE）|
| POST `/local-sources/scan` | `scan_local_sources()` | 扫描所有源目录（SSE）|

**本地视频 API**

| 路由 | 函数 | 说明 |
|---|---|---|
| GET `/local-videos` | `get_local_videos()` | 分页获取本地视频 |
| GET `/local-videos/stats` | `get_local_video_stats()` | 统计信息 |
| POST `/local-videos/cleanup` | `cleanup_invalid_local_videos()` | 清理无效记录 |
| DELETE `/local-videos/{id}` | `delete_local_video()` | 删除记录 |

**Jellyfin API**

| 路由 | 函数 | 说明 |
|---|---|---|
| GET `/jellyfin/stats` | `jellyfin_stats()` | Jellyfin 统计 |
| POST `/jellyfin/scan` | `jellyfin_scan()` | 扫描 Jellyfin 目录（SSE）|
| POST `/jellyfin/mark-directory` | `mark_directory_as_jellyfin()` | 标记目录为 Jellyfin |
| GET `/jellyfin/missing-count` | `get_jellyfin_missing_count()` | 缺失影片数量 |
| GET `/jellyfin/incomplete` | `get_jellyfin_incomplete()` | 不完整影片列表 |
| POST `/jellyfin/enrich-from-nfo` | `enrich_jellyfin_from_nfo()` | 从 NFO 补充信息（SSE）|
| GET `/jellyfin/folder-issues` | `get_jellyfin_folder_issues()` | 文件夹结构问题 |
| POST `/jellyfin/verify-status` | `verify_jellyfin_status()` | 验证 Jellyfin 状态 |
| POST `/jellyfin/refresh-status` | `refresh_jellyfin_status()` | 刷新状态 |
| POST `/jellyfin/scrape-missing` | `scrape_jellyfin_missing()` | 刮削 Jellyfin 缺失影片（SSE）|

**整理 API（Phase 0.5）**

| 路由 | 函数 | 说明 |
|---|---|---|
| POST `/organize/preview` | `organize_preview()` | 预览整理计划（SSE）|
| POST `/organize/execute` | `organize_execute()` | 执行整理（SSE）|
| POST `/organize/stop` | `organize_stop()` | 停止整理 |

**SSE 通用模式（整理/刮削/扫描均遵循）**：
```python
async def generate():
    q = asyncio.Queue()
    def progress_handler(p):
        q.put_nowait((event_name, data))
    def run_sync():
        do_work(..., progress_callback=progress_handler)
        q.put_nowait((None, None))  # 结束信号
    loop.run_in_executor(None, run_sync)
    while True:
        event, data = await q.get()  # 不设 timeout
        if event is None: break
        yield make_sse(event, data)
return StreamingResponse(generate(), media_type="text/event-stream")
```

**类别/演员 API**

| 路由 | 函数 | 说明 |
|---|---|---|
| GET `/categories/actors` | `get_actors()` | 按演员统计（分页）|
| GET `/categories/series` | `get_series()` | 按系列统计（分页）|
| GET `/categories/actors/{name}/movies` | `get_movies_by_actor()` | 按演员获取影片 |
| GET `/categories/series/{prefix}/movies` | `get_movies_by_series()` | 按系列获取影片 |
| GET `/categories/stats` | `get_categories_stats()` | 类别统计汇总 |

**演员头像 API**

| 路由 | 函数 | 说明 |
|---|---|---|
| GET `/actors/not-in-repo` | `get_actors_not_in_repo()` | 无头像演员列表 |
| GET `/actors/{name}/lookup` | `lookup_actor()` | 查找演员头像 |
| POST `/actors/download-avatars` | `download_actor_avatars()` | 批量下载头像（SSE）|

**其他 API**

| 路由 | 函数 | 说明 |
|---|---|---|
| GET `/health` | `health_check()` | 健康检查 |
| GET `/images/{type}/{code}` | `get_local_image()` | 获取本地图片（cover/poster/fanart/thumb）|
| POST `/translate` | `translate_video()` | 翻译单个视频字幕 |
| POST `/translate/batch` | `translate_batch()` | 批量翻译（SSE）|
| GET `/translate/check-tools` | `check_translation_tools()` | 检查翻译工具是否可用 |
| POST `/poster/regenerate-all` | `regenerate_all_posters()` | 重新生成所有 Poster |
| POST `/scrape/check-results` | `check_scrape_results()` | 检查刮削结果 |
| POST `/scrape/fix-results` | `fix_scrape_results()` | 修复刮削结果（SSE）|
| GET `/scrape/check-movie/{id}` | `check_movie_scrape()` | 检查单个影片刮削 |
| POST `/scrape/fix-movie/{id}` | `fix_movie_scrape()` | 修复单个影片刮削 |

---

## 四、前端模块（frontend/index.html）

单文件 Vue 3 SPA，所有代码在一个文件内，分段如下：

### CSS 区域（`<style>` 标签内）

| 主要样式类 | 说明 |
|---|---|
| `#app` | 初始 `display:none`（FOUC 防护）|
| `#app.app-ready` | Vue 挂载后显示 |
| `.modal-overlay` | 详情弹窗遮罩 |
| `.organize-overlay` | 整理进度浮层 |
| `.scrape-panel` | 刮削面板 |
| `.sidebar` | 左侧导航栏 |
| `.movie-grid` | 影片卡片网格 |

**重要规范**：所有 overlay/modal 必须放在 `<div class="container">` 同级（最外层），不能嵌套在有 `overflow:auto/scroll/hidden` 的父级内，否则会被裁剪。

### JS 区域（`<script>` 标签内）

**Vue 应用主体结构**：
```javascript
const { createApp, ref, computed, onMounted, watch } = Vue;
const app = createApp({
    setup() {
        // 状态管理（全 ref）
        // 方法定义
        return { ... };
    }
}).mount('#app');
document.getElementById('app').classList.add('app-ready');
```

**主要状态 ref**：

| ref 变量 | 说明 |
|---|---|
| `movies` | 影片列表 |
| `selectedMovie` | 当前选中影片（触发详情弹窗）|
| `appMounted` | Vue 已挂载标志（防 FOUC）|
| `currentPage/totalPages` | 分页状态 |
| `scrapePanel` | 刮削面板状态（show/logs/pct 等）|
| `organizePanel` | 整理面板状态（show/mode/logs/pct/currentFile/stats）|
| `localSources` | 本地源目录列表 |
| `localVideos` | 本地视频列表 |
| `actorList/seriesList` | 演员/系列统计列表 |
| `toasts` | Toast 通知列表 |

**SSE 消息处理（整理面板）**：
```javascript
// 事件类型及对应前端逻辑
if (msg.event === 'found')         // 预览模式：显示找到的文件
if (msg.event === 'summary')       // 显示预览汇总
if (msg.event === 'item_progress') // 更新当前文件名
if (msg.event === 'copied/moved')  // 更新进度条+日志
if (msg.event === 'cleaned')       // 日志：源文件夹已清理
if (msg.event === 'jellyfin_updated')  // 日志：Jellyfin 记录已同步
if (msg.event === 'scrape_list_updated')  // 日志：刮削列表已清理
if (msg.event === 'skipped')       // 日志：目标已存在
if (msg.event === 'error')         // 红色日志：处理出错
if (msg.event === 'done')          // 完成：显示汇总统计
```

---

## 五、关键配置文件

### `backend/config.ini`（运行时配置）

```ini
[server]
host = 0.0.0.0
port = 8000

[paths]
data_dir = ../data           ; 相对于 backend/ 的数据目录
frontend_dir = ../frontend

[scrape]
timeout = 30
default_delay = 1.0
save_cover = true

[sources]
sources_json = [...]          ; JSON 数组，每个元素是一个数据源配置
                               ; 包含 id/name/url/enabled/priority 字段
```

### `start-backend.ps1` / `stop-backend.ps1`

- 启动/停止 FastAPI 服务的 PowerShell 脚本
- 启动命令：`uvicorn main:app --host {HOST} --port {PORT} --reload`

---

## 六、docs 目录

| 文件 | 说明 |
|---|---|
| `docs/PROJECT_PLAN.md` | 分阶段开发计划（Phase 0.5 已完成，Phase 1-4 待开发）|
| `docs/技术手册.md` | 完整架构/数据库/API 文档（~834 行）|
| `docs/DEFECT_LOG.md` | 缺陷记录 + 不合理代码习惯清单 |

---

## 七、测试目录

```
tests/
├── README.md              # 测试文件说明
├── test_*.py              # 功能测试（15个）
├── check_*.py             # 检查工具（5个）
├── fix_*.py               # 修复工具（5个）
├── cleanup_*.py           # 清理工具（2个）
├── audit_*.py             # 审计工具（1个）
├── find_*.py              # 查找工具（2个）
├── organize_*.py          # 整理工具（1个）
└── consolidate_*.py       # 合并工具（1个）
logs/
├── .gitkeep               # Git 占位文件
├── debug_out.txt          # 调试输出
└── mymoviedb.log          # 主程序日志
backups/
├── index.html.bak20260401 # 前端备份
├── index.html.orig        # 原始文件备份
└── diag/                  # 诊断脚本备份
    ├── check_stats.py
    ├── diag_jellyfin.py
    └── diag_scrape.py
```

**规范**：所有测试文件必须放在 `tests/` 目录，不允许在项目根目录或 backend/ 直接放 `test_*.py`。
