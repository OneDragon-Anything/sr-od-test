"""W59 先行件锁(W52 设计稿 §6 执行序第 1 步):R4 两件 + S7 fill-skip log。

- R4-1(§3.1):battle_loop recovered 三字段 + match 建立/续用块迁 handle_init
  ——execute 重入重置的框架语义锁(不依赖实机);
- R4-2(§3.2):对账异常元组 EQUIPS_CONSISTENCY_ERRORS 单点化 + deploy_bench
  消费锁;
- S7(§2):fill_gap_after 金不足/源不足跳过 → [cw][d2][fill-skip] log 行,
  行为不变(只加可观测性)。
"""
import inspect
import time
from types import SimpleNamespace
from sr_od.application.currency_war.telemetry import state

from sr_od.application.currency_war.kernel.cw_bench_equips import (
    EQUIPS_CONSISTENCY_ERRORS,
    EquipsInconsistencyError,
)

# ---------- R4-1:handle_init 三字段迁移 ----------


def _make_loop(monkeypatch, *, cw_match):
    """构 battle_loop 桩:bypass __init__,monkeypatch handle_init 依赖面。

    StrategyManager/CurrencyWarMatch/CurrencyWarConfig/遥测全部桩化(自动还原,
    不触真实配置/插件目录);ctx 用 SimpleNamespace 喂 handle_init 消费的字段。
    """
    from sr_od.application.currency_war.operations import battle_loop as bl

    monkeypatch.setattr(bl, 'reset_phase_round_cache', lambda: None)
    monkeypatch.setattr(bl, 'CurrencyWarConfig',
                        lambda idx: SimpleNamespace(strategy_id='stub',
                                                    strategy_seed=None))
    _session = SimpleNamespace()

    class _SM:  # StrategyManager 桩:instantiate → strategy → create_session
        def __init__(self, ctx, dirs):
            pass

        def instantiate(self, sid: str):
            return SimpleNamespace(create_session=lambda cfg: _session)

    monkeypatch.setattr(bl, 'StrategyManager', _SM)
    monkeypatch.setattr(bl, 'CurrencyWarMatch',
                        lambda strategy, session: SimpleNamespace(
                            strategy=strategy, session=session, _stub_match=True))
    monkeypatch.setattr(state, 'set_ctx_match',
                        lambda m: None)

    ctx = SimpleNamespace(
        cw_match=cw_match, current_instance_idx=1,
        currency_war_strategy_plugin_dirs=[],
        cw_briefing_affixes=None, cw_selected_difficulty=None,
        cw_enemy_difficulty=None, cw_briefing_bosses=None,
    )

    class _Loop(bl.CurrencyWarRunLoop):
        def __init__(self, ctx):  # noqa: D107  桩:bypass SrOperation.__init__
            self.ctx = ctx

    return _Loop(ctx)


def test_handle_init_new_match_first_execute(monkeypatch) -> None:
    """首次 execute(handle_init 由 _init_before_execute 调):cw_match 为空 →
    新局建立 + 三字段就位(与原 __init__ 时序等价)。"""
    op = _make_loop(monkeypatch, cw_match=None)
    op.handle_init()
    assert op._is_new_match is True
    assert getattr(op.ctx.cw_match, '_stub_match', False)   # match 已建立
    assert op._first_settlement_seen is False
    assert time.monotonic() - op._run_start_ts < 5


def test_handle_init_reentry_resets_three_fields(monkeypatch) -> None:
    """execute 重入(R4 审查检查项 4 的缺陷场景):三字段残留脏值 →
    handle_init 复位;_is_new_match 重判(cw_match 已建立 → 不再当新局,
    保守方向漏标不误标)。"""
    op = _make_loop(monkeypatch, cw_match=None)
    op.handle_init()                       # 第一轮 execute
    # 模拟第一轮执行中字段变脏(结算已见/时间戳陈旧/新局标记残留)
    op._first_settlement_seen = True
    _stale_ts = time.monotonic() - 9999.0
    op._run_start_ts = _stale_ts
    op.handle_init()                       # 第二轮 execute(execute 重入)
    assert op._first_settlement_seen is False       # 复位
    assert op._run_start_ts > _stale_ts             # 时间戳刷新
    assert op._is_new_match is False                # 重判:不再当新局


def test_handle_init_continuation_match_not_rebuilt(monkeypatch) -> None:
    """续跑局(ctx.cw_match 上轮留下):handle_init 延用不重建。"""
    _prev = SimpleNamespace(_prev_match=True)
    op = _make_loop(monkeypatch, cw_match=_prev)
    op.handle_init()
    assert op._is_new_match is False
    assert op.ctx.cw_match is _prev        # 延用,未 new


