"""T-21 sim 轮首收入对拍锁(开局金/首收入基线)。

对拍判据 = 「sim 开局金/首收入 vs 注册表直算值,同输入同输出,覆盖平局/
连胜/利息三通道」(设计依据 = docs/develop/sr_od/application/currency_war/
changes/2026-09-11-legacy-hygiene-ops/details/sim-baseline.md §T-21)。
权威源 = kernel/cw_economy.round_start_income 函数族(BoardState 设计
§4.2 轮首收入行「两域禁第二份」;真值凭据 = economy.md §10/§11)。

覆盖:
① 值分量全域对拍(sim_round_income × round_start_income;平局 streak=0 /
   连胜 streak>0 / 利息 cap+flat 三通道 × 息帽覆写族);
② base 平面感知键校准点锁(P1 r1/r2 常规/补给轮 3/4;P2r1/P3r1 hazard 回归);
③ 败补通道 ADR-0439 口径镜像(kernel 败补支 = 竞争口径待定谳 ADR-0623
   决策3,sim 常量修正随定谳,不属本锁语义);
④ 引擎息帽第二值源退役锁;
⑤ 端到端对拍:引擎默认局账本逐行 vs 注册表直算重算(进轮连胜按
   delta>0 重放,镜像 checks.runtime 精确重算锁口径;含开局金注入点锚);
⑥ win_reward_mult 接线锁(T-64):引擎注入局 e2e(伟大征服 ×3 施于
   连胜分量含奖励轮,fields.md §4.1)+ 账本行倍率披露经 checks.runtime
   镜像零违规(生产链锁)+ 镜像行键消费单元(缺键 = 接线前旧批次按
   1.0 重放兼容)。

挂账沿革:win_reward_mult 未入 sim 收入路径的 T-21 挂账已随 T-64 接线
闭合;①-⑤ 对拍路径仍一律 mult=1.0(缺省恒等,逐位等价)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_economy import (
    DEFAULT_INTEREST_CAP,
    LOSS_GOLD_BY_NODE,
    reward_base_gold,
    round_start_income,
    streak_gold,
)
from sr_od.application.currency_war.sim import engine_p1
from sr_od.application.currency_war.sim.engine_p1 import (
    sim_round_income,
    simulate_p1,
)

# 引擎节点词表(NODE_TYPE_POOL + P2 序;boss 含在战斗类)
_NODES: tuple[str, ...] = ('battle', 'encounter', 'boss', 'reward', 'supply')


# --- ① 值分量全域对拍(三通道;薄委托结构锁,防回退手算) ---


def test_income_row_matches_registry_full_domain() -> None:
    """同输入同输出:平面×轮×节点×连胜×金全域,值分量逐项相等。

    覆盖平局(streak=0,含 counter0=1 表值)/连胜(streak>0 查表)/
    利息(金库//10 封顶缺省帽)三通道。"""
    for plane in (1, 2):
        for rn in range(1, 10):
            for node in _NODES:
                for streak in (0, 1, 3, 6):
                    for gold in (0, 7, 55, 100):
                        got = sim_round_income(plane, rn, node, gold, streak)
                        exp = round_start_income(plane, rn, node, gold,
                                                 streak)
                        assert got == {'base': exp.base,
                                       'interest': exp.interest,
                                       'streak': exp.streak}, \
                            (plane, rn, node, streak, gold)


def test_income_row_cap_override_and_flat_channel() -> None:
    """利息通道:cap 经 interest_cap_resolved 归一(None→缺省帽;
    0 = 买断制有效覆写,禁真值折叠 ADR-0598)+ flat 与 cap 无关逐项相加
    (聚合单一源 = EconomyEffect.interest_flat_per_node)。"""
    for cap in (None, 9, 10, 0):
        for flat in (0, 2):
            got = sim_round_income(1, 5, 'battle', 100, 2,
                                   interest_flat=flat,
                                   interest_cap_override=cap)
            exp = round_start_income(1, 5, 'battle', 100, 2,
                                     interest_flat=flat, interest_cap=cap)
            assert got['interest'] == exp.interest, (cap, flat)
    assert sim_round_income(1, 5, 'battle', 100, 0,
                            interest_cap_override=0)['interest'] == 0, \
        '买断制 cap=0 被真值折叠回缺省(ADR-0598 陷阱在 sim 缝复潮)'
    assert sim_round_income(1, 5, 'battle', 100, 0)['interest'] \
        == DEFAULT_INTEREST_CAP, '无覆写须回落注册表缺省帽'


# --- ② base 平面感知键(T-21 校准行为点) ---


def test_base_plane_aware_key_calibration_points() -> None:
    """T-21 校准行为锁:P1 r1/r2 非奖励轮 base 3/4(原手搓段恒 5 =
    本批待校准差异);奖励轮查表同款;r3+ 恒 5;P2r1/P3r1=5(round
    单键直查 hazard 回归,BoardState §4.2 奖励轮行禁用形态)。"""
    assert sim_round_income(1, 1, 'battle', 0, 0)['base'] == 3
    assert sim_round_income(1, 2, 'encounter', 0, 0)['base'] == 4
    assert sim_round_income(1, 1, 'supply', 0, 0)['base'] == 3
    assert sim_round_income(1, 2, 'supply', 0, 0)['base'] == 4
    assert sim_round_income(1, 1, 'reward', 0, 0)['base'] == 3
    assert sim_round_income(1, 2, 'reward', 0, 0)['base'] == 4
    for rn in range(3, 10):
        assert sim_round_income(1, rn, 'battle', 0, 0)['base'] == 5, rn
    assert sim_round_income(2, 1, 'reward', 0, 0)['base'] == 5
    assert sim_round_income(2, 1, 'battle', 0, 0)['base'] == 5
    assert sim_round_income(3, 1, 'reward', 0, 0)['base'] == 5
    assert sim_round_income(3, 7, 'battle', 0, 0)['base'] == 5


# --- ③ 败补通道(ADR-0439 口径镜像;挂账口径不在此锁) ---


def test_loss_overlay_channel_adr0439_shape() -> None:
    """败补 = ADR-0439 口径:combat 轮进轮连胜 0 且上一战斗轮败 →
    连胜槽替换 LOSS_GOLD_BY_NODE[prev],base 仍按本轮平面键;奖励/
    补给轮不触发(引擎 elif 序:奖励/补给轮不发 LOSS_GOLD)。

    kernel 败补支 = 玩家裁定记录模型,与类型表的竞争口径判别数据不足
    (ADR-0623 决策3 待定谳)——sim 常量修正随定谳,本锁钉现口径。"""
    got = sim_round_income(1, 4, 'battle', 8, 0,
                           prev_node='encounter', prev_combat_lost=True)
    assert got['streak'] == LOSS_GOLD_BY_NODE['encounter']
    assert got['base'] == reward_base_gold(1, 4)
    # 奖励/补给轮:败态不触发(照各自分支语义)
    assert sim_round_income(1, 4, 'reward', 8, 0, prev_node='battle',
                            prev_combat_lost=True)['streak'] \
        == streak_gold(0)
    assert sim_round_income(1, 4, 'supply', 8, 0, prev_node='battle',
                            prev_combat_lost=True)['streak'] == 0
    # 连胜>0 或无败态 → 正常表值
    assert sim_round_income(1, 4, 'battle', 8, 2, prev_node='battle',
                            prev_combat_lost=True)['streak'] == streak_gold(2)
    assert sim_round_income(1, 4, 'battle', 8, 0)['streak'] == streak_gold(0)


# --- ④ 息帽第二值源退役 ---


def test_engine_module_interest_cap_single_source() -> None:
    """引擎模块不再定义裸 INTEREST_CAP=5(T-21 退役):缺省帽唯一源 =
    DEFAULT_INTEREST_CAP(派生自 cw_plane_table.GOLD_CAP_INTEREST//10,
    kernel「禁在本模块另写裸 5」纪律)。"""
    assert not hasattr(engine_p1, 'INTEREST_CAP')


# --- ⑤ 端到端对拍(引擎账本行 vs 注册表重算) ---


def test_engine_ledger_income_matches_registry_replay() -> None:
    """引擎默认局账本逐行 vs 注册表直算:值分量三分量逐行相等。

    进轮连胜重放 win 判据 = delta>0(镜像 checks.runtime 精确重算锁,
    与 sim 结算段逐位一致);败轮金覆写判据同锁(上一行战斗类且
    delta<=0)。开局金注入点锚 = P1 r1 gold_before=5(无独立注册表
    常量;轨迹级校准锚 = ADR-0447 反馈整定,靶边界见该表 docstring)。
    被动策略桩 + pool='fallback' = 快桶(收入公式与策略/Δ池无关)。"""
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        StrategySession,
    )

    class _PassiveStrategy:
        def decide_shop_screen(self, sess, cfg):  # noqa: ANN001
            return []

    res = simulate_p1(7, pool='fallback', strategy=_PassiveStrategy(),
                      session=StrategySession())
    rows = res.ledger
    assert rows, '账本空局不可作对拍载体'
    assert rows[0]['sim']['gold_before'] == 5, '开局金注入点漂移'
    # 进轮连胜重放(delta>0 战斗胜;镜像 checks.runtime)
    enter: dict[int, int] = {}
    running = 0
    for row in rows:
        enter[row.get('round_num') or 0] = running
        sim = row.get('sim') or {}
        if (sim.get('node') or '') in ('battle', 'encounter', 'boss'):
            running = running + 1 if (sim.get('delta') or 0) > 0 else 0
    prev: tuple[int, str, int] | None = None   # (rn, node, delta)
    for row in rows:
        sim = row['sim']
        rn = row.get('round_num') or 0
        inc = sim['income']
        enter_streak = enter.get(rn, 0)
        exp = round_start_income(1, rn, sim['node'], sim['gold_before'],
                                 enter_streak)
        exp_streak = exp.streak
        if (exp.branch == 'combat' and enter_streak == 0
                and prev is not None
                and prev[1] in LOSS_GOLD_BY_NODE and prev[2] <= 0):
            exp_streak = LOSS_GOLD_BY_NODE[prev[1]]
        assert inc['base'] == exp.base, (rn, sim['node'], 'base')
        assert inc['interest'] == exp.interest, (rn, sim['node'], 'interest')
        assert inc['streak'] == exp_streak, (rn, sim['node'], 'streak')
        assert 'invest' not in inc, '默认局无持卡,invest 键不应出现'
        prev = (rn, sim['node'], sim.get('delta') or 0)


