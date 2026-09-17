"""节点边界金补结·精确吸收回归锁(2026-09-18 reconcile 事故第 3 例修复批 +
T-42 扩窗批:两腿收入结构与 unknown 量域闩)。

病理一(实机局 run_20260918_022233,安灯 hook:reconcile_mismatch 停局,
证据 = .debug/temp/incidents/20260918-reconcile/report.md §6;语义对帧,
禁引 .debug 路径):1-3 普通战斗胜利后,游戏侧在结算屏前入账节点边界
收入 +18(结算屏金面板读数 52 = 逻辑 34 + 18),但战斗结束到下一干净
备战帧之间的帧(过渡帧/店开态收起帧)不产 GameState 观察,边界金无
补结时点;首个备战帧 heavy 观察实读 gold=52 对逻辑 34(最后逻辑写端 =
proj_sell_deployed_gold)必然失配 → 统一观察对账安灯当推算 bug 停机。

病理二(T-42 扩窗依据,run_20260918_054257/055133 journal 定谳):奖励轮
胜局的边界收入可拆**两腿**到账——第一腿 = 结算后首个备战帧金观察
(+4/+5,当时金场源仍为观察态,静默采新),第二腿 = 店开帧金观察
(+2/+5,间隔着 bot 卖牌投影写)——T-21 单发闩被第一腿提前关窗,第二腿
照真失配停(两局安灯停局根因;T-40 报告「闩未置」系机制细节误判,闩实际
置位且被第一腿消费)。修法 = 闩升级量域三态 ``boundary_gold_mode``:
known = 结算屏金面板读成功(精确额窗,T-21 原形态:首观察就地补结后
关窗);unknown = 读失败(未知额度窗:正向差按差额吸收,行标注
unknown_settled,窗存续到店开帧金观察收口)。安灯停机语义零改动:窗外/
负向差照停,零差照旧不消费。

锁依据 = GameState.exec_books.boundary_gold_mode / boundary_gold_truth_seen
字段注释(两腿结构、窗口界定、双计防)+ GameState._absorb_boundary_gold
docstring 命中条件全列 + tick_effect_boundary 四重闸 docstring(闩在 ∧
窗内无真值观察才公式结算)。
改锁先重推语义:本锁钉的是「闩窗内吸收、窗外照停、观察优先于公式、
店开帧收口」四向,禁为保绿机械跟绿。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel import cw_mismatch_policy as _policy
from sr_od.application.currency_war.kernel.cw_game_state import (
    BOUNDARY_GOLD_MODE_KNOWN,
    BOUNDARY_GOLD_MODE_UNKNOWN,
    BOUNDARY_GOLD_NOTE_UNKNOWN_SETTLED,
    GAME_STATE_SCHEMA_VERSION,
    SCREEN_SHOP_PANEL,
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


def _obs_sig(screen: str = '货币战争-备战') -> ChannelSig:
    return ChannelSig(family='obs', actor='CwScreenPrep',
                      screen=screen, mode='read')


def _mk_gold_logic(gs: GameState, value: int = _LOGIC_GOLD) -> None:
    """逻辑金播种(事故帧同款写端证据;source = logic,失配比对生效)。"""
    gs.write_logic(gs.gold, value, produced_by='TestBoundaryWriter',
                   evidence='proj_sell_deployed_gold', sig=_logic_sig())


def _observe_capture(gs: GameState, value: int,
                     screen: str = '货币战争-备战') -> list[dict]:
    """gold 观察写入 + 缺陷行捕获(sink 挂载/卸载成对;安灯钩子由调用方
    monkeypatch 注入 _policy._ANDON_HOOK)。"""
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        gs.observe(gs.gold, value, sig=_obs_sig(screen))
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    return rows


# ============================================================ 补结主锁(T-42 两腿形态)


def test_unknown_latch_two_leg_income_absorbed(monkeypatch) -> None:
    """T-42 主锁(run_20260918_055133 迷你重放):结算屏金面板读失败
    (gold=None)→ unknown 量域闩 → 第一腿(备战帧 obs→obs 正向差 +4)
    按差额吸收落 unknown_settled 行、窗存续 → bot 卖牌投影(逻辑金 5→6)
    → 第二腿(店开帧实读对逻辑正向差 +5)吸收不停机、店开帧收口。

    锁:两腿各落 boundary_gold_backfilled 行且注 unknown_settled、零
    observe_vs_logic_mismatch、安灯不触发、窗最终关(None)、观察赢覆盖
    照常(逻辑金 = 实读真值)、公式水位不动。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.gold, 3, sig=_obs_sig())
    gs.observe(gs.node, NodeKey(plane=1, round_num=1, kind='reward'),
               sig=_obs_sig())
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        apply_settlement_cover(gs, hp_after=82, streak_after=0, killed=True,
                               progress_delta=2)   # 金面板读失败(gold 缺省 None)
        assert gs.exec_books.boundary_gold_mode \
            == BOUNDARY_GOLD_MODE_UNKNOWN, '读失败置 unknown 量域闩'
        assert gs.exec_books.boundary_gold_truth_seen is False

        gs.observe(gs.gold, 7, sig=_obs_sig())   # 第一腿(obs→obs 正向差)
        assert gs.exec_books.boundary_gold_mode \
            == BOUNDARY_GOLD_MODE_UNKNOWN, 'unknown 窗存续等第二腿(非店开帧)'
        assert gs.exec_books.boundary_gold_truth_seen is True, \
            '真值观察到达 = 公式腿禁发标记置位'

        gs.write_logic(gs.gold, 8, produced_by='TestBoundaryWriter',
                       evidence='proj_sell_refund', sig=_logic_sig())
        gs.write_logic(gs.gold, 9, produced_by='TestBoundaryWriter',
                       evidence='proj_sell_refund', sig=_logic_sig())

        gs.observe(gs.gold, 14, sig=_obs_sig(SCREEN_SHOP_PANEL))   # 第二腿
    finally:
        set_defect_sink(None)
        consume_defect_sink()

    assert gs.gold.value == 14, '两腿收入全部入账(观察赢覆盖照常)'
    assert gs.exec_books.boundary_gold_mode is None, '店开帧金观察过站即收口'
    assert gs.exec_books.boundary_gold_truth_seen is False, '收口连标记归零'
    assert [(r['kind'], r.get('note')) for r in rows] == [
        ('boundary_gold_backfilled', BOUNDARY_GOLD_NOTE_UNKNOWN_SETTLED),
        ('boundary_gold_backfilled', BOUNDARY_GOLD_NOTE_UNKNOWN_SETTLED)], \
        '两腿各落 unknown_settled 归因行(无真失配行)'
    assert fired == [], 'unknown 闩窗内正向差:安灯不触发'
    assert gs.boundary_settled_ord is None, '吸收不冒充公式结算水位'


