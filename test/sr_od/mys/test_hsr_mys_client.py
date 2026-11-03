"""HsrMysClient 单测（landing §3.4 判据逐条）。

全部走 mock 管线（剧本式假 http_send / MagicMock client），零真实网络；
落盘走 pytest tmp_path。锁的判据（landing §3.4 / design.md §2.3 / §2.5 契约 5）：

- 过期短路：``store.is_expired()`` 直接 ``MysSessionExpired``，不发任何请求；
- 角色自动发现：绝对 URL 形态（binding 域 ROLE_LIST_URL + game_biz=hkrpg_cn）、
  is_chosen 优先否则首个、role_id 字符串化（实测响应 game_uid 为字符串，此处
  fixture 故意用 int 以锁死 ``str()`` 强制转换）、role.json 缓存写入；
- role.json 缓存命中：不发角色发现请求，server 取缓存值；
- 冻结字段集映射：index 快照 fixture（test/fixtures/mys/，实测结构固化）映射出
  ``HsrCharacter``——字段集增删即本文件失败（契约 §2.5-5），icon 等大字段不透传，
  equip 缺失（null）映射 None。
"""

import json
import threading
from dataclasses import asdict, fields
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from one_dragon.mys.mys_client import MysClient
from one_dragon.mys.mys_const import (
    GAME_RECORD_BASE_URL,
    GET_FP_URL,
    ROLE_LIST_URL,
)
from one_dragon.mys.mys_device import DeviceIdentity
from one_dragon.mys.mys_http import HttpSendResult
from one_dragon.mys.mys_session import (
    ROLE_FILE_NAME,
    SESSION_FILE_NAME,
    MysApiError,
    MysSessionExpired,
    SessionStore,
)
from sr_od.mys.hsr_mys_client import (
    ConeSummary,
    HsrCharacter,
    HsrMysClient,
)

#: index 实测结构快照（fixture 固化进测试仓，摆脱易失 trace 依赖）
INDEX_SNAPSHOT_PATH: Path = (
    Path(__file__).resolve().parents[2] / 'fixtures' / 'mys' / 'hkrpg_index_snapshot.json'
)

_VALID_FP = 'abcdef123456'


class _ScriptedHttpSend:
    """剧本式假发送（零网络，与 test_mys_client.py 同款手法）：按「URL 前缀 →
    响应」注册表首匹配分流，未命中即断言失败；记录全部调用供断言。"""

    def __init__(self, *routes: tuple[str, HttpSendResult]) -> None:
        self.calls: list[tuple[str, str, dict[str, str], bytes | None]] = []
        self._routes: dict[str, HttpSendResult] = dict(routes)

    def add_route(self, *routes: tuple[str, HttpSendResult]) -> None:
        for route_prefix, result in routes:
            self._routes[route_prefix] = result

    def __call__(
        self, url: str, method: str, headers: dict[str, str], body: bytes | None
    ) -> HttpSendResult:
        self.calls.append((url, method, dict(headers), body))
        for route_prefix, result in self._routes.items():
            if url.startswith(route_prefix):
                return result
        raise AssertionError(f'剧本外请求（测试剧本缺路由）: {method} {url}')

    def calls_for(self, prefix: str) -> list[tuple[str, str, dict[str, str], bytes | None]]:
        return [call for call in self.calls if call[0].startswith(prefix)]


def _json_result(payload: dict) -> HttpSendResult:
    return HttpSendResult(status=200, headers=[], body=json.dumps(payload).encode('utf-8'))


def _fp_ok_result() -> HttpSendResult:
    body = json.dumps({'retcode': 0, 'message': 'OK', 'data': {'code': 200, 'device_fp': _VALID_FP}})
    return HttpSendResult(status=200, headers=[], body=body.encode('utf-8'))


def _index_ok_result(data: dict) -> HttpSendResult:
    return _json_result({'retcode': 0, 'message': 'OK', 'data': data})


def _roles_result(roles: list[dict]) -> HttpSendResult:
    return _json_result({'retcode': 0, 'message': 'OK', 'data': {'list': roles}})


def _fixture_index_data() -> dict:
    """读 index 快照 fixture 的 data 字段（实测结构，含带/不带光锥各一）。"""
    snapshot = json.loads(INDEX_SNAPSHOT_PATH.read_bytes().decode('utf-8'))
    return snapshot['data']


def _hsr_role(game_uid: int | str, is_chosen: bool) -> dict:
    """崩铁国服角色条目（键集照实测响应：game_biz/game_uid/region/is_chosen 等；
    game_uid 形态故意可变——锁死 role_id 一律字符串化）。"""
    return {
        'game_biz': 'hkrpg_cn',
        'game_uid': game_uid,
        'region': 'prod_gf_cn',
        'region_name': '星穹列车',
        'nickname': 'fixture-nickname',
        'level': 60,
        'is_chosen': is_chosen,
        'is_official': True,
        'is_banned': False,
        'unmask': [],
    }


