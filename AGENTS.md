# AGENTS.md — CQUPTDDL（重邮聚合截止线）后端

给 AI/新人的跨会话速查手册。先读这里，别再从零探索。约 4k 行 Python，全部代码在 `src/cquptddl/`。

## 1. 项目是什么

聚合 **学在重邮 / 学习通 / 雨课堂** 三平台的作业，提供 REST API；可选把作业同步为 **Meet课程表** 事件，并通过 QQ 机器人（qqchan）推送临期/新作业提醒。

- Python **>=3.14**（用到 `uuid7`、`itertools.batched`），包管理 **uv**。
- 入口：`cquptddl:main` → `uvicorn cquptddl:app`（见 `src/cquptddl/__init__.py`）。
- 运行：`uv run cquptddl`；依赖装到 `.venv/`（含 `uvicorn`、`dotenv` 等可执行文件）。
- **无项目级 lint/类型检查配置**（`pyproject.toml` 里没有 ruff/ty 段，也没有 `ruff.toml`/`ty.toml`），但开发者**全局安装了 `ty` 与 `ruff`**，改动后必须用它们检查（见 §7）。`tests/` **是空目录**，无任何测试；dev 依赖只有 `aiosqlite`、`respx`（`uv.lock` 里没有 pytest），目前也未被任何代码使用。
- `README.md` 是空文件。分支：当前 `v2`（开发分支），`master` 落后于 `v2`；远端 `git@github.com:marton0710/CQUPTDDL.git`。
- 部署：`Dockerfile` 用 python:3.14-alpine，从自建源 `pypi.bail.asia` 装包，前端目录挂到 `/fe`（`FRONTEND_DIR`），暴露 8000。

## 2. 架构骨架（务必先理解这 4 个机制）

### 2.1 依赖注入：`core.factory`
- `core.depends_session` / `depends_client`：FastAPI 依赖，交出 session/client。
- `core.get_session()` / `get_client()`：把上面两个包成 `asynccontextmanager`，**给非路由代码（事件回调、后台任务）用**。
- `depends_session` 在 `yield` **之后** `commit()`。所以路由里不 commit 也会落库；但后台任务用 `get_session()` 时同样会自动 commit —— 不要让同一 session 并发。
- `depends_client` 自动加 `User-Agent: CQUPTDDL/<版本>`，传 `headers=` 时是合并而非覆盖。

### 2.2 符号表 `core.symbol`：服务层解耦层
`core.export("名字", 函数)` / `core.call("名字", *args)`。**跨 service 调用一律走符号表**，不直接 import 别的 service。
全部导出名（grep `core.symbol.export` / `core.export` 可复核）：
- `auth.*`：`password_login`、`get_login_qrcode`、`qrcode_login`、`relogin`、`get_user_from_token`、`refresh_token`、`logout`、`delete_account`
- `crypto.aes_encrypt` / `crypto.aes_decrypt`
- `platform.get_auth_method` / `bind` / `unbind` / `valid_cookie` / `fetch_homework`
- `homework.refresh_homework` / `complete` / `get_cached_homework` / `get_cached_homework_count` / `get_last_refresh_time` / `get_user_dying_homeworks` / `get_user_homeworks_with_deadline`
- `qqpush.configure` / `get_user_config_from_qqchan_id` / `push_dying_homeworks`
- `meetschedule.bind` / `unbind`
⚠️ 名字重复 `export` 会抛 `NameError`；改函数名要同步改 `call()` 里的字符串（无类型检查兜底）。

### 2.3 事件总线 `core.bus`（abxbus）
模块**导入时**注册 `core.bus.on(Event, handler)`，靠 `service/__init__.py` 里 `from . import ...` 触发注册 —— **新增 service 模块必须在 `service/__init__.py` 导入**，否则事件不生效。
事件定义全在 `model/event/__init__.py`：`UserRegisterEvent`（建 `QQPushConfig`）、`UserReloginRequiredEvent`、`HomeworkRefreshedEvent`（带 `new_homework_ids`）、`HomeworkDoneEvent`、`PlatformBound/Unbound`（增删刷新 job + 删作业）、`AutoRefreshHomeworkFailedEvent`、`AccountDeletedEvent`、`QQPushConfigChangedEvent`、`InvalidQQChanIDEvent`。

