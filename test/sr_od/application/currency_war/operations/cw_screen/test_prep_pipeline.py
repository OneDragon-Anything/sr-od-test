"""备战工序测试面(决策契约单动作形状 + 九段全扫行为 + 上线窗口信号表)。

两部分,判据唯一源 = prep_pipeline §1 + docs/develop/sr_od/application/
currency_war/flow/README.md §2.2 备战接口行:

- **契约形状**(``decide_prep_screen`` 终态契约 §2.2 单动作词表):返回
  **恰一个 CwAction** = 本帧要执行的那个;本帧无动作帧 →
  ``CwActionObsParam(scope='outer_loop')``(本帧无动作可发,交回外循环
  重观察;原 HoldFrame 通道并入,用户裁定 2026-09-20,``None`` 退役);
  非法形状由消费端 F3 守卫拒绝(策略器 bug 响亮暴露,禁静默跳过);
- **九段全扫**(``entry.emit``):各段触发态首中断言 + 回扫语义、自救
  动作序(按损失递增 + 真全量豁免)、晶矿垫件测试(垫件谓词过滤后取价值
  最小)、第 3 步空段零动作透传测试(旧升级判据直删后透传,新判据已写进代码)、
  节末凑息闭合即止测试、上线窗口信号表建表完备性。

帧构造纪律:
- 第 4 步商店会话标记(``shop_handled``)未打的帧会在第 4 步开店命中
  提前返回——测第 5-8 步的帧一律经 :func:`_mark_handled` 打标(商店
  会话已处理形态);生效序位经 ``gs.node_pos`` 观察写端落值
  (``effective_node_pos`` 读口,未观察 None 不当真)。
- 窗口辖域测试用追击飞霄线(synergy 3 = 板面追击 3 档;追击为流派
  键,``board_by_row`` 聚合含 flows)——规避配方底线门辖列车件的
  干扰(围栏语义与窗口辖域分立,测试只校验窗口)。
- 卖出场景帧 deployed 非空(空板守卫 = 评估器 as-built 纳入语义,
  deployed = 0 帧卖出哑火)且 deploy_vacancy = 0(防第 5 步部署先中,
  散件填位与凑息让位的序差属第 5 步语义,第 7 步测试只校验凑息)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_comp,
    cw4_gs,
    cw4_session,
    run_node,
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
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwAction,
    CwActionCollectOreParam,
    CwActionLevelUpParam,
    CwActionMoveUnitParam,
    CwActionObsParam,
    CwActionOpenBoxParam,
    CwActionOpenShopParam,
    CwActionSellBenchParam,
    CwActionStartBattleParam,
    CwActionWearEquipParam,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    CurrencyWarMatch,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    bridge as cw_bridge,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    entry,
    session_scope,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.sell_candidates import (
    INTEREST_EXEMPT_DEPLETED_KEY,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

_SIG = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')
_LOGIC_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep')


# ============================================================ 契约形状


def _prep_strategy(monkeypatch: pytest.MonkeyPatch,
                   emission: list[CwAction]) -> tuple[
        cw_bridge.MandateV1Strategy, StrategySession]:
    """mandate_v1 具现(真实类)+ 决策核发射缝桩,离线直调备战契约入口。

    - ``decide_prep_frame`` 模块桩 = 决策核发射缝——本测试辖「边界把发射
      序列映射成单动作/本帧无动作 obs」的形状,核内三遍编排/帧稳定截断不在
      测试面;预算披露(决策入口前置发射位之后)走真实现,零屏零外部面;
    - ``gs.frame_class_prep`` 缺省 'none' → 入口内务(帧代次消费)
      空转,方向刷新不触发,测试零全局残留。
    """
    session = StrategySession()
    strategy = cw_bridge.MandateV1Strategy(
        game_state_of(session),
        SimpleNamespace(strategy_seed=None))   # 终态契约:构造注入
    # (黑板帧装配已随 gs.prep_obs 退役删除——决策输入 = 容器直读,
    #  「观察帧缺失即抛错」防线随黑板消亡,编排前提由画面 op 保证。)
    monkeypatch.setattr(
        cw_bridge, 'decide_prep_frame',
        lambda session_, config, registry=None: list(emission))
    return strategy, session


def test_prep_contract_returns_single_action_first_of_emission(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """备战契约边界:有动作帧 → 返回恰一个 ``CwAction`` = 发射序列首项。

    出处 = docs/develop/sr_od/application/currency_war/flow/README.md §2.2 备战接口行(恰一个动作)。
    发射两动作只取首项:校验「单动作循环
    逐帧恰取一个动作」的边界映射——契约面返回列表整体(旧形状回潮)或
    取尾项都会在此红。
    """
    first = CwActionStartBattleParam()
    second = CwActionSellBenchParam(bench_idx=3)
    strategy, session = _prep_strategy(monkeypatch, [first, second])
    result = strategy.decide_prep_screen()
    assert isinstance(result, CwAction)
    assert result is first


def test_prep_contract_empty_emission_returns_hold_frame(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """备战契约边界:本帧无动作 → 返回 ``CwActionObsParam(scope='outer_loop')``
    = 本帧无动作交回外循环。

    出处 = docs/develop/sr_od/application/currency_war/flow/README.md §2.2 备战接口行(终态契约 §2.2:本帧无动作帧 = 交回外循环重观察,None 退役;原 HoldFrame 并入,用户裁定 2026-09-20)。
    备战域
    「本帧无动作」是合法通道:返回必须是 obs 交回口径本身——返回
    ``None``(退役形状回潮)或空列表或抛错都不合格。
    """
    strategy, session = _prep_strategy(monkeypatch, [])
    result = strategy.decide_prep_screen()
    assert isinstance(result, CwAction)
    assert isinstance(result, CwActionObsParam)
    assert result.scope == 'outer_loop'


def test_prep_consumer_rejects_illegal_return_f3_fail(
        test_context, monkeypatch: pytest.MonkeyPatch) -> None:
    """消费端守卫:非法返回(非 ``CwAction``)→ 决策循环 F3 fail。

    出处 = docs/develop/sr_od/application/currency_war/flow/README.md §2.2 备战接口行(返回恰一个动作;非法形状不进执行)。
    守卫断言
    语义 = 策略器 bug 响亮暴露:决策循环在执行前拒绝并以具名 fail
    交回外循环,禁静默跳过。走 op 决策动作 node 路径(两 node 形态
    ()的 ③-⑤ 单动作决策循环宿主,
    守卫逐字同,单测试辖同一条契约)。
    """

    class _IllegalPrepStrategy:
        """桩策略:备战决策返回非法形状(字符串;非 CwAction)。"""

        def decide_prep_screen(self) -> str:
            return '备战动作'

    match = CurrencyWarMatch(_IllegalPrepStrategy(), StrategySession())
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op = CwScreenPrep(test_context)
    # 阶段 3.5:黑板载体随 gs.prep_obs 退役——决策入口零参直读容器。
    rs = run_node(test_context, op, op.act)
    assert not rs.is_success
    assert rs.status == '策略输出非 CwAction(F3)'


# ============================================================ 九段全扫:帧构造助手


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
    """自救动作序测试(按损失递增:上阵安置 → 点消耗品 → 卖出 → 防御
    分支;每帧重评取首个可行,无试错计数;prep_pipeline §1 第 0 步)。"""

    @staticmethod
    def _rescue_frame():
        # 板面追击 1 + 飞霄(追击线终局件)在席;
        # cap 8 → 态 1 有空位可上
        sess = cw4_session()
        cw4_gs(sess, gold=30, level=6, round_num=2, node='战斗',
               bench=[_bc('飞霄')],
               front_row=_units(('知更鸟', '那刻夏')), back_row=(),
               deploy_cap=8)
        return sess

    def test_state1_deploy_free_and_window_exempt(self):
        """态 1(上阵安置,免费腾位):cap 有空位 ∧ 备战席有可上阵单位 →
        拖上阵(载体 = 统一拖动,阶段 5/6 丁:
        态 1 专用执行路径切 CwActionMoveUnitParam,选人 = bench 扫描序
        腾槽语义——unified-deploy-order §4 entry 备战工序部署面行 D3-4;
        原告警帧豁免窗口辖域语义已随 entry_signals 退役消隐——无窗口
        约束后告警帧与常规帧同态)。"""
        sess = self._rescue_frame()
        _set_overflow(sess)
        out = _emit(sess)
        moves = [e.action for e in out
                 if isinstance(e.action, CwActionMoveUnitParam)]
        assert moves and moves[0].src_domain == 'bench' \
            and moves[0].src_slot == 0, \
            f'统一拖动从 bench 槽 0 腾位,实得 {moves!r}'

    def test_state2_open_consumable_when_no_seats(self):
        """态 2(点开消耗品,免费腾位):无 cap 空位 ∧ 备战席有占席物品
        → 点开腾槽(占席道具不可卖但可点开——补给箱不可卖为实机定论;
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
        sess = cw4_session(cw4_comp('列车同行·反震'))
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
        # 取用观测键(统一让位优先级迭代 3.5;键表 = telemetry/schema.py
        # 键表节;键域 1..10 = 完成品保护迭代 design §2.5-7):c0/c1/c2 =
        # 注册表外测试名(实费缺读按中费 3 保守估,非成员非羁绊)= 同键
        # 等价牌群 → 兜底档 10 档位分布落账 ∧ 随机尾键命中落账(取用件
        # 在等价群内由尾键定序,命中哨兵语义;兜底档号 8→10 位移 =
        # design §2.2 十档判定表)。
        ct = state_of(sess).cw4_counters
        assert ct.get('self_rescue_sell_tier_10') == 1
        assert ct.get('self_rescue_sell_rng_tail_hit') == 1

    def test_state3_full_pool_exemptions_reach_line_member(self):
        """真全量豁免测试:候选只剩线内核心件(常规面恒拒)时自救仍可卖
        ——P78-4 核心/④件身份段在自救场景豁免、按价值序末位可卖。"""
        sess = cw4_session(cw4_comp('列车同行·反震'))
        cw4_gs(sess, gold=30, level=4, round_num=2, node='战斗',
               bench=[_bc('姬子·启行')] + [_bc('c2')] * 8,
               front_row=_units(('三月七', '瓦尔特', '丹恒·饮月', '姬子')),
               back_row=())
        _set_overflow(sess)
        out = _emit(sess)
        # 阶段 5/6:统一部署搜索的档 1 含锁定线核心(bench 姬子·启行),
        # 统一序列末位 = 场上部署外低值件(姬子)——自救卖出形态随 victim
        # 落位分派(SellBench/SellDeployed),零停机出口语义不变。
        from sr_od.application.currency_war.kernel.cw_vocab import (
            CwActionSellDeployedParam,
        )
        sells = [e.action for e in out
                 if isinstance(e.action, (CwActionSellBenchParam,
                                          CwActionSellDeployedParam))]
        assert len(sells) == 1, \
            '自救扩展面真全量:低值件末位可卖(零停机出口)'

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


# ============================================================ 第 1 步:消耗品


class TestStep1Consumable:
    """第 1 步点开消耗品测试(prep_pipeline §1 第 1 步:点开顺序 =
    书册卡 → 补给箱 → 星徽秘典,依据 = 现行实体面臂序在案)。"""

    def test_kind_priority_dominates_slot_order(self):
        """点开优先级差分测试:同帧 bookcard 与 supply_box 均在场且
        supply_box 槽位在前(槽 0)、bookcard 在后(槽 1)→ 按 kind
        优先级取书册卡——校验「kind 优先序」非「槽位序首中」(若按槽位
        序会先开槽 0 的补给箱)。"""
        from sr_od.application.currency_war.kernel.cw_vocab import (
            CwActionOpenBookcardParam,
        )
        sess = cw4_session()
        cw4_gs(sess, gold=30, level=6, round_num=2, node='战斗',
               bench=[BenchSlot(kind='supply_box'), BenchSlot(kind='bookcard')]
               + [_bc('c0')] * 7,
               front_row=_units(('三月七',)), back_row=())
        out = _emit(sess)
        assert len(out) == 1 \
            and isinstance(out[0].action, CwActionOpenBookcardParam)
        assert out[0].action.slot == 2, 'kind 优先:书册卡(槽 2)先于补给箱(槽 1)'


# ============================================================ 第 2 步:晶矿


class TestStep2Ore:
    """晶矿测试(prep_pipeline §1 第 2 步:席未满点全部;席满 = 统一序列
    末位让位一张,3.2 改造 = 垫件谓词过滤退役【拍,总纲 §2.7 无场景
    专属池子/身份过滤退役】——部署重排定型后的全局面序列,末位即让位
    对象;无任何可卖件 → 放弃晶矿保留;ore_defer 键族退役)。

    构帧纪律:统一序列前置 = 部署重排定型——场前排铺满 cap(空位帧
    备战位件会被 M1 补位收进部署需要面而整体 sheltered,测不到让位序)。
    """

    @staticmethod
    def _full_bench_frame():
        # deployed 非空且铺满 cap(level 6 → 6 件,绕空板守卫 + 板满
        # 前置);9 席满
        sess = cw4_session()
        cw4_gs(sess, gold=30, level=6, round_num=2, node='战斗',
               bench=[_bc('c1', star=2), _bc('c2', star=2), _bc('c0')]
               + [_bc('c3', star=2)] * 6,
               front_row=_units(('d1', 'd2', 'd3', 'd4')),
               back_row=_units(('d5', 'd6')))
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

    def test_full_seat_sells_sequence_tail(self):
        """席满 → 统一序列末位让位一张:1★ 件(同费档同概率域键更大)
        先于 2★ 件让位——「序列末位」非「垫件身份过滤」(垫件谓词退役,
        3.2;星级让位代价由档位结构承载)。"""
        sess = self._full_bench_frame()
        _write_ores(game_state_of(sess), (('gold', 100, 200, 30),))
        out = _emit(sess)
        sells = [e.action for e in out
                 if isinstance(e.action, CwActionSellBenchParam)]
        assert len(sells) == 1 and sells[0].reason == 'ore_make_room'
        # c0(唯一 1★,紧缩位 2 → 容器槽 2)= 序列末位被卖
        assert sells[0].bench_idx == 2

    def test_full_seat_yields_via_sequence_tail(self):
        """席满点晶矿 → 统一序列末位让路卖一件腾位(身份段已随统一让位
        优先级迭代 3.4 退役——原「全池身份排除 → 放弃晶矿」形态废止:
        万金油铺席件按档 8/10 落序列(万金油层 = 档 8、到两星掉兜底
        档 10,旧八档档 6/8 位移,design §2.2/§2.3-4 十档口径),序列
        真空才放弃晶矿;单动作契约 =
        先卖,下帧席位空出后采晶)。让位支接受 bench/场上两支:本构局
        (bench 三月七可上场 + 场上未识别件)部署定型后让位末位 = 场上
        未识别件——卖场上件腾位同样合法(entry_signals 退役后三月七
        可上场,部署定型参与让位序)。"""
        sess = cw4_session()
        cw4_gs(sess, gold=30, level=6, round_num=2, node='战斗',
               bench=[_bc('三月七', star=2)] * 9,
               front_row=_units(('d1', 'd2', 'd3', 'd4', 'd5', 'd6')),
               back_row=())
        _write_ores(game_state_of(sess), (('gold', 100, 200, 30),))
        out = _emit(sess)
        from sr_od.application.currency_war.kernel.cw_vocab import (
            CwActionSellDeployedParam,
        )
        sells = [e for e in out
                 if isinstance(e.action, (CwActionSellBenchParam,
                                          CwActionSellDeployedParam))]
        assert sells, f'席满帧应序列让路卖出(bench/场上支): {out!r}'
        assert sells[0].reason.startswith('ore_make_room'), \
            f'让路卖出场景 = 采晶矿前空位: {sells[0].action!r}(场景键 {sells[0].reason})'
        assert not [e for e in out
                    if isinstance(e.action, CwActionCollectOreParam)], \
            '单动作契约:腾位卖出帧不并发采晶(下帧席位空再采)'

    def test_rescan_collects_after_seat_freed(self):
        """回扫语义测试:席满卖序列末位腾位(上报后席 8)→ 下帧全扫
        回到第 2 步 → 点晶矿(腾位后回头点晶矿的回跳在全扫下自然表达)。"""
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

    # (「垫件过滤优先于全局价值排序」差分测试已随垫件谓词退役删除
    # (3.2,总纲 §2.7 身份过滤退役)——统一序列的取用语义断言由
    # strategies/impl/mandate_v1/criteria/test_sell_candidates.py
    # TestUnifiedSequence 承载。)


# ============================================================ 第 3 步:升级检查


class TestStep3LevelUp:
    """第 4 步升级测试(11 号稿 §2:触发单判据三分派 + 单帧原子发射——
    判据单帧测试主文件 = test_levelup_prob_axis.py,本类只校验工序接入调用
    形态)。"""

    def test_upgrade_friendly_state_emits_batch(self):
        """升级友好形态(带滞后 + 金充裕)发射升级整批:锁定线唯一
        未完成星级目标(希儿 3 费)带下界 7 > 等级 4 → stay_gate 触发,
        现金 − 批 ≥ 利息线 → 同帧执行帧一次买齐(P48 整买;先前空段期
        透传测试已随新判据写进代码而终结,替代语义 = 本形态测试)。"""
        sess = cw4_session(cw4_comp('希儿量子'))
        cw4_gs(sess, gold=80, level=4, round_num=2, node='战斗', plane=2,
               bench=[_bc(n, 1) for n in ('花火', '符玄', '缇宝', '刻律德菈')]
                     + [_bc('希儿', 1)],
               front_row=(), back_row=())
        _gs = game_state_of(sess)
        _gs.strategy_state = state_of(sess)   # 宿主归一(session_scope 函数族经 gs 取态)
        _gs.node_hist_pos = (2, 1)   # P2 水位(窗口谓词置位输入)
        session_scope.handle_node_boundary(_gs)
        state_of(sess).gold_ledger = 80   # 边界复位清账面后重锚(种子稳态)
        _mark_handled(sess)
        out = _emit(sess)
        ups = [e for e in out
               if isinstance(e.action, CwActionLevelUpParam)]
        assert ups, '升级友好形态:带滞后触发升级发射'
        assert ups[0].action.clicks >= 1


# ============================================================ 第 4 步:商店会话


class TestStep4ShopSession:
    """第 4 步商店会话入口测试(契约 A:标记判定 + 解拦复核接入调用位)。
    ``test_handled_marker_skips_step`` 兼辖「全静帧唯一完成态」事实
    (以上全部步骤无动作 → 恰一个出战交回,原第 8 步测试同帧同断言)。"""

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
        # gold 50 = 恰在溢余带外(不 > 息线)且凑息线外(不 < 息线):
        # 两金带动作都不触发,帧走满全扫到出战
        cw4_gs(sess, gold=50, level=6, round_num=2, node='战斗',
               bench=[], front_row=(), back_row=())
        _mark_handled(sess)
        out = _emit(sess)
        assert len(out) == 1 and isinstance(out[0].action, CwActionStartBattleParam)


# ============================================================ 第 5 步:部署调整


class TestStep5DeployWindow:
    """部署上场时机测试(entry_signals 整体退役后行为面登记,2026-11
    用户终裁「可退役」:无上阵窗口硬约束——上场时机 = 部署搜索骨架/L1
    完成度自适应,终局件不再被窗口挡;万敌 1 条/白厄 3 条知识真空接受
    损失,退化观测挂 sim)。"""

    @staticmethod
    def _window_frame(front: tuple[str, ...], *, level: int = 6,
                      deploy_cap: int | None = 8):
        # gold 50 = 恰在两金带外(不 > 息线 ⇒ 第 3 步溢余臂不触发;不 <
        # 息线 ⇒ 第 7 步凑息不触发)——上场时机测试只校验第 5 步部署。
        sess = cw4_session()
        cw4_gs(sess, gold=50, level=level, round_num=2, node='战斗',
               bench=[_bc('飞霄')],
               front_row=_units(front), back_row=(),
               deploy_cap=deploy_cap)
        _mark_handled(sess)
        return sess

    def test_endgame_member_deploys_without_window(self):
        """无窗口约束(行为翻转登记):追击仅 1 档(原「窗口未到」帧)纯
        终局件飞霄照上——L3 计数自然填位,退役前该帧被窗口辖域过滤不上
        (emit 无部署动作透传到出战)。"""
        sess = self._window_frame(('知更鸟', '那刻夏'))
        out = _emit(sess)
        from sr_od.application.currency_war.kernel.cw_vocab import (
            CwActionMoveUnitParam,
        )
        moves = [e.action for e in out
                 if isinstance(e.action, CwActionMoveUnitParam)]
        assert moves and moves[0].src_domain == 'bench' \
            and moves[0].src_slot == 0, \
            '终局件无窗口约束:飞霄按 L3 填位上场'

    def test_endgame_member_deploys_on_full_synergy(self):
        """档齐帧照上(行为方向与退役前一致):板面追击 3 档齐 = 候选线
        L1 增量主载,飞霄上场(阶段 5/6 载体 = 统一拖动)。"""
        sess = self._window_frame(('知更鸟', '不死途', '貊泽'))
        out = _emit(sess)
        from sr_od.application.currency_war.kernel.cw_vocab import (
            CwActionMoveUnitParam,
        )
        moves = [e.action for e in out
                 if isinstance(e.action, CwActionMoveUnitParam)]
        assert moves and moves[0].src_domain == 'bench' \
            and moves[0].src_slot == 0

    def test_transition_member_exempt(self):
        """过渡∩终局重叠件按过渡成员正常上阵(线内件优先占席,与窗口
        退役无关的既有语义):现行过渡配方成员(锁定线物化链)的部署由
        L1/L2 完成度承载。"""
        sess = cw4_session(cw4_comp('追击飞霄'))
        cw4_gs(sess, gold=30, level=6, round_num=2, node='战斗',
               bench=[_bc('飞霄')],
               front_row=_units(('知更鸟', '那刻夏')), back_row=(),
               deploy_cap=8)
        _mark_handled(sess)
        out = _emit(sess)
        from sr_od.application.currency_war.kernel.cw_vocab import (
            CwActionMoveUnitParam,
        )
        moves = [e.action for e in out
                 if isinstance(e.action, CwActionMoveUnitParam)]
        assert moves, '线内件的正常部署不被挡'

    def test_wandi_deploys_without_signal(self):
        """万敌上场不再依赖 always_on 信号(信号表已退役;L3 单位序承载
        ——退役前万敌靠 always_on 例外放行,退役后同帧行为不变,登记
        口径从「窗口例外」改「计数填位」)。"""
        sess = cw4_session()
        cw4_gs(sess, gold=30, level=6, round_num=2, node='战斗',
               bench=[_bc('万敌')],
               front_row=_units(('知更鸟', '那刻夏', '三月七')), back_row=(),
               deploy_cap=8)
        _mark_handled(sess)
        out = _emit(sess)
        from sr_od.application.currency_war.kernel.cw_vocab import (
            CwActionMoveUnitParam,
        )
        moves = [e.action for e in out
                 if isinstance(e.action, CwActionMoveUnitParam)]
        assert moves, '万敌按 L3 计数填位上场(无信号依赖)'


# ============================================================ 第 6 步:装备与工具


class TestStep6EquipTools:
    """第 6 步装备与工具接入调用测试(装备穿戴判据本体保留;工具评估留痕
    计数 = 现行 M7.5 发射位口径)。"""

    def test_wear_plan_emits_and_tool_eval_counter(self):
        """owned 可穿 → 穿戴计划发射(CwActionWearEquipParam);工具
        评估留痕(m7_5_evaluated;零可执行件帧 reject_none 暴露)。"""
        sess = cw4_session()
        cw4_gs(sess, gold=50, level=6, round_num=2, node='战斗',
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
    """节末凑息测试(金 < 息线 → 卖 1★ 全额退件补缺口;卖到缺口闭合
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
        """跨档可行帧(金 48,下一档线 50,缺口 2):卖 1★ 全额退件候选
        一张(退金 ≥ 缺口才发,取退金最小;单动作循环:每帧一张,卖出
        上报更新金位后下帧重评)。跨不了档的帧(gold 40 缺 10,退金 3)
        = 'no_tier_gain' 零卖出,资格面该测试由 criteria/test_sell_
        candidates 承载。"""
        sess = self._frame(48, [_bc('c0'), _bc('c1')])
        out = _emit(sess)
        sells = [e.action for e in out
                 if isinstance(e.action, CwActionSellBenchParam)]
        assert len(sells) == 1 and sells[0].reason == 'interest_prep'
        assert sells[0].bench_idx == 0

    def test_gap_closed_stops_selling(self):
        """闭合即止测试:卖出退金使金位 ≥ 息线后,下一帧不再卖(不多卖
        一张,卖回量最小化)。bench = 风堇(2 费 1★ 退 2,48+2 = 50
        恰闭合不越线——越过息线即入溢余带,第 3 步升级臂会接手,本测试
        只校验凑息即止)。风堇 = 非四体系(昼之半神/燃血):凑息资格件
        须穿过保护集身份段(统一保护集 changes/2026-10-15-unified-
        protection-set design.md §2.3;原构架卡芙卡属持续伤害系保护档,
        常规面禁卖,不再可作凑息样本)。"""
        sess = self._frame(48, [_bc('风堇')])   # 48 + 2(退) = 50 ≥ 50
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

    def test_exempt_depleted_frame_zero_action_with_counter(self):
        """凑息豁免剔光帧(第 8 步集成面):唯一可行件为线内未达标成员
        → 零卖出动作 + 剔光观测键落**生产** counters(roster-plane1-
        union design §2.2 第 5 项;观测键接入调用 = 第 8 步传 cw4_counters
        ——删该传参则行为不变而键永不落账,本测试锁生产写点)。金 2 →
        缺口 8:姬子·启行 2★(列车同行 need 3 未达标)退金 3×3−1 = 8
        恰跨档,布洛妮娅 1★ 退金 5 < 8 不可行——无豁免时本帧卖出在建
        阵容件,豁免后零动作。板上三月七/瓦尔特 = 部署定型内档 1,
        不入卖出池。候选线种在容器宿主状态(state_of(gs)——cw4_session
        桩与容器惰建态在此构造路径下非同对象,判据读口走容器侧)。"""
        sess = self._frame(2, [_bc('姬子·启行', 2), _bc('布洛妮娅')])
        st = state_of(game_state_of(sess))
        st.line_candidates = ('列车同行·反震',)
        out = _emit(sess)
        sells = [e.action for e in out
                 if isinstance(e.action, CwActionSellBenchParam)]
        assert not sells, '凑息零卖出(阶段 5/6:统一部署搜索把线内核心' \
            '件收进档 1——比凑息豁免更强的保护,同一零卖出出口)'
        # 阶段 5/6 行为申报:档 1 编入先于豁免剔除(池在豁免前已空,
        # 拒因 = no_candidates 非 exempt_depleted)——剔光观测键辖
        # 「豁免真翻转卖出→零动作」帧,由 criteria 单测
        # (test_sell_candidates 凑息豁免族)继续锁定。
        assert st.cw4_counters.get(INTEREST_EXEMPT_DEPLETED_KEY, 0) == 0, \
            '档 1 编入帧不落剔光键(键辖豁免真翻转帧)'

    def test_above_line_no_sell(self):
        """金 ≥ 息线 → 本步零动作(透传到出战;50 = 恰在溢余带外,
        第 3 步升级臂亦不触发)。"""
        sess = self._frame(50, [_bc('c0')])
        out = _emit(sess)
        assert isinstance(out[0].action, CwActionStartBattleParam)
        assert not [e for e in out
                    if isinstance(e.action, CwActionSellBenchParam)]

    def test_protected_member_now_sellable_per_sequence(self):
        """身份段退役后的节末凑息形态(统一让位优先级迭代 3.4:凑息 =
        部署重排后全局面序列取用,无身份排除;原「凑息保护档阻断观测键
        interest_round_protected_block」随身份保护判据退役——键停止
        生产):保护档成员(卡芙卡,1★ 退 2 ≥ 缺口 2)按统一序列取用 →
        凑息卖出发生。"""
        sess = self._frame(48, [_bc('卡芙卡')])
        out = _emit(sess)
        sells = [e for e in out
                 if isinstance(e.action, CwActionSellBenchParam)]
        assert sells, f'身份段退役后凑息应卖出可跨档件: {out!r}'
        assert not state_of(sess).cw4_counters.get(
            'interest_round_protected_block'), \
            '退役键不得复现'


# ============================================================
# 部署自适应 6 场景(entry_signals 整体退役后的行为登记锚;审查设计——
# 知识真空线〔万敌 1 条/白厄 3 条〕的退化面显式登记,退化明显再议的
# 对照基线;sim A/B 挂批跑工具恢复,欠账登记 = .debug/progress/
# unified-line-scoring-sim-debt.md)
# ============================================================


class TestDeployAdaptiveAfterEntryRetirement:
    """退役时点部署自适应行为面(单帧构局):无窗口硬约束下终局件
    上场时机全由 L1/L3 完成度与单位序承载。"""

    @staticmethod
    def _frame(*, front=(), bench=(), level=6, deploy_cap=None,
               lock_pair=None, target_comp=None, gold=50):
        sess = cw4_session(cw4_comp(target_comp) if target_comp else None)
        cw4_gs(sess, gold=gold, level=level, round_num=2, node='战斗',
               bench=list(bench), front_row=_units(tuple(front)),
               back_row=(), **({'deploy_cap': deploy_cap}
                               if deploy_cap is not None else {}))
        st = state_of(sess)
        if lock_pair is not None:
            from sr_od.application.currency_war.kernel.cw_intention import (
                IntentionState,
            )
            ist = IntentionState()
            ist.p1_pair = lock_pair
            st.v3_intention = ist
        if target_comp is not None:
            from sr_od.application.currency_war.kernel.cw_comps import get_comp
            st.target_comp = get_comp(target_comp)
        _mark_handled(sess)
        return sess

    @staticmethod
    def _moves(sess):
        from sr_od.application.currency_war.kernel.cw_vocab import (
            CwActionMoveUnitParam,
        )
        out = _emit(sess)
        return [e.action for e in out
                if isinstance(e.action, CwActionMoveUnitParam)]

    def test_baie_k_rich_both_fill(self):
        """①a 白厄未成型局 K 富余(level 6 人口宽裕):P1 配方锁(DOT)
        +bench 白厄三月七——三月七(列车体系件)与白厄(纯终局件)双上,
        L3 计数自然填位(退役前白厄被 plane_end 窗口挡,三月七被列车
        synergy 窗口挡)。"""
        sess = self._frame(front=('桑博', '艾丝妲'),
                           bench=[_bc('白厄'), _bc('三月七')],
                           lock_pair=('持续伤害',))
        assert len(self._moves(sess)) >= 2, 'K 富余:双件 L3 填位'

    def test_baie_k_tight_march7_only(self):
        """①b K 紧张(level 3 空位 1):体系侧三月七优先上位(列车体系
        件单位序),白厄留 bench——垫件分级 = L3 单位序自适应,无窗口
        也不过量上终局件。"""
        sess = self._frame(front=('桑博', '艾丝妲'),
                           bench=[_bc('白厄'), _bc('三月七')],
                           level=3, lock_pair=('持续伤害',))
        moves = self._moves(sess)
        assert len(moves) == 1 and moves[0].src_slot == 1, \
            'K 紧张:仅三月七(bench 槽 1)上位,白厄留席'

    def test_wandi_k_states_both_deploy(self):
        """② 万敌单卡局(P1 DOT 配方,K 两态):万敌退役前靠 always_on
        例外放行;退役后 K 富余/紧张(空 1)两态均上场——万敌 L3 单位序
        压过同帧竞争垫件(「越早越好」语义由计数序承接,sim 血线观测)。"""
        for level in (3, 6):
            sess = self._frame(front=('桑博', '艾丝妲'),
                               bench=[_bc('万敌')], level=level,
                               lock_pair=('持续伤害',))
            moves = self._moves(sess)
            assert moves and moves[0].src_slot == 0, \
                f'万敌 K {"紧张" if level == 3 else "富余"}态照上'

    def test_daheita_solo_l1_progressive(self):
        """③ 大黑塔单挂局(P2 未锁,候选含大黑塔线):bench 大黑塔+黑塔
        双上——候选线 L1 完成度渐进收件(无窗口也按线骨架收,退役前后
        行为一致——大黑塔 synergy 档未齐同帧行为)。"""
        sess = self._frame(bench=[_bc('大黑塔'), _bc('黑塔')], level=8)
        assert len(self._moves(sess)) >= 2, '候选线骨架渐进收件(双上)'

    def test_dot_mix_transition_skeleton(self):
        """④ DOT 混过渡局(P1 无配方锁):bench 卡芙卡+黑天鹅——持续
        伤害过渡体系骨架自然收(体系激活 L1 驱动,与窗口无关的既有
        语义登记)。"""
        sess = self._frame(front=('三月七', '瓦尔特'),
                           bench=[_bc('卡芙卡'), _bc('黑天鹅')])
        assert len(self._moves(sess)) >= 2, '过渡体系骨架自然收'

    def test_locked_daheita_regression_anchor(self):
        """⑤ 锁定大黑塔线回归锚:锁定帧上场行为与未锁候选帧一致
        (③ 对照)——退役前锁定帧窗口谓词结构性恒 False(两条豁免分支
        全覆盖),退役后零变化。"""
        sess = self._frame(bench=[_bc('大黑塔'), _bc('黑塔')], level=8,
                           target_comp='大黑塔银河学者')
        assert len(self._moves(sess)) >= 2, '锁定线骨架照常上场(零变化)'

    def test_locked_baie_regression_anchor(self):
        """⑥ 锁定白厄线回归锚:锁定线 L1 骨架(白厄空羁绊线 = 角色完成
        度单独承载)照常上场——退役前白厄线锁定帧本就豁免窗口,退役后
        零变化(白厄 3 条 plane_end 知识真空只影响未锁囤积期)。"""
        sess = self._frame(bench=[_bc('白厄'), _bc('三月七')],
                           target_comp='反甲白厄')
        assert len(self._moves(sess)) >= 2, '锁定白厄线照常上场(零变化)'