# --- ⑥ win_reward_mult 接线(T-64;引擎半部 + 镜像行键消费) ---


def test_engine_win_reward_mult_wiring_end_to_end() -> None:
    """伟大征服 ×3 施于引擎连胜分量(fields.md §4.1「收入修饰」施于
    连胜分量含奖励轮;T-21 挂账「sim 修正随之」桶的接线闭合)。

    固定剧本 (1,1) 直注入(cw_sim_invest「显式点名 = 直注入」契约,
    不经 decide_invest):选卡落在当轮收入之后(实机同点)→ r1 行倍率
    1.0、自 r2 起行倍率 3.0;期望值按注册表现算(int(round(
    streak_gold×mult)),kernel _streak_component 同式),败补槽不乘
    (ADR-0439 类型表连胜槽替换)。被动策略桩 + pool='fallback' = 快桶。"""
    from sr_od.application.currency_war.sim.checks import runtime
    from sr_od.application.currency_war.sim.cw_sim_invest import (
        SimInvestProfile,
    )
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        StrategySession,
    )

    class _PassiveStrategy:
        def decide_shop_screen(self, sess, cfg):  # noqa: ANN001
            return []

    res = simulate_p1(
        7, pool='fallback', strategy=_PassiveStrategy(),
        session=StrategySession(),
        invest=SimInvestProfile(picks=((1, 1, '伟大征服'),)))
    rows = res.ledger
    assert rows, '账本空局不可作对拍载体'
    assert rows[0]['sim']['win_reward_mult'] == 1.0, \
        'r1 选卡落在收入后,当轮倍率须仍 1.0(实机同点)'
    assert any(r['sim']['win_reward_mult'] == 3.0 for r in rows[1:]), \
        '持 伟大征服 后无任何行携带 3.0 倍率(接线断/行披露缺)'
    # 进轮连胜重放(delta>0 战斗胜;分支序镜像 checks.runtime:
    # supply→reward→败补→常规)
    enter: dict[int, int] = {}
    running = 0
    for row in rows:
        enter[row.get('round_num') or 0] = running
        sim = row.get('sim') or {}
        if (sim.get('node') or '') in ('battle', 'encounter', 'boss'):
            running = running + 1 if (sim.get('delta') or 0) > 0 else 0
    prev: tuple[int, str, int] | None = None   # (rn, node, delta)
    for row in rows:
        sim = row['sim']
        rn = row.get('round_num') or 0
        inc = sim['income']
        mult = sim['win_reward_mult']
        enter_streak = enter.get(rn, 0)
        if sim['node'] == 'supply':
            exp_streak = 0
        elif sim['node'] == 'reward':
            exp_streak = int(round(streak_gold(enter_streak) * mult))
        elif (enter_streak == 0 and prev is not None
                and prev[1] in LOSS_GOLD_BY_NODE and prev[2] <= 0):
            exp_streak = LOSS_GOLD_BY_NODE[prev[1]]
        else:
            exp_streak = int(round(streak_gold(enter_streak) * mult))
        assert inc['streak'] == exp_streak, \
            (rn, sim['node'], mult, 'streak 未按当轮倍率重算')
        prev = (rn, sim['node'], sim.get('delta') or 0)
    # 镜像生产链锁(测试纪律 13 供给半环):行倍率经真实账本喂入
    # 精确重算锁——引擎行未披露或镜像未消费,本断言二选一红
    rep = runtime.check_streak_combat_only_income([rows])
    assert rep['violations'] == 0, rep


