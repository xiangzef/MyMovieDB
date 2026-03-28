# MyMovieDB - 本地影视库刮削器

一个轻量级的本地影视库管理工具，支持刮削、搜索和浏览影片信息。

## 功能特性

- 🎬 **影片刮削** - 从多个数据源自动获取影片信息
- 🔍 **智能搜索** - 支持编号、标题搜索
- 🖼️ **封面管理** - 自动下载和本地存储封面图
- 🌐 **Web 界面** - 响应式设计，支持移动端
- 📦 **一键打包** - 可编译成 exe，系统托盘运行

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python + FastAPI |
| 数据库 | SQLite |
| 前端 | Vue.js + Element Plus |
| 爬虫 | requests + BeautifulSoup4 |

## 项目结构

```
MyMovieDB/
├── backend/                 # 后端
│   ├── main.py              # FastAPI 主入口
│   ├── database.py          # SQLite 数据库
│   ├── scraper.py           # 爬虫模块
│   ├── models.py            # 数据模型
│   ├── tray_launcher.py     # 系统托盘启动器
│   ├── icon.ico             # 程序图标
│   ├── requirements.txt     # 依赖
│   └── build.bat            # 打包脚本
├── frontend/                # 前端
│   └── index.html           # 单页应用
├── data/                    # 数据目录
│   ├── movies.db            # SQLite 数据库
│   └── covers/              # 封面图存储
├── dist/                    # 打包输出目录
│   └── MyMovieDB.exe        # 打包后的程序
└── README.md
```

---

## 使用方式

### 方式一：直接运行 Python（开发模式）

```bash
# 1. 安装依赖
cd backend
pip install -r requirements.txt

# 2. 启动后端
python -m uvicorn main:app --reload

# 3. 打开前端
# 直接在浏览器打开 frontend/index.html
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

打包完成后，`dist/MyMovieDB.exe` 就是可执行文件。

---

## 系统托盘功能

打包后的程序支持系统托盘运行：

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

## 数据源

| 数据源 | 状态 | 说明 |
|--------|------|------|
| avdanyuwiki.com | ✅ 主力 | 数据完整，更新及时 |
| javdbxxx.com | ❌ 被墙 | 403 Forbidden |
| 其他 | 测试中 | 待添加更多源 |

---

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | API 状态 |
| `/movies` | GET | 影片列表（分页） |
| `/movies/{id}` | GET | 影片详情 |
| `/movies/code/{code}` | GET | 按编号查询 |
| `/search?q=` | GET | 搜索影片 |
| `/scrape` | POST | 刮削影片 |
| `/covers/{filename}` | GET | 获取封面图 |
| `/health` | GET | 健康检查 |

完整 API 文档：http://localhost:8000/docs

---

## 配置说明

数据库会自动初始化，无需手动配置。

封面图保存在 `data/covers/` 目录。

---

## 常见问题

**Q: 刮削失败怎么办？**
A: 检查网络连接，可能是数据源不可用。可以尝试稍后重试。

**Q: 翻译功能不工作？**
A: Google Translate 可能被墙，需要 VPN 或使用代理。

**Q: 如何查看日志？**
A: 运行 Python 时终端会显示详细日志。

---

## 许可证

MIT License
