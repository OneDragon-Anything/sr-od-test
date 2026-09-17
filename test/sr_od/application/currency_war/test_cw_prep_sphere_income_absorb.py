"""备战环随机收入(点球金)吸收回归锁(20260918-reconcile 第 9 例收口)。

病理(实机局 run_20260918_071019,journal v40/v43→v46):奖励节点备战帧
点球 2 个,球金 +6 由游戏侧异步入账;备战帧卖牌退款投影(proj_sell_refund
3→4→5)在下一可信金读帧(店开帧 heavy 观察,screen = 货币战争-备战-开
商店,F2 gold 仅 shop 开态可信)被证伪(实读 11 对逻辑 5)→ 安灯停局。
豁免注册表条目 ('货币战争-备战','gold')×proj_sell_refund 的 screen 维
锚在备战屏而金真值只在店开帧读 → 三维护航结构性落空;且点球金金额执行
点不可推算(实机样本 +4/+7/+6 无界,data 注册表无数值表),设计上无逻辑
写端——豁免表按「写端前缀」申报表达不了「无写端外部收入」形状。

修法 = 申报窗(ExecBooks.prep_sphere_income_pending,apply_op_effect
ClickSpheres 分支按载荷球数开窗)+ observe() 失配分支正向差精确吸收
(prep_sphere_income_absorbed)+ 店开帧收口(照 bench 申报表族形态)。

锁依据 = ExecBooks.prep_sphere_income_pending 字段注释的吸收语义与红线
(未申报/负差/店开帧后照停)+ GameState._absorb_prep_sphere_income
docstring 命中条件全列。改锁先重推语义,禁为保绿机械跟绿。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel import (
    cw_mismatch_policy as _policy,
)
from sr_od.application.currency_war.kernel.cw_exec_state import (
    apply_op_effect,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    SCREEN_SHOP_PANEL,
    ChannelSig,
    GameState,
    consume_defect_sink,
    game_state_of,
    register_sig_actors,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    ClickSpheres,
    DeployMove,
)

register_sig_actors('TestSphereWriter')

#: 事故帧实录形(run_20260918_071019 v46):退款投影后逻辑金 5,店开帧
#: 实读 11 = 两球随机收入 +6。语义对帧,禁引 .debug 路径。
_LOGIC_GOLD: int = 5
_READ_GOLD: int = 11


def _logic_sig() -> ChannelSig:
    return ChannelSig(family='logic_action', actor='TestSphereWriter',
                      mode='compute')


def _shop_obs_sig() -> ChannelSig:
    return ChannelSig(family='obs', actor='CwScreenPrep',
                      screen=SCREEN_SHOP_PANEL, mode='read',
                      quality={'gold': 'real_read'})


def _seed_logic_gold(gs: GameState, value: int = _LOGIC_GOLD) -> None:
    """退款投影后的逻辑金基线(写端 evidence 同事故帧 = proj_sell_refund)。"""
    gs.write_logic(gs.gold, value, produced_by='TestSphereWriter',
                   evidence='proj_sell_refund', sig=_logic_sig())


def _observe_gold(gs: GameState, value: int) -> list[dict]:
    """店开帧金观察 + 缺陷行捕获(sink 挂载/卸载成对;安灯钩子由调用方
    monkeypatch 注入 _policy._ANDON_HOOK)。"""
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        gs.observe(gs.gold, value, sig=_shop_obs_sig())
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    return rows


# ============================================================ 吸收主锁


def test_sphere_income_absorbed_at_shop_panel(monkeypatch) -> None:
    """事故主形态:窗开(点球 2 个)+ 实读正向差 +6 → 吸收不停机。

    锁:无 observe_vs_logic_mismatch 行、安灯不被调、
    prep_sphere_income_absorbed 行在案(豁免 ≠ 消失)、窗清零、
    覆盖照常(观察赢,gold = 实读 11)。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    _seed_logic_gold(gs)
    gs.exec_books.prep_sphere_income_pending = 2

    rows = _observe_gold(gs, _READ_GOLD)

    assert gs.gold.value == _READ_GOLD, '观察赢覆盖照常'
    assert gs.exec_books.prep_sphere_income_pending == 0, '吸收后窗清零'
    assert [r['kind'] for r in rows] == ['prep_sphere_income_absorbed'], \
        '落 prep_sphere_income_absorbed 台账行(无真失配行,可审计)'
    assert fired == [], '申报窗内正向差:安灯不触发'


