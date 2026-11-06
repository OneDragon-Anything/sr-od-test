"""策略卡战斗结束回血 sim 状态副本链测试(镜像 src = sim/cw_sim_backend.py
的 _resolve_battle 战斗结束回血效果条目;kernel 触发函数单元面 = kernel/
cw_gain_chain/test_check_strategy_battle_end_heal.py,本文件锁 sim 结算效果条目
接入调用与状态副本里的值落地面)。

测试面依据 = 迭代设计 designs/T-325-xingji-heping-baoxian.md §4 锁 5
(REVIEW-T325 无需用户决定 7/7;驱动与断言形态先例 = 同目录
test_strategy_boss_end_heal_sim_chain.py,直加不 clip 边界沿其锁 4 实现
现值重推形):

- 节点矩阵:battle/encounter/boss 三型结算 → 回血笔 hp +10 + hp_trail
  成对追加(写流↔轨迹同构在效果条目粒度保持:结算笔 + 回血笔恰两笔);
  evidence ``sim:engine:strategy:battle_heal:p<位面>r<轮>``,sig = obs 族
  'sim:strategy' 组;胜败两态共同路径(败局存活也回);
- reward/supply → 零笔(扑满 ∈ reward 随默认子案 a 同闸零笔——触发域
  判读申报披露键承载,非定论);
- 死亡局 → 零笔(dead 提前 return 在调用点之前);
- 直加不 clip 边界:hp 预置 95 → 回血 105 越存量 100 上界仍直加(正部
  HP 加法家族形真值锁,后继补 clip 常量在此显式红)+ 三披露键存在性
  断言(scope/cap 家族键/完胜偏严);
- 无卡局写流不变(恰结算一笔,轨迹 +1)。

复用声明:引擎驱动助手 import 自 sim/test_sim_backend.py(已登记超限
拆分债文件,禁追加,只 import 复用不改)。
"""
from __future__ import annotations

import pytest
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
    _SIG_OBS,
    _backend,
    _close_shop_feed,
    _drive_env_grant_step,
    _force_settle,
    _start_battle_feed,
)

from sr_od.application.currency_war.kernel.cw_game_state import (
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_BATTLE_HEAL_SCOPE_ASSUMPTION,
    STRATEGY_BOSS_HEAL_HP_CAP_ASSUMPTION,
    STRATEGY_BOSS_HEAL_PERFECT_WIN_BIAS,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BOSS_BRIEFING,
    SCREEN_BRIEFING,
    SCREEN_INVEST_STRATEGY,
    SCREEN_LOBBY,
    SCREEN_PREP,
    SCREEN_SETTLE,
    SCREEN_SHOP,
    SCREEN_SUPPLY,
    SimBackend,
    uninstall_backend,
)

_CARD = '星际和平保险'
_PLANE_TRANSITION = '货币战争-位面过渡'
_HEAL_PREFIX = 'sim:engine:strategy:battle_heal:'
_HEAL_AMOUNT = 10


@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(沿同目录同名 fixture 先例,fixture 不可跨文件
    import 故本文件自带同语义副本)。"""
    consume_defect_sink()
    yield
    set_defect_sink(None)
    consume_defect_sink()


def _prep_backend(seed: int) -> SimBackend:
    """装配后端至 P1r1 备战屏(调用方负责 uninstall;先例 = 同目录
    test_strategy_boss_end_heal_sim_chain._prep_backend 形)。"""
    b = _backend(seed)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP, '前置:未达 P1r1 备战屏'
    return b


def _record_world_writes(gs, monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic/write_logic_rand/observe 记录
    (通道, 字段名, evidence, sig, value, produced_by) 写序(透传真实现
    零行为变化;跨文件 import helper 不立,先例 =
    test_strategy_boss_end_heal_sim_chain._record_world_writes)。"""
    calls: list[tuple] = []

    def _wrap_logic(real, channel: str):
        def rec(target, value, *, produced_by, evidence=None, sig, note=''):
            calls.append((channel, gs._field_name(target), evidence, sig,
                          value, produced_by))
            real(target, value, produced_by=produced_by, evidence=evidence,
                 sig=sig, note=note)
        return rec

    def _wrap_obs(real):
        def rec(target, value, *, evidence=None, sig, note=''):
            calls.append(('obs', gs._field_name(target), evidence, sig,
                          value, None))
            real(target, value, evidence=evidence, sig=sig, note=note)
        return rec

    monkeypatch.setattr(gs, 'write_logic',
                        _wrap_logic(gs.write_logic, 'logic'))
    monkeypatch.setattr(gs, 'write_logic_rand',
                        _wrap_logic(gs.write_logic_rand, 'rand'))
    monkeypatch.setattr(gs, 'observe', _wrap_obs(gs.observe))
    return calls


