"""策略卡胜利结算条件金 sim 状态副本链测试(镜像 src = sim/cw_sim_backend.py
的 _resolve_battle 策略胜利金币效果条目;kernel 触发函数单元面 =
kernel/cw_gain_chain/test_check_strategy_win_gold_grants.py,本文件锁
sim 结算效果条目接入调用与状态副本里的值落地面)。

测试面依据 = 设计稿(原件已退役;§ 号 = 原稿节序)§4 锁 4/锁 7 +
已退役评审稿(r1-S2 修法:节点类型矩阵四态——防实现批把接入调用误包进
kind in COMBAT_NODE_TYPES 守卫而静默翻转触发域默认案〔全部结算节点〕):
- ①普通奖励关(恒胜白拿路径)持卡有佩佩 → 金笔存在;
- ②扑满胜局 → 金笔存在,值 = 锚定同拍收入笔后合计(income 落账 observe
  居调用点之前,按收入笔现值 + 佩佩数断言);
- ③扑满败局(won=False 豁免 hp_delta=0)→ 零金笔(双判据必要性的接入调用
  级锁);④战斗类败局 → 零金笔;
- evidence = sim:engine:strategy_win_gold:p<位面>r<轮>(sim_evidence 前缀
  + 写点 tag 独立分域可过滤审计),sig 单形态 = obs 族 'sim:strategy'
  (组名沿在役惯例 obs/logic 共用);
- 金面禁直写:全程零 logic 金笔(observe 状态副本数值面写端通道分工);
- 披露键(锁 7 随局面):发金拍 setdefault 触发域假设键,值非空。
- 驱动形态 = 出战动作触发结算(2026-10-29 流程模型);引擎驱动助手
  import 自 sim/test_sim_backend.py(已登记超限拆分债文件,禁追加,只
  import 复用不改);扑满态 = 窗开前置 active_env ∈ PIGGY_ENV_NAMES
  (窗口收尾 is_piggy_node 现读,收入递延快照在窗开拍冻结)。
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
    BenchSlot,
    BenchView,
    Unit,
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_WIN_GOLD_SCOPE_ASSUMPTION,
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

_CARD = '招财狗'
_PIGGY_ENV = '经济过热'
_PLANE_TRANSITION = '货币战争-位面过渡'
_TRANSIT_SCREENS = (SCREEN_SETTLE, _PLANE_TRANSITION, SCREEN_INVEST_STRATEGY,
                    SCREEN_SUPPLY, SCREEN_ENCOUNTER, SCREEN_BOSS_BRIEFING,
                    SCREEN_MEGASTAR, SCREEN_PLANNER, SCREEN_SHOP)
_EV_PREFIX = 'sim:engine:strategy_win_gold:'


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


def _hold_card(gs) -> None:
    """持卡直置(注册状态容器直写 = 持卡事实单一源;不经 pick 链,佩佩入席
    由调用方受控直置,与 T-105 sim 锁 _hold_card 同形)。"""
    gs.write_logic(gs.active_strategies, [_CARD],
                   produced_by='test-seed', evidence='t:card', sig=_SIG)


def _seed_peipei(gs, n: int) -> None:
    """备战席直置 n 只 1★ 佩佩(计数域受控,不经获得链)。"""
    slots = [BenchSlot(kind='unit', unit=Unit(char_id='佩佩', star=1))
             for _ in range(n)]
    slots += [BenchSlot(kind='empty')] * (9 - n)
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)


def _win_gold_rows(calls: list[tuple]) -> list[tuple]:
    return [c for c in calls
            if c[1] == 'gold' and str(c[2] or '').startswith(_EV_PREFIX)]


def _prep_backend(seed: int, *, piggy: bool = False) -> SimBackend:
    """装配后端至 P1r1 备战屏(调用方负责 uninstall;先例 = 同目录
    到级金币效果条目锁 _prep_backend 形)。piggy = 窗开前置扑满环境(窗口收尾
    is_piggy_node 现读 → 收入递延快照在窗开拍冻结)。P1 序列现值
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
    序列真值;T-105 战后发放 sim 锁同形)。"""
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


def test_reward_node_win_pays_gold(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 4① + 锁 7:普通奖励关(恒胜白拿路径)持卡 1 佩佩 → 结算后
    金笔恰一笔(obs 族 sim:strategy,evidence strategy_win_gold:p1r1,
    值 = 结算前现值 + 1;非扑满奖励节点结算拍无同拍收入笔,窗开收入
    已在 gold_before 之前入账);金面零 logic 笔;披露键随发随局申报。"""
    b = _prep_backend(51)
    try:
        gs = b.gs
        _hold_card(gs)
        _seed_peipei(gs, 1)
        gold_before = int(gs.gold.value or 0)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        rows = _win_gold_rows(calls)
        assert len(rows) == 1, f'金笔数漂移: {[c[:3] for c in rows]}'
        row = rows[0]
        assert row[:2] == ('obs', 'gold'), f'通道漂移: {row[:2]}'
        assert row[2] == 'sim:engine:strategy_win_gold:p1r1', \
            f'evidence 漂移: {row[2]}'
        assert row[3].family == 'obs' \
            and row[3].group_id == 'sim:strategy', f'sig 漂移: {row[3]}'
        assert row[4] == gold_before + 1, \
            f'金值漂移: {row[4]} != {gold_before}+1'
        assert not [c for c in calls
                    if c[1] == 'gold' and c[0] in ('logic', 'rand')], \
            '金面出现 logic 直写笔'
        assert b.disclosures.get(STRATEGY_WIN_GOLD_SCOPE_ASSUMPTION) \
            == 'all_settlement_nodes_v0', '披露键未随发随局申报'
        assert b.screen_identity() == SCREEN_SETTLE, '结算后应泊结算屏'
    finally:
        uninstall_backend()


