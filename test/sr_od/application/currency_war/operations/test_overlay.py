"""货币战争 overlay 生命周期行为锁(选卡判据 / 触发登记 / 消费呈现 /
身份两段式 / 路由清点)。

五个部分(overlay 从「判据 → 登记 → 呈现/消费 → 识别收口 → 残留清理」
的一条生命周期线,外加 CwLoop 侧残面清理):

- **选卡判据 kernel**(原 overlay 三件选卡判据收编 kernel 的行为保持面):
  fortune 权重累加 + 严格大于 argmax + 无匹配缺省首卡;expert 主力阵营
  三级语义;flow 三零参入口契约(槽离屏 ValueError 响亮 / 写槽后同
  kernel 结论)。
- **触发登记**(S1-S6 判据逐条):伙伴成员增减/星徽穿卸/合成集不变静默;
  巨星跨档上穿与重选两形态;祈愿首达档一次;planner 合成落场上/2★ 上场
  /每费用档一次;占卜屋黑天鹅计数;阿哈/open_* 直登;登记三口契约
  (去重/消费/清空 + kind 封闭集)与回调边界(观察写/值等写零回调)。
- **消费呈现**:八选卡上报消费同 kind;sim 逐 kind 呈现门(fortune 仅
  底层=备战)/无模型 kind 消费披露;宿主交回(备战/商店两宿主每动作后
  pending 非空 → round_success 交回);kernel 兜底清空(清 pending 连
  簿记,生命周期 = 局)。
- **身份两段式**(CwLoop 真实现 ``_resolve_frame_identity``):pending 首
  中优先/未中落全扫描 + 对账行留证(B1 回归);底屏锚条目不入两段式
  (B2 回归,防备战名死循环);CwLoop 兜底清空(清 pending 不清簿记)
  与 sim 态直跳;M1 回归:settle_confirm 登记 fortune → 节点窗起点先落
  底层屏再查呈现门。
- **路由清点**(CwLoop ``_route_clear_stale_payloads``):未识别轮清全部
  可清槽;属屏命中轮只清异属屏;shop 豁免永不清;已 None 跳过。

纪律:零真实副作用(纯容器 + 桩面 + sim 后端装拆);缺陷台账缓冲前后
双清防跨用例顺序依赖。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import sr_od.application.currency_war.operations.cw_loop as loop_mod
from sr_od.application.currency_war.kernel.cw_events import (
    EncounterOption,
    SupplyOption,
    choose_expert_index,
    decide_fortune,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    _PAYLOAD_DOMAINS,
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    EncounterPayload,
    ExpertInvitePayload,
    GameState,
    ShopActionExecuted,
    ShopPayload,
    ShopSlot,
    SupplyPayload,
    Unit,
    consume_defect_sink,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_overlay_register import (
    KIND_SCREEN_NAMES,
    SCREEN_CHANGE_KINDS,
    clear_screen_changes,
    consume_screen_change,
    register_screen_change,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
    CwActionOpenBookcardParam,
    CwActionOpenBoxParam,
    CwActionOpenTomeParam,
    CwActionPickExpertInviteParam,
    CwActionPickFortuneParam,
    CwActionWearEquipParam,
    ShopCard,
)
from sr_od.application.currency_war.kernel.cw_world_decl import WorldDecl
from sr_od.application.currency_war.operations.cw_loop import CwLoop
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SimBackend,
    install_backend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_overlay import (
    OVERLAY_PARAM_PENDING,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_SIG_OBS = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')
_SIG = ChannelSig(family='logic_action', actor='test', mode='compute')
_CFG = RunConfig(selected_difficulty='A8', enemy_difficulty=108)

_OBS_SIG = ChannelSig(family='obs', actor='cw_observation',
                      screen='货币战争-遭遇节点', mode='read')


@pytest.fixture(autouse=True)
def _drain_defect_buffer():
    """测试卫生:登记/呈现/主域种子全程零 Field 写时无缓冲行,前后双清
    保持纪律(防跨用例顺序依赖红)。"""
    consume_defect_sink()
    yield
    consume_defect_sink()


# ============================================================
# 一、选卡判据 kernel(F-overlay 行为保持面)
# ============================================================


def _fresh_gs():
    """独立容器(桩 session 宿主;弱引用表按宿主隔离,零跨测残留)。"""
    return game_state_of(SimpleNamespace())


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


def test_flow_decide_fortune_reads_slot_returns_action():
    """写槽 → decide_fortune:同输入同 kernel 结论,产物 = CwActionPickFortuneParam。"""
    gs = _fresh_gs()
    gs.write_logic(gs.fortune_opts, ['无关键词', '强度提高'],
                   produced_by='test', sig=_SIG)
    pick = _live(gs).decide_fortune()
    assert isinstance(pick, CwActionPickFortuneParam)
    assert pick.idx == decide_fortune(['无关键词', '强度提高']) == 1


def test_flow_decide_expert_invite_cash_and_card_paths():
    """写槽(弹窗载体)→ decide_expert_invite:现金为王(-1)与真选卡两路。"""
    gs = _fresh_gs()
    gs.write_logic(
        gs.expert_invite,
        ExpertInvitePayload(card_bonds=['仙舟', None], board={}),
        produced_by='test', sig=_SIG)
    pick = _live(gs).decide_expert_invite()
    assert isinstance(pick, CwActionPickExpertInviteParam)
    assert pick.idx == -1   # board 空 = 现金为王兜底
    gs.write_logic(
        gs.expert_invite,
        ExpertInvitePayload(card_bonds=[None, '仙舟'], board={'仙舟': 2}),
        produced_by='test', sig=_SIG)
    assert _live(gs).decide_expert_invite().idx == 1   # 主力同线卡


# ============================================================
# 二、触发登记(S1-S6 判据)
# ============================================================


def _gs() -> GameState:
    return GameState(schema_version=GAME_STATE_SCHEMA_VERSION)


def _view(front: list = (), back: list = ()) -> DeployedView:
    """紧凑序 → 视图(front/back = Unit 列表,顺延落位)。"""
    f = list(front) + [None] * (4 - len(front))
    b = list(back) + [None] * (6 - len(back))
    return DeployedView(front_slots=f, back_slots=b)


def _u(cid: str, star: int = 1, equips: list | None = None) -> Unit:
    return Unit(char_id=cid, star=star, equips=list(equips or []))


def _write_dep(gs: GameState, view: DeployedView, source: str = 'test') -> None:
    """deployed 逻辑写(生产写路径 = write_logic → 值回调级联)。"""
    gs.write_logic(gs.deployed, view, produced_by=source,
                   evidence='t', sig=_SIG)


def _pending_kinds(gs: GameState) -> list[str]:
    return [p.kind for p in gs.screen_changes.pending]


class TestRegisterContract:
    def test_dedup_consume_clear_and_kind_closure(self):
        gs = _gs()
        register_screen_change(gs, 'megastar', KIND_SCREEN_NAMES['megastar'],
                               't')
        register_screen_change(gs, 'megastar', KIND_SCREEN_NAMES['megastar'],
                               't2')   # 同 kind 去重
        register_screen_change(gs, 'partner', KIND_SCREEN_NAMES['partner'],
                               't')
        assert _pending_kinds(gs) == ['megastar', 'partner'], 'FIFO + 去重'
        consume_screen_change(gs, 'partner')   # 与顺序无关的消费
        assert _pending_kinds(gs) == ['megastar']
        consume_screen_change(gs, 'partner')   # 不在册 = no-op
        clear_screen_changes(gs)
        assert _pending_kinds(gs) == []
        with pytest.raises(ValueError, match='集外'):
            register_screen_change(gs, 'bogus', 'x', 't')
        assert len(SCREEN_CHANGE_KINDS) == 9, 'kind 词表九项'


class TestPartnerTrigger:
    def test_member_add_with_anchor_fires(self):
        """成员增(姬子·启行在场 ∧ 另有成员)→ partner 登记
        (两种首触:三月七先上 + 姬子后上,后一写触发)。"""
        gs = _gs()
        _write_dep(gs, _view(front=[_u('三月七')]))
        assert _pending_kinds(gs) == []   # 姬子不在场:前提不满足
        _write_dep(gs, _view(front=[_u('三月七'), _u('姬子·启行')]))
        assert _pending_kinds(gs) == ['partner']

    def test_member_removal_fires_and_to_anchor_only_not(self):
        """成员减弹(写后仍 ≥2 人:姬子 + 另一成员);卖到只剩姬子不弹
        (「另有成员」前提不满足——用户确认口径 §1.2 在册边界)。"""
        gs = _gs()
        _write_dep(gs, _view(front=[_u('三月七'), _u('姬子·启行'),
                                     _u('丹恒·饮月')]))
        consume_screen_change(gs, 'partner')
        _write_dep(gs, _view(front=[_u('姬子·启行'), _u('丹恒·饮月')]))
        assert _pending_kinds(gs) == ['partner'], '成员减(剩 2 人)弹'
        consume_screen_change(gs, 'partner')
        _write_dep(gs, _view(front=[_u('姬子·启行')]))
        assert _pending_kinds(gs) == [], '卖到只剩姬子:不弹'

    def test_badge_wear_unwear_qualification_change(self):
        """星徽穿卸改资格集:非出身角色穿「列车同行星徽」获资格 → 弹;
        卸(含装备整体变化)失资格 → 弹(写后姬子 + 出身成员仍 ≥2)。"""
        gs = _gs()
        _write_dep(gs, _view(front=[_u('花火'), _u('姬子·启行'),
                                     _u('三月七')]))
        consume_screen_change(gs, 'partner')
        _write_dep(gs, _view(front=[_u('花火',
                                       equips=['列车同行星徽']),
                                    _u('姬子·启行'), _u('三月七')]))
        assert _pending_kinds(gs) == ['partner'], '穿徽获资格 = 集合增'
        consume_screen_change(gs, 'partner')
        _write_dep(gs, _view(front=[_u('花火'), _u('姬子·启行'),
                                     _u('三月七')]))
        assert _pending_kinds(gs) == ['partner'], '卸徽失资格 = 集合减'

    def test_classic_merge_keeps_set_silent(self):
        """经典合成不弹:三月七 1★×2 → 2★×1,名集合不变(零排除规则的
        结构性结果,非排除判断)。"""
        gs = _gs()
        _write_dep(gs, _view(front=[_u('三月七'), _u('三月七', star=2),
                                    _u('姬子·启行')]))
        consume_screen_change(gs, 'partner')
        _write_dep(gs, _view(front=[_u('三月七', star=2),
                                    _u('姬子·启行')]))
        assert _pending_kinds(gs) == [], '名集合不变 → 静默(存活对仅星变)'

    def test_merge_inheritance_badge_gain_fires(self):
        """合成继承获资格弹(用户裁定):非列车同出身的花火经单写获得
        「列车同行星徽」(合成继承形态的最小表达:存活对 equips 差含
        星徽;真实合成链 = 载体 equips 三方并集,资格变化面同此差)→
        集合真变 → partner 登记。"""
        gs = _gs()
        _write_dep(gs, _view(front=[_u('花火'), _u('姬子·启行'),
                                     _u('三月七')]))
        consume_screen_change(gs, 'partner')
        _write_dep(gs, _view(front=[_u('花火',
                                       equips=['列车同行星徽']),
                                    _u('姬子·启行'), _u('三月七')]))
        assert _pending_kinds(gs) == ['partner'], \
            '存活对装备差含星徽(继承获徽)= 集合增 → 弹'

    def test_badge_already_held_equip_change_silent(self):
        """徽保持静默边界:徽已持,后续装备变化(加非徽件)不改资格集
        → 不弹(资格集只看星徽在场性,不看装备数量)。"""
        gs = _gs()
        _write_dep(gs, _view(front=[_u('花火',
                                       equips=['列车同行星徽']),
                                    _u('姬子·启行'), _u('三月七')]))
        consume_screen_change(gs, 'partner')
        _write_dep(gs, _view(front=[_u('花火',
                                       equips=['列车同行星徽', '轮滑鞋']),
                                    _u('姬子·启行'), _u('三月七')]))
        assert _pending_kinds(gs) == [], '资格未变(徽已持):静默'

    def test_row_switch_non_trailblazer_silent(self):
        """换排(非开拓者)不弹:资格集与排无关(仅开拓者形态按排)。"""
        gs = _gs()
        _write_dep(gs, _view(front=[_u('三月七'), _u('姬子·启行')]))
        consume_screen_change(gs, 'partner')
        _write_dep(gs, _view(front=[_u('姬子·启行')], back=[_u('三月七')]))
        assert _pending_kinds(gs) == [], '排面变化零资格差 → 静默'


class TestMegastarUpcross:
    def test_first_member_no_fire_second_upcross_fires(self):
        """首档门槛:首成员上场不弹(1 < 2);第二成员上穿上档 → 弹。"""
        gs = _gs()
        _write_dep(gs, _view(front=[_u('花火')]))
        assert _pending_kinds(gs) == []
        _write_dep(gs, _view(front=[_u('花火'), _u('知更鸟')]))
        assert _pending_kinds(gs) == ['megastar']

    def test_downgrade_and_reup_fire_again_no_bookkeeping(self):
        """降档再升也弹(无簿记,用户裁定):3→2 不弹(下穿),2→3 上穿
        → 再弹。"""
        gs = _gs()
        _write_dep(gs, _view(front=[_u('花火'), _u('知更鸟'), _u('黑天鹅')]))
        consume_screen_change(gs, 'megastar')
        _write_dep(gs, _view(front=[_u('花火'), _u('知更鸟')]))
        assert _pending_kinds(gs) == [], '下穿不弹'
        _write_dep(gs, _view(front=[_u('花火'), _u('知更鸟'), _u('黑天鹅')]))
        assert _pending_kinds(gs) == ['megastar'], '再上穿即弹(无簿记)'


class TestWishTrialUpcross:
    def test_first_reach_fires_once_refall_reup_not(self):
        """祈愿首达档一次(降档再回不弹,用户裁定):2 档首达弹;
        2→1 降,1→2 再上穿档已弹过 → 不弹。"""
        gs = _gs()
        _write_dep(gs, _view(front=[_u('Saber'), _u('Archer')]))
        assert _pending_kinds(gs) == ['wish_trial']
        assert gs.screen_changes.wish_tiers_fired == {2}
        consume_screen_change(gs, 'wish_trial')
        _write_dep(gs, _view(front=[_u('Saber')]))
        assert _pending_kinds(gs) == []
        _write_dep(gs, _view(front=[_u('Saber'), _u('Archer')]))
        assert _pending_kinds(gs) == [], '档已弹过:降档再回不弹'
        _write_dep(gs, _view(front=[_u('Saber'), _u('Archer'),
                                     _u('远坂凛')]))
        assert _pending_kinds(gs) == ['wish_trial'], '更高档(3)首达仍弹'


class TestMegastarReselect:
    def test_chosen_removed_with_count_held_fires(self):
        """重选·名消失:chosen 卖出/下场,写后计数仍达首档(2)→ 弹。"""
        gs = _gs()
        gs.observe(gs.chosen_megastar, '花火', sig=_SIG_OBS)
        _write_dep(gs, _view(front=[_u('花火'), _u('知更鸟'), _u('黑天鹅')]))
        consume_screen_change(gs, 'megastar')
        _write_dep(gs, _view(front=[_u('知更鸟'), _u('黑天鹅')]))
        assert _pending_kinds(gs) == ['megastar'], 'chosen 跌出 ∧ 计数 2 达首档'

    def test_chosen_removed_below_tier_not_fire(self):
        """重选门槛:chosen 跌出但写后只剩 1 人(<首档 2)→ 不弹
        (用户裁定:只剩一个/零个不弹)。"""
        gs = _gs()
        gs.observe(gs.chosen_megastar, '花火', sig=_SIG_OBS)
        _write_dep(gs, _view(front=[_u('花火'), _u('知更鸟')]))
        consume_screen_change(gs, 'megastar')
        _write_dep(gs, _view(front=[_u('知更鸟')]))
        assert _pending_kinds(gs) == []

    def test_chosen_loses_badge_qualification_fires(self):
        """重选·卸徽失格:chosen 非出身,卸徽后出身∨持徽两失 → 跌出
        资格集(名仍存活)→ 弹(计数经资格集算,其他成员持徽补足)。"""
        gs = _gs()
        gs.observe(gs.chosen_megastar, '三月七', sig=_SIG_OBS)
        # 三月七持徽为盛会之星成员;另两位出身成员
        _write_dep(gs, _view(front=[
            _u('三月七', equips=['盛会之星星徽']),
            _u('花火'), _u('知更鸟')]))
        consume_screen_change(gs, 'megastar')
        _write_dep(gs, _view(front=[_u('三月七'), _u('花火'), _u('知更鸟')]))
        kinds = _pending_kinds(gs)
        assert 'megastar' in kinds, '卸徽失格 = 跌出资格集(计数 2 达首档)'


class TestPlannerStarTrigger:
    def test_deploy_2star_fires_tier_once(self):
        """2★ 上场弹(序贯 B:备战囤 2★,deploy 触发)且每费用档一次。"""
        gs = _gs()
        _write_dep(gs, _view(front=[_u('银狼LV.999', star=2)]))
        assert _pending_kinds(gs) == ['planner']
        assert gs.screen_changes.planner_tiers_fired == {3}   # 未观察档 = 语义 3
        consume_screen_change(gs, 'planner')
        _write_dep(gs, _view())   # 卖掉(星级 2→无:不弹)
        assert _pending_kinds(gs) == []
        _write_dep(gs, _view(front=[_u('银狼LV.999', star=2)]))
        assert _pending_kinds(gs) == [], '同费用档(3)已弹过'

    def test_merge_on_field_carrier_fires_via_buy_report(self):
        """合成落场上(序贯 A:买腿三合进场上载体)经值回调链弹——
        获得链递归中间层语义完整:buy 报文的 deployed 写即触发回调。"""
        from sr_od.application.currency_war.kernel.cw_action_report import (
            report_action_buy_card_param,
        )
        gs = _gs()
        # 场上 1★ 银狼 + 备战 1★:买 1 → 三合载体=场上 → 2★ 场上
        gs.observe(gs.bench, BenchView(
            slots=[BenchSlot(kind='unit', unit=_u('银狼LV.999', star=1))]
            + [BenchSlot(kind='empty')] * 8, capacity=9), sig=_SIG_OBS)
        _write_dep(gs, _view(front=[_u('银狼LV.999', star=1)]),
                   source='seed')
        clear_screen_changes(gs)
        card = ShopCard(x=0, slot=1, name='银狼LV.999', faction='?',
                        cost=3, star=1)
        gs.write_logic(gs.shop,
                       ShopPayload(cards=[ShopSlot(kind='content', card=card)]
                                   + [ShopSlot(kind='empty')] * 4,
                                   refresh_probs={}),
                       produced_by='test', sig=_SIG)
        out = report_action_buy_card_param(
            gs, CwActionBuyCardParam(card=card), _SIG,
            executed=ShopActionExecuted(bought_count=1))
        assert out.applied
        assert _pending_kinds(gs) == ['planner'], '场上载体 1★→2★ 经回调弹'

    def test_bench_merge_not_fire(self):
        """备战不触发(用户裁定):三张全备战 → 载体落备战零 deployed 写
        (名集合不变)→ 不弹;此后上场才弹(判据挂动作不挂状态)。"""
        gs = _gs()
        gs.observe(gs.bench, BenchView(
            slots=[BenchSlot(kind='unit', unit=_u('银狼LV.999', star=2))]
            + [BenchSlot(kind='empty')] * 8, capacity=9), sig=_SIG_OBS)
        assert _pending_kinds(gs) == [], '备战持 2★ 零 deployed 写零回调'
        _write_dep(gs, _view(front=[_u('银狼LV.999', star=2)]))
        assert _pending_kinds(gs) == ['planner'], '上场才弹'

    def test_direct_3star_fires_and_per_tier_bookkeeping(self):
        """无→3 按弹(用户裁定暂按会,实机复核标注 = 用户确认口径
        §4);升费后 4 费档再 2★ 再弹(每费用档一次)。"""
        gs = _gs()
        _write_dep(gs, _view(front=[_u('银狼LV.999', star=3)]))
        assert _pending_kinds(gs) == ['planner'], '无→3 按弹'
        consume_screen_change(gs, 'planner')
        # 费用档升至 4(deploy_move 升费腿/pick_planner 写 lv999_cost_tier)
        gs.write_logic(gs.lv999_cost_tier, 4, produced_by='test',
                       evidence='t', sig=_SIG)
        _write_dep(gs, _view())
        _write_dep(gs, _view(front=[_u('银狼LV.999', star=2)]))
        assert _pending_kinds(gs) == ['planner'], '新费用档(4)首 2★ 弹'
        assert gs.screen_changes.planner_tiers_fired == {3, 4}


class TestFortuneBattleCount:
    def test_fortune_every_two_settles(self):
        """黑天鹅在场每 2 场战斗结算登记一次(计数跨节点累积);不在场
        不计数。上报点直登(settle_confirm 腿)。"""
        from sr_od.application.currency_war.kernel.cw_game_state import (
            report_node_advance,
        )
        gs = _gs()
        gs.observe(gs.node_pos, (1, 1), sig=_SIG_OBS)
        _write_dep(gs, _view(front=[_u('黑天鹅')]))
        report_node_advance(gs, trigger='settle_confirm')
        assert _pending_kinds(gs) == [], '第 1 场(计数 1)不弹'
        # 结算屏观察重锚(生产 = settle 确认后下一节点被观察;动作推进门
        # 只放行 observation 态)。
        gs.observe(gs.node_pos, gs.node_pos.value, sig=_SIG_OBS)
        report_node_advance(gs, trigger='settle_confirm')
        assert _pending_kinds(gs) == ['fortune'], '第 2 场(2 倍数)弹'
        assert gs.screen_changes.fortune_battles == 2
        consume_screen_change(gs, 'fortune')
        gs.observe(gs.node_pos, gs.node_pos.value, sig=_SIG_OBS)
        report_node_advance(gs, trigger='settle_confirm')
        assert _pending_kinds(gs) == [] and \
            gs.screen_changes.fortune_battles == 3, '第 3 场不弹'


class TestDirectRegisters:
    def test_aha_on_invest_strategy_pick(self):
        """S5:pick_invest_strategy 选中「阿哈大悦」→ aha 登记(唯一路径);
        其他卡不登记。"""
        from sr_od.application.currency_war.kernel.cw_action_report import (
            report_action_pick_invest_strategy_param,
        )
        gs = _gs()
        report_action_pick_invest_strategy_param(
            gs, SimpleNamespace(norm_name='阿哈大悦'), _SIG)
        assert _pending_kinds(gs) == ['aha']
        consume_screen_change(gs, 'aha')
        report_action_pick_invest_strategy_param(
            gs, SimpleNamespace(norm_name='固定理财'), _SIG)
        assert _pending_kinds(gs) == []

    def test_open_box_registers(self):
        """S6:open_box 上报直登(kind = box_card)。"""
        from sr_od.application.currency_war.kernel.cw_action_report import (
            report_action_open_box_param,
        )
        gs = _gs()
        report_action_open_box_param(gs, CwActionOpenBoxParam(slot=1), _SIG)
        assert _pending_kinds(gs) == ['box_card']

    def test_open_bookcard_registers_on_success_only(self):
        """S6:open_bookcard 成功腿登记(kind = expert_invite);槽失配
        applied=False 零登记。"""
        from sr_od.application.currency_war.kernel.cw_action_report import (
            report_action_open_bookcard_param,
        )
        gs = _gs()
        gs.observe(gs.bench, BenchView(
            slots=[BenchSlot(kind='bookcard')] + [BenchSlot(kind='empty')] * 8,
            capacity=9), sig=_SIG_OBS)
        report_action_open_bookcard_param(
            gs, CwActionOpenBookcardParam(slot=1), _SIG)
        assert _pending_kinds(gs) == ['expert_invite']
        consume_screen_change(gs, 'expert_invite')
        report_action_open_bookcard_param(
            gs, CwActionOpenBookcardParam(slot=2), _SIG)   # 槽失配
        assert _pending_kinds(gs) == []

    def test_open_tome_registers_on_success_only(self):
        """S6:open_tome 成功腿登记(kind = star_tome);槽失配零登记。"""
        from sr_od.application.currency_war.kernel.cw_action_report import (
            report_action_open_tome_param,
        )
        gs = _gs()
        gs.observe(gs.bench, BenchView(
            slots=[BenchSlot(kind='tome')] + [BenchSlot(kind='empty')] * 8,
            capacity=9), sig=_SIG_OBS)
        report_action_open_tome_param(
            gs, CwActionOpenTomeParam(slot=1), _SIG)
        assert _pending_kinds(gs) == ['star_tome']
        consume_screen_change(gs, 'star_tome')
        report_action_open_tome_param(
            gs, CwActionOpenTomeParam(slot=2), _SIG)
        assert _pending_kinds(gs) == []


class TestCallbackBoundaries:
    def test_observe_write_zero_callbacks(self):
        """观察写零回调:gs.observe 覆盖 deployed 不触发任何登记
        (观察 = 重锚事实与纠偏,反应式兜底)。"""
        gs = _gs()
        gs.observe(gs.deployed,
                   _view(front=[_u('花火'), _u('知更鸟')]), sig=_SIG_OBS)
        assert _pending_kinds(gs) == [], '观察写不回调'

    def test_value_equal_write_zero_callbacks(self):
        """值等写零回调:同值重写(占用全等)无事件。"""
        gs = _gs()
        _write_dep(gs, _view(front=[_u('花火'), _u('知更鸟')]))
        consume_screen_change(gs, 'megastar')
        _write_dep(gs, _view(front=[_u('花火'), _u('知更鸟')]))
        assert _pending_kinds(gs) == []

    def test_wear_equip_deployed_target_feeds_qualification(self):
        """穿戴上报(部署域目标)经主域写喂资格集:非出身角色(三月七)
        穿盛会星徽 → 计数 +1 上穿档 3(与两名出身成员合计)。"""
        from sr_od.application.currency_war.kernel.cw_action_report import (
            report_action_wear_equip_param,
        )
        gs = _gs()
        _write_dep(gs, _view(front=[_u('花火'), _u('知更鸟'), _u('三月七')]))
        consume_screen_change(gs, 'megastar')
        gs.write_logic(gs.equips, ['盛会之星星徽'], produced_by='test',
                       evidence='t', sig=_SIG)
        out = report_action_wear_equip_param(
            gs, CwActionWearEquipParam(item_name='盛会之星星徽',
                                       char_name='三月七', row='front',
                                       slot=3), _SIG)
        assert out.applied
        assert _pending_kinds(gs) == ['megastar'], '穿徽 +1 计数上穿档 3'


# ============================================================
# 三、消费呈现(sim 呈现门 / 上报消费 / 宿主交回 / kernel 兜底清空)
# ============================================================


def _backend(seed: int = 7) -> SimBackend:
    b = SimBackend(seed=seed, cfg=_CFG)
    install_backend(b)
    return b


class TestPickReportsConsume:
    """八选卡上报 consume(两世界同一行代码)。"""

    def test_eight_picks_consume_own_kind(self):
        from sr_od.application.currency_war.kernel.cw_action_report import (
            report_action_pick_box_card_param,
            report_action_pick_expert_invite_param,
            report_action_pick_fortune_param,
            report_action_pick_megastar_param,
            report_action_pick_partner_param,
            report_action_pick_star_tome_param,
            report_action_pick_wish_trial_param,
        )
        from sr_od.application.currency_war.kernel.cw_action_report.pick_planner import (
            report_action_pick_planner_param,
        )
        calls = [
            ('partner', report_action_pick_partner_param),
            ('megastar', report_action_pick_megastar_param),
            ('wish_trial', report_action_pick_wish_trial_param),
            ('fortune', report_action_pick_fortune_param),
            ('star_tome', report_action_pick_star_tome_param),
            ('box_card', report_action_pick_box_card_param),
            ('expert_invite', report_action_pick_expert_invite_param),
        ]
        gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
        for kind, _fn in calls:
            register_screen_change(gs, kind, KIND_SCREEN_NAMES[kind], 't')
        for i, (kind, fn) in enumerate(calls):
            fn(gs, SimpleNamespace(), _SIG)
            left = [p.kind for p in gs.screen_changes.pending]
            assert kind not in left, f'{kind} 上报消费同 kind'
            assert len(left) == len(calls) - i - 1, '消费不误伤他条目'
        # planner 上报:效果腿拒出口(未路由腿型)也先 consume(消费先于
        # 腿型分派——弹窗处理事实与选择内容独立)。
        gs_p = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
        register_screen_change(gs_p, 'planner',
                               KIND_SCREEN_NAMES['planner'], 't')
        report_action_pick_planner_param(
            gs_p, SimpleNamespace(leg_type=''), _SIG)
        assert gs_p.screen_changes.pending == [], 'planner 上报消费同 kind'


class TestSimPresentationFromPending:
    """sim 呈现数据源 = 容器登记(逐 kind 呈现门/消费披露)。"""

    def test_megastar_and_planner_present_from_pending(self):
        """megastar/planner:登记即呈现(megastar 附候选写容器——候选源
        = 场上盛会之星成员,种子经逻辑写判据自动登记)。"""
        b = _backend()
        try:
            b.gs.write_logic(
                b.gs.deployed,
                _view(front=[_u('大丽花'), _u('加拉赫')]),
                produced_by='t', evidence='t', sig=_SIG)
            assert any(p.kind == 'megastar'
                       for p in b.gs.screen_changes.pending), '判据自动登记'
            b._present_pending_overlay()
            assert b.screen_identity() == '货币战争-盛会之星'
            assert b.gs.megastar_opts.value, '候选写容器槽(呈现写点)'
            consume_screen_change(b.gs, 'megastar')
            b._dismiss_modal()
            register_screen_change(
                b.gs, 'planner', KIND_SCREEN_NAMES['planner'], 't')
            b._present_pending_overlay()
            assert b.screen_identity() == '货币战争-银狼升星'
        finally:
            uninstall_backend()

    def test_partner_consumed_with_disclosure(self):
        """partner 无 sim 观察腿(呈现即卡 observe 重试)→ 消费 + 披露;
        判据登记链经逻辑写自动触发(姬子·启行 + 三月七 上场)。"""
        b = _backend()
        try:
            b.gs.write_logic(
                b.gs.deployed,
                _view(front=[_u('三月七'), _u('姬子·启行')]),
                produced_by='t', evidence='t', sig=_SIG)
            assert any(p.kind == 'partner'
                       for p in b.gs.screen_changes.pending), '判据自动登记'
            b._present_pending_overlay()
            assert b.gs.screen_changes.pending == [], '消费(不呈现)'
            assert f'{OVERLAY_PARAM_PENDING}:partner' in b.disclosures, '披露标记'
        finally:
            uninstall_backend()

    def test_fortune_gate_only_on_prep_base(self):
        """fortune 逐 kind 呈现门:底层非备战不呈现、条目存活;底层 =
        备战时呈现(用户确认口径)。"""
        b = _backend()
        try:
            b._screen = '货币战争-补给'
            register_screen_change(
                b.gs, 'fortune', KIND_SCREEN_NAMES['fortune'], 't')
            b._present_pending_overlay()
            assert b.screen_identity() == '货币战争-补给', '非备战底层不呈现'
            assert any(p.kind == 'fortune'
                       for p in b.gs.screen_changes.pending), '条目存活等待'
            b._screen = '货币战争-备战'
            b._present_pending_overlay()
            assert b.gs.screen_changes.pending == [], '底层备战时收口消费'
            assert f'{OVERLAY_PARAM_PENDING}:fortune' in b.disclosures, '呈现门收口披露'
        finally:
            uninstall_backend()

    def test_unmodeled_kinds_consumed_with_disclosure(self):
        """aha/wish_trial/star_tome 无 sim 呈现面 → 消费 + 披露(不呈现,
        防策略读空选项卡死;aha 实机 = 备战锚特殊规则,sim 近似申报)。"""
        b = _backend()
        try:
            b._screen = '货币战争-备战'
            for kind in ('aha', 'wish_trial', 'star_tome'):
                register_screen_change(
                    b.gs, kind, KIND_SCREEN_NAMES[kind], 't')
            b._present_pending_overlay()
            assert b.screen_identity() == '货币战争-备战', '零呈现'
            assert b.gs.screen_changes.pending == [], '三 kind 全消费'
            assert all(f'{OVERLAY_PARAM_PENDING}:{k}' in b.disclosures
                       for k in ('aha', 'wish_trial', 'star_tome')), \
                '逐 kind 披露留痕(aha/wish_trial/star_tome 各自键)'
        finally:
            uninstall_backend()

    def test_advance_pure_transfer_presents_expert_from_pending(self):
        """S6 声明消费:open_bookcard 纯转移声明(备战底屏)→ advance 末
        呈现检查自 pending 呈现专家邀请函(原声明特判退役)。"""
        b = _backend()
        try:
            register_screen_change(
                b.gs, 'expert_invite', KIND_SCREEN_NAMES['expert_invite'],
                'open_bookcard')
            b.advance(WorldDecl(next_screen='货币战争-备战', trigger=''))
            assert b.screen_identity() == '货币战争-备战-专家邀请函'
        finally:
            uninstall_backend()

    def test_reconcile_exempt_reads_pending(self):
        """对账豁免 overlay_pending 改读容器登记(队列呈现面退役)。"""
        b = _backend()
        try:
            assert b._reconcile_exempt_reason() != 'overlay_pending'
            register_screen_change(
                b.gs, 'planner', KIND_SCREEN_NAMES['planner'], 't')
            assert b._reconcile_exempt_reason() == 'overlay_pending'
            consume_screen_change(b.gs, 'planner')
            assert b._reconcile_exempt_reason() != 'overlay_pending'
        finally:
            uninstall_backend()


class TestHostHandback:
    """宿主动作后交回(确定性提前交回,取代等重观察发现)。"""

    def test_shop_act_hands_back_on_pending(self, test_context, monkeypatch):
        """商店宿主:非终结动作后 pending 非空 → round_success 交回
        (原 round_wait 让位);文案带登记事实。"""
        from one_dragon.base.geometry.point import Point
        from sr_od.application.currency_war.kernel.cw_vocab import (
            ShopCard,
        )
        from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
            ShopVisitLedger,
        )
        from sr_od.application.currency_war.operations.cw_screen import (
            cw_screen_shop as shop_mod,
        )
        from sr_od.application.currency_war.operations.cw_screen.cw_screen_shop import (
            CwScreenShop,
        )
        session = StrategySession()
        gs = game_state_of(session)
        card = ShopCard(x=0, slot=1, name='花火', faction='?', cost=3, star=1)
        monkeypatch.setattr(shop_mod, 'note_shop_action_receipt',
                            lambda *a, **k: None)   # 回执留证不入桩面
        monkeypatch.setattr(shop_mod, 'apply_action_outcome',
                            lambda *a, **k: None)   # 访问侧账不入桩面(交回判据独立)
        monkeypatch.setattr('time.sleep', lambda _s: None)
        gs.write_logic(
            gs.shop,
            ShopPayload(cards=[ShopSlot(kind='content', card=card)]
                        + [ShopSlot(kind='empty')] * 4, refresh_probs={}),
            produced_by='t', sig=_SIG)

        class _Ctl:
            def click(self, pt) -> None:
                pass

        match = SimpleNamespace(
            session=session,
            strategy=SimpleNamespace(
                decide_shop_action=lambda: CwActionBuyCardParam(card=card)))
        ctx = SimpleNamespace(cw_match=match, controller=_Ctl())
        shell = CwScreenShop.__new__(CwScreenShop)
        shell.ctx = ctx
        shell.op_name = 'test-shop'
        shell._config = SimpleNamespace(strategy_id='mandate_v1', ev_arm='')
        shell._click_pts = [Point(50, 50)] * 5
        shell._level_btn = None
        shell._refresh_btn = None
        shell.ledger = ShopVisitLedger()
        shell._entry = SimpleNamespace(shop=None)
        shell._visit_actions = []
        shell._obs = None
        register_screen_change(
            gs, 'planner', KIND_SCREEN_NAMES['planner'], 't')
        from test.sr_od.application.currency_war._cw_helpers import (
            run_node,
        )
        rr = run_node(test_context, shell, lambda: CwScreenShop.act(shell))
        assert rr.is_success and 'overlay 登记' in (rr.status or ''), \
            'pending 非空 → round_success 交回(文案带登记事实)'
        assert gs.screen_changes.pending, '交回不清条目(消费归选卡上报)'

    def test_prep_act_hands_back_on_pending(self, test_context, monkeypatch):
        """备战宿主:非终结动作执行后 pending 非空 → round_success 交回
        外循环分发(执行器/校验桩化,锁交回判定位)。"""
        from sr_od.application.currency_war.kernel.cw_vocab import (
            CwActionSellBenchParam,
        )
        from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
            CwScreenPrep,
        )
        session = StrategySession()
        gs = game_state_of(session)
        monkeypatch.setattr(test_context, 'cw_match',
                            SimpleNamespace(
                                session=session,
                                strategy=SimpleNamespace(
                                    decide_prep_screen=lambda:
                                    CwActionSellBenchParam(bench_idx=0))),
                            raising=False)
        shell = CwScreenPrep.__new__(CwScreenPrep)
        shell.ctx = test_context
        shell.op_name = 'test-prep'
        from sr_od.application.currency_war.prep_actions import (
            PrepActionExecutor,
        )
        shell._executor = PrepActionExecutor(shell, test_context)
        monkeypatch.setattr(shell, '_act_execute_default',
                            lambda a: None)
        register_screen_change(
            gs, 'megastar', KIND_SCREEN_NAMES['megastar'], 't')
        from test.sr_od.application.currency_war._cw_helpers import (
            run_node,
        )
        rr = run_node(test_context, shell, lambda: CwScreenPrep.act(shell))
        assert rr.is_success and 'overlay 登记' in (rr.status or ''), \
            '备战宿主 pending 非空 → 交回外循环分发'


class TestPrepBaseFallbackClear:
    """kernel 兜底清空(识别回备战底屏,overlay 生命周期契约兜底清空腿):
    清 pending 连簿记,生命周期 = 局。"""

    def test_clear_drops_all_pending(self):
        gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
        for kind in ('partner', 'fortune'):
            register_screen_change(gs, kind, KIND_SCREEN_NAMES[kind], 't')
        clear_screen_changes(gs)
        assert gs.screen_changes.pending == []
        assert gs.screen_changes.wish_tiers_fired == set(), \
            '兜底清只清 pending,簿记生命周期 = 局'


# ============================================================
# 四、CwLoop 身份两段式 + 兜底清空 + M1 回归
# ============================================================


def _loop_shell(test_context) -> CwLoop:
    """CwLoop 最小壳(身份判定函数只消费 ctx.cw_match.session;
    __new__ 绕过重型构造,round 基建不入桩面)。"""
    shell = CwLoop.__new__(CwLoop)
    shell.ctx = test_context
    return shell


@pytest.fixture
def live_loop(test_context, monkeypatch):
    """实机态(is_target_screen/get_match_screen_name 可桩)+ 挂局。"""
    session = StrategySession()
    gs = game_state_of(session)
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    shell = _loop_shell(test_context)
    return shell, gs


class TestTwoStageRealImpl:
    """两段式 + 对账行:锁 ``_resolve_frame_identity`` 真实现。"""

    def test_pending_first_hit_takes_priority(self, live_loop, monkeypatch):
        """pending 候选屏 is_target_screen 命中 → 取该名(预测优先);
        同帧全扫描不跑(提速本义)。"""
        shell, gs = live_loop
        register_screen_change(
            gs, 'megastar', KIND_SCREEN_NAMES['megastar'], 't')
        monkeypatch.setattr(
            loop_mod, 'is_target_screen',
            lambda ctx, screen, screen_name=None, **kw:
            screen_name == KIND_SCREEN_NAMES['megastar'])
        full_scans: list = []
        monkeypatch.setattr(
            loop_mod, 'get_match_screen_name',
            lambda *a, **k: full_scans.append(1) or '货币战争-补给')
        name, pred = shell._resolve_frame_identity(object())
        assert name == KIND_SCREEN_NAMES['megastar'], 'pending 首中优先'
        assert [p.kind for p in pred] == ['megastar'], '预测子集随行'
        assert full_scans == [], '首中即返,全扫描不跑'

    def test_miss_falls_back_to_full_scan_with_drift_row(
            self, live_loop, monkeypatch):
        """未中 → 全扫描兜底(反应式不变)+ arbitrate 对账行留证
        (B1 回归:对账行路径任意轮次可入,contextlib 模块级)。"""
        shell, gs = live_loop
        register_screen_change(
            gs, 'megastar', KIND_SCREEN_NAMES['megastar'], 't')
        monkeypatch.setattr(loop_mod, 'is_target_screen',
                            lambda *a, **k: False)
        monkeypatch.setattr(loop_mod, 'get_match_screen_name',
                            lambda *a, **k: '货币战争-补给')
        # 连续两次(B1 形态:原实现 iter%10 内函数局部 import 在非 10
        # 倍数轮 UnboundLocalError;提取函数 + 模块级 import 后任意次可入)。
        name1, _ = shell._resolve_frame_identity(object())
        name2, _ = shell._resolve_frame_identity(object())
        assert name1 == name2 == '货币战争-补给', '未中 → 全扫描兜底'

    def test_hit_prediction_no_drift_row(self, live_loop, monkeypatch):
        """实扫命中预测屏(全扫描路径同屏)= 静默,零对账行。"""
        shell, gs = live_loop
        register_screen_change(
            gs, 'megastar', KIND_SCREEN_NAMES['megastar'], 't')
        monkeypatch.setattr(loop_mod, 'is_target_screen',
                            lambda *a, **k: False)
        monkeypatch.setattr(
            loop_mod, 'get_match_screen_name',
            lambda *a, **k: KIND_SCREEN_NAMES['megastar'])
        name, _ = shell._resolve_frame_identity(object())
        assert name == KIND_SCREEN_NAMES['megastar']
        seq = gs.write_seq   # 零对账行:note_obs_event 不占新版本
        shell._resolve_frame_identity(object())
        assert gs.write_seq == seq, '命中预测 = 静默零行'

    def test_aha_base_screen_entry_excluded_from_two_stage(
            self, live_loop, monkeypatch):
        """B2 回归:aha 条目 screen_name = 备战(底屏锚)∉ 分发候选集
        → 不参与两段式(is_target_screen 零调用该名)、预测子集排除;
        与 megastar 并存时只试 megastar。"""
        shell, gs = live_loop
        register_screen_change(gs, 'aha', KIND_SCREEN_NAMES['aha'], 't')
        register_screen_change(
            gs, 'megastar', KIND_SCREEN_NAMES['megastar'], 't')
        tried: list = []

        def _fake_target(ctx, screen, screen_name=None, **kw):
            tried.append(screen_name)
            return screen_name == KIND_SCREEN_NAMES['megastar']

        monkeypatch.setattr(loop_mod, 'is_target_screen', _fake_target)
        monkeypatch.setattr(
            loop_mod, 'get_match_screen_name',
            lambda *a, **k: KIND_SCREEN_NAMES['megastar'])
        name, pred = shell._resolve_frame_identity(object())
        assert KIND_SCREEN_NAMES['aha'] not in tried, \
            '底屏锚条目不进两段式(防备战名死循环)'
        assert [p.kind for p in pred] == ['megastar'], '候选过滤在册'
        assert name == KIND_SCREEN_NAMES['megastar']


class TestLoopFallbackClear:
    """CwLoop 兜底清空:锁 ``_fallback_clear_pending`` 真实现(与 kernel
    ``clear_screen_changes`` 相对:本入口清 pending 不清簿记)。"""

    def test_clears_pending_keeps_bookkeeping(self, live_loop):
        shell, gs = live_loop
        gs.screen_changes.wish_tiers_fired.add(2)
        register_screen_change(
            gs, 'fortune', KIND_SCREEN_NAMES['fortune'], 't')
        shell._fallback_clear_pending()
        assert gs.screen_changes.pending == []
        assert gs.screen_changes.wish_tiers_fired == {2}, '簿记生命周期 = 局'

    def test_empty_pending_noop(self, live_loop):
        shell, _gs = live_loop
        shell._fallback_clear_pending()   # 空 = 直跳零异常

    def test_sim_state_skips(self, test_context, monkeypatch):
        """sim 装配态(mechanical_io_allowed False)直跳:呈现即消费
        由后端收口,实机兜底清不辖。"""
        from sr_od.application.currency_war.sim import cw_sim_ports
        monkeypatch.setattr(test_context, 'cw_match',
                            SimpleNamespace(session=StrategySession()),
                            raising=False)
        shell = _loop_shell(test_context)
        monkeypatch.setattr(cw_sim_ports, '_BACKEND', object())
        try:
            shell._fallback_clear_pending()   # sim 态直跳零异常
        finally:
            monkeypatch.undo()


class TestFortuneNodeWindowM1:
    """M1 回归(sim):settle_confirm 登记 fortune → 节点窗起点先落底层
    再查呈现门(评审复现形态:原序 fortune 门对旧结算屏恒 continue,
    吞节点屏呈现 + resume='offer' 悬挂)。"""

    def test_fortune_registered_at_settle_consumed_at_battle_window(self):
        from sr_od.application.currency_war.kernel.cw_action_report import (
            report_action_start_battle_param,
        )
        from sr_od.application.currency_war.kernel.cw_game_state import (
            report_node_advance,
        )
        from sr_od.application.currency_war.sim import cw_sim_ports
        from sr_od.application.currency_war.sim.cw_sim_backend import (
            SCREEN_BRIEFING,
            SCREEN_PREP,
            SCREEN_SETTLE,
        )
        _sig = ChannelSig(family='logic_action', actor='t', mode='compute')
        b = SimBackend(seed=7, cfg=RunConfig(selected_difficulty='A8',
                                             enemy_difficulty=108))
        install_backend(b)
        try:
            b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
            b._maybe_finish_wait()
            gs = b.gs
            # P1r1(奖励)→ 出战 → 结算;黑天鹅在场使 settle_confirm 登记
            # fortune(S4 判据)——构造最小形态:直接登记(判据链另有锁)。
            out = report_action_start_battle_param(gs, SimpleNamespace(),
                                                   _sig)
            cw_sim_ports.declare_world(out.world_decl)
            b._resolve_battle()
            assert b.screen_identity() == SCREEN_SETTLE
            register_screen_change(
                gs, 'fortune', KIND_SCREEN_NAMES['fortune'],
                's4_battle_count@settle_confirm')
            # settle_confirm 推进 → P1r2(battle)节点窗起点:先落底层
            #(battle → 备战档)再查呈现门 → fortune 收口消费,节点屏不被吞。
            adv = report_node_advance(gs, trigger='settle_confirm')
            assert adv.applied
            cw_sim_ports.declare_world(adv.world_decl)
            assert b.screen_identity() == SCREEN_PREP, \
                '节点窗底层照常呈现(battle → 备战),不被 fortune 门吞'
            assert gs.screen_changes.pending == [], \
                'fortune 在备战底层收口消费(逐 kind 呈现门)'
            assert any('fortune' in str(k) and 'unmodeled' in str(v)
                       for k, v in b.disclosures.items()), '消费披露在册'
        finally:
            uninstall_backend()


# ============================================================
# 五、路由清点(CwLoop._route_clear_stale_payloads)
# ============================================================


def _stub_loop(gs: GameState) -> SimpleNamespace:
    """桩 self:挂点只读 self.ctx.cw_match.gs,其余零依赖。"""
    return SimpleNamespace(ctx=SimpleNamespace(
        cw_match=SimpleNamespace(gs=gs)))


def _seed_route_payloads(gs: GameState) -> None:
    """播种四槽非 None(encounter 属屏 = 遭遇节点;supply/planner 异属屏;
    shop 豁免面播种为保活见证)。"""
    gs.observe(gs.encounter,
               EncounterPayload(options=[EncounterOption(idx=1)]),
               sig=_OBS_SIG)
    gs.observe(gs.supply,
               SupplyPayload(options=[SupplyOption(idx=1)]),
               sig=ChannelSig(family='obs', actor='cw_observation',
                              screen='货币战争-补给', mode='read'))
    gs.observe(gs.shop, ShopPayload(), sig=_OBS_SIG)
    gs.write_logic(gs.planner_opts, ['p1'], produced_by='test',
                   sig=ChannelSig(family='logic_action', actor='CwLoop',
                                  screen='', mode='compute'))


def test_route_clear_unidentified_clears_all_ten():
    gs = GameState(schema_version=1)
    _seed_route_payloads(gs)
    seq0 = gs.write_seq
    CwLoop._route_clear_stale_payloads(_stub_loop(gs), None)
    for name, (_, clearable) in _PAYLOAD_DOMAINS.items():
        if not clearable:
            assert getattr(gs, name).value is not None, name   # shop 豁免保活
        else:
            assert getattr(gs, name).value is None, name
    assert gs.write_seq > seq0


def test_route_clear_own_screen_keeps_own_slot():
    gs = GameState(schema_version=1)
    _seed_route_payloads(gs)
    CwLoop._route_clear_stale_payloads(_stub_loop(gs), '货币战争-遭遇节点')
    assert gs.encounter.value is not None          # 属屏在屏保活
    assert gs.supply.value is None                 # 异属屏清
    assert gs.planner_opts.value is None


def test_route_clear_shop_exempt_and_none_skip():
    gs = GameState(schema_version=1)
    _seed_route_payloads(gs)
    CwLoop._route_clear_stale_payloads(_stub_loop(gs), None)
    assert gs.shop.value is not None               # route_clearable=False 不清
    seq_after_first = gs.write_seq
    CwLoop._route_clear_stale_payloads(_stub_loop(gs), None)
    assert gs.write_seq == seq_after_first         # 已 None 跳过不占版本
