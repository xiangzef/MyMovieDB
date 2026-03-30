import database as db

sources = db.get_local_sources_with_jellyfin()
print("All sources in database:")
for s in sources:
    print(f"  - {s['path']} (Jellyfin={s['is_jellyfin']}, video_count={s['video_count']})")
