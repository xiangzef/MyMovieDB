---
name: mymoviedb
description: >
  MyMovieDB 项目专属开发助手。当用户需要在 MyMovieDB 项目上进行任何开发、
  调试、功能扩展、重构时，加载此 skill。
  触发词：MyMovieDB、影视库、番号、刮削、整理功能、jellyfin扫描、
  organizer、scraper、gfriends、local_videos、local_sources、
  index.html前端、main.py、database.py
---

# MyMovieDB 项目开发 Skill

> **这是 MyMovieDB 项目的完整开发知识库。每次开始任何开发工作前，必须完整读取本文件和 references/ 目录下的所有文件。**

---

## 一、立即行动清单（每次会话必做）

```
1. 阅读 references/code-map.md         → 了解所有文件、函数、API
2. 阅读 references/discipline.md       → 了解开发纪律、缺陷记录、经验
3. 查看 docs/PROJECT_PLAN.md           → 了解当前阶段和待开发任务
4. 运行 node check_html.js             → 确认 HTML 结构健康
5. 开始开发，完成后追加 docs/PROJECT_PLAN.md 开发日志
```

---

## 二、项目基本信息

| 项目 | 说明 |
|------|------|
| **名称** | MyMovieDB |
| **路径** | `F:\github\MyMovieDB` |
| **性质** | 本地影视库管理工具（刮削 + 整理 + 展示） |
| **技术栈** | Python 3.7+ / FastAPI / SQLite / Vue.js 3 / Pydantic v2 |
| **前端** | 单文件 SPA：`frontend/index.html`（4000+ 行） |
| **后端入口** | `backend/main.py` |
| **数据库** | `data/movies.db`（SQLite） |
| **启动** | `.\start-backend.ps1` |
| **双远程仓库** | GitHub(origin) + Gitee(gitee) |
| **访问** | http://localhost:8000 |

---

## 三、目录结构速查

```
MyMovieDB/
├── backend/                  # 后端 Python 代码
│   ├── main.py               # FastAPI 主入口（~3000行，路由层）
│   ├── database.py           # SQLite 数据库操作封装
│   ├── scraper.py            # 多源爬虫（Fanza/Avbase/AV-Wiki/Javcup）
│   ├── organizer.py          # 文件整理功能核心逻辑 ⭐
│   ├── gfriends.py           # 女优头像下载引擎（gfriends 仓库集成）
│   ├── jellyfin.py           # Jellyfin 格式目录扫描
│   ├── models.py             # Pydantic v2 数据模型
│   ├── config.py             # 全局配置（HOST/PORT/路径等）
│   ├── translator.py         # 翻译模块（Vosk日语识别 + Ollama qwen翻译 + ffmpeg）⭐
│   ├── migrate.py            # 数据库迁移脚本
│   ├── tray_launcher.py      # 系统托盘启动器（PyInstaller 打包用）
│   └── requirements.txt      # Python 依赖
├── frontend/
│   ├── index.html            # Vue 3 单文件 SPA（主前端）⭐
│   ├── admin.html            # 管理员页面
│   ├── login.html            # 登录页
│   ├── profile.html          # 个人资料页
│   └── register.html         # 注册页
├── data/                     # 数据目录（不进 Git）
│   ├── movies.db             # SQLite 主数据库
│   ├── covers/               # 影片封面本地存储
│   └── avatars/              # 女优头像本地缓存
├── docs/                     # 文档目录（所有 .md 在这里）
│   ├── CLAUDE.md             # AI 接力快速上下文
│   ├── PROJECT_PLAN.md       # 开发计划 + 开发日志 ⭐
│   ├── 技术手册.md            # 完整技术文档
│   ├── DEFECT_LOG.md         # 缺陷记录
│   ├── OPTIMIZATION_PLAN.md  # 优化计划
│   └── 项目规范.md            # 目录规范
├── tests/                    # 测试脚本（test_*.py / check_*.py）
├── logs/                     # 日志文件（debug_out.txt 等）
├── backups/                  # 备份文件（index.html.bak20260401 等）
├── .workbuddy/skills/mymoviedb/  # 本 Skill 目录
│   ├── SKILL.md              # 本文件
│   └── references/           # 详细参考文档
│       ├── code-map.md       # 代码地图（文件/函数/API）
│       └── discipline.md     # 开发纪律（规范/缺陷/经验）
├── check_html.js             # HTML/JS 结构验证工具 ⭐（每次提交前运行）
├── start-backend.ps1         # 启动后端
├── stop-backend.ps1          # 停止后端
└── build.bat                 # PyInstaller 打包
```

---

## 四、数据库表速查

