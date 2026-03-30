import database as db

# 手动添加 Z:\影视库
success = db.mark_source_as_jellyfin(r'Z:\影视库', video_count=0)
print(f"添加结果: {success}")

# 验证
sources = db.get_local_sources_with_jellyfin()
print("\n更新后的目录列表:")
for s in sources:
    print(f"  - {s['path']} (Jellyfin={s['is_jellyfin']})")
