# 测试文件说明

本目录包含所有测试和调试脚本，用于开发和调试 MyMovieDB 项目。

## 📁 文件分类（2026-03-29 优化合并）

### 🔍 数据库检查工具

| 文件 | 功能 | 用途 |
|------|------|------|
| `check_db.py` | **统一数据库检查工具** | 封面路径、刮削状态、影片完整性检查 |
| `check_missing_covers.py` | 检查缺少封面的 complete 影片 | 验证刮削完整性 |

### 🔧 数据库修复工具

| 文件 | 功能 | 用途 |
|------|------|------|
| `fix_covers.py` | **统一封面修复工具** | 路径修复、缩略图生成、状态重算 |
| `fix_missing_covers.py` | 批量下载缺失封面 | 配合 missing_covers.json 使用 |

### 🧪 爬虫功能测试

| 文件 | 功能 | 用途 |
|------|------|------|
| `test_scrapers.py` | **统一爬虫测试工具** | 单源测试、全源对比、批量测试 |
| `test_code_recognition.py` | 番号识别测试 | 文件名解析、前缀排除、特殊番号 |
| `test_fanza.py` | Fanza 爬虫测试 | 单独测试 Fanza 数据源 |
| `test_scrape_all.py` | 综合刮削测试 | 多番号刮削验证 |
| `test_scrape_logic.py` | 刮削逻辑测试 | 验证重新刮削 partial 状态影片 |

### 🎨 封面处理测试

| 文件 | 功能 | 用途 |
|------|------|------|
| `test_poster_crop.py` | Poster 裁切测试 | 验证从 fanart 右半边裁切效果 |

### 📄 数据文件

| 文件 | 功能 | 用途 |
|------|------|------|
| `missing_covers.json` | 缺少封面的影片列表 | 配合 fix_missing_covers.py 使用 |

## 🚀 快速使用指南

### 数据库检查
```bash
# 检查封面路径字段
python test/check_db.py images --limit 20

# 检查刮削状态
python test/check_db.py status --limit 30

# 检查特定番号
python test/check_db.py code --code SSIS-254

# 检查缺失封面
python test/check_db.py missing
```

### 数据库修复
```bash
# 修复相对路径
python test/fix_covers.py paths

# 更新封面路径
python test/fix_covers.py update

# 重算刮削状态
python test/fix_covers.py status

# 全部修复
python test/fix_covers.py all
```

### 爬虫测试
```bash
# 测试单个数据源
python test/test_scrapers.py single --source fanza --code SSIS-254

# 测试所有数据源
python test/test_scrapers.py all --code IPZZ-792

# 批量测试多个番号
python test/test_scrapers.py batch --codes "SSIS-254,IPZZ-792,JNT-114"
```

### 其他测试
```bash
# 番号识别测试
python test/test_code_recognition.py

# Fanza 爬虫测试
python test/test_fanza.py

# 封面裁切测试
python test/test_poster_crop.py
```

## 📝 开发建议

1. **新增测试文件**：请在本目录创建，并在本 README 中记录用途
2. **复用现有测试**：遇到类似问题时，先查找是否有对应的测试工具
3. **修改测试**：基于现有测试文件修改，保持命名规范
4. **合并原则**：功能相似的测试文件合并为一个（如 check_db.py, fix_covers.py）

## 🎯 测试文件命名规范

- `test_*.py` - 功能测试
- `check_*.py` - 检查诊断工具
- `fix_*.py` - 修复工具

## 📊 优化记录

**2026-03-29 合并优化**：
- ✅ 合并 `check_images.py` + `check_status.py` + `test_db_cover.py` → `check_db.py`
- ✅ 合并 `fix_cover_paths.py` + `update_db_covers.py` + `update_image_paths.py` → `fix_covers.py`
- ✅ 合并 `test_scrapers_optimized.py` + `test_scrapers_real.py` + `test_sources.py` → `test_scrapers.py`
- ✅ 删除冗余调试工具（`debug_avbase_actors.py`, `debug_scraper.py`）

**优化效果**：
- 测试文件数量：18个 → 8个
- 代码复用率提升
- 命令行参数更灵活

---

**最后更新**: 2026-03-29
**维护者**: MyMovieDB 开发团队
