"""番号识别测试脚本"""
import sys
sys.path.insert(0, '.')

# 导入函数
from main import _extract_code_from_filename, SPECIAL_CODE_PATTERNS

# 测试用例: (文件名, 期望结果, 说明)
test_cases = [
    # 正常番号
    ("IPZZ-792", "IPZZ-792", "标准番号"),
    ("GQN-011", "GQN-11", "标准番号（去掉前导零）"),
    ("JNT-114", "JNT-114", "素人番号"),
    ("ABC-123", "ABC-123", "标准番号（通用前缀）"),
    
    # 前缀排除问题
    ("390JNT-114", "JNT-114", "排除390前缀（数字+字母混合）"),
    ("WEBIPZZ-792", None, "排除WEB混合前缀"),
    ("HDABC-123", None, "排除HD混合前缀"),
    ("WEBABC-456", None, "排除WEB混合前缀"),
    ("1080PXYZ-999", None, "排除1080P混合前缀"),
    
    # 带空格的
    ("1080P XYZ-999", "XYZ-999", "排除1080P前缀"),
    
    # 非AV文件
    ("Avengers.Endgame.2019", None, "普通电影"),
    ("La.La.Land.2016", None, "普通电影"),
    ("Movie.2023.1080p", None, "普通电影"),
    ("Breaking.Bad.S05.720p", None, "美剧"),
    
    # 带其他字符的
    ("ABC-123_test", "ABC-123", "忽略后缀"),
    ("test XYZ-456 video", "XYZ-456", "中间识别"),
    ("IPZZ-792.1080p", "IPZZ-792", "忽略分辨率后缀"),
    
    # 下划线分隔的（不识别，因为正则要求短横线）
    ("ABC_123", None, "下划线分隔，不识别"),
    
    # FC2系列
    ("FC2-PPV-123456", "FC2-PPV-123456", "FC2-PPV番号"),
    ("fc2-ppv-789012", "FC2-PPV-789012", "FC2-PPV番号（小写）"),
    
    # HEYDOUGA系列
    ("HEYDOUGA-1234-567", "HEYDOUGA-1234-567", "HEYDOUGA番号"),
]

print("=== 番号识别测试 ===")
print()
print(f"特殊番号模式数量: {len(SPECIAL_CODE_PATTERNS)}")
for i, pattern in enumerate(SPECIAL_CODE_PATTERNS):
    print(f"  模式{i+1}: {pattern.pattern}")
print()

passed = 0
failed = 0

for filename, expected, desc in test_cases:
    result = _extract_code_from_filename(filename)
    status = "PASS" if result == expected else "FAIL"
    
    if status == "PASS":
        passed += 1
    else:
        failed += 1
    
    result_str = result if result else "(None)"
    expected_str = expected if expected else "(None)"
    print(f"[{status}] {filename:30} -> {result_str:20} | {desc}")

print()
print(f"=== 结果: {passed} 通过, {failed} 失败 ===")
