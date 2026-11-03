"""HTTP 发送契约与 requests 实装单测。

锁的设计约定（design.md §2.2 mys_http / landing §3.1 判据 2）：
- HttpSendResult.headers 保序保重复：同名字头两条不合并（Set-Cookie 双发逐条保留）；
- header_get 大小写不敏感、取首个匹配；
- RequestsHttpSend：redirect 禁用（302 原样返回不跟随）、Set-Cookie 全量
  收取（经 response.raw.headers 口径）、超时口径为模块常量 25s。
网络面全部走本机回环临时 HTTP 服务（port=0），零真实外网请求。
"""

import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import requests

from one_dragon.mys import mys_http
from one_dragon.mys.mys_http import HttpSendResult, RequestsHttpSend, header_get

#: 超时测试里服务端的故意延迟——远大于被收紧后的超时，且总耗时仍 <1s
_SLOW_DELAY_SECONDS: float = 1.2


def _make_handler_class(paths_seen: list[str]) -> type[BaseHTTPRequestHandler]:
    """按剧本应答的回环 handler 工厂；paths_seen 记录到达的服务端路径。"""

    class _LoopbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            paths_seen.append(self.path)
            if self.path == '/set-cookie-twice':
                self.send_response(200)
                # 同名头两条，验证传输层不合并（对齐登录响应多条 Set-Cookie 的实况）
                self.send_header('Set-Cookie', 'aliyungf_tc=first; Path=/')
                self.send_header('Set-Cookie', 'acw_tc=second; Path=/; HttpOnly')
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'ok')
            elif self.path == '/redirect':
                self.send_response(302)
                self.send_header('Location', '/final')
                self.end_headers()
            elif self.path == '/slow':
                time.sleep(_SLOW_DELAY_SECONDS)
                self.send_response(200)
                self.end_headers()
            else:
                self.send_response(200)
                self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            """静默回环服务访问日志（测试输出降噪；签名沿用基类）。"""

    return _LoopbackHandler


@pytest.fixture
def loopback_server() -> Iterator[tuple[ThreadingHTTPServer, list[str]]]:
    """port=0 随机空闲端口的回环临时服务 + 服务端收到的路径记录。"""
    paths_seen: list[str] = []
    server = ThreadingHTTPServer(('127.0.0.1', 0), _make_handler_class(paths_seen))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, paths_seen
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_http_send_result_headers_keep_order_and_duplicates() -> None:
    """HttpSendResult 契约：headers 为元组列表，同名字头两条原样保留不合并（保序）。"""
    headers: list[tuple[str, str]] = [
        ('Content-Type', 'application/json'),
        ('Set-Cookie', 'a=1; Path=/'),
        ('Set-Cookie', 'b=2; Path=/'),
    ]
    result = HttpSendResult(status=200, headers=headers, body=b'')
    set_cookie_pairs = [(k, v) for k, v in result.headers if k.lower() == 'set-cookie']
    assert set_cookie_pairs == [('Set-Cookie', 'a=1; Path=/'), ('Set-Cookie', 'b=2; Path=/')]


def test_header_get_case_insensitive_first_match() -> None:
    """header_get：头名大小写不敏感；同名多条取首个；缺失返回 None。"""
    headers: list[tuple[str, str]] = [
        ('Set-Cookie', 'a=1'),
        ('set-cookie', 'b=2'),
        ('X-Rpc-Aigis', '{"session_id": "s"}'),
    ]
    assert header_get(headers, 'set-cookie') == 'a=1'
    assert header_get(headers, 'SET-COOKIE') == 'a=1'
    assert header_get(headers, 'x-rpc-aigis') == '{"session_id": "s"}'
    assert header_get(headers, 'X-Missing') is None


def test_requests_http_send_collects_all_set_cookies(
    loopback_server: tuple[ThreadingHTTPServer, list[str]],
) -> None:
    """RequestsHttpSend：多条 Set-Cookie 逐条取全（raw.headers 口径不合并）。"""
    server, _ = loopback_server
    send = RequestsHttpSend()
    result = send(f'http://127.0.0.1:{server.server_address[1]}/set-cookie-twice', 'GET', {}, None)
    set_cookie_pairs = [(k, v) for k, v in result.headers if k.lower() == 'set-cookie']
    assert len(set_cookie_pairs) == 2
    assert 'aliyungf_tc=first' in set_cookie_pairs[0][1]
    assert 'acw_tc=second' in set_cookie_pairs[1][1]
    assert result.status == 200
    assert result.body == b'ok'


def test_requests_http_send_does_not_follow_redirect(
    loopback_server: tuple[ThreadingHTTPServer, list[str]],
) -> None:
    """RequestsHttpSend：redirect 禁用——302 原样返回，不请求 Location 目标。"""
    server, paths_seen = loopback_server
    send = RequestsHttpSend()
    result = send(f'http://127.0.0.1:{server.server_address[1]}/redirect', 'GET', {}, None)
    assert result.status == 302
    assert paths_seen == ['/redirect']


def test_requests_http_send_timeout_uses_module_constant(
    loopback_server: tuple[ThreadingHTTPServer, list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """超时口径 = 模块常量 REQUEST_TIMEOUT_SECONDS（真实运行 25s；测试收紧验证生效）。"""
    server, _ = loopback_server
    monkeypatch.setattr(mys_http, 'REQUEST_TIMEOUT_SECONDS', 0.3)
    send = RequestsHttpSend()
    with pytest.raises(requests.exceptions.Timeout):
        send(f'http://127.0.0.1:{server.server_address[1]}/slow', 'GET', {}, None)


def test_request_timeout_seconds_value_locked() -> None:
    """超时常量真值锁定 25 秒（miyoushe-api-flow.md §4.2 口径；防误改回退——
    上一条的收紧验证依赖「常量默认 25、monkeypatch 收紧」的分层不被破坏）。"""
    assert mys_http.REQUEST_TIMEOUT_SECONDS == 25.0
