"""SessionStore 全原语单测（落盘全部走 pytest tmp_path，零真实副作用）。

锁的设计约定（design.md §2.2 mys_session / landing §3.1 判据 3/4）：
- session.json 字段级 schema：``{schema_version, saved_at, expired(true|null),
  cookies}``；
- save_cookies 滚动续存保留 expired 标记；save_session_full 整体覆盖且产物
  无 expired 键；mark_expired 合并写入、文件缺失幂等无操作；
- clear 删 session.json 与 role.json、保留 device.json；
- 文件缺失/损坏时读取原语返回空态（load_cookies={} / load_role=None /
  load_device=None）。
"""

import json
import threading
from pathlib import Path

import pytest

from one_dragon.mys.mys_session import (
    DEVICE_FILE_NAME,
    ROLE_FILE_NAME,
    SESSION_EXPIRED_RETCODES,
    SESSION_FILE_NAME,
    MysApiError,
    MysSessionExpired,
    SessionStore,
)


@pytest.fixture
def store(tmp_path: Path) -> SessionStore:
    return SessionStore(tmp_path, threading.Lock())


@pytest.fixture
def session_dir(tmp_path: Path) -> Path:
    return tmp_path


def _read_store_json(session_dir: Path, name: str) -> dict:
    """测试侧直接读文件（独立于被测读取原语，锁的是落盘产物本身）。"""
    return json.loads((session_dir / name).read_bytes().decode('utf-8'))


def test_save_session_full_writes_schema_without_expired(
    store: SessionStore, session_dir: Path
) -> None:
    """save_session_full：产物含 schema 三字段且**无 expired 键**，cookies 原样落盘。"""
    store.save_session_full({'ltoken_v2': 'abc', 'account_mid_v2': 'xyz'})
    data = _read_store_json(session_dir, SESSION_FILE_NAME)
    assert data['schema_version'] == 1
    assert data['saved_at']  # ISO8601 字符串在场
    assert 'expired' not in data
    assert data['cookies'] == {'ltoken_v2': 'abc', 'account_mid_v2': 'xyz'}
    assert store.load_cookies() == {'ltoken_v2': 'abc', 'account_mid_v2': 'xyz'}
    assert store.is_expired() is False


def test_save_cookies_rolling_keeps_expired_mark(
    store: SessionStore, session_dir: Path
) -> None:
    """save_cookies 滚动续存：替换 cookies、更新 saved_at，**保留既有 expired 标记**。"""
    store.save_session_full({'ltoken_v2': 'old'})
    store.mark_expired()
    store.save_cookies({'ltoken_v2': 'new', 'acw_tc': 'rolling'})
    data = _read_store_json(session_dir, SESSION_FILE_NAME)
    assert data['expired'] is True
    assert data['cookies'] == {'ltoken_v2': 'new', 'acw_tc': 'rolling'}
    assert store.is_expired() is True


def test_save_cookies_without_prior_file_writes_null_expired(
    store: SessionStore, session_dir: Path
) -> None:
    """save_cookies 无既有文件：expired 落 null（schema 的 true|null 缺省态），视为未过期。"""
    store.save_cookies({'a': '1'})
    data = _read_store_json(session_dir, SESSION_FILE_NAME)
    assert data['expired'] is None
    assert store.is_expired() is False


def test_save_session_full_clears_expired_mark(
    store: SessionStore, session_dir: Path
) -> None:
    """先 mark_expired 再 save_session_full：整体覆盖后产物无 expired 键（标记消失）。"""
    store.save_cookies({'a': '1'})
    store.mark_expired()
    store.save_session_full({'a': '2'})
    data = _read_store_json(session_dir, SESSION_FILE_NAME)
    assert 'expired' not in data
    assert store.is_expired() is False


def test_mark_expired_merges_and_keeps_cookies(
    store: SessionStore, session_dir: Path
) -> None:
    """mark_expired：合并写入 expired=true，cookies 与其余字段原样保留。"""
    store.save_session_full({'ltoken_v2': 'keep'})
    store.mark_expired()
    data = _read_store_json(session_dir, SESSION_FILE_NAME)
    assert data['expired'] is True
    assert data['cookies'] == {'ltoken_v2': 'keep'}


