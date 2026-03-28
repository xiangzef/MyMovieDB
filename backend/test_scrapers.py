"""测试各网站爬虫"""
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import quote

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

def test_av_wiki():
    print('\n=== 测试 Av-Wiki ===')
    url = 'https://av-wiki.net/?s=SIM-091&post_type=product'
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        soup = BeautifulSoup(resp.text, 'lxml')
        # 找阅读全文链接
        more_links = soup.select('a.more-link, a[href*="av-wiki.net/sim"]')
        for l in more_links:
            href = l.get('href', '')
            if href and 'av-wiki.net/sim' in href:
                print(f'找到详情页: {href}')
                resp2 = requests.get(href, headers=headers, timeout=30)
                soup2 = BeautifulSoup(resp2.text, 'lxml')
                title = soup2.select_one('h1, .entry-title')
                if title:
                    print(f'标题: {title.get_text(strip=True)}')
                # 提取番号
                code_match = re.search(r'([A-Z]{1,6}-\d{2,5})', soup2.get_text(), re.IGNORECASE)
                if code_match:
                    print(f'番号: {code_match.group(1).upper()}')
                # 提取封面
                img = soup2.select_one('img')
                if img:
                    print(f'封面: {img.get("src", "")}')
                return True
        print('未找到详情链接')
        return False
    except Exception as e:
        print(f'错误: {e}')
        return False

def test_avbase():
    print('\n=== 测试 Avbase ===')
    url = 'https://www.avbase.net/works?q=BDSR-55301'
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        soup = BeautifulSoup(resp.text, 'lxml')
        # 找搜索结果
        items = soup.select('.movie-box, .item, a[href*="/works/"]')
        for item in items[:3]:
            href = item.get('href', '')
            if '/works/' in href and 'avbase' in href:
                print(f'找到详情页: {href}')
                resp2 = requests.get(href, headers=headers, timeout=30)
                soup2 = BeautifulSoup(resp2.text, 'lxml')
                title = soup2.select_one('h1, .title')
                if title:
                    print(f'标题: {title.get_text(strip=True)}')
                code_match = re.search(r'([A-Z]{1,6}-\d{2,5})', soup2.get_text(), re.IGNORECASE)
                if code_match:
                    print(f'番号: {code_match.group(1).upper()}')
                return True
        print('未找到结果')
        return False
    except Exception as e:
        print(f'错误: {e}')
        return False

def test_javd():
    print('\n=== 测试 Javd ===')
    url = 'https://javd.me/search?q=HUBLK-068'
    try:
        resp = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        print(f'重定向到: {resp.url}')
        soup = BeautifulSoup(resp.text, 'lxml')
        # 找电影链接
        links = soup.select('a[href*="/movie/"]')
        for l in links[:3]:
            href = l.get('href', '')
            if '/movie/' in href:
                print(f'找到详情页: {href}')
                resp2 = requests.get(href, headers=headers, timeout=30)
                soup2 = BeautifulSoup(resp2.text, 'lxml')
                title = soup2.select_one('h1')
                if title:
                    print(f'标题: {title.get_text(strip=True)}')
                code_match = re.search(r'([A-Z]{1,6}-\d{2,5})', soup2.get_text(), re.IGNORECASE)
                if code_match:
                    print(f'番号: {code_match.group(1).upper()}')
                return True
        print('未找到结果')
        return False
    except Exception as e:
        print(f'错误: {e}')
        return False

def test_javcup():
    print('\n=== 测试 Javcup ===')
    url = 'https://javcup.com/search?q=hmn-803'
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        soup = BeautifulSoup(resp.text, 'lxml')
        items = soup.select('.movie-item, .item, .video-item, a[href*="/movie/"]')
        for item in items[:5]:
            href = item.get('href', '')
            if href and ('/movie/' in href or '/video/' in href):
                print(f'找到详情页: {href}')
                resp2 = requests.get(href, headers=headers, timeout=30)
                soup2 = BeautifulSoup(resp2.text, 'lxml')
                title = soup2.select_one('h1')
                if title:
                    print(f'标题: {title.get_text(strip=True)}')
                code_match = re.search(r'([A-Z]{1,6}-\d{2,5})', soup2.get_text(), re.IGNORECASE)
                if code_match:
                    print(f'番号: {code_match.group(1).upper()}')
                return True
        print('未找到结果，HTML片段:')
        print(resp.text[:500])
        return False
    except Exception as e:
        print(f'错误: {e}')
        return False

def test_javinfo():
    print('\n=== 测试 Jav情报站 ===')
    # 先访问搜索页面获取cookie和hash
    search_page_url = 'https://pc5.top/search.php'
    try:
        session = requests.Session()
        session.headers.update(headers)
        resp = session.get(search_page_url, timeout=30)
        soup = BeautifulSoup(resp.text, 'lxml')

        # 提取hash
        hash_val = ''
        code_val = ''
        hash_input = soup.select_one('input[name="hash"]')
        code_input = soup.select_one('input[name="code"]')
        if hash_input:
            hash_val = hash_input.get('value', '')
        if code_input:
            code_val = code_input.get('value', '')

        print(f'获取到 hash: {hash_val[:20]}..., code: {code_val}')

        # 发送搜索请求
        search_url = f'https://pc5.top/search.php?s=fns-199&code={code_val}&hash={hash_val}'
        resp2 = session.get(search_url, timeout=30)
        soup2 = BeautifulSoup(resp2.text, 'lxml')

        # 找结果
        items = soup2.select('a[href*="/article/"]')
        for item in items[:3]:
            href = item.get('href', '')
            if '/article/' in href:
                print(f'找到详情页: {href}')
                resp3 = session.get(href, timeout=30)
                soup3 = BeautifulSoup(resp3.text, 'lxml')
                title = soup3.select_one('h1, .title')
                if title:
                    print(f'标题: {title.get_text(strip=True)}')
                code_match = re.search(r'([A-Z]{1,6}-\d{2,5})', soup3.get_text(), re.IGNORECASE)
                if code_match:
                    print(f'番号: {code_match.group(1).upper()}')
                return True
        print('未找到结果')
        return False
    except Exception as e:
        print(f'错误: {e}')
        return False

def test_javbooks():
    print('\n=== 测试 Javbooks ===')
    url = 'https://jkk044.com/serch_censored.htm'
    try:
        session = requests.Session()
        session.headers.update(headers)
        # 先获取页面
        resp = session.get(url, timeout=30)
        soup = BeautifulSoup(resp.text, 'lxml')

        # 找搜索表单
        forms = soup.select('form')
        print(f'找到 {len(forms)} 个表单')

        # 尝试直接搜索
        search_url = 'https://jkk044.com/serchinfo_censored/IamOverEighteenYearsOld/topicsbt_1.htm?keyword=PFES-138'
        resp2 = session.get(search_url, timeout=30)
        soup2 = BeautifulSoup(resp2.text, 'lxml')

        items = soup2.select('a[href*="htm"], tr')
        print(f'找到 {len(items)} 个链接')
        for item in items[:5]:
            href = item.get('href', '')
            text = item.get_text(strip=True)[:50]
            print(f'  {href}: {text}')
        return False
    except Exception as e:
        print(f'错误: {e}')
        return False

if __name__ == '__main__':
    print('='*50)
    print('测试各网站爬虫')
    print('='*50)

    test_av_wiki()
    test_avbase()
    test_javd()
    test_javcup()
    test_javinfo()
    test_javbooks()

    print('\n' + '='*50)
    print('测试完成')
    print('='*50)