def test_boundary_gold_backfilled_on_prep_observation(monkeypatch) -> None:
    """事故一主形态迷你重放(T-21 语义在 unknown 量域下回归):战斗结算
    (killed=None 残局首战形态)→ 效果段 killed 守卫跳过、闩存续 → 下一
    金观察实读 52 对逻辑 34 → 吸收不停机;窗非店开帧不收口(与单发闩的
    行为差:等店开帧或负差才关)。

    锁:boundary_gold_backfilled 行在案且注 unknown_settled、安灯不被调、
    覆盖照常(观察赢 = 补结落地,逻辑金 = 实读真值)、公式水位不动。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    _mk_gold_logic(gs)
    gs.observe(gs.node, NodeKey(plane=1, round_num=4, kind='battle'),
               sig=_obs_sig())
    gs.node_hist_ord = 4
    apply_settlement_cover(gs, hp_after=71, streak_after=0, killed=None)
    assert gs.exec_books.boundary_gold_mode == BOUNDARY_GOLD_MODE_UNKNOWN
    tick_effect_boundary(gs, prep_frame=True)   # killed=None 守卫跳过
    assert gs.exec_books.boundary_gold_mode == BOUNDARY_GOLD_MODE_UNKNOWN, \
        '守卫跳过不消费闩(等观察补结)'

    rows = _observe_capture(gs, _READ_GOLD)

    assert gs.gold.value == _READ_GOLD, '观察赢覆盖照常 = 补结落地'
    assert gs.exec_books.boundary_gold_mode == BOUNDARY_GOLD_MODE_UNKNOWN, \
        '非店开帧正向差窗存续(扩窗本体;店开帧/负差才收口)'
    assert [r['kind'] for r in rows] == ['boundary_gold_backfilled'], \
        '落 boundary_gold_backfilled 台账行(无真失配行,补结可审计)'
    assert rows[0].get('note') == BOUNDARY_GOLD_NOTE_UNKNOWN_SETTLED, \
        'unknown 量域吸收行带量域注记'
    assert fired == [], '闩窗内正向差:安灯不触发'
    assert gs.boundary_settled_ord is None, '吸收不落公式结算水位'


def test_boundary_gold_without_latch_still_stops(monkeypatch) -> None:
    """反腿:闩不在(无战斗结算覆盖,如备战期买入投影错值)同形状失配
    → 真失配照落照停。锁:吸收只认待补结闩,非金面全局放水。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    _mk_gold_logic(gs)
    assert gs.exec_books.boundary_gold_mode is None

    rows = _observe_capture(gs, _READ_GOLD)

    assert [r['kind'] for r in rows] == ['observe_vs_logic_mismatch']
    assert len(fired) == 1, '闩不在的真失配安灯照触发'


