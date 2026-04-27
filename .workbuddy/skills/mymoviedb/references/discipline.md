# MyMovieDB 开发纪律手册

> 所有已踩过的坑、历史缺陷、代码规范和编程纪律的完整汇编。
> 每次出现新 Bug 或新规范，必须在此文件末尾追加记录。

---

## 一、HTML 结构规范（最高优先级）

### 🔴 规则 1：每次修改 HTML 必须验证 div 平衡

**工具**：项目根目录的 `check_html.js`
```bash
node c:/Users/Administrator/WorkBuddy/Claw/check_html.js
```

输出必须是：
```
div: open=X close=X net=0
JS braces: net=0
```

`net` 不为 0 = 页面必崩。

**操作清单**：
1. 新增一个 `<div>` 块，必须同一次修改内补上对应的 `</div>`
2. 移动 HTML 块时，**必须删除源位置所有开闭标签对**，不能只搬走开标签
3. 每次提交前运行一次验证
4. 写入后立刻验证，不等到发现问题再检查

### 🔴 规则 2：overlay/modal 不能嵌套在滚动容器内

`position:fixed` 的元素（整理浮层、详情弹窗等）必须放在 `<div class="container">` 的**同级最外层**，不能嵌套在有 `overflow:auto/scroll/hidden` 的父级内，否则会被裁剪，不可见。

```html
<!-- ✅ 正确：与 .container 平级 -->
<div class="container">...</div>
<div class="organize-overlay">...</div>
<div class="modal-overlay">...</div>

<!-- ❌ 错误：嵌套在滚动容器内 -->
<div class="container" style="overflow:auto">
    <div class="organize-overlay">...</div>  <!-- 被裁剪！-->
</div>
```

---

## 二、replace_in_file 工具陷阱（最高频 Bug）

### 🔴 规则 3：写入后必须验证缩进

`replace_in_file` 工具写入多行字符串时，**实际写入的缩进经常和 old_str 的缩进不一致**：
- old_str 显示 12sp，写入后变成 4sp 或 8sp
- 导致 JS 花括号/div 标签漂移，页面白屏崩溃

**防御策略**：
1. 写入前先用 `read_file` 确认当前文件的实际缩进
2. 写入后立刻运行 `node check_html.js` 验证 div 平衡
3. 大段 HTML 重写时，优先用 Python 脚本整体替换（`write_to_file`），而非逐段 `replace_in_file`
4. 不要相信 old_str 的缩进就等于文件实际缩进

### 🔴 规则 4：replace_in_file 不完整替换会留 JS 残骸

当 replace_in_file 只替换了函数的一部分时，旧代码片段可能残留在文件中。  
表现为：页面运行时出现"变量未定义"或"意外的 token"，但文件看起来有新代码。

**检查方法**：用 `search_content` 搜索被替换的函数名，确认只有一处定义。

---

## 三、Python 代码规范

### 🔴 规则 5：字典访问永远用 `.get()`，不用 `[]`

**原因**：数据库字段、视频文件字段、API 返回字段可能为 `None`，`[]` 访问会触发 `KeyError`。

```python
# ❌ 错误
code = f["code"]      # f["code"] 可能 None → AttributeError
actor = f["actors"][0]  # f["actors"] 可能 None → TypeError

# ✅ 正确
code = f.get("code")
if not code:
    return  # 早退出

actors = f.get("actors") or []
```

**所有函数入口都要做 None 检查**：
```python
def _emit_preview_item(f, movies_map, target_root, progress_callback):
    code = f.get("code")
    if not code:
        progress_callback(OrganizeProgress(event="found", reason="无法识别番号"))
        return
```

### 🔴 规则 6：SQLite INSERT 必须显式设置所有 NOT NULL 字段

**原因**：INSERT 漏写字段，SQLite 默认 NULL，下次查询时触发修复循环。

```python
# ✅ 正确：列出所有字段，显式设置默认值
INSERT INTO local_videos (
    source_id, video_path, code, is_jellyfin, name, extension, file_size
) VALUES (?, ?, ?, COALESCE(?, 0), ?, ?, COALESCE(?, 0))
```

