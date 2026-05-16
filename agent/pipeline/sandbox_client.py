"""sandbox_client — Tier C 工具侧能力客户端(spec 002)。

生成的工具**不做** raw open()/requests;改用本模块,经 token 鉴权的
loopback socket 把请求发给受信 broker,broker 过 Cedar 后代办。
任何被拒 → 抛 BrokerDenied(工具拿到的是结构化拒绝,不是宿主异常)。

无 broker 环境(DS_BROKER_ADDR 未设)→ 直接抛错:工具**不能**退回
raw 访问 —— 这正是 Tier C「唯一出路」的意义。
"""

from __future__ import annotations

import json
import os
import socket


class BrokerDenied(RuntimeError):
    """Cedar 经 broker 拒绝了该 fs/net 请求。"""


def available() -> bool:
    return bool(os.environ.get("DS_BROKER_UDS") or os.environ.get("DS_BROKER_ADDR"))


def _connect():
    """优先 UDS(与 Tier B 组合,穿透 --network none),否则 TCP loopback。"""
    uds = os.environ.get("DS_BROKER_UDS")
    if uds and hasattr(socket, "AF_UNIX"):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(20)
        s.connect(uds)
        return s
    addr = os.environ.get("DS_BROKER_ADDR")
    if addr:
        host, port = addr.rsplit(":", 1)
        return socket.create_connection((host, int(port)), timeout=20)
    raise BrokerDenied("no broker (DS_BROKER_UDS/ADDR unset): Tier C 下无直接访问")


def _request(req: dict) -> dict:
    token = os.environ.get("DS_BROKER_TOKEN", "")
    req = {**req, "token": token}
    with _connect() as s:
        f = s.makefile("rwb")
        f.write((json.dumps(req) + "\n").encode("utf-8"))
        f.flush()
        line = f.readline()
    try:
        resp = json.loads(line or b"{}")
    except Exception:
        raise BrokerDenied("broker: malformed response")
    if not resp.get("ok"):
        raise BrokerDenied(resp.get("error", "denied"))
    return resp


def read_file(path: str) -> str:
    return _request({"op": "read_file", "path": path})["data"]


def write_out(path: str, data: str) -> int:
    return _request({"op": "write_file", "path": path, "data": data})["bytes"]


def http_get(url: str) -> str:
    return _request({"op": "net_get", "url": url})["data"]
