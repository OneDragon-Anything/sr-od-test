"""sim 策略卡到级装备腿世界链测试(镜像 src = sim/cw_sim_backend.py 的
_on_node_advance / _on_node_advance_terminal 双点接线段;kernel 检查腿
单元面 = kernel/cw_gain_chain/test_check_strategy_level_equip_grants.py,
本文件锁 sim 接线、宝钻世界联动与休眠数值边界)。

测试面依据 = 迭代设计 designs/T-141-zuanshi-shangren.md §4 锁 3/7/8/9:
- 推进点跨级发放主链(锁 2 sim 面):直构 level=8 + xp 贴阈,推经跨 9 →
  equips logic 写 + 闩一笔(producer strategy_level_equip_grant,logic 族
  sim:strategy)+ 发放拍 = 经验入账后;闩后续推进零再写(锁 3);
- 局终跨级(锁 7):末节点经验跨 9 → 发放先于局终声明(双点之二);
- 宝钻世界联动(锁 8):发放后 diamond_count +1 / deploy_cap = level +
  财富宝钻数 / back_layout +1(on_diamond_acquired 经 sim 接线调用);
- 休眠边界(锁 9,数值口径):节点经验合计 70 固化(NODE_XP_BY_TYPE ×
  PLANE_NODE_TABLES)+ 即时腿注册面上界 < 3→9 级累计门槛 194、封顶
  8 级——常量/注册行变更使 9 级可达时本锁先红 = 触发边界重申报;
  即时腿键集显式扩集制(新增即时腿 = 红 → 休眠上界随批重申报;
  免战牌 +30 入注册面随批重申报,合计 134 仍 < 194)。

驱动形态复用声明:引擎驱动助手 import 自 sim/test_sim_backend.py 与
同目录 test_p3_win_terminal.py(在册先例,禁追加只 import;整局驱动
_handle_click_source/_maybe_finish_wait 直调先例 = 同目录到级金腿锁)。
"""
from __future__ import annotations

import pytest
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG_OBS,
    _backend,
    _drive_env_grant_step,
    _force_settle,
    _node_advance_feed,
    _start_battle_feed,
)

from sr_od.application.currency_war.kernel.cw_economy import XP_TO_NEXT_LEVEL
from sr_od.application.currency_war.kernel.cw_game_state import (
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_ECONOMY,
)
from sr_od.application.currency_war.kernel.cw_node_schedule import (
    PLANE_NODE_TABLES,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    DISCLOSURE_RUN_COMPLETE,
    NODE_XP_BY_TYPE,
    SCREEN_BRIEFING,
    SCREEN_PREP,
    SimBackend,
    uninstall_backend,
)

_CARD = '钻石商人'
_EQUIP = '财富宝钻'
_EQUIP_EV = f'strategy_level_grant:{_CARD}#equip'
_LATCH_EV = f'strategy_level_grant:{_CARD}'
_PRODUCER = 'strategy_level_equip_grant'


@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(沿同目录同名 fixture 先例,fixture 不可跨文件
    import 故本文件自带同语义副本)。"""
    consume_defect_sink()
    yield
    set_defect_sink(None)
    consume_defect_sink()


def _record_writes(gs, monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic/write_logic_rand/observe 记录
    (通道, 字段名, evidence, sig, value, produced_by) 写序(透传真实现
    零行为变化;同目录到级金腿锁 _record_level_writes 同形副本)。"""
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


def _prep_backend(seed: int) -> SimBackend:
    """装配后端至 P1r1 备战屏(调用方负责 uninstall;先例 = 同目录到级
    金腿锁 _backend 形)。"""
    b = _backend(seed)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP, '前置:未达 P1r1 备战屏'
    return b


def _equip_legs(calls: list[tuple]) -> list[tuple]:
    return [c for c in calls if c[2] in (_EQUIP_EV, _LATCH_EV)]