特别注意：`is_jellyfin` 字段历史上多次因为 INSERT 漏写而变 NULL，必须显式设置。

### 🔴 规则 7：shutil 文件操作不加人工 timeout

**原因**：大文件（8GB+）通过 `shutil.copy2` 复制耗时正常（可能几分钟），加 timeout 是掩耳盗铃。

**规范**：
- 文件 I/O 操作（复制/移动）永远不设人工 timeout
- `await q.get()` 不传 timeout 参数，让流式事件自然完成
- 超时只用于**网络请求**（requests/aiohttp），不用于同步文件操作

### 🔴 规则 8：Python 语法验证必须在提交前运行

```bash
python -m py_compile backend/main.py
python -m py_compile backend/database.py
python -m py_compile backend/organizer.py
```

无输出 = 无语法错误。

---

## 四、SSE 流式接口规范

### 🔴 规则 9：用 Queue 模式，不用 Generator 模式

**错误模式（会导致 30s 超时）**：
```python
# ❌ 错误：Generator 模式，next(gen) 阻塞
async def generate():
    gen = organize_files_gen(request, ...)
    while True:
        item = await loop.run_in_executor(None, functools.partial(next, gen))
        yield make_sse(item)
```

**正确模式（Queue 模式）**：
```python
# ✅ 正确：Queue 解耦生产者和消费者
async def generate():
    q = asyncio.Queue()

    def progress_handler(p):
        data = p.model_dump(exclude_none=True)
        q.put_nowait((event_name, data))

    def run_sync():
        do_work(..., progress_callback=progress_handler)
        q.put_nowait((None, None))  # 结束信号

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, run_sync)

    while True:
        event_name, data = await q.get()  # 不设 timeout
        if event_name is None:
            break
        yield make_sse(event_name, data)

return StreamingResponse(generate(), media_type="text/event-stream")
```

### 🔴 规则 10：扫描必须流式推送，不等全部完成

**错误模式**：
```python
# ❌ 错误：等全部扫描完才推送
files = scan_video_files(source_paths)  # 阻塞 30s+
for f in files:
    yield OrganizeProgress(...)  # 太晚了
```

**正确模式**：
```python
# ✅ 正确：每找到一个文件立即推送
for item in scan_video_files_gen(source_paths):
    progress_callback(OrganizeProgress(event="found", ...))  # 实时推送
```

---

## 五、Vue 前端规范

### 🔴 规则 11：FOUC 防护（Vue 挂载前隐藏页面）

所有 `{{ }}` 模板语法在 Vue 加载前会被浏览器显示为原始文本。

**必须的防护**：
```css
/* CSS 初始隐藏 */
#app { display: none; }
#app.app-ready { display: block; }
```

```javascript
// Vue 挂载后显示
}).mount('#app');
document.getElementById('app').classList.add('app-ready');
```

Toast 容器额外保护：
```html
<div v-if="appMounted" class="toast-container">
    <div v-for="t in toasts">{{ t.msg }}</div>
</div>
```

### 🔴 规则 12：SSE EventSource 必须防抖/节流

大量 SSE 事件（每找到一个文件就发一条）直接更新 DOM 会导致 UI 卡顿。

```javascript
// 用 throttle 限制更新频率（每 100ms 最多更新一次）
let lastUpdateTime = 0;
function throttledUpdate(fn) {
    const now = Date.now();
    if (now - lastUpdateTime > 100) {
        fn();
        lastUpdateTime = now;
    }
}
```

### 🔴 规则 13：Vue ref 嵌套对象初始化要完整

```javascript
// ✅ 正确：初始化所有嵌套字段
const organizePanel = ref({
    show: false,
    mode: '',
    label: '',
    logs: [],
    pct: 0,
    currentFile: '',
    stats: { found: 0, moved: 0, copied: 0, skipped: 0, fail: 0, cleanup: 0 }
});

// 每次打开面板时也要重置 currentFile
organizePanel.value.currentFile = '';
organizePanel.value.stats = { found: 0, moved: 0, copied: 0, skipped: 0, fail: 0, cleanup: 0 };
```

### 规则 14：JS 语法验证

提交前检查 JS 是否有语法错误：
```bash
node check_html.js  # 同时检查 JS 花括号平衡
```

