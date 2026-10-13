"""备战工序九段全扫行为锁(迭代 2026-10-12-prep-shop-workflow-redesign 批 3.3)。

锁对象 = ``entry.emit`` 的九段全扫工序(prep_pipeline §1,判据唯一源):
各段触发态首中断言 + 回扫语义、自救动作序(按损失递增 + 真全量豁免)、
晶矿垫件锁(垫件谓词过滤后取价值最小)、第 3 步空段零动作透传锁
(旧升级判据直删后透传,新判据 3.4 落码)、节末凑息闭合即止锁。

帧构造纪律:
- 第 4 步商店会话标记(``shop_handled``)未打的帧会在第 4 步开店命中
  提前返回——测第 5-8 步的帧一律经 :func:`_mark_handled` 打标(商店
  会话已处理形态);生效序位经 ``gs.node_pos`` 观察写端落值
  (``effective_node_pos`` 读口,未观察 None 不当真)。
- 窗口辖域测试用追击飞霄线(synergy 3 = 板面追击 3 档;追击为流派
  键,``board_by_row`` 聚合含 flows)——规避配方底线门辖列车件的
  干扰(围栏语义与窗口辖域分立,锁只锁窗口)。
- 卖出场景帧 deployed 非空(空板守卫 = 评估器 as-built 收编语义,
  deployed = 0 帧卖出哑火)且 deploy_vacancy = 0(防第 5 步部署先中,
  散件填位与凑息让位的序差属第 5 步语义,本文件第 7 步锁只锁凑息)。
"""
from __future__ import annotations

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_comp,
    cw4_gs,
    cw4_session,
)

