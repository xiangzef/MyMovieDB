# NAS 媒体库与代理配置记录

> 记录时间：2026-11-11
> 服务器：Synology DS918+（DSM 6.2.1，192.168.1.179）

## 一、代理（mihomo / Clash Meta）

- **容器名**：`mihomo2`（Docker，镜像 `docker.1ms.run/metacubex/mihomo:latest`）
- **网络**：`host` + `privileged`，开启 **TUN**（gvisor 栈，auto-route）
- **重启策略**：`always`（NAS 重启后自动拉起）
- **配置文件**：NAS 上 `/volume1/docker/mihomo/config.yaml`
  （Windows 访问：`\\192.168.1.179\docker\mihomo\config.yaml`）
- **端口**：mixed-port `7890`（局域网可用），控制端口 `127.0.0.1:9090`
- **订阅**：nicejump（Clash YAML），已内联为静态节点
- **规则**：内网段（192.168/10/172.16/127）直连，其余按订阅规则走代理
- **注意**：
  - 订阅里原始的 `GEOIP` 规则会导致 mihomo 启动失败（缺地理库），已移除
  - 订阅到期/更换后，需要重新抓订阅并生成配置（内联节点不会自动更新）
  - 旧容器 `mihomo` 已停止（DSM API 删除接口报错，可在 Docker 界面手动删除）

## 二、媒体库结构

```
存储空间3（/volume4，共享名仍为中文）
├── 电影\<片名 (年份)>\...              ← Jellyfin/Emby「电影」库
├── 电视剧\<剧名>\Season N\<剧名 SxxEyy.ext>  ← 「电视剧」库
└── 云盘缓存\

home5（/volume5，Windows Z:）
└── 夸克网盘\...                        ← Jellyfin「夸克网盘」库（家庭视频，不刮削）
```

- Jellyfin（8096）/ Emby（8097，用户 `bin`）均为两个库：电影 + 电视剧
- 元数据语言：`zh-CN`，抓取源：TMDB / TheTVDB
- 剧集命名必须是 `SxxEyy`，否则识别不到集数
- 新增资源放进对应目录即可（实时监控开启，会自动扫描）

### 目录命名约定（2026-11 实际采用）

```
电影\{中文名} {英文名}\{原始发布名}.mp4 + movie.nfo
电视剧\{中文名} {英文名}\Season 1\{剧名} S01E01.ext + tvshow.nfo / season.nfo / 每集 .nfo
```

- 目录名不带年份（与既有 20 部片子保持一致）
- 剧集文件名前缀必须是「剧名 + SxxEyy」，如 `猎捕 The Hunt S01E01.mkv`
- 海报/剧照：`poster.jpg` `fanart.jpg` `thumb.jpg`，季海报 `Season N\season-poster.jpg`，
  剧照 `<剧名> S01Eyy-thumb.jpg`
- NFO 里带 `<imdbid>` / `<tmdbid>` / `<uniqueid>`，Jellyfin 扫描时可直接匹配条目，不依赖在线搜索
- 已知副作用：媒体服务器保存元数据时会「收编」本地图片（删掉 poster.jpg/thumb.jpg 改成
  引用自己缓存 `/config/metadata/library/...`），属正常行为

## 三、外网访问（VPS 转发）

- VPS：`47.101.178.144`（阿里云，nginx + frps:7000）
- 家里 NAS 未做端口映射，公网 IP 不可直连，全部走 VPS

| 服务 | 外网地址 |
|---|---|
| Jellyfin | http://47.101.178.144/jellyfin/ |
| Emby | http://47.101.178.144/emby/ |
| MyMovieDB | http://47.101.178.144/MyMovieDB/ |
| peach | http://47.101.178.144/peach/ |
| Transmission | http://47.101.178.144/transmission/ |
| Gitea | http://47.101.178.144/gitea/ |
| NAS SSH | `47.101.178.144:2022` |

- frps 配置：VPS `/etc/frps.ini`（token 在其内）
- 现有 frpc 在 NAS 上（由 DSM 管理）；Emby 用新增容器 `frpc-emby` 映射 8097
- Emby 的 frpc 配置：`\\192.168.1.179\docker\frpc\frpc.toml`
- VPS nginx 配置：`/etc/nginx/sites-enabled/default`（已含 `/emby/` location）

## 四、已知限制