def test_piggy_win_pays_gold_after_income_row(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 4②:扑满胜局(won=True, hp_delta=0)→ 金笔存在,值 = 锚定
    同拍收入笔后合计(扑满收入落账 observe 居本效果条目调用点之前,本效果条目值 =
    收入笔现值 + 佩佩数;序 = income 笔先、win 金笔后)。"""
    b = _prep_backend(52, piggy=True)
    try:
        gs = b.gs
        _hold_card(gs)
        _seed_peipei(gs, 1)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        income_rows = [c for c in calls
                       if c[1] == 'gold'
                       and c[2] == 'sim:engine:income:p1r1']
        assert len(income_rows) == 1, '前置:扑满收入笔应在结算拍落账'
        rows = _win_gold_rows(calls)
        assert len(rows) == 1, f'金笔数漂移: {[c[:3] for c in rows]}'
        assert rows[0][2] == 'sim:engine:strategy_win_gold:p1r1', \
            'evidence 漂移'
        assert rows[0][4] == income_rows[0][4] + 1, \
            f'金值漂移: {rows[0][4]} != 收入笔 {income_rows[0][4]} + 1'
        assert calls.index(income_rows[0]) < calls.index(rows[0]), \
            '序漂移:win 金笔应在同拍收入笔之后'
    finally:
        uninstall_backend()


def test_piggy_loss_zero_gold(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 4③:扑满败局(won=False 豁免 hp_delta=0)→ 零金笔(双判据
    必要性的接入调用级锁——not won 在函数内短路;收入笔照付败局形,胜败
    分野只在策略金币效果条目)。"""
    b = _prep_backend(53, piggy=True)
    try:
        gs = b.gs
        _hold_card(gs)
        _seed_peipei(gs, 1)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=False)
        _start_battle_feed(gs)
        assert _win_gold_rows(calls) == [], '扑满败局误发金'
        assert [c for c in calls if c[1] == 'gold'
                and c[2] == 'sim:engine:income:p1r1'], \
            '前置:扑满败局收入照付(败局 = 基础+息)'
        assert b.screen_identity() == SCREEN_SETTLE, '败局存活(未进终局)'
    finally:
        uninstall_backend()


def test_battle_loss_zero_gold(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 4④:战斗类败局(P1r3 battle 位)→ 零金笔(胜利判据短路;
    败局存活泊结算屏)。"""
    b = _prep_backend(54)
    try:
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='battle')
        _seed_peipei(gs, 1)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=False)
        _start_battle_feed(gs)
        assert _win_gold_rows(calls) == [], '战斗败局误发金'
        assert b.screen_identity() == SCREEN_SETTLE, '败局存活(未进终局)'
    finally:
        uninstall_backend()
