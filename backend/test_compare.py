import database
from gfriends import get_local_avatar_url

# Get all actors via the original function
t, actors = database.get_actor_stats(page=1, page_size=10000)
old_no_avatar = [a['name'] for a in actors if not a['has_avatar']]
print(f'旧函数: {len(old_no_avatar)} 个无头像')

# Get via new optimized function
t2, actors2 = database.get_actors_without_avatars()
new_no_avatar = [a['name'] for a in actors2]
print(f'新函数: {len(new_no_avatar)} 个无头像')

# Diff
old_set = set(old_no_avatar)
new_set = set(new_no_avatar)
print('旧有新无:', old_set - new_set)
print('新有旧无:', new_set - old_set)
