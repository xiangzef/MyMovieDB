# scripts/ — 运维脚本库

MyMovieDB 的**一次性运维脚本**都放在这里（削刮、修库、整理媒体库、探针）。
2026-11-12 起整体纳入 git 跟踪，配套本说明。

> ⚠️ 这些脚本大多会**直接改数据**（`data/movies.db`、`Z:\av`、`X:\jellyfin`），
> 跑之前先看脚本头部的说明；带 `--apply` / `--delete` 的先跑预览模式。

---

## 一、Jellyfin / Emby 媒体库整理（`scripts/jellyfin_helper.py` 体系）

> 完整说明见 `docs/JELLYFIN_HELPER.md`。独立仓库：`F:\github\jellyfin-helper`

| 脚本 | 作用 |
|------|------|
| `jellyfin_helper.py` | **主工具**：scan → fetch → plan → apply → push 一条龙，把新增资源整理成媒体服务器可识别结构 |
| `_tmdb_fetch.py` | TMDB 抓取模块（需在能访问 tmdb.org 的机器上跑；`--fetch-host vps` 会甩给 VPS） |
| `_selftest_helper.py` | 自测：发布名解析用例 + 沙盒全流程（不碰真实库） |
| `jellyfin_media_organize.py` | 早期版本：把下载目录重命名成标准结构 + 写 NFO + 下载图片（dry-run 默认） |
| `jellyfin_apply_metadata.py` | 把元数据 + 图片通过 API 写进 Jellyfin / Emby |
| `jellyfin_toggle_fetchers.py` | 临时禁用 / 恢复 TMDB+TVDB 抓削器（代理没修好时避免扫描卡死） |
| `probe_metadata_reach.py` | 探测服务器到 TMDB 的真实连通性（区分 DNS 污染 / 被封锁） |
| `_media_servers.py` | 媒体服务器连接配置（**凭据统一入口**，见下） |

## 二、AV 库（Z:\av）盘库与整理

| 脚本 | 作用 |
|------|------|
| `step1_rescan_relink.py` | 盘库数据重建：死源清理 + X:\jellyfin 全量重扫 + movies 按 code 重连 |
| `step2_scan_zav.py` | 扫描 Z:\av → local_videos 入库（source_id=14） |
| `step2_prep.py` | 刷新 movies.jellyfin_status + 添加 Z:\av 本地源 |
| `step2_scrape_driver.py` | 批量刮削驱动：消费 SSE 流并记录日志 |
| `step2_offline_scrape.py` | 离线批量刮削（DMM GraphQL / r18.dev / av-wiki 直连，绕过 SSE 超时） |
| `step3_organize_ltx.py` | Z:\av 原地整理为 `{女优}\{番号}+{标题}+{女优}+LTX\` + 破解标注 |
| `step3_dryrun.py` | Step3 预演：演员目录分布 + DMM 网络状态 |
| `rename_library.py` | 全库重命名 + 女优合并（dry-run，`--apply` 才执行） |
| `zav_check.py` / `zav_overlap.py` / `zav_torrents.py` / `zav_cleanup.py` | 盘库检查 / 番号重叠 / 种子归拢 / 根目录收尾 |
| `audit_zav.py` | 整理后总审计 |
| `verify_rename.py` | 重命名后总验证（目录结构、资产完整性、DB 一致性） |

## 三、刮削补全 / 修数据

| 脚本 | 作用 |
|------|------|
| `salvage_finalize.py` / `salvage_r18dev.py` | 补刮失败番号（r18.dev 直取 → 回查 DMM 升级日文全量） |
| `post_dmm_recovery.py` / `final_retry.py` / `fix_final_round.py` | DMM 恢复后的收尾批 / 终轮重试 |
| `fix_cover_remaining.py` / `fix_cover_stubborn.py` / `fix_missing_images.py` | 补封面（多图床 × 直连/代理重试） |
| `fix_snis939_cover.py` | 单片换高清封面（要求 > 600px 宽） |
| `fix_r18dev_titles.py` / `fix_title_alias.py` / `fix_actor_field.py` / `fix_nfo_paths.py` | 标题 / 演员字段 / NFO 路径修正 |
| `fix_duplicate_codes.py` / `fix_jellyfin_code_normalization.py` | 重复番号 / Jellyfin 导入丢前导零 |
| `finalize_rename.py` | 收尾：删空目录 + NFO 演员名日文化 + 补 LTX 标签 |
| `ingest_manual5.py` | 手工命名的 5 部连同封面入库 |

## 四、库同步 / 迁移 / 维护

| 脚本 | 作用 |
|------|------|
| `sync_media_paths.py` | 按磁盘实际状态同步 local_videos / local_sources（幂等） |
| `restore_jellyfin_local_videos.py` | 重建 Jellyfin 影片的 local_videos 记录 |
| `rebuild_jellyfin_sources.py` | 一键重建 Jellyfin 视频源 |
| `cleanup_jellyfin.py` | 清理 Jellyfin 视频源记录及其本地视频 |
| `check_jellyfin_sources.py` / `test_jellyfin_scan.py` | 视频源与扫描自检 |
| `migrate_db_to_nas.py` | 数据库迁移到 NAS |
| `media-merge.sh` | 跨卷搬运演员目录（rsync 复制+校验，成功才删源） |
| `clean_empty_folders.py` | 扫描目录找垃圾文件夹（空/仅种子/小而无影视），送回收站 |

## 五、探针 / 诊断

| 脚本 | 作用 |
|------|------|
| `dmm_probe.py` / `net_matrix.py` / `test_proxy_pass.py` / `test_single_source.py` | 各刮削源 直连 vs 代理 的连通性矩阵 |
| `inspect_unmatched_pages.py` / `probe_unmatched.py` | 看未命中片的真实返回内容 |
| `db_inspect*.py` (4 个) | movies.db 表结构 / 路径现状 / 死行统计 |
| `check_*.py` | 各专项体检（标题质量、缺图、重叠、演员字段、恢复成果…） |
| `debug_extract.py` / `check_titles.py` | 番号提取与标题质量调试 |

---

## 凭据管理（重要）

**任何 token / 密码都不写进脚本**。统一从两处取：

```powershell
# 1) 环境变量
$env:JELLYFIN_TOKEN = "xxxx"; $env:EMBY_TOKEN = "xxxx"

# 2) 配置文件（jellyfin_helper.py 首次运行自动生成）
%USERPROFILE%\.jellyfin_helper\config.json
```

`scripts/_media_servers.py` 是统一入口（`get_server("jellyfin")`），
新增脚本请从它取连接信息，别再硬编码。

NAS / Gitea 等其它系统的口令同样不入库，见 `docs/NAS_MEDIA_INFRA.md`。
