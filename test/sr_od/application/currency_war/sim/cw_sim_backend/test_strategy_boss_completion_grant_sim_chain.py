"""策略卡首领节点完成固定集发放 sim 状态副本链测试(镜像 src =
sim/cw_sim_backend.py 的 _resolve_battle 首领完成效果条目;kernel 触发函数
单元面 = kernel/cw_gain_chain/test_check_strategy_boss_completion_
grants.py,本文件锁 sim 结算效果条目接入调用与状态副本里的值落地面)。

测试面依据 = 原稿锁面(§ 号 = 原稿节序)§4 锁 4/5/6 +
原稿评审锁(驱动与断言形态先例 = 同目录 test_strategy_boss_battle_
grant_sim_chain.py):
- 持卡局 P1 首领节点(P1 序列现值末位)战斗结算后 equips 恰 +8(简易池
  注册表序全集)+ ``strategy_boss_completion#<卡名>`` 前缀 evidence 笔
  ×8 + 落一次性标志位(strategy_conditional_done 纯卡名;**断言用前缀匹配禁精确
  匹配**——gain_equipment 原语内追加 #equip 后缀,T-166 收尾批 D2
  口径);确定发放 = logic 渠道(锚定域 rand=False);
- 一次性标志位:落一次性标志位后续位面首领(P2 首领位)再结算零新增笔(「下个」恰
  一次,函数内一次性标志位自管防跨 boss 重复);
- 败局存活也发(卡面无「胜利」限定 = 直读);死亡局不发放(调用点在死亡
  提前 return 之后);
- 驱动形态 = 出战动作触发结算(2026-10-29 流程模型);引擎驱动助手
  import 自 sim/test_sim_backend.py(已登记超限拆分债文件,禁追加,只
  import 复用不改);helper 副本(状态副本写包装/类型备战驱动/定参结算)
  沿同目录先例自带同语义拷贝。
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
    SIMPLE_EQUIP_ALL,
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

_CARD = '武器批发商'
_PLANE_TRANSITION = '货币战争-位面过渡'
_TRANSIT_SCREENS = (SCREEN_SETTLE, _PLANE_TRANSITION, SCREEN_INVEST_STRATEGY,
                    SCREEN_SUPPLY, SCREEN_ENCOUNTER, SCREEN_BOSS_BRIEFING,
                    SCREEN_MEGASTAR, SCREEN_PLANNER, SCREEN_SHOP)

_EVIDENCE_PREFIX = 'strategy_boss_completion#'


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


def _hold_card(gs) -> None:
    """持卡直置(注册状态容器直写 = 持卡事实单一源;不经 pick 链)。"""
    gs.write_logic(gs.active_strategies, [_CARD],
                   produced_by='test-seed', evidence='t:card', sig=_SIG)


def _drive_step(b: SimBackend) -> None:
    """单步驱动(债文件 _drive_env_grant_step 副本 + 位面过渡空白点击
    支——跨位面驱动必经,先例 = test_p3_win_terminal._drive_step 过渡
    分派支;债文件禁追加故本文件自带同语义拷贝)。"""
    if b.screen_identity() == '货币战争-位面过渡':
        b._handle_click_source('货币战争-位面过渡', '区域-空白点击')
        return
    _drive_env_grant_step(b)


def _drive_to_kind_prep(monkeypatch: pytest.MonkeyPatch, b: SimBackend,
                        *, target_kind: str) -> None:
    """自当前窗驱动到指定位面节点类型的备战窗(途经战斗/奖励节点
    全胜强制穿过,中间屏走现役驱动步;目标判定 = 节点窗场字段 kind
    序列真值;同目录 boss 战后效果条目锁同形副本)。"""
    gs = b.gs
    for _ in range(120):
        node = gs.node.value
        screen = b.screen_identity()
        if screen == SCREEN_PREP and node is not None \
                and node.kind == target_kind:
            return
        if screen in _TRANSIT_SCREENS:
            _drive_step(b)
        elif screen == '货币战争-备战-开商店':
            # 备战开店形态(窗起发牌后自动弹店):关店动作单轨回备战
            _close_shop_feed(b)
        elif screen == SCREEN_PREP:
            _force_settle(monkeypatch, won=True)
            _start_battle_feed(gs)
        else:
            raise AssertionError(
                f'未预期屏 {screen!r}(target={target_kind})')
    raise AssertionError(f'驱动步数超限:未达 {target_kind} 备战窗')


def _grant_rows(calls: list[tuple]) -> list[tuple]:
    """strategy_boss_completion 前缀写行(通道, 字段名, evidence, sig,
    …)。"""
    return [c for c in calls
            if c[1] == 'equips'
            and str(c[2] or '').startswith(_EVIDENCE_PREFIX)]


def _latch_rows(calls: list[tuple]) -> list[tuple]:
    """strategy_boss_completion 前缀一次性标志位写行(strategy_conditional_done
    字段,evidence 同证据基)。"""
    return [c for c in calls
            if c[1] == 'strategy_conditional_done'
            and str(c[2] or '').startswith(_EVIDENCE_PREFIX)]


def test_boss_settle_grants_full_set_and_latch(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 4a(sim 端到端发放真值):持卡局 P1 首领节点战斗结算后
    equips 恰 +8(简易池注册表序全集,禁手抄清单)+ 前缀 evidence 笔
    ×8 + 落一次性标志位;确定发放 = logic 渠道,单形态 = logic_action 族
    'sim:strategy' 组。"""
    b = _prep_backend(81)
    try:
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='boss')
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        rows = _grant_rows(calls)
        assert len(rows) == len(SIMPLE_EQUIP_ALL), \
            f'装备笔数漂移(应 8 件): {[c[:3] for c in rows]}'
        pool = set(SIMPLE_EQUIP_ALL)
        assert all(str(r[2]).startswith(_EVIDENCE_PREFIX) for r in rows), \
            f'evidence 前缀漂移: {[str(r[2]) for r in rows]}'
        assert all(str(r[2]).endswith('#equip') for r in rows), \
            f'evidence 后缀漂移: {[str(r[2]) for r in rows]}'
        assert all(r[0] == 'rand' for r in rows), \
            f'sim 域 equips 状态容器未锚定 → 随机态通道标签(结构态;rand=False'\
            f' 锁值确定性 = 全集序比对,非通道): {[r[0] for r in rows]}'
        assert all(r[3].family == 'logic_action'
                   and r[3].group_id == 'sim:strategy' for r in rows), \
            f'sig 组漂移: {[r[3] for r in rows]}'
        assert list(gs.equips.value or [])[-len(SIMPLE_EQUIP_ALL):] \
            and set(gs.equips.value or []) >= pool, '入栏应含简易全集'
        latches = _latch_rows(calls)
        assert len(latches) == 1, f'一次性标志位写笔数漂移: {[c[:3] for c in latches]}'
        assert _CARD in (gs.strategy_conditional_done.value or ()), '未落一次性标志位'
        assert b.screen_identity() == SCREEN_SETTLE, '结算后应泊结算屏'
    finally:
        uninstall_backend()


