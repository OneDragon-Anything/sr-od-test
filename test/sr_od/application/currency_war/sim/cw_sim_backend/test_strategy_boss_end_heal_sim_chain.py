"""策略卡首领战结束回血 sim 状态副本链测试(镜像 src = sim/cw_sim_backend.py
的 _resolve_battle 首领战回血腿;kernel 触发函数单元面 = kernel/
cw_gain_chain/test_check_strategy_boss_end_heal.py,本文件锁 sim 结算腿
接入调用与状态副本里的值落地面)。

测试面依据 = 迭代设计 designs/T-313-fendou-xieyi.md §4 锁 3/4/5/6/7
(REVIEW-T313 无需用户决定 6/6;驱动与断言形态先例 = 同目录
test_strategy_boss_battle_grant_sim_chain.py,跨位面驱动先例 =
test_p3_win_terminal._drive_step 的位面过渡分派支):

- 锁 3:持卡局首领战结算(胜败两态)回血笔 hp +50 + hp_trail 成对追加
  (first_run 状态容器不变式② 写流↔轨迹同构在腿粒度保持:结算写 + 回血笔
  恰两笔);evidence ``sim:engine:strategy:boss_heal:p<位面>r<轮>``
  (sim_evidence 前缀契约,win 金腿同形)、sig = obs 族 'sim:strategy'
  组;建模假设披露键随局申报(cap/perfect_win_bias);
- 锁 4(直加不 clip 边界,现值重推落形):hp 预置 90 → 回血 140,
  越过存量 100 上界仍直加(正部 HP 加法家族形真值锁——后继补 clip 常
  量在此显式红,披露键 strategy_boss_heal_hp_cap_unverified 申报面);
- 锁 5:死亡局(boss 战致死)提前 return 不回血;
- 锁 6:无卡局首领战结算 hp 写流不变(恰结算一笔,轨迹 +1);
- 锁 7(完胜漏判方向锁):持卡局 boss 战(胜零损)后相邻战斗胜局零损
  → 结算环 last_two_rows 差分含 heal 项(+50),完胜判据
  (check_env_deploy_lock_perfect,相邻环行 hp 持平)返回空——漏判
  方向 = 偏严的结构性行为证据,防后继改判据时静默翻向。
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

from sr_od.application.currency_war.kernel.cw_env_grants import (
    check_env_deploy_lock_perfect,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_investments import (
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
from sr_od.application.currency_war.sim.cw_sim_base import ChannelSig

_CARD = '奋斗协议'
_PLANE_TRANSITION = '货币战争-位面过渡'
_HEAL_PREFIX = 'sim:engine:strategy:boss_heal:'

#: 完胜检查入参(logic 族;obs 族进写通道即炸渠道族校验)。
_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')


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
    test_strategy_boss_battle_grant_sim_chain._prep_backend 形)。"""
    b = _backend(seed)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP, '前置:未达 P1r1 备战屏'
    return b


def _record_world_writes(gs, monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic/write_logic_rand/observe 记录
    (通道, 字段名, evidence, sig, value, produced_by) 写序(透传真实现
    零行为变化;债文件禁追加故本文件自带副本,先例 =
    test_strategy_boss_battle_grant_sim_chain._record_world_writes)。"""
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
    经位面过渡屏空白点击收尾,先例 = test_p3_win_terminal._drive_step
    过渡分派支;目标判定 = 节点窗场字段 kind 序列真值)。"""
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


def test_boss_win_settle_heals_held_card(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 3a(胜局存活也回血):持卡局首领战结算(胜)→ 恰一笔回血写
    (+50)+ 轨迹成对追加(结算等值笔 + 回血笔恰两笔)+ evidence/sig
    形态 + 建模假设披露键随局申报。"""
    b = _prep_backend(81)
    try:
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='boss')
        node = gs.node.value
        assert node is not None and node.kind == 'boss', '前置:boss 备战窗'
        hp_before = int(gs.hp.value)
        trail_len = len(b.hp_trail)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        rows = _heal_rows(calls)
        assert len(rows) == 1, f'回血笔数漂移: {[c[:3] for c in rows]}'
        row = rows[0]
        assert row[0] == 'obs', f'回血写应走观察通道: {row[0]}'
        assert row[2] == (f'sim:engine:strategy:boss_heal:p{node.plane}'
                          f'r{node.round_num}'), f'evidence 漂移: {row[2]}'
        assert row[3].family == 'obs' \
            and row[3].group_id == 'sim:strategy', f'sig 组漂移: {row[3]}'
        assert row[4] == hp_before + 50, \
            f'回血值漂移: {row[4]} (before={hp_before})'
        # 轨迹成对(不变式②腿粒度):结算笔 + 回血笔恰两笔,末值 = 状态容器现值
        assert len(b.hp_trail) - trail_len == 2, \
            f'轨迹追加笔数漂移: {b.hp_trail[trail_len:]}'
        assert list(b.hp_trail[trail_len:]) == [hp_before, hp_before + 50], \
            '结算笔+回血笔轨迹值漂移'
        assert gs.hp.value == hp_before + 50, '状态容器终值漂移'
        assert b.screen_identity() == SCREEN_SETTLE, '结算后应泊结算屏'
        assert b.disclosures.get(STRATEGY_BOSS_HEAL_HP_CAP_ASSUMPTION) \
            == 'direct_add_no_clip_v0', 'cap 披露键未随局申报'
        assert b.disclosures.get(STRATEGY_BOSS_HEAL_PERFECT_WIN_BIAS) \
            == 'next_node_perfect_missed_strict_v0', '完胜偏严披露键未申报'
    finally:
        uninstall_backend()


def test_boss_loss_survival_heals(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 3b(败局存活也回血):卡面无「胜利」限定 = 败局存活同拍回血
    (败局 −23 + 回血 +50,调用点在胜败两态共同路径)。"""
    b = _prep_backend(82)
    try:
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='boss')
        hp_before = int(gs.hp.value)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=False)
        _start_battle_feed(gs)
        assert b.screen_identity() == SCREEN_SETTLE, '败局存活(未进终局)'
        rows = _heal_rows(calls)
        assert len(rows) == 1, f'败局回血笔数漂移: {[c[:3] for c in rows]}'
        assert rows[0][4] == hp_before - 23 + 50, \
            f'败局回血值漂移: {rows[0][4]} (before={hp_before})'
    finally:
        uninstall_backend()


