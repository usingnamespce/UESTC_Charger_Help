"""定期采集充电口状态，在内存中保留最新快照，并提供 HTTP 查询。"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hmac
import json
import os
import ssl
import threading
import time
import traceback
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from charger_api import STATUS_BROKEN, STATUS_BUSY, STATUS_FREE, fetch_station

RUNTIME_DIR = Path(__file__).resolve().parent
WEB_DIR = RUNTIME_DIR / "web"


CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".ico": "image/x-icon",
    ".webp": "image/webp",
}


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_SAMPLE_INTERVAL_S = 60
DEFAULT_STATION_WORKERS = 8
UTC = dt.timezone.utc


def utc_now() -> dt.datetime:
    return dt.datetime.now(UTC)


def iso_utc(value: Optional[dt.datetime] = None) -> str:
    value = value or utc_now()
    return value.astimezone(UTC).isoformat(timespec="milliseconds")


def resolve_local_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parent / path


def load_station_map(path: Path, limit: Optional[int] = None) -> Dict[str, int]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    items = list(data.items())
    if limit:
        items = items[:limit]
    return {name: int(station_id) for name, station_id in items}


@dataclass(frozen=True)
class OutletSnapshot:
    serial: int
    status: int
    used_min: Optional[int]


@dataclass(frozen=True)
class StationSnapshot:
    sampled_at: str
    outlets: tuple[OutletSnapshot, ...]
    free_count: int
    busy_count: int
    broken_count: int

    @classmethod
    def from_outlets(cls, sampled_at: str, outlets: List[Dict[str, Any]]) -> StationSnapshot:
        readings = (
            OutletSnapshot(outlet["serial"], outlet["status"], outlet.get("used_min"))
            for outlet in outlets
        )
        ordered = tuple(sorted(readings, key=lambda outlet: outlet.serial))
        return cls(
            sampled_at=sampled_at,
            outlets=ordered,
            free_count=sum(o.status == STATUS_FREE for o in ordered),
            busy_count=sum(o.status == STATUS_BUSY for o in ordered),
            broken_count=sum(o.status == STATUS_BROKEN for o in ordered),
        )


class SnapshotStore:
    """Publish one completed round at a time without keeping a history."""

    def __init__(self, station_map: Dict[str, int]):
        self._names = {station_id: name for name, station_id in sorted(station_map.items())}
        self._state: tuple[Dict[int, StationSnapshot], frozenset[int]] = ({}, frozenset())
        self._lock = threading.Lock()

    def publish(self, snapshots: Dict[int, StationSnapshot], failed_ids: set[int]) -> None:
        with self._lock:
            previous, _ = self._state
            self._state = ({**previous, **snapshots}, frozenset(failed_ids))

    def _read(self) -> tuple[Dict[int, StationSnapshot], frozenset[int]]:
        with self._lock:
            return self._state

    def _station_status(self, station_id: int, snapshot: Optional[StationSnapshot], failed: bool) -> Dict[str, Any]:
        if snapshot is None:
            status = "unavailable" if failed else "waiting"
        else:
            status = "stale" if failed else "ready"
        return {
            "station_id": station_id,
            "station_name": self._names[station_id],
            "sample_status": status,
            "last_seen_at": snapshot.sampled_at if snapshot is not None else None,
        }

    def list_stations(self, search: str = "") -> List[Dict[str, Any]]:
        needle = search.strip().casefold()
        snapshots, failed = self._read()
        rows = []
        for station_id, name in self._names.items():
            if needle not in name.casefold():
                continue
            snapshot = snapshots.get(station_id)
            row = self._station_status(station_id, snapshot, station_id in failed)
            if snapshot is not None and station_id not in failed:
                row.update(
                    outlet_count=len(snapshot.outlets),
                    free_count=snapshot.free_count,
                    busy_count=snapshot.busy_count,
                    broken_count=snapshot.broken_count,
                )
            else:
                row.update(outlet_count=None, free_count=None, busy_count=None,
                           broken_count=None)
            rows.append(row)
        return rows

    def list_outlets(self, station_id: int, search: str = "") -> Optional[Dict[str, Any]]:
        if station_id not in self._names:
            return None
        snapshots, failed = self._read()
        snapshot = snapshots.get(station_id)
        row = self._station_status(station_id, snapshot, station_id in failed)
        needle = search.strip()
        row["outlets"] = [
            {"serial": o.serial, "status": o.status, "used_min": o.used_min}
            for o in snapshot.outlets if needle in str(o.serial)
        ] if snapshot is not None and station_id not in failed else []
        return row

    def totals(self) -> Dict[str, int]:
        snapshots, failed = self._read()
        ready = [snapshot for sid, snapshot in snapshots.items() if sid not in failed]
        return {
            "station_count": len(self._names),
            "ready_station_count": len(ready),
            "failed_station_count": len(failed),
            "outlet_count": sum(len(snapshot.outlets) for snapshot in ready),
        }


class SnapshotCollector:
    def __init__(
        self,
        station_map: Dict[str, int],
        store: SnapshotStore,
        sample_interval_s: int,
        station_workers: int,
        auto_collect: bool = True,
    ):
        self.station_map = station_map
        self.store = store
        self.sample_interval_s = max(5, sample_interval_s)
        self.station_workers = max(1, station_workers)
        self.auto_collect = auto_collect
        self._stop_event = threading.Event()
        self._loop_thread: Optional[threading.Thread] = None
        self._run_lock = threading.Lock()
        self._last_run_started_at: Optional[str] = None
        self._last_run_finished_at: Optional[str] = None
        self._last_error: Optional[str] = None
        self._last_summary: Dict[str, Any] = {}

    def start(self) -> None:
        if not self.auto_collect:
            return
        if self._loop_thread and self._loop_thread.is_alive():
            return
        self._loop_thread = threading.Thread(target=self._loop, name="snapshot-collector", daemon=True)
        self._loop_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=5)

    def is_collecting(self) -> bool:
        return self._run_lock.locked()

    def status_snapshot(self) -> Dict[str, Any]:
        return {
            "sample_interval_s": self.sample_interval_s,
            "station_workers": self.station_workers,
            "station_total": len(self.station_map),
            "auto_collect": self.auto_collect,
            "is_collecting": self.is_collecting(),
            "last_run_started_at": self._last_run_started_at,
            "last_run_finished_at": self._last_run_finished_at,
            "last_error": self._last_error,
            "last_summary": self._last_summary,
        }

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            self.run_once()
            if self._stop_event.wait(self.sample_interval_s):
                break

    def run_once(self) -> Dict[str, Any]:
        if not self._run_lock.acquire(blocking=False):
            return {
                "status": "busy",
                "message": "采集任务正在进行中",
                "started_at": self._last_run_started_at,
            }

        started_at = iso_utc()
        self._last_run_started_at = started_at
        self._last_error = None
        try:
            try:
                summary = self._collect(started_at)
            except Exception:
                self._last_error = traceback.format_exc()
                self.store.publish({}, set(self.station_map.values()))
                print(self._last_error)
                summary = {"status": "error", "started_at": started_at, "finished_at": iso_utc(),
                           "station_ok": 0, "station_failed": len(self.station_map)}
            else:
                if summary["status"] == "error":
                    self._last_error = "本轮没有站点采样成功"
            self._last_run_finished_at = summary["finished_at"]
            self._last_summary = summary
            return summary
        finally:
            self._run_lock.release()

    def _collect(self, started_at: str) -> Dict[str, Any]:
        print(f"[collector] collect started at {started_at}")
        snapshots: Dict[int, StationSnapshot] = {}
        failures: Dict[int, Dict[str, Any]] = {}
        worker_count = min(self.station_workers, max(1, len(self.station_map)))

        def read(sid: int) -> StationSnapshot:
            outlets = fetch_station(sid)
            if outlets is None:
                raise ValueError("接口请求失败或返回无效数据")
            return StationSnapshot.from_outlets(iso_utc(), outlets)

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {executor.submit(read, sid): (name, sid) for name, sid in self.station_map.items()}
            for future in as_completed(futures):
                name, sid = futures[future]
                try:
                    snapshots[sid] = future.result()
                except Exception as exc:
                    failures[sid] = {"station_name": name, "station_id": sid, "error": str(exc)}

        self.store.publish(snapshots, set(failures))
        summary = {
            "status": "ok" if not failures else "partial" if snapshots else "error",
            "started_at": started_at,
            "finished_at": iso_utc(),
            "sample_time": max((snapshot.sampled_at for snapshot in snapshots.values()), default=None),
            "station_total": len(self.station_map),
            "station_ok": len(snapshots),
            "station_failed": len(failures),
            "outlet_total": sum(len(snapshot.outlets) for snapshot in snapshots.values()),
            "busy_total": sum(snapshot.busy_count for snapshot in snapshots.values()),
            "failed_stations": list(failures.values())[:12],
        }
        print(f"[collector] collect finished: ok={len(snapshots)}, failed={len(failures)}, "
              f"outlets={summary['outlet_total']}, busy={summary['busy_total']}")
        return summary


class ChargerService:
    def __init__(self, args: argparse.Namespace):
        self.station_file = resolve_local_path(args.stations)
        self.station_map = load_station_map(self.station_file, args.station_limit)
        self.store = SnapshotStore(self.station_map)
        self.collector = SnapshotCollector(
            station_map=self.station_map,
            store=self.store,
            sample_interval_s=args.sample_interval,
            station_workers=args.station_workers,
            auto_collect=not args.no_collector,
        )

    def start(self) -> None:
        self.collector.start()

    def stop(self) -> None:
        self.collector.stop()

    def health(self) -> Dict[str, Any]:
        return {
            "station_file": str(self.station_file),
            "collector": self.collector.status_snapshot(),
            "totals": self.store.totals(),
        }


class ChargerRequestHandler(BaseHTTPRequestHandler):
    service: Optional[ChargerService] = None
    # 管理接口口令（Basic Auth）：None 表示未配置。由 serve_forever 从环境变量注入。
    # 只作用于 /api/admin/*（如 /api/admin/collect）；普通查询接口不鉴权、全开放。
    auth_user: Optional[str] = None
    auth_pass: Optional[str] = None
    # 按 IP 限流：rate_window 秒内每个 IP 最多 rate_limit 次请求；0 表示不限。
    rate_limit: int = 0
    rate_window: int = 60
    _hits: Dict[str, "deque[float]"] = {}
    _hits_lock = threading.Lock()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_common_headers()
        self.end_headers()

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            path = parsed.path.rstrip("/") or "/"

            # 管理接口：先按 IP 限流，再校验口令；未配置口令则直接关闭，避免公网被随意触发。
            # 普通查询接口不鉴权、也不限流（只读内存快照）。
            if path.startswith("/api/admin"):
                if not self._check_rate_limit():
                    return
                if not self._require_admin_auth():
                    return

            if path == "/" or path == "/index.html":
                if self._serve_static("index.html"):
                    return
                self._write_json(
                    200,
                    {
                        "ok": True,
                        "data": {
                            "name": "charger-monitor",
                            "health": "/api/health",
                            "stations": "/api/stations",
                            "outlets": "/api/outlets?station_id=120204",
                            "collect": "/api/admin/collect",
                        },
                    },
                )
                return

            if self.service is None:
                self._write_json(500, {"ok": False, "error": "服务未初始化"})
                return

            if path == "/api/health":
                self._write_json(200, {"ok": True, "data": self.service.health()})
                return

            if path == "/api/stations":
                search = self._query_one(query, "search", "")
                data = self.service.store.list_stations(search=search)
                self._write_json(200, {"ok": True, "data": data})
                return

            if path == "/api/outlets":
                station_id = int(self._query_one(query, "station_id"))
                search = self._query_one(query, "search", "")
                data = self.service.store.list_outlets(station_id, search=search)
                if data is None:
                    self._write_json(404, {"ok": False, "error": "站点不存在"})
                    return
                self._write_json(200, {"ok": True, "data": data})
                return

            if path == "/api/admin/collect":
                data = self.service.collector.run_once()
                self._write_json(200, {"ok": True, "data": data})
                return

            if self._serve_static(path.lstrip("/")):
                return
            self._write_json(404, {"ok": False, "error": f"未知接口: {path}"})
        except ValueError as exc:
            self._write_json(400, {"ok": False, "error": str(exc)})
        except Exception:
            self._write_json(
                500,
                {
                    "ok": False,
                    "error": traceback.format_exc(limit=3),
                },
            )

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[http] {self.address_string()} - {fmt % args}")

    @staticmethod
    def _query_one(query: Dict[str, List[str]], key: str, default: Optional[str] = None) -> str:
        values = query.get(key)
        if not values:
            if default is None:
                raise ValueError(f"缺少参数: {key}")
            return default
        return values[0]

    def _send_common_headers(self) -> None:
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _check_rate_limit(self) -> bool:
        """按 IP 限流：窗口内超过阈值则返回 429。rate_limit=0 时不限。"""
        if not self.rate_limit:
            return True
        ip = self.client_address[0] if self.client_address else "?"
        now = time.time()
        with self._hits_lock:
            dq = self._hits.setdefault(ip, deque())
            while dq and dq[0] <= now - self.rate_window:
                dq.popleft()
            if len(dq) >= self.rate_limit:
                self._send_too_many()
                return False
            dq.append(now)
            # 内存保护：列表过大时清理空桶
            if len(self._hits) > 10000 and dq is not None:
                for k in [k for k, v in self._hits.items() if not v]:
                    self._hits.pop(k, None)
        return True

    def _send_too_many(self) -> None:
        body = json.dumps({"ok": False, "error": "访问过于频繁，请稍后再试"}, ensure_ascii=False).encode("utf-8")
        self.send_response(429)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _require_admin_auth(self) -> bool:
        """仅 /api/admin/* 需要口令；未配置口令时直接关闭（403）。"""
        if not self.auth_user:
            self._send_forbidden("手动采集已关闭（未配置管理口令）")
            return False
        header = self.headers.get("Authorization")
        if header and header.startswith("Basic "):
            try:
                decoded = base64.b64decode(header[6:].strip()).decode("utf-8")
                user, _, pw = decoded.partition(":")
            except Exception:
                user, pw = "", ""
            if (
                hmac.compare_digest(user, self.auth_user)
                and hmac.compare_digest(pw, self.auth_pass or "")
            ):
                return True
        self._send_auth_challenge()
        return False

    def _send_forbidden(self, msg: str) -> None:
        body = json.dumps({"ok": False, "error": msg}, ensure_ascii=False).encode("utf-8")
        self.send_response(403)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_auth_challenge(self) -> None:
        body = json.dumps({"ok": False, "error": "需要管理口令"}, ensure_ascii=False).encode("utf-8")
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="charger-monitor", charset="UTF-8"')
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._send_common_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, rel_path: str) -> bool:
        """从 WEB_DIR 提供静态文件；找不到返回 False。"""
        if not WEB_DIR.is_dir():
            return False
        rel_path = rel_path or "index.html"
        candidate = (WEB_DIR / rel_path).resolve()
        try:
            candidate.relative_to(WEB_DIR.resolve())
        except ValueError:
            return False
        if not candidate.is_file():
            return False
        ext = candidate.suffix.lower()
        content_type = CONTENT_TYPES.get(ext, "application/octet-stream")
        try:
            body = candidate.read_bytes()
        except OSError:
            return False
        self._write_bytes(200, body, content_type)
        return True


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="充电桩状态查询后端")
    parser.add_argument("--host", default=DEFAULT_HOST, help="监听地址，默认 127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="监听端口，默认 8765")
    parser.add_argument(
        "--stations",
        default=str(RUNTIME_DIR / "all.json"),
        help="站点清单 JSON，默认脚本同目录下的 all.json",
    )
    parser.add_argument(
        "--sample-interval",
        type=int,
        default=DEFAULT_SAMPLE_INTERVAL_S,
        help="采样间隔秒数，默认 60。测试时可临时改小。",
    )
    parser.add_argument(
        "--station-workers",
        type=int,
        default=DEFAULT_STATION_WORKERS,
        help="站点并发采样线程数，默认 8",
    )
    parser.add_argument(
        "--station-limit",
        type=int,
        default=None,
        help="仅采样前 N 个站点，方便本地压测和调试",
    )
    parser.add_argument(
        "--no-collector",
        action="store_true",
        help="只启动接口服务，不自动循环采样",
    )
    parser.add_argument("--ssl-cert", default=None, help="HTTPS 证书文件路径，例如 fullchain.pem")
    parser.add_argument("--ssl-key", default=None, help="HTTPS 私钥文件路径，例如 privkey.pem")
    return parser


def serve_forever(args: argparse.Namespace) -> None:
    service = ChargerService(args)
    ChargerRequestHandler.service = service

    # 管理口令（仅作用于 /api/admin/*）：设置 CHARGER_AUTH_USER / CHARGER_AUTH_PASS 即启用。
    auth_user = os.environ.get("CHARGER_AUTH_USER")
    auth_pass = os.environ.get("CHARGER_AUTH_PASS")
    if bool(auth_user) ^ bool(auth_pass):
        print("[charger] 警告: CHARGER_AUTH_USER 与 CHARGER_AUTH_PASS 必须同时设置，本次管理接口将被关闭")
        auth_user = auth_pass = None
    ChargerRequestHandler.auth_user = auth_user
    ChargerRequestHandler.auth_pass = auth_pass

    # 按 IP 限流（只作用于 /api/admin/*，即手动采集等重接口）：每 IP 每窗口最大请求数。
    # 默认 30 次/60秒；设为 0 表示不限。普通查询接口不限流、不鉴权（只读内存快照）。
    try:
        rate_limit = int(os.environ.get("CHARGER_RATE_LIMIT", "30"))
        rate_window = int(os.environ.get("CHARGER_RATE_WINDOW", "60"))
    except ValueError:
        rate_limit, rate_window = 30, 60
    ChargerRequestHandler.rate_limit = max(0, rate_limit)
    ChargerRequestHandler.rate_window = max(1, rate_window)

    server = ThreadingHTTPServer((args.host, args.port), ChargerRequestHandler)
    server.daemon_threads = True
    scheme = "http"

    if args.ssl_cert and args.ssl_key:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(certfile=args.ssl_cert, keyfile=args.ssl_key)
        server.socket = ssl_context.wrap_socket(server.socket, server_side=True)
        scheme = "https"

    print(f"[charger] station file: {service.station_file}")
    print(f"[charger] stations    : {len(service.station_map)}")
    print(f"[charger] listen      : {scheme}://{args.host}:{args.port}")
    print(f"[charger] admin-auth  : {'on (' + (auth_user or '') + ') 仅 /api/admin/*' if auth_user else 'off (管理接口已关闭)'}")
    print(f"[charger] rate-limit  : {ChargerRequestHandler.rate_limit} req/{ChargerRequestHandler.rate_window}s per IP" +
          (" (disabled)" if not ChargerRequestHandler.rate_limit else ""))
    if args.no_collector:
        print("[charger] collector   : disabled")
    else:
        print(f"[charger] collector   : every {service.collector.sample_interval_s}s")

    service.start()
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("\n[charger] stopping...")
    finally:
        server.shutdown()
        server.server_close()
        service.stop()


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    if bool(args.ssl_cert) ^ bool(args.ssl_key):
        parser.error("--ssl-cert 和 --ssl-key 必须同时提供，或者都不提供")
    serve_forever(args)


if __name__ == "__main__":
    main()
