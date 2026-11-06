"""策略卡战后触发发放 sim 状态副本链测试(镜像 src = sim/cw_sim_backend.py
的 _resolve_battle 只供策略算分的实现分支;kernel 触发函数单元面 =
kernel/cw_gain_chain/test_check_strategy_battle_grants.py,本文件锁
sim 结算腿接入调用与状态副本里的值落地面)。

测试面依据 = 迭代设计 designs/T-105-yizhan-yangzhan.md §4 锁 1/2/3/4/5/8:
- 持卡局遭遇节点(P1 序列现值恰一 encounter 位)战斗结算后,备战席
  supply_box 恰 +1 + strategy_post_battle evidence 笔(sig 组
  'sim:strategy' 首落);非遭遇节点/未持卡零发放;败局存活也发(卡文无
  「胜利」限定),死亡局不发放(调用点在死亡提前 return 之后);幂等 =
  _settled_key 既有守卫回归(同节点重放不双发);修饰局跟随 = 序列
  现值判定(非硬编码轮次)。
- 驱动形态 = 出战动作触发结算(2026-10-29 流程模型:遭遇选完回备战,
  出战声明 battle_resolve);复用声明沿本目录先例:引擎驱动助手 import
  自 sim/test_sim_backend.py(已登记超限拆分债文件,禁追加,只 import
  复用不改);途经策略定卡固定「加油站」= 零判读域写,断言与 seed
  采样解耦(_drive_env_grant_step 内建)。
"""
from __future__ import annotations

import pytest
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
    _SIG_OBS,
    _backend,
    _drive_env_grant_step,
    _force_settle,
    _record_all_writes,
    _start_battle_feed,
)

from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_ENCOUNTER_BATTLE_GRANTS,
)
from sr_od.application.currency_war.kernel.cw_node_schedule import (
    resolve_plane_node_seqs,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BOSS_BRIEFING,
    SCREEN_BRIEFING,
    SCREEN_ENCOUNTER,
    SCREEN_INVEST_STRATEGY,
    SCREEN_LOBBY,
    SCREEN_MEGASTAR,
    SCREEN_PLANNER,
    SCREEN_PREP,
    SCREEN_SETTLE,
    SCREEN_SHOP,
    SCREEN_SUPPLY,
    SimBackend,
    uninstall_backend,
)

_CARD = '以战养战'
_ITEM = '简易武装箱'
_PLANE_TRANSITION = '货币战争-位面过渡'
_TRANSIT_SCREENS = (SCREEN_SETTLE, _PLANE_TRANSITION, SCREEN_INVEST_STRATEGY,
                    SCREEN_SUPPLY, SCREEN_ENCOUNTER, SCREEN_BOSS_BRIEFING,
                    SCREEN_MEGASTAR, SCREEN_PLANNER, SCREEN_SHOP)

_EVIDENCE_PREFIX = 'strategy_post_battle#'


@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(沿同目录同名 fixture 先例,fixture 不可跨文件
    import 故本文件自带同语义副本)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        consume_defect_sink,
        set_defect_sink,
    )
    consume_defect_sink()
    yield
    set_defect_sink(None)
    consume_defect_sink()


def _supply_box_count(b: SimBackend) -> int:
    """备战席 supply_box 槽计数(bench 未观察 = 0)。"""
    view = b.gs.bench.value
    if view is None:
        return 0
    return sum(1 for s in view.slots
               if s is not None and s.kind == 'supply_box')


def _grant_rows(calls: list[tuple]) -> list[tuple]:
    """strategy_post_battle 前缀写行(通道, 字段名, evidence, sig)。"""
    return [c for c in calls
            if c[2] is not None and c[2].startswith(_EVIDENCE_PREFIX)]


def _drive_to_kind_prep(monkeypatch: pytest.MonkeyPatch, b: SimBackend,
                        *, target_kind: str) -> None:
    """自开局简报驱动到指定位面 1 节点类型的备战窗(不出战,调用方掌控
    结算胜负与构造);途经战斗/奖励节点全胜强制穿过,中间屏走现役驱动
    步(补给恒选无钻/策略定卡加油站 = 零判读域写)。目标判定 = 节点窗
    场字段 kind 序列真值(非硬编码轮次,修饰局重构零特判跟随)。"""
    gs = b.gs
    for _ in range(80):
        node = gs.node.value
        screen = b.screen_identity()
        if screen == SCREEN_PREP and node is not None \
                and node.kind == target_kind:
            return
        if screen in _TRANSIT_SCREENS:
            _drive_env_grant_step(b)
        elif screen == SCREEN_PREP:
            _force_settle(monkeypatch, won=True)
            _start_battle_feed(gs)
        else:
            raise AssertionError(
                f'未预期屏 {screen!r}(target={target_kind})')
    raise AssertionError(f'驱动步数超限:未达 {target_kind} 备战窗')


def _hold_card(gs) -> None:
    """持卡直置(不经 pick 链——设计稿 §1.2e:端到端锁复用断言形态不走
    驱动链;注册状态容器直写 = 持卡事实单一源)。"""
    gs.write_logic(gs.active_strategies, [_CARD],
                   produced_by='test-seed', evidence='t:card', sig=_SIG)