如果花括号 net ≠ 0，说明 replace_in_file 写入了损坏的代码。

---

## 六、番号识别规范

### 规则 15：番号识别四级优先级顺序

`organizer.py` 的 `_CODE_PATTERNS` 按以下优先级匹配（不能颠倒）：

```python
1. FC2PPV: r'\b(FC2[-_]?PPV[-_]?\d{5,9})\b'
   → FC2PPV1234567, FC2-PPV-123456

2. 数字前缀系列: r'\b(\d{3}[A-Z]{2,6}[-_]?\d{2,5})\b'
   → 300MIUM-746, 390JAC-123

3. 标准带连字符: r'\b([A-Z]{2,6}-\d{2,5})\b'
   → CAWD-285, SSIS-196（优先匹配）

4. 无连字符（次优先）: r'\b([A-Z]{2,6})(\d{3,5})\b'
   → IPX722 → 补连字符 → IPX-722
```

### 规则 16：字幕后缀处理顺序不能颠倒

`_extract_code_with_suffix` 的处理顺序是硬性要求：

```
❌ 错误顺序：先剥多盘标识 → 再剥字幕后缀（CAWD-285-C-A 会误判）

✅ 正确顺序：
  Step1: 剥字幕后缀（优先级 -UC > -U > -C，不区分大小写）
  Step2: 剥多盘标识（-A/-B；如 Step1 未消耗 -C，则末尾 -C 是多盘 C 盘）
  Step3: 调用 _extract_code() 提取番号
```

**验证用例**：
- `CAWD-285-C.mp4` → code=CAWD-285, subtitle=chinese, disc=""
- `CAWD-285-A.mp4` → code=CAWD-285, subtitle=none, disc="A"
- `CAWD-285-C-A.mp4` → code=CAWD-285, subtitle=chinese, disc="A"
- `CAWD-285-UC.mp4` → code=CAWD-285, subtitle=bilingual, disc=""

### 规则 17：垃圾前缀清洗

文件名可能带域名水印（`amav.xyz-`、`bbsxv.xyz-`）或中文括号前缀（`【ses23.com】`）。

`_strip_garbage_prefix` 函数会自动清洗，但注意：
- 清洗后匹配失败时，也要对原始名字再尝试一次（覆盖无分隔符粘连的情况）
- 清洗结果不能缓存，因为同一名字可能在不同上下文中有不同的前缀

---

## 七、Git 提交规范

### 规则 18：提交前检查清单

```
□ node check_html.js → div net=0，JS braces net=0
□ python -m py_compile backend/*.py → 无 SyntaxError
□ git status → 确认改动范围，只提交相关文件
□ 测试文件在 tests/ 目录，不在根目录
□ commit message 写清楚"修复了什么"和"为什么"
```

### 规则 19：双远程推送

本项目维护 GitHub 和 Gitee 双远端：
```bash
git push origin main   # GitHub
git push gitee main    # Gitee
```

---

## 八、历史缺陷记录

> 完整记录所有已出现的 Bug，防止重蹈覆辙。

