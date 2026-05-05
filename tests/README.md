# 测试文件说明

本目录包含测试和调试脚本，用于开发和维护 MyMovieDB 项目。

## 📁 保留文件清单（2026-05-05 整理）

### 🔍 数据库检查工具

| 文件 | 功能 | 用途 |
|------|------|------|
| `check_db.py` | 统一数据库检查工具 | 封面路径、刮削状态、番号查询、缺失封面检查 |
| `check_data_quality.py` | 数据质量检查 | 孤儿记录、重复番号、缺失资源检查 |
| `audit_database.py` | 数据库健康度审计 | movies/local_videos 表健康度统计 |

### 🔧 修复和维护工具

| 文件 | 功能 | 用途 |
|------|------|------|
| `fix_covers.py` | 封面修复工具 | 路径修复、更新封面路径、重算刮削状态 |
| `cleanup_orphans.py` | 孤儿记录清理 | 删除无视频且无刮削信息的孤立记录 |
| `scrape_partial_covers.py` | partial 封面补刮 | 对 jellyfin_status=partial 且无 poster 的影片联网刮削封面 |

### 🧪 功能测试

| 文件 | 功能 | 用途 |
|------|------|------|
| `test_code_extraction.py` | 番号提取测试 | 测试 `_extract_code` 函数，覆盖垃圾前缀、FC2、常规番号等场景 |
| `test_scrapers.py` | 爬虫测试工具 | 单数据源测试、全部数据源对比、批量多番号测试 |
| `test_scrape_logic.py` | 刮削逻辑测试 | 验证 stats 统计、partial 状态影片、刮削逻辑 |
| `test_jellyfin_import.py` | Jellyfin 导入测试 | 测试 NFO 解析、数据库导入流程 |
| `test_poster_crop.py` | 海报裁切测试 | 从 fanart 右边裁切 poster 并验证效果 |
| `test_translate.py` | 翻译功能测试 | Faster-Whisper VAD 语音识别 + Ollama 翻译流程 |

## 🚀 快速使用指南

### 数据库检查

```bash
# 检查封面路径字段
python tests/check_db.py images --limit 20

# 检查刮削状态
python tests/check_db.py status --limit 30

# 检查特定番号
python tests/check_db.py code --code SSIS-254

# 检查缺失封面
python tests/check_db.py missing
```

### 数据库修复

```bash
# 修复相对路径
python tests/fix_covers.py paths

# 更新封面路径
python tests/fix_covers.py update

# 重算刮削状态
python tests/fix_covers.py status

# 全部修复
python tests/fix_covers.py all
```

### 爬虫测试

```bash
# 测试单个数据源
python tests/test_scrapers.py single --source fanza --code SSIS-254

# 测试所有数据源
python tests/test_scrapers.py all --code IPZZ-792

# 批量测试多个番号
python tests/test_scrapers.py batch --codes "SSIS-254,IPZZ-792,JNT-114"
```

### 番号提取测试

```bash
python tests/test_code_extraction.py
```

### 翻译测试

```bash
python tests/test_translate.py "X:\jellyfin\明日花キララ\HODV-20574\HODV-20574.avi"
```

## 📝 开发建议

1. **新增测试文件**：请在本目录创建，并在本 README 中记录用途
2. **复用现有测试**：遇到类似问题时，先查找是否有对应的测试工具
3. **修改测试**：基于现有测试文件修改，保持命名规范
4. **清理原则**：临时脚本用完即删，长期工具保留在 tests/

## 📊 目录结构

```
tests/
├── README.md              # 本文件
├── test_*.py              # 功能测试
├── check_*.py             # 检查工具
├── fix_*.py               # 修复工具
├── cleanup_*.py           # 清理工具
├── audit_*.py             # 审计工具
└── scrape_partial_*.py    # 补刮工具
```

---

**最后更新**: 2026-05-05
