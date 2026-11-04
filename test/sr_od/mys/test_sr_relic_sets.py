"""sr_relic_sets 套装快照常量与套装效果助手单测。

锁的内容（design.md changes/mys-relic-sets §1 数据层 / §3 测试策略；断言依据
全部来自本文件固化的锚点值，不读本机易失快照件）：

- 快照完整性：RELIC_SETS 恰 62 套（隧洞 34 + 位面饰品 28）、效果齐备形态
  （62 条带 '2'、34 条 cavern 带 '4'、ornament 无 '4'）、192 件名唯一、
  pos 坐标系（隧洞 1-4 / 位面 5-6）；
- 锚点：官方全名套装（骇域漫游的信使 4 件件名 + 2/4 效果、生命的翁瓦克
  2 件 + 充能效率效果——社区简称≠官方全名，勿按简称入表）、3.6/3.7 新
  套装在列（快照 verification 块新套装抽 2）；
- 件名反查：resolve_set_name 锚点命中；未知件名 None + warning（``sr_relic_sets:``
  前缀、文案含件名）不抛异常；
- build_set_effects 三形态与排序：满装（4+2 双激活）/ 缺件（只 2 件档）/
  饰品 1 件（count<2 不产出条目）/ 未知件名静默跳过（告警责任在
  resolve_set_name）；piece_count 降序、同级按 set_name。
"""

from unittest.mock import MagicMock

import pytest

import sr_od.mys.sr_relic_sets as sr_relic_sets
from sr_od.mys.sr_relic_sets import RELIC_SETS, build_set_effects, resolve_set_name

_MESSENGER_PIECES: list[str] = [
    '信使的全息目镜', '信使的百变义手', '信使的密信挎包', '信使的酷跑板鞋',
]
_WAKKA_PIECES: list[str] = ['翁瓦克的诞生之岛', '翁瓦克的环岛海岸']


def test_relic_sets_snapshot_completeness() -> None:
    """快照完整性：恰 62 套（隧洞 34 + 位面饰品 28）；效果齐备形态
    （62 条带非空 '2'、34 条 cavern 带非空 '4'、ornament 无 '4' 键）；
    件名全集恰 192 且唯一（反查索引 PIECE_TO_SET 的正确性前提）；
    pos 坐标系：隧洞 1-4、位面 5-6（与 sr_codes.RELIC_POS_CN 同源）。"""
    cavern_sets = [s for s in RELIC_SETS if s.kind == 'cavern']
    ornament_sets = [s for s in RELIC_SETS if s.kind == 'ornament']
    assert len(RELIC_SETS) == 62
    assert len(cavern_sets) == 34
    assert len(ornament_sets) == 28

    for relic_set in RELIC_SETS:
        assert relic_set.effects.get('2')
    for relic_set in cavern_sets:
        assert relic_set.effects.get('4')
        assert len(relic_set.pieces) == 4
        assert [p.pos for p in relic_set.pieces] == [1, 2, 3, 4]
    for relic_set in ornament_sets:
        assert '4' not in relic_set.effects
        assert [p.pos for p in relic_set.pieces] == [5, 6]

    piece_names = [p.name for s in RELIC_SETS for p in s.pieces]
    assert len(piece_names) == 192
    assert len(set(piece_names)) == 192


def test_anchor_and_new_version_sets() -> None:
    """官方全名套装锚点：骇域漫游的信使（4 件件名逐一定名 + 2/4 件效果）、
    生命的翁瓦克（2 件件名 + 充能效率效果）；3.6/3.7 新套装在列
    （verification.new_sets_check 抽 2：伶人=3.7 隧洞、寰宇生研院=3.6 位面）。"""
    by_name = {s.set_name: s for s in RELIC_SETS}

    messenger = by_name['骇域漫游的信使']
    assert messenger.kind == 'cavern'
    assert [p.name for p in messenger.pieces] == _MESSENGER_PIECES
    assert messenger.effects['2'] == '速度提高6%。'
    assert '我方全体速度提高12%' in messenger.effects['4']

    wakka = by_name['生命的翁瓦克']
    assert wakka.kind == 'ornament'
    assert [p.name for p in wakka.pieces] == _WAKKA_PIECES
    assert '能量恢复效率' in wakka.effects['2']

    assert by_name['戏梦点星的伶人'].kind == 'cavern'
    assert by_name['寰宇生研院'].kind == 'ornament'


