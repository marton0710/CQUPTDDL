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
scripts/    运维脚本，不进应用（migrate_db.py / check_ids.py，见 §9）
```
注意：`model/db/__init__.py` 的 `__all__` 里 `LastRefreshTime`、`PlatformCookies` **已不存在**，是历史残留。

## 4. 关键数据模型

- **User**：主键 `id` = 真实统一认证码；`password` 为 AES 密文（扫码登录为 `None`）；`token_version: UUID` 用于退出登录时批量失效 token。
- **Homework**：主键 `id = uuid5(NAMESPACE, user_id + platform + platform_custom)`，即 `Homework.generate_id(user_id, platform, platform_custom)`。`platform_custom` 由各平台给出，且必须在**「用户 × 平台」范围内全局唯一**（不能只在课程内唯一）：学习通 `hmw_info["key"]`（实测 = `f"{taskrefId}-{classId}"`）、学在重邮 `item["id"]`、雨课堂 `str(item["id"])`。
  ⚠️ **改这个函数等于改所有作业主键**：旧主键的行不会消失也不会被覆盖，而 `refresh_homework` 只增不删 → 新代码一上线就是整体重复一次。主键换规则必须配一次性迁移，见 §9。
- **PlatformInfo**：主键 `(user_id, platform)`；`credentials` 是 AES 密文 JSON；`last_refreshed_homework` 兼作**冷却计时**（`_check_platform_cooldown` 直接改它）。
- **MeetscheduleEntry**：主键 = `homework.id`，但**只是弱外键**（`model/db/meetschedule_tracked_event.py` 已不声明 `foreign_key`；历史库上的物理外键是 `1758fa4` 之前留下的，已在生产手工删掉）。`status` 走 `pending → pending-update / pending-delete → success` 状态机。
  ⚠️ 主键跟随 homework，所以任何改作业主键的操作**必须同步改这张表**：`entry.id` 指向一个不存在的作业时，PUSH/UPDATE 阶段会判 `PERMANENT` 并把 entry 删掉，而删远端 Meet 事件只走 DELETE 阶段 → 不处理就会在用户日历里留下**永远删不掉的孤儿事件**。
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

- 已验证的**基线**：`ty check`、`ruff check .` 均 **All checks passed**，`ruff format --check .` 输出 **75 files already formatted**。**格式全部合规，不要跑 `ruff format .` 大范围改写**（要修就只 `ruff format <单个文件>`）。
- 工具版本（2025-09 时点）：`ty 0.0.81`、`ruff 0.16.8`。`ruff` 默认规则集下 `T100`（`breakpoint`）会报错，F401 等也会。
- `ty check` 必须在**仓库根**跑：放别处会因找不到 `pyproject.toml`/`.venv` 而无法解析依赖，产生大量假报错。
- 未配置 ruff/ty 的 `[tool.*]` 段，也没有 `ruff.toml`/`ty.toml`；`.ruff_cache` 已被 gitignore。
- 行内抑制用 `# ty: ignore[规则名]`（不需要 `# type: ignore`）；ruff 用 `# noqa: 规则名`。
- **SQLModel/SQLAlchemy 表达式会让 `ty` 误报**：`select(<Model>).where(<列> == <值>)` 常被判成 `invalid-argument-type`（`<列> == <值>` 静态上返回 `bool`）。仓库既有代码就是直接挂 `# ty: ignore[invalid-argument-type]`，照做即可；`select(Model.id)` / `select(func.count())` 这类单列表述式通常不需要。
- 文件系统只读的会话里 `ruff` 会因写不了 `.ruff_cache` 而失败，此时加 `--no-cache`。

## 8. 代码约定与坑（照做能省很多 token）