def test_sphere_income_without_window_still_stops(monkeypatch) -> None:
    """反腿·未申报:窗关(没点过球)时同形状实读 → 真失配照落照停。

    锁:吸收只认执行申报窗,非全局放水——gold 失配默认处置不变。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    _seed_logic_gold(gs)
    assert gs.exec_books.prep_sphere_income_pending == 0

    rows = _observe_gold(gs, _READ_GOLD)

    assert [r['kind'] for r in rows] == ['observe_vs_logic_mismatch']
    assert len(fired) == 1, '未申报的真失配安灯照触发'


def test_sphere_income_negative_diff_still_stops(monkeypatch) -> None:
    """反腿·负差:窗开但实读不升(退款投影虚高类病灶形态)→ 照停。

    收入不可负,负差 = 推算 bug 不被吞(安灯停机语义零改动)。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    _seed_logic_gold(gs)
    gs.exec_books.prep_sphere_income_pending = 2

    rows = _observe_gold(gs, 4)

    assert [r['kind'] for r in rows] == ['observe_vs_logic_mismatch']
    assert len(fired) == 1, '负差交回三分流照停'
    assert gs.exec_books.prep_sphere_income_pending == 0, \
        '店开帧 = 窗末站,评估(含照停)后照常收口——后续正向差不续吞'


def test_sphere_income_window_closes_at_shop_panel(monkeypatch) -> None:
    """收口锁:店开帧金观察 = 窗末站(等值观察亦收口),窗不跨读存续。

    病理防线:虚额残留窗若不收口,后续任意正向失配(含买落空类真投影
    bug)会被误吸收——同外部授予闩窗口上界纪律。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    _seed_logic_gold(gs)
    gs.exec_books.prep_sphere_income_pending = 2

    rows = _observe_gold(gs, _LOGIC_GOLD)   # 等值观察(球金 0/点击落空形态)

    assert rows == [], '等值观察无失配无吸收行'
    assert gs.exec_books.prep_sphere_income_pending == 0, \
        '店开帧金观察收口(末站),窗不跨读存续'

    # 收口后同帧位正向差照真失配停(窗不再吞)。
    gs.write_logic(gs.gold, 10, produced_by='TestSphereWriter',
                   evidence='proj_sell_refund', sig=_logic_sig())
    rows2 = _observe_gold(gs, 13)

    assert [r['kind'] for r in rows2] == ['observe_vs_logic_mismatch']
    assert len(fired) == 1, '收口后的正向差不再被吸收'


# ============================================================ 置位端(申报点)


def test_apply_op_effect_clickspheres_opens_window() -> None:
    """置位端:ClickSpheres 执行发出按载荷球数开窗,多批累加;非点球
    动作零影响。零推进语义不变(金账不写,只开窗)。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    assert gs.exec_books.prep_sphere_income_pending == 0

    apply_op_effect(session, ClickSpheres(points=((100, 200), (300, 400))))
    assert gs.exec_books.prep_sphere_income_pending == 2, '按载荷球数开窗'

    apply_op_effect(session, ClickSpheres(points=((500, 600),)))
    assert gs.exec_books.prep_sphere_income_pending == 3, '多批执行累加'

    apply_op_effect(session, DeployMove(bench_idx=0, to_row='front',
                                        faction='公司'))
    assert gs.exec_books.prep_sphere_income_pending == 3, \
        '非点球动作零影响'