def test_resolve_set_name_hit_and_miss_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """件名反查：隧洞与位面锚点命中官方全名；未知件名返回 None 不抛异常，
    warning 恰一条且带 ``sr_relic_sets:`` 前缀、文案含件名便于定位。"""
    assert resolve_set_name('信使的全息目镜') == '骇域漫游的信使'
    assert resolve_set_name('翁瓦克的诞生之岛') == '生命的翁瓦克'

    fake_log = MagicMock()
    monkeypatch.setattr(sr_relic_sets, 'log', fake_log)
    assert resolve_set_name('不存在的套装件名') is None
    assert fake_log.warning.call_count == 1
    warning_text = str(fake_log.warning.call_args.args[0])
    assert warning_text.startswith('sr_relic_sets:')
    assert '不存在的套装件名' in warning_text


def test_build_set_effects_full_load() -> None:
    """满装形态：隧洞 4 件 + 位面 2 件 → 信使 2+4 双档 + 翁瓦克单 2 件档；
    piece_count 降序使信使条目在前；条目携带实际佩戴件名与套装 kind。"""
    entries = build_set_effects(_MESSENGER_PIECES, _WAKKA_PIECES)

    assert [e['set_name'] for e in entries] == ['骇域漫游的信使', '生命的翁瓦克']

    messenger = entries[0]
    assert messenger['kind'] == 'cavern'
    assert messenger['piece_count'] == 4
    assert messenger['pieces'] == _MESSENGER_PIECES
    assert [a['count'] for a in messenger['activated']] == [2, 4]
    assert messenger['activated'][0]['desc'] == '速度提高6%。'
    assert '我方全体速度提高12%' in messenger['activated'][1]['desc']

    wakka = entries[1]
    assert wakka['kind'] == 'ornament'
    assert wakka['piece_count'] == 2
    assert wakka['pieces'] == _WAKKA_PIECES
    assert len(wakka['activated']) == 1  # 饰品套无 4 件档
    assert wakka['activated'][0]['count'] == 2
    assert '能量恢复效率' in wakka['activated'][0]['desc']


def test_build_set_effects_partial_and_unknown() -> None:
    """缺件与未知件名形态：信使 2 件 → 只列 2 件档（4 件档不激活）；
    饰品 1 件 → count<2 一档未激活、不产出条目；快照 miss 件名 → 静默
    跳过不产出条目（告警责任在 resolve_set_name，本函数零日志）。"""
    entries = build_set_effects(_MESSENGER_PIECES[:2], [])
    assert len(entries) == 1
    assert entries[0]['piece_count'] == 2
    assert [a['count'] for a in entries[0]['activated']] == [2]

    assert build_set_effects([], _WAKKA_PIECES[:1]) == []
    assert build_set_effects(['不存在的套装件名'], ['也不存在的件名']) == []


def test_build_set_effects_sorting() -> None:
    """排序：piece_count 降序在前；同级（2 件）按 set_name 稳定输出。"""
    entries = build_set_effects(
        _MESSENGER_PIECES,
        [*_WAKKA_PIECES, '「黑塔」的空间站点', '「黑塔」的漫历轨迹'],
    )

    assert [(e['set_name'], e['piece_count']) for e in entries] == [
        ('骇域漫游的信使', 4),
        ('太空封印站', 2),
        ('生命的翁瓦克', 2),
    ]


def test_set_names_unique_across_all_sets() -> None:
    """防御纵深：RELIC_SETS 内 set_name 重复会令 _SET_BY_NAME 静默 last-wins（T-1 验收 F2）。"""
    names = [s.set_name for s in RELIC_SETS]
    assert len(names) == len(set(names))
