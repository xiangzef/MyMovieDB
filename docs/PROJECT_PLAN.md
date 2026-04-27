# MyMovieDB 重构 + 整理功能 · 项目计划书

> **版本**: v2.0  
> **制定日期**: 2026-04-03  
> **负责人**: 小尼克 (WorkBuddy AI)  
> **项目路径**: `F:\github\MyMovieDB`  
> **本文档用途**: AI 接力工作指南 + 开发纪律规范

---

## 📌 目录

1. [项目背景](#1-项目背景)
2. [新增功能：整理功能](#2-新增功能整理功能)
3. [四阶段重构计划](#3-四阶段重构计划)
4. [字幕信息集成](#4-字幕信息集成)
5. [数据库变更](#5-数据库变更)
6. [API 设计](#6-api-设计)
7. [开发纪律规范](#7-开发纪律规范)
8. [Token 与成本估算](#8-token-与成本估算)
9. [接力注意事项](#9-接力注意事项)

---

## 1. 项目背景

### 1.1 现状

- **技术栈**: Python (FastAPI) + SQLite + 单文件 Vue.js 前端
- **问题**: `main.py` 超过 3000 行，scraper/gfriends/database 耦合严重，无类型校验，无测试
- **已有功能**: 多源刮削、Jellyfin 扫描、头像批量下载、NFO 生成
- **缺失功能**: 文件夹整理、字幕信息管理

### 1.2 项目目标

1. ✅ **重构**: 拆分为清晰架构，提升可维护性
2. ✅ **新增**: 整理功能（Jellyfin 标准化文件夹结构）
3. ✅ **完善**: 字幕信息识别与前端展示
4. ✅ **规范**: 建立开发纪律，确保 AI 接力可行性

---

## 2. 新增功能：整理功能

### 2.1 功能概述

**整理功能**扫描用户指定的源目录（本地硬盘或网络硬盘），将视频文件按 Jellyfin 标准文件夹结构重新组织。

### 2.2 目标文件夹结构

```
驱动器根目录 (如 E:\)
└── jellyfin\
    └── {女演员名}\
        └── {番号}\
            ├── {番号}-fanart.jpg      # 背景图
            ├── {番号}-poster.jpg      # 海报
            ├── {番号}-thumb.jpg       # 缩略图
            ├── {番号}.nfo             # Jellyfin 元数据 (Kodi 兼容)
            └── {番号}{后缀}.mp4      # 视频文件 (保留原文件名含后缀)
```

**示例**:
```
E:\jellyfin\三上悠亜\IPZZ-792\IPZZ-792.mp4
E:\jellyfin\三上悠亜\IPZZ-792\IPZZ-792.nfo
E:\jellyfin\三上悠亜\IPZZ-792\IPZZ-792-poster.jpg
E:\jellyfin\三上悠亜\IPZZ-792\IPZZ-792-fanart.jpg
E:\jellyfin\三上悠亜\IPZZ-792\IPZZ-792-thumb.jpg
```

### 2.3 字幕后缀识别规则

| 文件名后缀 | 字幕类型 | 数据库值 | NFO 标签 | 说明 |
|-----------|---------|---------|---------|------|
| `IPZZ-792.mp4` | 无字幕 | `none` | — | 原始文件 |
| `IPZZ-792-C.mp4` | 中文字幕 | `chinese` | `<subtitle_type>chinese</subtitle_type>` | 有字幕 |
| `IPZZ-792-U.mp4` | 英文字幕 | `english` | `<subtitle_type>english</subtitle_type>` | 有字幕 |
| `IPZZ-792-UC.mp4` | 双语字幕 | `bilingual` | `<subtitle_type>bilingual</subtitle_type>` | 两种都有 |

**识别正则表达式**:
```python
# 字幕后缀检测（加在番号识别之后）
SUBTITLE_SUFFIX_PATTERN = re.compile(
    r'^(?P<code>[A-Z]{2,6}-\d{2,5})'
    r'(?:-(?P<suffix>C|U|UC))?'
    r'(?:\.(?P<ext>\w+))?$',
    re.IGNORECASE
)
```

### 2.4 整理流程

```
[1] 用户选择源目录（可多选，包含网络路径）
        ↓
[2] 扫描目录下所有视频文件（*.mp4/*.mkv/*.avi/*.wmv）
        ↓
[3] 从文件名提取番号（含字幕后缀）
    例: "FC2-PPV-123456-C.mp4" → code="FC2-PPV-123456", suffix="C"
        ↓
[4] 查询数据库获取演员名（主女演员，第一个）
    如未查到，使用"未知演员"作为目录名
        ↓
[5] 构建目标路径
    {目标根目录}/jellyfin/{女演员名}/{番号}/{原文件名}
        ↓
[6] 检查目标路径是否已存在
    - 不存在: 直接复制/移动
    - 已存在: 检查文件大小
        → 源更大: 提示覆盖
        → 相同/更小: 跳过（可配置）
        ↓
[7] 生成/更新 NFO 文件（嵌入 subtitle_type）
        ↓
[8] 汇总报告（SSE 流式输出）
```

### 2.5 整理模式

| 模式 | 说明 | 风险 |
|------|------|------|
| **预览 (Preview)** | 仅扫描，生成操作清单，不实际移动文件 | 无 |
| **复制 (Copy)** | 复制到目标目录，保留源文件 | 低 |
| **移动 (Move)** | 移动到目标目录，删除源文件 | ⚠️ 高 |

### 2.6 模块文件规划

```
backend/
├── organizer.py          # [新建] 整理功能核心逻辑
│   ├── scan_directory()           # 扫描源目录
│   ├── extract_code_with_suffix() # 番号+字幕后缀提取
│   ├── build_target_path()        # 构建 Jellyfin 路径
│   ├── organize_file()            # 执行整理（复制/移动）
│   ├── generate_nfo_with_subtitle() # 带字幕类型的 NFO 生成
│   └── get_organize_preview()     # 预览模式：生成操作清单
│
├── models.py              # [修改] MovieResponse 添加 subtitle_type
├── database.py            # [修改] movies 表添加 subtitle_type 列
└── main.py                # [修改] 添加 /organize 路由组
```

---

## 3. 四阶段重构计划

### 3.1 总览

| 阶段 | 内容 | 任务数 | 工时 | Token 预估 | 优先级 |
|------|------|--------|------|-----------|--------|
| 🔴 **Phase 1** | 安全稳定（FastAPI/Pydantic/googletrans） | 4 | ~10h | ~20M | P0 |
| 🟡 **Phase 2** | 架构优化（main.py 拆分/Alembic/适配器） | 5 | ~20h | ~55M | P1 |
| 🟣 **Phase 3** | 前端现代化（Vite/组件拆分/TypeScript） | 5 | ~40h | ~109M | P2 |
| 🟢 **Phase 4** | 质量/DevOps（pytest/vitest/CI/CD） | 4 | ~22h | ~34M | P2 |
| 🆕 **Phase 0.5** | **整理功能开发** | 5 | ~15h | ~35M | **P0** |

> ⚠️ Phase 0.5（整理功能）是新插入的最高优先级阶段，与 Phase 1 并行开发。

---

### 3.2 Phase 0.5 — 整理功能（🆕 新增，P0）

**目标**: 开发文件整理功能并集成到前端

| 任务 | 文件 | 描述 | 复杂度 |
|------|------|------|--------|
| 0.5.1 | `database.py` | movies 表添加 `subtitle_type` 列 | 低 |
| 0.5.2 | `organizer.py` | 整理功能核心逻辑（扫描/提取/整理/NFO） | 高 |
| 0.5.3 | `models.py` | 添加 `SubtitleType` Enum + `OrganizeRequest`/`OrganizeResponse` | 中 |
| 0.5.4 | `main.py` | 添加 `/organize` 路由组（SSE 流式输出） | 中 |
| 0.5.5 | `index.html` | 前端：整理功能 UI（目录选择/模式切换/预览/执行） | 中 |

**数据库变更**:
```sql
ALTER TABLE movies ADD COLUMN subtitle_type TEXT DEFAULT 'none';
-- 值: 'none' | 'chinese' | 'english' | 'bilingual'
```

**API 设计**:
```
POST /organize/preview
  Body: { source_paths: string[], target_root: string }
  Response: SSE — { action: "found", path, code, suffix, target_path }

POST /organize/execute
  Body: { source_paths: string[], target_root: string, mode: "copy" | "move" }
  Response: SSE — { action: "copied" | "moved" | "skipped" | "error", ... }
```

---

### 3.3 Phase 1 — 安全稳定（P0，约 10h）

| 任务 | 文件 | 描述 | 复杂度 |
|------|------|------|--------|
| 1.1 | `main.py` | Pydantic v2 模型迁移（替换 BaseModel） | 中 |
| 1.2 | `scraper.py` | googletrans 异常隔离（超时兜底） | 低 |
| 1.3 | `gfriends.py` | 添加网络超时和重试上限 | 低 |
| 1.4 | `main.py` | FastAPI 全局异常处理器 | 中 |

**预计 Token**: ~20M

---

### 3.4 Phase 2 — 架构优化（P1，约 20h）

| 任务 | 文件 | 描述 | 复杂度 |
|------|------|------|--------|
| 2.1 | `main.py` | 路由拆分（routes/） | 高 |
| 2.2 | `database.py` | Alembic 迁移脚本 | 中 |
| 2.3 | `scraper.py` | 适配器模式重构（interface） | 高 |
| 2.4 | `models.py` | 统一 Pydantic v2 模型 | 中 |
| 2.5 | `main.py` | 配置外部化（.env） | 低 |

**预计 Token**: ~55M

---

### 3.5 Phase 3 — 前端现代化（P2，约 40h）

| 任务 | 文件 | 描述 | 复杂度 |
|------|------|------|--------|
| 3.1 | `frontend/` | Vite + Vue 3 迁移 | 高 |
| 3.2 | `frontend/` | TypeScript 全量迁移 | 高 |
| 3.3 | `frontend/` | 组件拆分（Modal, Grid, Header...） | 中 |
| 3.4 | `frontend/` | 整理功能 UI 组件 | 中 |
| 3.5 | `frontend/` | Pinia 状态管理 | 中 |

**预计 Token**: ~109M

---

### 3.6 Phase 4 — 质量/DevOps（P2，约 22h）

| 任务 | 文件 | 描述 | 复杂度 |
|------|------|------|--------|
| 4.1 | `tests/` | pytest 单元测试（覆盖率 > 60%） | 中 |
| 4.2 | `tests/` | vitest 前端测试 | 中 |
| 4.3 | `frontend/` | CI/CD 流水线（GitHub Actions） | 中 |
| 4.4 | `backend/` | Docker 化部署 | 中 |

**预计 Token**: ~34M

---

### 3.7 完整 Token 汇总

| 阶段 | Token 预估 |
|------|-----------|
| Phase 0.5（整理功能） | ~35M |
| Phase 1（安全稳定） | ~20M |
| Phase 2（架构优化） | ~55M |
| Phase 3（前端现代化） | ~109M |
| Phase 4（质量/DevOps） | ~34M |
| **总计** | **~253M** |

---

## 4. 字幕信息集成

### 4.1 NFO 文件格式（含字幕标签）

在 `backend/nfo_writer.py`（新建或扩展）:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<movie>
  <title>IPZZ-792</title>
  <originaltitle>...</originaltitle>
  <plot>...</plot>
  <genre>...</genre>
  <actor>
    <name>三上悠亜</name>
    <type>Actor</type>
  </actor>
  <premiered>2020-01-01</premiered>
  <studio>...</studio>
  <!-- Jellyfin 自定义字幕字段 -->
  <subtitle_type>chinese</subtitle_type>
  <local_subtitle>true</local_subtitle>
</movie>
```

### 4.2 前端展示

**电影详情弹窗**（`index.html`）:

```html
<!-- 在时长/制作商行之后添加 -->
<div class="modal-row" v-if="selectedMovie.subtitle_type && selectedMovie.subtitle_type !== 'none'">
  <span class="modal-label">字幕</span>
  <span class="subtitle-badge"
    :class="'subtitle-' + selectedMovie.subtitle_type">
    {{ subtitleLabel(selectedMovie.subtitle_type) }}
  </span>
</div>
```

**字幕徽章样式**:
- `subtitle-chinese`: 绿色标签「中文字幕 🇨🇳」
- `subtitle-english`: 蓝色标签「英文字幕 🇺🇸」
- `subtitle-bilingual`: 紫色标签「双语字幕 🌐」

### 4.3 字幕类型映射

```python
SUBTITLE_LABELS = {
    "none": None,               # 不显示
    "chinese": "中文字幕 🇨🇳",
    "english": "英文字幕 🇺🇸",
    "bilingual": "双语字幕 🌐",
}
```

---

## 5. 数据库变更

### 5.1 movies 表变更

```sql
-- 添加字幕类型列
ALTER TABLE movies ADD COLUMN subtitle_type TEXT DEFAULT 'none'
    CHECK(subtitle_type IN ('none', 'chinese', 'english', 'bilingual'));

-- 添加整理记录（可选，便于追溯）
ALTER TABLE movies ADD COLUMN last_organized_at TIMESTAMP;
ALTER TABLE movies ADD COLUMN organized_path TEXT;
```

### 5.2 数据迁移策略

```python
# backend/migrations/add_subtitle_type.py
def migrate():
    """自动迁移：为已整理的路径推断字幕类型"""
    conn = get_db()
    # 扫描已有的 jellyfin 目录结构
    # 从文件名后缀识别并更新数据库
```

---

## 6. API 设计

### 6.1 整理功能 API

```
POST   /organize/preview     预览整理计划（不实际移动）
POST   /organize/execute     执行整理（SSE 流式）
GET    /organize/status      查询整理状态
POST   /organize/stop        停止正在进行的整理
GET    /organize/jellyfin-config  获取 Jellyfin 根目录配置
```

### 6.2 响应格式（SSE）

```json
// 预览阶段
event: found
data: {"path": "E:/Videos/IPZZ-792-C.mp4", "code": "IPZZ-792", "suffix": "C", "target": "E:/jellyfin/三上悠亜/IPZZ-792/IPZZ-792-C.mp4", "status": "new"}

event: summary
data: {"total": 150, "new": 140, "exists": 8, "error": 2, "estimated_size": "120GB"}

// 执行阶段
event: copied
data: {"source": "E:/Videos/IPZZ-792-C.mp4", "target": "E:/jellyfin/三上悠亜/IPZZ-792/", "size": "1.2GB", "elapsed": "5s"}

event: error
data: {"path": "...", "reason": "目标路径权限不足"}
```

---

## 7. 开发纪律规范

### 7.1 核心原则

> **每次代码变更后，必须同步更新本计划书。**
> 本计划书是唯一的真相来源（Single Source of Truth）。

### 7.2 修改记录格式

每次完成一个任务（或部分完成），在下方「开发日志」中追加记录：

```markdown
## 📝 开发日志

### YYYY-MM-DD HH:MM — [任务ID] 任务名称
- **执行者**: 小尼克 / 其他 AI / 大尼克
- **变更文件**: `file1.py`, `file2.py`
- **变更内容**: 简要描述做了什么
- **Token 消耗**: 估算值
- **备注**: 遇到的问题/决策/风险
```

### 7.3 任务状态管理

| 状态 | 含义 | 更新时机 |
|------|------|---------|
| `📋 待开发` | 尚未开始 | 制定计划时 |
| `🔄 开发中` | 正在进行 | 开始执行时 |
| `✅ 完成` | 已交付 | 验证通过后 |
| `⚠️ 阻塞` | 等待前置条件 | 遇到阻塞时 |
| `🛠 优化` | 已完成但可改进 | 发现优化点时 |

### 7.4 AI 接力检查清单

每次开始新的开发会话前，AI 必须：

- [ ] 阅读本计划书全文
- [ ] 检查「开发日志」了解已完成/进行中任务
- [ ] 确认当前阶段的优先级
- [ ] 记录开始时间到开发日志
- [ ] 完成后更新任务状态 + 追加日志

### 7.5 代码质量纪律

1. **禁止**: 在 `main.py` 中新增 > 50 行的非路由代码
2. **必须**: 每个新模块有独立文件 + docstring
3. **必须**: 数据库字段变更同步更新 `database.py` 的 `ALTER TABLE` 逻辑
4. **必须**: 前端变更同步更新 `index.html` 中的 Vue 数据结构
5. **必须**: 新增 API 端点在本文档「API 设计」章节中注册

### 7.6 测试纪律

- 每个 `organize.py` 的核心函数（提取/路径构建/NFO生成）必须有单元测试
- Phase 4 之前至少保证关键路径可通过手动测试
- 不得提交导致 `start-backend.ps1` 启动失败的代码

---

## 📝 开发日志

> 每完成一个任务块，在此追加记录。

---

### 2026-04-03 22:05 — Phase 0.5 整理功能开发完成 ✅

- **执行者**: 小尼克 (WorkBuddy AI)
- **变更文件**:
  - `backend/database.py` — 添加 `subtitle_type`/`last_organized_at`/`organized_path` 列；`update_movie_organize_info()` + `get_movies_by_codes()` 新函数
  - `backend/models.py` — 添加 `SubtitleType` Enum、`SUBTITLE_LABELS`、`OrganizeRequest/OrganizeMode/OrganizePreviewItem/OrganizeProgress` 模型；`MovieResponse` 增加 `subtitle_type/organized_path/last_organized_at`
  - `backend/organizer.py` — **新建**，~340行，核心整理逻辑（SSE回调架构）
  - `backend/main.py` — 添加 `/organize/preview`、`/organize/execute`、`/organize/stop` 路由
  - `frontend/index.html` — 新增"📁 整理"Tab（含完整UI：源目录/目标目录/预览/执行/字幕徽章/详情弹窗字幕展示）
  - `PROJECT_PLAN.md` — 重构计划书（含整理功能设计、开发纪律）
  - `CLAUDE.md` — AI 接力上下文文件（Cursor/Cline 自动读取）

- **字幕后缀识别验证**:
  - ✅ `IPZZ-792-C.mp4` → `chinese`
  - ✅ `IPZZ-792-U.mp4` → `english`
  - ✅ `IPZZ-792-UC.mp4` → `bilingual`
  - ✅ `FC2-PPV-123456-C.mp4` → `chinese`（修复 FC2-PPV 正则）
  - ✅ `HEYDOUGA-1234-567-UC.mp4` → `bilingual`

- **Token 消耗**: Phase 0.5 约 ~8M（含 organzier.py 新建）
- **备注**:
  - JNT-1 类单数字番号无法识别字幕后缀（项目番号标准要求≥2位），符合预期
  - `organizer.py` 使用 SSE 回调架构（参考 jellyfin.py 的 SSE 模式）
  - 封面/NFO 复制：`_copy_asset_files()` 从 movie_data 已有路径复制（不再重复下载）


---

## 8. Token 与成本估算

### 8.1 分阶段 Token 明细

| 阶段 | 任务数 | 工时 | Token 预估 | Haoku 积分 | 4o-mini 积分 |
|------|--------|------|-----------|-----------|-------------|
| Phase 0.5 整理功能 | 5 | ~15h | ~35M | ~560 | ~1,400 |
| Phase 1 安全稳定 | 4 | ~10h | ~20M | ~320 | ~800 |
| Phase 2 架构优化 | 5 | ~20h | ~55M | ~880 | ~2,200 |
| Phase 3 前端现代化 | 5 | ~40h | ~109M | ~1,744 | ~4,360 |
| Phase 4 质量/DevOps | 4 | ~22h | ~34M | ~544 | ~1,360 |
| **总计** | **23** | **~107h** | **~253M** | **~4,048** | **~10,120** |

### 8.2 积分说明

> 以 $0.008 / 1K token（Haoku）为基准  
> 4o-mini: $0.02 / 1K token  
> 实际消耗取决于代码复杂度波动，±20% 属正常范围

### 8.3 成本优化建议

- **Phase 1、2.5**（整理功能核心 + 安全稳定）：用 Haoku，节省约 60%
- **Phase 2、3**（复杂重构 + TypeScript）：用 Sonnet 3.5 Haiku，保质量
- **Phase 4**（测试 + CI）：用 Haoku，简单脚本无需高级模型

---

## 9. 接力注意事项

### 9.1 关键文件索引

| 文件 | 用途 | 注意事项 |
|------|------|---------|
| `backend/main.py` | FastAPI 入口，当前 ~3000 行 | 路由拆分目标：routes/ |
| `backend/scraper.py` | 爬虫模块，含多源适配器 | 适配器模式重构重点 |
| `backend/database.py` | 数据库操作 | `ALTER TABLE` 变更需向后兼容 |
| `backend/gfriends.py` | 头像下载 | URL 编码问题历史，需关注 |
| `backend/jellyfin.py` | Jellyfin 扫描 | 已有 SSE 模式可参考 |
| `frontend/index.html` | 单文件 Vue SPA | 3128 行，TypeScript 迁移目标 |
| `backend/config.py` | 配置模块 | 番号识别正则在此 |
| `backend/models.py` | Pydantic 模型 | 需添加 SubtitleType/OrganizeRequest |

### 9.2 数据库状态

- SQLite 文件: `F:\github\MyMovieDB\data\movies.db`
- 头像目录: `F:\github\MyMovieDB\data\avatars\`（已从 git 排除）
- 封面目录: `F:\github\MyMovieDB\data\covers\`
- 演员头像命名规范（2026-04-03 重构）: 真实名字（非 URL 编码）

### 9.3 已知风险

1. **网络爬虫不稳定**: Avdanyuwiki/Avbase/Javcup 均存在质量问题，整理功能依赖数据库已有数据
2. **网络路径**: `\\server\share` 等 UNC 路径在 Windows 下需特殊处理
3. **大文件复制**: >10GB 的文件需要进度条和断点续传

### 9.4 启动命令

```powershell
# 启动后端
cd F:\github\MyMovieDB
.\start-backend.ps1

# 访问前端
# http://localhost:端口号（见 start-backend.ps1 输出）
```

---

## ✅ 计划书状态

| 项目 | 状态 |
|------|------|
| 功能设计 | ✅ 完成 |
| 数据库变更 | ✅ 完成 |
| Phase 0.5 开发 | ✅ 完成 |
| Phase 1 开发 | 📋 待开发 |
| Phase 2 开发 | 📋 待开发 |
| Phase 3 开发 | 📋 待开发 |
| Phase 4 开发 | 📋 待开发 |

*本计划书由 WorkBuddy AI (小尼克) 于 2026-04-03 制定，请保持更新。*