def _genshin_role() -> dict:
    """原神角色条目（过滤判据的反例：不进崩铁定位）。"""
    return {
        'game_biz': 'hk4e_cn',
        'game_uid': '147261583',
        'region': 'cn_gf01',
        'region_name': '天空岛',
        'nickname': 'fixture-nickname',
        'level': 60,
        'is_chosen': True,
        'is_official': True,
        'is_banned': False,
        'unmask': [],
    }


@pytest.fixture
def store(tmp_path: Path) -> SessionStore:
    return SessionStore(tmp_path, threading.Lock())


@pytest.fixture
def send() -> _ScriptedHttpSend:
    return _ScriptedHttpSend((GET_FP_URL, _fp_ok_result()))


@pytest.fixture
def client(store: SessionStore, send: _ScriptedHttpSend) -> MysClient:
    device = DeviceIdentity(store, send)
    return MysClient(store, device, send)


@pytest.fixture
def hsr(client: MysClient, store: SessionStore) -> HsrMysClient:
    return HsrMysClient(client, store)


# ---- 过期短路 ----


def test_expired_short_circuit_raises_without_any_request(
    store: SessionStore, hsr: HsrMysClient, send: _ScriptedHttpSend
) -> None:
    """is_expired() 为真 → 直接 MysSessionExpired，不发请求（design.md §2.3
    判据 1：不发起注定失败的请求）。"""
    store.save_cookies({'stale': 'x'})  # 会话文件存在是标记过期的前提
    store.mark_expired()

    with pytest.raises(MysSessionExpired):
        hsr.get_characters()
    assert send.calls == []  # 零请求


# ---- 角色自动发现与缓存 ----


def test_auto_discovery_absolute_url_chosen_first_and_role_cache(
    tmp_path: Path, store: SessionStore, hsr: HsrMysClient, send: _ScriptedHttpSend
) -> None:
    """无缓存自动发现：绝对 URL 形态（ROLE_LIST_URL 原样直用 + game_biz 查询）、
    is_chosen 优先（原神角色与未选中崩铁角色都不该被选）、role_id 字符串化
    （fixture 故意给 int）、role.json 写入缓存。"""
    send.add_route(
        (
            ROLE_LIST_URL,
            _roles_result([
                _genshin_role(),
                _hsr_role(100000001, is_chosen=False),
                _hsr_role(100000002, is_chosen=True),
            ]),
        ),
        (GAME_RECORD_BASE_URL + 'hkrpg/api/index', _index_ok_result(_fixture_index_data())),
    )
    characters = hsr.get_characters()

    # 角色发现走绝对 URL（不落 game_record 基座），query 带 game_biz=hkrpg_cn
    role_calls = send.calls_for(ROLE_LIST_URL)
    assert len(role_calls) == 1
    assert role_calls[0][0] == f'{ROLE_LIST_URL}?game_biz=hkrpg_cn'

    # is_chosen 优先：选中 100000002（字符串化后），server 取发现的 region
    index_calls = send.calls_for(GAME_RECORD_BASE_URL + 'hkrpg/api/index')
    assert index_calls[0][0] == (
        GAME_RECORD_BASE_URL + 'hkrpg/api/index?role_id=100000002&server=prod_gf_cn'
    )
    assert store.load_role() == {'role_id': '100000002', 'server': 'prod_gf_cn'}

    assert len(characters) == 2
    assert characters[0].name == '藿藿'


def test_auto_discovery_falls_back_to_first_hsr_role(
    hsr: HsrMysClient, store: SessionStore, send: _ScriptedHttpSend
) -> None:
    """无 is_chosen 真值的崩铁角色 → 取首个（is_chosen 优先否则首个）。"""
    send.add_route(
        (
            ROLE_LIST_URL,
            _roles_result([_hsr_role('900000001', is_chosen=False), _hsr_role('900000002', is_chosen=False)]),
        ),
        (GAME_RECORD_BASE_URL, _index_ok_result(_fixture_index_data())),
    )
    hsr.get_characters()

    index_url = send.calls_for(GAME_RECORD_BASE_URL)[0][0]
    assert 'role_id=900000001' in index_url
    assert store.load_role() == {'role_id': '900000001', 'server': 'prod_gf_cn'}


