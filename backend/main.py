"""
FastAPI 主入口
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pathlib import Path
from typing import Optional
import logging
import threading
import re
import time

from models import (
    MovieResponse, MovieListResponse,
    ScrapeRequest, ScrapeResponse
)
from pydantic import BaseModel, Field
from typing import Optional, List
import database as db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化数据库
db.init_all_tables()

# 创建 FastAPI 应用
app = FastAPI(
    title="MyMovieDB API",
    description="本地影视库刮削器 API",
    version="1.0.0"
)

# 配置 CORS（允许前端访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境建议限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录（封面图）
data_dir = Path(__file__).parent.parent / "data"
data_dir.mkdir(parents=True, exist_ok=True)
covers_dir = data_dir / "covers"
covers_dir.mkdir(parents=True, exist_ok=True)
app.mount("/covers", StaticFiles(directory=str(covers_dir)), name="covers")


@app.get("/")
async def root():
    """API 根路径"""
    return {"message": "MyMovieDB API", "version": "1.0.0"}


@app.get("/movies", response_model=MovieListResponse)
async def get_movies(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    """获取影片列表"""
    total, movies = db.get_all_movies(page, page_size)
    
    # 转换数据格式
    items = []
    for movie in movies:
        movie = db.row_to_movie_response(movie)
        items.append(MovieResponse(**movie))
    
    return MovieListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )


@app.get("/movies/{movie_id}", response_model=MovieResponse)
async def get_movie(movie_id: int):
    """获取单个影片详情"""
    movie = db.get_movie_by_id(movie_id)
    
    if not movie:
        raise HTTPException(status_code=404, detail="影片不存在")
    
    movie = db.row_to_movie_response(movie)
    return MovieResponse(**movie)


@app.get("/movies/code/{code}", response_model=MovieResponse)
async def get_movie_by_code(code: str):
    """根据编号获取影片"""
    movie = db.get_movie_by_code(code)
    
    if not movie:
        raise HTTPException(status_code=404, detail="影片不存在")
    
    movie = db.row_to_movie_response(movie)
    return MovieResponse(**movie)


@app.get("/search")
async def search_movies(
    q: str = Query(..., description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    """搜索影片"""
    total, movies = db.search_movies(q, page, page_size)
    
    items = []
    for movie in movies:
        movie = db.row_to_movie_response(movie)
        items.append(MovieResponse(**movie))
    
    return MovieListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )


@app.post("/scrape", response_model=ScrapeResponse)
async def scrape_movie_endpoint(request: ScrapeRequest):
    """刮削影片信息（智能合并）"""
    from scraper import scrape_movie

    try:
        # 调用爬虫
        movie_data = scrape_movie(request.keyword, request.save_cover)

        if not movie_data:
            return ScrapeResponse(
                success=False,
                message=f"未找到影片: {request.keyword}"
            )

        # 检查本地库是否有该番号的视频
        local_video = db.get_local_video_by_code(request.keyword.strip())
        if local_video:
            movie_data["local_video_id"] = local_video["id"]

        # 使用 upsert：存在则智能合并，不存在则创建
        movie_id, is_new = db.upsert_movie(movie_data)

        # 如果本地库有关联，同步更新本地视频记录
        if local_video:
            db.mark_video_scraped(local_video["id"], movie_id)
            db.link_movie_to_local_video(movie_id, local_video["id"])

        movie = db.get_movie_by_id(movie_id)
        movie = db.row_to_movie_response(movie)

        if is_new:
            message = "刮削成功，新建记录"
        else:
            message = "影片已存在，智能更新完成"

        if local_video:
            message += f"（已关联本地: {local_video['name']}）"

        return ScrapeResponse(
            success=True,
            message=message,
            movie=MovieResponse(**movie)
        )

    except Exception as e:
        logger.error(f"刮削失败: {e}")
        return ScrapeResponse(
            success=False,
            message=f"刮削失败: {str(e)}"
        )


@app.delete("/movies/{movie_id}")
async def delete_movie(movie_id: int):
    """删除影片"""
    success = db.delete_movie(movie_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="影片不存在")
    
    return {"message": "删除成功"}


# ========== 本地视频源管理 API ==========

# 全局刮削停止标志（job_id -> stop_event）
_scrape_stop_flags: dict = {}
_scrape_lock = threading.Lock()


class LocalSourceCreate(BaseModel):
    path: str = Field(..., description="目录路径")
    name: Optional[str] = Field(None, description="显示名称")


class LocalVideoListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[dict]


# 番号正则：1-6位字母或数字 + 短横线 + 2-5位数字（不区分大小写，统一转为大写）
_CODE_PATTERN = re.compile(r'^([A-Za-z0-9]{1,6})-(\d{2,5})')


def _parse_codes(raw: str) -> list:
    """解析输入文本，返回有效番号列表（去重，保持顺序）"""
    raw = raw.strip()
    if not raw:
        return []
    # 支持逗号、空格、换行、分号、中英文逗号
    parts = re.split(r'[,，\s\n;；]+', raw)
    seen = set()
    codes = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # 尝试匹配番号
        m = _CODE_PATTERN.search(p.upper())
        if m:
            code = f"{m.group(1)}-{m.group(2)}"
            if code not in seen:
                seen.add(code)
                codes.append(code)
        else:
            # 尝试直接作为番号使用（不区分大小写，统一转大写）
            p = p.upper()
            if re.match(r'^[A-Z0-9]{1,6}-\d{2,5}$', p) and p not in seen:
                seen.add(p)
                codes.append(p)
    return codes


def _send_sse(data: dict) -> str:
    """生成 SSE data 行"""
    import json
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/scrape/batch", tags=["刮削"])
async def scrape_batch(req: ScrapeRequest):
    """
    批量刮削接口（支持 SSE 实时进度）
    请求体: { "keyword": "ABC-123, XYZ-456\nDEF-789", "save_cover": true }
    keyword 支持多番号，用逗号/空格/换行/分号分隔
    """
    from scraper import scrape_movie
    import uuid

    job_id = str(uuid.uuid4())[:8]
    stop_event = threading.Event()
    with _scrape_lock:
        _scrape_stop_flags[job_id] = stop_event

    codes = _parse_codes(req.keyword)
    if not codes:
        with _scrape_lock:
            _scrape_stop_flags.pop(job_id, None)
        return {"success": False, "message": "未识别到有效番号"}

    total = len(codes)

    def generate():
        success_count = 0
        fail_count = 0
        local_link_count = 0

        for i, code in enumerate(codes):
            # 检查停止标志
            if stop_event.is_set():
                yield _send_sse({
                    "type": "stopped",
                    "code": code,
                    "index": i + 1,
                    "total": total,
                    "message": "用户停止了刮削"
                })
                break

            # 发送当前处理信息
            yield _send_sse({
                "type": "scraping",
                "job_id": job_id,
                "code": code,
                "title": f"正在刮削 {code} ({i+1}/{total})...",
                "index": i + 1,
                "total": total,
                "pct": int((i / total) * 100)
            })

            # 检查本地库是否有该番号的视频
            local_video = db.get_local_video_by_code(code)
            local_video_id = local_video["id"] if local_video else None
            local_path = local_video.get("path") if local_video else None

            try:
                movie_data = scrape_movie(code, req.save_cover)
                if movie_data:
                    # 注入本地视频关联
                    if local_video_id:
                        movie_data["local_video_id"] = local_video_id
                    movie_id, is_new = db.upsert_movie(movie_data)
                    # 标记本地视频已刮削
                    if local_video_id:
                        db.mark_video_scraped(local_video_id, movie_id)
                        local_link_count += 1

                    yield _send_sse({
                        "type": "success",
                        "job_id": job_id,
                        "code": code,
                        "title": movie_data.get("title", ""),
                        "local_path": local_path,
                        "is_new": is_new,
                        "index": i + 1,
                        "total": total,
                        "pct": int(((i + 1) / total) * 100)
                    })
                    success_count += 1
                else:
                    yield _send_sse({
                        "type": "fail",
                        "job_id": job_id,
                        "code": code,
                        "message": "未找到影片信息",
                        "index": i + 1,
                        "total": total,
                        "pct": int(((i + 1) / total) * 100)
                    })
                    fail_count += 1

            except Exception as e:
                logger.error(f"刮削 {code} 失败: {e}")
                yield _send_sse({
                    "type": "error",
                    "job_id": job_id,
                    "code": code,
                    "message": str(e)[:100],
                    "index": i + 1,
                    "total": total,
                    "pct": int(((i + 1) / total) * 100)
                })
                fail_count += 1

            # 请求间隔
            time.sleep(0.5)

        # 完成
        yield _send_sse({
            "type": "done",
            "job_id": job_id,
            "processed": success_count + fail_count,
            "success_count": success_count,
            "fail_count": fail_count,
            "local_link_count": local_link_count,
            "total": total
        })

        # 清理
        with _scrape_lock:
            _scrape_stop_flags.pop(job_id, None)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no"
    }
    return StreamingResponse(generate(), media_type="text/event-stream", headers=headers)


@app.post("/scrape/stop", tags=["刮削"])
async def stop_scrape(req: dict = None):
    """停止指定 job_id 的刮削任务"""
    job_id = (req or {}).get("job_id") if req else None
    with _scrape_lock:
        if job_id and job_id in _scrape_stop_flags:
            _scrape_stop_flags[job_id].set()
            return {"success": True, "message": f"已发送停止信号: {job_id}"}
        elif job_id:
            return {"success": False, "message": f"任务不存在: {job_id}"}
        else:
            # 停止所有任务
            for ev in _scrape_stop_flags.values():
                ev.set()
            return {"success": True, "message": "已停止所有刮削任务"}


@app.post("/local-sources", tags=["本地视频"])
async def add_local_source(req: LocalSourceCreate):
    """添加本地视频源目录"""
    import os
    path = req.path.strip().rstrip('\\').rstrip('/')

    # 验证路径是否存在
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail=f"路径不存在或不是有效目录: {path}")

    source_id = db.create_local_source(path, req.name)
    if source_id is None:
        raise HTTPException(status_code=400, detail="该目录已添加")

    sources = db.get_local_sources()
    added = next((s for s in sources if s["id"] == source_id), None)
    return {"success": True, "source": added}


@app.get("/local-sources", tags=["本地视频"])
async def list_local_sources():
    """获取所有本地视频源"""
    sources = db.get_local_sources()
    stats = db.get_local_video_stats()
    return {"sources": sources, "stats": stats}


@app.delete("/local-sources/{source_id}", tags=["本地视频"])
async def remove_local_source(source_id: int):
    """删除本地视频源"""
    success = db.delete_local_source(source_id)
    if not success:
        raise HTTPException(status_code=404, detail="视频源不存在")
    return {"success": True, "message": "已删除"}


@app.post("/local-sources/scan", tags=["本地视频"])
async def scan_local_sources():
    """扫描所有已添加的目录，查找视频文件"""
    import os
    import re
    import threading
    import time

    # 视频扩展名
    VIDEO_EXTENSIONS = {
        '.mp4', '.mkv', '.avi', '.wmv', '.mov',
        '.flv', '.webm', '.m4v', '.mpg', '.mpeg',
        '.ts', '.mts', '.m2ts', '.vob', '.ogv'
    }

    # 编号提取正则：1-6位字母或数字 + 短横线 + 2-5位数字
    CODE_PATTERN = re.compile(r'^([A-Za-z0-9]{1,6})-(\d{2,5})')

    sources = db.get_local_sources()
    if not sources:
        return {"success": False, "message": "请先添加视频目录"}

    total_found = 0
    scan_results = []

    # 扫描前清理所有源的无番号旧记录
    db.cleanup_videos_without_code()

    for source in sources:
        source_id = source["id"]
        base_path = source["path"]
        found_count = 0

        if not os.path.isdir(base_path):
            scan_results.append({"source_id": source_id, "path": base_path, "status": "目录不存在", "count": 0})
            continue

        # 遍历目录（只扫描一级，不递归）
        try:
            for entry in os.scandir(base_path):
                if not entry.is_file():
                    continue

                filename = entry.name
                ext = os.path.splitext(filename)[1].lower()

                if ext not in VIDEO_EXTENSIONS:
                    continue

                # 提取编号
                code = None
                name_without_ext = os.path.splitext(filename)[0]

                match = CODE_PATTERN.search(name_without_ext)
                if match:
                    # 提取前缀和数字，统一转大写
                    prefix, number = match.groups()
                    code = f"{prefix.upper()}-{number}"

                try:
                    file_size = entry.stat().st_size
                except OSError:
                    file_size = 0

                # 只保存有番号的视频
                if not code:
                    continue

                video_data = {
                    "source_id": source_id,
                    "name": filename,
                    "path": entry.path,
                    "code": code,
                    "extension": ext,
                    "file_size": file_size,
                }

                vid_id, is_new = db.upsert_local_video(video_data)
                found_count += 1
                total_found += 1

        except PermissionError:
            scan_results.append({"source_id": source_id, "path": base_path, "status": "权限不足", "count": found_count})
            continue

        # 更新源的视频数量
        db.update_local_source_scan(source_id, found_count)
        scan_results.append({"source_id": source_id, "path": base_path, "status": "完成", "count": found_count})

    return {
        "success": True,
        "total_found": total_found,
        "results": scan_results,
        "stats": db.get_local_video_stats()
    }


@app.post("/local-sources/scrape", tags=["本地视频"])
async def scrape_local_videos():
    """对扫描到的本地视频批量刮削（只刮削有编号的）"""
    from scraper import scrape_movie
    import threading
    import time

    unscraped = db.get_unscraped_local_videos()
    if not unscraped:
        return {"success": True, "message": "没有需要刮削的视频", "processed": 0, "success_count": 0}

    success_count = 0
    fail_count = 0
    skip_count = 0
    results = []

    for video in unscraped:
        code = video.get("code")
        video_id = video["id"]

        if not code:
            skip_count += 1
            results.append({"video_id": video_id, "code": None, "status": "skip", "message": "无编号"})
            continue

        try:
            movie_data = scrape_movie(code, save_cover=True)
            if not movie_data:
                fail_count += 1
                results.append({"video_id": video_id, "code": code, "status": "fail", "message": "未找到"})
                continue

            # upsert 影片
            movie_id, is_new = db.upsert_movie(movie_data)
            # 关联本地视频：local_videos.movie_id 和 movies.local_video_id 双向关联
            db.mark_video_scraped(video_id, movie_id)
            db.link_movie_to_local_video(movie_id, video_id)
            success_count += 1
            results.append({"video_id": video_id, "code": code, "status": "success", "title": movie_data.get("title")})

            # 避免请求过快
            time.sleep(0.5)

        except Exception as e:
            logger.error(f"刮削 {code} 失败: {e}")
            fail_count += 1
            results.append({"video_id": video_id, "code": code, "status": "error", "message": str(e)[:100]})

    return {
        "success": True,
        "processed": len(unscraped),
        "success_count": success_count,
        "fail_count": fail_count,
        "skip_count": skip_count,
        "results": results,
        "stats": db.get_local_video_stats()
    }


@app.get("/local-videos", response_model=LocalVideoListResponse, tags=["本地视频"])
async def get_local_videos(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    source_id: int = Query(None, description="按视频源筛选"),
    scraped: int = Query(None, description="刮削状态: 0=未刮, 1=已刮"),
    keyword: str = Query(None, description="搜索文件名或编号")
):
    """获取本地视频列表"""
    total, items = db.get_local_videos(
        page=page,
        page_size=page_size,
        source_id=source_id,
        scraped=scraped,
        keyword=keyword
    )

    return LocalVideoListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )


@app.get("/local-videos/stats", tags=["本地视频"])
async def get_local_video_stats():
    """获取本地视频统计"""
    return db.get_local_video_stats()


@app.delete("/local-videos/{video_id}", tags=["本地视频"])
async def delete_local_video(video_id: int):
    """删除本地视频记录"""
    success = db.delete_local_video(video_id)
    if not success:
        raise HTTPException(status_code=404, detail="视频不存在")
    return {"success": True}
async def get_cover(filename: str):
    """获取封面图"""
    cover_path = covers_dir / filename
    
    if not cover_path.exists():
        raise HTTPException(status_code=404, detail="封面不存在")
    
    return {"url": f"/covers/{filename}"}


# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