def test_mark_expired_missing_file_is_noop(store: SessionStore, session_dir: Path) -> None:
    """mark_expired：文件缺失时幂等无操作（不创建文件）。"""
    store.mark_expired()
    assert not (session_dir / SESSION_FILE_NAME).exists()
    assert store.is_expired() is False


def test_clear_removes_session_and_role_keeps_device(
    store: SessionStore, session_dir: Path
) -> None:
    """clear：删 session.json 与 role.json，device.json 保留（设备锚不随登出轮换）。"""
    store.save_session_full({'a': '1'})
    store.save_role({'role_id': '1001', 'server': 'prod_gf_cn'})
    store.save_device('123e4567-e89b-12d3-a456-426614174000')
    store.clear()
    assert not (session_dir / SESSION_FILE_NAME).exists()
    assert not (session_dir / ROLE_FILE_NAME).exists()
    assert (session_dir / DEVICE_FILE_NAME).exists()
    assert store.load_device() == '123e4567-e89b-12d3-a456-426614174000'
    assert store.load_cookies() == {}
    assert store.load_role() is None


def test_load_cookies_missing_or_corrupt_returns_empty(
    store: SessionStore, session_dir: Path
) -> None:
    """load_cookies：文件缺失返回空 dict；损坏（非合法 JSON）同样返回空 dict。"""
    assert store.load_cookies() == {}
    (session_dir / SESSION_FILE_NAME).write_bytes(b'{oops not json')
    assert store.load_cookies() == {}


def test_load_cookies_filters_non_string_values(
    store: SessionStore, session_dir: Path
) -> None:
    """load_cookies：非字符串值剔除（与参考实现 loadSession 过滤口径一致；
    JSON 解析后键恒为字符串，键维度无需过滤）。"""
    (session_dir / SESSION_FILE_NAME).write_bytes(
        json.dumps({'schema_version': 1, 'cookies': {'ok': 'v', 'k': None, 'n': 3}}).encode('utf-8')
    )
    assert store.load_cookies() == {'ok': 'v'}


def test_role_roundtrip_and_missing(
    store: SessionStore, session_dir: Path
) -> None:
    """save_role/load_role：往返一致；缺失返回 None。"""
    assert store.load_role() is None
    role = {'role_id': '100000001', 'server': 'prod_gf_cn'}
    store.save_role(role)
    assert store.load_role() == role
    assert _read_store_json(session_dir, ROLE_FILE_NAME)['role_id'] == '100000001'


def test_device_roundtrip_and_missing(
    store: SessionStore, session_dir: Path
) -> None:
    """save_device/load_device：往返一致；文件缺失返回 None（首次运行语义）。"""
    assert store.load_device() is None
    store.save_device('123e4567-e89b-12d3-a456-426614174000')
    assert store.load_device() == '123e4567-e89b-12d3-a456-426614174000'


def test_load_device_corrupt_file_signals_damage(
    store: SessionStore, session_dir: Path
) -> None:
    """load_device：文件存在但损坏（解析失败/字段非法）返回空串哨兵——
    与缺失（None）可区分，供设备模块走「重生成 + warning」分支。"""
    (session_dir / DEVICE_FILE_NAME).write_bytes(b'not json at all')
    assert store.load_device() == ''
    (session_dir / DEVICE_FILE_NAME).write_bytes(
        json.dumps({'schema_version': 1, 'device_id': 12345}).encode('utf-8')
    )
    assert store.load_device() == ''


def test_session_expired_contract() -> None:
    """会话失效契约（跨阶段消费面，定案修订只改 SESSION_EXPIRED_RETCODES 一处）：
    失效码常量值锁定 {10001, -100}；MysSessionExpired 是 MysApiError 子类，
    code/message 可结构化读取（3.2 request 映射、3.4 信封翻译的依据）。"""
    assert frozenset({10001, -100}) == SESSION_EXPIRED_RETCODES
    expired = MysSessionExpired(10001, 'Please login')
    assert isinstance(expired, MysApiError)
    assert expired.code == 10001
    assert expired.message == 'Please login'
