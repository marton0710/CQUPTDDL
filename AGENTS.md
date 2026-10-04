# AGENTS.md — CQUPTDDL（重邮聚合截止线）后端

跨会话速查手册，先读这里。约 4.7k 行 Python，全在 `src/cquptddl/`。

## 1. 项目速览

聚合 **学在重邮 / 学习通 / 雨课堂** 作业的 REST API；可选同步成 **Meet课程表** 事件，并经 QQ 机器人（qqchan）推送临期/新作业。

- Python **>=3.14**（`uuid7`、`itertools.batched`）+ **uv**；入口 `cquptddl:main`，运行 `uv run cquptddl`（`DEBUG=true` 时 reload 且只监听 127.0.0.1）。
- 开发分支 `v2`（`master` 落后），远端 `git@github.com:marton0710/CQUPTDDL.git`；`README.md` 是空的。
- 部署：`Dockerfile`（python:3.14-alpine）从自建源 `pypi.bail.asia` 装包，前端 `COPY fe /fe` 由 `FRONTEND_DIR` 指向，暴露 8000。
- 前端静态托管在 `router/__init__.py`：`FRONTEND_DIR` 有值才 `router.frontend("/", ..., fallback="index.html")`，随 `app.include_router` 生效。

## 2. 配置、检查与验证

- 配置来自 `.env`（`pydantic-settings`，`extra="ignore"`，大小写不敏感），见 `core/config.py`。**必需**：`DATABASE_URL`、`SECRET_KEY`、`QQBOT_URL`、`QQBOT_RECV_API_KEY`、`QQBOT_SEND_API_KEY`。没有 `.env.example`（`.env` 已 gitignore），根目录有本地 `test.db`。
- **建表只有 `SQLModel.metadata.create_all`**（`core/db.py:_migrate_db`）：只建缺失的表，**永不 ALTER**。改字段/类型得自己写一次性迁移或重建库，别往 `_migrate_db` 塞自动迁移。
- 改完 `.py` 必须在**仓库根**跑 `ty check && ruff check . && ruff format --check .`（`ty`/`ruff` 是全局命令，不在 `.venv`，`pyproject.toml` 里也没有配置段）。基线三条全绿（format 输出 `88 files already formatted`）；**不要 `ruff format .` 全量改写**，要修只 format 单个文件。
- `ty` 会被 SQLModel 表达式误报：`select(M).where(列 == 值)` 常判 `invalid-argument-type`，照现有代码挂 `# ty: ignore[invalid-argument-type]`（`select(M.id)` / `select(func.count())` 一般不用）。抑制写 `# ty: ignore[规则]` / `# noqa: 规则`，不是 `# type: ignore`；只读文件系统下 ruff 加 `--no-cache`。
- 验证：`uv run python -c "import cquptddl"` 能抓大部分 import / 符号注册错误，`/docs` 看路由；注意它会读 `.env` 并连库。

## 3. 架构五机制

### 3.1 依赖注入 `core.factory`

- `depends_session` / `depends_client`：FastAPI 依赖；路由用别名 `SessionDep`（`middleware.session`）、`UserDep`（`middleware.auth` = `need_login` 校验 `token` Cookie 后返回 `User`）。
- `get_session()` / `get_client()`：`asynccontextmanager` 版，**给非路由代码（钩子 / 事件回调、后台任务）用**。
- session 在 `yield` **之后** `commit()`：路由不 commit 也会落库，`get_session()` 同样；别让同一 session 并发。
- `depends_client` 自动加 `User-Agent: CQUPTDDL/<版本>`，`headers=` 是合并非覆盖；未设 `timeout`，吃 httpx 默认 5s。
- 独立短事务先例：`platform/fetch.py:_check_platform_cooldown` 用按 用户×平台 的 `asyncio.Lock` + 自己的 `get_session()` 读写 `last_refreshed_homework`，冷却中抛 429。

### 3.2 符号表 `core.symbol`

