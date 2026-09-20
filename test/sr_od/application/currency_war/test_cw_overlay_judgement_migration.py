"""普查迁移批 2 锁面(overlay 三件选卡判据收编 kernel + 契约扩员 12→15)。

判据来源 = 对抗裁决 F-overlay-01/02/03(CONFIRMED;裁决过程档
`.debug/temp/audit-sweep/adjudication-1.md`,寿命随迁移批,锁语义自足)+
终态契约 design.md「契约扩员附记」。

行为保持判据:三件判据自画面 handler 逐位平移 kernel,期望值 = 迁移前
实码语义手推(同输入同输出):
- fortune:关键词权重累加(伤害倍率 3.0/强度提高 2.0/层数提高 2.0/
  伤害 1.0/提高 0.5)+ 严格大于 argmax(并列取首卡)+ 全无命中落首卡;
- expert:主力阵营(计数最大,并列取名字序首个)同线 → 任一在场同线 →
  -1 现金为王(board 空/卡空同款);在场浓度版,E9 规格分叉已挂账不改;
- equip:key_fit 子串 +100 压倒泛用关键词 +1.0,并列取首卡,锁定线解析
  失败按未锁态。

契约面锁:三新 Pick 子类型入双注册表;ABC 抽象入口 15;flow 三零参入口
= 槽离屏 ValueError(观察层失约)+ 写槽后同 kernel 结论(同输入同输出)+
equip 意向注入(self.state.locked_comp → kernel 参数)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_equip_value import (
    decide_equip_overlay_pick,
)
from sr_od.application.currency_war.kernel.cw_events import (
    choose_expert_index,
    decide_fortune,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    ExpertInvitePayload,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.kernel.cw_vocab import (
    CW_ACTION_TYPES,
    PICK_ACTION_TYPES,
    CwActionPickEquipParam,
    CwActionPickExpertInviteParam,
    CwActionPickFortuneParam,
)

_SIG = ChannelSig(family='logic_action', actor='cw-mig2-test', mode='compute')


def _fresh_gs():
    """独立容器(桩 session 宿主;弱引用表按宿主隔离,零跨测残留)。"""
    return game_state_of(SimpleNamespace())


# ==================== F-overlay-01:命运卜者(decide_fortune)====================

def test_fortune_keyword_weights_cumulative_and_first_card_tie():
    """权重累加制 + 严格大于 argmax + 无匹配缺省首卡(迁移前实码语义)。"""
    # 「伤害倍率提高」= 伤害倍率3.0 + 子串伤害1.0 + 提高0.5 = 4.5 > 强度提高2.5
    assert decide_fortune(['伤害倍率提高', '强度提高', '层数提高']) == 0
    assert decide_fortune(['无关键词甲', '强度提高', '伤害']) == 1
    assert decide_fortune(['甲', '乙', '提高']) == 2
    # 累加制:「伤害倍率」文同时命中「伤害」「提高」子串(既有行为非缺陷)
    assert decide_fortune(['甲', '伤害倍率']) == 1
    # 严格大于:同分并列取首卡
    assert decide_fortune(['强度提高', '强度提高']) == 0
    # 全无命中 / 空输入 = 首卡缺省
    assert decide_fortune(['甲', '乙', '丙']) == 0
    assert decide_fortune([]) == 0


# ==================== F-overlay-02:专家邀请函(choose_expert_index)====================

def test_expert_dominant_line_then_any_present_line_then_cash():
    """三级语义原样(在场浓度版):主力同线 → 任一在场同线 → -1 现金为王。"""
    # ① 主力阵营(计数最大)同线优先
    assert choose_expert_index(['仙舟', None, '贝洛伯格', None],
                               {'仙舟': 3}) == 0
    # 并列取名字序首个(确定性):'仙舟' < '贝洛伯格'
    assert choose_expert_index(['贝洛伯格', '仙舟'],
                               {'仙舟': 2, '贝洛伯格': 2}) == 1
    # ② 主力阵营不在卡上 → 任一在场阵营同线(卡序先者)
    assert choose_expert_index(['量子同频', '贝洛伯格'],
                               {'欢愉': 2, '贝洛伯格': 1}) == 1
    # ③ 全无同线 → -1;board 空(读数失败)/卡空同款
    assert choose_expert_index(['仙舟', '贝洛伯格'], {'欢愉': 2}) == -1
    assert choose_expert_index(['仙舟'], {}) == -1
    assert choose_expert_index([], {'仙舟': 1}) == -1


# ==================== F-overlay-03:选择装备(decide_equip_overlay_pick)====================

def test_equip_overlay_generic_leg_and_defaults(monkeypatch):
    """未锁态 = 仅泛用关键词腿;key_fit 子串 +100 压倒泛用;并列/空取首卡。"""
    # 未锁:泛用腿(伤害/强度/提高)命中者胜
    assert decide_equip_overlay_pick(['无特效甲', '强度提高药剂'],
                                     locked_comp='') == 1
    # 全无命中并列取首卡;空输入取 0
    assert decide_equip_overlay_pick(['甲', '乙'], locked_comp='') == 0
    assert decide_equip_overlay_pick([], locked_comp='') == 0

    # 锁定线:key_fit_names(成品∪材料)子串命中 +100,压过泛用腿
    import sr_od.application.currency_war.kernel.cw_comps as cw_comps_mod

    def _fake_get_comp(name: str):
        if name == '目标线':
            return SimpleNamespace(key_equips=('轮滑鞋',))
        return None

    monkeypatch.setattr(cw_comps_mod, 'get_comp', _fake_get_comp)
    assert decide_equip_overlay_pick(['伤害提高药剂', '轮滑鞋·改'],
                                     locked_comp='目标线') == 1
    # 注册表漂移(锁线解析失败)= 按未锁态(仅泛用腿,保守:漏提权非错提权)
    assert decide_equip_overlay_pick(['伤害提高药剂', '无特效乙'],
                                     locked_comp='不存在的线') == 0


# ==================== 契约面:扩员 12→15 ====================

def test_new_pick_types_in_both_registries():
    """三新子类型入统一词表与选择族单表,且逐类自持 idx/reason 字段
    (词表摊平后无公共基类,选择族契约 = 逐类重声明)。"""
    for cls in (CwActionPickFortuneParam, CwActionPickExpertInviteParam, CwActionPickEquipParam):
        assert cls in CW_ACTION_TYPES, cls.__name__
        assert cls in PICK_ACTION_TYPES, cls.__name__
        assert 'idx' in cls.__dataclass_fields__, cls.__name__
        assert 'reason' in cls.__dataclass_fields__, cls.__name__


def test_abstract_entries_expanded_to_15():
    """ABC 抽象入口 12→15:三新零参入口在 abstract 集(运行时契约面)。"""
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        CwStrategy,
    )
    abstract_names = CwStrategy.__abstractmethods__
    for name in ('decide_fortune', 'decide_expert_invite', 'decide_equip_pick'):
        assert name in abstract_names, name


# ==================== flow 三零参入口(写槽 → 同 kernel 结论)====================

def _live(gs):
    """活策略核(mandate_v1 具现;构造注入,light)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import bridge
    return bridge.MandateV1Strategy(gs, SimpleNamespace(strategy_seed=None))