def test_boundary_gold_negative_delta_still_stops(monkeypatch) -> None:
    """形状守卫:闩在但实读低于逻辑(入账族不可负,负差 = 推算 bug 病灶
    形态)→ 真失配照落照停,吸收不吞(T-42 红线:负向差照旧语义)。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    _mk_gold_logic(gs)
    apply_settlement_cover(gs, hp_after=71, streak_after=0, killed=None)
    assert gs.exec_books.boundary_gold_mode is not None

    rows = _observe_capture(gs, _LOGIC_GOLD - 4)

    assert [r['kind'] for r in rows] == ['observe_vs_logic_mismatch']
    assert len(fired) == 1, '闩窗内负差照停(真投影 bug 不被吞)'


# ============================================================ known 路径回归


def test_settlement_cover_gold_parse_absorbs_in_place(monkeypatch) -> None:
    """known 精确额窗(T-21 原形态并存回归):结算屏金面板解析成功
    (实读 52 已含入账)→ 置 known 量域闩 → 补结在战斗结算点就地发生,
    行不带量域注记,首观察即关窗。"""
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
    assert [(r['kind'], r.get('note')) for r in rows] == \
        [('boundary_gold_backfilled', None)], \
        'known 精确额吸收行不带 unknown_settled 注记(量域分型可辨)'
    assert fired == []
    assert gs.exec_books.boundary_gold_mode is None, 'known 首观察即关窗'


def test_known_window_closed_positive_diff_still_stops(monkeypatch) -> None:
    """known 窗外照停(精确额语义边界):金面板读成功就地补结后,窗已关
    ——后续正向差(入账族形状但无窗申报)= 真失配照停,精确额窗不放水。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    _mk_gold_logic(gs)
    apply_settlement_cover(gs, hp_after=71, streak_after=0, killed=True,
                           gold=_READ_GOLD)
    assert gs.exec_books.boundary_gold_mode is None
    # 写端证据用 proj_buy_gold(备战帧 gold 的 proj_sell_refund 前缀在
    # EXEMPT_REGISTRY 有点球金豁免条目,会让本锁失真成 exempt 行)。
    gs.write_logic(gs.gold, _READ_GOLD - 1, produced_by='TestBoundaryWriter',
                   evidence='proj_buy_gold', sig=_logic_sig())

    rows = _observe_capture(gs, _READ_GOLD + 3)

    assert [r['kind'] for r in rows] == ['observe_vs_logic_mismatch']
    assert len(fired) == 1, 'known 窗已关的正向差照停'


# ============================================================ 窗过期与收口形状


def test_unknown_window_closes_at_shop_frame_equal_obs(monkeypatch) -> None:
    """过期锁·店开帧收口(只认帧位不认差值):unknown 窗存续中店开帧
    等值金观察过站即关窗——此后正向差照真失配停(防窗跨轮存活续吞)。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    _mk_gold_logic(gs)
    apply_settlement_cover(gs, hp_after=71, streak_after=0, killed=True)
    assert gs.exec_books.boundary_gold_mode == BOUNDARY_GOLD_MODE_UNKNOWN

    rows = _observe_capture(gs, _LOGIC_GOLD, screen=SCREEN_SHOP_PANEL)   # 等值

    assert rows == [], '等值观察零缺陷行'
    assert gs.exec_books.boundary_gold_mode is None, '店开帧过站收口(含等值)'
    gs.write_logic(gs.gold, _LOGIC_GOLD + 1, produced_by='TestBoundaryWriter',
                   evidence='proj_buy_gold', sig=_logic_sig())

    rows2 = _observe_capture(gs, _LOGIC_GOLD + 4)

    assert [r['kind'] for r in rows2] == ['observe_vs_logic_mismatch']
    assert len(fired) == 1, '收口后正向差照停(窗过期不放水)'


def test_unknown_window_negative_obs_closes_no_absorb(monkeypatch) -> None:
    """过期锁·负向差照旧消费语义(观察→观察形状):负差采新(观察赢)
    但关窗不续吞——后续正向差照真失配停。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.gold, _LOGIC_GOLD, sig=_obs_sig())   # 观察态 34
    apply_settlement_cover(gs, hp_after=71, streak_after=0, killed=True)
    assert gs.exec_books.boundary_gold_mode == BOUNDARY_GOLD_MODE_UNKNOWN

    rows = _observe_capture(gs, _LOGIC_GOLD - 2)   # 负差,obs→obs 采新

    assert rows == [], '观察→观察无失配比对可达,零缺陷行'
    assert gs.gold.value == _LOGIC_GOLD - 2, '观察赢采新'
    assert gs.exec_books.boundary_gold_mode is None, '负向差照旧消费语义关窗'
    gs.write_logic(gs.gold, _LOGIC_GOLD - 1, produced_by='TestBoundaryWriter',
                   evidence='proj_buy_gold', sig=_logic_sig())

    rows2 = _observe_capture(gs, _LOGIC_GOLD + 4)

    assert [r['kind'] for r in rows2] == ['observe_vs_logic_mismatch']
    assert len(fired) == 1, '关窗后正向差照停'