**声明与实现分离**：`core/symbol.py` 用泛型 `Symbol[**P, R]` / `AsyncSymbol[**P, R]` 预声明跨 service 接口（同时就是类型签名），实现处挂 `@core.symbol.<属性名>.register`，调用处直接 `core.symbol.<属性名>(...)`（异步的记得 `await`）。**跨 service 调用一律走符号表**，别直接 import 别的 service。全表（`grep -rn "\.register" src/cquptddl/service` 可复核，属性名下划线连写、字符串键带点，如 `auth_password_login` ↔ `"auth.password_login"`）：

- `auth_password_login` `auth_get_login_qrcode` `auth_qrcode_login` `auth_relogin` `auth_get_user_from_token` `auth_refresh_token` `auth_logout` `auth_delete_account`
- `crypto_aes_encrypt` `crypto_aes_decrypt`
- `platform_get_auth_method` `platform_bind` `platform_unbind` `platform_valid_cookie` `platform_fetch_homework`
- `homework_refresh_homework` `homework_complete` `homework_get_cached_homework` `homework_get_cached_homework_count` `homework_get_last_refresh_time` `homework_get_user_dying_homeworks` `homework_get_user_homeworks_with_deadline`
- `qqpush_configure` `qqpush_get_configure` `qqpush_get_user_config_from_qqchan_id` `qqpush_push_dying_homeworks`
- `meetschedule_bind` `meetschedule_unbind` `meetschedule_is_bound`
- `ics_list_subscriptions` `ics_create_subscription` `ics_delete_subscription` `ics_render_feed` `ics_get_url_count`

⚠️ 同名重复 `register` 抛 `NameError`；注册发生在**模块导入时**，导入链断了要到调用时才炸（见 3.3 的 import 链路）。`Symbol`/`AsyncSymbol` 自带签名，ty 能查调用参数，但注册键名仍是运行时字符串 —— 删改符号要同步 `symbol.py` 声明与实现。`core.symbol.mock(name, func)` 仅 `DEBUG` 下可临时替换实现（退出恢复；现役用例见 `tests/test_symbol_mock.py`，mock 掉 `platform.fetch_homework` 测刷新去重）。⚠️ `Symbol` 声明里的参数**没有默认值**，实现有默认值时调用处得挂 `# ty: ignore[missing-argument]`（如 `platform_fetch_homework` 省略 `check_cooldown`）。

### 3.3 钩子 `core.hook`

进程内轻量扩展点：`@core.hook.on("名字", background=False, index=99)` 注册（一个函数可叠多个），`await core.hook.trigger("名字", *args, **kw)` 触发。handler 与符号一样在**模块导入时**生效，靠 `service/__init__.py` 的 `from . import ...` 链路 —— **新增 service 模块必须能被这条链 import 到**，否则钩子 / 符号全不生效。

- 同步 handler 按注册顺序 `await`，单个抛异常只记 `error` 并继续跑后面的；`background=True` 的丢给 `core.task.background`，不等待、异常由 task 完成回调记日志（耗时 / 跨事务逻辑优先 background）。
- `auth.before_delete_user` 是唯一带 `session` 的同步钩子（meetschedule 借它解绑，`delete_account` 随后 `session.delete(user)`），别改成 background。
- 现有钩子：`auth.after_register`（建 QQPushConfig）、`auth.after_login`（暂无 handler，预留）、`auth.before_delete_user` / `auth.after_delete_user`（清刷新 job / 推送策略 / meetschedule 绑定）、`platform.after_bind` / `platform.after_unbind`（增删刷新 job、删本地作业）、`homework.after_refresh`（新作业入库后：qqpush 提醒 + meetschedule 推送）、`homework.after_done`、`qqpush.after_config_change`（重载该用户推送策略）。

### 3.4 事件总线 `core.bus`（abxbus）

只剩两个全局广播事件（`model/event/__init__.py`），监听方都在 `qqpush/push.py` 用 `core.bus.on(Event, handler)`：`UserReloginRequiredEvent`（`auth.relogin` emit → 推"登录已过期"）与 `AutoRefreshHomeworkFailedEvent`（`refresh_task._job` emit → 推刷新失败提醒）。**新逻辑优先用 3.3 的 hook，别再加 bus 事件**。

### 3.5 后台任务

