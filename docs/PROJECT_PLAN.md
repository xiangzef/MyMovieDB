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

### 2026-04-28 22:55 — 翻译模块重构 + 文件整理 ✅

- **执行者**: 小尼克 (WorkBuddy AI)
- **变更文件**:
  - `backend/translator.py` — 重构翻译模块，改用 Ollama qwen2.5:7b 本地模型翻译；移除 Google/DeepL API 依赖
  - `tests/test_translate.py` — 重构测试脚本，统一工作流程：音频持久化 → 语音识别 → 翻译 → SRT生成 → 音频清理
  - `backend/main.py` — 修改（翻译相关）
  - `.claude/settings.json` — 清理过时的权限规则
  - `SKILL.md` — 更新目录结构，translator.py 不再标注"勿动"
  - `code-map.md` — 更新 translator.py 说明

- **翻译模块新架构**:
  - 音频: `{视频名}_audio.wav` 本地持久化存储
  - 语音识别: Faster-Whisper（带时间戳 segments）
  - 翻译: Ollama qwen2.5:7b 本地模型（http://localhost:11434）
  - SRT字幕: 带时间戳的 SRT 文件
  - 流程: 提取音频 → 识别 → 翻译 → 生成SRT → 成功后删除音频；中途失败保留音频供断点续传

- **文件整理**:
  - `frontend/debug_indent.py` → `tests/debug_indent.py`
  - `frontend/debug_out.txt` → `logs/debug_out.txt`
  - `frontend/index.html.orig` + `frontend/index.html.bak20260401` → `backups/`

- **提交**: git commit -m "feat: 翻译模块重构 + 文件整理"

---

### 2026-04-29 18:30 — 添加 Vosk 备选方案 + 翻译模块完善 ✅

- **执行者**: 小尼克 (WorkBuddy AI)
- **变更文件**:
  - `backend/translator.py` — 添加 VOSK_AVAILABLE + TRANSLATOR_AVAILABLE 标志位；`_transcribe_with_vosk()` 方法
  - `backend/main.py` — `play_video` 已修复 `get_all_sources` → `get_local_sources`

- **Token 消耗**: 约 ~2M
- **备注**:
  - Whisper 网络下载模型失败时自动回退到 Vosk
  - Vosk 离线日语识别不提供时间戳（需改用 chunk 分块方案）

---

### 2026-04-29 23:05 — 翻译模块完成 Faster-Whisper VAD + Ollama 两步流程 ✅

- **执行者**: 小尼克 (WorkBuddy AI)
- **变更文件**:
  - `backend/translator.py` — 添加 HuggingFace 镜像源(HF_ENDPOINT)、能量检测 VAD(`_energy_based_vad`)、Vosk VAD 分段识别(`_transcribe_with_vosk_vad`)
  - `tests/test_translate.py` — 重写为 Faster-Whisper VAD 工作流

- **翻译模块最终架构**:
  ```
  视频 → ffmpeg提取音频 → Faster-Whisper VAD 识别（句级时间戳）→ 日语SRT
                                                                        ↓
                                                              Ollama qwen2.5:7b 逐句翻译
                                                                        ↓
                                                              生成双语SRT + 文本对照
  ```
  - 优先使用 Faster-Whisper（带 Silero VAD，精确句级时间戳）
  - 若 Whisper 不可用/网络不通 → 回退到 能量检测VAD + Vosk 分段识别
  - 镜像源: `https://hf-mirror.com` 解决国内网络问题

- **实测结果（2小时视频 HODV-20574）**:
  | 项目 | 数值 |
  |------|------|
  | 视频总时长 | 2小时4分 (7447秒) |
  | VAD过滤后语音 | ~9分钟 (594秒) |
  | 识别片段数 | 374个 |
  | 日文字符 | 2970 |
  | 生成文件 | `_ja.srt` (23KB), `.srt` (30KB双语), `_translated.txt` (16KB) |

- **Token 消耗**: 约 ~3M
- **备注**:
  - faster-whisper base 模型约 75MB，已缓存本地
  - VAD 参数 `vad_parameters=dict(min_silence_duration_ms=500)` 正确写法
  - 音频文件在 SRT 生成成功后自动删除
  - tests/ 目录已在 .gitignore，不纳入版本控制

---

### 2026-11-07 — 盘库数据重建 + Z:\av 离线刮削 + LTX 破解整理 ✅

