# 测试文件说明

本目录包含所有测试和调试脚本，用于开发和调试 MyMovieDB 项目。

## 📁 文件分类

### 🔍 数据库检查和诊断工具

| 文件 | 功能 | 用途 |
|------|------|------|
| `check_images.py` | 检查数据库中的封面路径字段 | 快速查看影片的 fanart/poster/thumb/cover_url 字段 |
| `check_missing_covers.py` | 检查标记为 complete 但缺少封面文件的影片 | 验证刮削完整性，找出封面丢失问题 |
| `check_status.py` | 检查刮削状态为 complete 的影片详情 | 验证刮削状态是否准确 |
| `test_db_cover.py` | 检查特定番号的封面路径和文件存在性 | 调试单个影片的封面问题 |

### 🔧 数据库修复工具

| 文件 | 功能 | 用途 |
|------|------|------|
| `fix_cover_paths.py` | 修复相对路径为绝对路径 | 批量修复数据库中的封面路径格式 |
| `fix_missing_covers.py` | 批量下载缺失的封面并生成 NFO | 修复刮削不完整的影片（配合 missing_covers.json） |
| `update_db_covers.py` | 更新数据库中的封面路径字段 | 根据实际文件更新数据库记录 |
| `update_image_paths.py` | 扫描封面目录并更新数据库路径 | 根据已有封面文件批量更新数据库 |

### 🧪 爬虫功能测试

| 文件 | 功能 | 用途 |
|------|------|------|
| `test_code_recognition.py` | 番号识别测试 | 测试文件名解析、前缀排除、特殊番号识别 |
| `test_fanza.py` | Fanza (DMM) 爬虫测试 | 测试 Fanza 数据源刮削效果 |
| `test_scrape_all.py` | 综合刮削测试 | 测试多番号刮削、验证完整度 |
| `test_scrapers_optimized.py` | 优化爬虫解析逻辑测试 | 调试爬虫解析细节 |
| `test_scrapers_real.py` | 各数据源真实可用性测试 | 测试 Avbase/AV-Wiki/Javcup/Avdanyuwiki |
| `test_sources.py` | 各数据源独立测试 | 分别测试每个爬虫的搜索/刮削能力 |

### 🎨 封面处理测试

| 文件 | 功能 | 用途 |
|------|------|------|
| `test_poster_crop.py` | 测试 poster 裁切逻辑 | 验证从 fanart 右半边裁切 poster 的效果 |

### 📊 刮削逻辑测试

| 文件 | 功能 | 用途 |
|------|------|------|
| `test_scrape_logic.py` | 测试刮削逻辑 | 验证重新刮削 partial 状态影片的流程 |

### 🐛 调试工具

| 文件 | 功能 | 用途 |
|------|------|------|
| `debug_avbase_actors.py` | 调试 Avbase 演员提取逻辑 | 调试演员信息提取问题 |
| `debug_scraper.py` | 调试单个爬虫功能 | 快速测试 AvdanyuwikiScraper |

### 📄 数据文件

| 文件 | 功能 | 用途 |
|------|------|------|
| `missing_covers.json` | 缺少封面的影片列表 | 配合 fix_missing_covers.py 使用 |

## 🚀 快速使用指南

### 调试番号识别问题
```bash
python test/test_code_recognition.py
```

### 测试爬虫可用性
```bash
# 测试所有数据源
python test/test_sources.py

# 测试 Fanza 爬虫
python test/test_fanza.py

# 综合刮削测试
python test/test_scrape_all.py
```

### 检查封面完整性
```bash
# 检查缺少封面的影片
python test/check_missing_covers.py

# 检查特定番号
python test/test_db_cover.py
```

### 修复封面问题
```bash
# 修复相对路径
python test/fix_cover_paths.py

# 批量下载缺失封面
python test/fix_missing_covers.py

# 更新数据库封面路径
python test/update_db_covers.py
```

### 测试封面裁切
```bash
python test/test_poster_crop.py
```

## 📝 开发建议

1. **新增测试文件**：请在本目录创建，并在本 README 中记录用途
2. **复用现有测试**：遇到类似问题时，先查找是否有对应的测试工具
3. **修改测试**：基于现有测试文件修改，保持命名规范（test_*.py / check_*.py / fix_*.py）
4. **调试数据源**：使用 debug_*.py 文件快速定位问题

## 🎯 测试文件命名规范

- `test_*.py` - 功能测试
- `check_*.py` - 检查诊断工具
- `fix_*.py` - 修复工具
- `debug_*.py` - 调试工具
- `update_*.py` - 数据更新工具

---

**最后更新**: 2026-03-29
**维护者**: MyMovieDB 开发团队
