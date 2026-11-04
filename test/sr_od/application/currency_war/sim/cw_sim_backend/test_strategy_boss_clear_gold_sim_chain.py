"""策略卡首领通关价值金 sim 世界链测试(镜像 src = sim/cw_sim_backend.py
的 _resolve_battle 首领通关价值金腿;kernel 触发函数单元面 =
kernel/cw_gain_chain/test_check_strategy_boss_clear_gold.py,本文件锁
sim 结算腿接线与世界真值落地面)。

测试面依据 = 迭代设计 designs/T-332-souda-che.md §4 锁 3/锁 4(驱动与
断言形态先例 = 同目录 test_strategy_boss_completion_grant_sim_chain.py
/ test_strategy_win_gold_sim_chain.py):
- 首个 won boss(「通关下一个首领节点」)→ 金笔恰一笔(obs 族
  'sim:strategy' 组,evidence = ``sim_evidence`` 前缀形
  ``sim:engine:strategy:boss_clear_value:p<位面>r<轮>``——kernel 触发
  函数内惰性 import sim_evidence(先例 = check_env_star_merge_gold/
  check_strategy_hp_loss_grants 金笔同款;前缀承载 _MISMATCH_SUPPRESS_
  PREFIXES 失配抑制消费面)+ 闩落(strategy_conditional_
  done 纯卡名);
- 一次性闩:闩落后续位面首领(P2 首领位)再胜零金笔零新闩(「下一个」
  恰一次,函数内闩自管防跨 boss 重复);
- 败局存活(won=False)零发放零闩(「通关」= 胜利限定,与武器批发商
  无胜利限定形对形分化);死亡局(hp_floor_triggered 濒死败局)零发放
  零闩直接进终局(挂点在死亡提前 return 之后);
- 驱动形态 = 出战动作触发结算(2026-10-29 流程模型);引擎驱动助手
  import 自 sim/test_sim_backend.py(在册超限拆分债文件,禁追加,只
  import 复用不改);helper 副本(世界写包装/类型备战驱动/定参结算)
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

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    board_bench_char_value_sum,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    DeployedView,
    Unit,
    consume_defect_sink,
    set_defect_sink,
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

_CARD = '搜打撤'
_PLANE_TRANSITION = '货币战争-位面过渡'
_TRANSIT_SCREENS = (SCREEN_SETTLE, _PLANE_TRANSITION, SCREEN_INVEST_STRATEGY,
                    SCREEN_SUPPLY, SCREEN_ENCOUNTER, SCREEN_BOSS_BRIEFING,
                    SCREEN_MEGASTAR, SCREEN_PLANNER, SCREEN_SHOP)

_EV_PREFIX = 'sim:engine:strategy:boss_clear_value:'


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
    test_strategy_boss_completion_grant_sim_chain._prep_backend 形)。"""
    b = _backend(seed)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP, '前置:未达 P1r1 备战屏'
    return b


