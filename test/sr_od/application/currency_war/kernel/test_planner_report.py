"""银狼策划上报测试面(分支类型判定单源 / 名称归一分层 / 分支应用三态 / 采样池)。

判据权威版本(持久索引):银狼闭环设计 §2.0/§2.1/§2.4(docs/develop/
sr_od/application/currency_war/ 迭代详设;单相即时上报契约 §2.0)。
测试面:

- **分支类型判定单源**(§2.1①):装备域优先——破解芯片卡文含「弱化」
  仍判 equip(碰撞治理);longest-match(分身墨镜Max 不被短名截胡);相似
  归一唯一命中;多命中 = equip 且件名未解析(禁猜);升费关键词/unknown
  (弱化兜底档已退役:含弱化词未知名卡文落 unknown);
- **打分两档制**(升费档 > 装备档):无名弱化卡文零弱化档分,按装备档回落;
- **装备入账分支**(§2.1②):归一命中 → 入栏 + 获得后果链;未解析 → 值不变
  翻来源 + 留证;unknown = 零记账 + 留证(含弱化词未知名卡文退役后落此档);
- **即时单相上报**(§2.0):确认点击后一次上报即应用完整效果分支,无发射/
  落地两相、无证据一次性标志位;
- **注册表级装备名分层归一**(``normalize_registry_equip_name``):互撞族
  精确快道恒命中 / OCR 形变救援(containment + LCS 唯一命中)/ 多命中
  拒识(fail-closed 禁猜);
- **采样链 v0 池**(§2.4):硬编码名单(4 费排除 Max 件口径)无 Max 件,
  种子可复现;
- **好运令牌后果链基准**(§2.2 全渠道):apply_equip_acquire_consequence
  对表外件零写零行为、表内件送出单位。

观察收尾(等值静默/差异 logic_rand_outcome)= 基座测试
test_game_state.py::test_write_logic_rand_and_observe_random_outcome,
不重复。
"""
from __future__ import annotations

import random

import pytest

