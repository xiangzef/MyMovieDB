with open('index.html','r',encoding='utf-8') as f:
    lines = f.readlines()

stack = []
for i in range(1210, 1340):
    l = lines[i]
    stripped = l.lstrip()
    indent = len(l) - len(stripped)
    raw = stripped[:60]
    if stripped.startswith('</div>'):
        if stack:
            open_l, open_indent, open_tag = stack.pop()
            print(f'CLOSE {i+1}({indent}) -> OPEN {open_l+1}({open_indent}): {open_tag[:40]}')
        else:
            print(f'CLOSE {i+1}({indent}) -> STACK EMPTY')
    elif stripped.startswith('<div'):
        stack.append((i, indent, stripped[:60]))