def test_unknown_window_zero_diff_keeps_open(monkeypatch) -> None:
    """过期锁·等值观察不消费不关窗(T-21「零新信息不误关窗」语义在
    unknown 量域下回归):窗存续等真值变化。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    _mk_gold_logic(gs)
    apply_settlement_cover(gs, hp_after=71, streak_after=0, killed=None)
    assert gs.exec_books.boundary_gold_mode == BOUNDARY_GOLD_MODE_UNKNOWN

    rows = _observe_capture(gs, _LOGIC_GOLD)   # 等值,备战帧

    assert rows == []
    assert gs.exec_books.boundary_gold_mode == BOUNDARY_GOLD_MODE_UNKNOWN, \
        '等值观察不关窗'
    assert gs.exec_books.boundary_gold_truth_seen is False, \
        '等值观察不置公式禁发标记'


# ============================================================ 双计防 + 公式腿


def test_observation_consumes_latch_formula_must_not_double_add(monkeypatch) -> None:
    """观察优先于公式(双计防):unknown 窗内金观察到达(实读真值已随
    覆盖入逻辑)后 truth_seen 置位,效果段公式结算必须禁发——否则真值 +
    公式值双计,下一观察必失配(run_20260918_022233 公式 +5 vs 真差 +4
    同族)。窗存续(truth_seen 扩窗后的第二重闸,单看 mode 不再充分)。"""
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
    assert gs.exec_books.boundary_gold_mode == BOUNDARY_GOLD_MODE_UNKNOWN, \
        '非店开帧正向差窗存续'
    assert gs.exec_books.boundary_gold_truth_seen is True

    tick_effect_boundary(gs, prep_frame=True)

    assert gs.gold.value == _READ_GOLD, 'truth_seen 置位,公式禁叠算(防双计)'
    assert gs.boundary_settled_ord is None, '无公式结算即无水位'


def test_formula_settlement_normal_path_unaffected() -> None:
    """公式腿正常路径回归(事故局 01:27:23 健康形态):战斗结算置 unknown
    闩后金读 carried(无观察到达,truth_seen 未置)→ 备战帧公式结算照常
    发生、落水位、消费闩;结算后同值观察零缺陷行零安灯(公式欠准时才由
    真失配显影,语义不变)。"""
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
    assert gs.exec_books.boundary_gold_mode == BOUNDARY_GOLD_MODE_UNKNOWN, \
        '结算覆盖置 unknown 闩'

    tick_effect_boundary(gs, prep_frame=True)

    expected = 30 + round_start_income(2, 3, 'battle', 30, 2).total
    assert gs.gold.value == expected, '公式结算照常(carried 腿补结)'
    assert gs.boundary_settled_ord == 12, '水位照落'
    assert gs.exec_books.boundary_gold_mode is None, '公式结算消费闩'
    assert gs.exec_books.boundary_gold_truth_seen is False

    rows = _observe_capture(gs, expected)

    assert rows == [], '结算后同值观察:零缺陷行(不受补结机制影响)'


def test_formula_settled_window_positive_diff_still_stops(monkeypatch) -> None:
    """过期锁·公式腿消费后窗关(公式欠准显影语义):carried 腿公式结算
    消费闩后,后续正向差(公式欠准形态)照真失配停——不被窗吞(T-21
    「公式欠准由观察显影」红线在扩窗形态下保持)。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.gold, 30, sig=_obs_sig())
    gs.observe(gs.streak, 2, sig=_obs_sig())
    gs.observe(gs.node, NodeKey(plane=2, round_num=3, kind='battle'),
               sig=_obs_sig())
    gs.node_hist_ord = 12
    apply_settlement_cover(gs, hp_after=76, streak_after=2, killed=True)
    tick_effect_boundary(gs, prep_frame=True)
    assert gs.exec_books.boundary_gold_mode is None, '公式结算消费闩'

    rows = _observe_capture(gs, gs.gold.value + 3)

    assert [r['kind'] for r in rows] == ['observe_vs_logic_mismatch']
    assert len(fired) == 1, '公式结算后的正向差照停(欠准显影不被吞)'
