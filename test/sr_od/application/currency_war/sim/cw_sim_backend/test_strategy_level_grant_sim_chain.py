"""sim 策略卡到级金腿状态副本链测试(镜像 src = sim/cw_sim_backend.py 的
_on_node_advance / _on_node_advance_terminal 双点接入调用段;kernel 决策函数
单元面 = kernel/cw_gain_chain/test_check_strategy_level_grants.py,本文件
锁 sim 接入调用与状态副本里的值落地面)。

测试面依据 = 迭代设计 designs/T-108-chengzhang-jijin.md §4 锁 1/2/3/6/7/
8/10(实现批修正:锁 8 文字面 = 现役 NODE_XP_BY_TYPE × PLANE_NODE_TABLES
(含 P3)常量下完整 P1+P2+P3 持卡局全程零发放,经验写源 = 节点经验 ×
选卡即时腿两源,上界 96 < 门槛 194 封顶 7 级):
- 跨级发放主链(锁 1,直构状态容器强制 level=8 + xp 贴近阈值〔XP_TO_NEXT_
  LEVEL 单一源,8 级直构可得〕):推进跨 9 → 金 +40 恰一次,双通道形态
  = 金 observe 独立笔(evidence sim:engine:strategy:level_gold:<卡名>,
  obs 族 sim:strategy)+ 一次性标志位 write_logic(producer strategy_level_grant,
  logic 族 sim:strategy);金零 logic 笔(金面禁直写);发放拍 = 经验
  入账后、窗收入前;
- 一次性封账(锁 2):发放后继续推进零再写零再一次性标志位;
- 表外卡零写(锁 3):持 STRATEGY_ECONOMY 已登记非到级卡(boss 金族)
  强制 9 级推进 → 金/一次性标志位全零动;
- 状态检查型语义(锁 6):拿卡时已 level ≥ 9 → 下一次节点推进发放;
- 局终跨级(锁 7):末节点经验跨 9 → 发放先于局终声明(双点之二);
- 休眠边界(锁 8):完整 P1+P2+P3 持卡局(seed 37 胜局锚)全程零发放
  ∧ 全程等级 < 9——经验常量/序列变更使 9 级可达时本锁先红,触发边界
  重申报(防静默激活);
- 披露键(锁 10):语义假设键 + 休眠边界键恒已登记。

驱动形态复用声明:引擎驱动助手 import 自 sim/test_sim_backend.py 与
同目录 test_p3_win_terminal.py(已登记先例,禁追加只 import;整局驱动
_handle_click_source/_maybe_finish_wait 直调先例 = 本目录 boss 金腿锁)。
"""
from __future__ import annotations

import pytest
from test.sr_od.application.currency_war.sim.cw_sim_backend.test_p3_win_terminal import (  # noqa: E501
    _drive_step,
)
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG_OBS,
    _backend,
    _drive_env_grant_step,
    _force_settle,
    _node_advance_feed,
    _start_battle_feed,
)

from sr_od.application.currency_war.kernel.cw_game_state import (
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    DISCLOSURE_RUN_COMPLETE,
    DISCLOSURE_STRATEGY_LEVEL_DORMANT,
    DISCLOSURE_STRATEGY_LEVEL_SEMANTICS,
    SCREEN_BRIEFING,
    SCREEN_PREP,
    SimBackend,
    uninstall_backend,
)

_CARD = '成长基金'
_OUT_OF_SCOPE = '特战资金'
_GOLD_EV = 'sim:engine:strategy:level_gold:成长基金'
_DONE_EV = 'strategy:level_gold:成长基金'


@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(沿同目录同名 fixture 先例,fixture 不可跨文件
    import 故本文件自带同语义副本)。"""
    consume_defect_sink()
    yield
    set_defect_sink(None)
    consume_defect_sink()


def _record_level_writes(gs, monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic/write_logic_rand/observe 记录
    (通道, 字段名, evidence, sig, value, produced_by) 写序(透传真实现
    零行为变化;_record_all_writes 同形扩展 value/produced_by 两轴——
    债文件禁追加故本文件自带副本)。"""
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
    """装配后端至 P1r1 备战屏(调用方负责 uninstall;先例 = 同目录
    boss 金腿锁 _backend 形)。"""
    b = _backend(seed)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP, '前置:未达 P1r1 备战屏'
    return b


def _grant_calls(calls: list[tuple]) -> list[tuple]:
    return [c for c in calls if c[2] == _GOLD_EV
            or (c[1] == 'strategy_conditional_done' and c[2] == _DONE_EV)]