- `core.task.background(coro, name)` 立即跑；`register()` 供事件循环启动前登记，由 `core.init()` 的 `task.start()` 统一启动。
- APScheduler 三处：`homework/refresh_task.scheduler`（按 用户×平台 刷新，job id `homework_fetch_schedule_{uid}_{platform}`，间隔 `homework_cache_base_ttl`+jitter）、`qqpush/globals.scheduler`、`meetschedule/refresh_task.scheduler`。
- 生命周期 `cquptddl/__init__.py:lifespan`：`core.init()`（建表 + 启任务）→ `service.init()`（刷新 job、qqpush on_boot、meetschedule 钩子 + 同步）；关闭相反。

## 4. 目录与数据模型

```
core/       config / db / factory / symbol / hook / event_bus / task
model/db/   SQLModel 表：User Homework PlatformInfo QQPushConfig MeetscheduleConfig MeetscheduleEntry IcsSubscription
model/schema/ API 模型与枚举（PlatformEnum、AuthMethod）     model/event/ 事件定义
router/api/ auth homework ics platform qqpush meetscheule(文件名拼写如此，前缀 /meetschedule)
middleware/ auth(UserDep) session(SessionDep) qqpush(verify_api_key: X-API-Key)
service/    auth crypto homework ics platform qqpush meetschedule
exc.py      业务异常（CquptddlException→HTTPException，类属性 status/detail）
```

`model/db/__init__.py` 的 `__all__` 里 `LastRefreshTime`、`PlatformCookies` 是历史残留，**已不存在**。

- **User**：主键 `id` = 统一认证码；`password` 是 AES 密文（扫码登录为 `None`）；`token_version` 用于批量失效 token。
- **Homework**：主键 `id = uuid5(NAMESPACE, user_id + platform + platform_custom)`（`Homework.generate_id`）。`platform_custom` 必须在**用户×平台**内唯一（学习通 `hmw_info["key"]`、学在重邮 `item["id"]`、雨课堂 `str(item["id"])`）。⚠️ 改它 = 改所有作业主键，而刷新**只增不删** → 上线即整体重复一遍，必须配一次性迁移。
- **PlatformInfo**：主键 `(user_id, platform)`；`credentials` 是 AES 密文 JSON；`last_refreshed_homework` 兼冷却计时。
- **MeetscheduleEntry**：主键 = `homework.id`，仅是**弱外键**（不声明 `foreign_key`）；`status` 走 `pending → pending-update / pending-delete → success`。⚠️ 任何改作业主键的操作必须同步改这张表，否则 PUSH/UPDATE 判 `PERMANENT` 删 entry，而删远端事件只走 DELETE → 用户日历里留下删不掉的孤儿事件。
- **IcsSubscription**：主键 `id`（uuid7），**一个用户可多条**；`token_hash`=sha256(token) 唯一索引；`created_at` 兼作 feed 的 `DTSTAMP`；`fetch_count`/`last_fetched_at` 记拉取统计。
- **PlatformEnum 的值就是中文名**（`"学在重邮"`/`"学习通"`/`"雨课堂"`），路径参数也用它。

## 5. 跨 service 传 `User` 还是 `user_id`

刻意不统一，别"顺手统一"：

- **只收 `user_id: str`**：按 uid 过滤 / 归属校验的接口 —— `homework.*` 查询与 `complete`、`platform.valid_cookie`/`unbind`、`qqpush.configure`、`meetschedule.bind`/`unbind`、全部 ics 接口。
- **收 `User`**：要读 / 回写 `password`、`ids_cookie`、`token_version`、`name` 的（`auth.relogin`/`login`/`logout`、`platform.bind`/`relogin`），或本身是**扩展点契约**的（`auth.delete_account` 与钩子 `auth.before_delete_user(session, User)`，最后 `session.delete(user)`）。
- ⚠️ 改签名先看下游：`platform.fetch_homework` 自己只用 `user.id`，但内部要调 `auth.relogin(session, user, ...)`，所以必须继续收 `User`（传递性依赖，不是漏改）。

## 6. 业务要点

### auth