def _record_world_writes(gs, monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic/write_logic_rand/observe 记录
    (通道, 字段名, evidence, sig, value, produced_by) 写序(透传真实现
    零行为变化;债文件禁追加故本文件自带副本,先例 =
    test_strategy_boss_completion_grant_sim_chain._record_world_writes)。"""
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
    """持卡直置(注册容器直写 = 持卡事实单一源;不经 pick 链)。"""
    gs.write_logic(gs.active_strategies, [_CARD],
                   produced_by='test-seed', evidence='t:card', sig=_SIG)


def _seed_board(gs) -> None:
    """板面直置(前排 1★2费花火 = 2 金;价值增量断言受控,不经获得链;
    战斗为抽象结算不改板面,值贯穿全程恒定)。"""
    gs.observe(gs.deployed,
               DeployedView(front_slots=[Unit(char_id='花火', star=1,
                                              equips=[]), None, None, None],
                            back_slots=[]),
               sig=_SIG_OBS)


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
    序列真值;同目录 boss 战后腿锁同形副本)。"""
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


def _gold_rows(calls: list[tuple]) -> list[tuple]:
    """strategy:boss_clear_value 前缀金笔行(通道, 字段名, evidence,
    sig, value, …)。"""
    return [c for c in calls
            if c[1] == 'gold'
            and str(c[2] or '').startswith(_EV_PREFIX)]


def _latch_rows(calls: list[tuple]) -> list[tuple]:
    """strategy:boss_clear_value 前缀闩写行(strategy_conditional_done
    字段,evidence 同证据基)。"""
    return [c for c in calls
            if c[1] == 'strategy_conditional_done'
            and str(c[2] or '').startswith(_EV_PREFIX)]


def test_first_won_boss_gold_and_latch(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 3a(sim 端到端发放真值):持卡局首个 won boss 结算 → 金笔
    恰一笔(obs 族 'sim:strategy' 组,evidence 带结算点时点段,值 =
    紧邻前一笔 gold 现值 + 板面价值)且闩恰一笔落卡名。"""
    b = _prep_backend(85)
    try:
        gs = b.gs
        _hold_card(gs)
        _seed_board(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='boss')
        node = gs.node.value
        ev = f'{_EV_PREFIX}p{node.plane}r{node.round_num}'
        board_value = board_bench_char_value_sum(gs)
        assert board_value > 0, '前置:板面直置后价值应 > 0'
        gold_before = int(gs.gold.value or 0)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        rows = _gold_rows(calls)
        assert len(rows) == 1, f'金笔数漂移: {[c[:3] for c in rows]}'
        row = rows[0]
        assert row[:2] == ('obs', 'gold'), f'通道漂移: {row[:2]}'
        assert row[2] == ev, f'evidence 漂移: {row[2]!r} (期望 {ev!r})'
        assert row[3].family == 'obs' \
            and row[3].group_id == 'sim:strategy', f'sig 漂移: {row[3]}'
        # 值增量对收入免疫:金笔 = 紧邻前一笔 gold 现值 + 板面价值
        #(结算段收入笔在挂点前落账则取其值;无前序笔 = 收入已在窗开
        # 拍入账,退回记录前现值——两种形态 boss 位结算都可达)。
        all_gold = [c for c in calls if c[1] == 'gold']
        idx = all_gold.index(row)
        prev = all_gold[idx - 1][4] if idx > 0 else gold_before
        assert row[4] == prev + board_value, \
            f'金值漂移: {row[4]} != {prev}+{board_value}'
        latches = _latch_rows(calls)
        assert len(latches) == 1, f'闩笔数漂移: {[c[:3] for c in latches]}'
        assert latches[0][0] == 'logic', '闩 = 逻辑态通道'
        assert _CARD in (gs.strategy_conditional_done.value or ()), '闩未落'
        assert b.screen_identity() == SCREEN_SETTLE, '结算后应泊结算屏'
    finally:
        uninstall_backend()


def test_second_won_boss_no_repeat_after_latch(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 3b(一次性闩跨位面):P1 首领胜局闩落 → 驱动至 P2 首领位再
    胜 → 零金笔零新闩(「下一个」恰一次;幂等守卫防同战斗重放,闩防
    跨 boss 重复)。"""
    b = _prep_backend(86)
    try:
        gs = b.gs
        _hold_card(gs)
        _seed_board(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='boss')
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert _CARD in (gs.strategy_conditional_done.value or ()), \
            '前置:首首领胜局闩未落'
        calls = _record_world_writes(gs, monkeypatch)
        _drive_to_kind_prep(monkeypatch, b, target_kind='boss')
        assert gs.node.value.plane == 2, \
            f'前置:应达 P2 首领位备战窗(plane={gs.node.value.plane})'
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        # 闩后零重复判据 = 本腿前缀笔零新增(gold 全列表会混入 P2 途程
        # 其他收入通道产出,非本腿语义面)。
        assert _gold_rows(calls) == [], '闩后跨位面首领重复发金'
        assert _latch_rows(calls) == [], '闩后零新闩笔'
        assert _CARD in (gs.strategy_conditional_done.value or ()), '闩漂移'
    finally:
        uninstall_backend()


def test_boss_loss_survival_zero_gold_and_latch(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 4a(boss 败局存活零发放):持卡局首领战败未死 → 零金笔零闩
    (「通关」= 胜利限定直读,与武器批发商无胜利限定形对形分化;败局
    存活泊结算屏,闩未消耗 = 后续首领通关仍可触发)。"""
    b = _prep_backend(87)
    try:
        gs = b.gs
        _hold_card(gs)
        _seed_board(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='boss')
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=False)
        _start_battle_feed(gs)
        assert b.screen_identity() == SCREEN_SETTLE, '败局存活(未进终局)'
        assert _gold_rows(calls) == [], 'boss 败局误发金'
        assert _latch_rows(calls) == [], 'boss 败局误闩'
        assert _CARD not in (gs.strategy_conditional_done.value or ()), \
            '败局闩应未消耗'
    finally:
        uninstall_backend()


def test_dead_battle_zero_gold_and_latch(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 4b(死亡局零发放):保底已用 + 濒死局首领战败 → hp 归零死亡
    提前 return 在挂点之前,零金笔零闩直接进终局(局终不见发放,与实机
    一致;死亡早退形态仅 sim _resolve_battle 可构造,kernel 镜像不可
    表达)。"""
    b = _prep_backend(88)
    try:
        gs = b.gs
        _hold_card(gs)
        _seed_board(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='boss')
        gs.observe(gs.hp_floor_triggered, True, sig=_SIG_OBS)
        gs.observe(gs.hp, 1, sig=_SIG_OBS)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=False)
        _start_battle_feed(gs)
        assert b.done and b.screen_identity() == SCREEN_LOBBY, \
            '败局致死应进终局'
        assert _gold_rows(calls) == [], '死亡局误发金'
        assert _latch_rows(calls) == [], '死亡局误闩'
        assert _CARD not in (gs.strategy_conditional_done.value or ()), \
            '死亡局误闩'
    finally:
        uninstall_backend()