def test_next_plane_boss_no_repeat_after_latch(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 4b(一次性标志位跨位面):P1 首领结算落一次性标志位 → 驱动至 P2 首领位再
    结算 → 零新增发放笔零新一次性标志位(「下个」恰一次;幂等守卫防同战斗重放,
    一次性标志位防跨 boss 重复)。"""
    b = _prep_backend(82)
    try:
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='boss')
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert _CARD in (gs.strategy_conditional_done.value or ()), \
            '前置:首首领结算未落一次性标志位'
        calls = _record_world_writes(gs, monkeypatch)
        _drive_to_kind_prep(monkeypatch, b, target_kind='boss')
        assert gs.node.value.plane == 2, \
            f'前置:应达 P2 首领位备战窗(plane={gs.node.value.plane})'
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        # 一次性标志位后零重复判据 = 本效果条目前缀笔零新增(equips 全列表会混入 P2
        # 途程其他发放通道产出,非本效果条目语义面)。
        assert _grant_rows(calls) == [], '一次性标志位后跨位面首领重复发放'
        assert _latch_rows(calls) == [], '一次性标志位后零新一次性标志位写笔'
        assert _CARD in (gs.strategy_conditional_done.value or ()), '一次性标志位漂移'
    finally:
        uninstall_backend()


def test_loss_survival_still_grants(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 5(败局存活也发):持卡局首领战败未死 → 固定集照入栏(卡面无
    「胜利」限定 = 直读;调用点在胜败两态共同路径,败局待办登记之前)。"""
    b = _prep_backend(83)
    try:
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='boss')
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=False)
        _start_battle_feed(gs)
        assert b.screen_identity() == SCREEN_SETTLE, '败局存活(未进终局)'
        rows = _grant_rows(calls)
        assert len(rows) == len(SIMPLE_EQUIP_ALL), \
            f'败局存活未足额发放: {[c[:3] for c in rows]}'
        assert _CARD in (gs.strategy_conditional_done.value or ()), \
            '败局存活未落一次性标志位'
    finally:
        uninstall_backend()


def test_dead_battle_no_grant(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 6(死亡局不发放):保底已用 + 濒死局首领战败 → hp 归零死亡
    提前 return 在调用点之前,零发放直接进终局(局终不见发放,与实机
    一致)。"""
    b = _prep_backend(84)
    try:
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='boss')
        gs.observe(gs.hp_floor_triggered, True, sig=_SIG_OBS)
        gs.observe(gs.hp, 1, sig=_SIG_OBS)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=False)
        _start_battle_feed(gs)
        assert b.done and b.screen_identity() == SCREEN_LOBBY, \
            '败局致死应进终局'
        assert _grant_rows(calls) == [], '死亡局误发放'
        assert _CARD not in (gs.strategy_conditional_done.value or ()), \
            '死亡局误置一次性标志位'
    finally:
        uninstall_backend()
