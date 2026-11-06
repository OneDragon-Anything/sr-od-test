"""sim 策略尾款金腿测试(镜像 src = sim/cw_sim_backend.py 的
strategy_final_supply_gold_of 聚合 helper + _begin_node_window 收尾
「最后一个补给阶段」金腿;同族先例 = 本目录 test_strategy_boss_gold.py)。

测试面依据 = 迭代设计 designs/T-93-weikuan-jiaofu.md §2.3/§2.5/§4
十一锁面(锁 1-8),例值按现表重派生(锚点 = 展平全序列最末 supply 位,
默认表现值 (3,3);P3 入表后域扩展自动跟随):
- 锚点发放真值(锁 1/7/8):(3,3) 窗金增量 = 轮首收入面(kernel 公式
  现算,supply 支 base+息,禁只断言 +30)+ 30,独立观察笔(evidence 与
  收入笔分键,收入三分量账不混入);同节点窗重放零双发(幂等守卫复用);
- 非锚 supply 零发放(锁 2,「全局一次」辖域行为锁)/ 非 supply 节点
  零发放(锁 3)/ 未持卡零发放(锁 4);
- 修饰局锚点跟随(锁 5,期望由 resolve_plane_node_seqs 程序化派生,
  非硬编码);
- 拿卡当节点不发放(锁 6,窗口前段聚合读时序机制锁——直构「同窗晚到
  手」状态容器态,不假设场景可达:现行建模域 offer 槽域与 supply 零重合)。

复用声明:引擎驱动助手 import 自 sim/test_sim_backend.py(已登记超限
拆分债文件,禁追加,只 import 复用不改;先例 = 本目录
test_strategy_boss_gold.py)。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import cw4_box
from test.sr_od.application.currency_war.sim.cw_sim_backend.test_p3_win_terminal import (
    _drive_step,
)
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
    _SIG_OBS,
)

from sr_od.application.currency_war.kernel.cw_economy import (
    round_start_income,
)
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SCREEN_INVEST_ENV,
    SCREEN_PREP,
    SimBackend,
    income_modifiers_of,
    install_backend,
    strategy_final_supply_gold_of,
    strategy_invest_node_gold_of,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_CARD = '尾款交付'
_MOD_ENV = '人身意外险'

#: 尾款金独立笔 evidence(sim 写统一前缀 + 写点 tag,单一源 =
#: sim_evidence;写点形态 = strategy:final_supply_gold:p{位面}r{轮})。
_GOLD_EV_PREFIX = 'sim:engine:strategy:final_supply_gold:p'


def _backend(seed: int = 37, *, env_name: str = '') -> SimBackend:
    """装配后端至 P1r1 备战屏(env_name 非空走投资环境屏选环境流——改
    节点序列经环境注册写场字段 ``node_seq_by_plane``,直写状态容器不触;
    装配形态先例 = test_strategy_boss_gold._backend;seed 37 = P3 全程
    存活探针锚,先例 = 本目录 test_p3_win_terminal)。调用方负责
    uninstall。"""
    from sr_od.application.currency_war.kernel.cw_action_report import (
        report_action_pick_invest_env_param,
    )
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108,
        env_present=bool(env_name)))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    if env_name:
        assert b.screen_identity() == SCREEN_INVEST_ENV
        b.gs.write_logic(b.gs.invest_env_opts,
                         [env_name, '轮岗', '头彩'],
                         produced_by='Test', evidence='t:opts', sig=_SIG)
        out = report_action_pick_invest_env_param(
            b.gs, SimpleNamespace(idx=0), _SIG)
        assert out.applied
        cw_sim_ports.declare_world(out.world_decl)
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP
    return b


def _hold(b: SimBackend, names: list[str]) -> None:
    """持卡直种(测试种子纪律:生产写端 = 获得链,观察直种先例 =
    test_strategy_boss_gold._hold)。"""
    b.gs.observe(b.gs.active_strategies, names,
                 evidence='test:hold', sig=_SIG_OBS)


def _drive_until_pos(b: SimBackend, pos: tuple[int, int],
                     limit: int = 512) -> None:
    """步进驱动至节点序位(超限响错防死循环;单步助手 =
    test_p3_win_terminal._drive_step——位面过渡屏在其分派表内,
    test_sim_backend._drive_env_grant_step 无该档,达 P3 必经;先例 =
    test_env_pick_grant_sim_chain._drive_until_pos)。"""
    for _ in range(limit):
        if b._node_pos() == pos:
            return
        _drive_step(b, 37)
    raise AssertionError('驱动步数超限,谓词未达成')


def test_final_supply_gold_leg_via_engine_window() -> None:
    """锚点发放真值(锁 1/7/8,单局串联):(3,2) 战斗窗捕获收入面输入
    (金 = (3,2) 收入落账后现值 = (3,3) 息算基数;连胜变化在 (3,2) 结算
    刻落账、supply 轮不动连胜,(3,3) 窗开同值)→ (3,3) 窗独立笔
    evidence 分键 + 窗金增量 = 收入面(kernel 公式现算)+30(锁值含收入
    分量,禁只断言 +30)→ 同节点窗重放零双发。"""
    b = _backend()
    try:
        gs = b.gs
        _hold(b, [_CARD])
        _drive_until_pos(b, (3, 2))
        g2 = int(gs.gold.value or 0)
        _drive_until_pos(b, (3, 3))
        # 锁 1/8 独立笔:evidence 与收入笔分键(若并入收入写则留 income 键)
        assert gs.gold.evidence == _GOLD_EV_PREFIX + '3r3', \
            f'锚点窗独立笔缺或来源漂移: {gs.gold.evidence}'
        s3 = max(int(gs.streak.value or 0), 0)
        mult, flat, cap = income_modifiers_of(gs)
        # 本局途中经获得链到手的每节点金卡(如按劳分配,固定 seed 采样
        # 池现值)使窗开先落一笔 invest 分量(腿骑聚合,收入段最前)——
        # 收入面息基数 = 窗开金 = g2 + invest(g2 捕获于上一窗后,窗间
        # 无其他金写),invest 程序化现算非硬编码
        invest = strategy_invest_node_gold_of(gs)
        income = round_start_income(
            3, 3, 'supply', g2 + invest, s3, win_reward_mult=mult,
            interest_flat=flat, interest_cap=cap).total
        assert gs.gold.value == g2 + income + invest + 30, \
            f'窗金增量 ≠ invest+收入面+30: ' \
            f'{g2}+{invest}+{income}+30 vs {gs.gold.value}'
        # 锁 7 幂等回归:同节点窗重放,守卫住整段收尾零双发
        gold_at_anchor = gs.gold.value
        b._begin_node_window()
        assert gs.gold.value == gold_at_anchor \
            and gs.gold.evidence == _GOLD_EV_PREFIX + '3r3', \
            f'同窗重放双发或来源漂移: {gold_at_anchor} vs {gs.gold.value}'
    finally:
        uninstall_backend()


def test_non_anchor_supply_and_battle_windows_zero_grant() -> None:
    """非锚 supply 零发放(锁 2,「全局一次」辖域行为锁)+ 非 supply
    节点零发放(锁 3):(1,5)(默认局 P1 supply,非末位)与 (3,4)
    (锚点后继 battle)窗后无尾款独立笔,金来源 = 收入笔。"""
    b = _backend()
    try:
        gs = b.gs
        _hold(b, [_CARD])
        _drive_until_pos(b, (1, 5))
        assert gs.gold.evidence == 'sim:engine:income:p1r5', \
            f'非锚 supply 窗出现尾款笔: {gs.gold.evidence}'
        _drive_until_pos(b, (3, 4))
        assert gs.gold.evidence == 'sim:engine:income:p3r4', \
            f'锚点后继 battle 窗出现尾款笔: {gs.gold.evidence}'
    finally:
        uninstall_backend()


def test_no_final_supply_gold_without_card() -> None:
    """未持卡零发放(锁 4):锚点窗金来源 = 收入笔(聚合 0 → 零值零写)。"""
    b = _backend()
    try:
        gs = b.gs
        _drive_until_pos(b, (3, 3))
        assert gs.gold.evidence == 'sim:engine:income:p3r3', \
            f'未持卡局出现尾款笔: {gs.gold.evidence}'
    finally:
        uninstall_backend()


def test_modified_env_anchor_follows_field() -> None:
    """修饰局锚点跟随(锁 5):期望由 ``resolve_plane_node_seqs('人身
    意外险')`` 程序化派生(不硬编码轮次)——派生末 supply 位发放,该表
    其余 supply 位零发放(逐位过窗断言)。seed 93 = 修饰局全程存活探针
    锚(默认局存活锚 37 在修饰局 hp 轨迹移位下 P3r1 战死,不可达锚点
    (3,7);sim 战斗 = p0.5 固定随机,存活性与持卡无关,种子即存活
    判定量)。"""
    b = _backend(seed=93, env_name=_MOD_ENV)
    try:
        gs = b.gs
        _hold(b, [_CARD])
        seqs = gs.node_seq_by_plane.value
        supplies = sorted((p, r) for p, seq in (seqs or {}).items()
                          for r, kind in enumerate(seq, 1)
                          if kind == 'supply')
        anchor = supplies[-1]
        assert anchor == (3, 7), f'修饰局锚点现值漂移: {anchor}'
        for pos in supplies[:-1]:
            _drive_until_pos(b, pos)
            assert gs.gold.evidence == f'sim:engine:income:p{pos[0]}r{pos[1]}', \
                f'非锚 supply {pos} 出现尾款笔: {gs.gold.evidence}'
        _drive_until_pos(b, anchor)
        assert gs.gold.evidence == _GOLD_EV_PREFIX + f'{anchor[0]}r{anchor[1]}', \
            f'修饰局发放位未随场字段现值: {gs.gold.evidence}'
    finally:
        uninstall_backend()


def test_same_window_pickup_after_front_segment_no_grant(monkeypatch) -> None:
    """拿卡当节点不发放(锁 6,机制锁·直构形态,不假设场景可达):直构
    「窗口前段聚合读之后、同窗收尾段才到手」的状态容器态(生产时序 = 选卡
    确认是 offer 呈现后的玩家动作,恒晚于窗口前段聚合读)→ 该窗零发放。
    注入点 = 商店全刷(收尾段位 = 收入→…→尾款金→商店全刷;若未来实现
    把腿移到 offer 呈现之后,同窗到手先于聚合读,本锁红)。"""
    import sr_od.application.currency_war.sim.cw_sim_backend as sb

    b = _backend()
    try:
        gs = b.gs
        orig_deal_shop = sb.deal_shop

        def _late_pick_deal(g, rng, *, level, probs, tag):
            if b._node_pos() == (3, 3):
                g.observe(g.active_strategies, [_CARD],
                          evidence='test:late_pick', sig=_SIG_OBS)
            orig_deal_shop(g, rng, level=level, probs=probs, tag=tag)

        monkeypatch.setattr(sb, 'deal_shop', _late_pick_deal)
        _drive_until_pos(b, (3, 3))
        assert gs.gold.evidence == 'sim:engine:income:p3r3', \
            f'同窗晚到手触发尾款笔(时序机制破): {gs.gold.evidence}'
    finally:
        uninstall_backend()


def test_strategy_final_supply_gold_aggregation_matrix() -> None:
    """聚合数值直构(状态容器锁聚合数学):尾款交付 = 30、未持 = 0
    (数值 = 卡面真值字面锁;0 = 零值零写前提)。helper 锚域单元锁 =
    kernel/test_node_pos_primitive.py(锁 10,不在此重复)。"""
    assert strategy_final_supply_gold_of(cw4_box(
        active_strategies=(_CARD,))) == 30
    assert strategy_final_supply_gold_of(cw4_box()) == 0