```sql
-- 主表：影片信息
movies (
    id, code UNIQUE,          -- 番号，如 IPZZ-792
    title, title_jp, title_cn,
    release_date, duration, studio, maker, director,
    cover_url, preview_url,
    genres TEXT,              -- JSON 数组
    actors TEXT,              -- JSON 数组（女演员）
    actors_male TEXT,         -- JSON 数组（男演员）
    local_cover_path, fanart_path, poster_path, thumb_path,
    plot,
    source TEXT,              -- scraped/jellyfin/manual
    source_type TEXT,         -- web/jellyfin/local
    local_video_id, video_path,
    scrape_status TEXT,       -- complete/partial/empty
    scrape_source, detail_url,
    subtitle_type TEXT,       -- none/chinese/english/bilingual ⭐
    organized_path,           -- 整理后目标目录
    last_organized_at,
    created_at, updated_at
)

-- 视频源目录（用户添加的目录）
local_sources (
    id, path UNIQUE, name, enabled,
    video_count, is_jellyfin INTEGER,  -- 0=普通目录 1=Jellyfin目录
    last_scan_at, created_at
)

-- 本地视频文件（扫描到的每个视频文件）
local_videos (
    id, source_id, name, path,
    code, extension, file_size,
    scraped INTEGER,           -- 0=未刮削 1=已刮削
    movie_id,                  -- 关联到 movies.id
    is_jellyfin INTEGER,       -- 0=普通 1=在Jellyfin目录中
    fanart_path, poster_path, thumb_path,
    created_at, updated_at
)

-- 用户表
users (
    id, username UNIQUE, password_hash,
    email, role,               -- admin/guest
    is_active, created_at, last_login
)
```

---

## 五、番号识别规则（关键逻辑）

```python
# 四级正则，按优先级排列（backend/organizer.py）
_CODE_PATTERNS = [
    # 1. FC2PPV: FC2PPV1234567（支持有无连字符）
    re.compile(r'\b(FC2[-_]?PPV[-_]?\d{5,9})\b', re.IGNORECASE),
    # 2. 300MIUM / 390JAC 等含数字前缀的系列
    re.compile(r'\b(\d{3}[A-Z]{2,6}[-_]?\d{2,5})\b', re.IGNORECASE),
    # 3. 常规番号带连字符：CAWD-285、SSIS-196（优先）
    re.compile(r'\b([A-Z]{2,6}-\d{2,5})\b', re.IGNORECASE),
    # 4. 常规番号无连字符：IPX722、MVSD487 → 自动补连字符 → IPX-722
    re.compile(r'\b([A-Z]{2,6})(\d{3,5})\b', re.IGNORECASE),
]

# 黑名单（排除编码格式关键词）
_CODE_BLACKLIST = ['X264','X265','XC','WEB','HD','MP4','MKV','AVC','HEVC',...]

# 垃圾前缀清洗
_RE_GARBAGE_PREFIX = r'^(?:[a-z0-9\-]+\.(?:xyz|com|net|...)[@-])'
_RE_CN_BRACKET_PREFIX = r'^[【\[（(][^\]】）)]*[】\]）)]\s*'
```

**字幕后缀 + 多盘标识处理顺序（严格不能反）**：
1. 先剥离字幕后缀：`-UC` → bilingual，`-U` → english，`-C` → chinese
2. 再剥离多盘标识：`-A`、`-B`、`-C`（C盘）
3. 最后提取番号

示例：`CAWD-285-C-A.mp4` → 字幕=chinese，盘=A，番号=CAWD-285

---

## 六、核心 SSE 设计模式

**整理/刮削等耗时操作一律用 Queue 模式（非 Generator 模式）**：

```python
# ✅ 正确：Queue 模式（backend/main.py 中的 SSE endpoint）
@app.post("/organize/execute")
async def organize_execute(req: OrganizeRequest):
    loop = asyncio.get_event_loop()
    q = asyncio.Queue()

    def progress_handler(p: OrganizeProgress):
        data = p.model_dump(exclude_none=True)
        q.put_nowait(("progress", data))

    def run_sync():
        organize_files_sync(
            source_paths=req.source_paths,
            target_root=req.target_root,
            mode=req.mode,
            progress_callback=progress_handler,
        )
        q.put_nowait((None, None))  # 结束信号

    loop.run_in_executor(None, run_sync)

    async def event_stream():
        while True:
            event_name, data = await q.get()  # 不设 timeout！
            if event_name is None:
                break
            yield f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

---

## 七、整理功能（Phase 0.5）核心流程

**目标目录结构**：
```
{target_root}/jellyfin/{女演员名}/{番号}/
    {番号}{字幕后缀}{多盘标识}.mp4  → 如 IPZZ-792-C-A.mp4
    {番号}.nfo
    {番号}-poster.jpg
    {番号}-fanart.jpg
    {番号}-thumb.jpg
