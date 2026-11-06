"""策略卡首领战后随机装备发放 sim 状态副本链测试(镜像 src =
sim/cw_sim_backend.py 的 _resolve_battle 首领战后效果条目;kernel 触发函数
单元面 = kernel/cw_gain_chain/test_check_strategy_boss_battle_grants.py,
本文件锁 sim 结算效果条目接入调用与状态副本里的值落地面)。

测试面依据 = 迭代设计 designs/T-166-qiang-zaishou.md §4 锁 2/3/4/5/6/9
+ REVIEW-T166(驱动与断言形态先例 = 同目录 test_strategy_encounter_
battle_grant_sim_chain.py / test_strategy_hp_loss_sim_chain.py):
- 持卡局 boss 节点(P1 序列现值末位)战斗结算后 equips 恰 +1 +
  ``strategy_boss_battle#<卡名>`` 前缀 evidence 笔(sig 组
  'sim:strategy';**断言用前缀匹配禁精确匹配**——gain_equipment 原语内
  追加 #equip 后缀,T-166 收尾批 D2 口径);非 boss 节点/未持卡零发放;
  败局存活也发(卡面无「胜利」限定 = 直读);死亡局不发放(调用点在死亡
  提前 return 之后);幂等 = _settled_key 既有守卫回归(同节点重放不
  双发);修饰局跟随 = 序列现值判定(非硬编码轮次);采样断言 = 名 ∈
  简易池派生集,禁手抄清单。
- 装备笔计数断言前提 = 简易池 ∩ EQUIP_ACQUIRE_CONSEQUENCES = ∅(空集
  守卫已登记 = test_strategy_hp_loss_sim_chain.py::
  test_simple_pool_no_acquire_consequences,同池同前提不重复立锁)。
- 驱动形态 = 出战动作触发结算(2026-10-29 流程模型);引擎驱动助手
  import 自 sim/test_sim_backend.py(已登记超限拆分债文件,禁追加,只
  import 复用不改);helper 副本(状态副本写包装/类型备战驱动/定参结算)
  沿同目录先例自带同语义拷贝。
"""
from __future__ import annotations

from types import SimpleNamespace

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
    equips_by_category,
)
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BOSS_BRIEFING,
    SCREEN_BRIEFING,
    SCREEN_ENCOUNTER,
    SCREEN_INVEST_ENV,
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

_CARD = '枪在手'
#: T-167 展开卡参数化扩名(designs/T-167-qiang-zaishou-plus.md §4 锁 2
#: +1 名;战后效果条目与模式卡逐字同句,端到端行身份 = evidence 前缀分卡)。
_CARD_PLUS = '枪在手+'
_MOD_ENV = '人身意外险'
_PLANE_TRANSITION = '货币战争-位面过渡'
_TRANSIT_SCREENS = (SCREEN_SETTLE, _PLANE_TRANSITION, SCREEN_INVEST_STRATEGY,
                    SCREEN_SUPPLY, SCREEN_ENCOUNTER, SCREEN_BOSS_BRIEFING,
                    SCREEN_MEGASTAR, SCREEN_PLANNER, SCREEN_SHOP)

_EVIDENCE_PREFIX = 'strategy_boss_battle#'


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
    test_strategy_hp_loss_sim_chain._prep_backend 形)。"""
    b = _backend(seed)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP, '前置:未达 P1r1 备战屏'
    return b


def _prep_backend_env(seed: int, env_name: str) -> SimBackend:
    """装配后端至 P1r1 备战屏,途经投资环境屏选环境(节点序列经环境注册
    写场字段 ``node_seq_by_plane``;先例 = 同目录 test_strategy_boss_gold
    ._backend env 分支形)。"""
    from sr_od.application.currency_war.kernel.cw_action_report import (
        report_action_pick_invest_env_param,
    )
    from sr_od.application.currency_war.sim.cw_sim_backend import (
        install_backend,
    )
    from sr_od.application.currency_war.sim.cw_sim_run_config import (
        RunConfig,
    )
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108,
        env_present=bool(env_name)))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
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


def _record_world_writes(gs, monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic/write_logic_rand/observe 记录
    (通道, 字段名, evidence, sig, value, produced_by) 写序(透传真实现
    零行为变化;债文件禁追加故本文件自带副本,先例 =
    test_strategy_hp_loss_sim_chain._record_world_writes)。"""
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
    """自当前窗驱动到指定位面 1 节点类型的备战窗(途经战斗/奖励节点
    全胜强制穿过,中间屏走现役驱动步;目标判定 = 节点窗场字段 kind
    序列真值;同目录 win 金币效果条目/损血效果条目锁同形副本)。"""
    gs = b.gs
    for _ in range(80):
        node = gs.node.value
        screen = b.screen_identity()
        if screen == SCREEN_PREP and node is not None \
                and node.kind == target_kind:
            return
        if screen in _TRANSIT_SCREENS:
            _drive_env_grant_step(b)
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
    """strategy_boss_battle 前缀写行(通道, 字段名, evidence, sig, …)。"""
    return [c for c in calls
            if c[1] == 'equips'
            and str(c[2] or '').startswith(_EVIDENCE_PREFIX)]


