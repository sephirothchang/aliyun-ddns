# aliyun-ddns Docker 镜像

用于自动更新阿里云 DNS 解析记录（DDNS）。

## 功能
- 定时获取公网 IP。
- 查询阿里云现有解析记录。
- 若 IP 未变化则跳过；若变化则自动更新。
- 所有参数通过外部配置文件传入。

## 配置文件
复制 `config.example.yml` 为你自己的 `config.yml` 并填写参数。

关键参数：
- `access_key_id`
- `access_key_secret`
- `region_id`
- `domain_name`
- `rr`
- `record_type` (`A` 或 `AAAA`)
- `ttl`
- `interval_seconds`

## 构建镜像
```bash
docker build -t aliyun-ddns:latest .
```

## 运行容器
```bash
docker run -d \
  --name aliyun-ddns \
  --restart unless-stopped \
  -v /path/to/config.yml:/app/config.yml:ro \
  aliyun-ddns:latest
```

> 群辉 Docker 也可以用同样思路：将 `config.yml` 挂载到容器 `/app/config.yml`。

## 可选：自定义配置路径
```bash
docker run -d \
  --name aliyun-ddns \
  --restart unless-stopped \
  -v /path/to/my-config.yml:/data/my-config.yml:ro \
  aliyun-ddns:latest \
  python /app/ddns_updater.py --config /data/my-config.yml
```


## 使用 Docker Compose
在项目目录准备好 `config.yml` 后，直接运行：

```bash
docker compose up -d --build
```

停止服务：

```bash
docker compose down
```
