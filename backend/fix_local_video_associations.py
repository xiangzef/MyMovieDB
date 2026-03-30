"""
修复被网络刮削覆盖的本地视频关联
- 恢复 source_type 和 video_path
- 恢复 local_video_id 关联
"""
import database as db

def fix_local_video_associations():
    conn = db.get_db()
    cursor = conn.cursor()
    
    # 1. 查找所有 local_videos 表中有记录但 movies 表中 local_video_id 为空的影片
    cursor.execute("""
        SELECT lv.id as lv_id, lv.code, lv.path, m.id as movie_id, m.source_type, m.local_video_id
        FROM local_videos lv
        LEFT JOIN movies m ON lv.code = m.code
        WHERE m.id IS NOT NULL AND m.local_video_id IS NULL
    """)
    rows = cursor.fetchall()
    
    print(f"找到 {len(rows)} 个需要修复的关联")
    
    for row in rows:
        lv_id = row[0]
        code = row[1]
        path = row[2]
        movie_id = row[3]
        
        # 更新 movies 表
        cursor.execute("""
            UPDATE movies 
            SET local_video_id = ?, 
                source_type = 'jellyfin',
                video_path = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (lv_id, path, movie_id))
        
        # 更新 local_videos 表的 movie_id
        cursor.execute("UPDATE local_videos SET movie_id = ? WHERE id = ?", (movie_id, lv_id))
        
        print(f"✅ 修复: {code} -> local_video_id={lv_id}, path={path}")
    
    conn.commit()
    conn.close()
    print(f"\n修复完成，共 {len(rows)} 条记录")

if __name__ == "__main__":
    fix_local_video_associations()