- 注释、日志、异常 detail 全是**中文**；提交信息是 Conventional Commits（`feat(scope):` / `fix(scope):` / `style` / `chore`）。
- 每个模块顶部 `_logger = getLogger(__name__)` 并显式 `setLevel`（根 logger 是 WARNING，不设就看不到日志）。
- 业务异常一律加进 `exc.py`（继承 `CquptddlException`，用类属性写 `status`/`detail`）；抛未知异常前先记日志并给用户一个 uuid 错误码。
- `session.get_one()` 会抛 `NoResultFound`；"可能不存在"用 `session.get()` 并判 `None`。
- 路由函数名大量重复用 `_`（依赖 FastAPI 只看装饰器）；路由前缀在 `router/api/__init__.py`，全部挂 `/api` 下。
- 类型检查器是 `ty`，不是 mypy（见 §7 的检查命令）。
- **不要在生产路径上留 `breakpoint()`**：`ruff` 报 `T100`，而且它会直接卡死对应的后台刷新任务。
- **不要 `_logger.debug(<整个响应体>)`**：平台响应动辄几十 KB（学习通一条通知就是），排障完立刻删；要留痕就记条数或长度。

## 9. 一次性迁移：`scripts/migrate_db.py`

作业主键换规则时用它（背景见 §4）。它是**独立脚本**，不进应用生命周期：不调 `core.init()`/`service.init()`（那会建表 + 起 APScheduler），也不调 `homework.refresh_homework`（那会 commit 并 emit `HomeworkRefreshedEvent`，引发 QQ 全量推送、还会给新主键建 entry，和迁移打架）；只直接用 `platform.fetch_homework(..., check_cooldown=False)`。

做法：对每个 (user, platform) 拉一次作业，按新旧两套规则各算一次主键，命中旧主键的行**原地改名**（`UPDATE ... SET id=...`，先子表 `meetscheduleentry` 再父表 `homework`）；本次没拉到的作业**直接删掉**（先把对应 entry 置 `pending-delete`，交给新代码的 DELETE 阶段去删远端事件，**绝不在脚本里碰 Meet API**）。每个 (user, platform) 一个事务，接口异常整段跳过、不碰数据库。

- 配对以主键法为主；作业被老师改过名时用 `url` 归一化后兜底（学习通取 `taskrefId`+`classId`，学在重邮取 `course_id`+`hmw_id`，雨课堂取 URL 末两段）。**必须归一化**——学习通 url 带会轮换的 `enc=` 签名。
- 旧规则碰撞（同课程同名作业，生产里真实存在）会让两条作业算出同一个旧主键：先到者改名，败者不动，交给上线后的一次 refresh 正常插入并建 entry。
- 输出：stdout 是 JSONL（每目标一行 + 最后一行 `__summary__`，含完整 `{旧:新}` 字典），日志走 stderr；**必须在宿主机侧 `| tee` 接收**（`docker/podman exec` 的输出不进 `logs`，容器一 kill 可写层也没了）。
- 跑法：容器内先 `python /migrate_db.py --dry-run` 审一遍，再 `--yes` 正式跑。**只能在容器内跑**：宿主机 `.env` 指向 sqlite，且 `SECRET_KEY` 不同会导致平台凭据解不开。
- 冻结旧代码用 `podman exec <ctr> kill -STOP 1`；**不要用 `podman pause`**（cgroup freezer 会把 `exec` 也冻住）。迁移完 `kill` 容器，再上新镜像。

### `scripts/check_ids.py`（只读诊断）

迁移前后来回确认用。不给任何参数：先打印库中作业主键分布（**旧规则几条 / 新规则几条**），再自动挑一个能拉到的 (user, platform) 比对 `item.id` 与旧规则 id。全程只读，结束回滚（连 relogin 刷新的 cookie 都不落库）。

- 迁移**完成**的标志：`旧规则 0`。
- 迁移**根本没生效**的标志：`旧规则 = 总行数`，且逐条比对出现 `相同=True` —— 说明代码算出来的 `platform_custom` 退化成了 `course_name + title`，此时 `migrate_db.py` 的「改名」会**恒为 0**（每条作业都被判成"新主键已在库"），而它仍会照常删掉"没拉到的作业"。**这种情况绝对不能上新代码**：refresh 会把全部旧主键行按新主键重插一遍，造成整体重复。