def _hold_card(gs, *, card: str = _CARD) -> None:
    """持卡直置(注册状态容器直写 = 持卡事实单一源;不经 pick 链)。"""
    gs.write_logic(gs.active_strategies, [card],
                   produced_by='test-seed', evidence='t:card', sig=_SIG)


def _drive_to_kind_prep(monkeypatch: pytest.MonkeyPatch, b: SimBackend,
                        *, target_kind: str) -> None:
    """自当前窗驱动到指定节点类型的备战窗(途经战斗全胜强制穿过;跨位面
    经位面过渡屏空白点击收尾,先例 =
    test_strategy_boss_end_heal_sim_chain._drive_to_kind_prep;目标判定 =
    节点窗场字段 kind 序列真值)。"""
    gs = b.gs
    for _ in range(150):
        node = gs.node.value
        screen = b.screen_identity()
        if screen == SCREEN_PREP and node is not None \
                and node.kind == target_kind:
            return
        if screen == _PLANE_TRANSITION:
            b._handle_click_source(_PLANE_TRANSITION, '区域-空白点击')
        elif screen in (SCREEN_SETTLE, SCREEN_SHOP, SCREEN_SUPPLY,
                        SCREEN_INVEST_STRATEGY, SCREEN_BOSS_BRIEFING) \
                or screen in ('货币战争-遭遇节点', '货币战争-盛会之星',
                              '货币战争-银狼升星'):
            _drive_env_grant_step(b)
        elif screen == '货币战争-备战-开商店':
            _close_shop_feed(b)
        elif screen == SCREEN_PREP:
            _force_settle(monkeypatch, won=True)
            _start_battle_feed(gs)
        else:
            raise AssertionError(
                f'未预期屏 {screen!r}(target={target_kind})')
    raise AssertionError(f'驱动步数超限:未达 {target_kind} 备战窗')


def _heal_rows(calls: list[tuple]) -> list[tuple]:
    """回血前缀 hp 写行(通道, 字段名, evidence, sig, value, …)。"""
    return [c for c in calls
            if c[1] == 'hp'
            and str(c[2] or '').startswith(_HEAL_PREFIX)]


def _hp_rows(calls: list[tuple]) -> list[tuple]:
    """全部 hp 写行(结算笔 + 回血笔 + 开局种等)。"""
    return [c for c in calls if c[1] == 'hp']


