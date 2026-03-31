# MyMovieDB - 本地影视库刮削器

一个轻量级的本地影视库管理工具，支持刮削、搜索和浏览影片信息。

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)
![Vue](https://img.shields.io/badge/Vue-3-4FC08D.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

---

## 功能特性

| 功能 | 说明 |
|------|------|
| 🎬 **影片刮削** | 从多个数据源自动获取影片信息 |
| 📁 **Jellyfin 导入** | 一键扫描 Jellyfin 格式影视库，自动导入元数据 |
| 📂 **本地视频管理** | 扫描本地目录，批量刮削视频文件 |
| 🔍 **智能搜索** | 支持编号、标题搜索 |
| 🖼️ **封面管理** | 自动下载和本地存储封面图 |
| 👩 **女演员分类** | gfriends 头像引擎，按女演员浏览作品 |
| 🏷️ **番号系列分类** | 按番号前缀分类浏览作品 |
| 🌐 **Web 界面** | 响应式设计，支持移动端 |
| 📦 **一键打包** | 可编译成 exe，系统托盘运行 |

---

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python + FastAPI |
| 数据库 | SQLite |
| 前端 | Vue.js 3（CDN 单文件） |
| 爬虫 | requests + BeautifulSoup4 |
| 女优头像 | gfriends 仓库（`gfriends/gfriends`） |

---

## 项目结构

```
MyMovieDB/
├── backend/                 # 后端
│   ├── main.py              # FastAPI 主入口
│   ├── database.py           # SQLite 数据库操作
│   ├── scraper.py           # 爬虫模块（多数据源）
│   ├── gfriends.py          # gfriends 女优头像引擎
│   ├── jellyfin.py          # Jellyfin 扫描模块
│   ├── models.py            # Pydantic 数据模型
│   ├── config.py            # 配置管理
│   ├── tray_launcher.py      # 系统托盘启动器
│   └── requirements.txt      # Python 依赖
├── frontend/
│   └── index.html            # Vue 3 单页应用
├── data/                     # 数据目录（自动创建）
│   ├── movies.db              # SQLite 数据库
│   ├── covers/               # 封面图存储
│   ├── avatars/              # gfriends 头像缓存
│   ├── nfo/                  # NFO 文件
│   └── backup/               # 数据库备份
├── dist/                     # 打包输出目录
│   └── MyMovieDB.exe        # 打包后的程序
├── README.md                  # 本文档
└── config.ini                # 配置文件
```

---

## 快速开始

### 方式一：直接运行 Python（开发模式）

```bash
# 1. 安装依赖
cd backend
pip install -r requirements.txt

# 2. 启动后端
python -m uvicorn main:app --reload

# 3. 打开前端
# 浏览器直接打开 frontend/index.html
# 后端地址：http://localhost:8000
```

### 方式二：打包成 exe（推荐）

```bash
# 1. 进入 backend 目录
cd backend

# 2. 安装打包依赖
pip install pystray Pillow pyinstaller

# 3. 运行打包脚本
build.bat
```

打包完成后，`dist/MyMovieDB.exe` 即为可执行文件，支持系统托盘运行。

---

## 系统托盘功能

| 操作 | 说明 |
|------|------|
| 双击托盘图标 | 打开浏览器 |
| 右键 → 打开 | 打开浏览器 |
| 右键 → 退出 | 完全关闭程序 |

**特点：**
- 后台静默运行，不显示黑窗口
- 关闭浏览器不会关闭程序
- 开机自启（可选功能）

---

## 影片库管理

### 影片刮削

支持单个刮削和批量刮削，自动从多个数据源获取：

- 番号、标题、封面图
- 发布日期、制作商、发行商
- 女演员、类别标签
- 剧照预览

**刮削策略：**
- 已完整刮削的影片自动跳过（`scrape_status = complete`）
- 部分刮削的影片可一键修复
- 支持 SSE 实时进度显示

### 本地视频管理

扫描本地目录，自动识别视频文件：

```
支持的格式：mp4, mkv, avi, mov, wmv, flv, webm, m4v, mpg, mpeg, ts, mts, m2ts, vob
```

**功能：**
- 批量扫描目录
- 自动提取番号
- 批量刮削（多线程）
- 刮削状态检查与修复

---

## 女演员分类页（gfriends 头像引擎）

### 核心功能

- 📊 **女演员统计** — 按作品数量降序展示所有女演员
- 🖼️ **头像展示** — 从 [gfriends](https://github.com/gfriends/gfriends) 仓库获取真实女优头像
- 🔍 **真伪识别** — gfriends 收录的女演员有头像；未收录的显示为「佚名」（可能是素人/临时艺名）
- ⬇️ **批量下载** — 一键下载所有已知女优的头像到本地缓存

### 工作原理

gfriends 是一个收录了 **10,000+** AV 女优头像的开源仓库：

```
https://raw.githubusercontent.com/gfriends/gfriends/master/
├── Filetree.json      ← 演员名→头像URL映射（几MB）
└── Content/           ← 头像图片目录
    ├── A/             ← A 开头演员
    ├── S/             ← S 开头演员
    └── ...
```

**判断逻辑：**
| 状态 | 说明 |
|------|------|
| gfriends 能查到 | 知名 AV 女优，显示头像 ✅ |
| gfriends 查不到 | 素人/临时艺名，显示为「佚名」❌ |

### 本地缓存

头像图片保存在 `data/avatars/` 目录，按 `md5(演员名)[12:-12].jpg` 命名，避免文件名冲突。

---

## Jellyfin 导入功能

### 目录结构要求

```
影视库/
├── 女星名称/
│   ├── SSIS-001/
│   │   ├── SSIS-001.mp4        # 视频文件
│   │   ├── SSIS-001.nfo        # NFO 元数据（可选）
│   │   ├── SSIS-001-poster.jpg # 海报图（可选）
│   │   └── SSIS-001-fanart.jpg # 背景图（可选）
│   └── ...
└── ...
```

### 使用方法

1. 点击「本地目录」Tab → 「🔍 扫描 Jellyfin 格式影视库」
2. 输入影视库路径，等待扫描完成
3. 导入的影片标记为 `📁 Jellyfin` 来源，自动关联本地视频路径

**特点：**
- ✅ 支持无 NFO 文件的目录
- ✅ 支持多种图片命名格式
- ✅ SSE 实时进度显示
- ✅ 支持停止扫描

---

## 番号系列分类

按番号前缀分类展示影片，如：

| 系列 | 代表作品 |
|------|---------|
| SSNI | 61 部 |
| ABP | 55 部 |
| SSIS | 47 部 |
| SONE | 43 部 |

点击任意系列可查看该系列所有影片的详情列表。

---

## API 接口

### 影片相关

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 前端页面 |
| `/health` | GET | 健康检查 |
| `/movies` | GET | 影片列表（分页、筛选） |
| `/movies/{id}` | GET | 影片详情 |
| `/movies/code/{code}` | GET | 按番号查询 |
| `/search?q=` | GET | 搜索影片 |

### 刮削相关

| 接口 | 方法 | 说明 |
|------|------|------|
| `/scrape` | POST | 刮削单个影片 |
| `/scrape/batch` | POST | 批量刮削（SSE 实时进度） |
| `/scrape/stop` | POST | 停止刮削任务 |
| `/scrape/status/{job_id}` | GET | 查询刮削任务状态 |
| `/scrape/check/{movie_id}` | GET | 检查影片刮削完整性 |
| `/scrape/fix/{movie_id}` | POST | 修复影片刮削 |

### 本地目录

| 接口 | 方法 | 说明 |
|------|------|------|
| `/local-sources` | GET | 目录列表 |
| `/local-sources` | POST | 添加目录 |
| `/local-sources/{id}` | DELETE | 删除目录 |
| `/local-sources/scan` | POST | 扫描所有目录（SSE） |
| `/local-sources/{id}/scrape` | POST | 扫描指定目录 |
| `/local-videos` | GET | 本地视频列表（分页） |
| `/local-videos/stats` | GET | 本地视频统计 |

### Jellyfin

| 接口 | 方法 | 说明 |
|------|------|------|
| `/jellyfin/scan` | POST | 扫描 Jellyfin 库（SSE） |
| `/jellyfin/stats` | GET | Jellyfin 导入统计 |

### 类别

| 接口 | 方法 | 说明 |
|------|------|------|
| `/categories/stats` | GET | 类别统计概览 |
| `/categories/actors` | GET | 女演员列表（分页、搜索） |
| `/categories/series` | GET | 番号系列列表（分页、搜索） |
| `/categories/actors/{name}/movies` | GET | 某女演员的影片 |
| `/categories/series/{prefix}/movies` | GET | 某番号系列的影片 |

### 女演员头像

| 接口 | 方法 | 说明 |
|------|------|------|
| `/actors/lookup/{name}` | GET | 查询演员是否为真实女优 |
| `/actors/download-avatars` | POST | 批量下载头像 |
| `/avatars/{hash}.jpg` | GET | 头像图片 |

### 封面与文件

| 接口 | 方法 | 说明 |
|------|------|------|
| `/covers/{path}` | GET | 获取封面图 |
| `/local-image` | GET | 获取本地图片（安全限制） |
| `/open-folder` | POST | 打开文件夹 |

> 完整 API 文档：http://localhost:8000/docs

---

## 数据源

| 数据源 | 状态 | 说明 |
|--------|------|------|
| Fanza (DMM) | ✅ 主力 | 官方站点，数据最全 |
| Avbase | ✅ 备用 | 100% 成功率，75% 完整度 |
| AV-Wiki | ✅ 备用 | 100% 成功率 |
| Javcup | ✅ 备用 | 100% 成功率 |
| 其他 | ❌ 已禁用 | 403/需JS/需hash |

---

## 数据存储

| 目录 | 说明 |
|------|------|
| `data/movies.db` | SQLite 数据库 |
| `data/covers/` | 封面图（按 md5 命名） |
| `data/avatars/` | gfriends 头像缓存 |
| `data/nfo/` | NFO 元数据文件 |
| `data/backup/` | 数据库自动备份 |

---

## 常见问题

**Q: 刮削失败怎么办？**
A: 检查网络连接，可能是数据源不可用。可以尝试稍后重试。

**Q: 翻译功能不工作？**
A: Google Translate 可能被墙，需要 VPN 或使用代理。

**Q: 如何查看日志？**
A: 运行 Python 时终端会显示详细日志。

**Q: 女演员显示「佚名」是什么意思？**
A: 表示该演员不在 gfriends 仓库中，可能是素人/临时艺名（马甲），无法关联其系列作品。

**Q: 如何下载女优头像？**
A: 在「类别」Tab 点击「批量下载头像」，程序会自动从 gfriends 仓库下载所有已知女优的头像到本地。

---

## 配置说明

数据库会自动初始化，无需手动配置。

封面图保存在 `data/covers/` 目录，头像缓存在 `data/avatars/` 目录。

---

## 许可证

MIT License