- **执行者**: OpenCode (GLM-5.3-Flash)
- **背景**: 用户把全部本地视频合并进 `X:\jellyfin`，库检索数据大面积失效（1125 条 local_videos 中 836 条死路径）；`Z:\av` 新增 108 部 LTX 破解版视频需刮削并原地整理。
- **变更文件**:
  - `backend/main.py` — `_is_valid_av_code` 修复误伤 bug：原 `prefix.startswith('SD')/endswith('BD')` 会拒掉 JBD / RBD / SDSI 等真实番号前缀，改为仅精确匹配排除词
  - `backend/scraper.py` — `download_and_crop_cover` 增加 DMM 图床 Referer 头（`https://www.dmm.co.jp/`），否则 dmm 图床 403
  - `scripts/step1_rescan_relink.py` — 死源删除 + 死记录清理 + X:\jellyfin 全量重扫（严格 Jellyfin 目录 + 宽松文件名兜底）+ movies 按 code 重连
  - `scripts/step2_scan_zav.py` — Z:\av 扫描入库（含 11 个手工番号映射，如 `snis00872hhb` → SNIS-087）
  - `scripts/step2_offline_scrape.py` — **离线刮削 driver：移植 peach 的 DMM GraphQL 源**（`api.video.dmm.co.jp/graphql`，直连、无年龄门、不需日本 IP）+ av-wiki 直连 + jav321 代理兜底
  - `scripts/step3_organize_ltx.py` — Z:\av 原地整理 `{演员}\{番号}\{番号}-LTX.mp4`，NFO 注入 `<tag>LTX</tag><tag>破解</tag>`
  - 其余 `salvage_*.py / fix_*.py` 为本轮一次性修复脚本