def test_flow_entries_fail_loud_on_offscreen_slot():
    """槽离屏(None)= 观察层失约抛错,禁静默按空态决策(黑板契约)。"""
    strategy = _live(_fresh_gs())
    with pytest.raises(ValueError):
        strategy.decide_fortune()
    with pytest.raises(ValueError):
        strategy.decide_expert_invite()
    with pytest.raises(ValueError):
        strategy.decide_equip_pick()


def test_flow_decide_fortune_reads_slot_returns_action():
    """写槽 → decide_fortune:同输入同 kernel 结论,产物 = CwActionPickFortuneParam。"""
    gs = _fresh_gs()
    gs.write_logic(gs.fortune_opts, ['无关键词', '强度提高'],
                   produced_by='cw-mig2-test', sig=_SIG)
    pick = _live(gs).decide_fortune()
    assert isinstance(pick, CwActionPickFortuneParam)
    assert pick.idx == decide_fortune(['无关键词', '强度提高']) == 1


def test_flow_decide_expert_invite_cash_and_card_paths():
    """写槽(弹窗载体)→ decide_expert_invite:现金为王(-1)与真选卡两路。"""
    gs = _fresh_gs()
    gs.write_logic(
        gs.expert_invite,
        ExpertInvitePayload(card_bonds=['仙舟', None], board={}),
        produced_by='cw-mig2-test', sig=_SIG)
    pick = _live(gs).decide_expert_invite()
    assert isinstance(pick, CwActionPickExpertInviteParam)
    assert pick.idx == -1   # board 空 = 现金为王兜底
    gs.write_logic(
        gs.expert_invite,
        ExpertInvitePayload(card_bonds=[None, '仙舟'], board={'仙舟': 2}),
        produced_by='cw-mig2-test', sig=_SIG)
    assert _live(gs).decide_expert_invite().idx == 1   # 主力同线卡


def test_flow_decide_equip_pick_injects_locked_comp(monkeypatch):
    """equip 意向注入:handler 零意向读,flow 入口自 self.state 取
    locked_comp 注 kernel → key_fit 腿生效(压过泛用腿)。"""
    import sr_od.application.currency_war.kernel.cw_comps as cw_comps_mod

    def _fake_get_comp(name: str):
        if name == '目标线':
            return SimpleNamespace(key_equips=('轮滑鞋',))
        return None

    monkeypatch.setattr(cw_comps_mod, 'get_comp', _fake_get_comp)
    gs = _fresh_gs()
    gs.write_logic(gs.equip_pick_opts, ['伤害提高药剂', '轮滑鞋·改'],
                   produced_by='cw-mig2-test', sig=_SIG)
    strategy = _live(gs)
    strategy.state.v3_intention = IntentionState()
    strategy.state.v3_intention.locked_comp = '目标线'
    pick = strategy.decide_equip_pick()
    assert isinstance(pick, CwActionPickEquipParam)
    assert pick.idx == 1   # key_fit 子串 +100 压过泛用腿
