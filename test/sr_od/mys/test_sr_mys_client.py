"""SrMysClient 单测（SrMysClient 设计契约判据；正本 = docs/develop/sr_od/backend/mys.md「sr_od/mys（崩铁特有封装）」节）。

全部走 mock 管线（剧本式假 http_send / MagicMock client），零真实网络；
落盘走 pytest tmp_path。锁的判据：

- 过期短路：``store.is_expired()`` 直接 ``MysSessionExpired``，不发任何请求
  （v1 ``get_characters`` 与 v2 ``get_characters_detail`` 同管线同判据）；
- 角色自动发现：绝对 URL 形态（binding 域 ROLE_LIST_URL + game_biz=hkrpg_cn）、
  is_chosen 优先否则首个、role_id 字符串化（实测响应 game_uid 为字符串，此处
  fixture 故意用 int 以锁死 ``str()`` 强制转换）、role.json 缓存写入；
- role.json 缓存命中：不发角色发现请求，server 取缓存值；
- 冻结字段集映射：index 快照 fixture（test/fixtures/mys/，实测结构固化）映射出
  ``SrCharacter`` v2（v1 八字段 + element_cn/base_type_cn 两中文字段）
  ——字段集增删即本文件失败，icon 等大字段不透传，
  equip 缺失（null）映射 None；
- 明细富映射（get_characters_detail，avatar/info 端点）：剧本按 URL 分流
  （index → v1 轻剧本不动；avatar/info → detail 剧本，detail 栈不注册 index
  路由——端点回归回 index 即响亮失败）；detail 请求 URL 含 avatar/info 与
  need_wiki=true（端点切换存在性锁）；CharacterDetail 及八个子结构冻结字段
  集逐字对账（CharacterDetail 冻结字段集含套装效果组，增删即失败）；词条/面板
  name_cn 两路解析（fixture 动态词典 + 快照兜底 + 占位符/空名实测形态）；
  主词条部位校验哨兵 warning（畸形数据不中断映射）；空遗器/无光锥/缺件/
  星魂未解锁等形态透传。
- 套装映射（mys-data.md §2 映射契约）：逐件 set_name 件名反查
  （真实件名 → 套装官方全名；未知件名 → 「未知套装」+ resolve 层 warning
  恰一次，映射/build 层不重复告警）；角色级 set_effects 激活档形态（4 件套
  2/4 双档、2 件套单档、缺件不足 4 无 4 件档、全空 → 空列表、ornaments 空 →
  无饰品条目）与 set_effects 序列化面对账。
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
from sr_od.mys import sr_mys_client, sr_relic_sets
from sr_od.mys.sr_mys_client import (
    CharacterDetail,
    ConeSummary,
    SrCharacter,
    SrMysClient,
    SrPanelProperty,
    SrPropertyEntry,
    SrRank,
    SrRelic,
    SrSetEffect,
    SrSetEffectEntry,
    SrSkill,
    SrSkillStage,
)

#: index 实测结构快照（fixture 固化进测试仓，摆脱易失 trace 依赖）
INDEX_SNAPSHOT_PATH: Path = (
    Path(__file__).resolve().parents[2] / 'fixtures' / 'mys' / 'hkrpg_index_snapshot.json'
)

#: avatar/info 全量明细真实样本（2026-11-04 实测响应加工：抽 3 角色 + 词典
#: 14 键，见 fixture _source 注记；端点勘误见 miyoushe-api-flow.md §8.2，
#: 明细映射契约见 docs/develop/sr_od/backend/mys.md「sr_od/mys」节）
DETAIL_SAMPLE_PATH: Path = (
    Path(__file__).resolve().parents[2] / 'fixtures' / 'mys' / 'hkrpg_avatar_info_detail_sample.json'
)

#: detail 端点（avatar/info）与 v1 index 的 RECORD 基座前缀（剧本按 URL 分流）
_AVATAR_INFO_PREFIX: str = GAME_RECORD_BASE_URL + 'hkrpg/api/avatar/info'
_INDEX_PREFIX: str = GAME_RECORD_BASE_URL + 'hkrpg/api/index'

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
def sr(client: MysClient, store: SessionStore) -> SrMysClient:
    return SrMysClient(client, store)


# ---- 过期短路 ----


def test_expired_short_circuit_raises_without_any_request(
    store: SessionStore, sr: SrMysClient, send: _ScriptedHttpSend
) -> None:
    """is_expired() 为真 → 直接 MysSessionExpired，不发请求（过期短路判据：
    不发起注定失败的请求）。"""
    store.save_cookies({'stale': 'x'})  # 会话文件存在是标记过期的前提
    store.mark_expired()

    with pytest.raises(MysSessionExpired):
        sr.get_characters()
    assert send.calls == []  # 零请求


# ---- 角色自动发现与缓存 ----


def test_auto_discovery_absolute_url_chosen_first_and_role_cache(
    tmp_path: Path, store: SessionStore, sr: SrMysClient, send: _ScriptedHttpSend
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
    characters = sr.get_characters()

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
    sr: SrMysClient, store: SessionStore, send: _ScriptedHttpSend
) -> None:
    """无 is_chosen 真值的崩铁角色 → 取首个（is_chosen 优先否则首个）。"""
    send.add_route(
        (
            ROLE_LIST_URL,
            _roles_result([_hsr_role('900000001', is_chosen=False), _hsr_role('900000002', is_chosen=False)]),
        ),
        (GAME_RECORD_BASE_URL, _index_ok_result(_fixture_index_data())),
    )
    sr.get_characters()

    index_url = send.calls_for(GAME_RECORD_BASE_URL)[0][0]
    assert 'role_id=900000001' in index_url
    assert store.load_role() == {'role_id': '900000001', 'server': 'prod_gf_cn'}


def test_role_cache_skips_discovery_and_uses_cached_server(
    store: SessionStore, sr: SrMysClient, send: _ScriptedHttpSend
) -> None:
    """role.json 缓存命中：零角色发现请求，server 取缓存值（不硬编码）。"""
    store.save_role({'role_id': '42', 'server': 'prod_gf_cn'})
    send.add_route(
        (GAME_RECORD_BASE_URL + 'hkrpg/api/index', _index_ok_result(_fixture_index_data())),
    )
    sr.get_characters()

    assert send.calls_for(ROLE_LIST_URL) == []  # 缓存命中不发现
    index_url = send.calls_for(GAME_RECORD_BASE_URL + 'hkrpg/api/index')[0][0]
    assert index_url == GAME_RECORD_BASE_URL + 'hkrpg/api/index?role_id=42&server=prod_gf_cn'


def test_corrupted_role_cache_falls_back_to_discovery(
    store: SessionStore, sr: SrMysClient, send: _ScriptedHttpSend
) -> None:
    """缓存损坏（字段非法）视同无缓存：重发现并覆盖缓存。"""
    (store._session_dir / ROLE_FILE_NAME).write_bytes(b'{"role_id": 123}')  # 类型非法
    send.add_route(
        (ROLE_LIST_URL, _roles_result([_hsr_role('777', is_chosen=True)])),
        (GAME_RECORD_BASE_URL, _index_ok_result(_fixture_index_data())),
    )
    sr.get_characters()

    assert len(send.calls_for(ROLE_LIST_URL)) == 1  # 坏缓存触发重发现
    assert store.load_role() == {'role_id': '777', 'server': 'prod_gf_cn'}


def test_discovery_without_hsr_role_raises_and_keeps_no_cache(
    sr: SrMysClient, store: SessionStore, tmp_path: Path, send: _ScriptedHttpSend
) -> None:
    """发现失败（无崩铁国服角色）→ MysApiError，且不写 role.json。"""
    send.add_route((ROLE_LIST_URL, _roles_result([_genshin_role()])))

    with pytest.raises(MysApiError):
        sr.get_characters()
    assert not (tmp_path / ROLE_FILE_NAME).exists()


# ---- 冻结字段集映射（mock client，聚焦映射本身）----


def test_frozen_field_set_mapping_from_index_snapshot(tmp_path: Path) -> None:
    """index 快照 fixture → SrCharacter 冻结字段集（v1 八字段 +
    element_cn/base_type_cn 两中文字段：字段增删即判据失败）；icon/
    figure_path/element_id/is_chosen 等实测在场字段不透传；equip null → None；
    中文字段经码表查表填充（wind→风 / bt=7→丰饶，ice→冰 / bt=1→毁灭）。"""
    snapshot = json.loads(INDEX_SNAPSHOT_PATH.read_bytes().decode('utf-8'))
    mock_client = MagicMock(spec=MysClient)
    mock_client.request.return_value = snapshot['data']
    store = SessionStore(tmp_path, threading.Lock())
    store.save_role({'role_id': '1', 'server': 'prod_gf_cn'})
    sr = SrMysClient(mock_client, store)

    characters = sr.get_characters()

    # 字段集冻结：SrCharacter 与 ConeSummary 的字段名集合逐字对账
    assert {f.name for f in fields(SrCharacter)} == {
        'id', 'name', 'level', 'rarity', 'rank', 'element', 'base_type', 'equip',
        'element_cn', 'base_type_cn',
    }
    assert {f.name for f in fields(ConeSummary)} == {'name', 'level', 'rank', 'rarity'}

    first, second = characters
    assert first == SrCharacter(
        id=1217, name='藿藿', level=60, rarity=5, rank=1,
        element='wind', base_type=7,
        equip=ConeSummary(name='惊魂夜', level=50, rank=1, rarity=5),
        element_cn='风', base_type_cn='丰饶',
    )
    assert second == SrCharacter(
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
    tmp_path: Path, store: SessionStore, sr: SrMysClient
) -> None:
    """过期短路不清任何落盘文件（会话失效只打标记不清数据契约）。"""
    store.save_session_full({'ltoken_v2': 'keep'})
    store.save_role({'role_id': '1', 'server': 'prod_gf_cn'})
    store.mark_expired()

    with pytest.raises(MysSessionExpired):
        sr.get_characters()

    saved = json.loads((tmp_path / SESSION_FILE_NAME).read_bytes().decode('utf-8'))
    assert saved['expired'] is True
    assert saved['cookies'] == {'ltoken_v2': 'keep'}
    assert (tmp_path / ROLE_FILE_NAME).exists()


# ---- 明细富映射（get_characters_detail，avatar/info 端点富映射契约）----


def _fixture_detail_data() -> dict:
    """读 avatar/info 真实样本 fixture 的 data 字段（2026-11-04 实测响应加工，
    抽样三形态见 fixture _source 注记）。"""
    sample = json.loads(DETAIL_SAMPLE_PATH.read_bytes().decode('utf-8'))
    return sample['data']


def _stack_with_routes(
    tmp_path: Path, *routes: tuple[str, HttpSendResult]
) -> tuple[SrMysClient, _ScriptedHttpSend]:
    """任意剧本路由的完整客户端栈（role.json 缓存命中，零角色发现请求）。"""
    send = _ScriptedHttpSend((GET_FP_URL, _fp_ok_result()), *routes)
    store = SessionStore(tmp_path, threading.Lock())
    store.save_role({'role_id': '1', 'server': 'prod_gf_cn'})
    device = DeviceIdentity(store, send)
    return SrMysClient(MysClient(store, device, send), store), send


def _detail_stack(tmp_path: Path, data: dict | None = None) -> tuple[SrMysClient, _ScriptedHttpSend]:
    """avatar/info 剧本直灌的 detail 栈：只注册 detail 端点路由——端点回归回
    index 会撞「剧本外请求」响亮失败（URL 分流的 fail-closed 语义）；v1 index
    路由只在显式需要的对账测试按 URL 分流追加。"""
    return _stack_with_routes(
        tmp_path,
        (_AVATAR_INFO_PREFIX, _json_result(
            {'retcode': 0, 'message': 'OK', 'data': data if data is not None else _fixture_detail_data()})),
    )


def test_detail_expired_short_circuit_raises_without_any_request(
    store: SessionStore, sr: SrMysClient, send: _ScriptedHttpSend
) -> None:
    """detail 复用 v1 过期短路：is_expired() 直接 MysSessionExpired，零请求
    （detail 与 v1 会话语义完全一致契约）。"""
    store.save_cookies({'stale': 'x'})
    store.mark_expired()

    with pytest.raises(MysSessionExpired):
        sr.get_characters_detail()
    assert send.calls == []


def test_detail_frozen_field_sets_locked(tmp_path: Path) -> None:
    """冻结字段集逐字对账：CharacterDetail
    16 字段 + 八个子结构字段名集合（set_name/set_effects 为套装映射组
    契约面），任何增删即失败；SrRank 不设 pos_cn（星魂 pos 是星魂序号，
    与遗器部位码撞值域——结构性防混淆）；序列化面 = 冻结字段集（icon/desc/
    figure_path/point_id 等不透传字段不出现在载荷，set_effects 档条目键集
    同判）。"""
    sr, _ = _detail_stack(tmp_path)
    details = sr.get_characters_detail()

    assert {f.name for f in fields(CharacterDetail)} == {
        'id', 'name', 'level', 'rarity', 'rank', 'element', 'element_cn',
        'base_type', 'base_type_cn', 'equip', 'relics', 'ornaments', 'ranks',
        'skills', 'properties', 'set_effects',
    }
    assert {f.name for f in fields(SrRelic)} == {
        'name', 'pos', 'pos_cn', 'rarity', 'level', 'main', 'subs', 'set_name',
    }
    assert {f.name for f in fields(SrSetEffect)} == {
        'set_name', 'kind', 'piece_count', 'pieces', 'activated',
    }
    assert {f.name for f in fields(SrSetEffectEntry)} == {'count', 'desc'}
    assert {f.name for f in fields(SrPropertyEntry)} == {'name_cn', 'value', 'times'}
    assert {f.name for f in fields(SrRank)} == {'pos', 'name', 'desc', 'is_unlocked'}
    assert {f.name for f in fields(SrSkill)} == {'name', 'level', 'is_activated', 'stages'}
    assert {f.name for f in fields(SrSkillStage)} == {'name', 'desc', 'level'}
    assert {f.name for f in fields(SrPanelProperty)} == {'name_cn', 'base', 'add', 'final'}

    # 序列化面（含嵌套展开）= 冻结字段集，不透传清单一个都不出现
    payload = asdict(details[0])
    assert set(payload.keys()) == {f.name for f in fields(CharacterDetail)}
    assert set(payload['equip'].keys()) == {f.name for f in fields(ConeSummary)}
    assert set(payload['relics'][0].keys()) == {f.name for f in fields(SrRelic)}
    assert set(payload['relics'][0]['main'].keys()) == {f.name for f in fields(SrPropertyEntry)}
    assert set(payload['set_effects'][0].keys()) == {f.name for f in fields(SrSetEffect)}
    assert set(payload['set_effects'][0]['activated'][0].keys()) == {
        f.name for f in fields(SrSetEffectEntry)
    }
    assert set(payload['ranks'][0].keys()) == {f.name for f in fields(SrRank)}
    assert set(payload['skills'][0].keys()) == {f.name for f in fields(SrSkill)}
    assert set(payload['skills'][0]['stages'][0].keys()) == {f.name for f in fields(SrSkillStage)}
    assert set(payload['properties'][0].keys()) == {f.name for f in fields(SrPanelProperty)}


def test_detail_mapping_full_form(tmp_path: Path) -> None:
    """甲（丹恒•饮月：带光锥+4 遗器+2 饰品+星魂 2/6 混合解锁+普攻四段行迹）
    逐组对账：轻口径 10 字段与 v1 同语义（中文字段查表填充）、遗器/饰品同构
    映射（pos_cn 部位查表）、星魂全量透传（未解锁层在列）、行迹取 remake 与
    分段文案（普攻四段一条以上）、面板字符串数值透传；一次调用恰一次
    avatar/info 请求（复用 v1 定位管线，不重复打接口）。

    真实样本行迹有 18 条（含 10 条属性加成），分段 desc 全文数百字——行迹按
    「全量元组（remake/level/is_activated/分段名与级）+ 抽样 desc 全文」对账，
    其余五组仍整体深对账（行迹 desc 逐字段映射由冻结字段集测试锁结构、本测试
    抽样锁值）。
    """
    sr, send = _detail_stack(tmp_path)

    details = sr.get_characters_detail()

    assert len(details) == 3
    assert [d.name for d in details] == ['丹恒•饮月', '米沙', '素裳']

    first = details[0]
    assert (first.id, first.name, first.level, first.rarity, first.rank) == (
        1213, '丹恒•饮月', 80, 5, 2,
    )
    assert (first.element, first.element_cn, first.base_type, first.base_type_cn) == (
        'imaginary', '虚数', 1, '毁灭',
    )
    assert first.equip == ConeSummary(name='比阳光更明亮的', level=80, rank=1, rarity=5)
    assert first.relics == [
        SrRelic(
            name='快枪手的野穗毡帽', pos=1, pos_cn='头部', rarity=5, level=15,
            set_name='野穗伴行的快枪手',
            main=SrPropertyEntry(name_cn='生命值', value='705', times=0),
            subs=[
                SrPropertyEntry(name_cn='生命值', value='3.4%', times=1),
                SrPropertyEntry(name_cn='暴击率', value='5.5%', times=2),
                SrPropertyEntry(name_cn='暴击伤害', value='17.4%', times=3),
                SrPropertyEntry(name_cn='效果抵抗', value='6.9%', times=2),
            ],
        ),
        SrRelic(
            name='快枪手的粗革手套', pos=2, pos_cn='手部', rarity=5, level=15,
            set_name='野穗伴行的快枪手',
            main=SrPropertyEntry(name_cn='攻击力', value='352', times=0),
            subs=[
                SrPropertyEntry(name_cn='生命值', value='42', times=1),
                SrPropertyEntry(name_cn='暴击伤害', value='22.0%', times=4),
                SrPropertyEntry(name_cn='效果命中', value='3.8%', times=1),
                SrPropertyEntry(name_cn='击破特攻', value='12.9%', times=2),
            ],
        ),
        SrRelic(
            name='快枪手的猎风披肩', pos=3, pos_cn='躯干', rarity=5, level=15,
            set_name='野穗伴行的快枪手',
            main=SrPropertyEntry(name_cn='暴击伤害', value='64.8%', times=0),
            subs=[
                SrPropertyEntry(name_cn='防御力', value='9.7%', times=2),
                SrPropertyEntry(name_cn='暴击率', value='5.5%', times=2),
                SrPropertyEntry(name_cn='效果抵抗', value='8.2%', times=2),
                SrPropertyEntry(name_cn='击破特攻', value='18.7%', times=3),
            ],
        ),
        SrRelic(
            name='快枪手的铆钉马靴', pos=4, pos_cn='脚部', rarity=5, level=15,
            set_name='野穗伴行的快枪手',
            main=SrPropertyEntry(name_cn='攻击力', value='43.2%', times=0),
            subs=[
                SrPropertyEntry(name_cn='生命值', value='80', times=2),
                SrPropertyEntry(name_cn='防御力', value='42', times=2),
                SrPropertyEntry(name_cn='暴击率', value='3.2%', times=1),
                SrPropertyEntry(name_cn='暴击伤害', value='16.8%', times=3),
            ],
        ),
    ]
    assert first.ornaments == [
        SrRelic(
            name='泰科铵的镭射球场', pos=5, pos_cn='位面球', rarity=5, level=15,
            set_name='繁星竞技场',
            main=SrPropertyEntry(name_cn='虚数属性伤害提高', value='38.8%', times=0),
            subs=[
                SrPropertyEntry(name_cn='生命值', value='3.8%', times=1),
                SrPropertyEntry(name_cn='攻击力', value='7.3%', times=2),
                SrPropertyEntry(name_cn='暴击率', value='8.4%', times=3),
                SrPropertyEntry(name_cn='效果抵抗', value='7.7%', times=2),
            ],
        ),
        SrRelic(
            name='泰科铵的弧光赛道', pos=6, pos_cn='连结绳', rarity=5, level=15,
            set_name='繁星竞技场',
            main=SrPropertyEntry(name_cn='攻击力', value='43.2%', times=0),
            subs=[
                SrPropertyEntry(name_cn='攻击力', value='21', times=1),
                SrPropertyEntry(name_cn='防御力', value='16', times=1),
                SrPropertyEntry(name_cn='暴击率', value='5.8%', times=2),
                SrPropertyEntry(name_cn='暴击伤害', value='23.3%', times=4),
            ],
        ),
    ]
    assert first.ranks == [
        SrRank(pos=1, name='萦天', desc='使【亢心】的可叠加层数增加4层。且每段攻击额外获得1层【亢心】。',
                is_unlocked=True),
        SrRank(pos=2, name='九斿', desc='施放终结技后丹恒•饮月行动提前100%，并且会额外获得1个【逆鳞】。',
                is_unlocked=True),
        SrRank(pos=3, name='云旂', desc='战技等级+2，最多不超过15级；普攻等级+1，最多不超过10级。',
                is_unlocked=False),
        SrRank(pos=4, name='嘲风', desc='【叱咤】的增益效果会持续到下一个自身回合结束。', is_unlocked=False),
        SrRank(pos=5, name='偃蹇', desc='终结技等级+2，最多不超过15级；天赋等级+2，最多不超过15级。',
                is_unlocked=False),
        SrRank(pos=6, name='见谯',
                desc='我方其他角色施放终结技后，丹恒•饮月下一次施放【盘拏耀跃】时虚数属性抗性穿透提高20%，'
                     '该效果最多叠加3层。',
                is_unlocked=False),
    ]
    assert len(first.skills) == 18
    assert [(s.name, s.level, s.is_activated, [(st.name, st.level) for st in s.stages]) for s in first.skills] == [
        ('普攻', 6, True, [('泽芝', 6), ('瞬华', 6), ('天矢阴', 6), ('盘拏耀跃', 6)]),
        ('战技', 10, True, [('龙力自在', 10)]),
        ('终结技', 10, True, [('苍龙傲睨，劫水濯世', 10)]),
        ('天赋', 10, True, [('亢心', 10)]),
        ('秘技', 1, True, [('掣空如虹', 1)]),
        ('额外能力', 1, True, [('伏辰', 1)]),
        ('额外能力', 1, True, [('修禹', 1)]),
        ('额外能力', 1, True, [('起蛰', 1)]),
        ('属性加成', 1, True, [('伤害强化•虚数', 1)]),
        ('属性加成', 1, True, [('伤害强化•虚数', 1)]),
        ('属性加成', 1, True, [('伤害强化•虚数', 1)]),
        ('属性加成', 1, True, [('伤害强化•虚数', 1)]),
        ('属性加成', 1, True, [('伤害强化•虚数', 1)]),
        ('属性加成', 1, True, [('暴击率强化', 1)]),
        ('属性加成', 1, True, [('暴击率强化', 1)]),
        ('属性加成', 1, True, [('暴击率强化', 1)]),
        ('属性加成', 1, True, [('生命强化', 1)]),
        ('属性加成', 1, True, [('生命强化', 1)]),
    ]
    # 分段 desc 全文抽样：普攻首末段 + 额外能力（多段列表逐条映射的证据）
    assert first.skills[0].stages[0].desc == (
        '施放2段攻击对指定敌方单体造成等同于丹恒•饮月100%攻击力的虚数属性伤害。'
    )
    assert first.skills[0].stages[3].desc == (
        '施放7段攻击对指定敌方单体造成等同于丹恒•饮月500%攻击力的虚数属性伤害。'
        '从第4段攻击开始同时对其相邻目标造成等同于丹恒•饮月180%攻击力的虚数属性伤害。'
    )
    assert first.skills[5].stages[0].desc == '战斗开始时，立即恢复15点能量。'
    assert first.properties == [
        SrPanelProperty(name_cn='生命值', base='2300', add='1227', final='3527'),
        SrPanelProperty(name_cn='攻击力', base='1333', add='1944', final='3277'),
        SrPanelProperty(name_cn='防御力', base='760', add='133', final='893'),
        SrPanelProperty(name_cn='速度', base='102', add='0', final='102'),
        SrPanelProperty(name_cn='暴击率', base='71.5%', add='0.0%', final='71.5%'),
        SrPanelProperty(name_cn='暴击伤害', base='194.5%', add='0.0%', final='194.5%'),
        SrPanelProperty(name_cn='虚数属性伤害提高', base='61.2%', add='0.0%', final='61.2%'),
        SrPanelProperty(name_cn='击破特攻', base='31.7%', add='0.0%', final='31.7%'),
        SrPanelProperty(name_cn='欢愉度', base='0.0%', add='0.0%', final='0.0%'),
        SrPanelProperty(name_cn='治疗量加成', base='0.0%', add='0.0%', final='0.0%'),
        SrPanelProperty(name_cn='能量恢复效率', base='100.0%', add='0.0%', final='100.0%'),
        SrPanelProperty(name_cn='效果命中', base='3.8%', add='0.0%', final='3.8%'),
        SrPanelProperty(name_cn='效果抵抗', base='22.8%', add='0.0%', final='22.8%'),
    ]
    # 一次调用恰一次 avatar/info 请求（index 路由未注册——回归即响亮失败）
    assert len(send.calls_for(_AVATAR_INFO_PREFIX)) == 1


def test_detail_property_name_cn_dynamic_dict_and_snapshot_paths(tmp_path: Path) -> None:
    """词条/面板 name_cn 两路解析（三层查表契约）：词典路——pt=57 在 fixture 词典
    命中；pt=36 词典 name 带占位符经 property_name_relic 规避；快照路——词典
    子集未收录的 52/24 直落硬编码快照（快照全集 56 码与词典同域，键缺即归因
    依据）；空名形态（实测 pt=8 词典两字段全空 + 快照如实标注空）落
    「未知属性(pt=N)」终兜底。真实 avatar/info 样本中 pt=36/8 无词条引用
    （raw 64 角色全量扫描实证），本测试对甲的副词条定点改写触发这两个实测
    词典形态，其余断言全部来自未改写的真实数据。"""
    fixture = _fixture_detail_data()
    fixture_keys = set(fixture['property_info'].keys())
    assert {'57', '36', '8'} <= fixture_keys  # 词典路归因前提
    assert '52' not in fixture_keys and '24' not in fixture_keys  # 快照路归因前提
    fixture['avatar_list'][0]['relics'][0]['properties'][0]['property_type'] = 36  # 实测占位符形态
    fixture['avatar_list'][0]['relics'][1]['properties'][0]['property_type'] = 8  # 实测空名形态
    sr, _ = _detail_stack(tmp_path, fixture)
    first, _, third = sr.get_characters_detail()

    # 词典路：pt=57 词典命中（甲头部副词条）
    assert first.relics[0].subs[3] == SrPropertyEntry(name_cn='效果抵抗', value='6.9%', times=2)
    # 词典路占位符规避：pt=36 词典 name='受治疗量提高#1[f1]%'，显示名取干净 relic 字段
    assert first.relics[0].subs[0] == SrPropertyEntry(name_cn='治疗量加成', value='3.4%', times=1)
    # 快照路：词典子集未收录 52（键缺），直落硬编码快照
    assert first.relics[0].subs[1] == SrPropertyEntry(name_cn='暴击率', value='5.5%', times=2)
    assert first.ornaments[0].main == SrPropertyEntry(
        name_cn='虚数属性伤害提高', value='38.8%', times=0
    )
    # 空名形态（实测 pt=8）：词典词条两字段全空、快照也空 → 终兜底文案
    assert first.relics[1].subs[0] == SrPropertyEntry(name_cn='未知属性(pt=8)', value='42', times=1)
    # 面板行同规则：pt=24 词典未收录走快照、pt=7 词典命中
    assert first.properties[6] == SrPanelProperty(
        name_cn='虚数属性伤害提高', base='61.2%', add='0.0%', final='61.2%'
    )
    assert first.properties[9] == SrPanelProperty(
        name_cn='治疗量加成', base='0.0%', add='0.0%', final='0.0%'
    )
    # 丙侧词典路：素裳头部副词条 pt=57 照常词典命中
    assert third.relics[0].subs[2] == SrPropertyEntry(name_cn='效果抵抗', value='4.3%', times=1)


def test_detail_mapping_degenerate_forms(tmp_path: Path) -> None:
    """乙（米沙：equip=null + 零遗器零饰品 + 星魂 6/6 全解锁 + 4 星角色）与
    丙（素裳：缺件共 3 件 + 未激活行迹 + 4 星光锥）形态：equip None、
    relics/ornaments 空列表；缺件角色按实际件数映射；星魂 6 条全量透传
    （解锁状态不做过滤——全解锁〔乙〕与混合解锁〔甲 2/6〕两形态都在列）；
    未激活行迹与空副词条列表照常透传（真实样本无空副词条件——raw 64 角色
    全量扫描实证，丙侧删键触发缺键退空列表契约）。"""
    data = _fixture_detail_data()
    del data['avatar_list'][2]['ornaments'][1]['properties']  # 空副词条形态
    sr, _ = _detail_stack(tmp_path, data)
    _, second, third = sr.get_characters_detail()

    assert second.id == 1312
    assert second.name == '米沙'
    assert second.equip is None
    assert second.relics == []
    assert second.ornaments == []
    assert second.rarity == 4
    assert second.element_cn == '冰'
    assert second.base_type_cn == '毁灭'
    assert [r.pos for r in second.ranks] == [1, 2, 3, 4, 5, 6]
    assert all(r.is_unlocked is True for r in second.ranks)

    # 丙：缺件 3 件（1 遗器 + 2 饰品），pos 是唯一部位键；4 星光锥摘要
    assert third.rarity == 4
    assert len(third.relics) == 1
    assert len(third.ornaments) == 2
    assert [r.pos for r in third.relics + third.ornaments] == [1, 5, 6]
    assert third.ornaments[1].subs == []  # 空副词条列表照常映射
    assert third.equip == ConeSummary(name='春水初生', level=40, rank=5, rarity=4)
    assert third.skills[5].name == '额外能力'
    assert third.skills[5].is_activated is False  # 未激活行迹状态透传
    assert third.element_cn == '物理'
    assert third.base_type_cn == '巡猎'


def test_detail_malformed_main_affix_warns_but_mapping_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """数据异常哨兵：甲头部主词条定点改写为 pt=52（pos=1 配置集只认 27）→
    warning 哨兵但映射继续，该件仍随明细返回（name_cn 照常查表）；全 fixture
    恰此一条主词条告警（真实样本 9 件主词条全部合法——raw 64 角色全量扫描
    零违规实证，本测试定点改写触发畸形形态）。"""
    fake_log = MagicMock()
    monkeypatch.setattr(sr_mys_client, 'log', fake_log)
    data = _fixture_detail_data()
    data['avatar_list'][0]['relics'][0]['main_property']['property_type'] = 52
    sr, _ = _detail_stack(tmp_path, data)

    details = sr.get_characters_detail()

    first = details[0]
    assert first.relics[0].pos == 1
    assert first.relics[0].main == SrPropertyEntry(name_cn='暴击率', value='705', times=0)
    warning_texts = [str(call.args[0]) for call in fake_log.warning.call_args_list]
    affix_warnings = [text for text in warning_texts if '主词条校验未通过' in text]
    assert len(affix_warnings) == 1
    assert 'pos=1' in affix_warnings[0]
    assert 'pt=52' in affix_warnings[0]


# ---- 套装映射（mys-data.md §2 映射契约：set_name 反查 + set_effects 激活档）----


def test_relic_set_name_resolved_and_set_effects_two_tier_activation(tmp_path: Path) -> None:
    """甲（快枪手 4 件 + 繁星竞技场 2 件，真实件名 fixture）：逐件 set_name
    反查正确（件名 → 套装官方全名，relics/ornaments 同规则）；set_effects
    两条目按 piece_count 降序——快枪手（cavern）4 件套 2/4 两档激活（pieces
    为实际佩戴件名、佩戴序 = 响应数组顺序），繁星竞技场（ornament）2 件档
    激活；效果文案与套装常量表逐字一致（官方原文透传）。"""
    sr, _ = _detail_stack(tmp_path)
    first = sr.get_characters_detail()[0]

    assert [r.set_name for r in first.relics] == ['野穗伴行的快枪手'] * 4
    assert [o.set_name for o in first.ornaments] == ['繁星竞技场'] * 2
    assert first.set_effects == [
        SrSetEffect(
            set_name='野穗伴行的快枪手', kind='cavern', piece_count=4,
            pieces=['快枪手的野穗毡帽', '快枪手的粗革手套', '快枪手的猎风披肩', '快枪手的铆钉马靴'],
            activated=[
                SrSetEffectEntry(count=2, desc='攻击力提高12%。'),
                SrSetEffectEntry(count=4, desc='使装备者的速度提高6%，普攻造成的伤害提高10%。'),
            ],
        ),
        SrSetEffect(
            set_name='繁星竞技场', kind='ornament', piece_count=2,
            pieces=['泰科铵的镭射球场', '泰科铵的弧光赛道'],
            activated=[
                SrSetEffectEntry(
                    count=2,
                    desc='使装备者的暴击率提高8%。当装备者当前暴击率大于等于70%时，普攻和战技造成的伤害提高20%。',
                ),
            ],
        ),
    ]


def test_unknown_piece_name_falls_back_with_single_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """未知件名形态（新版本套装未入常量）：甲一件遗器件名改自造名 →
    set_name 落「未知套装」字面量、resolve 层 warning 恰一次（映射层逐件
    反查触发、build 层静默跳过不重复告警）；set_effects 不含「未知套装」
    条目，快枪手剩 3 件只激活 2 件档（不足 4 无 4 件档）。"""
    fake_log = MagicMock()
    monkeypatch.setattr(sr_relic_sets, 'log', fake_log)
    data = _fixture_detail_data()
    data['avatar_list'][0]['relics'][2]['name'] = '自造的不存在件名'
    sr, _ = _detail_stack(tmp_path, data)

    first = sr.get_characters_detail()[0]

    assert first.relics[2].name == '自造的不存在件名'
    assert first.relics[2].set_name == '未知套装'
    resolve_warnings = [
        str(call.args[0]) for call in fake_log.warning.call_args_list
        if 'sr_relic_sets:' in str(call.args[0])
    ]
    assert len(resolve_warnings) == 1
    assert all(entry.set_name != '未知套装' for entry in first.set_effects)
    kuai = next(entry for entry in first.set_effects if entry.set_name == '野穗伴行的快枪手')
    assert kuai.piece_count == 3
    assert kuai.pieces == ['快枪手的野穗毡帽', '快枪手的粗革手套', '快枪手的铆钉马靴']
    assert [act.count for act in kuai.activated] == [2]


def test_set_effects_empty_for_unequipped_character(tmp_path: Path) -> None:
    """乙（米沙全空形态）：零遗器零饰品 → set_effects == []（零激活条目）。"""
    sr, _ = _detail_stack(tmp_path)
    second = sr.get_characters_detail()[1]

    assert second.relics == []
    assert second.ornaments == []
    assert second.set_effects == []


def test_set_effects_partial_cavern_without_ornaments(tmp_path: Path) -> None:
    """丙缺件形态（自造加工：同套 2 件遗器 + 0 饰品，复用甲的真实快枪手件）：
    同套 ≥2 激活 2 件档、不足 4 无 4 件档（set_effects 恰一条 cavern 条目、
    activated 单档）；ornaments 空 → 无饰品条目。"""
    data = _fixture_detail_data()
    data['avatar_list'][2]['relics'] = data['avatar_list'][0]['relics'][:2]  # 快枪手 pos1/2
    data['avatar_list'][2]['ornaments'] = []
    sr, _ = _detail_stack(tmp_path, data)
    third = sr.get_characters_detail()[2]

    assert [r.pos for r in third.relics] == [1, 2]
    assert third.ornaments == []
    assert third.set_effects == [
        SrSetEffect(
            set_name='野穗伴行的快枪手', kind='cavern', piece_count=2,
            pieces=['快枪手的野穗毡帽', '快枪手的粗革手套'],
            activated=[SrSetEffectEntry(count=2, desc='攻击力提高12%。')],
        ),
    ]


# ---- 防御分支（端点存在性锁 / avatar_list 缺失上抛 / 词典局部脏词条 / 数组键缺失退空）----


def test_detail_request_hits_avatar_info_with_need_wiki(tmp_path: Path) -> None:
    """端点切换存在性锁（防回归回 index）：detail 数据请求 URL = RECORD 基座
    + avatar/info，query 带 need_wiki=true（property_info 等五词典来源开关，
    端点勘误见 miyoushe-api-flow.md §8.2）与 role_id/server 定位参数（与 v1 同源，取自
    role.json 缓存）。"""
    sr, send = _detail_stack(tmp_path)

    sr.get_characters_detail()

    assert len(send.calls_for(_AVATAR_INFO_PREFIX)) == 1
    assert send.calls_for(_AVATAR_INFO_PREFIX)[0][0] == (
        GAME_RECORD_BASE_URL + 'hkrpg/api/avatar/info?need_wiki=true&role_id=1&server=prod_gf_cn'
    )


def test_detail_missing_avatar_list_raises_as_protocol_error(tmp_path: Path) -> None:
    """avatar/info 响应缺 avatar_list（其余字段在场）→ MysApiError 协议错误
    上抛，不静默返回空列表掩盖响应形态漂移；同一形态漂移下 v1 index 剧本
    同判（按 URL 分流双路由，同一防线两口径一致）。"""
    data = _fixture_detail_data()
    del data['avatar_list']
    sr, send = _stack_with_routes(
        tmp_path,
        (_AVATAR_INFO_PREFIX, _json_result({'retcode': 0, 'message': 'OK', 'data': data})),
        (_INDEX_PREFIX, _json_result({'retcode': 0, 'message': 'OK', 'data': {}})),
    )

    with pytest.raises(MysApiError, match='avatar_list'):
        sr.get_characters_detail()
    with pytest.raises(MysApiError, match='avatar_list'):
        sr.get_characters()
    # 上抛发生在各自端点的数据请求之后，非短路误报
    assert len(send.calls_for(_AVATAR_INFO_PREFIX)) == 1
    assert len(send.calls_for(_INDEX_PREFIX)) == 1


def test_detail_dirty_property_info_entries_skipped_mapping_continues(tmp_path: Path) -> None:
    """响应词典混入局部脏词条（值非 dict / 键非可归一整型）→ 归一时跳过而非
    抛错（_normalize_property_info 契约），整份明细照常映射：被脏词条占位的码
    查表自动退快照层（pt=7 → 治疗量加成），合法词典词条不受牵连（pt=59 照常
    命中）——词典局部异常既不中断映射也不污染其余码的三层查表。"""
    data = _fixture_detail_data()
    data['property_info']['7'] = '垃圾'  # 脏词条①：键可归一但值非 dict
    data['property_info']['abc'] = {  # 脏词条②：值合法但键归一不了 int
        'name': '不应出现的脏名',
        'property_name_relic': '不应出现的脏名',
    }
    sr, _ = _detail_stack(tmp_path, data)

    details = sr.get_characters_detail()  # 不抛异常是第一判据

    assert len(details) == 3
    # ① "7" 被跳过 → pt=7 词典 miss、落快照层（甲面板 pt=7 行，下标 9 与
    # 全量对账测试锁定的同一行序）
    assert details[0].properties[9] == SrPanelProperty(
        name_cn='治疗量加成', base='0.0%', add='0.0%', final='0.0%'
    )
    # ② "abc" 被跳过 → 动态词典照常生效，pt=59（丙头部副词条）仍走词典路命中
    assert details[2].relics[0].subs[3] == SrPropertyEntry(
        name_cn='击破特攻', value='6.4%', times=1
    )


def test_detail_missing_array_keys_fall_back_to_empty_lists(tmp_path: Path) -> None:
    """角色条目缺 relics / ornaments 数组键（响应形态漂移面）→ 对应字段退空
    列表、映射不抛错不中断（_map_relic_list 契约）；另一侧数组照常映射作
    对照（甲饰品 2 件在列、丙遗器部位齐全）。"""
    data = _fixture_detail_data()
    del data['avatar_list'][0]['relics']  # 甲缺 relics 键
    del data['avatar_list'][2]['ornaments']  # 丙缺 ornaments 键
    sr, _ = _detail_stack(tmp_path, data)

    details = sr.get_characters_detail()

    first, _, third = details
    assert first.relics == []
    assert len(first.ornaments) == 2  # 甲饰品不受键缺失牵连
    assert third.ornaments == []
    assert [r.pos for r in third.relics] == [1]  # 丙遗器不受键缺失牵连