def test_framework_calls_handle_init_before_execute() -> None:
    """框架语义锁:_init_before_execute 调 handle_init(execute 每次开头)。"""
    from one_dragon.base.operation.operation import Operation
    src = inspect.getsource(Operation._init_before_execute)
    assert 'self.handle_init()' in src


# ---------- R4-2:对账异常元组单点化 ----------


def test_equips_consistency_errors_tuple() -> None:
    """元组包含 EquipsInconsistencyError 且可作 except 捕获面。"""
    assert EquipsInconsistencyError in EQUIPS_CONSISTENCY_ERRORS
    caught = False
    try:
        raise EquipsInconsistencyError('c', [], [], 't')
    except EQUIPS_CONSISTENCY_ERRORS:
        caught = True
    assert caught


def test_deploy_bench_consumes_tuple() -> None:
    """deploy_bench 挂点消费元组(不再手写异常类;上游演化只改元组单点)。"""
    from sr_od.application.currency_war.operations.prep import deploy_bench
    src = inspect.getsource(deploy_bench)
    assert 'except EQUIPS_CONSISTENCY_ERRORS' in src
    assert 'except EquipsInconsistencyError' not in src   # 旧手写面清零


# ---------- S7:fill-skip 可观测性 ----------


def _bench_char(name: str):
    """注册表真值构造 BenchChar(同 test_cw_evolution 构造法)。"""
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.kernel.cw_state import BenchChar
    c = CHARACTERS[name]
    return BenchChar(slot=0, char_id=name,
                     faction=(c.factions or ['?'])[0],
                     position_pref=c.position_pref(), star=1)


def _fill_state(gold: int, shop_names_cost: list[tuple[str, int]]):
    """构造 gap>0 的填位场景:仙舟三人已上场(level 8)、bench 空、店给插件卡。"""
    from sr_od.application.currency_war.kernel.cw_state import (
        GameState,
        ShopCard,
        _recount_board,
    )

    st = GameState()
    st.gold = gold
    st.level = 8
    st.deployed = [_bench_char('藿藿'), _bench_char('符玄'), _bench_char('彦卿')]
    st.board = _recount_board(st.deployed)
    st.bench = []
    st.shop = [ShopCard(x=i, faction='', name=n, cost=c)
               for i, (n, c) in enumerate(shop_names_cost)]
    return st


def test_fill_skip_gold_logged_behavior_unchanged(monkeypatch) -> None:
    """金不足跳过店内插件件 → [cw][d2][fill-skip] 金不足行 + 源不足汇总行;
    填位行为不变(fills 仍为空,与无 log 时一致)。"""
    from sr_od.application.currency_war.kernel import cw_evolution
    from sr_od.application.currency_war.kernel.cw_state import CompTransaction

    captured: list[tuple[str, object]] = []

    class _Log:  # log 桩:只捕 info,不写真实日志面
        @staticmethod
        def info(msg, *args):
            captured.append(('info', msg % args if args else msg))

    monkeypatch.setattr(cw_evolution, 'log', _Log)
    st = _fill_state(gold=2, shop_names_cost=[('知更鸟', 5)])
    tx = CompTransaction([], [], [], reason='t')
    fills = cw_evolution.fill_gap_after(tx, st)
    assert fills == []   # 行为不变:金 2 < 费 5,仍跳过
    msgs = [m for _, m in captured]
    assert any('fill-skip' in m and '金不足' in m and '知更鸟' in m
               for m in msgs), msgs
    assert any('fill-skip' in m and '留空位' in m for m in msgs), msgs


def test_fill_no_log_when_fully_filled(monkeypatch) -> None:
    """缺口填满(反向锁):无 fill-skip 噪声行。"""
    from sr_od.application.currency_war.kernel import cw_evolution
    from sr_od.application.currency_war.kernel.cw_state import CompTransaction

    captured: list[str] = []

    class _Log:
        @staticmethod
        def info(msg, *args):
            captured.append(msg % args if args else msg)

    monkeypatch.setattr(cw_evolution, 'log', _Log)
    # gap=1(level 1 空板)且 bench 有插件单卡可填 → 填满,零 fill-skip 行
    st = _fill_state(gold=10, shop_names_cost=[])
    from sr_od.application.currency_war.kernel.cw_state import _recount_board
    st.level = 1
    st.deployed = []
    st.board = _recount_board([])
    st.bench = [_bench_char('知更鸟')]
    tx = CompTransaction([], [], [], reason='t')
    fills = cw_evolution.fill_gap_after(tx, st)
    assert len(fills) == 1 and fills[0].source == 'bench'
    assert not any('fill-skip' in m for m in captured), captured


