# -*- coding: utf-8 -*-
"""
PyInstaller 打包配置
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# 收集依赖
datas = []
datas += collect_data_files('googletrans')
datas += collect_data_files('uvicorn')
datas += collect_data_files('starlette')
datas += collect_data_files('fastapi')
datas += collect_data_files('pydantic')
datas += collect_data_files('httpcore')
datas += collect_data_files('httpx')
datas += collect_data_files('anyio')
datas += collect_data_files('sniffio')
datas += collect_data_files('pystray')

# 隐藏导入
hiddenimports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.auto',
    'starlette',
    'fastapi',
    'pydantic',
    'pydantic.BaseModel',
    'httpcore',
    'httpx',
    'anyio',
    'sniffio',
    'googletrans',
    'pystray',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
]
