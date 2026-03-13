#!/usr/bin/env python3
import argparse
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests
import yaml
from alibabacloud_alidns20150109 import models as alidns_models
from alibabacloud_alidns20150109.client import Client as AlidnsClient
from alibabacloud_tea_openapi import models as open_api_models


@dataclass
class Config:
    access_key_id: str
    access_key_secret: str
    region_id: str
    domain_name: str
    rr: str
    record_type: str
    ttl: int
    interval_seconds: int
    timezone: str
    endpoint: str
    ip_sources: list[str]


def _pick_str(raw: dict, *keys: str, default: Optional[str] = None) -> Optional[str]:
    for key in keys:
        if key in raw and raw[key] not in (None, ""):
            return str(raw[key])
    return default


def _pick_int(raw: dict, *keys: str, default: Optional[int] = None) -> Optional[int]:
    for key in keys:
        if key in raw and raw[key] not in (None, ""):
            return int(raw[key])
    return default


def load_config(path: Path) -> Config:
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")

    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    access_key_id = _pick_str(raw, "access_key_id", "access_id")
    access_key_secret = _pick_str(raw, "access_key_secret", "access_secret")
    domain_name = _pick_str(raw, "domain_name", "domain")
    rr = _pick_str(raw, "rr", default="@")
    record_type = _pick_str(raw, "record_type", "type")
    ttl = _pick_int(raw, "ttl")
    interval_seconds = _pick_int(raw, "interval_seconds", "redo")

    required_values = {
        "access_key_id/access_id": access_key_id,
        "access_key_secret/access_secret": access_key_secret,
        "domain_name/domain": domain_name,
        "record_type/type": record_type,
        "ttl": ttl,
        "interval_seconds/redo": interval_seconds,
    }
    missing = [k for k, v in required_values.items() if v in (None, "")]
    if missing:
        raise ValueError(f"配置文件缺少必填项: {', '.join(missing)}")

    ip_sources = raw.get(
        "ip_sources",
        ["https://api.ipify.org", "https://ifconfig.me/ip", "https://ip.sb"],
    )
    if not isinstance(ip_sources, list) or not ip_sources:
        raise ValueError("ip_sources 必须是非空数组")

    region_id = _pick_str(raw, "region_id", default="cn-hangzhou")
    timezone = _pick_str(raw, "timezone", default="Asia/Shanghai")

    return Config(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        region_id=region_id,
        domain_name=domain_name,
        rr=rr,
        record_type=str(record_type).upper(),
        ttl=int(ttl),
        interval_seconds=int(interval_seconds),
        timezone=timezone,
        endpoint=str(raw.get("endpoint", "alidns.cn-hangzhou.aliyuncs.com")),
        ip_sources=[str(x) for x in ip_sources],
    )


def create_client(config: Config) -> AlidnsClient:
    open_api_config = open_api_models.Config(
        access_key_id=config.access_key_id,
        access_key_secret=config.access_key_secret,
        region_id=config.region_id,
        endpoint=config.endpoint,
    )
    return AlidnsClient(open_api_config)


def get_public_ip(sources: list[str], timeout: int = 5) -> str:
    last_error: Optional[Exception] = None
    for url in sources:
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            ip = resp.text.strip()
            if ip:
                return ip
        except Exception as exc:  # pylint: disable=broad-except
            last_error = exc
            logging.warning("获取公网 IP 失败 (%s): %s", url, exc)

    raise RuntimeError(f"无法获取公网 IP，最后错误: {last_error}")


def find_record(client: AlidnsClient, config: Config):
    req = alidns_models.DescribeSubDomainRecordsRequest(
        sub_domain=f"{config.rr}.{config.domain_name}",
        type=config.record_type,
    )
    resp = client.describe_sub_domain_records(req)
    records = getattr(resp.body, "domain_records", None)
    if not records or not records.record:
        return None

    return records.record[0]


def create_record(client: AlidnsClient, config: Config, value: str) -> None:
    req = alidns_models.AddDomainRecordRequest(
        domain_name=config.domain_name,
        rr=config.rr,
        type=config.record_type,
        value=value,
        ttl=config.ttl,
    )
    client.add_domain_record(req)
    logging.info("已创建解析记录: %s.%s -> %s", config.rr, config.domain_name, value)


def update_record(client: AlidnsClient, config: Config, record_id: str, value: str) -> None:
    req = alidns_models.UpdateDomainRecordRequest(
        record_id=record_id,
        rr=config.rr,
        type=config.record_type,
        value=value,
        ttl=config.ttl,
    )
    client.update_domain_record(req)
    logging.info("已更新解析记录: %s.%s -> %s", config.rr, config.domain_name, value)


def run_once(client: AlidnsClient, config: Config) -> None:
    ip = get_public_ip(config.ip_sources)
    record = find_record(client, config)

    if record is None:
        logging.info("未找到记录，准备创建。目标 IP: %s", ip)
        create_record(client, config, ip)
        return

    current_value = record.value
    if current_value == ip:
        logging.info("IP 未变化，跳过更新。当前: %s", current_value)
        return

    logging.info("IP 变化: %s -> %s", current_value, ip)
    update_record(client, config, record.record_id, ip)


def main() -> int:
    parser = argparse.ArgumentParser(description="阿里云 DDNS 自动更新")
    parser.add_argument(
        "--config",
        default="/app/config.yaml",
        help="配置文件路径，默认 /app/config.yaml",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    try:
        config = load_config(Path(args.config))
        if config.interval_seconds <= 0:
            raise ValueError("interval_seconds/redo 必须 > 0")

        os.environ["TZ"] = config.timezone
        if hasattr(time, "tzset"):
            time.tzset()

        client = create_client(config)
        logging.info(
            "DDNS 服务已启动，检查间隔: %s 秒，时区: %s",
            config.interval_seconds,
            config.timezone,
        )

        while True:
            try:
                run_once(client, config)
            except Exception as exc:  # pylint: disable=broad-except
                logging.exception("本轮更新失败: %s", exc)
            time.sleep(config.interval_seconds)

    except Exception as exc:  # pylint: disable=broad-except
        logging.exception("启动失败: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