- 统一认证走 `fuckids`；二维码会话在**进程内字典** `service/auth/ids.py:_qrcode_login_sessions`（多 worker 失效），TTL `qr_login_session_ttl`，`_clear_expired_qrlogin_session()` 惰性清理 —— 别退回无界增长。未扫描返回 202。
- JWT：uid 先 AES 加密再进 payload，`isrefresh` 区分 access/refresh，校验比对 `token_version`；Cookie 为 `token`（httpOnly）+ `refresh_token`（path 限 `/api/auth/refresh`）。
- AES 密钥 = `md5(SECRET_KEY)[:16]`，CBC，前 16 字节 IV。**换 `SECRET_KEY` 会让已存密码 / 凭据全部解不开**。
- `relogin`：扫码用户（password 为 `None`）无法自动重登 → 发 `UserReloginRequiredEvent` 并抛 510。`GET /api/auth/me` 还会返回 `ics_url_count`。

### platform

- 抽象基类 `service/platform/base/__init__.py:Platform`，`__init_subclass__` 自动注册；子类必须定义 `name` 和 `auth_method`（否则 `SyntaxError`）。新增平台 = 写子类 + 在 `platform/__init__.py` import。
- 学习通 = 账号密码（`AuthMethod.PASSWORD`，自写 `encryptByAES`，key 硬编码）；学在重邮 / 雨课堂复用统一认证（`AuthMethod.CQUPT_IDS` → `base/utils.login_with_ddl_account`，cookie 失效时自动 `auth.relogin` 重试一次）。雨课堂登录后要**重排 `sessionid` cookie** 才能跨两个 yuketang 域共享。
- `fetch_homework()`：未绑定 → 428；冷却中 → 429（`check_cooldown=False` 可跳过）；最多 `homework_refresh_attempts`（默认 3）次，**只对 `httpx.TimeoutException` 重试**（固定 1s），cookie 失效则 relogin 后重发；用尽后**原样抛最后一次异常** —— 别把超时吞成空列表，那会让刷新静默失败。
- 解析失败**不要抛异常**：学习通对未知收件箱用 `...chaoxing:unknown-inbox` logger 记录并 `continue`（非 DEBUG 下该 logger 被禁用）。

### homework

- 刷新**只新增，不删除**（删除逻辑被注释掉了）。`done` 是本地状态，不是平台状态（只有 meetschedule PULL 回写）。
- `homework_cache_base_ttl`(+jitter) 是**自动刷新间隔**，不是读缓存 TTL（查询直接读库）；手动刷新冷却 `homework_cooldown_ttl`。
- `get_last_refresh_time` 用多平台 `max()`（代码里标了 `XXX` 争议）。多平台刷新时 `router/api/homework.py` 把异常转成给用户看的提示列表，未知异常带 uuid 错误码。

### qqpush

- **现役是 `push.py`**（qqchan `/qqchan/send`，默认纯文本），只有它被 import；`push_wild.py` / `push_official.py` 是同源死代码（零引用），改推送只改 `push.py`。⚠️ 死代码里也挂着同名的 `@core.symbol...register` / `@core.hook.on` —— **别顺手 import 它们**，重复注册会直接 `NameError`。
- 后端 → 机器人用 `QQBOT_RECV_API_KEY`，机器人 → 后端用 `QQBOT_SEND_API_KEY`（`X-API-Key`，`middleware/qqpush.verify_api_key`）。命名与 qqbot 端一致，**不对称是故意的**。
- `ScheduledStrategy`（cron 推 scope 小时内截止的）与 `RealtimeStrategy`（每作业一个 job，`deadline - scope` 触发）；实时推送进 `buffer`（`asyncio.Lock`），由 5 秒间隔的 `push_buffered_homeworks` 合并发送。未绑定 `qqchan_id` 静默跳过；返回 `"无此id"` → 抛 `QQChanIDNotExist` → `_unbind` 清空绑定并触发 `qqpush.after_config_change` 钩子（重载推送策略）。

### meetschedule（最复杂，核心 `refresh_task.py` 约 600 行）