def test_cross_level_grant_main_chain_then_latch(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """跨级发放主链 + 一次性封账(锁 1/2):直构 level=8 + xp=(71,72)
    (8→9 门槛 72,cw_economy XP_TO_NEXT_LEVEL 单一源)→ 推进跨 9 →
    金 +40 恰一次(observe 独立笔,值 = 跨级前现值 + 40)、一次性标志位写一笔
    (producer strategy_level_grant)、发放拍 = xp:node 之后窗收入之前、
    金零 logic 笔;再推进一级(级仍 ≥9)→ 零再写零再一次性标志位。"""
    b = _prep_backend(23)
    try:
        gs = b.gs
        gs.observe(gs.active_strategies, [_CARD],
                   evidence='test:hold', sig=_SIG_OBS)
        gs.observe(gs.level, 8, sig=_SIG_OBS)
        gs.observe(gs.xp, (71, 72), sig=_SIG_OBS)
        gold_before = int(gs.gold.value or 0)
        calls = _record_level_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        _node_advance_feed(gs, trigger='settle_confirm')
        legs = _grant_calls(calls)
        assert len(legs) == 2, f'发放笔数漂移: {[c[:3] for c in legs]}'
        gold_leg, done_leg = legs
        # 金腿:observe 独立笔(obs 族 sim:strategy),值 = 跨级前 +40
        assert gold_leg[:2] == ('obs', 'gold'), f'金通道漂移: {gold_leg[:2]}'
        assert gold_leg[3].family == 'obs' \
            and gold_leg[3].group_id == 'sim:strategy', \
            f'金 sig 漂移: {gold_leg[3]}'
        assert gold_leg[4] == gold_before + 40, \
            f'金值漂移: {gold_leg[4]} != {gold_before}+40'
        # 一次性标志位写笔:write_logic(producer strategy_level_grant,logic 族
        # sim:strategy),值 = (卡名,)
        assert done_leg[:2] == ('logic', 'strategy_conditional_done'), \
            f'一次性标志位通道漂移: {done_leg[:2]}'
        assert done_leg[3].family == 'logic_action' \
            and done_leg[3].group_id == 'sim:strategy', \
            f'一次性标志位 sig 漂移: {done_leg[3]}'
        assert done_leg[4] == (_CARD,), f'一次性标志位值漂移: {done_leg[4]!r}'
        assert done_leg[5] == 'strategy_level_grant', \
            f'producer 漂移: {done_leg[5]!r}'
        # 发放拍序:金腿在 xp:node 入账后、窗收入前(跨级事件拍)
        idx_xp = next(i for i, c in enumerate(calls)
                      if c[1] == 'level' and c[2] == 'sim:engine:xp:node')
        idx_income = next(i for i, c in enumerate(calls)
                          if c[1] == 'gold' and str(c[2] or '').startswith(
                              'sim:engine:income:'))
        assert idx_xp < calls.index(gold_leg) < idx_income, \
            f'发放拍漂移: xp@{idx_xp} gold@{calls.index(gold_leg)} ' \
            f'income@{idx_income}'
        # 金面禁直写:全程零 logic 金笔(双通道分工)
        assert not [c for c in calls
                    if c[1] == 'gold' and c[0] in ('logic', 'rand')], \
            '金面出现 logic 直写笔'
        # 落一次性标志位定后一次性封账(锁 2):级仍 ≥9 再推进 → 零新增笔
        #(驱动步全屏分派推进至节点序位真前进;途经策略屏固定定卡加油
        # 站 = 零判读域写;战斗恒胜桩防死亡分支截断)
        n_after_first = len(calls)
        assert int(gs.level.value or 0) >= 9, '前置:跨级未达 9'
        pos_before = b._node_pos()
        for _ in range(8):
            if b.done or b._node_pos() != pos_before:
                break
            _drive_env_grant_step(b)
        assert b._node_pos() != pos_before, '前置:续推进未发生'
        assert _grant_calls(calls[n_after_first:]) == [], '一次性标志位后再发放'
        assert gs.strategy_conditional_done.value == (_CARD,), '一次性标志位值漂移'
    finally:
        uninstall_backend()


def test_state_semantics_hold_at_level_grants(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """状态检查型语义(锁 6):先置 level=9 再持卡(拿卡时已达标)→
    下一次节点推进发放——等级 = 状态容器现值非事件流,禁实现批顺手改成
    严格跨越型而无锁。"""
    b = _prep_backend(24)
    try:
        gs = b.gs
        gs.observe(gs.level, 9, sig=_SIG_OBS)
        gs.observe(gs.active_strategies, [_CARD],
                   evidence='test:hold', sig=_SIG_OBS)
        gold_before = int(gs.gold.value or 0)
        calls = _record_level_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        _node_advance_feed(gs, trigger='settle_confirm')
        legs = _grant_calls(calls)
        assert len(legs) == 2, f'拿卡已达标未发放: {[c[:3] for c in legs]}'
        assert legs[0][4] == gold_before + 40, \
            f'金值漂移: {legs[0][4]} != {gold_before}+40'
        assert legs[1][4] == (_CARD,), '一次性标志位值漂移'
    finally:
        uninstall_backend()


def test_out_of_scope_card_zero_write(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """表外卡零写(锁 3):持 STRATEGY_ECONOMY 已登记非到级卡(特战资金
    boss 金族)+ 强制 9 级 → 推进零金笔零一次性标志位写笔(交集过滤按字段现值)。"""
    b = _prep_backend(25)
    try:
        gs = b.gs
        gs.observe(gs.active_strategies, [_OUT_OF_SCOPE],
                   evidence='test:hold', sig=_SIG_OBS)
        gs.observe(gs.level, 9, sig=_SIG_OBS)
        calls = _record_level_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        _node_advance_feed(gs, trigger='settle_confirm')
        assert _grant_calls(calls) == [], '表外卡误发放'
        assert gs.strategy_conditional_done.value in (None, ()), '表外卡误置一次性标志位'
    finally:
        uninstall_backend()


def test_terminal_cross_grants_before_game_over(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """局终跨级(锁 7):末节点经验入账跨 9 → 发放先于局终声明(双点之
    二;直构 = 备战窗强置级/xp 后直调局终推进 handler,handler 内序 =
    经验入账 → 金腿 → 局终披露与收尾)。"""
    b = _prep_backend(26)
    try:
        gs = b.gs
        gs.observe(gs.active_strategies, [_CARD],
                   evidence='test:hold', sig=_SIG_OBS)
        gs.observe(gs.level, 8, sig=_SIG_OBS)
        gs.observe(gs.xp, (71, 72), sig=_SIG_OBS)
        gold_before = int(gs.gold.value or 0)
        calls = _record_level_writes(gs, monkeypatch)
        b._on_node_advance_terminal()
        legs = _grant_calls(calls)
        assert len(legs) == 2, f'局终点未发放: {[c[:3] for c in legs]}'
        assert legs[0][4] == gold_before + 40, \
            f'局终金值漂移: {legs[0][4]} != {gold_before}+40'
        assert legs[1][4] == (_CARD,) \
            and legs[1][5] == 'strategy_level_grant', f'局终一次性标志位形态漂移: {legs[1]}'
        # 发放先于局终声明:handler 收尾后局终位与披露齐备
        assert b.done, '局终位未收尾'
        assert gs.strategy_conditional_done.value == (_CARD,), '一次性标志位未随局终存续'
        assert b.disclosures.get(DISCLOSURE_RUN_COMPLETE) \
            == 'survived_p3_boss', '局终披露漂移'
    finally:
        uninstall_backend()


def test_dormant_full_p3_run_zero_grant(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """休眠边界(锁 8,慢桶):完整 P1+P2+P3 持卡局(seed 37 胜局锚,
    _drive_step 全程分派)全程零发放 ∧ 全程等级 < 9——现役经验两源
    (节点经验表 × 选卡即时腿)上界 96 < 3→9 级门槛 194,封顶 7 级;
    经验常量/序列变更使 9 级可达时本锁先红 = 触发边界重申报。"""
    b = _prep_backend(37)
    try:
        gs = b.gs
        gs.observe(gs.active_strategies, [_CARD],
                   evidence='test:hold', sig=_SIG_OBS)
        calls = _record_level_writes(gs, monkeypatch)
        max_level = 0
        for _ in range(4096):
            if b.done:
                break
            _drive_step(b, 37)
            max_level = max(max_level, int(gs.level.value or 0))
        assert b.done, '4096 步内未收尾(流程异常)'
        assert DISCLOSURE_RUN_COMPLETE in b.disclosures, \
            '前置:非胜局锚(seed 37 应走完 P3 存活终局)'
        assert _grant_calls(calls) == [], '休眠局出现到级发放'
        assert gs.strategy_conditional_done.value in (None, ()), '休眠局误置一次性标志位'
        assert max_level < 9, \
            f'9 级已达(上界 ≥ 门槛): max_level={max_level} —— 休眠前提' \
            '失效,触发边界重申报'
    finally:
        uninstall_backend()


def test_disclosure_keys_registered() -> None:
    """披露键(锁 10):语义假设键 + 休眠边界键恒已登记(全程披露面,
    与采样无关;值串 = 纯声明)。"""
    b = _prep_backend(27)
    try:
        assert b.disclosures[DISCLOSURE_STRATEGY_LEVEL_SEMANTICS] \
            == 'pick_already_at_level_also_grants_unverified'
        assert b.disclosures[DISCLOSURE_STRATEGY_LEVEL_DORMANT] \
            == 'bound_96_lt_threshold_194_cap_level7'
    finally:
        uninstall_backend()
