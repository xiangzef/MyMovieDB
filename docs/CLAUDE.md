# MyMovieDB - AI 开发助手上下文

> ⚠️ **开始任何开发工作前，请先阅读 `docs/PROJECT_PLAN.md` 全文。**

---

## 项目概述

本地影视库刮削器。Python + FastAPI + SQLite + Vue.js（单文件 SPA）

**项目路径**: `F:\github\MyMovieDB`

**关键路径**:
- 后端入口: `backend/main.py` (~3000 行)
- 数据库: `backend/database.py`
- 爬虫: `backend/scraper.py`
- 头像: `backend/gfriends.py`
- 前端: `frontend/index.html` (3128 行 Vue SPA)
- 配置: `backend/config.py`（番号识别正则）

**启动**: `.\start-backend.ps1`（PowerShell）

---

## 当前最重要的任务

### 🔴 最高优先级：Phase 0.5 — 整理功能开发

详见 `PROJECT_PLAN.md` → 章节「Phase 0.5」

**目标**: 开发文件整理功能，按 Jellyfin 结构重组视频文件

**目标文件夹结构**:
```
{根}\jellyfin\{女演员}\{番号}\{番号}.mp4
                              \{番号}.nfo
                              \{番号}-poster.jpg
                              \{番号}-fanart.jpg
                              \{番号}-thumb.jpg
```

**字幕后缀识别**（文件名级别）:
- `IPZZ-792.mp4` → 无字幕 (`subtitle_type = none`)
- `IPZZ-792-C.mp4` → 中文字幕 (`subtitle_type = chinese`)
- `IPZZ-792-U.mp4` → 英文字幕 (`subtitle_type = english`)
- `IPZZ-792-UC.mp4` → 双语字幕 (`subtitle_type = bilingual`)

**数据库变更**: `movies` 表需添加 `subtitle_type` 列（值: `none|chinese|english|bilingual`）

**新建模块**: `backend/organizer.py`（整理核心逻辑）

---

## 开发纪律

1. **每次代码变更 → 同步更新 `PROJECT_PLAN.md` 开发日志**
2. **main.py 新增代码 ≤ 50 行**（超了就拆到独立模块）
3. **数据库字段变更 → 同步 `ALTER TABLE` + `models.py` + API**
4. **AI 接力流程**: 读 PLAN.md → 查开发日志 → 从最高优先级继续

---

## 数据库

- SQLite: `data/movies.db`
- 头像: `data/avatars/`（已从 git 排除，命名规范：真实演员名字符）
- 封面: `data/covers/`

---

## 已知风险

1. 爬虫数据源质量不稳定（Avdanyuwiki/Avbase/Javcup 均有问题）
2. 网络路径 (UNC) 在 Windows 下需特殊处理
3. >10GB 大文件需要进度条

---

## 技术债务

- `main.py` 超过 3000 行 → Phase 2 拆分
- 前端 3128 行无构建 → Phase 3 迁移 Vite+TypeScript
- googletrans 已弃用 → Phase 1 替换 deep-translator
