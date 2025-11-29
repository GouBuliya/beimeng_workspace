# Temu Auto Publish Auth Server

认证服务器，为 Temu 自动发布系统提供用户管理和单设备登录限制功能。

## 功能特性

- 用户注册/登录/登出
- JWT 令牌认证
- 单设备登录限制（新登录自动踢出旧会话）
- 用户管理（CRUD）
- 强制下线功能
- Docker 容器化部署

## 技术栈

- **后端框架**: FastAPI
- **数据库**: PostgreSQL 15
- **缓存**: Redis 7
- **认证**: JWT (PyJWT) + bcrypt
- **ORM**: SQLAlchemy 2.0 (async)
- **容器化**: Docker + Docker Compose

## 快速开始

### 使用 Docker Compose（推荐）

1. 复制环境变量配置文件：

```bash
cp env.example .env
```

2. 修改 `.env` 文件中的配置，**特别是 JWT_SECRET_KEY 和数据库密码**

3. 启动所有服务：

```bash
docker-compose up -d
```

4. 查看服务状态：

```bash
docker-compose ps
```

5. 查看日志：

```bash
docker-compose logs -f auth-server
```

### 本地开发

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 确保 PostgreSQL 和 Redis 正在运行

3. 配置环境变量或创建 `.env` 文件

4. 启动服务：

```bash
uvicorn app.main:app --reload --port 8001
```

## API 文档

启动服务后访问：

- Swagger UI: http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc

## 主要 API 端点

### 认证

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /auth/register | 用户注册 |
| POST | /auth/login | 用户登录（踢出旧会话）|
| POST | /auth/logout | 用户登出 |
| POST | /auth/refresh | 刷新令牌 |
| POST | /auth/verify | 验证令牌 |
| GET | /auth/me | 获取当前用户信息 |
| PUT | /auth/password | 修改密码 |

### 用户管理（需要管理员权限）

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /users | 获取用户列表 |
| POST | /users | 创建用户 |
| GET | /users/{id} | 获取用户详情 |
| PUT | /users/{id} | 更新用户 |
| DELETE | /users/{id} | 删除用户 |
| POST | /users/{id}/force-logout | 强制用户下线 |

## 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| POSTGRES_USER | 数据库用户名 | temu_auth |
| POSTGRES_PASSWORD | 数据库密码 | temu_auth_password |
| POSTGRES_DB | 数据库名称 | temu_auth_db |
| POSTGRES_HOST | 数据库主机 | localhost |
| POSTGRES_PORT | 数据库端口 | 5432 |
| REDIS_HOST | Redis 主机 | localhost |
| REDIS_PORT | Redis 端口 | 6379 |
| REDIS_PASSWORD | Redis 密码 | (空) |
| JWT_SECRET_KEY | JWT 密钥 | (必须修改) |
| JWT_ACCESS_TOKEN_EXPIRE_MINUTES | 访问令牌过期时间（分钟）| 60 |
| JWT_REFRESH_TOKEN_EXPIRE_DAYS | 刷新令牌过期时间（天）| 7 |
| AUTH_SERVER_PORT | 服务端口 | 8001 |
| INIT_ADMIN_USERNAME | 初始管理员用户名 | admin |
| INIT_ADMIN_PASSWORD | 初始管理员密码 | admin123456 |

## 客户端集成

在 `temu-auto-publish` 项目中配置以下环境变量：

```bash
# 启用远程认证
USE_REMOTE_AUTH=true

# 认证服务器地址
AUTH_SERVER_URL=http://localhost:8001
```

## 项目结构

```
temu-auto-publish-server/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 应用入口
│   ├── core/
│   │   ├── config.py        # 配置管理
│   │   ├── database.py      # 数据库连接
│   │   ├── security.py      # 安全工具
│   │   └── redis_client.py  # Redis 会话管理
│   ├── auth/
│   │   ├── router.py        # 认证路由
│   │   ├── service.py       # 认证服务
│   │   ├── schemas.py       # Pydantic 模型
│   │   └── deps.py          # 依赖注入
│   ├── users/
│   │   ├── router.py        # 用户管理路由
│   │   ├── service.py       # 用户管理服务
│   │   └── schemas.py       # Pydantic 模型
│   └── models/
│       └── user.py          # 用户数据库模型
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## 安全注意事项

1. **生产环境必须修改 JWT_SECRET_KEY**
2. 使用强密码保护数据库和 Redis
3. 建议在生产环境使用 HTTPS
4. 定期更换管理员密码
5. 监控异常登录行为

