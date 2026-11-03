"""设备身份单测：device_id 持久化与损坏重生成、getFp 四判据、缓存与冷却降级。

锁的设计约定（design.md §2.2 mys_device / landing §3.1 判据 4/5）：
- device_id 持久化往返（device.json 存在即用，正常路径严禁轮换）；
- 文件损坏（解析失败/字段非法）重生成 + warning 留痕（唯一例外）；
- getFp 四判据（HTTP 2xx + retcode==0 + data.code==200 + fp 正则）任一不过
  即降级不带头；请求体为 20 字段固定指纹模板（IDFV=device_id 大写）；
- fp 内存缓存 24h（命中不二次请求）；失败 30 分钟冷却（冷却期降级不带头）。
网络面全部 mock http_send，零真实请求；落盘走 pytest tmp_path。
"""

import json
import logging
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from one_dragon.mys.mys_const import GET_FP_URL
from one_dragon.mys.mys_device import (
    DEVICE_FP_HEADER,
    DEVICE_ID_HEADER,
    DEVICE_PLATFORM_HEADER,
    DeviceIdentity,
)
from one_dragon.mys.mys_http import HttpSendResult
from one_dragon.mys.mys_session import DEVICE_FILE_NAME, SessionStore
from one_dragon.utils.log_utils import log as framework_log

_VALID_DEVICE_ID = '123e4567-e89b-12d3-a456-426614174000'
_VALID_FP = 'abcdef123456'


class _ListHandler(logging.Handler):
    """捕获框架日志的列表 handler（断言 warning 留痕用）。"""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@contextmanager
def _capture_warnings() -> Iterator[_ListHandler]:
    """临时挂到框架 logger 的 warning 捕获器（用完摘除，不污染其他测试）。"""
    handler = _ListHandler()
    framework_log.addHandler(handler)
    try:
        yield handler
    finally:
        framework_log.removeHandler(handler)


class _FakeHttpSend:
    """剧本式假发送：按序返回预置结果，记录全部调用供断言（结果用尽后复用末项）。"""

    def __init__(self, *results: HttpSendResult) -> None:
        self.calls: list[tuple[str, str, dict[str, str], bytes | None]] = []
        self._results: list[HttpSendResult] = list(results)

    def __call__(
        self, url: str, method: str, headers: dict[str, str], body: bytes | None
    ) -> HttpSendResult:
        self.calls.append((url, method, headers, body))
        index = min(len(self.calls) - 1, len(self._results) - 1)
        return self._results[index]


def _fp_result(
    status: int = 200,
    retcode: int = 0,
    inner_code: int = 200,
    device_fp: str | None = _VALID_FP,
) -> HttpSendResult:
    """构造一个 getFp 假响应（默认全判据通过形态，按需破坏单条判据）。"""
    data: dict = {'code': inner_code}
    if device_fp is not None:
        data['device_fp'] = device_fp
    body = json.dumps({'retcode': retcode, 'message': 'OK', 'data': data})
    return HttpSendResult(
        status=status,
        headers=[('Content-Type', 'application/json')],
        body=body.encode('utf-8'),
    )


@pytest.fixture
def store(tmp_path: Path) -> SessionStore:
    return SessionStore(tmp_path, threading.Lock())


def test_device_id_roundtrip_not_rotated(store: SessionStore) -> None:
    """device_id 持久化：存量合法 id 即用且不轮换；两次构建身份一致（设备锚稳定）。"""
    store.save_device(_VALID_DEVICE_ID)
    fake = _FakeHttpSend(_fp_result())
    headers = DeviceIdentity(store, fake).get_headers()
    assert headers[DEVICE_ID_HEADER] == _VALID_DEVICE_ID
    assert store.load_device() == _VALID_DEVICE_ID
    headers_again = DeviceIdentity(store, _FakeHttpSend(_fp_result())).get_headers()
    assert headers_again[DEVICE_ID_HEADER] == _VALID_DEVICE_ID


def test_device_id_missing_first_run_generates_silently(store: SessionStore) -> None:
    """首次运行：文件缺失静默生成 uuid 并落盘（无 warning——首建不是轮换）。"""
    assert store.load_device() is None
    with _capture_warnings() as captured:
        device_id = DeviceIdentity(store, _FakeHttpSend(_fp_result())).get_headers()[DEVICE_ID_HEADER]
    assert uuid.UUID(device_id)  # 合法 uuid 形态
    assert store.load_device() == device_id
    assert captured.records == []


