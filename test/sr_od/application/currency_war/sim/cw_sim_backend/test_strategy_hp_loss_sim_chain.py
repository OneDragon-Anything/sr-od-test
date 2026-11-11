"""策略卡损血档位触发发放 sim 状态副本链测试(镜像 src = sim/cw_sim_backend.py
的 _resolve_battle 损血档位效果条目;kernel 触发函数单元面 =
kernel/cw_gain_chain/test_check_strategy_hp_loss_grants.py,本文件锁
sim 结算效果条目接入调用与状态副本里的值落地面)。

测试面依据 = 原稿锁面(§ 号 = 原稿节序)§4 锁 3/4/5 +
原稿评审锁(节点矩阵形态先例 = 同目录 test_strategy_win_gold_sim_
chain.py 的 T-130 锁 4):
- ①战斗类败局(hp_delta<0)→ 金笔+装备笔存在,金值 = 同拍现值 +
  5×桶数(同窗既有收入笔教训,T-130 R2-2);②胜局 → 零笔零累积;
  ③普通奖励关(恒胜白拿路径,强制败局掷点被改写)→ 零笔;④扑满局
  (不掉血豁免)→ 零笔;⑤死亡局(_game_over 早退)→ 零笔;
- 锁 4 保底截断真值差:hp=15 败局扣 40 → 记 14 → 零桶零发放(面值
  口径此局会错发 2 桶——防静默翻转);
- 锁 5 余数跨战结转:连续败局 15+10 → 第二局发 1 桶、accum 余 5;
- 装备笔计数断言前提 = 简易池 ∩ EQUIP_ACQUIRE_CONSEQUENCES = ∅
  (O6/T-116 先例:获得后果表扩员会静默扩断言面,空集守卫断言已登记);
- 驱动形态 = 出战动作触发结算(2026-10-29 流程模型);引擎驱动助手
  import 自 sim/test_sim_backend.py(已登记超限拆分债文件,禁追加,只
  import 复用不改);helper 扩展(自定义扣血强判/状态副本写包装)沿同目录
  先例自带同语义副本。
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

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    EQUIP_ACQUIRE_CONSEQUENCES,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_HP_LOSS_BUCKET_ASSUMPTION,
    equips_by_category,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BOSS_BRIEFING,
    SCREEN_BRIEFING,
    SCREEN_ENCOUNTER,
    SCREEN_INVEST_STRATEGY,
    SCREEN_MEGASTAR,
    SCREEN_PLANNER,
    SCREEN_PREP,
    SCREEN_SETTLE,
    SCREEN_SHOP,
    SCREEN_SUPPLY,
    SimBackend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_battle import (
    SIM_BATTLE_FACE,
    BattleOutcome,
)

_CARD = '保险'
_PIGGY_ENV = '经济过热'
_PLANE_TRANSITION = '货币战争-位面过渡'
_TRANSIT_SCREENS = (SCREEN_SETTLE, _PLANE_TRANSITION, SCREEN_INVEST_STRATEGY,
                    SCREEN_SUPPLY, SCREEN_ENCOUNTER, SCREEN_BOSS_BRIEFING,
                    SCREEN_MEGASTAR, SCREEN_PLANNER, SCREEN_SHOP)
_GOLD_PREFIX = 'sim:engine:strategy_hp_loss:'
_ACCUM_EV = 'strategy_hp_loss:accum:p1r3'
_DISCLOSURE_VALUE = 'bucket_carry_truth_diff_battle_only_v0'


@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(沿同目录同名 fixture 先例,fixture 不可跨文件
    import 故本文件自带同语义副本)。"""
    consume_defect_sink()
    yield
    set_defect_sink(None)
    consume_defect_sink()


def test_simple_pool_no_acquire_consequences() -> None:
    """锁 3 装备笔计数断言前提(空集守卫):简易池 ∩ 获得后果表 = ∅
    ——池内件获得零级联,「每档恰 1 件入栏」断言才成立;装备注册表
    扩员出带获得后果的新简易件时本前提红 = 断言面扩员显式申报
    (O6/T-116 先例)。"""
    assert set(equips_by_category('简易')) & \
        set(EQUIP_ACQUIRE_CONSEQUENCES) == set(), \
        '简易池出现带获得后果的件:装备笔计数断言面需随批重审'


