with open(r'F:\github\MyMovieDB\frontend\index.html', encoding='utf-8') as f:
    content = f.read()

script = content[content.rfind('<script>')+8:]
lines = script.split('\n')

start = -1
end = -1
for i, l in enumerate(lines):
    if 'const organizeExecute' in l and 'scan' not in l:
        start = i
    if start >= 0 and i > start:
        if l.strip() == '};':
            end = i
            break

print('organizeExecute: lines', start+1, '-', end+1)

depth = 0
for i in range(start, end+1):
    line = lines[i]
    opens = line.count('{')
    closes = line.count('}')
    depth += opens
    print('%4d d=%2d %s' % (i+1, depth, line.rstrip()[:90]))
    depth -= closes
