import re

# Current regex (anchored)
_SUBTITLE_SUFFIX_RE_ANCHORED = re.compile(
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

# New searching regex (non-anchored)
_SUBTITLE_SUFFIX_RE_SEARCH = re.compile(
    r'(?P<code>(?:'
    r'FC2-PPV-\d{5,7}|'
    r'HEYDOUGA-\d{4}-\d{3,5}|'
    r'[A-Z]{2,6}-\d{2,5}|'
    r'\d[A-Z0-9]{1,5}-\d{2,5}'
    r'))'
    r'(?:[-.]?(?P<suffix>C|U|UC))?'
    r'(?:[.].+)?',
    re.IGNORECASE
)

test_names = [
    '489155.com@SNOS-146.mp4',
    'xmmdh.net_SSIS-157C_1_1.mp4',
    '489155.com@VEC-769(1).mp4',
    'SNIS-001-C.mp4',
    'FC2-PPV-123456.mp4',
    'HEYDOUGA-2020-001.mp4',
    'SSIS-157.mp4',
    'IPZZ-792-C.mp4',
    'HEYDOUGA-2022-123-ABC.mp4',  # should NOT match (extra after code)
]

print("=== NEW SEARCHING regex ===")
for name in test_names:
    from pathlib import Path
    stem = Path(name).stem
    m = _SUBTITLE_SUFFIX_RE_SEARCH.search(stem)
    if m:
        print(f"'{name}' -> code={m.group('code')}, suffix={m.group('suffix')}")
    else:
        print(f"'{name}' -> NO MATCH")
