"""策略卡羁绊条件战后发放 sim 世界链测试(镜像 src = sim/cw_sim_backend.py
的 _resolve_battle 武装拍挂点 + _begin_node_window 交付拍挂点;kernel
触发函数单元面 = kernel/cw_gain_chain/test_check_strategy_bond_battle_
grants.py 与 test_discharge_strategy_bond_battle_grants.py,本文件锁
sim 双挂点接线与世界真值落地面)。

测试面依据 = 迭代设计 designs/T-172-buyao-xiaokan-women-de-jiban.md
§4 锁 1/2/3/4/5/7 + REVIEW-T172(驱动与断言形态先例 = 同目录
test_strategy_boss_battle_grant_sim_chain.py):
- 两拍全链:持卡局合格战斗(任意节点 kind)结算拍武装(armed True)→
  下一节点窗开交付 equips 恰 +5(逐件 ∈ 星徽池派生集,禁手抄清单)+
  ``strategy_bond_battle#<卡名>`` 前缀 evidence 笔(sig 组
  'sim:strategy';**断言用前缀匹配禁精确匹配**——gain_equipment 原语
  内追加 #equip 后缀)+ armed 消费 False;
- 可重复链锁(无 done 一次性标志位,卡面无「首次」限定 = 战后触发族直读):连续
  两场合格战斗各交付 1 次(armed 消费-再武装链);
- 条件不满足(7 激活板)零武装零写;未持卡零武装;死亡局不武装(挂点
  在死亡提前 return 之后,局终不见发放);
- 幂等回归 = 既有守卫(同节点战斗重放 _settled_key 整段跳过;窗重放
  面 = armed 消费后非 True 结构性短路,重入零双发);
- 板面直构形态注记(8 门槛需 ≥8 激活羁绊,构成式写明防后人误判不可
  构造):独立羁绊 6 名各 1 人(tiers=(1,) 单人即激活)+ 治疗 2 人
  (tiers=(2,))+ 护盾 2 人(同 2)+ 贝洛伯格借同持 2 人(娜塔莎/
  杰帕德)×1 = 9 激活 ≥ 8;负控板去杰帕德 = 7 激活(治疗 2 + 独立 6,
  贝洛伯格/护盾双双跌回 1 人不激活)。布洛妮娅系选边型双羁绊角色直构
  引入选边分支,避开(独立计入口径由其余 6 名覆盖)。**直构双源同喂
  义务**:board_by_row 身份聚合只算 factions+flows 不含 independent
  (cw_board_by_row._trait_tags 口径),独立羁绊计数只有 board 容器
  (左面板直读口径)可承载——直构须 deployed 注入 + board 直写两源
  同值,单喂 deployed 则独立 6 名全漏计(激活 = 3 误负控)。
- 驱动形态 = 出战动作触发结算(2026-10-29 流程模型);引擎驱动助手
  import 自 sim/test_sim_backend.py(已登记超限拆分债文件,禁追加,只
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

from sr_od.application.currency_war.kernel.cw_game_state import (
    DeployedView,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    equips_by_category,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SCREEN_LOBBY,
    SCREEN_PREP,
    SCREEN_SETTLE,
    SimBackend,
    uninstall_backend,
)

_CARD = '不要小看我们的羁绊'
_EVIDENCE_PREFIX = 'strategy_bond_battle#'

#: 中途过屏集合(settle/过渡/补给/遭遇/简报/巨星/升星/商店/投资策略;
#: 驱动步 = _drive_env_grant_step 单步,先例 = 同目录 win 金腿锁同形)。
_PLANE_TRANSITION = '货币战争-位面过渡'
_TRANSIT_SCREENS = (SCREEN_SETTLE, _PLANE_TRANSITION, '货币战争-投资策略',
                    '货币战争-补给', '货币战争-遭遇节点',
                    '货币战争-BOSS简报', '货币战争-盛会之星',
                    '货币战争-银狼升星', '货币战争-商店')

#: 板面直构双源(board 容器 = 左面板口径含独立羁绊计数——board_by_row
#: 身份聚合只算 factions+flows 不含 independent,独立行只有左面板可读,
#: 双源 max 融合下两源须同喂;deployed 注入 = 身份口径)。full = 9 激活
#: ≥ 8;short(去杰帕德:贝洛伯格/护盾跌回 1 人)= 7 激活负控。
_BOND_BOARD_FULL_DICT: dict[str, int] = {
    '大守护者': 1, '救世主': 1, '头号玩家': 1, '挚爱之人': 1,
    '魔术师': 1, '命运卜者': 1, '治疗': 2, '护盾': 2, '贝洛伯格': 2,
}
_BOND_BOARD_SHORT_DICT: dict[str, int] = {
    '大守护者': 1, '救世主': 1, '头号玩家': 1, '挚爱之人': 1,
    '魔术师': 1, '命运卜者': 1, '治疗': 2, '贝洛伯格': 1, '护盾': 1,
}
#: 8+ 激活直构板(构成式见模块 docstring;4 前排 + 6 后排)。
_BOND_BOARD_FULL: tuple[tuple[str, str], ...] = (
    ('姬子·启行', 'front'), ('娜塔莎', 'front'), ('砂金', 'front'),
    ('杰帕德', 'front'),
    ('白厄', 'back'), ('银狼LV.999', 'back'), ('昔涟', 'back'),
    ('Archer', 'back'), ('黑天鹅', 'back'), ('藿藿', 'back'),
)
#: 7 激活负控板(去杰帕德:贝洛伯格/护盾跌回 1 人)。
_BOND_BOARD_SHORT: tuple[tuple[str, str], ...] = tuple(
    u for u in _BOND_BOARD_FULL if u[0] != '杰帕德')


@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(沿同目录同名 fixture 先例,fixture 不可跨文件
    import 故本文件自带同语义副本)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        consume_defect_sink,
        set_defect_sink,
    )
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


def _hold_card(gs, *, card: str = _CARD) -> None:
    """持卡直置(注册容器直写 = 持卡事实单一源;不经 pick 链)。"""
    gs.write_logic(gs.active_strategies, [card],
                   produced_by='test-seed', evidence='t:card', sig=_SIG)


def _inject_bond_board(gs, *, short: bool) -> None:
    """羁绊板直构(双源同喂:deployed 行域注入 = 身份口径 + board 容器
    直写 = 左面板口径——board_by_row 身份聚合只算 factions+flows 不含
    independent,独立羁绊计数只有 board 容器可承载,双源 max 融合下
    直构须两源同值,与实机「board = 左面板 OCR 真值」同构)。"""
    front = [Unit(char_id=n, star=1) for n, row in _BOND_BOARD_FULL
             if row == 'front']
    units = _BOND_BOARD_SHORT if short else _BOND_BOARD_FULL
    back = [Unit(char_id=n, star=1) for n, row in units if row == 'back']
    if short:
        front = [u for u in front if u.char_id != '杰帕德']
    gs.observe(gs.deployed,
               DeployedView(front_slots=front, back_slots=back),
               sig=_SIG_OBS)
    gs.observe(gs.board,
               dict(_BOND_BOARD_SHORT_DICT if short
                    else _BOND_BOARD_FULL_DICT),
               sig=_SIG_OBS)


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


def _equip_grant_rows(calls: list[tuple]) -> list[tuple]:
    """strategy_bond_battle 前缀装备写行(通道, 字段名, evidence, …)。"""
    return [c for c in calls
            if c[1] == 'equips'
            and str(c[2] or '').startswith(_EVIDENCE_PREFIX)]


def _arm_records(calls: list[tuple]) -> list[tuple]:
    """武装标记写行(结算拍 arm 笔)。"""
    return [c for c in calls
            if c[1] == 'strategy_bond_battle_armed']


def _drive_to_kind_prep(monkeypatch: pytest.MonkeyPatch, b: SimBackend,
                        *, target_kind: str) -> None:
    """自当前窗驱动到指定位面 1 节点类型的备战窗(途经战斗/奖励节点
    全胜强制穿过,中间屏走现役驱动步;目标判定 = 节点窗场字段 kind
    序列真值;同目录 win 金腿/损血腿锁同形副本)。"""
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


def test_settle_arms_then_window_delivers_five(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 1(两拍全链 sim 端到端):持卡 + 8 激活板 → P1 首个战斗结算
    拍 armed True(evidence ``strategy_bond_battle#arm:<卡名>``)→ 下一
    节点窗开交付 equips 恰 +5(逐件 ∈ 星徽池、前缀 evidence 笔、
    'sim:strategy' 组、随机态通道)+ armed 消费 False。"""
    b = _prep_backend(81)
    try:
        gs = b.gs
        _hold_card(gs)
        _inject_bond_board(gs, short=False)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert b.screen_identity() == SCREEN_SETTLE, '结算后应泊结算屏'
        arms = _arm_records(calls)
        assert len(arms) == 1 and arms[0][4] is True, \
            f'结算拍未武装: {[c[:5] for c in arms]}'
        assert str(arms[0][2]) == f'strategy_bond_battle#arm:{_CARD}', \
            f'武装笔 evidence 漂移: {arms[0][2]!r}'
        # 结算拍零发放(发放时点 = 下一节点窗开,两拍制时点保真)
        assert _equip_grant_rows(calls) == [], '结算拍误发放'
        equips_before = list(gs.equips.value or [])
        _drive_env_grant_step(b)
        rows = _equip_grant_rows(calls)
        assert len(rows) == 5, f'窗开交付笔数漂移: {[c[:3] for c in rows]}'
        pool = set(equips_by_category('星徽'))
        assert [r[4][-1] for r in rows] == \
            list(gs.equips.value or [])[len(equips_before):], \
            '入栏序应 = 写序'
        assert all(r[4][-1] in pool for r in rows), '发放名出池'
        assert list(gs.equips.value or []) == \
            equips_before + [r[4][-1] for r in rows], 'equips 应恰 +5'
        for r in rows:
            assert r[0] == 'rand', '采样发放应走随机态通道'
            assert str(r[2]).startswith(
                f'strategy_bond_battle#{_CARD}'), \
                f'evidence 前缀漂移: {r[2]!r}'
            assert r[3].family == 'logic_action' \
                and r[3].group_id == 'sim:strategy', f'sig 组漂移: {r[3]}'
        assert gs.strategy_bond_battle_armed.value is False, \
            '交付后武装应消费'
    finally:
        uninstall_backend()