def _record_world_writes(gs, monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic/write_logic_rand/observe 记录
    (通道, 字段名, evidence, sig, value, produced_by) 写序(透传真实现
    零行为变化;债文件禁追加故本文件自带副本,先例 =
    test_strategy_win_gold_sim_chain._record_world_writes)。"""
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


def _force_settle_delta(monkeypatch: pytest.MonkeyPatch, won: bool,
                        hp_delta: int) -> None:
    """强制胜负 + 自定义扣血结算输出(_force_settle 同形扩展 delta 轴
    ——锁 4 截断局/锁 5 采样对需定制扣血;patch 面 = 调用方模块命名
    空间绑定,定义模块 patch 对 from-import 调用点不可见)。"""
    import sr_od.application.currency_war.sim.cw_sim_backend as backend_mod
    monkeypatch.setattr(
        backend_mod, 'settle_battle',
        lambda rng, *, plane, round_num: BattleOutcome(
            won=won, progress=1.0 if won else 0.0, base_damage=None,
            progress_damage=None, hp_delta=hp_delta, face=SIM_BATTLE_FACE))


def _hold_card(gs) -> None:
    """持卡直置(注册状态容器直写 = 持卡事实单一源;不经 pick 链)。"""
    gs.write_logic(gs.active_strategies, [_CARD],
                   produced_by='test-seed', evidence='t:card', sig=_SIG)


def _prep_backend(seed: int, *, piggy: bool = False) -> SimBackend:
    """装配后端至 P1r1 备战屏(调用方负责 uninstall;先例 = 同目录
    test_strategy_win_gold_sim_chain._prep_backend 形)。piggy = 窗开
    前置扑满环境(窗口收尾 is_piggy_node 现读)。P1 序列现值
    P1r1 = reward 位。"""
    b = _backend(seed)
    if piggy:
        b.gs.observe(b.gs.active_env, _PIGGY_ENV, sig=_SIG_OBS)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP, '前置:未达 P1r1 备战屏'
    assert b.gs.node.value.kind == 'reward', '前置:P1r1 应为奖励位(现值序列)'
    return b


def _drive_to_kind_prep(monkeypatch: pytest.MonkeyPatch, b: SimBackend,
                        *, target_kind: str) -> None:
    """自当前窗驱动到指定位面 1 节点类型的备战窗(途经战斗/奖励节点
    全胜强制穿过,中间屏走现役驱动步;目标判定 = 节点窗场字段 kind
    序列真值;同目录 win 金币效果条目锁同形副本)。"""
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


def _gold_rows(calls: list[tuple]) -> list[tuple]:
    return [c for c in calls
            if c[1] == 'gold' and str(c[2] or '').startswith(_GOLD_PREFIX)]


def _equip_rows(calls: list[tuple]) -> list[tuple]:
    return [c for c in calls if c[1] == 'equips'
            and str(c[2] or '').startswith('strategy_hp_loss:')]


def _accum_rows(calls: list[tuple]) -> list[tuple]:
    return [c for c in calls if c[1] == 'strategy_hp_loss_accum'
            and c[0] == 'logic']


def test_battle_loss_pays_one_bucket(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 3①:战斗类败局(P1r3 battle 位,扣 23)→ 金笔+装备笔存在:
    金笔恰一笔(obs 族 sim:strategy,evidence strategy_hp_loss:p1r3,
    值 = 同拍现值 + 5×1 桶);装备笔恰 1 件(名 ∈ 简易池派生集);
    累积器两笔同窗相邻(23 入账 + 发放刻取模 3);金面零 logic 直写笔;
    披露键随发随局申报。"""
    b = _prep_backend(61)
    try:
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='battle')
        gold_before = int(gs.gold.value or 0)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle_delta(monkeypatch, won=False, hp_delta=-23)
        _start_battle_feed(gs)
        rows = _gold_rows(calls)
        assert len(rows) == 1, f'金笔数漂移: {[c[:3] for c in rows]}'
        row = rows[0]
        assert row[:2] == ('obs', 'gold'), f'通道漂移: {row[:2]}'
        assert row[2] == f'{_GOLD_PREFIX}p1r3', f'evidence 漂移: {row[2]}'
        assert row[3].family == 'obs' \
            and row[3].group_id == 'sim:strategy', f'sig 漂移: {row[3]}'
        assert row[4] == gold_before + 5, \
            f'金值漂移: {row[4]} != {gold_before}+5×1 桶'
        assert not [c for c in calls
                    if c[1] == 'gold' and c[0] in ('logic', 'rand')], \
            '金面出现 logic 直写笔'
        equip_rows = _equip_rows(calls)
        assert len(equip_rows) == 1, \
            f'装备笔数漂移: {[c[:3] for c in equip_rows]}'
        pool = set(equips_by_category('简易'))
        assert equip_rows[0][4][-1] in pool, \
            f'装备名出池: {equip_rows[0][4]!r}'
        assert str(equip_rows[0][2]).endswith('#equip'), \
            f'装备 evidence 漂移: {equip_rows[0][2]}'
        accum = _accum_rows(calls)
        assert [c[4] for c in accum] == [23, 3], \
            f'累积器两笔漂移(入账+取模): {[c[4] for c in accum]}'
        assert all(c[2] == _ACCUM_EV for c in accum), \
            f'累积 evidence 漂移: {[c[2] for c in accum]}'
        assert gs.strategy_hp_loss_accum.value == 3, '累积器终值漂移'
        assert b.disclosures.get(STRATEGY_HP_LOSS_BUCKET_ASSUMPTION) \
            == _DISCLOSURE_VALUE, '披露键未随发随局申报'
        assert b.screen_identity() == SCREEN_SETTLE, '结算后应泊结算屏'
    finally:
        uninstall_backend()