@pytest.mark.parametrize('card', [_CARD, _CARD_PLUS])
def test_boss_settle_grants_random_equip(
        card: str, monkeypatch: pytest.MonkeyPatch,
        _isolate_defect_buffer) -> None:
    """锁 2(sim 端到端发放真值;T-167 展开卡参数化 +1 名):持卡局 boss
    节点战斗结算后 equips 恰 +1(采样名 ∈ 简易池派生集,禁手抄清单)+
    strategy_boss_battle#<卡名> 前缀 evidence 笔(随机态通道,**前缀匹配
    禁精确匹配**——原语内追加 #equip 后缀;前缀带卡名段分卡归属,
    「枪在手」前缀不吞「枪在手+」笔),sig 单形态 = logic_action 族
    'sim:strategy' 组。"""
    b = _prep_backend(71)
    try:
        gs = b.gs
        _hold_card(gs, card=card)
        _drive_to_kind_prep(monkeypatch, b, target_kind='boss')
        equips_before = list(gs.equips.value or [])
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        rows = _grant_rows(calls)
        assert len(rows) == 1, \
            f'装备笔数漂移: {[c[:3] for c in rows]}'
        row = rows[0]
        pool = set(equips_by_category('简易'))
        assert row[4][-1] in pool, f'装备名出池: {row[4]!r}'
        assert row[4] == equips_before + [row[4][-1]], 'equips 应恰 +1'
        assert row[0] == 'rand', f'采样发放应走随机态通道: {row[0]}'
        assert str(row[2]).startswith(f'strategy_boss_battle#{card}'), \
            f'evidence 前缀未归 {card}: {row[2]}'
        assert str(row[2]).endswith('#equip'), f'evidence 漂移: {row[2]}'
        assert row[3].family == 'logic_action' \
            and row[3].group_id == 'sim:strategy', f'sig 组漂移: {row[3]}'
        assert b.screen_identity() == SCREEN_SETTLE, '结算后应泊结算屏'
    finally:
        uninstall_backend()


def test_non_boss_node_zero_grant(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 3(非 boss 节点零发放):持卡局普通战斗(P1 首个 battle 位)
    结算后零笔(节点类型条件,kind = 结算点现值)。"""
    b = _prep_backend(72)
    try:
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='battle')
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert _grant_rows(calls) == [], '非首领节点误写发放笔'
    finally:
        uninstall_backend()


def test_no_card_boss_zero_grant(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 4(未持卡零发放):未持卡局同一 boss 节点结算后零笔。"""
    b = _prep_backend(73)
    try:
        gs = b.gs
        _drive_to_kind_prep(monkeypatch, b, target_kind='boss')
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert _grant_rows(calls) == [], '未持卡误写发放笔'
    finally:
        uninstall_backend()


def test_loss_survival_still_grants(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 5a(败局存活也发):持卡局 boss 战败未死 → 装备照入栏(卡面无
    「胜利」限定 = 直读;调用点在胜败两态共同路径,败局待办登记之前)。"""
    b = _prep_backend(74)
    try:
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='boss')
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=False)
        _start_battle_feed(gs)
        assert b.screen_identity() == SCREEN_SETTLE, '败局存活(未进终局)'
        rows = _grant_rows(calls)
        assert len(rows) == 1, f'败局存活未发放: {[c[:3] for c in rows]}'
        assert rows[0][4][-1] in set(equips_by_category('简易')), \
            '败局存活发放名出池'
    finally:
        uninstall_backend()


def test_dead_battle_no_grant(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 5b(死亡局不发放):保底已用 + 濒死局 boss 战败 → hp 归零死亡
    提前 return 在调用点之前,零发放直接进终局(局终不见发放,与实机一致)。"""
    b = _prep_backend(75)
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
    finally:
        uninstall_backend()


def test_settled_key_guard_no_double_grant(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 6(幂等回归):同 boss 节点战斗重放(battle_resolve 重入)→
    _settled_key 既有守卫整段跳过,零二次发放零新增笔(防本效果条目绕过)。"""
    b = _prep_backend(76)
    try:
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='boss')
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        equips_after_first = list(gs.equips.value or [])
        assert len(equips_after_first) >= 1, '前置:首结算已入栏'
        calls = _record_world_writes(gs, monkeypatch)
        _start_battle_feed(gs)
        assert list(gs.equips.value or []) == equips_after_first, \
            '_settled_key 重入双发'
        assert _grant_rows(calls) == [], '重入零新增发放笔'
    finally:
        uninstall_backend()


def test_modified_plane_boss_follows_sequence(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """锁 9(修饰局跟随,序列现值判定非硬编码轮次):插入型修饰局
    (人身意外险,boss 位前插 supply)P1 序列的 boss 位次由序列真值
    派生(默认 P1 末位 r9 → 修饰局 r10);触发效果条目 node_kind 传结算点
    现值,序列重构零特判跟随。"""
    b = _prep_backend_env(77, _MOD_ENV)
    try:
        gs = b.gs
        _hold_card(gs)
        seq = list((gs.node_seq_by_plane.value or {}).get(1) or [])
        r_boss = seq.index('boss') + 1
        assert r_boss != 9 and seq[r_boss - 2] == 'supply', \
            f'修饰序列形状不符(应为 boss 前插 supply): {seq}'
        _drive_to_kind_prep(monkeypatch, b, target_kind='boss')
        assert gs.node.value.round_num == r_boss, \
            '前置:应达修饰序列 boss 位备战窗'
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        rows = _grant_rows(calls)
        assert len(rows) == 1, \
            f'修饰局 boss 结算未发放: {[c[:3] for c in rows]}'
        assert rows[0][4][-1] in set(equips_by_category('简易')), \
            '修饰局发放名出池'
    finally:
        uninstall_backend()