```

**流程**（`organize_files_sync` in `organizer.py`）：
1. `scan_video_files_gen` 流式扫描 → 每文件立即 emit `found` 事件
2. `db.get_movies_by_codes` 批量查库
3. PREVIEW 模式：emit `summary` 后结束
4. COPY/MOVE 模式：逐文件处理
   - 跳过无番号 / FC2 / 未刮削（MOVE模式）
   - `shutil.copy2` 或 `shutil.move`
   - 成功后依次：
     a. `_cleanup_source_folder` → 清空原目录
     b. `_update_jellyfin_scan_record` → 同步 local_videos
     c. `_remove_from_scrape_list` → 删除原路径 local_videos 记录

**移动后清理判断逻辑**（`_is_residual_only_folder`）：
- 空文件夹 → 可删
- 只剩 .torrent/.url/.html/.txt/.ini/.db → 可删
- 只剩图片/nfo（无视频）→ 可删
- 有视频文件 → 不可删
- 有子目录 → 不可删
- 有未知文件类型 → 保守不删

---

## 八、Jellyfin 扫描记录同步逻辑

整理完成后调用 `_update_jellyfin_scan_record`：
1. 查 `local_sources WHERE is_jellyfin=1`
2. 检查 target_dir 是否以某个 Jellyfin 源路径开头
3. 调用 `db.sync_local_video_after_organize(movie_id, new_video_path, code, name, ext)`
4. `sync_local_video_after_organize` 逻辑：
   - 查找 `local_sources` 中包含新路径的目录 → 获取 source_id + is_jellyfin
   - 如果 `local_videos` 中已有该 `movie_id` → UPDATE 路径和 is_jellyfin
   - 否则 → INSERT 新记录
   - 同步更新 `movies.source_type = 'jellyfin'`

---

## 九、开发纪律速查（详见 references/discipline.md）

### 🔴 P0 硬规则（违反必出 Bug）

| 规则 | 原因 |
|------|------|
| 每次修改 HTML 后运行 `node check_html.js` | div 不平衡导致整个页面崩溃 |
| replace_in_file 后立即验证缩进 | 工具缩进错位导致 JS 白屏 |
| Python dict 用 `.get()` 不用 `[]` | 字段可能为 None 导致 KeyError |
| SQLite INSERT 显式列出所有 NOT NULL 字段 | 漏字段触发启动修复循环 |
| SSE endpoint 用 Queue 不用 Generator | Generator 模式有 30s 超时 bug |
| 文件 I/O 操作不设 timeout | 大文件正常耗时被误判为超时 |
| `position:fixed` overlay 放在 container 最外层 | overflow 父级会裁剪 fixed 元素 |

### 🟡 提交前检查清单

```bash
node check_html.js              # div net=0, JS braces net=0
python -m py_compile backend/*.py  # 无 SyntaxError
git status                      # 确认改动范围
git push origin main && git push gitee main  # 同步双远端
```

---

## 十、前端页面模块速查（index.html）

| Tab | 功能 | 关键 Vue 变量 |
|-----|------|--------------|
| 🎬 影片库 | 分页展示 + 搜索 + 详情弹窗 | `movies`, `selectedMovie`, `searchQuery` |
| 📂 本地视频 | 添加目录/扫描/批量刮削 | `localSources`, `localVideos`, `scrapePanel` |
| 🎊 Jellyfin | 扫描 Jellyfin 格式库 | `jellyfinStats`, `jellyfinScanResult` |
| 👩 类别 | 女演员/番号系列分类浏览 | `categories`, `actorList`, `seriesList` |
| 📁 整理 | 文件整理（预览/复制/移动） | `organizePanel`, `organizeItems`, `organizeRunning` |
| 🌐 翻译 | 翻译功能（勿动）⚠️ | `translator.py` + 前端翻译 Tab |

**SSE 事件处理统一位置**：`index.html` 约 3700-3780 行

---

## 十一、当前未完成任务（Phase 计划）

| 阶段 | 状态 | 内容 |
|------|------|------|
| Phase 0.5 整理功能 | ✅ 完成 | 文件整理、Jellyfin同步、刮削列表清理 |
| Phase 1 安全稳定 | 📋 待开发 | googletrans 异常隔离、全局异常处理 |
| Phase 2 架构优化 | 📋 待开发 | main.py 拆分（routes/）、Alembic 迁移 |
| Phase 3 前端现代化 | 📋 待开发 | Vite + Vue 3 + TypeScript |
| Phase 4 质量/DevOps | 📋 待开发 | pytest + CI/CD + Docker |

详细任务列表见 `docs/PROJECT_PLAN.md`。

---

## 十二、常用命令速查

```powershell
# 启动后端
cd F:\github\MyMovieDB
.\start-backend.ps1

# 验证 HTML 结构
node check_html.js

# 验证 Python 语法
python -m py_compile backend/organizer.py
python -m py_compile backend/main.py

# 提交推送到双远端
git add -A
git commit -m "feat: ..."
git push origin main
git push gitee main

# 查看最近提交
git log --oneline -5
```

---

*本 Skill 由 小尼克 (WorkBuddy AI) 于 2026-04-27 整理。*  
*详细代码说明见 references/code-map.md，开发纪律见 references/discipline.md*
