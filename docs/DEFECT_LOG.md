# MyMovieDB 缺陷记录

> 记录已修复的缺陷及代码习惯问题，防止重蹈覆辙。

---

## 🔴 缺陷 #1：FOUC — Vue 挂载前原始模板语法闪现

**严重程度**: 高
**首次发现**: 2026-04-05（长期存在，可能从开发初期就有）

### 现象
页面加载时，浏览器先显示原始 `{{ }}` 模板语法（如 `{{ t.msg }}`、`{{ scanResult.total_found }}`、`{{ selectedMovie.code }}`），然后这些文本消失，被 Vue 渲染的真实内容替换。

### 根本原因（Root Cause）

```
浏览器加载顺序：
1. 解析 HTML → 遇到 <div id="app"> 开始渲染 DOM
2. #app 内所有 {{ 变量 }} 作为普通文本显示 ← FOUC 发生点
3. 解析到 <script src="/vue.global.min.js"> → 浏览器请求 Vue CDN
4. Vue CDN 响应 → 执行 createApp().mount('#app')
5. Vue 编译模板，DOM 被正确替换 ← 问题消失
```

Vue 的 `{{ }}` 语法是 Vue 运行时编译器处理的，在 Vue.js 本身加载完成之前，浏览器完全不知道这些是模板语法，会当作普通文本来渲染。

**核心问题**：`#app` 在 CSS 中没有 `display: none`，导致 Vue 加载的"空白期"内，原始 HTML 被直接显示。

### 修复方案

**1. CSS 初始隐藏（防止浏览器渲染原始模板）**

```css
/* FOUC 防护：Vue 加载前隐藏 #app，防止 {{ }} 原始模板语法闪现 */
#app { display: none; }
#app.app-ready { display: block; }
```

**2. Vue 挂载后显示（安全时机）**

```javascript
}).mount('#app');
// Vue 挂载完成后显示 #app，触发 CSS .app-ready 规则
document.getElementById('app').classList.add('app-ready');
```

**3. Toast 容器额外保护（即使 CSS 失效仍有保障）**

```html
<!-- v-if="appMounted" 防止初始化时 {{ t.msg }} 闪现 -->
<div v-if="appMounted" class="toast-container">
    <div v-for="t in toasts" :key="t.id" class="toast" :class="t.type">{{ t.msg }}</div>
</div>
```

### 代码习惯问题（导致此缺陷未被及时发现）

| 问题 | 合理做法 |
|------|---------|
| **SPA 首屏完全依赖 CDN** | Vue 优先本地打包（Vite build），或确保 CSS 初始隐藏 |
| **appMounted 只保护部分组件** | 如果要保护，就全局统一保护，不要东一块西一块 |
| **开发时网络快 FOUC 不明显** | 用 Chrome 慢速网络模拟（DevTools → Network → throttling）测试 |

---

## 🔴 缺陷 #2：重复详情弹窗导致数据竞争

**严重程度**: 高
**首次发现**: 2026-04-05
**相关 commit**: `f0a4d21`（推测）

### 现象
电影详情页初始卡片卡在屏幕上，显示原始 `{{ selectedMovie.code }}` 等模板文本，不消失。

### 根本原因

`index.html` 中存在两个详情弹窗：
- **旧弹窗**（约 1479-1568 行）：`<div class="modal" v-if="selectedMovie">`
- **新弹窗**（约 1581 行起）：`<div class="modal-overlay" :class="{show: appMounted && selectedMovie}">`

旧弹窗的 `.modal` CSS 类**没有默认 `display: none`**，而新弹窗的 `.modal-overlay` 在 `appMounted=false` / `selectedMovie=null` 时不显示。两个弹窗同时存在于 DOM 中，旧弹窗在 Vue 编译完成前就以原始模板文本形式渲染出来。

### 修复方案
删除旧弹窗（约 90 行代码）。

### 代码习惯问题

| 问题 | 合理做法 |
|------|---------|
| **直接修改旧代码而不清理废弃代码** | 删除旧弹窗时务必清理干净，留下死代码是隐患 |
| **修改功能时没有检查全文件结构** | 每次修改前后用 `grep` 确认关键元素（如 `.modal`）是否唯一 |

---

## 🔴 缺陷 #3：头像文件名大小写 Bug

**严重程度**: 中
**首次发现**: 2026-04-01
**相关 commit**: 头像系统重构

