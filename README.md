# CQUPTDDL 接口文档

## 1. 项目说明

CQUPTDDL 是一个基于 FastAPI 的作业查询服务，提供以下能力：

- 用户登录
- 用户注册
- 获取超星（学习通）作业
- 获取学在重邮作业
- 获取雨课堂作业

## 2. 基础信息

- 基础地址：`/api`
- 数据格式：`application/json`
- 认证方式：`Bearer Token`

### 请求头示例

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

## 3. 通用说明

### 3.1 成功响应

不同接口返回格式略有差异：

- 登录 / 注册接口：

```json
{
  "code": 200,
  "username": "xxx",
  "token": "xxx"
}
```

- 作业查询接口：

```json
{
  "errcode": 0,
  "username": "xxx",
  "homework": []
}
```

### 3.2 失败响应

统一返回 FastAPI 的 `HTTPException` 结构：

```json
{
  "detail": {
    "code": 400,
    "message": "错误信息"
  }
}
```

### 3.3 Token 过期说明

当 `access_token` 无效或已过期时，鉴权层会返回错误：

```json
{
  "detail": {
    "code": 400,
    "message": "token 无效或已过期"
  }
}
```

前端或调用方应在收到该错误后重新登录并获取新的 Token。

---

## 4. 接口列表

## 4.1 用户登录

### 请求地址

`POST /api/login`

### 请求说明

用户登录并获取 `access_token`。

### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| username | string | 是 | 用户名 |
| password | string | 是 | 密码 |
| email | string | 是 | 邮箱 |

### 请求示例

```json
{
  "username": "testuser",
  "password": "123456",
  "email": "test@example.com"
}
```

### 成功响应

```json
{
  "code": 200,
  "username": "testuser",
  "token": "eyJhbGciOiJIUzI1NiIs..."
}
```

### 失败响应

```json
{
  "detail": {
    "code": 400,
    "message": "用户名或密码错误"
  }
}
```

---

## 4.2 用户注册

### 请求地址

`POST /api/register`

### 请求说明

注册新用户。

### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| username | string | 是 | 用户名 |
| password | string | 是 | 密码 |
| confirm_password | string | 是 | 确认密码 |
| email | string | 是 | 邮箱 |

### 请求示例

```json
{
  "username": "testuser",
  "password": "123456",
  "confirm_password": "123456",
  "email": "test@example.com"
}
```

### 成功响应

```json
{
  "code": 200,
  "username": "testuser"
}
```

### 失败响应

```json
{
  "detail": {
    "code": 400,
    "message": "用户名已存在"
  }
}
```

---

## 4.3 获取超星作业

### 请求地址

`POST /api/chaoxing`

### 请求说明

获取超星（学习通）作业列表。

该接口需要登录态 Token。

### 请求头

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| username | string | 是 | 超星用户名 |
| password | string | 是 | 超星密码 |

### 请求示例

```json
{
  "username": "student01",
  "password": "123456"
}
```

### 成功响应

```json
{
  "errcode": 0,
  "username": "student01",
  "homework": [
    {
      "title": "作业标题",
      "content": "作业标题",
      "deadline": "2026-05-10T12:00:00",
      "course_name": "课程名",
      "url": "https://example.com",
      "platform": "学习通"
    }
  ]
}
```

### 失败响应

```json
{
  "detail": {
    "code": 400,
    "message": "token 无效或已过期"
  }
}
```

---

## 4.4 获取学在重邮作业

### 请求地址

`POST /api/xuezai`

### 请求说明

获取学在重邮作业列表。

该接口需要登录态 Token。

### 请求头

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| username | string | 是 | 学在重邮用户名 |
| password | string | 是 | 学在重邮密码 |

### 请求示例

```json
{
  "username": "student01",
  "password": "123456"
}
```

### 成功响应

```json
{
  "errcode": 0,
  "username": "student01",
  "homework": []
}
```

### 失败响应

```json
{
  "detail": {
    "code": 400,
    "message": "token 无效或已过期"
  }
}
```

---

## 4.5 获取雨课堂作业

### 请求地址

`POST /api/yuketang`

### 请求说明

获取雨课堂作业列表。

该接口需要登录态 Token。

### 请求头

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| username | string | 是 | 用户名 |
| cookies | object | 是 | 雨课堂 cookies 对象 |

### 请求示例

```json
{
  "username": "student01",
  "cookies": {
    "sessionid": "xxx"
  }
}
```

### 成功响应

```json
{
  "errcode": 0,
  "username": "student01",
  "homework": []
}
```

### 失败响应

```json
{
  "detail": {
    "code": 400,
    "message": "token 无效或已过期"
  }
}
```

---

## 5. 认证说明

### 5.1 获取 Token

调用 `POST /api/login` 成功后返回：

```json
{
  "token": "eyJhbGciOiJIUzI1NiIs..."
}
```

### 5.2 使用 Token

访问受保护接口时，在请求头中添加：

```http
Authorization: Bearer <access_token>
```

### 5.3 Token 过期处理

如果 Token 失效或过期，返回内容通常为：

```json
{
  "detail": {
    "code": 400,
    "message": "token 无效或已过期"
  }
}
```

建议客户端处理逻辑：

1. 捕获 401/400 认证错误
2. 清除本地 Token
3. 跳转到登录页
4. 重新登录后再访问接口

---

## 6. 数据结构说明

### Homework

| 字段名 | 类型 | 说明 |
|---|---|---|
| title | string | 作业标题 |
| content | string | 作业内容 |
| deadline | datetime \| null | 截止时间 |
| course_name | string | 课程名 |
| url | string | 作业链接 |
| platform | string | 平台名称 |

---

## 7. 备注

- `POST /api/login` 与 `POST /api/register` 不需要 Token。
- `POST /api/chaoxing`、`POST /api/xuezai`、`POST /api/yuketang` 都需要 `Authorization` 认证。
- 当前接口返回结构中存在 `code` 和 `errcode` 两种成功字段，前端使用时注意区分。
- 如果后续增加刷新 Token 机制，建议补充 `/api/refresh` 接口。