def test_below_threshold_zero_arm_zero_grant(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 2(条件不满足零武装):持卡 + 7 激活板 → 结算拍零武装、下一
    节点窗零发放笔(无 strategy_bond_battle 笔)。"""
    b = _prep_backend(82)
    try:
        gs = b.gs
        _hold_card(gs)
        _inject_bond_board(gs, short=True)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert b.screen_identity() == SCREEN_SETTLE
        assert _arm_records(calls) == [], '不足阈值误武装'
        _drive_env_grant_step(b)
        assert _equip_grant_rows(calls) == [], '不足阈值窗开误发放'
    finally:
        uninstall_backend()


def test_no_card_zero_arm_zero_grant(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 3(未持卡零武装):条件满足板、active_strategies 无本卡 →
    零武装零发放。"""
    b = _prep_backend(83)
    try:
        gs = b.gs
        _inject_bond_board(gs, short=False)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert b.screen_identity() == SCREEN_SETTLE
        assert _arm_records(calls) == [], '未持卡误武装'
        _drive_env_grant_step(b)
        assert _equip_grant_rows(calls) == [], '未持卡窗开误发放'
    finally:
        uninstall_backend()


def test_repeatable_two_qualified_battles_deliver_twice(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 4(可重复链锁):板面真值恒 ≥8 激活,途经战斗全部合格——
    全程武装笔数 = 合格战斗数 N,交付笔数 = 5 × N 精确配对(每场合格
    战斗恰获其下一节点窗 1 次交付),armed True→False 交替链 ≥2 次 =
    消费-再武装(禁单发形态并存)。"""
    b = _prep_backend(84)
    try:
        gs = b.gs
        _hold_card(gs)
        _inject_bond_board(gs, short=False)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert gs.strategy_bond_battle_armed.value is True, '首战未武装'
        for _ in range(60):
            delivers = _equip_grant_rows(calls)
            if len(delivers) >= 10:
                break
            screen = b.screen_identity()
            if screen in _TRANSIT_SCREENS:
                _drive_env_grant_step(b)
            elif screen == '货币战争-备战-开商店':
                _close_shop_feed(b)
            elif screen == SCREEN_PREP:
                _force_settle(monkeypatch, won=True)
                _start_battle_feed(gs)
            else:
                raise AssertionError(f'未预期屏 {screen!r}')
        else:
            raise AssertionError('驱动步数超限:交付未达两窗')
        arms = [c for c in calls
                if c[1] == 'strategy_bond_battle_armed' and c[4] is True]
        delivers = _equip_grant_rows(calls)
        assert len(arms) >= 2, f'消费-再武装链未达两次: {len(arms)}'
        assert len(delivers) == 5 * len(arms), \
            f'交付笔数应 = 5 × 合格战斗数: {len(delivers)} vs {len(arms)}'
        pool = set(equips_by_category('星徽'))
        assert all(c[4][-1] in pool for c in delivers), '发放名出池'
        assert all(str(c[2]).startswith(
            f'strategy_bond_battle#{_CARD}') for c in delivers), \
            'evidence 前缀漂移'
        assert len(gs.equips.value or []) == 5 * len(arms), '入栏总数漂移'
        assert gs.strategy_bond_battle_armed.value is False, \
            '末窗交付后应已消费'
    finally:
        uninstall_backend()


def test_settled_replay_no_rearm_no_regrant(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 5(幂等回归):同节点战斗重放(battle_resolve 重入)→
    _settled_key 既有守卫整段跳过,零二次武装零新增笔(防本腿绕过);
    随后正常推进窗开恰交付一次(armed 消费,窗口幂等守卫辖域)。"""
    b = _prep_backend(85)
    try:
        gs = b.gs
        _hold_card(gs)
        _inject_bond_board(gs, short=False)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert gs.strategy_bond_battle_armed.value is True, '前置:首战武装'
        calls = _record_world_writes(gs, monkeypatch)
        _start_battle_feed(gs)
        assert b.screen_identity() == SCREEN_SETTLE, '重放应泊原结算屏'
        assert gs.strategy_bond_battle_armed.value is True, '重入误改武装'
        assert _arm_records(calls) == [], '重入零新增武装笔'
        assert _equip_grant_rows(calls) == [], '重入零新增发放笔'
        _drive_env_grant_step(b)
        assert len(gs.equips.value or []) == 5, '窗开应恰交付一次'
        assert gs.strategy_bond_battle_armed.value is False, '交付后应消费'
    finally:
        uninstall_backend()


def test_dead_battle_no_arm_no_grant(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 7(死亡局):保底已用 + 濒死局 boss 战败 → hp 归零死亡提前
    return 在武装挂点之前,零武装直接进终局(局终不见发放,与实机
    一致;boss 位伤害可击穿 1 hp 濒死,普通战斗位伤害不必然致死)。"""
    b = _prep_backend(86)
    try:
        gs = b.gs
        _hold_card(gs)
        _inject_bond_board(gs, short=False)
        _drive_to_kind_prep(monkeypatch, b, target_kind='boss')
        gs.observe(gs.hp_floor_triggered, True, sig=_SIG_OBS)
        gs.observe(gs.hp, 1, sig=_SIG_OBS)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=False)
        _start_battle_feed(gs)
        assert b.done and b.screen_identity() == SCREEN_LOBBY, \
            '败局致死应进终局'
        assert _arm_records(calls) == [], '死亡局误武装'
        assert _equip_grant_rows(calls) == [], '死亡局误发放'
    finally:
        uninstall_backend()
