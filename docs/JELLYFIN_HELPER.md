# Jellyfin / Emby 影视整理助手（scripts/jellyfin_helper.py）

把 NAS 上新下载的影视资源，整理成 Jellyfin / Emby 能直接识别的标准结构 + 抓取中文元数据。

> 背景见 `NAS_MEDIA_INFRA.md` 第五节：NAS 访问不到 `api.themoviedb.org`（DNS 污染），
> 所以元数据是**在能访问 tmdb.org 的机器上抓**（默认甩给 VPS），再写成本地 NFO + 图片，
> 媒体服务器扫库即可显示。等代理修好后，Jellyfin 自己就能刮，这个脚本就不必再跑了。

---

## 一、它做什么

```
电影\{中文名} {英文名}\{原始发布名}.ext
    movie.nfo  poster.jpg  fanart.jpg  thumb.jpg

电视剧\{中文名} {英文名}\
    tvshow.nfo  poster.jpg  fanart.jpg  thumb.jpg
    Season N\
        season.nfo  season-poster.jpg
        {剧名} SxxEyy.ext  {剧名} SxxEyy.nfo  {剧名} SxxEyy-thumb.jpg
```

- 发布名解析：去方括号/年份/分辨率/编码/音轨/压制组等标签，识别标题、年份、季集号、分集小标题
- 中文片名优先用发布名里的 `[中文名]`，其次是文件名开头的中文段（如 `非洲：地球的野性家园.Africa...`），
  再次是文件夹名里的中文；都没有就用 TMDB 的 zh-CN 名
- **下载未完成的文件会自动跳过**（`.bt.xltd` / `.xltd` / `.!qb` / `.tmp` 等），并在扫描结果里列出来
- 匹配 TMDB 时多策略搜索（原样 → 去年份 → 逐步缩短前缀/后缀 → 中文名），
  再按年份 + 标题 token + 特征词校验打分，**宁可漏配也不错配**
- 已整理过的目录会读 `movie.nfo` / `tvshow.nfo` 里的 `tmdbid` 直接定位，不重复搜索
- 最后通过 API 把元数据和图片推给 Jellyfin / Emby（可选，也可只让服务器读 NFO）

## 二、命令

```bash
python scripts/jellyfin_helper.py <命令> [参数]
```

| 命令 | 作用 |
|------|------|
| `scan` | 扫描新增资源，解析发布名，看看识别得对不对 |
| `fetch` | 抓 TMDB 元数据（`--fetch-host vps\|local`），存成 pack |
| `plan` | 生成整理计划（只打印，不动文件） |
| `apply` | 执行整理：移动/重命名 + 写 NFO + 下载图片 |
| `push` | 把元数据与图片写进 Jellyfin / Emby，并触发扫库 |
| `run` | scan → fetch → plan → apply → push 一条龙（加 `--apply` 才真动手） |
| `probe` | 检测服务器到 TMDB 的真实连通性（区分 DNS 污染 / 被封锁） |

常用参数：

| 参数 | 说明 |
|------|------|
| `--since 2d` | 扫最近 2 天的文件（支持 `12h` / `30m` / `all`） |
| `--only movie\|tv\|both` | 扫哪个库，默认 both |
| `--paths <目录…>` | 直接指定目录，忽略库根目录 |
| `--movie-root / --tv-root` | 临时改库根目录 |
| `--fetch-host vps\|local` | 在哪台机器抓元数据（默认 vps） |
| `--server jellyfin\|emby` | push/probe 只针对某一台 |
| `--apply` | `run` 子命令下真正执行 |

## 三、典型流程

```powershell
# 1) 先看识别结果
python scripts/jellyfin_helper.py scan --since 2d

# 2) 抓元数据（默认甩给 VPS，它能访问 tmdb.org）
python scripts/jellyfin_helper.py fetch --since 2d

# 3) 看计划对不对
python scripts/jellyfin_helper.py plan --since 2d

# 4) 执行整理
python scripts/jellyfin_helper.py apply --since 2d

# 5) 推给服务器 + 扫库
python scripts/jellyfin_helper.py push --since 2d
```

