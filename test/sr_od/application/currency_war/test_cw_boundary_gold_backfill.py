"""节点边界金补结·精确吸收回归锁(2026-09-18 reconcile 事故第 3 例修复批)。

病理(实机局 run_20260918_022233,安灯 hook:reconcile_mismatch 停局,
证据 = .debug/temp/incidents/20260918-reconcile/report.md §6;语义对帧,
禁引 .debug 路径):1-3 普通战斗胜利后,游戏侧在结算屏前入账节点边界
收入 +18(结算屏金面板读数 52 = 逻辑 34 + 18),但战斗结束到下一干净
备战帧之间的帧(过渡帧/店开态收起帧)不产 GameState 观察,边界金无
补结时点;首个备战帧 heavy 观察实读 gold=52 对逻辑 34(最后逻辑写端 =
proj_sell_deployed_gold)必然失配 → 统一观察对账安灯当推算 bug 停机。
机制本身(战斗结算窗内游戏侧入账)不是推算 bug,是「游戏侧状态变更未
投影进逻辑态」同架构类第 3 例:修法 = 边界事件持久化——结算屏真值覆盖
写端置待补结闩(exec_books.boundary_gold_pending),任一 gold 观察到达
即消费;失配形状(闩窗内正向差)落 boundary_gold_backfilled 台账行后
覆盖照常 = 补结落地,闩不在(未申报窗)照真失配停,安灯停机语义零改动。

锁依据 = GameState.exec_books.boundary_gold_pending 字段注释(窗口界定:
战斗结算 → 下一金观察之间无 bot 金动作,窗内金差只可能来自游戏侧入账)
+ GameState._absorb_boundary_gold docstring 命中条件全列 +
tick_effect_boundary 三重闸 docstring(闩消费后公式结算禁叠算防双计)。
改锁先重推语义:本锁钉的是「闩窗内吸收、窗外照停、观察优先于公式」
三向,禁为保绿机械跟绿。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel import cw_mismatch_policy as _policy
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    NodeKey,
    apply_settlement_cover,
    consume_defect_sink,
    register_sig_actors,
    set_defect_sink,
    tick_effect_boundary,
)

register_sig_actors('TestBoundaryWriter')

#: 事故帧实录制:战斗前卖上场牌投影后的逻辑金(最后逻辑写端 =
#: proj_sell_deployed_gold,与两起实机停局缺陷行同款)。
_LOGIC_GOLD: int = 34
#: 下一备战帧实读 = 逻辑 34 + 边界收入 18(1-3 普通战斗节点边界收入)。
_READ_GOLD: int = 52


def _logic_sig() -> ChannelSig:
    return ChannelSig(family='logic_action', actor='TestBoundaryWriter',
                      mode='compute')


def _obs_sig() -> ChannelSig:
    return ChannelSig(family='obs', actor='CwScreenPrep',
                      screen='货币战争-备战', mode='read')


def _mk_gold_logic(gs: GameState, value: int = _LOGIC_GOLD) -> None:
    """逻辑金播种(事故帧同款写端证据;source = logic,失配比对生效)。"""
    gs.write_logic(gs.gold, value, produced_by='TestBoundaryWriter',
                   evidence='proj_sell_deployed_gold', sig=_logic_sig())


def _observe_capture(gs: GameState, value: int) -> list[dict]:
    """gold 观察写入 + 缺陷行捕获(sink 挂载/卸载成对;安灯钩子由调用方
    monkeypatch 注入 _policy._ANDON_HOOK)。"""
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        gs.observe(gs.gold, value, sig=_obs_sig())
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    return rows


# ============================================================ 补结主锁


def test_boundary_gold_backfilled_on_prep_observation(monkeypatch) -> None:
    """事故主形态迷你重放:战斗结算(killed=None 残局首战形态)→ 效果段
    killed 守卫跳过、闩存续 → 下一金观察实读 52 对逻辑 34 → 吸收不停机。

    锁:无 observe_vs_logic_mismatch 行、安灯不被调、
    boundary_gold_backfilled 行在案(补结可验证 = 台账行)、闩消费、
    覆盖照常(观察赢 = 补结落地,逻辑金 = 实读真值)、公式水位不动
    (吸收不冒充公式结算水位)。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    _mk_gold_logic(gs)
    gs.observe(gs.node, NodeKey(plane=1, round_num=4, kind='battle'),
               sig=_obs_sig())
    gs.node_hist_ord = 4
    apply_settlement_cover(gs, hp_after=71, streak_after=0, killed=None)
    assert gs.exec_books.boundary_gold_pending, '结算覆盖置待补结闩'
    tick_effect_boundary(gs, prep_frame=True)   # killed=None 守卫跳过
    assert gs.exec_books.boundary_gold_pending, '守卫跳过不消费闩(等观察补结)'

    rows = _observe_capture(gs, _READ_GOLD)

    assert gs.gold.value == _READ_GOLD, '观察赢覆盖照常 = 补结落地'
    assert gs.exec_books.boundary_gold_pending is False, '金观察到达闩即消费'
    assert [r['kind'] for r in rows] == ['boundary_gold_backfilled'], \
        '落 boundary_gold_backfilled 台账行(无真失配行,补结可审计)'
    assert fired == [], '闩窗内正向差:安灯不触发'
    assert gs.boundary_settled_ord is None, '吸收不落公式结算水位'