from sr_od.application.currency_war.kernel.cw_action_report.sell_bench import (
    report_action_sell_bench_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    ChannelSig,
    OreSight,
    Unit,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionCollectOreParam,
    CwActionDeployMoveParam,
    CwActionLevelUpParam,
    CwActionOpenBoxParam,
    CwActionOpenShopParam,
    CwActionSellBenchParam,
    CwActionStartBattleParam,
    CwActionWearEquipParam,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    entry,
    session_scope,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

_SIG = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')
_LOGIC_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep')


def _units(names: tuple[str, ...]) -> list[Unit]:
    return [Unit(char_id=n, star=1) for n in names]


def _write_ores(gs, points: tuple) -> None:
    gs.observe(gs.spheres, OreSight(
        count=len(points), colors=tuple(dict.fromkeys(p[0] for p in points)),
        points=points), sig=_SIG)


def _mark_handled(sess) -> None:
    """打商店会话标记(「本节点已处理」形态:第 4 步跳过 → 帧可达第
    5-8 步)。"""
    gs = game_state_of(sess)
    node = gs.node.value
    gs.observe(gs.node_pos,
               (int(node.plane), int(node.round_num)) if node else (1, 2),
               sig=_SIG)
    session_scope.mark_shop_handled(gs)


def _set_overflow(sess) -> None:
    game_state_of(sess).observe(
        game_state_of(sess).overflow_warning, True, sig=_SIG)


def _emit(sess):
    return entry.emit(sess, None)


# ============================================================ 第 0 步:自救序


class TestStep0SelfRescue:
    """自救动作序锁(按损失递增:上阵安置 → 点消耗品 → 卖出 → 防御
    分支;每帧重评取首个可行,无试错计数;prep_pipeline §1 第 0 步)。"""

    @staticmethod
    def _rescue_frame():
        # 板面追击 1(窗口未到:追击 3 档差二)+ 飞霄(追击线终局件)在席;
        # cap 8 → 态 1 有空位可上
        sess = cw4_session()
        cw4_gs(sess, gold=30, level=6, round_num=2, node='战斗',
               bench=[_bc('飞霄')],
               front_row=_units(('知更鸟', '那刻夏')), back_row=(),
               deploy_cap=8)
        return sess

    def test_state1_deploy_free_and_window_exempt(self):
        """态 1(上阵安置,免费腾位):cap 有空位 ∧ 备战席有可上阵单位 →
        拖上阵;**告警帧豁免窗口辖域**——同一帧无告警时被第 5 步窗口
        辖域挡下的纯终局件,告警帧照上(上阵纯为腾槽保命,豁免行 =
        prep_pipeline 第 0 步态 1)。"""
        sess = self._rescue_frame()
        _set_overflow(sess)
        out = _emit(sess)
        moves = [e.action for e in out
                 if isinstance(e.action, CwActionDeployMoveParam)]
        assert moves and moves[0].bench_idx == 0
        # 对照:同帧无告警(打标)→ 第 5 步窗口辖域挡下,无部署
        sess2 = self._rescue_frame()
        _mark_handled(sess2)
        out2 = _emit(sess2)
        assert not [e for e in out2
                    if isinstance(e.action, CwActionDeployMoveParam)], \
            '无告警帧:窗口未到的纯终局件只囤不上'

    def test_state2_open_consumable_when_no_seats(self):
        """态 2(点开消耗品,免费腾位):无 cap 空位 ∧ 备战席有占席物品
        → 点开腾槽(占席道具不可卖但可点开——补给箱不可卖为实机定谳;
        告警帧冻结条款对点消耗品例外:点开本身就是自救动作)。"""
        sess = cw4_session()
        # deployed 4 = cap(level 4)→ 无空位;bench 含占席物品槽
        cw4_gs(sess, gold=30, level=4, round_num=2, node='战斗',
               bench=[BenchSlot(kind='supply_box'), BenchSlot(kind='tome')]
               + [_bc('c0')] * 7,
               front_row=_units(('三月七', '瓦尔特', '丹恒·饮月', '姬子')),
               back_row=())
        _set_overflow(sess)
        out = _emit(sess)
        assert len(out) == 1 and isinstance(out[0].action, CwActionOpenBoxParam)

    def test_state3_sells_lowest_value_and_line_member_last(self):
        """态 3(卖出,有损腾位):候选评估器自救扩展面(仅备战席 + 真
        全量持有)——价值最低者让位;线内件整体置末层(P78 资格仲裁族
        全通道豁免,「零停机出口」优先于硬资格)。"""
        sess = cw4_session(cw4_comp('列车同行'))
        cw4_gs(sess, gold=30, level=4, round_num=2, node='战斗',
               bench=[_bc('c0'), _bc('c1'), _bc('姬子·启行')] + [_bc('c2')] * 6,
               front_row=_units(('三月七', '瓦尔特', '丹恒·饮月', '姬子')),
               back_row=())
        _set_overflow(sess)
        out = _emit(sess)
        sells = [e.action for e in out
                 if isinstance(e.action, CwActionSellBenchParam)]
        assert len(sells) == 1
        assert sells[0].reason == 'self_rescue_sell'
        assert sells[0].bench_idx == 0, '价值最低散件让位,线内件置末层'

    def test_state3_full_pool_exemptions_reach_line_member(self):
        """真全量豁免锁:候选只剩线内核心件(常规面恒拒)时自救仍可卖
        ——P78-4 核心/④件身份段在自救场景豁免、按价值序末位可卖。"""
        sess = cw4_session(cw4_comp('列车同行'))
        cw4_gs(sess, gold=30, level=4, round_num=2, node='战斗',
               bench=[_bc('姬子·启行')] + [_bc('c2')] * 8,
               front_row=_units(('三月七', '瓦尔特', '丹恒·饮月', '姬子')),
               back_row=())
        _set_overflow(sess)
        out = _emit(sess)
        sells = [e.action for e in out
                 if isinstance(e.action, CwActionSellBenchParam)]
        assert len(sells) == 1 and sells[0].reason == 'self_rescue_sell', \
            '自救扩展面真全量:线内核心件末位可卖(零停机出口)'

    def test_state4_defensive_zero_action_not_battle(self, monkeypatch):
        """态 4(防御性分支,识别异常真实形态的兜底):真全量可卖下候选
        空结构性不可达——monkeypatch 模拟候选空(识别异常),断言零动作
        正常交回外循环且不出战(告警冻结条款:告警不消出战无效)。"""
        sess = cw4_session()
        cw4_gs(sess, gold=30, level=4, round_num=2, node='战斗',
               bench=[_bc('c0')] * 9,
               front_row=_units(('三月七', '瓦尔特', '丹恒·饮月', '姬子')),
               back_row=())
        _set_overflow(sess)
        monkeypatch.setattr(
            entry, 'evaluate_sell_candidates',
            lambda gs, scenario, **kw: ((), 'no_candidates'))
        out = _emit(sess)
        assert out == [], '防御分支零动作交回外循环(不出战)'
        assert state_of(sess).cw4_counters.get('self_rescue_no_exit') == 1

    def test_alert_freezes_other_steps(self):
        """告警冻结条款:告警在场时其余步骤不执行(标记未处理也不开店
        ——告警不消出战无效,其他动作无意义;例外仅自救动作本身)。"""
        sess = cw4_session()
        cw4_gs(sess, gold=30, level=4, round_num=2, node='战斗',
               bench=[BenchSlot(kind='supply_box')] * 9,
               front_row=_units(('三月七', '瓦尔特', '丹恒·饮月', '姬子')),
               back_row=())
        _set_overflow(sess)
        out = _emit(sess)
        assert not [e for e in out
                    if isinstance(e.action, (CwActionOpenShopParam,
                                             CwActionStartBattleParam))]


# ============================================================ 第 2 步:晶矿


class TestStep2Ore:
    """晶矿锁(prep_pipeline §1 第 2 步:席未满点全部;席满垫件谓词
    过滤后取价值最小,无试错计数;ore_defer 键族退役)。"""

    @staticmethod
    def _full_bench_frame():
        # deployed 非空(绕空板守卫:评估器 as-built 收编语义,deployed=0
        # 帧卖出哑火);9 席满
        sess = cw4_session()
        cw4_gs(sess, gold=30, level=6, round_num=2, node='战斗',
               bench=[_bc('c1', star=2), _bc('c2', star=2), _bc('c0')]
               + [_bc('c3', star=2)] * 6,
               front_row=_units(('三月七',)), back_row=())
        return sess

    def test_free_seat_collects_all(self):
        """席位未满 → 点全部晶矿(批式上界分批推进)。"""
        sess = cw4_session()
        cw4_gs(sess, gold=30, level=6, round_num=2, node='战斗',
               bench=[_bc('c0')],
               front_row=_units(('三月七',)), back_row=())
        _write_ores(game_state_of(sess),
                    (('gold', 100, 200, 30), ('blue', 300, 400, 20)))
        _mark_handled(sess)   # 标记不影响第 2 步(更早段)
        out = _emit(sess)
        assert len(out) == 1 and isinstance(out[0].action, CwActionCollectOreParam)
        assert out[0].action.points

    def test_full_seat_sells_pad_not_first_value(self):
        """席满 → 垫件谓词过滤后取价值最小:垫件被卖、非垫件(2★)
        不被卖——「过滤后取最小」非「全池排序首位判断」(价值函数无
        垫件身份维,prep_pipeline 第 2 步消费声明)。"""
        sess = self._full_bench_frame()
        _write_ores(game_state_of(sess), (('gold', 100, 200, 30),))
        out = _emit(sess)
        sells = [e.action for e in out
                 if isinstance(e.action, CwActionSellBenchParam)]
        assert len(sells) == 1 and sells[0].reason == 'ore_make_room'
        # c0(唯一 1★ 垫件,紧缩位 2 → 容器槽 2)被卖;2★ 非垫件不动
        assert sells[0].bench_idx == 2

    def test_full_seat_no_pad_yields_ore(self):
        """席满 ∧ 无垫件(全 2★)→ 本节点放弃晶矿(确定的
        高价值持有不换随机产出)——不发射晶矿动作也不卖,透传到后续
        步骤(第 4 步开店)。"""
        sess = cw4_session()
        cw4_gs(sess, gold=30, level=6, round_num=2, node='战斗',
               bench=[_bc(f'c{i}', star=2) for i in range(9)],
               front_row=_units(('三月七',)), back_row=())
        _write_ores(game_state_of(sess), (('gold', 100, 200, 30),))
        out = _emit(sess)
        assert not [e for e in out
                    if isinstance(e.action, (CwActionCollectOreParam,
                                             CwActionSellBenchParam))]
        assert isinstance(out[0].action, CwActionOpenShopParam), \
            '晶矿放弃后透传,扫描继续(第 4 步开店命中)'
        assert state_of(sess).cw4_counters.get('ore_yield_no_pad') == 1

    def test_rescan_collects_after_seat_freed(self):
        """回扫语义锁:席满卖垫件腾位(上报后席 8)→ 下帧全扫回到第 2
        步 → 点晶矿(腾位后回头点晶矿的回跳在全扫下自然表达)。"""
        sess = self._full_bench_frame()
        _write_ores(game_state_of(sess), (('gold', 100, 200, 30),))
        out1 = _emit(sess)
        sell = next(e.action for e in out1
                    if isinstance(e.action, CwActionSellBenchParam))
        # 卖出落地(上报:腾位 + 退金进账)→ 下帧全扫
        report_action_sell_bench_param(
            game_state_of(sess), sell, sig=_LOGIC_SIG)
        out2 = _emit(sess)
        assert len(out2) == 1 \
            and isinstance(out2[0].action, CwActionCollectOreParam)


# ============================================================ 第 3 步:空段透传


class TestStep3Passthrough:
    """第 3 步零动作透传锁:旧升级判据内核随 emit 重写直删(用户裁定
    2026-10-13),本步为空段——任何帧零升级动作,扫描继续(新判据 3.4
    落码,line_and_upgrade §2)。"""

    def test_no_levelup_in_upgrade_friendly_states(self):
        """升级友好形态(金充裕 + 板满 + 线内候补在席)零升级动作——
        旧 M3 判据链在此形态会评估发射,空段期恒透传。"""
        sess = cw4_session(cw4_comp('列车同行'))
        cw4_gs(sess, gold=100, level=4, round_num=2, node='战斗',
               bench=[_bc('c0')] * 9,
               front_row=_units(('三月七', '瓦尔特', '丹恒·饮月', '姬子')),
               back_row=())
        _mark_handled(sess)
        out = _emit(sess)
        assert not [e for e in out
                    if isinstance(e.action, CwActionLevelUpParam)], \
            '第 3 步空段:零升级动作透传(3.4 落新判据)'
        # 凑息不触发(gold 100 ≥ 50)→ 出战兜底
        assert isinstance(out[0].action, CwActionStartBattleParam)


# ============================================================ 第 4 步:商店会话


class TestStep4ShopSession:
    """第 4 步商店会话入口锁(契约 A:标记判定 + 解拦复核接线位——
    复核判定函数本体归 3.6,本批占位恒不解拦)。"""

    def test_unhandled_opens_shop(self):
        """标记未处理(值 ≠ 当前节点号)→ CwActionOpenShopParam(备战侧
        决策性开店意图的唯一来源)。"""
        sess = cw4_session()
        cw4_gs(sess, gold=30, level=6, round_num=2, node='战斗',
               bench=[], front_row=(), back_row=())
        out = _emit(sess)
        assert len(out) == 1 and isinstance(out[0].action, CwActionOpenShopParam)

    def test_handled_marker_skips_step(self):
        """标记 = 当前节点号(本节点已处理)→ 跳过本步,扫描继续到
        出战。"""
        sess = cw4_session()
        cw4_gs(sess, gold=60, level=6, round_num=2, node='战斗',
               bench=[], front_row=(), back_row=())
        _mark_handled(sess)
        out = _emit(sess)
        assert isinstance(out[0].action, CwActionStartBattleParam)


# ============================================================ 第 5 步:部署调整


class TestStep5DeployWindow:
    """部署窗口辖域锁(用户裁定 2026-10-12:终局成员在其上线窗口前
    不上阵;纯终局件谓词 = 终局库成员 ∧ 非现行过渡配方成员;窗口到 =
    entry_signals 信号命中——追击飞霄线 synergy 3 = 板面追击 3 档)。"""

    @staticmethod
    def _window_frame(front: tuple[str, ...]):
        # gold 60 ≥ 息线 50:防第 7 步凑息(来金族场上支)先中——窗口
        # 辖域锁只锁第 5 步部署
        sess = cw4_session()
        cw4_gs(sess, gold=60, level=6, round_num=2, node='战斗',
               bench=[_bc('飞霄')],
               front_row=_units(front), back_row=(), deploy_cap=8)
        _mark_handled(sess)
        return sess

    def test_endgame_member_blocked_before_window(self):
        """窗口未到(板面追击 1 < 3):纯终局件只囤不上——部署计划被
        窗口辖域过滤,无 DeployMove(透传到出战)。"""
        sess = self._window_frame(('知更鸟', '那刻夏'))
        out = _emit(sess)
        assert not [e for e in out
                    if isinstance(e.action, CwActionDeployMoveParam)]
        assert isinstance(out[0].action, CwActionStartBattleParam)

    def test_endgame_member_deploys_on_window(self):
        """窗口到(板面追击 3 档齐 = synergy 信号命中):终局件可上。"""
        sess = self._window_frame(('知更鸟', '不死途', '貊泽'))
        out = _emit(sess)
        moves = [e.action for e in out
                 if isinstance(e.action, CwActionDeployMoveParam)]
        assert moves and moves[0].bench_idx == 0

    def test_transition_member_exempt_from_window(self):
        """过渡∩终局重叠件按过渡成员正常上阵:现行过渡配方成员
        (target_comp 物化链)不受窗口辖域辖(它们的上阵是过渡行为)。"""
        sess = cw4_session(cw4_comp('追击飞霄'))
        cw4_gs(sess, gold=30, level=6, round_num=2, node='战斗',
               bench=[_bc('飞霄')],
               front_row=_units(('知更鸟', '那刻夏')), back_row=(),
               deploy_cap=8)
        _mark_handled(sess)
        out = _emit(sess)
        moves = [e.action for e in out
                 if isinstance(e.action, CwActionDeployMoveParam)]
        assert moves, '过渡配方成员(线内件)的正常部署不被窗口挡'

    def test_accumulator_always_on(self):
        """全局累积型例外([21]「越早越好」):万敌 = hp_charge_stack →
        always_on 信号,窗口未到(夜半 0 档)也照上。"""
        sess = cw4_session()
        cw4_gs(sess, gold=30, level=6, round_num=2, node='战斗',
               bench=[_bc('万敌')],
               front_row=_units(('知更鸟', '那刻夏', '三月七')), back_row=(),
               deploy_cap=8)
        _mark_handled(sess)
        out = _emit(sess)
        moves = [e.action for e in out
                 if isinstance(e.action, CwActionDeployMoveParam)]
        assert moves, '万敌 always_on:窗口辖域外的累积型例外'


# ============================================================ 第 6 步:装备与工具


class TestStep6EquipTools:
    """第 6 步装备与工具接线锁(装备穿戴判据本体保留;工具评估留痕
    计数 = 现行 M7.5 发射位口径)。"""

    def test_wear_plan_emits_and_tool_eval_counter(self):
        """owned 可穿 → 穿戴计划发射(CwActionWearEquipParam);工具
        评估留痕(m7_5_evaluated;零可执行件帧 reject_none 显影)。"""
        sess = cw4_session()
        cw4_gs(sess, gold=60, level=6, round_num=2, node='战斗',
               bench=[], front_row=(), back_row=(),
               equips=['火力风暴潮'])
        _mark_handled(sess)
        out = _emit(sess)
        ct = state_of(sess).cw4_counters
        assert ct.get('m7_5_evaluated') == 1
        wears = [e.action for e in out
                 if isinstance(e.action, CwActionWearEquipParam)]
        assert wears and wears[0].item_name == '火力风暴潮'


# ============================================================ 第 7 步:节末凑息


class TestStep7NodeEndInterest:
    """节末凑息锁(金 < 息线 → 卖 1★ 全额退件补缺口;卖到缺口闭合
    即止、不多卖一张)。"""

    @staticmethod
    def _frame(gold: int, bench):
        # deployed 4 = cap(level 4 → vacancy 0:防第 5 步部署先中);deployed
        # 非空绕空板守卫
        sess = cw4_session()
        cw4_gs(sess, gold=gold, level=4, round_num=2, node='战斗',
               bench=bench,
               front_row=_units(('三月七', '瓦尔特', '丹恒·饮月', '姬子')),
               back_row=())
        _mark_handled(sess)
        return sess

    def test_below_line_sells_single_refund_unit(self):
        """金 40 < 息线 50 → 卖 1★ 全额退件候选一张(单动作循环:每帧
        一张,卖出上报更新金位后下帧重评)。"""
        sess = self._frame(40, [_bc('c0'), _bc('c1')])
        out = _emit(sess)
        sells = [e.action for e in out
                 if isinstance(e.action, CwActionSellBenchParam)]
        assert len(sells) == 1 and sells[0].reason == 'interest_prep'
        assert sells[0].bench_idx == 0

    def test_gap_closed_stops_selling(self):
        """闭合即止锁:卖出退金使金位 ≥ 息线后,下一帧不再卖(不多卖
        一张,卖回量最小化)。"""
        sess = self._frame(48, [_bc('c0')])   # 48 + 3(退) = 51 ≥ 50
        out1 = _emit(sess)
        sell = next(e.action for e in out1
                    if isinstance(e.action, CwActionSellBenchParam))
        report_action_sell_bench_param(game_state_of(sess), sell,
                                       sig=_LOGIC_SIG)
        out2 = _emit(sess)
        assert not [e for e in out2
                    if isinstance(e.action, CwActionSellBenchParam)], \
            '缺口闭合即止:金位 ≥ 息线后零卖出'
        assert isinstance(out2[0].action, CwActionStartBattleParam)

    def test_above_line_no_sell(self):
        """金 ≥ 息线 → 本步零动作(透传到出战)。"""
        sess = self._frame(60, [_bc('c0')])
        out = _emit(sess)
        assert isinstance(out[0].action, CwActionStartBattleParam)
        assert not [e for e in out
                    if isinstance(e.action, CwActionSellBenchParam)]


# ============================================================ 第 8 步:出战


class TestStep8Battle:
    """第 8 步出战锁(以上全部步骤无动作 ⇒ 备战环唯一完成态)。"""

    def test_all_quiet_starts_battle(self):
        sess = cw4_session()
        cw4_gs(sess, gold=60, level=6, round_num=2, node='战斗',
               bench=[], front_row=(), back_row=())
        _mark_handled(sess)
        out = _emit(sess)
        assert len(out) == 1 and isinstance(out[0].action, CwActionStartBattleParam)


# ============================================================ entry_signals 建表核对(数据地基)


class TestEntrySignalsTable:
    """上线窗口信号表建表锁(landing 3.3:COMP_LIBRARY 扩 entry_signals
    字段并建表——20 线全登记、值域合法、键 ⊆ 线终局成员;fail 读法 =
    缺行 → 窗口谓词恒假,数据地基由完备性保证不静默)。"""

    _KINDS = ('level', 'synergy', 'plane_end', 'always_on')

    def test_all_lines_registered_and_value_domain(self):
        from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
        assert len(COMP_LIBRARY) >= 20
        for comp in COMP_LIBRARY:
            assert comp.entry_signals, f'{comp.name}:entry_signals 缺表'
            members = set(comp.core_chars) | set(comp.shared_chars or ())
            for name, sig in comp.entry_signals.items():
                assert name in members, \
                    f'{comp.name}:{name} 非线终局成员(core ∪ shared)'
                assert isinstance(sig, tuple) and len(sig) == 2
                kind, threshold = sig
                assert kind in self._KINDS, f'{comp.name}:{name} 信号类 {kind}'
                assert isinstance(threshold, int)

    def test_synergy_threshold_matches_form_tiers(self):
        """synergy 阈值 = 该线主羁绊成型档(查表对拍:阈值 ⇔ form_tiers
        取键的档位——主羁绊键 = bond_signal 或 form_tiers 首键)。"""
        from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
        for comp in COMP_LIBRARY:
            key = comp.bond_signal or (
                comp.form_tiers and next(iter(comp.form_tiers)))
            want = comp.form_tiers.get(key) if key else None
            for name, (kind, threshold) in comp.entry_signals.items():
                if kind == 'synergy':
                    assert threshold == want, (
                        f'{comp.name}:{name} synergy 阈值 {threshold}'
                        f' ≠ 主羁绊 {key} 成型档 {want}')
