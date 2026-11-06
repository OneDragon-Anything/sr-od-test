"""策略卡死亡救援 sim 世界链测试(镜像 src = sim/cw_sim_backend.py 的
_resolve_battle 死亡救援腿;kernel 触发函数单元面 =
kernel/cw_gain_chain/test_take_strategy_death_save.py,本文件锁
sim 结算折算点接线与 M-B 独立叠加序列的世界真值落地面)。

测试面依据 = 迭代设计 designs/T-323-cang-yishou.md §4 锁 3/4 + 用户裁定
2026-11-04(M-B 独立叠加 = 卡救先消耗,全局保底留给后续致死;序列
致死①→卡救→致死②→保底 1→致死③→局终;已过全局保底后拿卡仍可被救):
- 致死矩阵:①持卡败局致死 → hp 写 40 + 奖励两笔 + 一次性标志位置位 +
  hp_floor_triggered 零翻转(M-B 钉死)+ 结算环行 killed=False/hp_after=40
  + 建模假设披露键随局申报;②同局第二次致死 → 全局保底 hp=1(保底位
  翻真);③第三次致死 → dead 局终;④非致死败局 → 原路零涉;
  ⑤胜局(hp_delta=0)→ 救援预判恒假零涉;
- 锁 4 已过保底拿卡:先耗全局保底(hp=1)再持卡 → 下一次致死 → 卡救
  hp=40(M-B 与 M-A 的行为分叉点,M-A 下此局 = dead);
- 驱动形态 = 出战动作触发结算(2026-10-29 流程模型);引擎驱动助手
  import 自 sim/test_sim_backend.py(已登记超限拆分债文件,禁追加,只
  import 复用不改);helper 扩展(自定义扣血强判/世界写包装)沿同目录
  test_strategy_hp_loss_sim_chain.py 先例自带同语义副本。
"""
from __future__ import annotations

import pytest
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
    _backend,
    _close_shop_feed,
    _drive_env_grant_step,
    _start_battle_feed,
)