from sr_od.application.currency_war.kernel.cw_events import (
    PlannerOption,
    classify_planner_branch,
    decide_planner,
    normalize_equip_name,
    normalize_registry_equip_name,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
    bench_units_of,
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionPickInvestStrategyParam,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')


def _lsig(actor: str = 'CwScreenYinLang') -> ChannelSig:
    return ChannelSig(family='logic_action', actor=actor, mode='compute')


def _make_gs(*, bench: list[tuple[str, int]] | None = None,
             equips: list[str] | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察,供 None 边界分支)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if bench is not None:
        slots = [BenchSlot(kind='unit',
                           unit=Unit(char_id=c, star=s))
                 for i, (c, s) in enumerate(bench)]
        slots += [BenchSlot(kind='empty')] * (9 - len(slots))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    if equips is not None:
        gs.observe(gs.equips, list(equips), sig=_SIG_OBS)
    return gs


class _RowSink:
    """缺陷台账行收集(set_defect_sink 缺省关,fixture 装配 + 必达收尾)。"""

    def __init__(self) -> None:
        self.rows: list[dict] = []
        set_defect_sink(self.rows.append)

    def close(self) -> None:
        set_defect_sink(None)
        consume_defect_sink()

    def kinds(self) -> list[str]:
        return [r['kind'] for r in self.rows]


@pytest.fixture
def rows_sink() -> _RowSink:
    s = _RowSink()
    try:
        yield s
    finally:
        s.close()


# ============================================================ 分支类型判定单源


def test_leg_classifier_equip_domain_first_and_longest_match() -> None:
    """分支类型分类测试(design §2.1①):装备域优先——破解芯片卡文含「弱化」
    仍判 equip(决策关键词碰撞治理);longest-match;相似归一;多命中
    = equip+未解析;关键词降级;unknown。"""
    # 破解芯片 = 名字 + 含「弱化」效果文 → 装备域识别标志先行(碰撞治理;
    # 含弱化词未知名卡文退役后落 unknown)。
    assert classify_planner_branch(
        '破解芯片 前台强度 30% 首次穿戴该装备时，会使多个节点变为弱化状'
        '态：敌人的生命上限降低10%，伤害降低 20%') == ('equip', '破解芯片')
    # longest-match:分身墨镜Max 不被短名「分身墨镜」截胡。
    assert classify_planner_branch(
        '分身墨镜Max 获得时解锁并获得2星专家【银狼】') == ('equip', '分身墨镜Max')
    assert classify_planner_branch(
        '分身墨镜 获得时解锁并获得1星专家【银狼】') == ('equip', '分身墨镜')
    # 相似归一:OCR 形变(基础名破坏)唯一命中。
    assert normalize_equip_name('破解 芯片!') == '破解芯片'
    assert classify_planner_branch('破解 芯片!') == ('equip', '破解芯片')
    # 多命中(识别标志未中,注册表多件同时高相似)= 装备信号成立、件名未解析
    # (禁猜——繁体形变使「数据拷贝仪」基础名识别标志不中,Max 与基础名同时高相似)。
    assert normalize_equip_name('数據拷贝仪Max') == ''
    assert classify_planner_branch('数據拷贝仪Max') == ('equip', '')
    # 关键词(识别标志/相似均未中才轮到;弱化兜底档退役后含弱化词未知名卡文同落 unknown)。
    assert classify_planner_branch(
        '提升费用至4费,变为1星银狼LV.999') == ('upgrade', '')
    assert classify_planner_branch('使后续节点【弱化】') == ('unknown', '')
    assert classify_planner_branch('随便什么不认识的卡') == ('unknown', '')
    assert classify_planner_branch('') == ('unknown', '')


def test_decide_planner_weaken_tier_retired(rows_sink: _RowSink) -> None:
    """打分两档制退役测试(升费档 > 装备档):无名弱化卡文零弱化档分——按
    装备档回落(reason = 装备(...)),不再有 55 分「全场弱化」占优档;
    已知装备小分卡(轮滑鞋 = 4 分)对无名弱化卡文(0 分)胜出(退役前
    55 分弱化档占优)。"""
    gs = _make_gs(bench=[], equips=[])
    pick = decide_planner(
        [PlannerOption(idx=0, text='使后续节点【弱化】'),
         PlannerOption(idx=1, text='轮滑鞋')], gs)
    assert pick.idx == 1, '装备档 4 分胜出(退役前弱化档 55 分占优)'
    assert '全场弱化' not in pick.reason
    pick2 = decide_planner(
        [PlannerOption(idx=0, text='使后续节点【弱化】')], gs)
    assert pick2.idx == 0
    assert pick2.reason.startswith('装备('), '无名弱化卡文按装备档回落'
    assert '全场弱化' not in pick2.reason, '弱化档 reason 词已不存在'


# ============================================================ 装备入账分支与 unknown 分支


def test_equip_leg_gain_with_consequence_chain(
        rows_sink: _RowSink) -> None:
    """装备入账分支(design §2.1②/§2.2):入栏 + 获得后果链(分身墨镜送 1★银狼
    进备战席,与 2× 既有 1★ 银狼合成升星——效果同商店购买)。"""
    gs = _make_gs(bench=[('银狼', 1), ('银狼', 1)], equips=['幸运星'])
    from sr_od.application.currency_war.kernel.cw_action_report.pick_planner import (
        report_action_pick_planner_param,
    )
    out = report_action_pick_planner_param(gs, None, branch_type='equip',
                                           norm_item='分身墨镜', sig=_lsig())
    assert out.applied is True
    assert gs.equips.value == ['幸运星', '分身墨镜'], '装备入栏'
    assert gs.equips.source == 'logic'
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units == [('银狼', 2)], '送出 1★银狼与既有两枚合成 → 2★(购买同语义)'
    assert gs.bench.source == 'logic', '后果链确定面同源 write_logic'
    assert rows_sink.kinds() == [], '表内件零留证行'


def test_equip_leg_unresolved_flips_source(
        rows_sink: _RowSink) -> None:
    """未解析(norm_item='')→ 禁猜名:equips 值不变翻来源 + 留证行。"""
    from sr_od.application.currency_war.kernel.cw_action_report.pick_planner import (
        report_action_pick_planner_param,
    )
    gs = _make_gs(bench=[('希儿', 1)], equips=['幸运星'])
    out = report_action_pick_planner_param(gs, None, branch_type='equip',
                                           norm_item='', sig=_lsig())
    assert out.applied is True
    assert gs.equips.value == ['幸运星'], '值不变'
    assert gs.equips.source == 'logic_rand', '翻来源(观察差异收尾自愈)'
    assert rows_sink.kinds() == ['planner_equip_name_unresolved']
    assert gs.bench.source == 'observation', '无后果链(不猜件名)'


def test_unknown_leg_evidenced_zero_write(
        rows_sink: _RowSink) -> None:
    """unknown = 零记账 + 留证证未识别事实(含弱化词未知名卡文退役后落
    此档——静默零记账变响亮申报;原 weaken 派发分支已删,未路由分支类型 =
    终态兜底零写)。"""
    from sr_od.application.currency_war.kernel.cw_action_report.pick_planner import (
        report_action_pick_planner_param,
    )
    gs = _make_gs(bench=[('希儿', 1)], equips=[])
    seq_before = gs.write_seq
    out = report_action_pick_planner_param(gs, None, branch_type='unknown',
                                           norm_item='', sig=_lsig())
    assert out.applied is True and gs.write_seq == seq_before, '零容器写'
    assert rows_sink.kinds() == ['planner_leg_unknown']
    out2 = report_action_pick_planner_param(gs, None, branch_type='',
                                            norm_item='', sig=_lsig())
    assert out2.applied is True and gs.write_seq == seq_before
    assert out2.reason == 'unrouted_leg_zero_write', '终态兜底 reason 更名'
    assert rows_sink.kinds() == ['planner_leg_unknown'], '兜底零留证'


# ============================================================ 即时单相上报


def test_planner_report_is_immediate_single_phase(
        rows_sink: _RowSink) -> None:
    """单相即时上报测试(design §2.0):确认点击后一次上报即应用效果分支
    (2★ 源即消费)——无发射相零写窗、无落地证据一次性标志位(两相已退役)。"""
    from sr_od.application.currency_war.kernel.cw_action_report.pick_planner import (
        report_action_pick_planner_param,
    )
    gs = _make_gs(bench=[('银狼LV.999', 2)], equips=['幸运星'])
    param = CwActionPickInvestStrategyParam(idx=1, norm_name='骇客专家:银狼')
    out1 = report_action_pick_planner_param(gs, param, _lsig('CwActionPickPlannerOp'),
                                            branch_type='upgrade')
    assert out1.applied is True
    assert gs.bench.value.slots[0].unit.star == 1, '一次上报即变换(无证据一次性标志位)'
    assert gs.active_strategies.value in (None, []), '持卡面未被 planner 上报触碰'


# ============================================================ 注册表级名称分层归一


def test_registry_norm_exact_hits_on_collision_families() -> None:
    """互撞族/特权/后缀族完美 OCR 恒命中(第 1 层精确快道):纯 LCS 判据
    直移 158 名键集时这些名会多命中拒识——精确相等必须先走快道。"""
    for name in ('垃圾袋', '金垃圾袋', '生命之花', '生命之环',
                 '追击星徽', '击破星徽', '昼之半神星徽', '夜之半神星徽',
                 '很硬的甲', '很硬的甲·特权', '分身墨镜', '分身墨镜Max',
                 '数据拷贝仪Pro', '管理员手套ProMax',
                 '白昼·光速螺旋桨', '极·白昼·光速螺旋桨',
                 '财富', '财富(基础)', '穿刺死棘之枪', '穿越死棘之枪'):
        assert normalize_registry_equip_name(name) == name, \
            f'完美 OCR 恒命中(精确快道):{name}'


def test_registry_norm_rescues_ocr_deformation() -> None:
    """OCR 形变救援:containment 层消解装饰噪声(括号/前后缀文案,
    longest-first 使后缀族长名胜出);相似层救援无 containment 命中的
    字形形变(LCS ≥0.75 唯一命中)。"""
    assert normalize_registry_equip_name('【垃圾袋】') == '垃圾袋'
    assert normalize_registry_equip_name('生命之花!') == '生命之花'
    assert normalize_registry_equip_name('获得 信心注入器·特权 x1') \
        == '信心注入器·特权'
    assert normalize_registry_equip_name('极·白昼·光速螺旋桨(已装备)') \
        == '极·白昼·光速螺旋桨', 'longest-first:极·白昼 先于 白昼· 胜出'
    assert normalize_registry_equip_name('折叠小偈') == '折叠小刀', \
        '字形形变相似救援(无 containment 命中,LCS 3/4 唯一)'


def test_registry_norm_multi_hit_refuses() -> None:
    """多命中拒识(fail-closed,禁猜):相似层多命中返回 ''(追击/击破
    星徽互撞形变);containment 并列最长落相似层后仍多命中返回 '';
    注册表外名零命中返回 ''。"""
    assert normalize_registry_equip_name('追 击星徽') == '', \
        '相似层双命中(追击星徽 LCS 1.0 / 击破星徽 0.75)= 拒识'
    assert normalize_registry_equip_name('生命之花与生命之环') == '', \
        'containment 并列最长(两 4 字键)→ 相似层多命中 = 拒识'
    assert normalize_registry_equip_name('星币收集器') == '', \
        '注册表外名零命中 = 拒识(禁猜)'


# ============================================================ 采样链 v0 池


def test_hacker_mod_pool_v0_no_max() -> None:
    """采样链 v0 池形状测试(design §2.4):硬编码名单 = 4 费装备排除 Max 件
    的显式第二真相源——成员恒 5(专属 10 件的非 Max 件),零 Max 件,种子
    可复现(同种子同序列)。"""
    from sr_od.application.currency_war.data.cw_equipment_wear_rules_data import (
        ITEM_WEAR_GATES,
    )
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        HACKER_MOD_POOL_V0,
        roll_hacker_mod,
    )
    assert len(HACKER_MOD_POOL_V0) == 5
    assert all(not n.endswith('Max') for n in HACKER_MOD_POOL_V0), \
        '排除 Max 件(用户定为临时口径)'
    assert all(n in ITEM_WEAR_GATES for n in HACKER_MOD_POOL_V0), \
        '成员 ⊆ 银狼专属 10 件名单'
    a = [roll_hacker_mod(random.Random(7)) for _ in range(20)]
    b = [roll_hacker_mod(random.Random(7)) for _ in range(20)]
    assert a == b and set(a) <= set(HACKER_MOD_POOL_V0), '种子可复现'