### 现象
演员头像图片无法加载。

### 根本原因
- `quote()` 函数生成 URL 编码文件名（`%E4%B8%89%E4%B8%8A%E6%82%96...`）
- 实际文件保存时，Python 的 `open(path, 'wb')` 将 URL 编码文件名写入文件系统
- 但 Starlette 的 `StaticFiles` 对 URL 请求做 **URL decode**，查找 `/avatars/%E4%B8%89...` 时，文件系统中的文件名是 `%E6`（小写），而 URL 中的 `%E4`（大写）匹配不上

### 修复方案
改用演员**真实名字**作为文件名（如 `三上悠亜.jpg`），避开 URL 编码的大小写不一致问题。

### 代码习惯问题

| 问题 | 合理做法 |
|------|---------|
| **使用间接层（URL 编码）作为文件名** | 直接使用业务含义的名称（真实演员名），减少转换链路 |
| **没有意识到 URL decode 语义** | 涉及 URL 和文件系统交互时，测试大小写、空格、Unicode 全部场景 |

---

## 🟡 不合理代码习惯清单

### 1. 全局变量污染（避免）
```javascript
// ❌ 不好：全局停止控制器
let jellyfinAbortController = null;

// ✅ 好：封装在模块内或使用 WeakMap/闭包
const jellyfinController = new AbortController();
```

### 2. 魔法数字（避免）
```javascript
// ❌ 不好
scrapePanel.value.logs.splice(0, scrapePanel.value.logs.length);

// ✅ 好：使用语义化常量或数组方法
scrapePanel.value.logs.length = 0; // 或 clear()
```

### 3. 冗余/死代码（避免）
```javascript
// ❌ 不好：旧弹窗从未被使用，却留在代码库中
// <div class="modal" v-if="selectedMovie"> ... </div>

// ✅ 好：删除不用的代码，或用注释标注"TODO: 删除"
```

### 4. CSS 类名冲突风险（避免）
```javascript
// ❌ 不好：旧弹窗用 .modal，新弹窗用 .modal-overlay，容易混淆
.modal { /* 没有 display 控制 */ }

// ✅ 好：明确命名规范，如 .detail-modal-old / .detail-modal-overlay
```

### 5. 错误信息暴露内部实现（避免）
```javascript
// ❌ 不好：直接返回 str(e) 到 API 响应
raise HTTPException(status_code=500, detail=str(e))

// ✅ 好：通用消息 + exc_info=True 写入日志
raise HTTPException(status_code=500, detail="服务器内部错误")
logger.exception("API 错误")
```

### 6. 刮削优先级硬编码（避免）
```javascript
// ❌ 不好：优先级数字散落在代码中，无文档
if source['priority'] == 1: ...

// ✅ 好：使用 Enum 或配置常量
class ScraperPriority(Enum):
    DANZA = 1
    AVBASE = 2
```

### 7. replace_in_file 工具的双写字符问题（工具缺陷记录）
```javascript
// replace_in_file 工具有时会错误替换 || 和 =>
// 修改后务必用 node --check 验证 JS 语法
// 验证方式：提取 <script>...</script> 内容到临时文件，跑 node --check
```

---

## ✅ 开发规范（预防措施）

### 前端（Vue SPA）
1. **CSS 初始隐藏**：SPA 根元素必须有 `display: none` 初始样式，挂载后移除
2. **关键状态用 `appMounted` 保护**：`v-if="appMounted"` 包裹页面主体
3. **上线前慢速网络测试**：Chrome DevTools Network 设为 Slow 3G，确认无 FOUC
4. **修改弹窗/Modal 时用 `grep` 确认唯一性**：防止重复弹窗
5. **删除废弃代码**：每次功能重构后，用 `grep` 搜索关键 class/id 确认无残留

### 后端（FastAPI）
1. **API 错误脱敏**：所有 500 错误返回通用消息，细节写日志
2. **数据库修改后验证**：修改模型后用 `python -c "from backend.models import Movie; print('OK')"` 验证导入
3. **CDN 依赖检查**：确认外部 JS CDN 在目标网络可访问（内网环境可能无法访问）

### 通用
1. **每次修改后运行语法检查**：JS 用 `node --check`，Python 用 `python -m py_compile`
2. **Git 小步提交**：每个可独立运行的改动单独 commit，便于追溯
