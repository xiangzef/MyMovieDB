from PIL import Image
from pathlib import Path
from scraper import _crop_poster_from_right

# 测试 fanart
covers_dir = Path("F:/github/MyMovieDB/data/covers")
fanart_file = covers_dir / "SSIS-254" / "SSIS-254-fanart.jpg"

if fanart_file.exists():
    fanart = Image.open(fanart_file)
    print(f"原始 fanart 尺寸: {fanart.size}")
    
    # 测试裁切函数
    poster = _crop_poster_from_right(fanart, 1000, 1500)
    print(f"裁切后 poster 尺寸: {poster.size}")
    print(f"宽高比: {poster.size[0] / poster.size[1]:.3f} (目标 2:3 ≈ 0.667)")
    
    # 保存测试结果
    test_output = covers_dir / "SSIS-254" / "test-poster.jpg"
    poster.convert("RGB").save(test_output, "JPEG", quality=90)
    print(f"\n测试 poster 已保存: {test_output}")
else:
    print("fanart 文件不存在")