- 中英混合剧名（如「布鲁克林99 Brooklyn Nine-Nine」）自动搜索会失败，需要手动匹配或改成英文名
- 无法识别的文件（如 `P.2026.2160p...`）不要强行匹配，否则元数据会错配
- `存储空间3` 改名为 `home3` 的计划未执行（改共享名会影响容器挂载和媒体库路径）

## 五、⚠️ 元数据源连通性诊断（2026-11-12，重要）

### 结论：只有 DNS 污染，没有 IP/SNI 封锁

| 域名 | 现象 | 真实 IP（可用） |
|------|------|----------------|
| `api.themoviedb.org` | 解析被污染成 Twitter/Facebook/Dropbox 的 IP | `65.9.130.24` `.53` `.126` `.129`、`54.192.138.2` `.23` `.65` `.121` |
| `api4.thetvdb.com` | 同样被污染，**且真实 IP 从家宽不可达**（超时） | `18.64.211.x`（VPS 可达，家宽不行） |
| `www.themoviedb.org` | 可达（网页版，Cloudflare 有反爬） | — |

**证据链**（家宽本机 + Jellyfin 容器内双向验证）：

```powershell
# 家宽直连真实 IP → TMDB 正常返回 JSON（401=缺 key，说明 API 通）
curl.exe --resolve "api.themoviedb.org:443:65.9.130.24" https://api.themoviedb.org/3/configuration
#   → {"status_code":7,"status_message":"Invalid API key...","success":false}
```

容器内探测（`POST /Items/{id}/RemoteImages/Download?imageUrl=...`，Jellyfin 服务端去取 URL）：

| 探测 URL | 结果 | 含义 |
|----------|------|------|
| `http://47-101-178-144.sslip.io/probe.txt` | HTTP 503（= 我 VPS 的 nginx） | 容器 DNS + 出网正常 |
| `http://65-9-130-24.sslip.io/probe.txt` | HTTP 403（= TMDB 真实 IP） | **容器能直连真实 TMDB** |
| `http://api.themoviedb.org/probe.txt` | Connection refused（秒失败） | 污染 IP 连不上 |

### NAS/网络侧事实

- NAS 自己**不跑 DNS**（192.168.1.179:53 无响应），DSM 的 DNS 设置是 `192.168.1.1`
- 192.168.1.1 = 中国电信智能网关（OpenWrt / LuCI，http://192.168.1.1/cgi-bin/luci）→ **容器用的就是它**
- 家宽向 114.114.114.114 / 223.5.5.5 / 路由器 问 `api.themoviedb.org` **全被污染**；
  但同一域名在 VPS 上问 114DNS 却拿到真实 IP（VPS 出口不经过污染链路）
- ⇒ **换 DNS 服务器没用**，必须走「固定 hosts」或「代理」

### 三种修法

| 方案 | 做法 | 前提 | 效果 |
|------|------|------|------|
| **A. 路由器 hosts（推荐）** | LuCI → 服务 → dnsmasq → 自定义主机记录：`65.9.130.24 api.themoviedb.org` | 路由器管理员密码 | 全网生效，Jellyfin 自己刮，不需 mihomo |
| **B. 容器 hosts** | compose 加 `extra_hosts: ["api.themoviedb.org:65.9.130.24"]` 后重建容器 | 需要重建容器 | 只影响该容器 |
| **C. mihomo** | Container Manager 启动 `mihomo2` | 订阅有效（至 2026-12-08） | 全局代理，顺带修所有污染域名 |

> TVDB 从家宽不可达，所以剧集刮削走 TMDB 即可（Jellyfin 的 TV 抓削顺序 TheTVDB → TheMovieDb，
> TVDB 失败会自动跳过，只是慢 100 秒）。

### Jellyfin 自身配置能不能改？

**不能。** 已核对 Jellyfin 12.4.0 的 `ServerConfiguration` 全部 47 个字段，以及 TMDb / OMDb
插件的全部配置项：**没有 TMDB BaseUrl、没有 HTTP 代理开关**（Jellyfin 的 HttpClient 走
默认系统代理，只能靠容器环境变量 `HTTPS_PROXY`，而容器环境变量要靠 Docker API 改，而
DSM 的 Docker API 对本账号返回 114）。

### 应急方案（本次 4 部纪录片用的就是这个）