from sr_od.application.currency_war.kernel.cw_game_state import (
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_DEATH_SAVE_GRANTS,
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

_CARD = '藏一手'
_PLANE_TRANSITION = '货币战争-位面过渡'
_TRANSIT_SCREENS = (SCREEN_SETTLE, _PLANE_TRANSITION, SCREEN_INVEST_STRATEGY,
                    SCREEN_SUPPLY, SCREEN_ENCOUNTER, SCREEN_BOSS_BRIEFING,
                    SCREEN_MEGASTAR, SCREEN_PLANNER, SCREEN_SHOP)
_DS_PREFIX = 'strategy_death_save:'

#: 救援载荷(表载值现算,禁手抄——表漂移时本常量随 import 联动,断言面
#: 锁的是「载荷来自表」而非字面 40/30/80;表行值本身归 cw_investments
#: 表锁文件钉死)。
_SAVE_HP, _SAVE_XP, _SAVE_GOLD = STRATEGY_DEATH_SAVE_GRANTS[_CARD]
_ONCE_KEY = 'death_save_once_assumption'
_FLOOR_KEY = 'death_save_independent_floor_assumption'


@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(沿同目录同名 fixture 先例,fixture 不可跨文件
    import 故本文件自带同语义副本)。"""
    consume_defect_sink()
    yield
    set_defect_sink(None)
    consume_defect_sink()


def _record_world_writes(gs, monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic/write_logic_rand/observe 记录
    (通道, 字段名, evidence, sig, value, produced_by) 写序(透传真实现
    零行为变化;先例 = test_strategy_hp_loss_sim_chain._record_world_
    writes 同形副本;每测试包装一次,拍间清表防重复包装)。"""
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
    """强制胜负 + 自定义扣血结算输出(_force_settle 同形扩展 delta 轴;
    patch 面 = 调用方模块命名空间绑定,定义模块 patch 对 from-import
    调用点不可见)。"""
    import sr_od.application.currency_war.sim.cw_sim_backend as backend_mod
    monkeypatch.setattr(
        backend_mod, 'settle_battle',
        lambda rng, *, plane, round_num: BattleOutcome(
            won=won, progress=1.0 if won else 0.0, base_damage=None,
            progress_damage=None, hp_delta=hp_delta, face=SIM_BATTLE_FACE))


def _hold_card(gs) -> None:
    """持卡直置(注册容器直写 = 持卡事实单一源;不经 pick 链)。"""
    gs.write_logic(gs.active_strategies, [_CARD],
                   produced_by='test-seed', evidence='t:card', sig=_SIG)


def _prep_backend(seed: int) -> SimBackend:
    """装配后端至 P1r1 备战屏(调用方负责 uninstall;先例 = 同目录
    test_strategy_hp_loss_sim_chain._prep_backend 形)。"""
    b = _backend(seed)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP, '前置:未达 P1r1 备战屏'
    return b


def _drive_to_kind_prep(monkeypatch: pytest.MonkeyPatch, b: SimBackend,
                        *, target_kind: str) -> None:
    """自当前窗驱动到指定节点类型的备战窗(途经战斗/奖励节点全胜强制
    穿过,中间屏走现役驱动步;同目录 win 金腿锁同形副本)。"""
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
            _force_settle_delta(monkeypatch, won=True, hp_delta=0)
            _start_battle_feed(gs)
        else:
            raise AssertionError(
                f'未预期屏 {screen!r}(target={target_kind})')
    raise AssertionError(f'驱动步数超限:未达 {target_kind} 备战窗')


def _ds_rows(calls: list[tuple]) -> list[tuple]:
    """救援写端行(evidence 含 strategy_death_save: 前缀,sim:engine:
    前缀为 observe 面包装同命中)。"""
    return [c for c in calls if _DS_PREFIX in str(c[2] or '')]


def _settle_lethal(monkeypatch: pytest.MonkeyPatch, b: SimBackend,
                   calls: list[tuple]) -> None:
    """致死败局结算(扣血 = 当前 hp 现值全扣 → 恰致死;扣量从现值现算,
    对驱动途中的 hp 漂移鲁棒;先清写记录,断言面只看本拍)。"""
    del calls[:]
    _force_settle_delta(monkeypatch, won=False,
                        hp_delta=-int(b.gs.hp.value or 0))
    _start_battle_feed(b.gs)


def test_rescue_floor_death_sequence(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 3①②③ M-B 独立叠加全序列:致死①→卡救(hp=40+奖励两笔+一次性标志位
    置位+保底位零翻转)→致死②→全局保底 hp=1(保底位翻真,卡救不耗
    保底)→致死③→dead 局终(hp=0)。三拍接续断言 = 用户裁定 2026-11-04
    「叠加,先消耗这个」的直接序列化。"""
    b = _prep_backend(71)
    try:
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='battle')
        calls = _record_world_writes(gs, monkeypatch)
        # —— 致死①:救援拍 ——
        gold_before = int(gs.gold.value or 0)
        _settle_lethal(monkeypatch, b, calls)
        rows = _ds_rows(calls)
        # hp 笔恰一笔(obs 族,值 = 表载救援值);金笔 = 现值 + 表载金;
        # 一次性标志位写笔置位 True(produced_by 署名救援写端);保底位零翻转(M-B)。
        hp_rows = [c for c in rows if c[1] == 'hp']
        assert len(hp_rows) == 1 and hp_rows[0][4] == _SAVE_HP \
            and hp_rows[0][0] == 'obs', \
            f'救援 hp 笔漂移: {[(c[0], c[2], c[4]) for c in hp_rows]}'
        gold_rows = [c for c in rows if c[1] == 'gold']
        assert len(gold_rows) == 1 \
            and gold_rows[0][4] == gold_before + _SAVE_GOLD, \
            f'救援金笔漂移: {[(c[2], c[4]) for c in gold_rows]}'
        latch_rows = [c for c in rows
                      if c[1] == 'strategy_death_save_used']
        assert len(latch_rows) == 1 and latch_rows[0][4] is True \
            and latch_rows[0][0] == 'logic', \
            f'一次性标志位写笔漂移: {[(c[0], c[4]) for c in latch_rows]}'
        assert gs.hp_floor_triggered.value is None, \
            '救援局误翻全局保底位(M-B:救援不耗保底)'
        assert gs.hp.value == _SAVE_HP, '救援后 hp 漂移'
        xp_rows = [c for c in calls if c[1] == 'xp' and c[0] == 'logic'
                   and _DS_PREFIX in str(c[2] or '')]
        assert len(xp_rows) == 1, '救援经验笔缺失(grant_xp 经验腿)'
        # 结算环行:救援局 = 败局存活(killed=False)+ hp_after=40。
        tail = gs.settlement_ring.last_row()
        assert tail is not None and tail.killed is False \
            and tail.hp_after == _SAVE_HP, \
            f'救援局结算环行漂移: killed={tail.killed} ' \
            f'hp={tail.hp_after}'
        # 建模假设披露键随局申报(随发随局)。
        assert b.disclosures.get(_ONCE_KEY) == 'assumed_v0', \
            '一次性假设披露键未申报'
        assert b.disclosures.get(_FLOOR_KEY) == 'assumed_v0', \
            '独立叠加假设披露键未申报'
        # —— 致死②:一次性标志位挡卡救,全局保底接盘 ——
        _drive_to_kind_prep(monkeypatch, b, target_kind='battle')
        _settle_lethal(monkeypatch, b, calls)
        assert _ds_rows(calls) == [], '第二次致死误再救援(一次性标志位失效)'
        assert gs.hp.value == 1, '全局保底未接盘(应写 1)'
        assert gs.hp_floor_triggered.value is True, '保底位未翻真'
        # —— 致死③:保底已用再归零 → 局终 ——
        _drive_to_kind_prep(monkeypatch, b, target_kind='battle')
        _settle_lethal(monkeypatch, b, calls)
        assert _ds_rows(calls) == [], '第三次致死误救援'
        assert gs.hp.value == 0, '致死③未局终(应 hp=0 死亡)'
    finally:
        uninstall_backend()


def test_floor_consumed_then_card_still_saves(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 4 已过保底拿卡:无卡局先耗全局保底(hp=1)→ 中途持卡 → 下一次
    致死 → 卡救 hp=40(M-B:两槽独立,拿卡前耗保底不废卡救;M-A 共享槽
    读法下此局 = dead——本锁钉死两模型分叉点的默认案形态)。"""
    b = _prep_backend(72)
    try:
        gs = b.gs
        # 无卡致死①:全局保底接盘(hp=1,救援零涉)。
        _drive_to_kind_prep(monkeypatch, b, target_kind='battle')
        calls = _record_world_writes(gs, monkeypatch)
        _settle_lethal(monkeypatch, b, calls)
        assert gs.hp.value == 1 and gs.hp_floor_triggered.value is True, \
            '前置:无卡致死应由全局保底接盘'
        assert _ds_rows(calls) == [], '无卡局误救援'
        # 中途持卡 + 致死②:卡救独立触发(M-B 分叉点)。
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='battle')
        _settle_lethal(monkeypatch, b, calls)
        hp_rows = [c for c in _ds_rows(calls) if c[1] == 'hp']
        assert len(hp_rows) == 1 and hp_rows[0][4] == _SAVE_HP, \
            '已过保底拿卡未被救(M-B 独立叠加断裂)'
        assert gs.hp.value == _SAVE_HP, '卡救后 hp 漂移'
    finally:
        uninstall_backend()


def test_non_lethal_loss_no_rescue(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 3④:非致死败局(扣血后 hp>0)→ 原路零涉(致死预判不等式
    不成立,救援函数不被调;hp 落点 = apply_hp_outcome 正常写)。"""
    b = _prep_backend(73)
    try:
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='battle')
        hp_before = int(gs.hp.value or 0)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle_delta(monkeypatch, won=False,
                            hp_delta=-(hp_before // 2))
        _start_battle_feed(gs)
        assert _ds_rows(calls) == [], '非致死败局误触发救援'
        assert gs.hp.value == hp_before - hp_before // 2, \
            '非致死败局 hp 落点漂移(应走 apply_hp_outcome 原路)'
        assert gs.hp_floor_triggered.value is None, '非致死局误翻保底位'
    finally:
        uninstall_backend()


def test_win_no_rescue(monkeypatch: pytest.MonkeyPatch,
                       _isolate_defect_buffer) -> None:
    """锁 3⑤:胜局(hp_delta=0)→ 救援预判恒假零涉(delta<0 首闸;
    奖励关恒胜改写/扑满豁免同归 delta=0 形态,结构性零涉不另设)。"""
    b = _prep_backend(74)
    try:
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='battle')
        hp_before = int(gs.hp.value or 0)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle_delta(monkeypatch, won=True, hp_delta=0)
        _start_battle_feed(gs)
        assert _ds_rows(calls) == [], '胜局误触发救援'
        assert gs.hp.value == hp_before, '胜局 hp 漂移(应等值写)'
    finally:
        uninstall_backend()
