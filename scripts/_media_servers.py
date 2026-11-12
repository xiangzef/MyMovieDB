# -*- coding: utf-8 -*-
"""
媒体服务器连接配置（Jellyfin / Emby）—— 凭据统一从这里取，不写死在脚本里。

取值优先级：
  1. 环境变量：JELLYFIN_BASE / JELLYFIN_TOKEN / JELLYFIN_USER（Emby 同理）
  2. 配置文件 ：%USERPROFILE%\\.jellyfin_helper\\config.json（jellyfin_helper.py 生成）
  3. 默认值   ：只有地址，用户名/token 为空

用法：
    from _media_servers import get_server
    base, token, user = get_server("jellyfin")
"""
from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_FILE = Path(os.environ.get(
    "JELLYFIN_HELPER_HOME", Path.home() / ".jellyfin_helper")) / "config.json"

DEFAULTS = {
    "jellyfin": {"base": "http://192.168.1.179:8096", "token": "", "user": ""},
    "emby": {"base": "http://192.168.1.179:8097", "token": "", "user": ""},
}
ENV = {
    "jellyfin": ("JELLYFIN_BASE", "JELLYFIN_TOKEN", "JELLYFIN_USER"),
    "emby": ("EMBY_BASE", "EMBY_TOKEN", "EMBY_USER"),
}


def _file_cfg():
    try:
        if CONFIG_FILE.exists():
            return json.load(open(CONFIG_FILE, encoding="utf-8"))
    except Exception:
        pass
    return {}


def get_server(which="jellyfin"):
    """返回 (base_url, token, user_id)；缺 token 时 token 为空串"""
    cfg = dict(DEFAULTS.get(which, DEFAULTS["jellyfin"]))
    file_cfg = _file_cfg().get(which) or {}
    cfg.update({k: v for k, v in file_cfg.items() if v})
    env_base, env_token, env_user = ENV.get(which, (None, None, None))
    if os.environ.get(env_base or ""):
        cfg["base"] = os.environ[env_base]
    if os.environ.get(env_token or ""):
        cfg["token"] = os.environ[env_token]
    if os.environ.get(env_user or ""):
        cfg["user"] = os.environ[env_user]
    return cfg.get("base", ""), cfg.get("token", ""), cfg.get("user", "")


def auth_header(token):
    return {"Authorization": 'MediaBrowser Token="%s"' % token,
            "Content-Type": "application/json"}


def need_token(which, token):
    if not token:
        raise SystemExit(
            f"缺少 {which} 的 API token。请任选一种方式提供：\n"
            f"  set {ENV[which][1]}=xxxx   （环境变量）\n"
            f"  或在 {CONFIG_FILE} 里填 {which}.token\n"
            f"  token 可在 {which} 的 设置/管理后台 → API 密钥 生成")
