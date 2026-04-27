# MyMovieDB 优化重构计划
> **版本**: v2.1  
> **制定日期**: 2026-04-12  
> **制定者**: WorkBuddy AI (接力自 v2.0)  
> **项目路径**: `F:\github\MyMovieDB`  

---

## 📋 目录

1. [当前状态总结](#1-当前状态总结)
2. [Bug 修复记录](#2-bug-修复记录)
3. [Movie_Data_Capture 对比分析](#3-moviedatacapture-对比分析)
4. [代码问题清单](#4-代码问题清单)
5. [优化方案](#5-优化方案)
6. [排工期](#6-排工期)

---

## 1. 当前状态总结

### 项目已完成功能

| 功能 | 状态 | 备注 |
|------|------|------|
| 影片刮削（多源） | ✅ 完成 | DMM/Avbase/Av-Wiki/Javcup |
| Jellyfin 扫描导入 | ✅ 完成 | SSE 实时进度 |
| 本地视频管理 | ✅ 完成 | 批量扫描+刮削 |
| 女演员分类 | ✅ 完成 | gfriends 头像引擎 |
| 番号系列分类 | ✅ 完成 | |
| **整理功能（Phase 0.5）** | ✅ 完成 | organizer.py 已实现 |
| 字幕类型识别 | ✅ 完成 | -C/-U/-UC 后缀 |
| NFO 文件生成 | ✅ 完成 | 含 subtitle_type 标签 |

### 技术债务

| 问题 | 严重度 | 备注 |
|------|--------|------|
| main.py ~3500 行 | 🔴 高 | Phase 2 拆分目标 |
| 前端单文件 ~3600 行 | 🔴 高 | Phase 3 Vite 迁移目标 |
| organizer.py 有两个同名函数 | 🟡 中 | 后者覆盖前者，需合并 |
| 前端 Vue return 导出缺失 | 🔴 高 | 曾导致页面卡死（已修）|
| 无单元测试 | 🟡 中 | Phase 4 目标 |
| googletrans 已弃用 | 🟡 中 | Phase 1 替换目标 |

---

## 2. Bug 修复记录

### 2026-04-12 — 前端页面卡死 / 按钮失效

**根因**: WorkBuddy 在开发整理 Tab 时，在 Vue `return {}` 导出块中**遗漏了多个关键变量**，导致模板引用时产生 `undefined` 错误，阻塞 Vue 挂载。

**修复内容**（`frontend/index.html`）:

```diff
  organizePreview, organizeExecute, stopOrganize,
+ organizePanel, organizeLogEl, addOrganizeLog, organizeAbortController,
  // Movies
```

**缺失导出清单**:

| 变量 | 类型 | 用途 | 影响 |
|------|------|------|------|
| `organizePanel` | `ref()` | 整理进度状态（currentFile/logs/status/new/exists）| 🔴 致命：模板全用它 |
| `organizeLogEl` | `ref()` | 日志滚动容器 DOM | 🟡 中：日志无法自动滚动 |
| `addOrganizeLog` | `function` | 添加日志行 | 🟡 中：所有 organize 日志报错 |
| `organizeAbortController` | `variable` | AbortController 停止整理 | 🟡 中：停止按钮失效 |

**教训**: 前端 Vue return 导出是 WorkBuddy AI 最容易遗漏的地方。AI 接力开发时，必须用脚本验证所有模板引用变量都在 return 中导出。

---

## 3. Movie_Data_Capture 对比分析

### 3.1 架构对比

| 维度 | Movie_Data_Capture | MyMovieDB |
|------|-------------------|-----------|
| 入口 | CLI（命令行） | Web UI（浏览器） |
| 核心模块 | 5 个独立 .py | 全部在 main.py |
| 文件整理 | `core.py` 独立模块 | `organizer.py` 独立模块 ✅ |
| 爬虫策略 | 多源加权评分 | 多源串行/备用 |
| 数据库 | SQLite | SQLite ✅ |
| 前端 | CLI 彩色输出 | Vue 3 单文件 SPA |
| 进度反馈 | tqdm + 日志 | SSE WebSocket |
| 刮削策略 | 线程池并发 | 单线程串行 |

### 3.2 Movie_Data_Capture 的优势

1. **多源加权评分**：`core.py` 中 `multi_source_scrape()` 对多个数据源的结果进行质量评分，取最优结果
2. **线程池并发**：支持配置并发数量（`--threads`），刮削效率高
3. **更完善的字幕处理**：从文件元数据（metadata）读取字幕语言，不只依赖文件名后缀
4. **NFO 格式更规范**：直接生成 Jellyfin/Emby 兼容 NFO，包含 `<premiered>`、`<set>`（系列）、`<tag>` 等字段
5. **CLI 参数丰富**：支持 `--help`、配置文件、热重载等
6. **代码无循环依赖**：core.py、downloader.py、Uploader.py 完全独立

### 3.3 MyMovieDB 优于 Movie_Data_Capture 的地方

1. **Web UI**：浏览器访问，随时随地可用，移动端适配
2. **女演员头像**：gfriends 引擎，真实头像，提升可识别性
3. **SSE 实时进度**：WebSocket 式的无刷新进度推送
4. **影片库搜索**：前端直接搜索，无需 CLI
5. **多源刮削兜底**：任一源失败自动切换，不卡死

### 3.4 可借鉴的改进点（从 Movie_Data_Capture 迁移）

| 改进点 | 说明 | 优先级 |
|--------|------|--------|
| **字幕元数据识别** | 用 ffprobe/mediainfo 读取视频内嵌字幕轨道语言 | 🟡 中 |
| **多源加权评分** | 同一番号多源结果按数据完整度评分选优 | 🟡 中 |
| **刮削并发控制** | `asyncio.Semaphore` 控制并发数，速率限制 | 🟡 中 |
| **NFO 系列标签** | 添加 `<set>` 系列标签（gfans 的 series 信息） | 🟡 中 |
| **配置文件热重载** | `config.ini` 变更无需重启后端 | 🟢 低 |
| **CLI 接口** | 可选提供 CLI 命令行入口（`python -m mymoviedb`） | 🟢 低 |

---

## 4. 代码问题清单

### 4.1 organizer.py — 两个同名函数

**位置**: `backend/organizer.py`  
**问题**: 文件末尾有两个 `organize_files_sync` 函数定义（第二个覆盖第一个），且两者逻辑几乎相同，仅在批量查库的时机上略有差异。

```python
# 函数1（第 ~460 行）：批量查库在扫描完成后
# 函数2（第 ~530 行）：批量查库在 streaming 扫描阶段

# 实际生效的是函数2（Python 后定义覆盖前定义）
```

**修复**: 合并为一个，逻辑以函数2为准（streaming scan + 批量查库），删除函数1。

**影响**: 当前功能仍可用，但代码维护困难，易引发歧义。

### 4.2 organizer.py — `_emit_preview_item` 使用了空 `movies_map`

**位置**: `backend/organizer.py` → `organize_files_sync()` 函数内  
**问题**: streaming scan 阶段每个文件立即 emit `found` 事件时，`movies_map` 此时为空 `{}`，导致 `_emit_preview_item` 中的演员名、目标路径等详细信息无法填充，前端预览只能看到文件路径和番号。

```python
for item in scan_video_files_gen(source_paths):
    # movies_map 此时为 {}，_emit_preview_item 无法获取演员名
    _emit_preview_item(item, {}, target_root, progress_callback)  # ❌ 演员名=未知演员
```

**修复**: streaming scan 阶段只 emit 基础信息（路径+番号），详细信息在批量查库完成后补充 emit，或改为扫描完毕后再统一 emit。

### 4.3 前端 — `organizePanel.currentFile` 在模板中访问方式

**位置**: `frontend/index.html` 整理 Tab  
**问题**: `organizePanel` 是 `ref()` 对象，`organizePanel.currentFile` 在模板中需要正确访问。

```html
<!-- 模板中直接用 organizePanel.currentFile（Vue 3 会自动 unwrap）✅ -->
<div v-if="organizeRunning && organizePanel.currentFile">

<!-- 但在 JavaScript 中必须用 organizePanel.value.currentFile ❌ -->
```

**状态**: 模板中使用方式正确（Vue 3 自动 unwrap），但需要注意 JavaScript 中访问 ref 对象时要加 `.value`。

### 4.4 main.py — 挂载 `organize_files_sync` 为同步函数，无法发挥 asyncio 优势

**位置**: `backend/main.py` → `/organize/execute` 路由  
**问题**: `organize_files_sync` 本身是同步函数，`asyncio.get_event_loop().run_in_executor()` 虽能在线程池中运行，但无法利用 `robocopy` 的真正异步进度（因为它仍然调用的是 `shutil.copy2/move`）。

**修复**: 改用 `robocopy` subprocess 的真正异步 `create_subprocess_exec`（`organize.py` 中已有 `_async_copy_file` / `_async_move_file`，但未被调用）。

### 4.5 前端 — index.html 过长（~3600 行）

**问题**: 单文件 Vue SPA 超过 3000 行后：
- AI 修改时代码定位困难，容易漏改/改错
- 两个 AI 接力开发时冲突频繁
- 无法按模块独立测试

**修复**: Phase 3 Vite 迁移时拆分组件（详见 PROJECT_PLAN.md Phase 3）。

---

## 5. 优化方案

### 5.1 立即可做（1-2h）

| 任务 | 负责人 | 变更文件 |
|------|--------|---------|
| 合并 organizer.py 两个同名函数 | WorkBuddy | `backend/organizer.py` |
| 修复 _emit_preview_item 使用空 movies_map | WorkBuddy | `backend/organizer.py` |
| 清理前端废弃变量（organizeMode 等） | WorkBuddy | `frontend/index.html` |
| organizer.py 添加函数级 docstring | WorkBuddy | `backend/organizer.py` |

### 5.2 短期优化（1 周内）

| 任务 | 负责人 | 优先级 |
|------|--------|--------|
| Phase 1: googletrans → deep-translator 替换 | WorkBuddy | 🔴 P0 |
| Phase 1: FastAPI 全局异常处理器 | WorkBuddy | 🟡 P1 |
| Phase 2: main.py 路由拆分（routes/） | WorkBuddy | 🟡 P1 |
| Phase 2: organizer.py 正式接入 robocopy 异步 | WorkBuddy | 🟡 P1 |
| 添加字幕元数据识别（ffprobe）| WorkBuddy | 🟢 P2 |

### 5.3 中期目标（1 个月内）

| 任务 | 负责人 | 优先级 |
|------|--------|--------|
| Phase 3: 前端组件拆分（Vite） | WorkBuddy | 🔴 P0 |
| Phase 3: TypeScript 迁移 | WorkBuddy | 🔴 P0 |
| Phase 1: gfriends 网络超时兜底 | WorkBuddy | 🟡 P1 |
| Phase 2: Alembic 数据库迁移 | WorkBuddy | 🟡 P1 |

---

## 6. 排工期

### 立即任务（本周）

| 任务 | 预计工时 | 预计 Token | 状态 |
|------|---------|-----------|------|
| 合并 organizer.py 两个函数 + 修复 movies_map | 1h | 2M | 📋 待开始 |
| 清理前端废弃变量 | 0.5h | 0.5M | 📋 待开始 |
| googletrans → deep-translator | 1h | 2M | 📋 Phase 1 |
| 全局异常处理器 | 1h | 2M | 📋 Phase 1 |

### Phase 1（安全稳定）

| 任务 | 预计工时 | 预计 Token |
|------|---------|-----------|
| Pydantic v2 模型迁移 | 2h | 4M |
| googletrans → deep-translator | 1h | 2M |
| gfriends 网络超时 | 1h | 2M |
| FastAPI 全局异常处理 | 1h | 2M |
| **Phase 1 小计** | **5h** | **~10M** |

### Phase 2（架构优化）

| 任务 | 预计工时 | 预计 Token |
|------|---------|-----------|
| main.py 路由拆分 | 4h | 10M |
| Alembic 迁移 | 2h | 5M |
| scraper 适配器模式 | 3h | 8M |
| 统一 Pydantic v2 模型 | 2h | 4M |
| .env 配置外部化 | 1h | 2M |
| organizer 接入 robocopy 异步 | 2h | 4M |
| **Phase 2 小计** | **14h** | **~33M** |

### Phase 3（前端现代化）

| 任务 | 预计工时 | 预计 Token |
|------|---------|-----------|
| Vite + Vue 3 迁移 | 8h | 20M |
| TypeScript 全量迁移 | 12h | 30M |
| 组件拆分 | 6h | 15M |
| Pinia 状态管理 | 4h | 10M |
| 字幕元数据 ffprobe | 3h | 6M |
| **Phase 3 小计** | **33h** | **~81M** |

### 总计

| 阶段 | 工时 | Token 预估 |
|------|------|-----------|
| 立即任务 | ~2.5h | ~4.5M |
| Phase 1 | ~5h | ~10M |
| Phase 2 | ~14h | ~33M |
| Phase 3 | ~33h | ~81M |
| **总计** | **~54.5h** | **~128.5M** |

---

## 📝 开发日志

### 2026-04-12 — 接力开发 & 紧急 Bug 修复

- **执行者**: WorkBuddy AI (接力自 2026-04-07)
- **变更文件**:
  - `frontend/index.html` — 补全 `organizePanel`/`organizeLogEl`/`addOrganizeLog`/`organizeAbortController` 四个缺失导出
  - `PROJECT_PLAN.md` — 补充 Phase 0.5 完成记录
- **Bug 根因**: WorkBuddy 在开发整理 Tab 时，在 Vue `return {}` 导出块中遗漏了 `organizePanel` 等四个关键变量，导致模板引用时产生 `undefined` 错误，Vue 挂载失败，页面卡死在加载状态
- **教训**: 前端 Vue `return {}` 导出是 WorkBuddy 最容易遗漏的地方，AI 接力时必须用脚本验证所有模板引用变量都在 `return` 中导出
- **新增内容**: 本文档（`OPTIMIZATION_PLAN.md`），包含 Movie_Data_Capture 对比分析 + 完整排工期

---

*本文档由 WorkBuddy AI 于 2026-04-12 接力制定，请保持与 PROJECT_PLAN.md 同步更新。*