def test_combat_node_matrix_heals_on_win_settlement(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """节点矩阵锁(battle/encounter/boss 三型 × 胜局):每战斗结算恰一笔回
    血(+10)+ 轨迹成对(结算等值笔 + 回血笔恰两笔)+ evidence 逐节点
    分账 + sig 组形态。"""
    b = _prep_backend(91)
    try:
        gs = b.gs
        _hold_card(gs)
        for kind in ('battle', 'encounter', 'boss'):
            _drive_to_kind_prep(monkeypatch, b, target_kind=kind)
            node = gs.node.value
            assert node is not None and node.kind == kind, \
                f'前置:{kind} 备战窗'
            hp_before = int(gs.hp.value)
            trail_len = len(b.hp_trail)
            calls = _record_world_writes(gs, monkeypatch)
            _force_settle(monkeypatch, won=True)
            _start_battle_feed(gs)
            rows = _heal_rows(calls)
            assert len(rows) == 1, \
                f'{kind} 回血笔数漂移: {[c[:3] for c in rows]}'
            row = rows[0]
            assert row[0] == 'obs', f'回血写应走观察通道: {row[0]}'
            assert row[2] == (f'sim:engine:strategy:battle_heal:'
                              f'p{node.plane}r{node.round_num}'), \
                f'evidence 漂移: {row[2]}'
            assert row[3].family == 'obs' \
                and row[3].group_id == 'sim:strategy', \
                f'sig 组漂移: {row[3]}'
            assert row[4] == hp_before + _HEAL_AMOUNT, \
                f'回血值漂移: {row[4]} (before={hp_before})'
            assert len(b.hp_trail) - trail_len == 2, \
                f'轨迹追加笔数漂移: {b.hp_trail[trail_len:]}'
            assert list(b.hp_trail[trail_len:]) == \
                [hp_before, hp_before + _HEAL_AMOUNT], \
                '结算笔+回血笔轨迹值漂移'
            assert b.screen_identity() == SCREEN_SETTLE, \
                '结算后应泊结算屏'
    finally:
        uninstall_backend()


def test_loss_survival_heals(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """败局存活也回血:卡面「战斗后」无「胜利」限定 = 败局存活同拍回血
    (败局 −23 + 回血 +10,调用点在胜败两态共同路径)。"""
    b = _prep_backend(92)
    try:
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='encounter')
        hp_before = int(gs.hp.value)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=False)
        _start_battle_feed(gs)
        assert b.screen_identity() == SCREEN_SETTLE, '败局存活(未进终局)'
        rows = _heal_rows(calls)
        assert len(rows) == 1, f'败局回血笔数漂移: {[c[:3] for c in rows]}'
        assert rows[0][4] == hp_before - 23 + _HEAL_AMOUNT, \
            f'败局回血值漂移: {rows[0][4]} (before={hp_before})'
    finally:
        uninstall_backend()


def test_reward_and_supply_zero_heal(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """reward/supply 零笔:奖励关白胜结算(kind=reward,扑满 ∈ reward
    同闸)零回血笔、恰结算等值一笔;补给节点出战 = supply_finish 推进
    (无 battle_resolve)整窗零回血笔。"""
    b = _prep_backend(93)
    try:
        gs = b.gs
        _hold_card(gs)
        # P1r1 = reward:结算奖励关 → 白胜等值笔,零回血笔
        node = gs.node.value
        assert node is not None and node.kind == 'reward', '前置:奖励关窗'
        hp_before = int(gs.hp.value)
        trail_len = len(b.hp_trail)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert _heal_rows(calls) == [], '奖励关误回血(扑满 ∈ reward 同闸)'
        hp_rows = _hp_rows(calls)
        assert len(hp_rows) == 1, \
            f'奖励关 hp 写流漂移(应恰结算一笔): {[c[:3] for c in hp_rows]}'
        assert hp_rows[0][4] == hp_before, '奖励关结算笔应等值写'
        assert len(b.hp_trail) - trail_len == 1, '奖励关轨迹应恰 +1'
        # 补给节点:驱动至 supply 窗,窗内推进(supply_finish)零结算零回血
        _drive_to_kind_prep(monkeypatch, b, target_kind='supply')
        node = gs.node.value
        supply_round = node.round_num
        supply_plane = node.plane
        calls2 = _record_world_writes(gs, monkeypatch)
        for _ in range(80):
            node = gs.node.value
            if node is None or (node.plane, node.round_num) != \
                    (supply_plane, supply_round):
                break
            screen = b.screen_identity()
            if screen == SCREEN_PREP:
                # 补给出战 = supply_finish 推进(非 battle_resolve),
                # _force_settle 不适用——零战斗面直接推进。
                _start_battle_feed(gs)
            elif screen == _PLANE_TRANSITION:
                b._handle_click_source(_PLANE_TRANSITION, '区域-空白点击')
            elif screen in (SCREEN_SETTLE, SCREEN_SHOP, SCREEN_SUPPLY,
                            SCREEN_INVEST_STRATEGY, SCREEN_BOSS_BRIEFING) \
                    or screen in ('货币战争-遭遇节点', '货币战争-盛会之星',
                                  '货币战争-银狼升星'):
                _drive_env_grant_step(b)
            elif screen == '货币战争-备战-开商店':
                _close_shop_feed(b)
            else:
                raise AssertionError(f'未预期屏 {screen!r}(supply 窗)')
        else:
            raise AssertionError('补给窗推进步数超限')
        assert _heal_rows(calls2) == [], \
            f'补给窗误回血: {[c[:3] for c in _heal_rows(calls2)]}'
    finally:
        uninstall_backend()


def test_dead_battle_no_heal(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """死亡局不回血:保底已用 + 濒死局战斗败致死 → hp 归零死亡提前
    return 在回血调用点之前,零回血笔直接进终局。"""
    b = _prep_backend(94)
    try:
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='battle')
        gs.observe(gs.hp_floor_triggered, True, sig=_SIG_OBS)
        gs.observe(gs.hp, 1, sig=_SIG_OBS)
        trail_len = len(b.hp_trail)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=False)
        _start_battle_feed(gs)
        assert b.done and b.screen_identity() == SCREEN_LOBBY, \
            '败局致死应进终局'
        assert _heal_rows(calls) == [], '死亡局误回血'
        hp_rows = _hp_rows(calls)
        assert len(hp_rows) == 1, \
            f'死亡局 hp 写流漂移(应恰死亡归零一笔): {[c[:3] for c in hp_rows]}'
        assert len(b.hp_trail) - trail_len == 1, '死亡局轨迹应恰 +1(归零笔)'
    finally:
        uninstall_backend()


