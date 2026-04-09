import re

# 最终正则：去掉负前瞻，加数字前缀分支
_SUBTITLE_SUFFIX_RE = re.compile(
    r'^(?P<code>(?:'
    r'FC2-PPV-\d{5,7}|'                           # FC2-PPV-xxxxxx
    r'HEYDOUGA-\d{4}-\d{3,5}|'                    # HEYDOUGA-xxxx-xxxx
    r'[A-Z]{2,6}-\d{2,5}|'                        # 字母-数字（如 SSIS-157, VEC-769）
    r'\d[A-Z0-9]{1,5}-\d{2,5}'                    # 数字前缀-数字（如 390JNT-114）
    r'))'
    r'(?:[-.]?(?P<suffix>C|U|UC))?'                # 可选字幕后缀（支持 -C 或直接 C）
    r'(?:[.].+)?$',                               # 可选扩展名
    re.IGNORECASE
)

test_files = [
    ("390JNT-114.mp4",  "390JNT-114", None),
    ("VEC-769.mp4",     "VEC-769",    None),
    ("SSIS-157C.mp4",   "SSIS-157",   "C"),
    ("SSIS-157-C.mp4",  "SSIS-157",   "C"),
    ("JNT-001.mp4",     "JNT-001",    None),
    ("FC2-PPV-123456.mp4", "FC2-PPV-123456", None),
    ("WEBIPZZ-001.mp4", None, None),   # 不应匹配
]
print("测试结果:")
all_ok = True
for f, exp_code, exp_suf in test_files:
    m = _SUBTITLE_SUFFIX_RE.match(f)
    code = m.group('code') if m else None
    suf = m.group('suffix') if m and m.group('suffix') else None
    ok = (code == exp_code and suf == exp_suf)
    status = "✓" if ok else "✗"
    if not ok: all_ok = False
    print(f"  {status} {f:30} code={code or 'NO MATCH':20} suf={suf or '-':4}  期望: code={exp_code or 'NO'} suf={exp_suf or '-'}")
print("\n全部通过" if all_ok else "\n有失败项!")
