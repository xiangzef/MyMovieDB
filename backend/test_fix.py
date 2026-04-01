import sys
sys.path.insert(0, 'F:/github/MyMovieDB/backend')
import gfriends
import database as db

total, actors = db.get_actor_stats(page=1, page_size=1000)
known = sum(1 for a in actors if a['has_avatar'])
print(f'总演员: {total}, 有头像: {known}, 无头像: {total - known}')

# Show first 5 with avatars
with_av = [a for a in actors if a['has_avatar']][:10]
print('\n有头像的演员:')
for a in with_av:
    print(f'  {a["name"]} -> {a["local_url"]}')

# Show first 5 without avatars
without_av = [a for a in actors if not a['has_avatar']][:5]
print('\n无头像的演员 (前5):')
for a in without_av:
    print(f'  {a["name"]}')