def test_battle_win_zero_pen(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 3②:战斗胜局 → 零笔零累积(触发判据 = 实际损血,胜局
    hp_delta=0 在触发函数首序短路;_settled_key 域内无任何 strategy_hp_
    loss 面)。"""
    b = _prep_backend(62)
    try:
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='battle')
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle_delta(monkeypatch, won=True, hp_delta=0)
        _start_battle_feed(gs)
        assert _gold_rows(calls) == [], '胜局误发金'
        assert _equip_rows(calls) == [], '胜局误发装备'
        assert _accum_rows(calls) == [], '胜局误入账'
        assert gs.strategy_hp_loss_accum.value == 0, '胜局误改累积器'
    finally:
        uninstall_backend()


def test_reward_free_win_zero_pen(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 3③:普通奖励关(恒胜白拿路径)→ 零笔——强制败局掷点被
    won=True/hp_delta=0 改写(M14 结构规则),损血结构性不存在。"""
    b = _prep_backend(63)
    try:
        gs = b.gs
        _hold_card(gs)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle_delta(monkeypatch, won=False, hp_delta=-40)
        _start_battle_feed(gs)
        assert _gold_rows(calls) == [], '奖励关误发金'
        assert _equip_rows(calls) == [], '奖励关误发装备'
        assert _accum_rows(calls) == [], '奖励关误入账'
        assert gs.strategy_hp_loss_accum.value == 0, '奖励关误改累积器'
    finally:
        uninstall_backend()


def test_piggy_exemption_zero_pen(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 3④:扑满局(不掉血豁免 M17)→ 零笔——败局掷点保留但
    hp_delta 改写 0,损血结构性不存在;收入笔照付(前置对拍 = 豁免只
    辖血不辖收入)。"""
    b = _prep_backend(64, piggy=True)
    try:
        gs = b.gs
        _hold_card(gs)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle_delta(monkeypatch, won=False, hp_delta=-40)
        _start_battle_feed(gs)
        income_rows = [c for c in calls
                       if c[1] == 'gold'
                       and c[2] == 'sim:engine:income:p1r1']
        assert len(income_rows) == 1, '前置:扑满收入笔应在结算拍落账'
        assert _gold_rows(calls) == [], '扑满局误发金'
        assert _equip_rows(calls) == [], '扑满局误发装备'
        assert _accum_rows(calls) == [], '扑满局误入账'
    finally:
        uninstall_backend()


def test_death_zero_pen_early_return(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 3⑤:死亡局(保底已用再次归零)→ 零笔(_game_over 提前
    return 在触发链前,天然不达调用点;累积器保持 0)。"""
    b = _prep_backend(65)
    try:
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='battle')
        gs.observe(gs.hp_floor_triggered, True, sig=_SIG_OBS)
        gs.observe(gs.hp, 5, sig=_SIG_OBS)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle_delta(monkeypatch, won=False, hp_delta=-23)
        _start_battle_feed(gs)
        assert _gold_rows(calls) == [], '死亡局误发金'
        assert _equip_rows(calls) == [], '死亡局误发装备'
        assert _accum_rows(calls) == [], '死亡局误入账'
        assert gs.strategy_hp_loss_accum.value == 0, '死亡局误改累积器'
        assert gs.hp.value == 0, '前置:死亡局 hp 应归零'
    finally:
        uninstall_backend()


def test_floor_truncation_truth_diff_zero_bucket(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 4:保底截断真值差——hp=15 败局扣 40 → 实际记 14(写值差,
    「损失」不超持有量)→ 零桶零发放;面值口径此局会错发 2 桶,本锁
    钉死防静默翻转(裁决点 3 默认案)。"""
    b = _prep_backend(66)
    try:
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='battle')
        gs.observe(gs.hp, 15, sig=_SIG_OBS)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle_delta(monkeypatch, won=False, hp_delta=-40)
        _start_battle_feed(gs)
        accum = _accum_rows(calls)
        assert [c[4] for c in accum] == [14], \
            f'真值记账漂移(应记写值差 14 非 outcome 面值 40): ' \
            f'{[c[4] for c in accum]}'
        assert _gold_rows(calls) == [], '截断局误发金(面值口径错发 2 桶)'
        assert _equip_rows(calls) == [], '截断局误发装备'
        assert gs.strategy_hp_loss_accum.value == 14, '累积器终值漂移'
        assert gs.hp.value == 1, '前置:首次保底应剩 1'
    finally:
        uninstall_backend()


def test_remainder_carryover_two_battles(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 5:余数跨战结转——连续败局扣 15 + 扣 10:第一局 0 桶零发放
    (余 15 留存),第二局累加至 25 发 1 桶(金 = 同拍现值 + 5,装备
    1 件)、accum 余 5(裁决点 2 默认案:全程累计读法)。"""
    b = _prep_backend(67)
    try:
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='battle')
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle_delta(monkeypatch, won=False, hp_delta=-15)
        _start_battle_feed(gs)
        assert _gold_rows(calls) == [], '第一局不足阈值误发金'
        assert _equip_rows(calls) == [], '第一局不足阈值误发装备'
        accum = _accum_rows(calls)
        assert [c[4] for c in accum] == [15] \
            and accum[0][2] == _ACCUM_EV, '第一局余数入账漂移'
        _drive_to_kind_prep(monkeypatch, b, target_kind='battle')
        gold_before = int(gs.gold.value or 0)
        _force_settle_delta(monkeypatch, won=False, hp_delta=-10)
        _start_battle_feed(gs)
        rows = _gold_rows(calls)
        assert len(rows) == 1, f'第二局金笔数漂移: {[c[:3] for c in rows]}'
        assert rows[0][2] == f'{_GOLD_PREFIX}p1r4', '第二局 evidence 漂移'
        assert rows[0][4] == gold_before + 5, \
            f'第二局金值漂移: {rows[0][4]} != {gold_before}+5×1 桶'
        assert len(_equip_rows(calls)) == 1, '第二局装备笔数漂移'
        assert gs.strategy_hp_loss_accum.value == 5, '余数结转终值漂移'
    finally:
        uninstall_backend()
