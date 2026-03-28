"""继续测试网站"""
import requests
from bs4 import BeautifulSoup
import re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

def test_avbase_detail():
    """测试 Avbase 详情页"""
    print('\n=== 测试 Avbase 详情页 ===')
    url = 'https://www.avbase.net/works/BDSR-55301'
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        print(f'状态码: {resp.status_code}')
        print(f'URL: {resp.url}')
        soup = BeautifulSoup(resp.text, 'lxml')

        # 提取信息
        title = soup.select_one('h1, .title, .works-title')
        if title:
            print(f'标题: {title.get_text(strip=True)[:80]}')

        code_match = re.search(r'([A-Z]{1,6}-\d{2,5})', soup.get_text(), re.IGNORECASE)
        if code_match:
            print(f'番号: {code_match.group(1).upper()}')

        img = soup.select_one('img')
        if img:
            src = img.get('src') or img.get('data-src', '')
            print(f'封面: {src}')

        print(f'\nHTML片段:\n{soup.get_text()[:300]}')
    except Exception as e:
        print(f'错误: {e}')

def test_javd_direct():
    """直接测试 Javd 详情页"""
    print('\n=== 测试 Javd 直接访问 ===')
    # 根据用户给的重定向URL
    url = 'https://javd.me/movie/69c3f0f50fa10/HUBLK-068'
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        print(f'状态码: {resp.status_code}')
        soup = BeautifulSoup(resp.text, 'lxml')

        title = soup.select_one('h1, h2')
        if title:
            print(f'标题: {title.get_text(strip=True)[:80]}')

        # 提取番号
        code_match = re.search(r'([A-Z]{1,6}-\d{2,5})', soup.get_text(), re.IGNORECASE)
        if code_match:
            print(f'番号: {code_match.group(1).upper()}')

        # 提取封面
        imgs = soup.select('img')
        for img in imgs[:2]:
            src = img.get('src', '') or img.get('data-src', '')
            if src:
                print(f'封面: {src}')

    except Exception as e:
        print(f'错误: {e}')

def test_javd_search():
    """测试 Javd 搜索"""
    print('\n=== 测试 Javd 搜索 ===')
    url = 'https://javd.me/search?q=HUBLK-068'
    try:
        resp = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        print(f'最终URL: {resp.url}')
        soup = BeautifulSoup(resp.text, 'lxml')

        # 找所有链接
        links = soup.select('a')
        for l in links:
            href = l.get('href', '')
            if '/movie/' in href:
                print(f'找到电影链接: {href}')
                text = l.get_text(strip=True)[:50]
                print(f'  文字: {text}')

    except Exception as e:
        print(f'错误: {e}')

def test_javcup_search():
    """测试 Javcup 搜索"""
    print('\n=== 测试 Javcup ===')
    url = 'https://javcup.com/search?q=hmn-803'
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        print(f'状态码: {resp.status_code}')
        soup = BeautifulSoup(resp.text, 'lxml')

        # 找结果
        links = soup.select('a')
        movie_links = []
        for l in links:
            href = l.get('href', '')
            if href.startswith('/movie/') or href.startswith('/video/'):
                movie_links.append(href)
                print(f'找到: {href}')

        if movie_links:
            # 访问第一个详情页
            detail_url = 'https://javcup.com' + movie_links[0]
            resp2 = requests.get(detail_url, headers=headers, timeout=30)
            soup2 = BeautifulSoup(resp2.text, 'lxml')
            title = soup2.select_one('h1, .title')
            if title:
                print(f'\n详情页标题: {title.get_text(strip=True)[:80]}')
            code_match = re.search(r'([A-Z]{1,6}-\d{2,5})', soup2.get_text(), re.IGNORECASE)
            if code_match:
                print(f'番号: {code_match.group(1).upper()}')

    except Exception as e:
        print(f'错误: {e}')

def test_avbase_search():
    """测试 Avbase 搜索"""
    print('\n=== 测试 Avbase 搜索 ===')
    url = 'https://www.avbase.net/works?q=BDSR-55301'
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        print(f'状态码: {resp.status_code}')
        soup = BeautifulSoup(resp.text, 'lxml')

        links = soup.select('a')
        for l in links[:20]:
            href = l.get('href', '')
            text = l.get_text(strip=True)[:50]
            if href:
                print(f'{href}: {text}')

    except Exception as e:
        print(f'错误: {e}')

def test_javbooks_search():
    """测试 Javbooks 搜索"""
    print('\n=== 测试 Javbooks ===')
    url = 'https://jkk044.com/serchinfo_censored/IamOverEighteenYearsOld/topicsbt_1.htm?keyword=PFES-138'
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        print(f'状态码: {resp.status_code}')
        soup = BeautifulSoup(resp.text, 'lxml')

        # 找表格或列表
        rows = soup.select('tr')
        print(f'找到 {len(rows)} 行')
        for row in rows[:5]:
            cells = row.select('td')
            if cells:
                print(' | '.join([c.get_text(strip=True)[:30] for c in cells[:4]]))

    except Exception as e:
        print(f'错误: {e}')

if __name__ == '__main__':
    test_avbase_detail()
    test_javd_direct()
    test_javd_search()
    test_javcup_search()
    test_avbase_search()
    test_javbooks_search()