@pytest.mark.parametrize(
    'corrupt_bytes',
    [
        pytest.param(b'not json at all', id='parse-failure'),
        pytest.param(b'{"schema_version": 1, "device_id": 12345}', id='field-invalid'),
    ],
)
def test_device_id_corrupt_regenerated_with_warning(
    tmp_path: Path, corrupt_bytes: bytes
) -> None:
    """损坏件重生成 + warning 留痕：新 uuid 落盘（唯一例外路径）。"""
    store = SessionStore(tmp_path, threading.Lock())
    (tmp_path / DEVICE_FILE_NAME).write_bytes(corrupt_bytes)
    with _capture_warnings() as captured:
        device_id = DeviceIdentity(store, _FakeHttpSend(_fp_result())).get_headers()[DEVICE_ID_HEADER]
    assert uuid.UUID(device_id)
    assert store.load_device() == device_id
    assert any(
        record.levelno == logging.WARNING and 'device_id' in record.getMessage()
        for record in captured.records
    )


def test_device_id_invalid_uuid_string_regenerated_with_warning(store: SessionStore) -> None:
    """存量 device_id 是字符串但不合 uuid 形态：同样按损坏重生成 + warning。"""
    store.save_device('deadbeef-not-a-uuid')
    with _capture_warnings() as captured:
        device_id = DeviceIdentity(store, _FakeHttpSend(_fp_result())).get_headers()[DEVICE_ID_HEADER]
    assert uuid.UUID(device_id)
    assert device_id != 'deadbeef-not-a-uuid'
    assert any(
        record.levelno == logging.WARNING and 'device_id' in record.getMessage()
        for record in captured.records
    )


def test_getfp_success_headers_and_body_template(store: SessionStore) -> None:
    """getFp 成功路径：四判据全过 → 设备头带 fp；请求体为 20 字段模板 + 大写 device_id。"""
    store.save_device(_VALID_DEVICE_ID)
    fake = _FakeHttpSend(_fp_result())
    headers = DeviceIdentity(store, fake).get_headers()
    assert headers[DEVICE_FP_HEADER] == _VALID_FP
    assert headers[DEVICE_ID_HEADER] == _VALID_DEVICE_ID
    assert headers[DEVICE_PLATFORM_HEADER] == '4'

    assert len(fake.calls) == 1
    url, method, sent_headers, body = fake.calls[0]
    assert url == GET_FP_URL
    assert method == 'POST'
    assert sent_headers['Referer'] == 'https://act.mihoyo.com/'
    request_body = json.loads((body or b'').decode('utf-8'))
    assert request_body['device_id'] == _VALID_DEVICE_ID.upper()
    assert request_body['platform'] == '1'
    assert request_body['app_name'] == 'bbs_cn'
    assert request_body['device_fp'] == '38d7ee834d1e9'
    ext_fields = json.loads(request_body['ext_fields'])
    assert len(ext_fields) == 20
    assert ext_fields['IDFV'] == _VALID_DEVICE_ID.upper()
    assert ext_fields['model'] == 'iPhone12,5'
    assert ext_fields['screenSize'] == '414×896'


def test_getfp_cache_hit_no_second_request(store: SessionStore) -> None:
    """24h 内存缓存：连续两次 get_headers 只发起一次 getFp，fp 均在场。"""
    fake = _FakeHttpSend(_fp_result())
    identity = DeviceIdentity(store, fake)
    first = identity.get_headers()
    second = identity.get_headers()
    assert len(fake.calls) == 1
    assert first[DEVICE_FP_HEADER] == second[DEVICE_FP_HEADER] == _VALID_FP


@pytest.mark.parametrize(
    'failure_kwargs',
    [
        pytest.param({'status': 500}, id='http-not-ok'),
        pytest.param({'retcode': -1}, id='retcode-nonzero'),
        pytest.param({'inner_code': 403}, id='inner-code-not-200'),
        pytest.param({'device_fp': 'abcde'}, id='fp-too-short'),
        pytest.param({'device_fp': 'has space!'}, id='fp-bad-chars'),
    ],
)
def test_getfp_criteria_failure_degrades_without_fp_header(
    store: SessionStore, failure_kwargs: dict
) -> None:
    """getFp 四判据：任一判据不过 → fp 置空降级，设备头不带 x-rpc-device_fp。"""
    fake = _FakeHttpSend(_fp_result(**failure_kwargs))
    headers = DeviceIdentity(store, fake).get_headers()
    assert DEVICE_FP_HEADER not in headers
    assert headers[DEVICE_ID_HEADER] == store.load_device()
    assert len(fake.calls) == 1


def test_getfp_cooldown_degrades_without_second_request(store: SessionStore) -> None:
    """失败冷却：获取失败后 30 分钟内不再请求，期间持续降级不带头。"""
    fake = _FakeHttpSend(_fp_result(status=500))
    identity = DeviceIdentity(store, fake)
    first = identity.get_headers()
    second = identity.get_headers()
    assert DEVICE_FP_HEADER not in first
    assert DEVICE_FP_HEADER not in second
    assert len(fake.calls) == 1  # 冷却期内不二次请求