def test_runtime_mirror_consumes_row_mult_key() -> None:
    """镜像行键消费单元:``sim.win_reward_mult`` 施于奖励/常规槽;
    补给/败补槽不乘;缺键行 = 接线前旧批次按 1.0 折算(重放兼容,
    与旧口径逐位等价——非缺键守卫辖域)。负控 = 持倍率行按未乘表值
    入账 → 违规计 1(镜像对倍率失明即红)。"""
    from sr_od.application.currency_war.sim.checks import runtime

    def _row(rn: int, node: str, delta: int, streak: int,
             mult: float | None = None) -> dict:
        sim: dict = {'node': node, 'delta': delta,
                     'income': {'streak': streak, 'base': 0, 'interest': 0}}
        if mult is not None:
            sim['win_reward_mult'] = mult
        return {'round_num': rn, 'sim': sim}

    ledger = [
        # 旧批次行(缺键):常规槽按纯表值
        _row(1, 'battle', -3, streak_gold(0)),
        # 败补槽 = 类型表连胜槽替换,不乘 3.0
        _row(2, 'battle', -2, LOSS_GOLD_BY_NODE['battle'], 3.0),
        # 奖励/常规槽 ×3(含 counter0=1 表值同乘)
        _row(3, 'reward', 0, int(round(streak_gold(0) * 3.0)), 3.0),
        # 缺键行(旧批次)奖励槽按 1.0
        _row(4, 'reward', 0, streak_gold(0)),
        _row(5, 'supply', 0, 0, 3.0),
        _row(6, 'encounter', 2, int(round(streak_gold(0) * 3.0)), 3.0),
    ]
    rep = runtime.check_streak_combat_only_income([ledger])
    assert rep['violations'] == 0, rep
    # 负控:同一持倍率行按未乘表值入账 → 镜像必红
    bad = list(ledger)
    bad[5] = _row(6, 'encounter', 2, streak_gold(0), 3.0)
    rep_bad = runtime.check_streak_combat_only_income([bad])
    assert rep_bad['violations'] == 1, rep_bad
