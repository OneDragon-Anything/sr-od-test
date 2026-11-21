"""sr_relic_sets 套装快照常量与套装效果助手单测。

锁的内容（套装快照常量数据层契约——快照完整性/件名反查/套装效果聚合；
断言依据全部来自本文件固化的基准值，不读本机易失快照件）：

- 快照完整性：RELIC_SETS 恰 64 套（隧洞 34 + 位面饰品 30）、效果齐备形态
  （64 条带 '2'、34 条 cavern 带 '4'、ornament 无 '4'）、196 件名唯一、
  pos 坐标系（隧洞 1-4 / 位面 5-6）；
- 基准：官方全名套装（骇域漫游的信使 4 件件名 + 2/4 效果、生命的翁瓦克
  2 件 + 充能效率效果——社区简称≠官方全名，勿按简称入表）、3.6/3.7 新
  套装在列（快照 verification 块新套装抽 2）、4.7 新位面套锚点
  （神的瞬息欢愉/亚空异容所：件名+效果+desc，文本源=官方版本公告）；
- 件名反查：resolve_set_name 基准命中；未知件名 None + warning（``sr_relic_sets:``
  前缀、文案含件名）不抛异常；
- build_set_effects 三形态与排序：满装（4+2 双激活）/ 缺件（只 2 件档）/
  饰品 1 件（count<2 不产出条目）/ 未知件名静默跳过（告警责任在
  resolve_set_name）；piece_count 降序、同级按 set_name。
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import sr_od.mys.sr_relic_sets as sr_relic_sets
from one_dragon.utils import os_utils
from sr_od.mys.sr_codes import RELIC_POS_CN
from sr_od.mys.sr_relic_sets import (
    RELIC_POS_EN,
    RELIC_SETS,
    build_set_effects,
    resolve_set_name,
)

_MESSENGER_PIECES: list[str] = [
    '信使的全息目镜', '信使的百变义手', '信使的密信挎包', '信使的酷跑板鞋',
]
_WAKKA_PIECES: list[str] = ['翁瓦克的诞生之岛', '翁瓦克的环岛海岸']

#: 国际服未收录套装（id 留空串,宁缺勿错）；国际服同步后回填并收紧本名单。
PENDING_INTL_SYNC: set[str] = {
    '星如我见的领航员', '戏梦点星的伶人', '贪噬禁果的异端',
    '坠星启航地', '寰宇生研院', '神的瞬息欢愉', '亚空异容所',
}


def test_relic_sets_snapshot_completeness() -> None:
    """快照完整性：恰 64 套（隧洞 34 + 位面饰品 30）；效果齐备形态
    （64 条带非空 '2'、34 条 cavern 带非空 '4'、ornament 无 '4' 键）；
    件名全集恰 196 且唯一（反查索引 PIECE_TO_SET 的正确性前提）；
    pos 坐标系：隧洞 1-4、位面 5-6（与 sr_codes.RELIC_POS_CN 同源）。"""
    cavern_sets = [s for s in RELIC_SETS if s.kind == 'cavern']
    ornament_sets = [s for s in RELIC_SETS if s.kind == 'ornament']
    assert len(RELIC_SETS) == 64
    assert len(cavern_sets) == 34
    assert len(ornament_sets) == 30

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
    assert len(piece_names) == 196
    assert len(set(piece_names)) == 196


def test_set_ids_contract() -> None:
    """套装 id 契约：格式（小写仅字母数字）、非空 id 唯一（模板库注册表与
    权威表连键的前提）、空 id 集合恰等于白名单（宁缺勿错——白名单外缺 id
    说明回填漏做，白名单内出现 id 说明国际服已同步应转正并收紧名单）。"""
    import re

    non_empty = [s.id for s in RELIC_SETS if s.id]
    assert all(re.fullmatch(r'[a-z0-9]+', i) for i in non_empty)
    assert len(non_empty) == len(set(non_empty))

    empty_names = {s.set_name for s in RELIC_SETS if not s.id}
    assert empty_names == PENDING_INTL_SYNC


def test_relic_pos_en_matches_cn_domain() -> None:
    """部位英文映射：键域与 RELIC_POS_CN 同域（1-6 双向对齐），值为小写
    字母数字（模板 template_id 部位段的格式前提）。"""
    assert set(RELIC_POS_EN) == set(RELIC_POS_CN)
    import re

    assert all(re.fullmatch(r'[a-z0-9]+', v) for v in RELIC_POS_EN.values())


def test_anchor_and_new_version_sets() -> None:
    """官方全名套装基准：骇域漫游的信使（4 件件名逐一定名 + 2/4 件效果）、
    生命的翁瓦克（2 件件名 + 充能效率效果）；3.6/3.7 新套装在列
    （verification.new_sets_check 抽 2：伶人=3.7 隧洞、寰宇生研院=3.6 位面）；
    4.7 新位面套（神的瞬息欢愉/亚空异容所）：件名+效果+obtain+desc 锚定。"""
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

    # 4.7 新位面套锚点（文本源=官方版本公告；社区 wiki 曾把「深黯」误作「深黢」，
    # 件名以公告原文为准）
    aha = by_name['神的瞬息欢愉']
    assert aha.kind == 'ornament'
    assert [p.name for p in aha.pieces] == ['瞬息欢愉的永恒舞台', '瞬息欢愉的魔术道具']
    assert aha.effects['2'] == \
        '使装备者的速度提高6%。当装备者的欢愉度大于等于40%时，进入战斗时立刻使行动提前40%。'
    assert aha.obtain == '戏剧中人·差分宇宙'
    assert aha.pieces[0].desc.startswith('位面球中封装着瞬息欢愉之地的舞台')

    sub = by_name['亚空异容所']
    assert sub.kind == 'ornament'
    assert [p.name for p in sub.pieces] == ['异容所的深黯裂隙', '异容所的负向胶卷']
    assert '击破特攻提高18%' in sub.effects['2']


def test_resolve_set_name_hit_and_miss_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """件名反查：隧洞与位面基准命中官方全名；未知件名返回 None 不抛异常，
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


def test_piece_desc_obtain_and_template_anchor() -> None:
    """单件 desc / 套装 obtain 齐备形态（196/64 全非空，纯展示文本透传）；
    识别模板规范库锚点：有 id 套装的模板在盘（template_id 公式 =
    套装id_部位英文），空 id 套装（国际服待同步名单）不落库。"""
    pieces = [p for s in RELIC_SETS for p in s.pieces]
    assert all(p.desc for p in pieces)
    assert all(s.obtain for s in RELIC_SETS)

    messenger = next(s for s in RELIC_SETS if s.set_name == '骇域漫游的信使')
    for piece in messenger.pieces:
        template_id = f'{messenger.id}_{RELIC_POS_EN[piece.pos]}'
        path = os_utils.get_path_under_work_dir(
            'assets', 'template', 'relic_icon', template_id, 'raw.webp')
        assert Path(path).is_file(), f'规范库缺模板: {template_id}'

    for set_name in PENDING_INTL_SYNC:
        relic_set = next(s for s in RELIC_SETS if s.set_name == set_name)
        assert relic_set.id == '', f'待国际服同步套装应空 id: {set_name}'
