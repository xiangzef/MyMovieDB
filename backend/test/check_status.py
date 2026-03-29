import sqlite3

conn = sqlite3.connect('F:/github/MyMovieDB/data/movies.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 查询 scrape_status = complete 但可能缺少内容的影片
cursor.execute('''
    SELECT code, title, cover_url, actors, studio, release_date, scrape_status
    FROM movies
    WHERE scrape_status = 'complete'
    LIMIT 10
''')
rows = cursor.fetchall()

for row in rows:
    code = row['code']
    cover = bool(row['cover_url'])
    actors = row['actors'][:30] if row['actors'] else None
    studio = row['studio']
    date = row['release_date']
    status = row['scrape_status']
    print(f'{code}: cover={cover}, actors={actors}, studio={studio}, date={date}, status={status}')

conn.close()