| 日期 | 缺陷标题 | 根本原因 | 修复方案 |
|------|---------|---------|---------|
| 2026-04-01 | 头像文件名大小写 Bug | `quote()` 生成大写 URL 编码，Starlette StaticFiles decode 后找不到小写文件 | 改用演员真实名字作文件名 |
| 2026-04-03 | StaticFiles URL decode 问题 | StaticFiles 会 decode URL，文件名必须是真实字符 | 重构头像系统为真实名字 |
| 2026-04-04 | 番号识别贪婪 Bug | `[A-Z0-9]+` 吃掉不属于番号的数字 | 改为 `[A-Z0-9]*[A-Z]` |
| 2026-04-04 | organize/preview SSE StopIteration | `next(gen)` 未包装，Generator 耗尽时异常逃逸 | `functools.partial(next, gen)` |
| 2026-04-05 | 前端 Vue 白屏 | `onMounted(async () =>` 被 replace_in_file 错误 HTML 实体编码为 `=>` | `=>` 不编码 |
| 2026-04-05 | FOUC 模板语法闪现 | `#app` 无初始隐藏，Vue 加载空白期原始 `{{ }}` 被显示 | `#app { display:none }` + `app-ready` 类 |
| 2026-04-05 | 重复详情弹窗 | 旧弹窗（`.modal`）和新弹窗（`.modal-overlay`）同时存在 DOM | 删除旧弹窗 90 行代码 |
| 2026-04-11 | 每次启动修复 45 条 NULL | INSERT 未显式设置 is_jellyfin 导致持续为 NULL | 加 `COALESCE(?, 0)` |
| 2026-04-11 | 整理 30s 超时 | 两个 Generator 混用 + 每次迭代固定 30s wait | 改用 Queue 模式 + 无 timeout |
| 2026-04-11 | preview 卡住 | `scan_video_files` 批量扫描完才返回，阻塞 SSE | 改用 `scan_video_files_gen` 流式扫描 |
| 2026-04-11 | code=None 崩溃 | `f["code"]` 在无法识别番号时为 None 触发 AttributeError | `.get("code")` + None 早退出 |
| 2026-04-12 | JS 白屏闪回 | replace_in_file 写函数体缩进错误（4sp vs 12sp） | 写入后立刻运行 `check_html.js` |
| 2026-04-12 | organize overlay 不显示 | 整理浮层嵌套在 `overflow:auto` 父级内被裁剪 | 移到 `.container` 同级 |
| 2026-04-12 | 多余 `</div>` 导致乱码 | 移动 HTML 块时残留闭合标签，div 不平衡 | 删除多余标签，验证 div balance |
| 2026-04-13 | is_jellyfin 401/4/4 每次循环 | Step1 用 `IS NOT` 子查询虚高 rowcount；CaseB 覆盖双目录电影的 CaseA 结果 | Step1 用 `COALESCE!=` 精确比较 + 排除孤立行；CaseB 排除双目录电影 |
| 2026-04-13 | 前端整理页崩溃 | JS 残骸代码（replace_in_file 未完整替换）+ div 未闭合 | 删 JS 残骸，补 `</div>` 关闭 `#app` |
| 2026-04-13 | 大量"无法识别番号" | RE_CODE 只匹配行首，文件名有垃圾域名前缀（`amav.xyz-` 等） | 新增 `_strip_garbage_prefix` + 4 级正则 + 无连字符自动补 `-` |
| 2026-04-13 | 文件夹命名带 `[_楓ふうあ_]` 方括号 | `_safe_dir_name` 未去方括号 | 加 `re.sub` 去 `[]`，strip 前后 `_` |
| 2026-04-13 | 前端日志全是 undefined | `item.source_path` 为 undefined 时 `.split()` 崩溃 | `(item.source_path || '').split()` 兜底 |
| 2026-04-27 | 整理执行卡住（TypeError） | `_update_jellyfin_scan_record` 定义 7 个参数，调用时只传 3 个 | 补全所有 7 个参数（含 movie_id/new_video_path/new_name/new_extension） |

---

## 九、代码习惯问题（不合理习惯汇总）

### ❌ 应避免的习惯

| 习惯 | 合理做法 |
|---|---|
| 全局变量污染 | 封装在模块内或使用闭包 |
| 魔法数字（如 splice(0, 999)）| 使用语义常量或 `.length = 0` |
| 冗余/死代码留存 | 功能重构后立即删除废弃代码 |
| CSS 类名无规范（.modal vs .modal-overlay）| 明确命名规范，避免混淆 |
| 500 错误返回 `str(e)` 暴露内部信息 | 通用消息 + `logger.exception()` 写日志 |
| 刮削优先级硬编码数字 | 使用 Enum 或配置常量 |
| 数据库修改未验证 | `python -m py_compile` + import 测试 |
| 测试文件放根目录 | 必须放 `tests/` 目录 |
| CDN 依赖未考虑内网环境 | 提供本地 fallback 或确保 CDN 可访问 |
| 直接 `import` 无防御 | 可能失败的 import 用 try/except 包裹 |

### ✅ 推荐做法

```python
# 防御性 import
try:
    from translator import JapaneseVideoTranslator
except ImportError:
    JapaneseVideoTranslator = None

# 错误处理
raise HTTPException(status_code=500, detail="服务器内部错误")
logger.exception("实际错误信息")  # 写日志，不暴露给客户端

# 类型安全 ID
from typing import Optional
def get_movie(movie_id: int) -> Optional[MovieResponse]:
    ...
```