### 2.4 后台任务
- `core/task.background(coro, name)` 立即跑；`register()` + 启动后 `task.start()` 用于事件循环前注册。
- APScheduler 三处：`homework/refresh_task.scheduler`（按平台间隔刷新作业，job id `homework_fetch_schedule_{uid}_{platform}`，间隔 `homework_cache_base_ttl`+jitter）、`qqpush/globals.scheduler`（推送策略）、`meetschedule/refresh_task.scheduler`（同步）。
- 生命周期：`cquptddl/__init__.py:lifespan` → `core.init()`（建表 + 启 task）→ `service.init()`（建刷新 job、qqpush on_boot、meetschedule start_refresh）；关闭顺序相反。

## 3. 目录职责

```
core/       config(pydantic-settings 读 .env) / db(engine+建表) / factory / event_bus / task / symbol
model/db/   SQLModel 表：User, Homework, PlatformInfo, QQPushConfig, MeetscheduleConfig, MeetscheduleEntry
model/schema/  pydantic API 模型与枚举（PlatformEnum、AuthMethod）
model/event/   事件定义
router/api/ FastAPI 路由：auth / homework / platform / qqpush / meetscheule(拼写如此)
middleware/ need_login(token Cookie) / verify_api_key(X-API-Key)
service/    auth, crypto, homework, platform, qqpush, meetschedule
exc.py      所有业务异常（继承 HTTPException，带 status/detail）
```
注意：`model/db/__init__.py` 的 `__all__` 里 `LastRefreshTime`、`PlatformCookies` **已不存在**，是历史残留。

## 4. 关键数据模型

- **User**：主键 `id` = 真实统一认证码；`password` 为 AES 密文（扫码登录为 `None`）；`token_version: UUID` 用于退出登录时批量失效 token。
- **Homework**：主键 `id = uuid5(NAMESPACE, user_id + platform + <平台自定义串>)`。⚠️ `generate_id` 第二/三参含义**因平台而异**：学在重邮传 `course_name, title`，学习通传 `course_name, title`，雨课堂分别传 `str(item["id"])` 或 `course_name, title`。**改这个函数等于改所有作业主键，会导致作业重复入库**，除非同时写数据迁移。
- **PlatformInfo**：主键 `(user_id, platform)`；`credentials` 是 AES 密文 JSON；`last_refreshed_homework` 兼作**冷却计时**（`_check_platform_cooldown` 直接改它）。
- **MeetscheduleEntry**：主键 = `homework.id`（外键到 homework）；`status` 走 `pending → pending-update / pending-delete → success` 状态机。
- **PlatformEnum** 的枚举**值就是中文名**（`"学在重邮"`/`"学习通"`/`"雨课堂"`），API 路径参数也用它。

## 5. 各业务要点

### auth（登录）
- 统一认证走 `fuckids` 库：`password_login_async` / `get_qrcode_async` / `qrcode_login_async`。
- **二维码会话存在进程内内存字典** `service/auth/ids.py:_qrcode_login_sessions`，多 worker 会失效；过期会话由 `_clear_expired_qrlogin_session()` 惰性清理（TTL=`qr_login_session_ttl`）。**不要退回成无界增长**（曾经是 bug）。二维码未扫描时返回 202（`QRCodeNotScanned`）。
- JWT：uid 先 AES 加密再进 payload，`isrefresh` 区分 access/refresh，校验时比对 `token_version`。cookie：`token`（httpOnly）+ `refresh_token`（path 限定 `/api/auth/refresh`）。
- AES 密钥 = `md5(SECRET_KEY)[:16]`，CBC，前 16 字节是 IV。**更换 `SECRET_KEY` 会导致已存密码/凭据全部解不开**。
- `relogin`：扫码用户（password 为 None）无法自动重登 → 发 `UserReloginRequiredEvent` 并抛 510。

### platform（三平台适配）
抽象基类 `service/platform/base/__init__.py:Platform`，靠 `__init_subclass__` 自动注册到 `_platforms`，子类必须定义 `name` 和 `auth_method`（否则 `SyntaxError`）。新增平台 = 写 `Platform` 子类 + 在 `platform/__init__.py` import。
- `login()` 返回 cookies；`get_homework()` 返回 `list[Homework]`；`valid_cookie()`。
- 认证方式：学习通 = 账号密码（`AuthMethod.PASSWORD`，自写 `encryptByAES`，key 硬编码）；学在重邮 / 雨课堂 = 复用当前用户统一认证（`AuthMethod.CQUPT_IDS` → `base/utils.login_with_ddl_account`，内部会在 cookie 失效时自动 `auth.relogin` 重试一次）。
- 雨课堂登录后要**重排 `sessionid` cookie** 才能让 `cqupt.yuketang.cn` 与 `changjiang.yuketang.cn` 共享。
- `fetch_homework()` 统一封装：未绑定 → 428 `PlatformNotBound`；冷却中 → 429 `RefreshCoolingDown`；cookie 失效 → `InvalidPlatformCookie` 时 `auth.relogin` 后重试一次。
- 解析失败**不要抛异常**：学习通对未知收件箱用专门的 `chaoxing:unknown-inbox` logger 记录并 `continue`（该 logger 在非 DEBUG 下被禁用）。