def test_encounter_settle_grants_supply_box(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 1(sim 端到端发放真值):持卡局遭遇节点战斗结算后,备战席
    supply_box 恰 +1(带名槽件)+ strategy_post_battle#<卡名>#place
    evidence 笔,sig 单形态 = logic_action 族 'sim:strategy';
    pending_item_grants 定时队列不受扰(发放不走 GiftGrant 通道)。"""
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        _hold_card(gs)
        assert _supply_box_count(b) == 0, '持卡未结算零发放'
        _drive_to_kind_prep(monkeypatch, b, target_kind='encounter')
        grants_at_window = gs.pending_item_grants.value
        calls = _record_all_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert _supply_box_count(b) == 1, \
            f'遭遇结算后未落席: {_supply_box_count(b)}'
        slots = [s for s in gs.bench.value.slots
                 if s is not None and s.kind == 'supply_box']
        assert slots[0].item == _ITEM, '钉名槽件漂移'
        rows = _grant_rows(calls)
        assert [(c[0], c[1]) for c in rows] == [('rand', 'bench')], \
            f'发放写行形态漂移: {rows}'
        for c in rows:
            assert c[3].family == 'logic_action' \
                and c[3].group_id == 'sim:strategy', f'sig 组漂移: {c}'
        assert gs.bench.source == 'logic_rand', \
            '发放 = 随机态通道(未锚定窗,深井触发器 sim 锁同口径)'
        assert gs.pending_item_grants.value == grants_at_window, \
            '定时队列不受扰(发放不走 GiftGrant 通道,结算窗前后对拍)'
    finally:
        uninstall_backend()


def test_non_encounter_battle_node_zero_grant(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 2(非遭遇节点零发放):持卡局普通战斗(P1 首个 battle 位)
    结算后零箱零笔(节点类型条件,kind = 结算点现值)。"""
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='battle')
        calls = _record_all_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert _supply_box_count(b) == 0, '非遭遇节点误发放'
        assert _grant_rows(calls) == [], '非遭遇节点误写发放笔'
    finally:
        uninstall_backend()


def test_no_card_encounter_zero_grant(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 3(未持卡零发放):未持卡局同一遭遇节点结算后零箱零笔。"""
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        _drive_to_kind_prep(monkeypatch, b, target_kind='encounter')
        calls = _record_all_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert _supply_box_count(b) == 0, '未持卡误发放'
        assert _grant_rows(calls) == [], '未持卡误写发放笔'
    finally:
        uninstall_backend()


def test_loss_survival_still_grants(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 4a(败局存活也发):持卡局遭遇战败未死 → 箱照落(卡文无
    「胜利」限定 = 直读;调用点在胜败两态共同路径,败局待办登记之前)。"""
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='encounter')
        _force_settle(monkeypatch, won=False)
        _start_battle_feed(gs)
        assert b.screen_identity() == SCREEN_SETTLE, '败局存活(未进终局)'
        assert _supply_box_count(b) == 1, '败局存活未发放'
    finally:
        uninstall_backend()


def test_dead_battle_no_grant(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 4b(死亡局不发放):保底已用 + 濒死局遭遇战败 → hp 归零死亡
    提前 return 在调用点之前,零发放直接进终局(局终不见发放,与实机一致)。"""
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='encounter')
        gs.observe(gs.hp_floor_triggered, True, sig=_SIG_OBS)
        gs.observe(gs.hp, 1, sig=_SIG_OBS)
        _force_settle(monkeypatch, won=False)
        _start_battle_feed(gs)
        assert b.done and b.screen_identity() == SCREEN_LOBBY, \
            '败局致死应进终局'
        assert _supply_box_count(b) == 0, '死亡局误发放'
    finally:
        uninstall_backend()


def test_settled_key_guard_no_double_grant(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 5(幂等回归):同遭遇节点战斗重放(battle_resolve 重入)→
    _settled_key 既有守卫整段跳过,零二次发放零新增笔(防本腿绕过)。"""
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='encounter')
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert _supply_box_count(b) == 1, '前置:首结算已落席'
        calls = _record_all_writes(gs, monkeypatch)
        _start_battle_feed(gs)
        assert _supply_box_count(b) == 1, '_settled_key 重入双发'
        assert _grant_rows(calls) == [], '重入零新增发放笔'
    finally:
        uninstall_backend()


def test_modified_plane_sequence_encounter_kind_follows() -> None:
    """锁 8(修饰局跟随,序列现值判定非硬编码轮次):插入型修饰局
    (人身意外险,boss 位前插 supply)P1 序列的 encounter 位次由序列
    真值派生——现役修饰局遭遇位不移动(发放次数 = 序列 encounter 数,
    不变);触发腿 node_kind 传结算点现值,序列重构零特判跟随。"""
    base = resolve_plane_node_seqs('')[1]
    modified = resolve_plane_node_seqs('人身意外险')[1]
    enc_base = [i + 1 for i, k in enumerate(base) if k == 'encounter']
    enc_modified = [i + 1 for i, k in enumerate(modified)
                    if k == 'encounter']
    assert len(enc_base) == 1, f'默认域 P1 恰一遭遇位(现值): {enc_base}'
    assert enc_base == enc_modified, \
        '现役修饰局遭遇位不移动(插桩在 boss 位前,发放次数不变)'
    assert set(STRATEGY_ENCOUNTER_BATTLE_GRANTS) == {_CARD}, \
        '注册面现值(发放次数 = 持卡 × encounter 数)'
