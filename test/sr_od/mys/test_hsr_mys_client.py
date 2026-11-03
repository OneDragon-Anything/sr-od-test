"""HsrMysClient 单测（mys-account-mcp landing §3.4 / mys-roster-detail design §2-3/4 判据）。

全部走 mock 管线（剧本式假 http_send / MagicMock client），零真实网络；
落盘走 pytest tmp_path。锁的判据：

- 过期短路：``store.is_expired()`` 直接 ``MysSessionExpired``，不发任何请求
  （v1 ``get_characters`` 与 v2 ``get_characters_detail`` 同管线同判据）；
- 角色自动发现：绝对 URL 形态（binding 域 ROLE_LIST_URL + game_biz=hkrpg_cn）、
  is_chosen 优先否则首个、role_id 字符串化（实测响应 game_uid 为字符串，此处
  fixture 故意用 int 以锁死 ``str()`` 强制转换）、role.json 缓存写入；
- role.json 缓存命中：不发角色发现请求，server 取缓存值；
- 冻结字段集映射：index 快照 fixture（test/fixtures/mys/，实测结构固化）映射出
  ``HsrCharacter`` v2（v1 八字段 + element_cn/base_type_cn，mys-roster-detail
  design.md §2 契约 2）——字段集增删即本文件失败，icon 等大字段不透传，
  equip 缺失（null）映射 None；
- 明细富映射（get_characters_detail，同端点单次请求）：CharacterDetail 及
  六个子结构冻结字段集逐字对账（契约 3/4，增删即失败）；词条/面板 name_cn
  两路解析（fixture 动态词典 + 快照兜底）；主词条部位校验哨兵 warning
  （畸形数据不中断映射）；空遗器/无光锥/缺件/星魂未解锁等形态透传。
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
from sr_od.mys import hsr_mys_client
from sr_od.mys.hsr_mys_client import (
    CharacterDetail,
    ConeSummary,
    HsrCharacter,
    HsrMysClient,
    HsrPanelProperty,
    HsrPropertyEntry,
    HsrRank,
    HsrRelic,
    HsrSkill,
    HsrSkillStage,
)

#: index 实测结构快照（fixture 固化进测试仓，摆脱易失 trace 依赖）
INDEX_SNAPSHOT_PATH: Path = (
    Path(__file__).resolve().parents[2] / 'fixtures' / 'mys' / 'hkrpg_index_snapshot.json'
)

#: index 全量明细自造样例（结构对照 2026-11-03 实测快照，id/名值自造不绑真账号）
DETAIL_SAMPLE_PATH: Path = (
    Path(__file__).resolve().parents[2] / 'fixtures' / 'mys' / 'hkrpg_index_detail_sample.json'
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
    """index 快照 fixture → HsrCharacter 冻结字段集（契约 §2.5-5 v1 八字段 +
    mys-roster-detail 契约 2 两中文字段：字段增删即判据失败）；icon/
    figure_path/element_id/is_chosen 等实测在场字段不透传；equip null → None；
    中文字段经码表查表填充（wind→风 / bt=7→丰饶，ice→冰 / bt=1→毁灭）。"""
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
        'element_cn', 'base_type_cn',
    }
    assert {f.name for f in fields(ConeSummary)} == {'name', 'level', 'rank', 'rarity'}

    first, second = characters
    assert first == HsrCharacter(
        id=1217, name='藿藿', level=60, rarity=5, rank=1,
        element='wind', base_type=7,
        equip=ConeSummary(name='惊魂夜', level=50, rank=1, rarity=5),
        element_cn='风', base_type_cn='丰饶',
    )
    assert second == HsrCharacter(
        id=1312, name='米沙', level=80, rarity=4, rank=6,
        element='ice', base_type=1, equip=None,  # 实测未装备光锥形态
        element_cn='冰', base_type_cn='毁灭',
    )
    # 大体积字段不透传：序列化产物只有冻结字段集
    expected_keys = {
        'id', 'name', 'level', 'rarity', 'rank', 'element', 'base_type', 'equip',
        'element_cn', 'base_type_cn',
    }
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


# ---- 明细富映射（get_characters_detail，同端点契约 3/4）----


def _fixture_detail_data() -> dict:
    """读明细自造样例 fixture 的 data 字段（结构对照实测快照，id/名值自造）。"""
    sample = json.loads(DETAIL_SAMPLE_PATH.read_bytes().decode('utf-8'))
    return sample['data']


def _detail_client(tmp_path: Path) -> tuple[HsrMysClient, MagicMock]:
    """明细样例直灌的 mock 客户端（role.json 缓存命中，零发现请求）。"""
    mock_client = MagicMock(spec=MysClient)
    mock_client.request.return_value = _fixture_detail_data()
    store = SessionStore(tmp_path, threading.Lock())
    store.save_role({'role_id': '1', 'server': 'prod_gf_cn'})
    return HsrMysClient(mock_client, store), mock_client


def test_detail_expired_short_circuit_raises_without_any_request(
    store: SessionStore, hsr: HsrMysClient, send: _ScriptedHttpSend
) -> None:
    """detail 复用 v1 过期短路：is_expired() 直接 MysSessionExpired，零请求
    （契约 5：detail 与 v1 会话语义完全一致）。"""
    store.save_cookies({'stale': 'x'})
    store.mark_expired()

    with pytest.raises(MysSessionExpired):
        hsr.get_characters_detail()
    assert send.calls == []


def test_detail_frozen_field_sets_locked(tmp_path: Path) -> None:
    """契约 3/4 冻结字段集逐字对账：CharacterDetail 15 字段 + 六个子结构
    字段名集合，任何增删即失败；HsrRank 不设 pos_cn（星魂 pos 是星魂序号，
    与遗器部位码撞值域——结构性防混淆）；序列化面 = 冻结字段集（icon/desc/
    figure_path/point_id 等不透传字段不出现在载荷）。"""
    hsr, _ = _detail_client(tmp_path)
    details = hsr.get_characters_detail()

    assert {f.name for f in fields(CharacterDetail)} == {
        'id', 'name', 'level', 'rarity', 'rank', 'element', 'element_cn',
        'base_type', 'base_type_cn', 'equip', 'relics', 'ornaments', 'ranks',
        'skills', 'properties',
    }
    assert {f.name for f in fields(HsrRelic)} == {
        'name', 'pos', 'pos_cn', 'rarity', 'level', 'main', 'subs',
    }
    assert {f.name for f in fields(HsrPropertyEntry)} == {'name_cn', 'value', 'times'}
    assert {f.name for f in fields(HsrRank)} == {'pos', 'name', 'desc', 'is_unlocked'}
    assert {f.name for f in fields(HsrSkill)} == {'name', 'level', 'is_activated', 'stages'}
    assert {f.name for f in fields(HsrSkillStage)} == {'name', 'desc', 'level'}
    assert {f.name for f in fields(HsrPanelProperty)} == {'name_cn', 'base', 'add', 'final'}

    # 序列化面（含嵌套展开）= 冻结字段集，不透传清单一个都不出现
    payload = asdict(details[0])
    assert set(payload.keys()) == {f.name for f in fields(CharacterDetail)}
    assert set(payload['equip'].keys()) == {f.name for f in fields(ConeSummary)}
    assert set(payload['relics'][0].keys()) == {f.name for f in fields(HsrRelic)}
    assert set(payload['relics'][0]['main'].keys()) == {f.name for f in fields(HsrPropertyEntry)}
    assert set(payload['ranks'][0].keys()) == {f.name for f in fields(HsrRank)}
    assert set(payload['skills'][0].keys()) == {f.name for f in fields(HsrSkill)}
    assert set(payload['skills'][0]['stages'][0].keys()) == {f.name for f in fields(HsrSkillStage)}
    assert set(payload['properties'][0].keys()) == {f.name for f in fields(HsrPanelProperty)}


def test_detail_mapping_full_form(tmp_path: Path) -> None:
    """甲（带光锥+4 遗器+2 饰品+星魂 2）逐字段整体对账：轻口径 10 字段与 v1
    同语义（中文字段查表填充）、遗器/饰品同构映射（pos_cn 部位查表）、星魂
    全量透传（未解锁层在列）、行迹取 remake 与分段文案、面板字符串数值透传；
    一次调用恰一次 index 请求（复用 v1 定位管线，不重复打接口）。"""
    hsr, mock_client = _detail_client(tmp_path)

    details = hsr.get_characters_detail()

    assert len(details) == 3
    assert details[0] == CharacterDetail(
        id=8001, name='样例角色甲', level=80, rarity=5, rank=2,
        element='fire', element_cn='火', base_type=2, base_type_cn='巡猎',
        equip=ConeSummary(name='样例光锥・晨昏线', level=80, rank=1, rarity=5),
        relics=[
            HsrRelic(
                name='样例遗器・甲一头盔', pos=1, pos_cn='头部', rarity=5, level=15,
                main=HsrPropertyEntry(name_cn='生命值', value='705', times=0),
                subs=[
                    HsrPropertyEntry(name_cn='防御力', value='59', times=3),
                    HsrPropertyEntry(name_cn='自造词条甲', value='5.2%', times=2),
                ],
            ),
            HsrRelic(
                name='样例遗器・甲二手套', pos=2, pos_cn='手部', rarity=5, level=12,
                main=HsrPropertyEntry(name_cn='攻击力', value='352', times=0),
                subs=[
                    HsrPropertyEntry(name_cn='暴击伤害', value='22.4%', times=4),
                    HsrPropertyEntry(name_cn='速度', value='9', times=2),
                ],
            ),
            HsrRelic(
                name='样例遗器・甲三胸甲', pos=3, pos_cn='躯干', rarity=5, level=15,
                main=HsrPropertyEntry(name_cn='暴击率', value='32.4%', times=0),
                subs=[HsrPropertyEntry(name_cn='治疗量加成', value='12.5%', times=1)],
            ),
            HsrRelic(
                name='样例遗器・甲四护靴', pos=4, pos_cn='脚部', rarity=5, level=15,
                main=HsrPropertyEntry(name_cn='速度', value='25', times=0),
                subs=[HsrPropertyEntry(name_cn='攻击力', value='14.3%', times=2)],
            ),
        ],
        ornaments=[
            HsrRelic(
                name='样例饰品・甲一位面球', pos=5, pos_cn='位面球', rarity=5, level=15,
                main=HsrPropertyEntry(name_cn='生命值', value='43.2%', times=0),
                subs=[HsrPropertyEntry(name_cn='防御力', value='42', times=3)],
            ),
            HsrRelic(
                name='样例饰品・甲二连结绳', pos=6, pos_cn='连结绳', rarity=5, level=15,
                main=HsrPropertyEntry(name_cn='击破特攻', value='64.8%', times=0),
                subs=[HsrPropertyEntry(name_cn='未知属性(pt=99)', value='3.1%', times=1)],
            ),
        ],
        ranks=[
            HsrRank(pos=1, name='样例星魂一', desc='样例星魂一描述。', is_unlocked=True),
            HsrRank(pos=2, name='样例星魂二', desc='样例星魂二描述。', is_unlocked=True),
            HsrRank(pos=3, name='样例星魂三', desc='样例星魂三描述。', is_unlocked=False),
            HsrRank(pos=4, name='样例星魂四', desc='样例星魂四描述。', is_unlocked=False),
            HsrRank(pos=5, name='样例星魂五', desc='样例星魂五描述。', is_unlocked=False),
            HsrRank(pos=6, name='样例星魂六', desc='样例星魂六描述。', is_unlocked=False),
        ],
        skills=[
            HsrSkill(
                name='普攻', level=7, is_activated=True,
                stages=[HsrSkillStage(name='样例普攻', desc='样例普攻描述。', level=7)],
            ),
            HsrSkill(
                name='战技', level=12, is_activated=True,
                stages=[HsrSkillStage(name='样例战技', desc='样例战技描述。', level=12)],
            ),
            HsrSkill(
                name='终结技', level=12, is_activated=True,
                stages=[
                    HsrSkillStage(name='样例终结技上段', desc='样例终结技上段描述。', level=12),
                    HsrSkillStage(name='样例终结技下段', desc='样例终结技下段描述。', level=12),
                ],
            ),
            HsrSkill(
                name='额外能力', level=1, is_activated=True,
                stages=[HsrSkillStage(name='样例额外能力', desc='样例额外能力描述。', level=1)],
            ),
        ],
        properties=[
            HsrPanelProperty(name_cn='生命值', base='2406', add='2005', final='4411'),
            HsrPanelProperty(name_cn='攻击力', base='1111', add='597', final='1708'),
            HsrPanelProperty(name_cn='防御力', base='996', add='349', final='1346'),
            HsrPanelProperty(name_cn='速度', base='99', add='42', final='141'),
            HsrPanelProperty(name_cn='暴击率', base='10.8%', add='0.0%', final='10.8%'),
            HsrPanelProperty(name_cn='暴击伤害', base='223.0%', add='0.0%', final='223.0%'),
            HsrPanelProperty(name_cn='火属性伤害提高', base='32.4%', add='0.0%', final='32.4%'),
            HsrPanelProperty(name_cn='击破特攻', base='16.8%', add='0.0%', final='16.8%'),
            HsrPanelProperty(name_cn='欢愉度', base='0.0%', add='0.0%', final='0.0%'),
            HsrPanelProperty(name_cn='治疗量加成', base='0.0%', add='0.0%', final='0.0%'),
            HsrPanelProperty(name_cn='能量恢复效率', base='134.4%', add='0.0%', final='134.4%'),
            HsrPanelProperty(name_cn='效果命中', base='0.0%', add='0.0%', final='0.0%'),
            HsrPanelProperty(name_cn='效果抵抗', base='10.0%', add='0.0%', final='10.0%'),
        ],
    )
    mock_client.request.assert_called_once_with(
        'hkrpg/api/index', {'role_id': '1', 'server': 'prod_gf_cn'}
    )


def test_detail_property_name_cn_dynamic_dict_and_snapshot_paths(tmp_path: Path) -> None:
    """词条/面板 name_cn 两路解析（design §3）：词典路——pt=98 快照无此码只
    可能来自 fixture 动态词典、pt=36 词典 name 带占位符经 property_name_relic
    规避；快照路——词典子集未收录的 53/57 直落硬编码快照；空名形态自造变体
    （pt=99 词典两字段全空）落「未知属性(pt=N)」终兜底；面板行同名规则。"""
    hsr, _ = _detail_client(tmp_path)
    first, _, third = hsr.get_characters_detail()

    # 词典路：pt=98 只存在于 fixture 词典（快照无此码，词典名优先命中）
    assert first.relics[0].subs[1] == HsrPropertyEntry(name_cn='自造词条甲', value='5.2%', times=2)
    # 词典路占位符规避：pt=36 词典 name='受治疗量提高#1[f1]%'，显示名取干净 relic 字段
    assert first.relics[2].subs[0] == HsrPropertyEntry(name_cn='治疗量加成', value='12.5%', times=1)
    # 快照路：fixture 词典子集未收录 53/57（键缺），直落硬编码快照
    assert first.relics[1].subs[0] == HsrPropertyEntry(name_cn='暴击伤害', value='22.4%', times=4)
    assert third.relics[0].subs[0] == HsrPropertyEntry(name_cn='效果抵抗', value='8.4%', times=2)
    # 空名形态自造变体：词典词条两字段全空 → 快照也无 → 终兜底文案
    assert first.ornaments[1].subs[0] == HsrPropertyEntry(
        name_cn='未知属性(pt=99)', value='3.1%', times=1
    )
    # 面板行同规则：pt=14 词典命中、pt=58 词典未收录走快照、丙面板 pt=98 词典命中
    assert first.properties[6] == HsrPanelProperty(
        name_cn='火属性伤害提高', base='32.4%', add='0.0%', final='32.4%'
    )
    assert first.properties[7] == HsrPanelProperty(
        name_cn='击破特攻', base='16.8%', add='0.0%', final='16.8%'
    )
    assert third.properties[3] == HsrPanelProperty(
        name_cn='自造词条甲', base='12.0%', add='0.0%', final='12.0%'
    )


def test_detail_mapping_degenerate_forms(tmp_path: Path) -> None:
    """乙（equip=null + 零遗器零饰品 + 星魂 0）与丙（缺件共 4 件）形态：
    equip None、relics/ornaments 空列表；缺件角色按实际件数映射；星魂 6 条
    全量透传（rank=0 全未解锁也照常在列，不做 is_unlocked 过滤）；未激活
    行迹与空副词条列表照常透传。"""
    hsr, _ = _detail_client(tmp_path)
    _, second, third = hsr.get_characters_detail()

    assert second.id == 8002
    assert second.name == '样例角色乙'
    assert second.equip is None
    assert second.relics == []
    assert second.ornaments == []
    assert second.element_cn == '冰'
    assert second.base_type_cn == '毁灭'
    assert [r.pos for r in second.ranks] == [1, 2, 3, 4, 5, 6]
    assert all(r.is_unlocked is False for r in second.ranks)

    # 丙：缺件 4 件（2 遗器 + 2 饰品），pos 是唯一部位键
    assert len(third.relics) == 2
    assert len(third.ornaments) == 2
    assert [r.pos for r in third.relics + third.ornaments] == [1, 3, 5, 6]
    assert third.ornaments[1].subs == []  # 空副词条列表照常映射
    assert third.equip == ConeSummary(name='样例光锥・晚风哨', level=40, rank=1, rarity=5)
    assert third.skills[1].name == '额外能力'
    assert third.skills[1].is_activated is False  # 未激活行迹状态透传
    assert third.element_cn == '风'
    assert third.base_type_cn == '同谐'


def test_detail_malformed_main_affix_warns_but_mapping_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """数据异常哨兵：丙头部主词条 pt=52（pos=1 配置集只认 27）→ warning 哨兵
    但映射继续，该件仍随明细返回（name_cn 照常查表）；全 fixture 恰此一条
    主词条告警（其余 9 件部位-词条组合均合法，不产生哨兵）。"""
    fake_log = MagicMock()
    monkeypatch.setattr(hsr_mys_client, 'log', fake_log)
    hsr, _ = _detail_client(tmp_path)

    details = hsr.get_characters_detail()

    third = details[2]
    assert third.relics[0].pos == 1
    assert third.relics[0].main == HsrPropertyEntry(name_cn='暴击率', value='18.0%', times=0)
    warning_texts = [str(call.args[0]) for call in fake_log.warning.call_args_list]
    affix_warnings = [text for text in warning_texts if '主词条校验未通过' in text]
    assert len(affix_warnings) == 1
    assert 'pos=1' in affix_warnings[0]
    assert 'pt=52' in affix_warnings[0]


# ---- 防御分支（avatar_list 缺失上抛 / 词典局部脏词条 / 数组键缺失退空）----


def _detail_client_with_payload(tmp_path: Path, data: dict) -> tuple[HsrMysClient, MagicMock]:
    """自定义 data 载荷直灌的 mock 客户端（防御分支剧本用变体构造，装配与
    _detail_client 相同：role.json 缓存命中，零角色发现请求）。"""
    mock_client = MagicMock(spec=MysClient)
    mock_client.request.return_value = data
    store = SessionStore(tmp_path, threading.Lock())
    store.save_role({'role_id': '1', 'server': 'prod_gf_cn'})
    return HsrMysClient(mock_client, store), mock_client


def test_detail_missing_avatar_list_raises_as_protocol_error(tmp_path: Path) -> None:
    """index 响应缺 avatar_list（其余字段在场）→ MysApiError 协议错误上抛，
    不静默返回空列表掩盖响应形态漂移；同一坏剧本下 v1 get_characters 与
    v2 get_characters_detail 同判（同一防线两口径一致）。"""
    data = _fixture_detail_data()
    del data['avatar_list']
    hsr, mock_client = _detail_client_with_payload(tmp_path, data)

    with pytest.raises(MysApiError, match='avatar_list'):
        hsr.get_characters_detail()
    with pytest.raises(MysApiError, match='avatar_list'):
        hsr.get_characters()
    assert mock_client.request.called  # 上抛发生在 index 请求之后，非短路误报


def test_detail_dirty_property_info_entries_skipped_mapping_continues(tmp_path: Path) -> None:
    """响应词典混入局部脏词条（值非 dict / 键非可归一整型）→ 归一时跳过而非
    抛错（_normalize_property_info 契约），整份明细照常映射：被脏词条占位的码
    查表自动退快照层（pt=7 → 治疗量加成），合法词典词条不受牵连（pt=98 照常
    命中）——词典局部异常既不中断映射也不污染其余码的三层查表。"""
    data = _fixture_detail_data()
    data['property_info']['7'] = '垃圾'  # 脏词条①：键可归一但值非 dict
    data['property_info']['abc'] = {  # 脏词条②：值合法但键归一不了 int
        'name': '不应出现的脏名',
        'property_name_relic': '不应出现的脏名',
    }
    hsr, _ = _detail_client_with_payload(tmp_path, data)

    details = hsr.get_characters_detail()  # 不抛异常是第一判据

    assert len(details) == 3
    # ① "7" 被跳过 → pt=7 词典 miss、落快照层（甲面板 pt=7 行，下标 9 与
    # 全量对账测试锁定的同一行序）
    assert details[0].properties[9] == HsrPanelProperty(
        name_cn='治疗量加成', base='0.0%', add='0.0%', final='0.0%'
    )
    # ② "abc" 被跳过 → 动态词典照常生效，pt=98 仍走词典路命中
    assert details[0].relics[0].subs[1] == HsrPropertyEntry(
        name_cn='自造词条甲', value='5.2%', times=2
    )


def test_detail_missing_array_keys_fall_back_to_empty_lists(tmp_path: Path) -> None:
    """角色条目缺 relics / ornaments 数组键（响应形态漂移面）→ 对应字段退空
    列表、映射不抛错不中断（_map_relic_list 契约）；另一侧数组照常映射作
    对照（甲饰品 2 件在列、丙遗器部位齐全）。"""
    data = _fixture_detail_data()
    del data['avatar_list'][0]['relics']  # 甲缺 relics 键
    del data['avatar_list'][2]['ornaments']  # 丙缺 ornaments 键
    hsr, _ = _detail_client_with_payload(tmp_path, data)

    details = hsr.get_characters_detail()

    first, _, third = details
    assert first.relics == []
    assert len(first.ornaments) == 2  # 甲饰品不受键缺失牵连
    assert third.ornaments == []
    assert [r.pos for r in third.relics] == [1, 3]  # 丙遗器不受键缺失牵连
