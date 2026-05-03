# Jellyfin 扫描测试脚本
# 用法：python scripts/test_jellyfin_scan.py [目录路径]

import sys
sys.path.insert(0, 'backend')

from jellyfin import scan_jellyfin_directory

def main():
    import os

    if len(sys.argv) > 1:
        test_dir = sys.argv[1]
    else:
        test_dir = r"Z:\影视库"

    print(f"测试扫描目录: {test_dir}")
    print("-" * 50)

    if not os.path.exists(test_dir):
        print(f"❌ 目录不存在: {test_dir}")
        return

    results = scan_jellyfin_directory(test_dir)

    print(f"\n✅ 扫描完成，找到 {len(results)} 个影片")

    if results:
        print("\n前 10 个影片:")
        for i, item in enumerate(results[:10]):
            print(f"\n{i+1}. {item['code']}")
            print(f"   视频: {os.path.basename(item['video_path'])}")
            print(f"   NFO: {os.path.basename(item['nfo_path']) if item['nfo_path'] else '❌ 无'}")
            print(f"   海报: {os.path.basename(item['poster_file']) if item['poster_file'] else '❌ 无'}")

        skipped = len(results) - 10
        if skipped > 0:
            print(f"\n... 还有 {skipped} 个影片未显示")

    # 统计
    nfo_count = sum(1 for r in results if r.get('nfo_path'))
    no_nfo_count = len(results) - nfo_count
    print(f"\n统计:")
    print(f"  有 NFO: {nfo_count}")
    print(f"  无 NFO: {no_nfo_count}")

if __name__ == "__main__":
    main()