或者一条龙（先看计划，确认后再 `--apply`）：

```powershell
python scripts/jellyfin_helper.py run --since 2d
python scripts/jellyfin_helper.py run --since 2d --apply
```

## 四、配置文件

首次运行会在 `~/.jellyfin_helper/config.json` 生成默认配置，可直接改：

```json
{
  "movie_root": "Y:\\电影",
  "tv_root": "Y:\\电视剧",
  "vps": "root@47.101.178.144",
  "fetch_host": "vps",
  "jellyfin": {"base": "http://192.168.1.179:8096", "token": "...", "user": "..."},
  "emby": {"base": "http://192.168.1.179:8097", "token": "...", "user": "..."}
}
```

## 五、匹配不到怎么办

工具默认**不强配**（避免把 A 片安到 B 片名下），匹配不到会在 plan 里标 `[跳过]`。

两种手动兜底：

1. 把 TMDB id 写进对应目录的 `movie.nfo` / `tvshow.nfo`：

```xml
<tmdbid>121446</tmdbid>
```

再跑 `fetch → plan → apply`，工具会直接用这个 id 抓取。

2. 有些片子 TMDB 自己的站内搜索就是搜不到（例如 `Cosmos A Spacetime Odyssey` 2020 电影，
   各种关键词都搜不出来），这时只能手工查 id 再按上面办法指定。

> 匹配到的结果如果是「宽松匹配」（用缩短的关键词命中的），score 会偏低，建议在 plan 里
> 核对一眼再 apply。

## 六、实测过的发布名

| 文件名 | 解析结果 |
|--------|----------|
| `Birders.The.Central.Park.Effect.2012.1080p.WEB-DL.H264.AAC-SONYHD.mp4` | 标题 Birders The Central Park Effect / 年 2012 |
| `我的章鱼老师.1080p.BD中英双字[66影视www.66Ys.Co].mp4` | 标题 我的章鱼老师 |
| `[猎捕].The.Hunt.EP01.2015.BluRay.720p.x264.AC3.2Audios-CMCT.mkv` | The Hunt / S01E01 / 年 2015 / 中文名 猎捕 |
| `[萌宠成长记].CCTV1HD.Too.Cute.EP03.HDTV.720p.x264.AC3-CMCT.mkv` | Too Cute / S01E03 / 中文名 萌宠成长记 |
| `非洲：地球的野性家园.Africa.Earths.Wild.Home.S01E01.Welcome.to.Africa.1080p.HD中字[最新电影www.dyg7.com].mp4` | Africa Earths Wild Home / S01E01 / 分集小标题 Welcome to Africa / 中文名 非洲：地球的野性家园 |
| `狮王.荣耀之战.Lion.S01E01.1080p.CHS&ENG.www.xingfan.cc.mp4` | Lion / S01E01 / 中文名 狮王 荣耀之战 |
| `A.Gorilla.Story.-.Told.by.David.Attenborough.(2026).WEBRip-1080p.Proper.mkv` | A Gorilla Story Told by David Attenborough / 年 2026 |

## 七、相关文件

| 文件 | 作用 |
|------|------|
| `scripts/jellyfin_helper.py` | 主程序（本文件说明的对象） |
| `scripts/_tmdb_fetch.py` | TMDB 抓取模块，可单独跑：`python3 _tmdb_fetch.py spec.json out.json` |
| `scripts/_selftest_helper.py` | 自测：发布名解析 + 沙盒全流程（不碰真实库） |
| `scripts/probe_metadata_reach.py` | 连通性探测（旧版，等价于 `jellyfin_helper.py probe`） |
| `scripts/jellyfin_toggle_fetchers.py` | 临时禁用/恢复 TMDB+TVDB 抓削器（代理没修好时用） |
