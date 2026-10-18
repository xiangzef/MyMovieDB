"""
修复 Jellyfin 导入时 code 前导零丢失的问题

问题：scan_jellyfin_directory 从目录名提取 code（如 ABP-013 → ABP-13），
但 Jellyfin 目录名本身就带前导零，导致 code 格式不一致。

修复：统一将 movies.code 和 local_videos.code 更新为正确格式（ABP-13 → ABP-013），
同时重命名 covers 目录。

用法：python scripts/fix_jellyfin_code_normalization.py
"""
import sys
import os
import shutil
sys.path.insert(0, 'backend')
from database import get_db

def fix():
    db = get_db()
    c = db.cursor()
    covers_base = 'F:/github/MyMovieDB/data/covers'

    # 找出所有需要修正的 movies
    c.execute("""
        SELECT id, code, video_path FROM movies
        WHERE source_type = 'jellyfin'
        AND video_path IS NOT NULL AND video_path != ''
    """)

    updates = []
    for row in c:
        code = row['code']
        vpath = row['video_path']
        dir_name = os.path.basename(os.path.dirname(vpath)) if vpath else ''
        if dir_name != code and dir_name != '':
            if '-' in code and '-' in dir_name:
                code_pref, code_num = code.rsplit('-', 1)
                dir_pref, dir_num = dir_name.rsplit('-', 1)
                if code_pref == dir_pref and int(code_num) == int(dir_num):
                    updates.append((dir_name, code, row['id']))

    print(f'需要修正的 movies: {len(updates)}')
    if not updates:
        print('无需修正')
        return

    renamed_covers = 0
    updated_movies = 0
    updated_lv = 0
    errors = 0

    for new_code, old_code, movie_id in updates:
        # 1. 重命名 covers 目录（如果存在）
        old_cover = os.path.join(covers_base, old_code)
        new_cover = os.path.join(covers_base, new_code)
        if os.path.exists(old_cover):
            # Windows 两步 rename（大小写敏感问题）
            if old_cover.lower() != new_cover.lower():
                tmp = old_cover + '_tmp_'
                try:
                    os.rename(old_cover, tmp)
                    os.rename(tmp, new_cover)
                    renamed_covers += 1
                except Exception as e:
                    print(f'  ❌ rename covers {old_code} → {new_code}: {e}')
                    errors += 1
                    continue

        # 2. 更新 movies.code
        c.execute('UPDATE movies SET code = ? WHERE id = ?', (new_code, movie_id))

        # 3. 更新 local_videos.code
        c.execute('UPDATE local_videos SET code = ? WHERE code = ?', (new_code, old_code))
        updated_lv += c.rowcount

        updated_movies += 1

        if updated_movies % 50 == 0:
            print(f'  已处理 {updated_movies}/{len(updates)}')

    db.commit()
    print(f'\n✅ 完成: movies更新={updated_movies}, covers重命名={renamed_covers}, local_videos更新={updated_lv}, errors={errors}')
    db.close()

if __name__ == '__main__':
    fix()