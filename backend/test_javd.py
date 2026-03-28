import requests

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# 测试 Javd 搜索
url = 'https://javd.me/search?q=HUBLK-068'
resp = requests.get(url, headers=headers, timeout=30)
print('URL:', resp.url)
print('\n页面内容前2000字符:')
print(resp.text[:2000])
