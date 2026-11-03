<p align="center">
  <img src="assets/readme/hero.svg" alt="MyMovieDB 本地影视库刮削器" width="100%">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-3776AB?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.109+-009688?logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Vue-3-4FC08D?logo=vue.js" alt="Vue 3">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

> 轻量级本地影视库管理工具——自动刮削元数据、按女演员/番号分类、Jellyfin 一键导入，可打包成 exe 托盘运行。

## 功能特性

| 功能 | 说明 |
|------|------|
| 影片刮削 | 多数据源自动获取番号、标题、封面、演员、标签（SSE 实时进度） |
| Jellyfin 导入 | 一键扫描 Jellyfin 格式影视库，自动关联本地视频 |
| 女演员分类 | gfriends 头像引擎（10,000+ 真实头像），佚名演员独立列表 |
| 番号系列分类 | 按番号前缀浏览（SSIS / SSNI / ABP …） |
| 本地视频管理 | 扫描目录批量识别 mp4/mkv/avi 等 14 种格式，多线程刮削 |
| 一键打包 | PyInstaller 编译 exe，系统托盘静默运行 |

## 快速开始

```bash
# 开发模式
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload
# 浏览器打开 frontend/index.html（后端 http://localhost:8000）

# 打包成 exe
cd backend && pip install pystray Pillow pyinstaller
build.bat    # 产物：dist/MyMovieDB.exe，双击托盘运行
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python + FastAPI |
| 数据库 | SQLite（data/movies.db） |
| 前端 | Vue.js 3（CDN 单文件） |
| 爬虫 | requests + BeautifulSoup4 |
| 头像引擎 | [gfriends](https://github.com/gfriends/gfriends) |

## 数据源

| 数据源 | 状态 | 说明 |
|--------|------|------|
| Fanza (DMM) | 主力 | 官方站点，数据最全 |
| Avbase / AV-Wiki / Javcup | 备用 | 100% 成功率 |

## 目录结构

```
backend/    FastAPI 主入口 · 刮削 · gfriends · Jellyfin 扫描 · 托盘启动器
frontend/   Vue 3 单页应用
data/       movies.db · covers/ · avatars/ · nfo/ · backup/
```

## 常见问题

- **刮削失败** → 检查网络，数据源偶发不可用，稍后重试
- **翻译不工作** → Google Translate 需要代理
- **女演员显示「佚名」** → 不在 gfriends 仓库中（素人/马甲），无法关联系列作品

完整 API 文档：启动后访问 `http://localhost:8000/docs`

## License

MIT