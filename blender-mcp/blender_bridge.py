# Persistent bridge that runs INSIDE a headless Blender process.
# Listens on 127.0.0.1:9876 (BLENDER_BRIDGE_PORT) and executes commands.
#
# Protocol: 4-byte big-endian uint32 length prefix + UTF-8 JSON payload.
# Request:  {"id": <str>, "type": "ping"|"exec", "params": {...}}
# Response: {"id": <str>, "status": "ok"|"error", "result": ..., "message": ...}

import json
import os
import sys
import socket
import struct
import traceback
import contextlib
import io
import datetime

HOST = os.environ.get("BLENDER_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("BLENDER_BRIDGE_PORT", "9876"))

GLOBALS = {"__name__": "__blender_bridge__"}


def _send(conn, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    conn.sendall(struct.pack(">I", len(data)) + data)


def _recv_exactly(conn, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(min(65536, n - len(buf)))
        if not chunk:
            raise ConnectionError("client disconnected")
        buf += chunk
    return buf


def _handle_exec(params: dict) -> dict:
    code = params.get("code", "")
    if not code.strip():
        return {"status": "error", "message": "empty code"}
    stdout = io.StringIO()
    stderr = io.StringIO()
    env = dict(GLOBALS)
    env["_result"] = None
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exec(compile(code, "<mcp>", "exec"), env)
        GLOBALS.update({k: v for k, v in env.items() if not k.startswith("__")})
        result = env.get("_result")
        try:
            json.dumps(result)
        except (TypeError, ValueError):
            result = repr(result)
        return {
            "status": "ok",
            "result": result,
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
        }
    except Exception:
        return {
            "status": "error",
            "message": traceback.format_exc(),
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
        }


def _handle(req: dict) -> dict:
    rtype = req.get("type")
    if rtype == "ping":
        import bpy
        return {
            "status": "ok",
            "result": {
                "pong": True,
                "blender_version": list(bpy.app.version),
                "blender_version_string": bpy.app.version_string,
                "scene": bpy.context.scene.name if bpy.context.scene else None,
                "time": datetime.datetime.now().isoformat(),
            },
        }
    if rtype == "exec":
        return _handle_exec(req.get("params") or {})
    return {"status": "error", "message": f"unknown type: {rtype}"}


def main():
    import bpy  # noqa: F401  (ensures we are inside Blender)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(8)
    print(f"[bridge] Blender MCP bridge listening on {HOST}:{PORT}", flush=True)
    while True:
        try:
            conn, _ = srv.accept()
        except KeyboardInterrupt:
            break
        except Exception as exc:
            print(f"[bridge] accept error: {exc}", flush=True)
            continue
        try:
            conn.settimeout(3600)
            header = _recv_exactly(conn, 4)
            (length,) = struct.unpack(">I", header)
            if length > 64 * 1024 * 1024:
                raise ValueError("payload too large")
            payload = _recv_exactly(conn, length)
            req = json.loads(payload.decode("utf-8"))
            resp = _handle(req)
            resp["id"] = req.get("id")
            _send(conn, resp)
        except Exception:
            err = {"id": None, "status": "error", "message": traceback.format_exc()}
            try:
                _send(conn, err)
            except Exception:
                pass
        finally:
            try:
                conn.close()
            except Exception:
                pass


main()