1. 在能连 TMDB 的机器上抓元数据 → 写 NFO + 本地图片 → 媒体服务器扫库即可显示
2. 临时禁用 TMDB/TVDB 抓削器，避免扫描卡死：`scripts/jellyfin_toggle_fetchers.py`（加 `--restore` 还原）

### 本次新增脚本（scripts/）

| 脚本 | 作用 |
|------|------|
| `jellyfin_helper.py` | **主工具**：本地跑，scan → fetch → plan → apply → push 一条龙，把新增资源整理成 Jellyfin/Emby 结构（详见 `JELLYFIN_HELPER.md`） |
| `_tmdb_fetch.py` | TMDB 抓取模块（jellyfin_helper 的依赖，也可单独跑；需在能访问 tmdb.org 的机器上执行） |
| `_selftest_helper.py` | 自测：发布名解析用例 + 沙盒全流程（不碰真实库） |
| `jellyfin_media_organize.py` | 早期版本：把下载目录重命名成 Jellyfin 标准结构 + 写 NFO + 下载图片（默认 dry-run，`--apply` 执行） |
| `jellyfin_apply_metadata.py` | 把元数据 + 图片通过 API 直接写进 Jellyfin（`--emby` 写 Emby） |
| `jellyfin_toggle_fetchers.py` | 临时禁用/恢复 TMDB+TVDB 抓削器 |
| `probe_metadata_reach.py` | 探测媒体服务器到 TMDB 的真实连通性（旧版，等价于 `jellyfin_helper.py probe`） |

### 服务器凭据备忘

- NAS DSM：账号 `admin`（密码放密码管理器，**不要写进仓库**）；HTTP API 5000 端口可用；Docker API `SYNO.Docker.Container`
  返回 114，TaskScheduler/Service 返回 103，暂时无法用 API 操作容器；
  `SYNO.Core.Network` 的 method=get/set 可用，但 **set 对 DNS 字段无效**（改了不生效））
- Jellyfin：用户 `Admin`，API token 从环境变量 `JELLYFIN_TOKEN` 取（见 `scripts/_media_servers.py`）
- Emby：用户 `bin`，API token 从环境变量 `EMBY_TOKEN` 取（见 `scripts/_media_servers.py`）
- VPS：`root@47.101.178.144`（本机 id_rsa 可直连；`www.themoviedb.org` 可访问，
  `api.themoviedb.org` 同样被污染 → 只能爬网页 / 用 schema.org 的 ld+json）
- 路由器 192.168.1.1：OpenWrt/LuCI，密码未知
- Gitea：`http://192.168.1.179:3000`（公网 `http://47.101.178.144/gitea/`），
  用户 `admin`，**手上有的是 token（scope=write:repository，不能建仓），
  管理员密码未知** → 建仓需管理员密码或带 `write:user` 的 token

## 六、拆出的独立仓库（2026-11-12）

两个削刮/整理工具已从本仓库拆成独立仓库，各自 `git init` + 独立提交，并已推送到 Gitea：

| 目录 | Gitea 仓库 | 内容 |
|------|------------|------|
| `F:\github\javcli` | `admin/javcli` | AV 本地 cmd 削削器（`javcli/` 包 + `scrape.bat`），backend 依赖改为可配置（`MYMOVIEDB_HOME`） |
| `F:\github\jellyfin-helper` | `admin/jellyfin-helper` | Jellyfin/Emby 整理助手（`jellyfin_helper.py` + `_tmdb_fetch.py` + 自测） |

- 克隆：`http://192.168.1.179:3000/admin/<repo>.git`（公网 `http://47.101.178.144/gitea/admin/<repo>.git`）
- SSH：`ssh://git@192.168.1.179:2222/admin/<repo>.git`
- 两边都是**公开**仓库 → **凭据一律不进源码**：token/密码走 `~/.jellyfin_helper/config.json`
  或环境变量（`JELLYFIN_TOKEN` / `EMBY_TOKEN` / `JELLYFIN_USER` / `EMBY_USER`）
- Gitea 令牌：旧 token 只有 `write:repository`（能推不能建仓），新换的 `935aab78…` 是全权 token
  （已写进两个仓库的 `.git/config`）
- 推送脚本：`C:\Temp\opencode\push_to_gitea.ps1`（`-Token` / `-Password` 可自动建仓后推送）