---

## 十、测试规范

> 规范：用户亲自测试，AI 不自行运行测试。AI 只负责写测试文件，由用户手动执行。

```bash
# 用户执行测试
python -m pytest tests/ -v
python tests/test_scraper.py
```

测试文件命名规范：`tests/test_{模块名}.py`

---

## 十一、整理功能（Phase 0.5）专项规范

### 文件整理目标结构

```
{target_root}\
  {演员名}\
    {番号}\
      {番号}[-C|-U|-UC][-A|-B|-C].{ext}   ← 视频文件
      {番号}.nfo                            ← NFO 文件
      {番号}-poster.jpg
      {番号}-fanart.jpg
      {番号}-thumb.jpg
```

### 字幕后缀规范

| 后缀 | subtitle_type | 含义 |
|---|---|---|
| 无后缀 | none | 无字幕 |
| `-C` | chinese | 中文字幕 |
| `-U` | english | 无马赛克（英文/去码）|
| `-UC` | bilingual | 无马赛克 + 中文字幕 |

后缀不区分大小写，`-c`/`-C`/`-uc`/`-UC` 都识别。

### 多盘标识规范

| 后缀 | 含义 |
|---|---|
| `-A` | A 盘（第一部分）|
| `-B` | B 盘（第二部分）|
| `-C` | C 盘（第三部分，与字幕后缀同符号，靠处理顺序区分）|

### 源文件夹清理规范

整理（移动）完成后，检查源文件夹是否可安全删除：

**可删除条件**：
- 空文件夹
- 只剩 `.torrent`/`.url`/`.txt`/`.lnk` 等垃圾文件
- 只剩图片文件（封面/广告图）且无视频
- 只剩 `.nfo` 文件且无视频

**不可删除条件**：
- 仍有视频文件（可能是其他番号）
- 含子目录
- 含无法识别类型的文件

**不以文件大小作为判据**（小视频片段可能是正常内容）

### Jellyfin 同步规范

整理完成后，检查目标目录是否在 `local_sources` 表的 Jellyfin 目录下：

```python
# _update_jellyfin_scan_record 调用链
1. 查询 local_sources WHERE is_jellyfin=1，找到 target_dir 对应的 source
2. 调用 db.sync_local_video_after_organize(movie_id, new_video_path, ...)
3. sync 函数会 upsert local_videos 记录，设置 is_jellyfin=1
4. 同时更新 movies.source_type='jellyfin'
5. 发送 jellyfin_updated SSE 事件通知前端
```

**注意**：`_update_jellyfin_scan_record` 函数签名需要 7 个参数，调用时必须全部传入：
```python
_update_jellyfin_scan_record(
    target_dir=target_dir,
    code=f["code"],
    movie_id=movie_id,          # 必须！从 movies_map 获取
    new_video_path=target_file,  # 必须！整理后的完整路径
    new_name=Path(target_file).stem,
    new_extension=Path(target_file).suffix.lstrip("."),
    progress_callback=progress_callback,
)
```

---

## 十二、数据库安全规范

### 规则：向后兼容 ALTER TABLE

新增数据库字段不能直接 `CREATE TABLE`，必须：
1. `CREATE TABLE IF NOT EXISTS`（建表时含所有字段）
2. 用 `PRAGMA table_info(表名)` 查询现有列
3. 对新字段执行 `ALTER TABLE ADD COLUMN ... IF NOT EXISTS`（SQLite 需用 try/except）

```python
existing_columns = [col[1] for col in cursor.execute("PRAGMA table_info(movies)")]
if "new_field" not in existing_columns:
    try:
        cursor.execute("ALTER TABLE movies ADD COLUMN new_field TEXT")
    except Exception:
        pass  # 已存在则忽略
```

### 规则：事务安全

批量操作必须在事务内：
```python
conn = get_db()
cursor = conn.cursor()
try:
    # 批量操作
    conn.commit()
except Exception:
    conn.rollback()
    raise
finally:
    conn.close()
```