- **结果**:
  - X:\jellyfin 重扫 427 视频入库（388 严格 + 39 宽松兜底）；movies 重连 84 部、断开关联保留记录 762 部、jellyfin_status 刷新（complete 307 / partial 81 / broken 0）
  - Z:\av 108/108 入库（local_source id=14），33 部旧番号直接关联
  - 离线刮削 75 部：**DMM GraphQL 命中 64**、r18.dev 补刮 7、jav321/av-wiki 补 0（网络窗口期）
  - Step3 整理 104 部进 `{演员}\{番号}\` 结构 + LTX 标注；4 部全源未命中留根目录（ADN-151 / AVOP-004 / RBD-916 / SNIS-027）
- **关键经验**:
  - **网络矩阵**：av-wiki/javsee 可直连，jav321 需代理 7897，avbase/javcup/javdb/avdanyuwiki 被 Cloudflare 挑战（代理出口被封，cloudscraper 无效），DMM 网页有年龄门但 **GraphQL API 完全开放**——是当前最可靠的番号源，建议后续正式注册进 `config.ini` sources
  - SSE 批量刮削端点在 20 秒并行预算 + CF 封锁下基本不可用；离线直调 `enhanced_scraper`/自写源更可靠
  - 后端 stdout 必须 `PYTHONIOENCODING=utf-8`，否则 print emoji 会炸掉 SSE 流
  - r18.dev 影像库（`r18.dev/videos/vod/movies/detail/-/dvd_id={cid}/json`）覆盖 DMM 已下架老片，但标题/演员是英文
- **待办**: DMM 断流恢复后给 7 部 r18dev 换日文标题；4 部未命中片已由用户手工补全信息入库（ADN-151/AVOP-004/RBD-916/SNIS-027），源端确实无收录（DMM 无 cid、r18.dev 限流）

---

### 2026-11-07 — Z:\av 手工命名补录 + 全库重命名/女优合并 ✅

- **背景**: 用户为 4 部全源未命中的影片手工改文件名（写入番号+标题+女优）并补充封面图，另补全了 SSNI-473。要求统一命名格式、合并同一女优的多个艺名、英文罗马字艺名改日文。
- **入库**: `scripts/ingest_manual5.py` — ADN-151 / AVOP-004 / RBD-916 / SNIS-027 / SSNI-473 五部入库（含封面裁切 fanart/poster/thumb、NFO、LTX 标签）
- **重命名**: `scripts/rename_library.py`
  - 统一格式：`Z:\av\{女优}\{番号}+{电影名}+{女优名}+LTX\` 同名 `.mp4/.nfo/-poster.jpg/-fanart.jpg/-thumb.jpg`
  - 女优合并：**RION / 宇都宮しをん / 安齋らら → 安齋らら**（18 部）
  - 英文罗马字转日文：RION→安齋らら、Saeko Matsushita→松下紗栄子、Kokomi Sakura→桜ここみ、Ruri Saijo→西條るり、Anri Okita→沖田杏梨、Ema Yumekawa→夢川エマ、Shion Utsunomiya→宇都宮しをん
  - 标题清洗：去开头番号、去结尾重复女优名、非法字符替换、截断 60 字
- **最终结构**: 12 个女优目录 / 109 部影片（三上悠亜 43、松下紗栄子 38、安齋らら 18、其余 1-2 部）；根目录零残留；DB 路径 109/109 有效；**109/109 部海报+背景图齐全**（`fix_cover_remaining.py` + `fix_cover_stubborn.py` 多图床重试补齐 24 部）；SNIS-166 用 NFO 老数据修正标题为「秘密捜査官の女 巨乳エージェント恥辱の報酬」
- **脚本**: `scripts/fix_title_alias.py`（标题尾部旧艺名清理）、`scripts/finalize_rename.py`（NFO 艺人名日文化+LTX 标签校验）、`scripts/fix_cover_remaining.py`（缺图补抓）、`scripts/verify_rename.py`（结构校验）
- **备份**: 重命名清单 `data/rename_manifest_*.json`（可回滚）

---

### 2026-11-07 — javcli：本地 cmd 刮削 CLI ✅

- **背景**: 用户要求开发本地 cmd 输入输出的刮削程序，整合 Movie_Data_Capture / peach / JavSP / MyMovieDB 四家优秀刮削方法（JavSP 本地无源码，按方法整合实现）。
- **交付形态**: Python 包 `javcli/` + `scrape.bat` 启动器（用户确认；以后可选 PyInstaller 打 exe）；输出联动数据库为可选 `--save-db`（默认纯文件输出）。
- **变更文件**:
  - `javcli/__init__.py / __main__.py` — 包入口
  - `javcli/number.py` — 番号解析：MDC 规则表思路 + peach 水印剥离 + MyMovieDB 混合前缀排除（`WEBIPZZ-792`→None、`390JNT-114`→JNT-114）；`same_code()` 字母相同+数字整数相等（与 movies.db normalize_code 对齐，保留前导零）
  - `javcli/net.py` — 直连/代理(7897)交替重试、同主机 2s 间隔、每源首选路由（DMM 间歇 SSL 断流经验）
  - `javcli/merge.py` — peach 字段级合并：标量取第一个非空、actors 取第一个非空列表、genres 合并最多 3 家去重；title/release_date/duration/cover+actors+genres 齐了短路
  - `javcli/sources/` — `dmm.py`（GraphQL 猜 cid→搜索回核，移植 step2_offline_scrape）、`r18dev.py`（命中后回查 DMM 升级日文全量，移植 salvage_finalize 链）、`jav321.py`（代理 POST）、`legacy.py`（封装 backend 各 Legacy 爬虫+关翻译+身份闸）、`base.py` 分级、`__init__.py` 注册表
  - `javcli/output.py` — Kodi 兼容 NFO（MDC 字段集 + MyMovieDB fanart/thumb/filenameandpath）、封面三图裁切（fanart 原图 / poster 右侧 2:3 1000x1500 / thumb 300x450）、`{番号}+{标题}+{女优}+LTX` 目录命名、ACTOR_ALIAS 女优合并、DMM 图床 Referer + ps→pl 候选
  - `javcli/dbio.py` — `--save-db`：same_code 对齐已有番号防重复建行、upsert 后**恢复库里已存在的 Z:\av 资产路径**（fanart/poster/thumb/video/organized）防覆盖、local_videos 关联
  - `javcli/cli.py` — argparse 主入口；`--json` 合并结果打 stdout（日志走 stderr）；目录批量给 `-o` 时写 `-o/<番号>/`
  - `scrape.bat` — cmd 启动器（**必须 ASCII + CRLF**：UTF-8 中文注释 + LF 行尾曾导致 cmd 解析死循环）
  - `javcli/README.md` — 用法/源链/参数文档
- **结果（全部实测通过）**:
  - 番号解析 18 用例全过（推广水印/混合前缀/数字前缀/FC2/HEYZO/carib/紧凑番号）
  - 裸番号 SSIS-541：DMM 命中短路，fanart(2184x1468)/poster(1000x1500)/thumb(300x450)/NFO/JSON 全出
  - 备源链 `javsee,av-wiki,jav321`：av-wiki 命中（javsee CF 403 属已知）
  - `--organize`：dummy 文件移动改名为 `三上悠亜\SSNI-473+...+三上悠亜+LTX\`，NFO filenameandpath 正确
  - `--save-db` SSIS-541：复用 movie_id=1627、Z:\av 资产路径全部保留、genres 保留库内 破解/中文字幕 标签、local_videos 关联
  - 目录批量 2 部（BF-542 走 r18dev→DMM 升级链、SNIS-166 r18dev 英文数据）均写入 `-o` 目录
  - `--json` 管道 `python -c json.load(sys.stdin)` 解析成功；`scrape.bat` 端到端中文输出正常
- **已知局限**: SNIS-166 类 DMM 无收录片 r18dev 只有英文标题且封面可能下载失败；javsee/avbase/javcup/javdb 受 Cloudflare 影响命中率不稳
- **待办**: 清理 `C:\Temp\opencode\javcli_test*` 测试目录；可选把 DMM GraphQL 正式并入 backend 供 UI 使用

---

### 2026-11-09 — javcli 易用性修复 + 新增视频实测 ✅

- **问题 1（用户反馈「打开就关闭了」）**: 双击 `scrape.bat` 无参数 → 打印帮助后 `exit /b 2` → 窗口瞬间关闭，什么都看不见。
  - **初版修复**: 无参数时显示用法并 `pause` 留窗；`.venv` 缺失时也提示（仅无参数时留窗，带参数不 pause）。
  - **修复中发现的更深的 bug（关键教训）**: 初版 `if "%~1"=="" (...)` 块里的 `echo javcli ... (MDC / peach ...)` **未转义右括号被 cmd 当作 if 块结束符**，导致块后面的 `echo Usage:` + `exit /b 2` 变成无条件执行——**带参数也走进无参数分支**（`--version` 都被吃掉）。隔离复现（dbg4.bat）确认后，把块内所有 echo 的 `()` 去掉/改写，注释里写明「if 块内 echo 禁止未转义括号」。
  - **最终验证**: `--version`→`javcli 0.1.0` EXIT=0；`--list-sources` EXIT=0；无参数→用法+pause 留窗 EXIT=2；`scrape.bat TEK-089 --no-images -o ...` 端到端参数传递正常（全源未命中时 EXIT=1，属网络波动：TEK-089 上一轮还能 r18dev 命中）。
- **问题 2（广告垃圾文件误解析）**: PRESTIGE 目录的广告文件被解析成假番号并白白发网络请求：`UUS75.COM→UUS-75`、`uuf39.com→UUF-39`、`GM.GM85.CC→GM-85`、`vip1196→VIP-1196`。
  - **修复 `javcli/number.py`**: ① `_TLD_RE` 域名后缀拒收（只认常见 TLD com/net/org/cc/la/vip/xyz/top/cc 等，`IPZZ-901.restored` 这类正常点号后缀不误伤）；② 紧凑格式（字母数字无分隔）前一字符是 `.` 时拒收（域名残留特征）。
- **测试**:
  - `javcli/_test_number.py` 回归 **40 用例全过**（原有 13 + 点号后缀不误伤 5 + 广告拒收 11 + 新增 20 文件解析 + same_code 3）
  - **Z:\av 11/8–11/9 新增 20 部视频实测：20/20 DMM 命中、零失败**（FNS/IPZZ/SSIS/HMN/NTRH 系列，含 `www.98T.la@` 水印、`_4K60帧原档`、`(1)` 重名后缀、中文长文件名等刁钻命名），每部输出 fanart/poster/thumb/NFO/JSON 五件套到 `-o` 目录
  - PRESTIGE-ABS 目录批量：8 部 ABS 真片 + 16 个广告（广告全部被解析层拒收跳过）
- **PRESTIGE-ABS 目录批量**: 24 任务 —— **16 个广告全部被解析层拒收跳过** ✅；8 部 ABS（`ABS-049/072/078/095/098/128/137/142`）**全源未命中**，摸底结论：
  - DMM：4 种搜索词全 0 结果 —— **DMM 不收录プレステージ**；av-wiki 搜索「0件」（キカタン/シロウト站，不收 PRESTIGE）；r18dev/javsee/jav321 无收录
  - avbase/javcup/javdb/avsox/avmoo/avdanyuwiki：**必须走代理 7897，而本机 Clash 代理没开**（直连全被 GFW 重置/CF 拦；`clash-verge-service` 在跑但端口未监听）
  - JavBus/Javbooks/javhoo/javd/javinfo 在 backend 里是已禁用空壳（`pass`，调用抛 NotImplementedError）
  - **用户决策：不管 ABS，收尾交付**；开了代理后可用 `--sources avbase,javcup,javdb` 重试这 8 部
- **顺手修复**: `javcli/sources/dmm.py` 搜索兜底里的 `POPULARITY` 排序不被 GraphQL 枚举接受（实测全部请求失败），改为 3 组 query 变体全用合法的 `RELEASE_DATE`（introspection 查询被服务端禁用，合法值只能实测）
- **测试输出**: `C:\Temp\opencode\javcli_newtest\`（20 部）、`javcli_pretest\`（ABS 批量），未动 Z:\av 原文件
- **归位 + 入库功能（用户要求「没看到整理结果」→ 真正归位到 Z:\av）**:
  - `javcli/dbio.py` `save_to_db()` 新增 `tags`（追加进 genres，新片也带 LTX/破解）与 `organized` 参数（`{folder, video, fanart, poster, thumb}`）：提供时**跳过重复下载封面**（封面已由 CLI 下载到归位目录），upsert 后把 `fanart/poster/thumb/local_cover/video/organized_path` 路径列 **UPDATE 到归位目录**（与 Z:\av 既有 109 部一致），覆盖「已有资产保护」块的 keep 值
  - `javcli/cli.py`：`organize_file()` 返回 `(folder, written, organized)`；`_finish()` 贯通 `organized`/`tags` 到 `save_to_db`
  - **试点 SSIS-549**（`--organize --save-db` 传文件路径）: 文件移动改名到 `Z:\av\つばさ舞\SSIS-549+…+LTX\`，三图/NFO/JSON 齐全；movie_id=2468（首次误按番号跑建的行已用正确路径覆盖复用），`video_path/organized_path/fanart/poster/thumb/local_cover` 全部指向归位目录，genres 含 `LTX`/`破解` ✅
  - **坑**: `scrape.bat SSIS-549` 传番号走 code 分支（输出到 cwd），归位必须传**文件路径**（`scrape.bat "Z:\av\SSIS-549.mp4" --organize --save-db`）
  - **批量归位**: Z:\av 根目录 20 部散置视频（11/8–11/9 新增，含 ADN-179）`--organize --save-db` 后台执行
- **批量归位结果 ✅（2026-11-09）**: **20/20 成功**——全部 DMM 命中、移动改名到 `Z:\av\{女优}\{番号}+{标题}+{女优}+LTX\`、三图/NFO/JSON 齐全；**Z:\av 根目录散置视频清零**（女优目录 17 个）
  - 入库核验 20/20 ALL OK：`video_path/organized_path/fanart/poster/thumb` 全部 `Z:\av` 开头且磁盘存在、genres 含 `LTX`+`破解`；新片建行 2469–2482，已有行（1678–1682/2296）复用并覆盖路径；抽查 NFO `filenameandpath` 正确指向归位目录
  - **发现 bug（已有行 genres 丢标签）**: `backend/database.py` `merge_movie_data()` 对 genres 是「**新列表更长才覆盖**」（`old_list_len < len(new_value)`）——IPZZ-762（id=1680）旧行 10 个 genres > 新数据，LTX/破解 被合并逻辑丢掉。**修复 `javcli/dbio.py`**: upsert 后读回 genres，缺标签则 UPDATE 强制补齐（不改 backend 公共逻辑）；用 IPZZ-762 重跑 `--save-db` 端到端验证通过
  - 顺带清理 id=1680 genres 里混入的一条标题垃圾（`死ぬほど大嫌いな上司と…`，历史数据污染）
  - PRESTIGE 目录 16 广告原样保留 ✅（ABS 视频已增至 12 部，按用户决定不处理）

---

### 2026-11-10 — ABS（プレステージ无修正）专项：新增 javdirect 源 + 14 部归位入库 ✅

**背景**: 用户问「PRESTIGE-ABS-朱音ゆい 为何没整理」。此前结论是 DMM/r18dev/av-wiki 均不收录 ABS，且 avbase/javcup/javdb 走代理仍被 Cloudflare 403（代理出口 IP 被拉黑，连 in-app 浏览器都显示 "Sorry, you have been blocked"）。本次代理换节点后找到可行源。

- **新增数据源 `javdirect`（`javcli/sources/javdirect.py`）**: jav.direct 无修正/モザイク破壊专站
  - 站内搜索 `?s=` 返回 403 → **按番号猜 URL**：`/uncensored/dr-abs-xxx/`、`/uncensored/abs-xxx/`、`/censored/dr-abs-xxx/`、`/censored/abs-xxx/`、`/未分類/abs-xxx/`
  - 解析：`<h1>` 标题（去 `[モザイク破壊]`、去番号）+ `meta description` + maker/label/genre 链接 + `品番:/出演者:/シリーズ:/メーカー:/レーベル:/ジャンル:` 结构化字段
  - **女优四级兜底**：performer 链接 → description `『…』` → `出演者:` 字段 → 标题尾部/开头括号人名（**用 `/performer/<名字>/` 页 200 + 名字回核验证**，普通词 404，避免把标题词误当人名）
  - 封面：页面首个含本番号的 `javstore/supjav` `pl.jpg`（去 `?w=` 参数）；个别图床 521 时无图
  - 注册到 `sources/__init__.py` 的可选项（默认关闭，首选路由 proxy），`--list-sources` 可见
- **实测**: 14 部 ABS 中 **13 部命中**（标题/女优/片商/类型/封面全解），仅 `ABS-058` jav.direct 未收录（ABSOLUTE 标签页 1–4 页均无）——从 Yahoo!Japan 搜索核实标题为「ゆいの一日花嫁修業」朱音ゆい（MissAV/123AV 佐证）
- **`output.py` `clean_title()` 增强**: 去标题**开头**重复女优（`【朱音ゆい】xxx`、`朱音ゆい、xxx`），解决 ABS-095/123 文件夹名里女优出现两次的问题；受影响的 095/123 已重跑归位并删除旧目录
- **归位 + 入库结果**: **14/14 全部完成** → `Z:\av\朱音ゆい\{番号}+{标题}+朱音ゆい+LTX\`（原 `PRESTIGE-ABS-朱音ゆい` 里的视频清零）
  - movie_id 2483–2496；核验 14/14：`video/organized/fanart/poster/thumb` 均在 `Z:\av` 且存在，genres 含 `LTX`+`破解`
  - `ABS-049`/`ABS-095` 的 `.zh.srt` 字幕跟随归位（改名为 `{base}.zh.srt`，Kodi/Jellyfin 同名字幕规范）
  - `ABS-058` 例外处理：jav.direct 无收录 → 手工元数据（标题/女优/片商/系列/类型）+ **ffmpeg 截帧**生成 fanart/poster/thumb（居中裁 2:3），NFO/JSON/DB 正常写入
- **同期问题**: NAS（`\\192.168.1.179`）改密码导致 6 个网络盘断开 → 更新 Windows 凭据（`admin`）后全部恢复；Clash 节点多次失效（SSL EOF/连接重置），重启 Verge + 用户手动换节点后恢复

---

## 📋 待办事项（下次继续）

### 🟢 已完成（本次完成）

| 任务 | 说明 |
|------|------|
| ✅ 翻译模块完整工作流 | Faster-Whisper VAD + Ollama 两步流程 |
| ✅ 生成日语 SRT | `xxx_ja.srt` |
| ✅ 生成双语 SRT | `xxx.srt` (日语+中文) |
| ✅ 测试完整翻译流程 | 2小时视频验证成功 |

### 🔴 继续优化（可选）

| 优先级 | 任务 | 说明 |
|--------|------|------|
| P1 | 断点续传 | 音频持久化 + 中断后从已有音频继续 |
| P1 | SSE进度反馈 | 翻译进度实时推送到前端 |
| P2 | 批量翻译 | 多个视频排队处理 |

### 🟡 中期（Phase 1 范畴）

| 优先级 | 任务 | 说明 |
|--------|------|------|
| P1 | Phase 1 安全稳定 | googletrans 异常隔离、全局异常处理 |
| P1 | 主程序重构 | main.py 路由拆分（routes/） |

### ⚠️ 技术债务（待清理）

| 任务 | 说明 | 状态 |
|------|------|------|
| **tests/ 文件夹整理** | 删除不必要的临时脚本，保留可复用脚本并添加注释 | 📋 待处理 |

**整理原则**：
- 保留：`test_*.py`（功能测试）、`check_*.py`（检查工具）、`fix_*.py`（修复工具）
- 删除：临时调试脚本、无注释的一次性脚本
- 保留的脚本必须添加顶部 docstring 说明用途

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
