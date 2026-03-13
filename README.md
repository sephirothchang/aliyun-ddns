# aliyun-ddns Docker 镜像

用于自动更新阿里云 DNS 解析记录（DDNS）。

## 功能
- 定时获取公网 IP。
- 查询阿里云现有解析记录。
- 若 IP 未变化则跳过；若变化则自动更新。
- 所有参数通过外部配置文件传入。

## 配置文件
默认读取容器路径：`/app/config.yaml`。

先创建本地配置文件：

```bash
cp config.example.yml ./config.yaml
```

关键参数（你要求的字段）：
- `access_id`（或 `access_key_id`）
- `access_secret`（或 `access_key_secret`）
- `domain_name`
- `redo`（更新间隔秒数；等价于 `interval_seconds`）
- `ttl`
- `timezone`
- `type`（等价于 `record_type`）

## 构建镜像
```bash
docker build -t aliyun-ddns:latest .
```

## 运行容器（挂载本地配置文件）
```bash
docker run -d \
  --name aliyun-ddns \
  --restart unless-stopped \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  aliyun-ddns:latest
```

## 使用 Docker Compose
在项目目录准备好 `./config.yaml` 后，直接运行：

```bash
docker compose up -d --build
```

停止服务：

```bash
docker compose down
```