### homework（缓存/刷新）
- 刷新**只新增，不删除**（删除逻辑在 `refresh_homework.py` 里被注释掉了）。完成状态 `done` 是本地状态，不是平台状态（除 meetschedule PULL 会回写）。
- 缓存 TTL = `homework_cache_base_ttl` + 最多 `homework_cache_jitter`；手动刷新冷却 `homework_cooldown_ttl`。
- `get_last_refresh_time` 用 `max()`，代码里标了 `XXX` 争议（多平台不同步刷新）。
- 多平台刷新时 `router/api/homework.py` 把异常转成给用户看的提示字符串列表，未知异常带 uuid 错误码。

### qqpush（QQ 推送）
- **现役实现是 `push.py`**（走 qqchan `/qqchan/send`，发纯文本，未传 `ismarkdown`）：`__init__.py`、`strategy.py`、`on_boot.py` 都只 import 它。
- `push_wild.py` 与 `push_official.py` 是**同源的死代码**（历史版本，`push_official` 多传 `ismarkdown=True`）—— 全仓库零引用。**改推送逻辑只需改 `push.py`**；但若将来要切回官方 API，这两个文件的差异就是参考。
- 后端主动推游戏机器人用 `QQBOT_RECV_API_KEY`；机器人回调后端用 `QQBOT_SEND_API_KEY`（`X-API-Key` 头）。命名与 qqbot 端一致，**不是对称的**。
- 策略：`ScheduledStrategy`（cron 定时推 scope 小时内截止）与 `RealtimeStrategy`（每个作业一个 job，在 `deadline - scope` 触发）。实时推送经 `buffer`（带 asyncio.Lock）由 5 秒间隔的 `push_buffered_homeworks` 合并发送。
- 未绑定 qqchan_id 时静默跳过；推送返回 `"无此id"` → 发 `InvalidQQChanIDEvent` 清空绑定。

### meetschedule（同步到 Meet课程表）
核心在 `refresh_task.py`（610 行，最复杂）。要点：
- `_job` 每 `meetschedule_sync_interval` 秒一次，固定顺序 **PUSH → UPDATE → DELETE → PULL**；阶段内按 user 分组，每组一个 client + `AsyncMeetSchedule`。
- 远程结果只分 `OK / MISSING / PERMANENT / TRANSIENT`，本地动作**只由唯一真值表 `_transition(phase, result)` 决定**。改同步规则就改这里，别在阶段中间删数据。
- 无显式重试计数/退避：TRANSIENT 保持状态靠下轮重试；PERMANENT(422/409) 与"作业不存在/无 deadline"直接删跟踪，避免无限重试。
- 401/403 → 用户加入 `to_unbind`，四阶段跑完后删其全部条目 + `MeetscheduleConfig`。
- 限流 `limiter.throttle`：60 次/分钟（FIXED_WINDOW，MemoryStore，**进程内**，多 worker 不共享）；限流 key 取 SDK 私有属性 `meet._client.headers["X-API-Key"]`（**SDK 一改就炸**）。
- 批量 100；push 必须 `allow_duplicate_title=True`；`create_batch` 返回数量与请求不符 → 整批 TRANSIENT（防重复创建）。
- 绑定要校验 key 权限 `SCHEDULE_READ + ENTITIES_READ + ENTITIES_WRITE`（不足 → 403）。
- 快照分区必须在改任何状态之前完成；`_job` 中途不 commit。

## 6. 本地开发与验证

