# 测试文件说明

本目录包含所有测试和调试脚本，用于开发和调试 MyMovieDB 项目。

## 📁 文件分类（2026-04-29 整理）

### 🔍 数据库检查工具

| 文件 | 功能 | 用途 |
|------|------|------|
| `check_db.py` | **统一数据库检查工具** | 封面路径、刮削状态、影片完整性检查 |
| `check_missing_covers.py` | 检查缺少封面的 complete 影片 | 验证刮削完整性 |
| `check_data_quality.py` | 数据质量检查 | 检查数据完整性 |
| `check_video_paths.py` | 视频路径检查 | 验证视频文件路径 |
| `check_jellyfin_stats.py` | Jellyfin 统计检查 | 统计 Jellyfin 状态 |

### 🔧 数据库修复工具

| 文件 | 功能 | 用途 |
|------|------|------|
| `fix_covers.py` | **统一封面修复工具** | 路径修复、缩略图生成、状态重算 |
| `fix_missing_covers.py` | 批量下载缺失封面 | 配合修复工具使用 |
| `fix_one.py` | 修复单个影片 | 指定番号修复 |
| `fix_stats.py` | 修复统计信息 | 更新统计数据 |
| `fix_jellyfin_partial.py` | 修复 Jellyfin 不完整记录 | 批量修复 |

### 🧪 爬虫功能测试

| 文件 | 功能 | 用途 |
|------|------|------|
| `test_scrapers.py` | **统一爬虫测试工具** | 单源测试、全源对比、批量测试 |
| `test_code_recognition.py` | 番号识别测试 | 文件名解析、前缀排除、特殊番号 |
| `test_code_extraction.py` | 番号提取测试 | 测试 _extract_code 函数 |
| `test_fanza.py` | Fanza 爬虫测试 | 单独测试 Fanza 数据源 |
| `test_scrape_all.py` | 综合刮削测试 | 多番号刮削验证 |
| `test_scrape_logic.py` | 刮削逻辑测试 | 验证重新刮削 partial 状态影片 |

### 🎨 封面处理测试

| 文件 | 功能 | 用途 |
|------|------|------|
| `test_poster_crop.py` | Poster 裁切测试 | 验证从 fanart 右半边裁切效果 |
| `reorganize_covers.py` | 封面目录重组 | 调整封面存储结构（{番号}/ 文件夹） |

### 🧪 Jellyfin 功能测试

| 文件 | 功能 | 用途 |
|------|------|------|
| `test_jellyfin_import.py` | Jellyfin 导入测试 | 验证 NFO 解析、数据库导入 |
| `verify_jellyfin_dirs.py` | 验证 Jellyfin 目录 | 验证目录结构 |
| `add_jellyfin_dirs.py` | 添加 Jellyfin 源 | 批量添加 Jellyfin 源目录 |
| `update_jellyfin_count.py` | 更新 Jellyfin 计数 | 批量更新视频计数 |

### 🔧 清理和维护工具

| 文件 | 功能 | 用途 |
|------|------|------|
| `cleanup_jellyfin.py` | 清理 Jellyfin 数据 | 清理孤立记录 |
| `cleanup_orphans.py` | 清理孤立文件 | 清理无关联数据 |
| `consolidate_partial.py` | 合并 partial 影片 | 合并重复记录 |
| `find_movies_without_videos.py` | 查找无视频影片 | 查找孤立影片记录 |
| `find_poster.py` | 查找封面文件 | 查找缺失封面 |
| `organize_partial_jellyfin.py` | 整理 Jellyfin 部分数据 | 整理不完整数据 |
| `organize_videos.py` | 番号电影整理工具 | 规范化文件名、移动到番号文件夹、清理垃圾文件 |
| `scrape_partial_covers.py` | 刮削缺失封面 | 批量刮削封面 |
| `audit_database.py` | 数据库审计 | 全面审计数据库 |

### 🌐 翻译功能

| 文件 | 功能 | 用途 |
|------|------|------|
| `test_translate.py` | 翻译测试脚本 | 视频语音翻译测试 |

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

### 其他测试
```bash
# 番号识别测试
python tests/test_code_recognition.py

# Fanza 爬虫测试
python tests/test_fanza.py

# 封面裁切测试
python tests/test_poster_crop.py
```

## 📝 开发建议

1. **新增测试文件**：请在本目录创建，并在本 README 中记录用途
2. **复用现有测试**：遇到类似问题时，先查找是否有对应的测试工具
3. **修改测试**：基于现有测试文件修改，保持命名规范
4. **清理原则**：临时脚本用完即删，长期工具保留在 tests/

## 🎯 测试文件命名规范

- `test_*.py` - 功能测试
- `check_*.py` - 检查诊断工具
- `fix_*.py` - 修复工具
- `cleanup_*.py` - 清理工具
- `audit_*.py` - 审计工具
- `find_*.py` - 查找工具
- `organize_*.py` - 整理工具
- `consolidate_*.py` - 合并工具

## 📊 目录结构

```
tests/
├── README.md              # 本文件
├── test_*.py              # 功能测试
├── check_*.py             # 检查工具
├── fix_*.py               # 修复工具
├── cleanup_*.py           # 清理工具
├── find_*.py              # 查找工具
├── audit_*.py             # 审计工具
└── organize_*.py          # 整理工具
```

---

**最后更新**: 2026-04-29
**维护者**: MyMovieDB 开发团队