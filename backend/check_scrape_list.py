import sys
sys.path.insert(0, '.')
from database import get_unscraped_local_videos, check_and_fix_scrape_status

# 模拟前端批量刮削请求的默认参数
result = get_unscraped_local_videos(page=1, per_page=9999, search='', source_id=None)
print(f"get_unscraped_local_videos 返回总数: {result['total']}")
print(f"返回页数: {result['pages']}")
print()
print("前20个视频:")
for v in result['items'][:20]:
    status = v.get('scrape_status') or 'NULL'
    title = (v.get('title') or '')[:20]
    src = v.get('source_type') or 'NULL'
    print(f"  [{v['code']}] status={status} src={src} title={title}")

# 统计这些视频的 scrape_status 分布
print()
status_counts = {}
src_counts = {}
for v in result['items']:
    s = v.get('scrape_status') or 'NULL'
    src = v.get('source_type') or 'NULL'
    status_counts[s] = status_counts.get(s, 0) + 1
    src_counts[src] = src_counts.get(src, 0) + 1

print("scrape_status 分布:", status_counts)
print("source_type 分布:", src_counts)
