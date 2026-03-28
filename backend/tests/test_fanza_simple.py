"""
简单测试 Fanza 爬虫
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from bs4 import BeautifulSoup

# 测试 URL
url = "https://www.dmm.co.jp/mono/dvd/-/detail/=/cid=ssis254/"

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})
session.cookies.set("age_check_done", "1", domain=".dmm.co.jp")

resp = session.get(url, timeout=10)
print(f"状态码: {resp.status_code}")

soup = BeautifulSoup(resp.content, "lxml")

# 提取标题
title = soup.select_one("h1")
print(f"标题: {title.get_text(strip=True) if title else '无'}")

# 提取演员
actors = soup.select('a[href*="article=actress"]')
print(f"演员: {[a.get_text(strip=True) for a in actors[:3]]}")

# 提取封面
img = soup.select_one('img[src*="pics.dmm"]')
print(f"封面: {img.get('src', '')[:60] if img else '无'}...")

# 检查是否有效
if "SSIS" in resp.text.upper():
    print("✅ 页面有效")
else:
    print("❌ 页面无效")
