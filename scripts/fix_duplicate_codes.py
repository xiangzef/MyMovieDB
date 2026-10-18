"""
修复重复番号问题（normalize_code 规范化后相同的番号）- 完整版

问题：Jellyfin 导入时 code 格式不一致，如 MIDA-092 和 MIDA-92 都被当作不同番号，
但 normalize_code 后都变成 MIDA-92，导致 local_videos 关联错误。

修复策略：
1. 每组保留 scrape_status=complete 的记录（没有则保留任意一个）
2. 更新 local_videos.movie_id 指向正确记录
3. 删除重复的 movies 记录
"""
import sys
sys.path.insert(0, 'backend')
from database import get_db, normalize_code

def fix_duplicates():
    db = get_db()
    c = db.cursor()

    # 找出所有 movies 按 normalized code 分组
    c.execute("SELECT id, code, scrape_status, source_type FROM movies ORDER BY code")
    rows = c.fetchall()

    from collections import defaultdict
    groups = defaultdict(list)
    for r in rows:
        groups[normalize_code(r['code'])].append(dict(r))

    fixed = []
    deleted = 0
    updated_lv = 0

    for norm_code, items in groups.items():
        if len(items) <= 1:
            continue

        # 优先保留 complete 的
        complete_items = [x for x in items if x['scrape_status'] == 'complete']
        if complete_items:
            keep = complete_items[0]
        else:
            keep = items[0]  # 没有 complete 就保留第一个

        other_codes = [x['code'] for x in items if x['code'] != keep['code']]
        other_ids = [x['id'] for x in items if x['code'] != keep['code']]

        print(f"\n=== {norm_code}: 保留 {keep['code']} (id={keep['id']}, status={keep['scrape_status']}) ===")
        if other_codes:
            print(f"  删除: {other_codes}")

        # 更新 local_videos 指向保留的记录
        for oc in other_codes:
            c.execute("""
                UPDATE local_videos
                SET movie_id = ?
                WHERE code = ? AND movie_id != ?
            """, (keep['id'], oc, keep['id']))
            updated = c.rowcount
            if updated > 0:
                print(f"    更新 {updated} 条 local_videos ({oc} → {keep['code']})")
                updated_lv += updated

        # 删除重复的 movies 记录
        for oc in other_codes:
            c.execute("DELETE FROM movies WHERE code = ?", (oc,))
            deleted += c.rowcount

        fixed.append((keep['code'], other_codes))

    db.commit()
    print(f"\n\n✅ 完成：修复了 {len(fixed)} 组重复番号")
    print(f"   更新了 {updated_lv} 条 local_videos 关联")
    print(f"   删除了 {deleted} 条重复 movies 记录")
    db.close()

if __name__ == '__main__':
    fix_duplicates()