def test_role_cache_skips_discovery_and_uses_cached_server(
    store: SessionStore, hsr: HsrMysClient, send: _ScriptedHttpSend
) -> None:
    """role.json 缓存命中：零角色发现请求，server 取缓存值（不硬编码）。"""
    store.save_role({'role_id': '42', 'server': 'prod_gf_cn'})
    send.add_route(
        (GAME_RECORD_BASE_URL + 'hkrpg/api/index', _index_ok_result(_fixture_index_data())),
    )
    hsr.get_characters()

    assert send.calls_for(ROLE_LIST_URL) == []  # 缓存命中不发现
    index_url = send.calls_for(GAME_RECORD_BASE_URL + 'hkrpg/api/index')[0][0]
    assert index_url == GAME_RECORD_BASE_URL + 'hkrpg/api/index?role_id=42&server=prod_gf_cn'


def test_corrupted_role_cache_falls_back_to_discovery(
    store: SessionStore, hsr: HsrMysClient, send: _ScriptedHttpSend
) -> None:
    """缓存损坏（字段非法）视同无缓存：重发现并覆盖缓存。"""
    (store._session_dir / ROLE_FILE_NAME).write_bytes(b'{"role_id": 123}')  # 类型非法
    send.add_route(
        (ROLE_LIST_URL, _roles_result([_hsr_role('777', is_chosen=True)])),
        (GAME_RECORD_BASE_URL, _index_ok_result(_fixture_index_data())),
    )
    hsr.get_characters()

    assert len(send.calls_for(ROLE_LIST_URL)) == 1  # 坏缓存触发重发现
    assert store.load_role() == {'role_id': '777', 'server': 'prod_gf_cn'}


def test_discovery_without_hsr_role_raises_and_keeps_no_cache(
    hsr: HsrMysClient, store: SessionStore, tmp_path: Path, send: _ScriptedHttpSend
) -> None:
    """发现失败（无崩铁国服角色）→ MysApiError，且不写 role.json。"""
    send.add_route((ROLE_LIST_URL, _roles_result([_genshin_role()])))

    with pytest.raises(MysApiError):
        hsr.get_characters()
    assert not (tmp_path / ROLE_FILE_NAME).exists()


# ---- 冻结字段集映射（mock client，聚焦映射本身）----


def test_frozen_field_set_mapping_from_index_snapshot(tmp_path: Path) -> None:
    """index 快照 fixture → HsrCharacter 冻结字段集（契约 §2.5-5：字段增删即
    判据失败）；icon/figure_path/element_id/is_chosen 等实测在场字段不透传；
    equip null → None。"""
    snapshot = json.loads(INDEX_SNAPSHOT_PATH.read_bytes().decode('utf-8'))
    mock_client = MagicMock(spec=MysClient)
    mock_client.request.return_value = snapshot['data']
    store = SessionStore(tmp_path, threading.Lock())
    store.save_role({'role_id': '1', 'server': 'prod_gf_cn'})
    hsr = HsrMysClient(mock_client, store)

    characters = hsr.get_characters()

    # 字段集冻结：HsrCharacter 与 ConeSummary 的字段名集合逐字对账
    assert {f.name for f in fields(HsrCharacter)} == {
        'id', 'name', 'level', 'rarity', 'rank', 'element', 'base_type', 'equip',
    }
    assert {f.name for f in fields(ConeSummary)} == {'name', 'level', 'rank', 'rarity'}

    first, second = characters
    assert first == HsrCharacter(
        id=1217, name='藿藿', level=60, rarity=5, rank=1,
        element='wind', base_type=7,
        equip=ConeSummary(name='惊魂夜', level=50, rank=1, rarity=5),
    )
    assert second == HsrCharacter(
        id=1312, name='米沙', level=80, rarity=4, rank=6,
        element='ice', base_type=1, equip=None,  # 实测未装备光锥形态
    )
    # 大体积字段不透传：序列化产物只有冻结字段集
    expected_keys = {'id', 'name', 'level', 'rarity', 'rank', 'element', 'base_type', 'equip'}
    for character in characters:
        assert set(asdict(character).keys()) == expected_keys
    mock_client.request.assert_called_once_with(
        'hkrpg/api/index', {'role_id': '1', 'server': 'prod_gf_cn'}
    )


def test_session_file_survives_expired_short_circuit(
    tmp_path: Path, store: SessionStore, hsr: HsrMysClient
) -> None:
    """过期短路不清任何落盘文件（design.md §2.6：会话失效不清数据）。"""
    store.save_session_full({'ltoken_v2': 'keep'})
    store.save_role({'role_id': '1', 'server': 'prod_gf_cn'})
    store.mark_expired()

    with pytest.raises(MysSessionExpired):
        hsr.get_characters()

    saved = json.loads((tmp_path / SESSION_FILE_NAME).read_bytes().decode('utf-8'))
    assert saved['expired'] is True
    assert saved['cookies'] == {'ltoken_v2': 'keep'}
    assert (tmp_path / ROLE_FILE_NAME).exists()