# ---------- 增补件:valley_rollback 两发射点补填 expect(设计稿 §1.7) ----------
# 任务书写「SellBench 发射」为笔误——实际唯二发射点是 SwapDeploy(_swap_action)
# 与 SellDeployed(_sell_action),按设计稿 §1.7 与现状代码为准。


def _rollback_state():
    """谷底回滚场景:last_deployed=新档上场名单(含最弱件)、bench 有旧档保留件
    (last_retained)→ SwapDeploy 支;无保留件 → SellDeployed 支。"""
    from sr_od.application.currency_war.kernel.cw_evolution import EvolutionState
    from sr_od.application.currency_war.kernel.cw_state import _recount_board

    st = _fill_state(gold=10, shop_names_cost=[])   # level 8,仙舟 3 人在场
    st.board = _recount_board(st.deployed)
    mem = EvolutionState()
    mem.last_deployed = ['藿藿', '符玄', '彦卿']
    mem.last_retained = ['桑博']
    st.bench = [None] * 9   # 槽位模型(定长 9,None=空槽)
    st.bench[0] = _bench_char('桑博')   # 旧档保留件入 bench
    return st, mem


def test_rollback_swap_emits_expect_from_snapshot() -> None:
    """正向锁:SwapDeploy 支发射即带 expect_deployed/expect_bench=快照名
    (候选生成时 state 的 d_idx/b_idx 槽内名),且对生成快照执行正常通过。"""
    from sr_od.application.currency_war.kernel import cw_evolution
    from sr_od.application.currency_war.kernel.cw_state import (
        SwapDeploy,
        simulate,
    )

    st, mem = _rollback_state()
    act = cw_evolution.rollback_weakest(st, mem)
    assert isinstance(act, SwapDeploy)
    assert act.expect_deployed != '' and act.expect_bench != ''
    # 最弱件按(星级,费用)键 → 三件同名键取 min 首个;expect 与快照槽一致
    assert act.expect_deployed == st.deployed[act.deployed_idx].char_id
    assert act.expect_bench == '桑博'
    assert mem.paused is True
    # 对生成快照执行:expect 一致 → 正常通过(非 stale_proposal)
    out = simulate(st, act)
    assert not (out.action_log and 'stale_proposal' in str(out.action_log[-1]))


def test_rollback_sell_emits_expect() -> None:
    """正向锁(退役支):无旧档保留件 → SellDeployed 带 expect=快照名。"""
    from sr_od.application.currency_war.kernel import cw_evolution
    from sr_od.application.currency_war.kernel.cw_state import (
        SellDeployed,
        simulate,
    )

    st, mem = _rollback_state()
    mem.last_retained = []   # 无保留件 → 退役支
    act = cw_evolution.rollback_weakest(st, mem)
    assert isinstance(act, SellDeployed)
    assert act.expect == st.deployed[act.deployed_idx].char_id != ''
    out = simulate(st, act)
    assert not (out.action_log and 'stale_proposal' in str(out.action_log[-1]))


def test_rollback_expect_stale_rejected() -> None:
    """反向锁:生成后 bench/deployed 变动(跨代际)→ 执行期 expect 不符 →
    stale_proposal 整动作拒(死防线激活实证;禁止从 working 取名的语义锚)。"""
    from sr_od.application.currency_war.kernel import cw_evolution
    from sr_od.application.currency_war.kernel.cw_state import simulate

    st, mem = _rollback_state()
    act = cw_evolution.rollback_weakest(st, mem)   # 对快照生成(expect 已锁名)
    # 陈旧场景:生成与执行之间,上场槽位被换成别人(另一动作先执行)
    _repl = _bench_char('娜塔莎')
    _repl.star = 1
    st.deployed[act.deployed_idx] = _repl
    out = simulate(st, act)
    assert (out.action_log
            and out.action_log[-1].get('result') == 'rejected'
            and 'stale_proposal' in str(out.action_log[-1].get('reason', '')))


def test_rollback_sell_expect_stale_rejected() -> None:
    """反向锁(退役支):expect 与场上槽内名不符 → stale_proposal 拒。"""
    from sr_od.application.currency_war.kernel import cw_evolution
    from sr_od.application.currency_war.kernel.cw_state import simulate

    st, mem = _rollback_state()
    mem.last_retained = []
    act = cw_evolution.rollback_weakest(st, mem)
    st.deployed[act.deployed_idx] = _bench_char('娜塔莎')   # 跨代际换人
    out = simulate(st, act)
    assert (out.action_log
            and out.action_log[-1].get('result') == 'rejected'
            and 'stale_proposal' in str(out.action_log[-1].get('reason', '')))