def test_direct_add_no_clip_boundary_with_disclosures(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """直加不 clip 边界 + 披露键存在性:hp 预置 95 → 胜零损 + 回血 = 105
    越存量 100 上界仍直加(正部 HP 加法家族形真值锁,后继引入 clip 常量
    在此显式红;轨迹仍成对);三披露键(scope/cap 家族键/完胜偏严)随局
    申报。"""
    b = _prep_backend(95)
    try:
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='battle')
        gs.observe(gs.hp, 95, sig=_SIG_OBS)
        trail_len = len(b.hp_trail)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        rows = _heal_rows(calls)
        assert len(rows) == 1, f'回血笔数漂移: {[c[:3] for c in rows]}'
        assert rows[0][4] == 105, f'直加越界回血值漂移: {rows[0][4]}'
        assert gs.hp.value == 105, '状态容器终值应 105(不 clip)'
        assert list(b.hp_trail[trail_len:]) == [95, 105], \
            '轨迹应恰结算笔+回血笔成对'
        assert b.disclosures.get(STRATEGY_BATTLE_HEAL_SCOPE_ASSUMPTION) \
            == 'combat_node_types_piggy_excluded_v0', \
            '触发域判读申报披露键未随局申报'
        assert b.disclosures.get(STRATEGY_BOSS_HEAL_HP_CAP_ASSUMPTION) \
            == 'direct_add_no_clip_v0', 'cap 家族披露键未随局申报'
        assert b.disclosures.get(STRATEGY_BOSS_HEAL_PERFECT_WIN_BIAS) \
            == 'next_node_perfect_missed_strict_v0', \
            '完胜偏严披露键未随局申报'
    finally:
        uninstall_backend()


def test_no_card_battle_write_stream_unchanged(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """无卡局写流不变:未持卡局同一战斗节点结算 → hp 写流恰结算一笔、
    轨迹 +1、零回血笔(基线形态维持)。"""
    b = _prep_backend(96)
    try:
        gs = b.gs
        _drive_to_kind_prep(monkeypatch, b, target_kind='battle')
        hp_before = int(gs.hp.value)
        trail_len = len(b.hp_trail)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert _heal_rows(calls) == [], '未持卡误回血'
        hp_rows = _hp_rows(calls)
        assert len(hp_rows) == 1, \
            f'无卡局 hp 写流漂移(应恰结算一笔): {[c[:3] for c in hp_rows]}'
        assert hp_rows[0][4] == hp_before, '无卡局结算笔应等值写'
        assert len(b.hp_trail) - trail_len == 1, '无卡局轨迹应恰 +1'
    finally:
        uninstall_backend()
