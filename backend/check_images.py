import sqlite3
conn = sqlite3.connect('F:/github/MyMovieDB/data/movies.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute('SELECT code, fanart_path, poster_path, thumb_path, cover_url FROM movies LIMIT 5')
rows = cursor.fetchall()
for row in rows:
    code = row['code']
    fanart = row['fanart_path']
    poster = row['poster_path']
    thumb = row['thumb_path']
    cover = row['cover_url']
    print(f'{code}:')
    print(f'  fanart: {fanart}')
    print(f'  poster: {poster}')
    print(f'  thumb: {thumb}')
    print(f'  cover_url: {cover[:50] if cover else None}')
conn.close()