```bash
uv sync                 # 安装依赖
uv run cquptddl         # 启动（DEBUG=true 时 reload + 只监听 127.0.0.1）
```
- 配置全部来自 `.env`（`pydantic-settings`，`extra="ignore"`，字段名大小写不敏感）。**必需**：`DATABASE_URL`、`SECRET_KEY`、`QQBOT_URL`、`QQBOT_RECV_API_KEY`、`QQBOT_SEND_API_KEY`。常用可调项见 `core/config.py`。`.env` 已被 gitignore，仓库里没有 `.env.example`。
- 本地用 `sqlite+aiosqlite:///./test.db`（仓库根有 `test.db`，首次导入 `config` 时就会实例化 Settings）。
- **建表方式只有 `SQLModel.metadata.create_all`**（`core/db.py:_migrate_db`）：只建缺失的表，**永不 ALTER**。改字段/类型必须自己写迁移或重建库。
- 验证手段：`uv run python -c "import cquptddl"` 能捕获大部分 import/符号注册错误；`/docs` 看路由。**注意 `import cquptddl` 会读取 `.env` 并连库**。

## 7. 提交前必须跑 ty + ruff（全局安装）

**改动任何 `.py` 后，提交前必须跑这两条并在项目根目录执行**（`ty`/`ruff` 是全局命令，不在 `.venv` 里，也**不在** `pyproject.toml` 里配置 —— 用工具默认规则）：

```bash
ty check          # 类型检查
ruff check .      # lint
ruff format --check .   # 格式（如需修复用 ruff format .）
```

- 已验证的**基线**：`HEAD` 上（不含工作区改动）`ty check` 与 `ruff check .` 均 **All checks passed**；`ruff format --check .` 当前输出 74 files already formatted（`HEAD` 的 72 个 `.py` + 未跟踪的 `AGENTS.md` 等）。**格式全部合规，不要跑 `ruff format .` 大范围改写**。
- 工具版本（2025-09 时点）：`ty 0.0.81`、`ruff 0.16.8`。`ruff` 默认规则集下 `T100`（`breakpoint`）会报错，F401 等也会。
- `ty check` 必须在**仓库根**跑：放别处会因找不到 `pyproject.toml`/`.venv` 而无法解析依赖，产生大量假报错。
- 未配置 ruff/ty 的 `[tool.*]` 段，也没有 `ruff.toml`/`ty.toml`；`.ruff_cache` 已被 gitignore。
- 行内抑制用 `# ty: ignore[规则名]`（不需要 `# type: ignore`）；ruff 用 `# noqa: 规则名`。

## 8. 代码约定与坑（照做能省很多 token）

- 注释、日志、异常 detail 全是**中文**；提交信息是 Conventional Commits（`feat(scope):` / `fix(scope):` / `style` / `chore`）。
- 每个模块顶部 `_logger = getLogger(__name__)` 并显式 `setLevel`（根 logger 是 WARNING，不设就看不到日志）。
- 业务异常一律加进 `exc.py`（继承 `CquptddlException`，用类属性写 `status`/`detail`）；抛未知异常前先记日志并给用户一个 uuid 错误码。
- `session.get_one()` 会抛 `NoResultFound`；"可能不存在"用 `session.get()` 并判 `None`。
- 路由函数名大量重复用 `_`（依赖 FastAPI 只看装饰器）；路由前缀在 `router/api/__init__.py`，全部挂 `/api` 下。
- 类型检查器是 `ty`，不是 mypy（见 §7 的检查命令）。
- ⚠️ **工作区有未提交的进行中重构，当前 `ty`/`ruff` 均不通过 —— 这 7 个报错全部来自工作区，HEAD 是干净的**：
  - `service/platform/chaoxing/__init__.py:75` 有 `breakpoint()`（会卡死学习通的后台自动刷新任务）和 `_logger.debug(data)` → ruff `T100`；
  - chaoxing / xzcy / yuketang 三个模块的 `setLevel` 被改成了 `DEBUG`，导致 `INFO` 变成未使用导入 → ruff 3×`F401`；
  - `Homework.generate_id` 签名正从 `(user_id, platform, course_name, title)` 收敛为 `(user_id, platform, platform_custom)`，但三个平台**仍按 4 个参数调用** → ty 3×`too-many-positional-arguments`（chaoxing:95、xzcy:60、yuketang:129）；`base/utils.py` 的 `login_from_platform_account` 已同步改名为 `login_with_ddl_account`。
  接手时的正确顺序：先删 `breakpoint()`、把三个平台改回 `INFO`，再决定 `generate_id` 到底要几参（**注意它是作业主键的来源，见 §4**）并统一调用方，最后让 `ty check` + `ruff check .` 归零。
