# -*- coding: utf-8 -*-
"""创建程序图标"""
from PIL import Image, ImageDraw

# 创建一个 64x64 的图标
img = Image.new('RGB', (64, 64), color=(30, 30, 50))
draw = ImageDraw.Draw(img)

# 画一个电影胶片风格的图标
draw.rectangle([10, 15, 54, 49], outline=(255, 200, 50), width=2)

# 胶片孔
for x in [18, 26, 34, 42, 50]:
    draw.rectangle([x, 18, x+3, 23], fill=(255, 200, 50))
    draw.rectangle([x, 41, x+3, 46], fill=(255, 200, 50))

# 播放符号
draw.polygon([(25, 28), (25, 38), (38, 33)], fill=(255, 200, 50))

# 保存为 ICO 格式
img.save('icon.ico', format='ICO')
print('图标创建成功: icon.ico')