def test_advance_point_cross_grant_then_latch(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """推进点跨级发放主链 + 一次性封账(锁 2 sim 面/锁 3):直构 level=8
    + xp=(71,72)(8→9 门槛 72)→ 推进跨 9 → equips logic 写恰一次
    (evidence strategy_level_grant:<卡>#equip,sig logic 族 sim:strategy,
    producer 专名)+ 闩一笔同基串;发放拍 = 节点经验入账后;闩后继续
    推进零再写零再闩。"""
    b = _prep_backend(28)
    try:
        gs = b.gs
        gs.observe(gs.active_strategies, [_CARD],
                   evidence='test:hold', sig=_SIG_OBS)
        gs.observe(gs.level, 8, sig=_SIG_OBS)
        gs.observe(gs.xp, (71, 72), sig=_SIG_OBS)
        calls = _record_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        _node_advance_feed(gs, trigger='settle_confirm')
        legs = _equip_legs(calls)
        assert len(legs) == 2, f'发放笔数漂移: {[c[:3] for c in legs]}'
        equip_leg, latch_leg = legs
        # 发放通道 = anchor 规则家族现值:sim 世界 prep_anchored 恒 False
        #(置位写端 = live reconcile_tracking,sim 不经)→ rand=False 确定
        # 事件经 anchor_aware_write 落随机态(未锚定期落账 = 未验证推算,
        # sim 无观察覆盖值随写即真值;T-102 tick 腿 sim 侧同规则,T-5 宝钻
        # 发放 write_logic_rand 同族先例);闩 = 登记事实直写 write_logic
        #(T-108 sim 闩同形)。
        assert equip_leg[:2] == ('rand', 'equips'), \
            f'发放通道漂移: {equip_leg[:2]}'
        assert equip_leg[3].family == 'logic_action' \
            and equip_leg[3].group_id == 'sim:strategy', \
            f'发放 sig 漂移: {equip_leg[3]}'
        assert equip_leg[4] == [_EQUIP], f'发放值漂移: {equip_leg[4]!r}'
        assert equip_leg[5] == _PRODUCER, \
            f'producer 漂移: {equip_leg[5]!r}'
        assert latch_leg[:2] == ('logic', 'strategy_conditional_done'), \
            f'闩通道漂移: {latch_leg[:2]}'
        assert latch_leg[3].group_id == 'sim:strategy' \
            and latch_leg[4] == (_CARD,) and latch_leg[5] == _PRODUCER, \
            f'闩形态漂移: {latch_leg}'
        # 发放拍序:装备腿在节点经验入账后(跨级事件拍,先于新节点窗)
        idx_xp = next(i for i, c in enumerate(calls)
                      if c[1] == 'level' and c[2] == 'sim:engine:xp:node')
        assert idx_xp < calls.index(equip_leg), '发放拍早于经验入账'
        # 一次性封账(锁 3):级仍 ≥9 续推进 → 零新增腿(驱动步全屏分派
        # 推进至节点序位真前进;战斗恒胜桩防死亡分支截断)
        n_after_first = len(calls)
        pos_before = b._node_pos()
        for _ in range(8):
            if b.done or b._node_pos() != pos_before:
                break
            _drive_env_grant_step(b)
        assert b._node_pos() != pos_before, '前置:续推进未发生'
        assert _equip_legs(calls[n_after_first:]) == [], '闩后再发放'
        assert gs.strategy_conditional_done.value == (_CARD,), '闩值漂移'
    finally:
        uninstall_backend()


def test_terminal_cross_grant_world_coupling_before_disclosure(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """局终跨级 + 宝钻世界联动(锁 7/8):末节点经验入账跨 9 → 发放先于
    局终声明(双点之二;直构 = 备战窗强置级/xp 后直调局终推进 handler,
    handler 内序 = 经验入账 → 装备腿 → 局终披露与收口);发放后宝钻回调
    三写 = diamond_count +1 / deploy_cap = level + 财富宝钻数 /
    back_layout +1(世界数值面 observe,sim 世界写即真值)。"""
    b = _prep_backend(29)
    try:
        gs = b.gs
        gs.observe(gs.active_strategies, [_CARD],
                   evidence='test:hold', sig=_SIG_OBS)
        gs.observe(gs.level, 8, sig=_SIG_OBS)
        gs.observe(gs.xp, (71, 72), sig=_SIG_OBS)
        back_before = int(gs.back_layout.value)
        calls = _record_writes(gs, monkeypatch)
        b._on_node_advance_terminal()
        legs = _equip_legs(calls)
        assert len(legs) == 2, f'局终点未发放: {[c[:3] for c in legs]}'
        assert legs[0][4] == [_EQUIP] and legs[1][4] == (_CARD,), \
            f'局终发放形态漂移: {legs}'
        # 宝钻世界联动三写(锁 8;回调消费返回值,发放同窗 equips 已含
        # 新宝钻 → deploy_cap = 9 + 1)
        assert int(gs.diamond_count.value) == 1, 'diamond_count 未 +1'
        assert int(gs.deploy_cap.value) == 9 + 1, \
            f'deploy_cap 漂移: {gs.deploy_cap.value!r} != level 9 + 宝钻 1'
        assert int(gs.back_layout.value) == min(9, back_before + 1), \
            'back_layout 未 +1'
        # 发放先于局终声明:handler 收口后局终位与披露齐备
        assert b.done, '局终位未收口'
        assert gs.strategy_conditional_done.value == (_CARD,), '闩未随局终存续'
        assert b.disclosures.get(DISCLOSURE_RUN_COMPLETE) \
            == 'survived_p3_boss', '局终披露漂移'
    finally:
        uninstall_backend()


def test_dormant_boundary_numeric() -> None:
    """休眠边界数值锁(锁 9):节点经验合计 70 固化(NODE_XP_BY_TYPE ×
    PLANE_NODE_TABLES 全三位面)+ 即时腿注册面(STRATEGY_ECONOMY
    xp_instant>0,键集显式扩集制)上界 < 3→9 级累计门槛 194、派生封顶
    恰 8 级——常量/注册行变更使上界 ≥ 门槛时本锁先红 = 触发边界重申报
    (防静默激活;免战牌 +30、固定理财 +4、固定理财+ +6 各随批重申报,
    合计 144 仍 < 194,余量见断言消息)。"""
    node_xp_total = sum(NODE_XP_BY_TYPE[k]
                        for seq in PLANE_NODE_TABLES.values() for k in seq)
    assert node_xp_total == 70, \
        f'节点经验合计漂移: {node_xp_total} != 70 —— 经验常量/序列变更,' \
        f'休眠边界重申报'
    instant = {name: eff.xp_instant
               for name, eff in STRATEGY_ECONOMY.items()
               if eff.xp_instant > 0}
    assert instant == {'伟大征服': 12, '成长的快乐': 4, '固定理财': 4,
                         '固定理财+': 6, '空仓+': 10, '经验到账': 10, '气氛组+': 8,
                         '免战牌': 30}, \
        f'即时腿注册面扩集: {instant} —— 新即时腿 = 休眠上界随批重申报'
    bound = node_xp_total + sum(instant.values())
    threshold_9 = sum(XP_TO_NEXT_LEVEL[lv] for lv in range(3, 9))
    assert threshold_9 == 194, \
        f'3→9 级门槛漂移: {threshold_9} != 194 —— 升级表变更,重申报'
    assert bound < threshold_9, \
        f'休眠前提失效: 上界 {bound} ≥ 门槛 {threshold_9} —— 9 级可达,' \
        f'触发边界重申报'
    cum = 0
    reach = 3
    for lv in range(3, 10):
        if cum + XP_TO_NEXT_LEVEL[lv] <= bound:
            cum += XP_TO_NEXT_LEVEL[lv]
            reach = lv + 1
        else:
            break
    assert reach == 8, \
        f'封顶等级漂移: {reach} != 8 —— 上界 {bound} 可达 {reach} 级,' \
        f'休眠口径重申报'
