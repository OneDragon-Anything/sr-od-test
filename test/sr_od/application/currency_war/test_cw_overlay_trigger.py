"""货币战争 overlay 触发登记行为锁。

锁面(触发登记完成判据逐条):
- 伙伴(S2):成员增减弹 / 星徽穿卸弹 / 经典合成集合不变不弹 /
  合成继承获资格弹 / 换排非开拓者不弹;
- 巨星(S1a/S1b):跨档上穿即弹(含降档回升)/ 重选两形态
  (名消失 + 卸徽失格)/ 首档门槛;
- 祈愿(S1a):首达档一次(降档再回不弹);
- planner(S3):合成落场上弹 / 2★ 上场弹 / 每费用档一次 /
  备战不触发 / 无→3 按弹;
- 占卜屋(S4):黑天鹅计数 2 倍数登记;
- 阿哈(S5)/ open_* 直登(S6);
- 获得链递归中间层语义完整(buy 三合一载体落场上经值回调);
- 观察写零回调;登记三口契约(去重/消费/清空 + kind 封闭集)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_buy_card_param,
    report_action_open_box_param,
    report_action_open_bookcard_param,
    report_action_open_tome_param,
    report_action_pick_invest_strategy_param,
    report_action_wear_equip_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    GameState,
    ShopActionExecuted,
    ShopPayload,
    ShopSlot,
    Unit,
    consume_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
    CwActionOpenBookcardParam,
    CwActionOpenBoxParam,
    CwActionOpenTomeParam,
    CwActionWearEquipParam,
    ShopCard,
)
from sr_od.application.currency_war.kernel.cw_overlay_register import (
    KIND_SCREEN_NAMES,
    SCREEN_CHANGE_KINDS,
    clear_screen_changes,
    consume_screen_change,
    register_screen_change,
)

_SIG_OBS = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')
_SIG = ChannelSig(family='logic_action', actor='test', mode='compute')


@pytest.fixture(autouse=True)
def _drain_defect_buffer():
    """测试卫生:主域种子经 observe 覆盖开局种子会产 logic_rand_outcome
    行入进程级缓冲——前后双清,防跨用例顺序依赖红。"""
    consume_defect_sink()
    yield
    consume_defect_sink()


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


# ============================================================ 登记三口契约


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


# ============================================================ S2 伙伴


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


# ============================================================ S1a 巨星跨档 / 祈愿


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


# ============================================================ S1b 巨星重选


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


# ============================================================ S3 planner


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
        gs = _gs()
        from sr_od.application.currency_war.kernel.cw_game_state import (
            game_state_of,
        )
        from sr_od.application.currency_war.kernel.cw_strategy_session import (
            StrategySession,
        )
        from types import SimpleNamespace
        session = StrategySession()
        gs = game_state_of(session)
        # 场上 1★ 银狼 + 备战 1★ + 店内 1★:买 1 → 三合载体=场上 → 2★ 场上
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


# ============================================================ S4 占卜屋


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


# ============================================================ S5 阿哈 / S6 open_*


class TestDirectRegisters:
    def test_aha_on_invest_strategy_pick(self):
        """S5:pick_invest_strategy 选中「阿哈大悦」→ aha 登记(唯一路径);
        其他卡不登记。"""
        from types import SimpleNamespace
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
        gs = _gs()
        report_action_open_box_param(gs, CwActionOpenBoxParam(slot=1), _SIG)
        assert _pending_kinds(gs) == ['box_card']

    def test_open_bookcard_registers_on_success_only(self):
        """S6:open_bookcard 成功腿登记(kind = expert_invite);槽失配
        applied=False 零登记。"""
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


# ============================================================ 观察写零回调 / 回调族契约


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
