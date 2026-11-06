"""布洛妮娅选边型双羁绊机制测试面(镜像 src = data/cw_chars.py 注册表修正
与 SIDE_PICK_DUAL_BONDS/side_pick_bond 规则单一源 + kernel/cw_bond_equips.
unit_bond_tags peers 承载 + 全仓 8 处板面羁绊计数聚合器透传)。

设计约定出处 = economy.md §8(布洛妮娅双羁绊知识登记,用户裁定
2026-10-28)+ fields.md §5.2 披露键组(角色机制键 bronya_side_pick_tie_
blood):注册表 factions/flows 双边都登记(采样域/成员反查双边命中),
板面羁绊计数按图鉴逻辑选边单边计入——图鉴原文「布洛妮娅会基于小队中
【贝洛伯格】和【燃血】角色的数量,加入人数更多的羁绊并获得相应技能」
(characters/布洛妮娅.md);比较基数 = 其余在场角色的注册表出身
(factions+flows,不含装备贡献);平局 = 燃血(可见条目形态默认;假设,
披露键承载);独立羁绊「大守护者」不受选边影响恒 1 层。

选边翻转语义:任何单位增删都可能翻转计入边 → 全量聚合器天然正确;
board 增量投影(``GameState._resync_board_delta``)在布洛妮娅在场且有
增删时退化为全量重算(逐子表多重集差对她自身键不变的翻转结构性不可
维护),本文件锁其退化分支与全量聚合同值。

聚合器场景约定(8 处共用,fixture = 直构单位,不含装备贡献):
- 场景甲 = 布洛妮娅 + 娜塔莎(贝洛伯格)+ 桑博(贝洛伯格/星间旅人)
  + 刃(星核猎手/燃血)→ 基数贝 2 > 燃 1,布洛妮娅计贝洛伯格
  (board 贝洛伯格 = 3);
- 场景乙 = 甲去掉桑博 → 基数贝 1 = 燃 1 平局 → 计燃血(假设分支,
  board 燃血 = 2、贝洛伯格 = 1)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.data.cw_chars import (
    BRONYA_SIDE_PICK_TIE_BLOOD,
    SIDE_PICK_DUAL_BONDS,
    char_first_faction,
    chars_by_faction,
    side_pick_bond,
)
from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_battle_calib import (
    board_factions_of,
)
from sr_od.application.currency_war.kernel.cw_board_by_row import board_by_row
from sr_od.application.currency_war.kernel.cw_bond_equips import (
    _recount_board,
    unit_bond_tags,
)
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    deployed_bond_counts,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    Unit,
    deployed_view_sequential,
    game_state_of,
)

_SIG = ChannelSig(family='logic_action', actor='BronyaSidePickTest')
_SIG_OBS = ChannelSig(family='obs', actor='BronyaSidePickTest')


def _u(char_id: str, equips: list[str] | None = None) -> SimpleNamespace:
    """直构上场单位(duck-type 同 Unit:unit_bond_tags 消费面只要
    char_id/equips;零装备贡献 = 选边基数只看出身口径)。"""
    return SimpleNamespace(char_id=char_id, equips=list(equips or []))


def _unit(char_id: str) -> Unit:
    """状态容器 Unit 直构(GameState 行域写入形状;零装备)。"""
    return Unit(char_id=char_id, star=1, equips=[])


def _units_a() -> list:
    """场景甲:布洛妮娅 + 2 贝洛伯格(娜塔莎/桑博)+ 1 燃血(刃)。"""
    return [_u('布洛妮娅'), _u('娜塔莎'), _u('桑博'), _u('刃')]


def _units_b() -> list:
    """场景乙:甲去掉桑博(贝 1 = 燃 1 平局 → 计燃血)。"""
    return [_u('布洛妮娅'), _u('娜塔莎'), _u('刃')]


def _board_a() -> dict[str, int]:
    """场景甲全集口径期望(board = 注册表出身全量派生,零装备贡献)。"""
    return {'贝洛伯格': 3, '大守护者': 1, '治疗': 1, '星间旅人': 1,
            '持续伤害': 1, '星核猎手': 1, '燃血': 1}


def _board_b() -> dict[str, int]:
    """场景乙全集口径期望(平局计燃血:燃血 = 布+刃 2)。"""
    return {'燃血': 2, '大守护者': 1, '贝洛伯格': 1, '治疗': 1,
            '星核猎手': 1}


# ============================================================ 注册表修正锁


def test_bronya_registry_dual_bond_registration() -> None:
    """注册表双羁绊登记锁(用户裁定 2026-10-28,economy.md §8):布洛妮娅
    factions=('贝洛伯格',)/flows=('燃血',)/independent='大守护者';
    主阵营派生单一源 char_first_faction = '贝洛伯格'(修正前空阵营 '');
    chars_by_faction 双边命中——贝洛伯格域含她(本批修正新增,修正前
    仅 flows 命中燃血域)、燃血域仍含她(flows 命中,采样域池集合同值,
    去重保单次)。池规模只记注释零断言值(贝洛伯格域现值 6 名/燃血域
    现值 8 名,随版本正常变动)。"""
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    bronya = CHARACTERS['布洛妮娅']
    assert bronya.factions == ('贝洛伯格',)
    assert bronya.flows == ('燃血',)
    assert bronya.independent == '大守护者'
    assert char_first_faction('布洛妮娅') == '贝洛伯格'
    bei_names = {c.name for c in chars_by_faction('贝洛伯格')}
    assert '布洛妮娅' in bei_names, '贝洛伯格域含布洛妮娅(注册表修正新增)'
    ran_names = {c.name for c in chars_by_faction('燃血')}
    assert '布洛妮娅' in ran_names, '燃血域仍含布洛妮娅(flows 命中)'
    # 采样域登记 = 注册表全域:SIDE_PICK_DUAL_BONDS 只登记选边型角色,
    # 不扩采样域(域成员资格单一源 = factions/flows 轴)。
    assert SIDE_PICK_DUAL_BONDS['布洛妮娅'] == ('贝洛伯格', '燃血')
    assert BRONYA_SIDE_PICK_TIE_BLOOD == 'bronya_side_pick_tie_blood'


# ============================================================ 选边规则三态锁


def test_side_pick_bond_three_states() -> None:
    """选边规则三态锁(图鉴「加入人数更多的羁绊」+ 平局 = 燃血假设,
    披露键 BRONYA_SIDE_PICK_TIE_BLOOD 承载):贝多 → 贝洛伯格/
    燃多 → 燃血/平局 → 燃血(假设分支,可见条目形态默认);非选边型
    角色 = None;基数 = peers 注册表出身(不含装备贡献),未注册 peer
    不计两边,开拓者两形态对选边基数均零贡献(列车同行/能量出身,
    不在选边两边)。"""
    assert side_pick_bond('布洛妮娅', ['娜塔莎', '桑博', '刃']) == '贝洛伯格'
    assert side_pick_bond('布洛妮娅', ['刃', '万敌', '娜塔莎']) == '燃血'
    assert side_pick_bond('布洛妮娅', ['娜塔莎', '刃']) == '燃血'
    assert side_pick_bond('希儿', ['刃']) is None, '非选边型角色 = None'
    assert side_pick_bond('布洛妮娅', ['无名氏', '']) == '燃血', \
        '未注册 peer 不计两边 → 零比零平局 → 乙'
    assert side_pick_bond('布洛妮娅', ['开拓者·欢愉', '开拓者·记忆']) == '燃血', \
        '开拓者不在选边两边(基数零贡献)'


# ============================================================ 标签单一源锁


def test_unit_bond_tags_side_pick_single_edge() -> None:
    """per-unit 标签单一源锁(cw_bond_equips.unit_bond_tags peers 承载):
    带 peers → 选边单边 + 大守护者(独立羁绊不受选边影响照常计入);
    peers None → 现行全集行为(双边照出,不传上下文的既有调用点兼容);
    非选边型角色带/不带 peers 同值(零行为差)。"""
    bronya = _u('布洛妮娅')
    assert unit_bond_tags(bronya, peers=_units_a()[1:]) == \
        ('贝洛伯格', '大守护者'), '贝多场景单边化 + 独立羁绊照常'
    assert unit_bond_tags(bronya, peers=_units_b()[1:]) == \
        ('燃血', '大守护者'), '平局场景计乙(燃血)'
    assert unit_bond_tags(bronya) == ('贝洛伯格', '燃血', '大守护者'), \
        'peers None = 全集兼容(现行行为零变化)'
    nat = _u('娜塔莎')
    assert unit_bond_tags(nat, peers=_units_a()) == ('贝洛伯格', '治疗'), \
        '非选边型角色标签不受 peers 影响'


def test_unit_bond_tags_badge_seen_relative_to_side_pick() -> None:
    """星徽判重相对选边后标签集(装备贡献叠加独立于选边,用户裁定
    2026-10-28):布洛妮娅计燃血时戴贝洛伯格星徽 → 选边后无贝洛伯格
    出身 → 星徽 add-if-absent 追加;计贝洛伯格时戴同星徽 → 已拥有
    不重复(标签多集恒 1)。"""
    blood_side_badge = _u('布洛妮娅', equips=['贝洛伯格星徽'])
    assert unit_bond_tags(blood_side_badge, peers=_units_b()[1:]) == \
        ('燃血', '大守护者', '贝洛伯格'), \
        '选边燃血 + 贝洛伯格星徽 = 选边后 seen 相对化追加'
    bei_side_badge = _u('布洛妮娅', equips=['贝洛伯格星徽'])
    assert unit_bond_tags(bei_side_badge, peers=_units_a()[1:]) == \
        ('贝洛伯格', '大守护者'), \
        '选边贝洛伯格 + 同星徽 = 已拥有不重复(add-if-absent)'


# ============================================================ 聚合器选边锁(8 处)


def test_recount_board_side_pick() -> None:
    """聚合器 1 `_recount_board`(状态派生 board 写端,全集+装备口径):
    场景甲 → 贝洛伯格 3(布洛妮娅选边计入);场景乙(翻转)→ 燃血 2
    /贝洛伯格 1(平局计燃血)。"""
    assert _recount_board(_units_a()) == _board_a()
    assert _recount_board(_units_b()) == _board_b()


def test_board_from_deployed_side_pick() -> None:
    """聚合器 2 `board_from_deployed`(实机观察 board 真值,全集+装备):
    下标工作表(0-3 前/4-9 后)口径同 _recount_board——场景甲/乙同构
    两断言。"""
    from sr_od.application.currency_war.obs.cw_observation import (
        board_from_deployed,
    )
    dep_a = [None] * 4 + _units_a()
    assert board_from_deployed(dep_a) == _board_a()
    dep_b = [None] * 4 + _units_b()
    assert board_from_deployed(dep_b) == _board_b()


def test_board_by_row_side_pick() -> None:
    """聚合器 3 `board_by_row`(按排聚合,标签 = factions+flows 无
    independent):选边不分排(peers = 全板其余角色,图鉴「小队中」=
    全队)——布洛妮娅前排、其余后排跨排构造,场景甲 total 贝洛伯格 3
    /场景乙 total 燃血 2。"""
    bb_a = board_by_row([_u('布洛妮娅'), _u('娜塔莎')],
                        [_u('桑博'), _u('刃')])
    assert bb_a.count('贝洛伯格') == 3, '选边不分排:跨排基数计入'
    assert bb_a.count('燃血') == 1
    bb_b = board_by_row([_u('布洛妮娅'), _u('娜塔莎')], [_u('刃')])
    assert bb_b.count('燃血') == 2, '平局计燃血(布洛妮娅单边)'
    assert bb_b.count('贝洛伯格') == 1


def test_deployed_bond_counts_side_pick() -> None:
    """聚合器 4 `deployed_bond_counts`(策略部署计数,factions+flows
    直读型):cid 集合口径——场景甲/乙同构两断言(无 independent,
    直读型无大守护者)。"""
    assert deployed_bond_counts({'布洛妮娅', '娜塔莎', '桑博', '刃'}) == \
        {'贝洛伯格': 3, '治疗': 1, '星间旅人': 1, '持续伤害': 1,
         '星核猎手': 1, '燃血': 1}
    assert deployed_bond_counts({'布洛妮娅', '娜塔莎', '刃'}) == \
        {'燃血': 2, '贝洛伯格': 1, '治疗': 1, '星核猎手': 1}


def test_board_factions_of_side_pick() -> None:
    """聚合器 5 `board_factions_of`(sim 账本特征,factions+flows 直读型,
    公开别名同函数对象):deployed 列表口径——场景甲/乙同构两断言。"""
    assert board_factions_of(_units_a()) == \
        {'贝洛伯格': 3, '治疗': 1, '星间旅人': 1, '持续伤害': 1,
         '星核猎手': 1, '燃血': 1}
    assert board_factions_of(_units_b()) == \
        {'燃血': 2, '贝洛伯格': 1, '治疗': 1, '星核猎手': 1}


def test_qualification_sets_side_pick(monkeypatch: pytest.MonkeyPatch) -> None:
    """聚合器 6 `_qualification_sets`(羁绊档位发放资格集,集合形状):
    watched 不含贝洛伯格/燃血(现值 = 弹窗两阵营 + 伙伴 + 击破),
    monkeypatch 扩容 ENV_BOND_TIER_GRANTS 两试验条目使两羁绊入 watched
    ——布洛妮娅标签单边化后资格自动单边:场景甲她 ∈ 贝洛伯格集 ∉
    燃血集;场景乙翻转后 ∈ 燃血集 ∉ 贝洛伯格集。"""
    from sr_od.application.currency_war.kernel.cw_faction_callbacks import (
        _qualification_sets,
    )
    patched = dict(cw_investments.ENV_BOND_TIER_GRANTS)
    patched['试验环境:选边锁甲'] = ('贝洛伯格', '以太钻头')
    patched['试验环境:选边锁乙'] = ('燃血', '以太钻头')
    monkeypatch.setattr(cw_investments, 'ENV_BOND_TIER_GRANTS', patched)
    view_a = SimpleNamespace(front_slots=_units_a()[:2],
                             back_slots=_units_a()[2:])
    sets_a = _qualification_sets(view_a)
    assert sets_a['贝洛伯格'] == {'布洛妮娅', '娜塔莎', '桑博'}, \
        '选边计入边有资格'
    assert sets_a['燃血'] == {'刃'}, '非计入边无资格(单边化)'
    view_b = SimpleNamespace(front_slots=_units_b()[:2],
                             back_slots=_units_b()[2:])
    sets_b = _qualification_sets(view_b)
    assert sets_b['燃血'] == {'布洛妮娅', '刃'}, '翻转后计入边随选边'
    assert sets_b['贝洛伯格'] == {'娜塔莎'}, '翻转后原计入边失资格'


def test_resync_board_delta_full_recompute_degenerate() -> None:
    """聚合器 7 board 增量投影全量退化分支(``GameState._resync_board_
    delta``):布洛妮娅在场 ∧ 有增删 → 不走增量差量,按新行域全量聚合
    (带 peers)直接得新 board——选边翻转增量不可维护,断言写入值与
    全量聚合重算同值(`_recount_board` 同口径,零装备贡献时两者相等);
    布洛妮娅在场但零增删(纯重排)→ 零差零写(退化分支不误伤零增删)。"""
    gs = game_state_of(None)
    view_a = deployed_view_sequential(
        [], [_unit('布洛妮娅'), _unit('娜塔莎'), _unit('桑博'), _unit('刃')])
    gs.observe(gs.deployed, view_a, sig=_SIG_OBS)
    gs.observe(gs.board, _board_a(), sig=_SIG_OBS)
    # 场景甲 → 乙(卖 1 贝洛伯格):退化分支全量聚合,与 _recount_board 同值
    view_b = deployed_view_sequential(
        [], [_unit('布洛妮娅'), _unit('娜塔莎'), _unit('刃')])
    gs.write_logic(gs.deployed, view_b, produced_by='T', sig=_SIG)
    assert gs.board.value == _board_b(), \
        '选边翻转 → board 与全量聚合重算同值(增量差量退化)'
    assert gs.board.evidence == 'proj_board_resync', '派生证据名不变'
    # 纯重排(同单位多重集,布洛妮娅在场零增删)→ 零差零写(原帧未换)
    board_before = gs.board
    view_reorder = deployed_view_sequential(
        [], [_unit('刃'), _unit('布洛妮娅'), _unit('娜塔莎')])
    gs.write_logic(gs.deployed, view_reorder, produced_by='T', sig=_SIG)
    assert gs.board.value == _board_b(), '纯重排零差:board 不变'
    assert gs.board is board_before, '零增删 → 零 board 写(不退化)'


def test_sim_observe_board_truth_side_pick() -> None:
    """聚合器 8 `_observe_board_truth`(sim 板面真值,全量循环经
    ``_row_unit_tags`` peers 透传):SimBackend 直构(不装配,观察面
    纯状态容器读写)——场景甲真值 = 选边口径;行域写翻转后真值随选边。"""
    from sr_od.application.currency_war.sim.cw_sim_backend import SimBackend
    from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig
    b = SimBackend(seed=9, cfg=RunConfig(selected_difficulty='A8',
                                         enemy_difficulty=108))
    gs = b.gs
    view_a = deployed_view_sequential(
        [], [_unit('布洛妮娅'), _unit('娜塔莎'), _unit('桑博'), _unit('刃')])
    gs.write_logic(gs.deployed, view_a, produced_by='T', sig=_SIG)
    b._observe_board_truth()
    assert gs.board.value == _board_a(), 'sim 板面真值 = 选边口径(场景甲)'
    view_b = deployed_view_sequential(
        [], [_unit('布洛妮娅'), _unit('娜塔莎'), _unit('刃')])
    gs.write_logic(gs.deployed, view_b, produced_by='T', sig=_SIG)
    b._observe_board_truth()
    assert gs.board.value == _board_b(), '翻转后 sim 真值随选边(场景乙)'