def test_boundary_gold_without_latch_still_stops(monkeypatch) -> None:
    """反腿:闩不在(无战斗结算覆盖,如备战期买入投影错值)同形状失配
    → 真失配照落照停。锁:吸收只认待补结闩,非金面全局放水。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    _mk_gold_logic(gs)
    assert gs.exec_books.boundary_gold_pending is False

    rows = _observe_capture(gs, _READ_GOLD)

    assert [r['kind'] for r in rows] == ['observe_vs_logic_mismatch']
    assert len(fired) == 1, '闩不在的真失配安灯照触发'


def test_boundary_gold_negative_delta_still_stops(monkeypatch) -> None:
    """形状守卫:闩在但实读低于逻辑(入账族不可负,负差 = 推算 bug 病灶
    形态)→ 真失配照落照停,吸收不吞。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    _mk_gold_logic(gs)
    apply_settlement_cover(gs, hp_after=71, streak_after=0, killed=None)
    assert gs.exec_books.boundary_gold_pending

    rows = _observe_capture(gs, _LOGIC_GOLD - 4)

    assert [r['kind'] for r in rows] == ['observe_vs_logic_mismatch']
    assert len(fired) == 1, '闩窗内负差照停(真投影 bug 不被吞)'


def test_settlement_cover_gold_parse_absorbs_in_place(monkeypatch) -> None:
    """置位先于覆盖序:结算屏金面板解析成功(实读 52 已含入账,事故局
    同值)时,补结在战斗结算点就地发生,不待下一备战帧。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    _mk_gold_logic(gs)

    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        apply_settlement_cover(gs, hp_after=71, streak_after=0, killed=True,
                               gold=_READ_GOLD)
    finally:
        set_defect_sink(None)
        consume_defect_sink()

    assert gs.gold.value == _READ_GOLD, '结算点就地补结(观察赢)'
    assert [r['kind'] for r in rows] == ['boundary_gold_backfilled']
    assert fired == []
    assert gs.exec_books.boundary_gold_pending is False, '本观察即消费闩'


# ============================================================ 双计防 + 正常路径回归


def test_observation_consumes_latch_formula_must_not_double_add(monkeypatch) -> None:
    """观察优先于公式:闩窗内金观察到达(实读真值已随覆盖入逻辑)后,
    效果段公式结算必须禁发——否则真值 + 公式值双计,下一观察必失配。
    (镜像/连胜/胜局守卫全在场,证闸 = 待补结闩本身。)"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.gold, 30, sig=_obs_sig())
    gs.observe(gs.streak, 2, sig=_obs_sig())
    gs.observe(gs.node, NodeKey(plane=2, round_num=3, kind='battle'),
               sig=_obs_sig())
    gs.node_hist_ord = 12
    apply_settlement_cover(gs, hp_after=76, streak_after=2, killed=True)
    gs.observe(gs.gold, _READ_GOLD, sig=_obs_sig())   # 实读真值静默覆盖
    assert gs.exec_books.boundary_gold_pending is False

    tick_effect_boundary(gs, prep_frame=True)

    assert gs.gold.value == _READ_GOLD, '闩已被观察消费,公式禁叠算(防双计)'
    assert gs.boundary_settled_ord is None, '无公式结算即无水位'


def test_formula_settlement_normal_path_unaffected() -> None:
    """正常路径回归(事故局 01:27:23 健康形态):战斗结算置闩后金读
    carried(无观察到达)→ 备战帧公式结算照常发生、落水位、消费闩;
    结算后同值观察零缺陷行零安灯(公式欠准时才由真失配显影,语义不变)。"""
    from sr_od.application.currency_war.kernel.cw_economy import (
        round_start_income,
    )
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.gold, 30, sig=_obs_sig())
    gs.observe(gs.streak, 2, sig=_obs_sig())
    gs.observe(gs.node, NodeKey(plane=2, round_num=3, kind='battle'),
               sig=_obs_sig())
    gs.node_hist_ord = 12
    apply_settlement_cover(gs, hp_after=76, streak_after=2, killed=True)
    assert gs.exec_books.boundary_gold_pending, '结算覆盖置闩'

    tick_effect_boundary(gs, prep_frame=True)

    expected = 30 + round_start_income(2, 3, 'battle', 30, 2).total
    assert gs.gold.value == expected, '公式结算照常(carried 腿补结)'
    assert gs.boundary_settled_ord == 12, '水位照落'
    assert gs.exec_books.boundary_gold_pending is False, '公式结算消费闩'

    rows = _observe_capture(gs, expected)

    assert rows == [], '结算后同值观察:零缺陷行(不受补结机制影响)'