- `_job` 每 `meetschedule_sync_interval` 秒一次，固定顺序 **PUSH → UPDATE → DELETE → PULL**；阶段内按 user 分组，每组一个 client。
- 远程结果只分 `OK / MISSING / PERMANENT / TRANSIENT`，本地动作**只由真值表 `_transition(phase, result)` 决定**。改同步规则改这里，别在阶段中间删数据。
- 无重试计数 / 退避：TRANSIENT 保持状态等下轮；PERMANENT(422/409) 与"作业不存在 / 无 deadline"直接删跟踪。401/403 → 用户进 `to_unbind`，四阶段跑完才统一解绑（删全部条目 + `MeetscheduleConfig`）。
- 快照分区必须在改任何状态之前完成；`_job` 中途不 commit。
- 绑定要校验 key 权限（`SCHEDULE_READ + ENTITIES_READ + ENTITIES_WRITE`，不足 403）且课程表已存在，之后把当前全部作业写成 entry。批量 100，push 必须 `allow_duplicate_title=True`，`create_batch` 返回数量与请求不符 → 整批 TRANSIENT（防重复创建）。
- 限流 `limiter.acquire`：60 次/分钟，FIXED_WINDOW + MemoryStore，**进程内**（多 worker 不共享）；key 取 SDK 私有属性 `meet._client.headers["X-API-Key"]`（**SDK 一改就炸**）。

### ics（日历订阅）

- **请求时即时渲染**：无后台任务、无缓存、**无钩子 / 事件监听**。`feed.py` 的 `build_calendar`/`render_ics` 必须是**纯函数**（`DTSTAMP` 取 `subscription.created_at`、VTIMEZONE 固定 1970–2038、查询 `order_by(deadline, id)`）—— `ETag = sha256(body)[:32]`，掺进 `now()` 就会抖动、304 失效。
- 只认 `If-None-Match`（不发 `Last-Modified`），刻意**不输出 `SEQUENCE`/`LAST-MODIFIED`**：现在刷新只增不改既有作业，UID 内容不可变；将来要更新旧作业字段，得给 `Homework` 加 `updated_at` + 迁移再补这两个属性，否则客户端不会刷新旧事件。
- 只收 `done == False` 且有 `deadline` 的作业，保留最近 `ics_past_days` 天内已截止的；完成后从 feed 消失，客户端自会删事件。`GET /api/ics/feed/{token}.ics` 不校验登录（日历客户端发不了 cookie），token 无效一律 404（不区分"不存在"与"已撤销"）。
- 多订阅：`GET`/`POST /api/ics/subscription`（POST 每次新建不去重，响应带明文 `token`，**只此一次**）、`DELETE /api/ics/subscription/{id}`（非本人或不存在 404）；前端用 `id` 区分并自己拼 feed URL，后端不返回完整 url。库里只存 `sha256(token)`，**别换 bcrypt/argon2**（对 256 位随机 token 没意义，只会拖慢 feed），丢了就删掉重建。
- 拉取统计：渲染成功后 `_record_fetch` 原子自增 `fetch_count` 并刷新 `last_fetched_at`（304 也算）。**统计字段绝不能进渲染结果**，否则 ETag 每次都变。配置：`ics_timezone`、`ics_event_duration_minutes`、`ics_past_days`。
- ⚠️ 订阅表由 `create_all` 建；从"一人一条"改成多订阅时主键 `user_id` → `id`，`create_all` 不 ALTER：**旧库要人工 `DROP TABLE icssubscription` 重建**，再让用户重新生成。

## 7. 约定

- 注释、日志、异常 detail 全是**中文**；提交信息 Conventional Commits（`feat(scope):` / `fix(scope):` / …）。
- 测试用 pytest，`tests/` 有 6 个文件（ics feed / 订阅 / url 计数 / 平台冷却 / version / 符号 mock）；dev 依赖里 `respx` 零引用。
- 每个模块 `_logger = getLogger(__name__)` 并显式 `setLevel`（根 logger 是 WARNING，不设看不到日志）。
- 业务异常一律加进 `exc.py`（继承 `CquptddlException`，类属性写 `status`/`detail`）；抛未知异常前先记日志并给用户 uuid 错误码。
- `session.get_one()` 会抛 `NoResultFound`；"可能不存在"用 `session.get()` 并判 `None`。路由函数名大量重复用 `_`（FastAPI 只看装饰器）。
- **不要留 `breakpoint()`**（ruff `T100`，还会卡死对应后台任务）；**不要 `_logger.debug(整个响应体)`**（平台响应动辄几十 KB），要留痕只记条数或长度。