def test_direct_add_no_clip_boundary(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 4(直加不 clip 边界,§5-3 现值重推落形):hp 预置 90 → 首领战
    胜零损 + 回血 = 140 越过存量 100 上界仍直加——正部 HP 加法家族形
    真值锁(后继引入 clip 常量在此显式红;轨迹仍成对)。"""
    b = _prep_backend(83)
    try:
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='boss')
        gs.observe(gs.hp, 90, sig=_SIG_OBS)
        trail_len = len(b.hp_trail)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        rows = _heal_rows(calls)
        assert len(rows) == 1, f'回血笔数漂移: {[c[:3] for c in rows]}'
        assert rows[0][4] == 140, f'直加越界回血值漂移: {rows[0][4]}'
        assert gs.hp.value == 140, '状态容器终值应 140(不 clip)'
        assert list(b.hp_trail[trail_len:]) == [90, 140], \
            '轨迹应恰结算笔+回血笔成对'
    finally:
        uninstall_backend()


def test_dead_battle_no_heal(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 5(死亡局不回血):保底已用 + 濒死局 boss 战败致死 → hp 归零
    死亡提前 return 在回血调用点之前,零回血笔直接进终局(局终不见回血,
    与实机一致)。"""
    b = _prep_backend(84)
    try:
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='boss')
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


def test_no_card_boss_write_stream_unchanged(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 6(无卡局写流不变):未持卡局同一 boss 节点结算 → hp 写流恰
    结算一笔、轨迹 +1、零回血笔(基线形态维持)。"""
    b = _prep_backend(85)
    try:
        gs = b.gs
        _drive_to_kind_prep(monkeypatch, b, target_kind='boss')
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


def test_next_node_perfect_win_missed_direction(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 7(完胜漏判方向锁):持卡局 boss 战(胜零损)+ 回血笔在环行
    后 → 相邻战斗胜局零损时结算环 last_two_rows 差分含 heal 项(+50),
    完胜判据(相邻环行 hp 持平)返回空——漏判方向 = 偏严的结构性行为
    证据,防后继改判据时静默翻向(cw_env_grants 偏差面条款辖内新事件
    源,披露键 strategy_boss_heal_perfect_win_bias 申报面)。"""
    b = _prep_backend(86)
    try:
        gs = b.gs
        _hold_card(gs)
        # 第一场普通战斗胜零损(环行 A)
        _drive_to_kind_prep(monkeypatch, b, target_kind='battle')
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        # 首领战胜零损 + 回血(环行 B,回血笔在环行后)
        _drive_to_kind_prep(monkeypatch, b, target_kind='boss')
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        # 相邻战斗胜零损(环行 C:状态容器已含回血)
        _drive_to_kind_prep(monkeypatch, b, target_kind='battle')
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        rows = gs.settlement_ring.last_two_rows()
        assert len(rows) == 2, f'结算环行数不足: {len(rows)}'
        tail, prev = rows[-1], rows[-2]
        assert tail.killed is True and prev.killed is True, \
            '前置:相邻两环行应均胜局'
        assert tail.hp_after is not None and prev.hp_after is not None, \
            '前置:相邻两环行 hp 应可判'
        assert tail.hp_after - prev.hp_after == 50, \
            f'环行差分应含 heal 项(+50): {prev.hp_after} → {tail.hp_after}'
        # 完胜判据在该差分形态下漏判(偏严方向结构性行为)
        gs.write_logic(gs.env_grant_deploy_locks, (('某角色', 7, (1, 5)),),
                       produced_by='test-seed', evidence='t:lock', sig=_SIG)
        gs.write_logic(gs.env_grants_done,
                       (('英雄登场', 'deploy_lock_uid#7'),),
                       produced_by='test-seed', evidence='t:done', sig=_SIG)
        effects = check_env_deploy_lock_perfect(gs, _LSIG)
        assert effects == (), \
            f'完胜判据应漏判返回空: {effects!r}'
        assert gs.env_grant_deploy_locks.value == \
            (('某角色', 7, (1, 5)),), '漏判形态下锁记录不得回退'
    finally:
        uninstall_backend()
