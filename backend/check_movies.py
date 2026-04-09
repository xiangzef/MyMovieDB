import sqlite3, json
conn = sqlite3.connect('F:/github/MyMovieDB/backend/data/movies.db')
cur = conn.cursor()

test_codes = [
    ('SNOS-146', '489155.com@SNOS-146'),
    ('VEC-769', '489155.com@VEC-769(1)'),
    ('SSIS-157', 'xmmdh.net_SSIS-157C_1_1'),
]

for code, orig_name in test_codes:
    cur.execute('SELECT code, title, actors FROM movies WHERE code=?', (code,))
    r = cur.fetchone()
    if r:
        code_db, title, actors = r
        print(f"FOUND: {code} -> title={title}")
        try:
            print(f"  actors: {json.loads(actors)}")
        except:
            print(f"  actors raw: {repr(actors)}")
    else:
        # Try LIKE
        cur.execute('SELECT code, title, actors FROM movies WHERE code LIKE ?', (f'%{code}%',))
        r2 = cur.fetchall()
        print(f"NOT FOUND: {code} (from '{orig_name}')")
        if r2:
            for r in r2:
                print(f"  LIKE match: {r[0]} - {r[1]}")
        else:
            print(f"  NO LIKE MATCH either")

# Also check what the regex extracts from each filename
import re
_SUBTITLE_SUFFIX_RE = re.compile(
    r'^(?P<code>(?:'
    r'FC2-PPV-\d{5,7}|'
    r'HEYDOUGA-\d{4}-\d{3,5}|'
    r'[A-Z]{2,6}-\d{2,5}|'
    r'\d[A-Z0-9]{1,5}-\d{2,5}'
    r'))'
    r'(?:[-.]?(?P<suffix>C|U|UC))?'
    r'(?:[.].+)?$',
    re.IGNORECASE
)

print("\n=== Regex extraction from filenames ===")
for name in ['489155.com@SNOS-146', '489155.com@VEC-769(1)', 'xmmdh.net_SSIS-157C_1_1']:
    stem = name.rsplit('.', 1)[0]
    m = _SUBTITLE_SUFFIX_RE.match(stem)
    if m:
        print(f"'{name}' -> code={m.group('code')}, suffix={m.group('suffix')}")
    else:
        print(f"'{name}' -> NO MATCH (stem='{stem}')")

conn.close()
