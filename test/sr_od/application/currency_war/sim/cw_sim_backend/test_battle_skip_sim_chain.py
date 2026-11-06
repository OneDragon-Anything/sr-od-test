"""sim 免战跳过状态副本链测试(镜像 src = sim/cw_sim_backend.py 的
_skip_battle 消费腿 + advance 分派 battle_skip 分支 + visible 按钮替换
子态;声明构造面 = kernel/cw_action_report/start_battle.py,其对照锁落
kernel/test_world_decl.py)。

测试面依据 = 迭代设计 designs/T-161-mianzhan-pai.md §4 锁 2/3/4/5 +
REVIEW-T161 §5 特别核查①(镜像现值 _on_node_advance 记账段——跳过拍 =
跨级事件拍,到级金/装备二腿随批镜像):
- 分派键集锁(锁 2)= kernel/test_world_decl.py 集内断言 + 集外
  ValueError 既有锁,本文件不重复;
- sim 跳过 walk 锁(锁 3):battle_skip 消费拍 hp/streak 零写、无结算
  收入落账、无难度记录、无结算环帧行、无败局待办,被跳节点经验照常
  入账(xp 真值 = 红验基准:禁用 skip 腿本锁先红);两跳后第三次战斗节点
  恢复常规 _resolve_battle;下一节点窗轮首收入照常发生;
- 幂等锁(锁 4):_settled_key 零双账——同节点重放 battle_skip、skip 后
  又到 battle_resolve、后到 node_advance 三形全空转;
- visible 子态锁(锁 5):reward 节点出辖域出战恒 True;battle 持卡
  余量>0 出战 False/跳过 True(备战/开商店两屏);用尽移除后出战恢复;
- 跨级到级金/装备腿镜像锁(REVIEW-T161 特别核查①增补):skip 跨级 →
  成长基金金腿双通道写 / 钻石商人装备腿直写 + 宝钻状态副本联动,发放拍 =
  经验入账后。

驱动形态复用声明:引擎驱动助手 import 自 sim/test_sim_backend.py(已登记
超限拆分债文件,禁追加,只 import 复用不改)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
    _SIG_OBS,
    _backend,
    _close_shop_feed,
    _drive_to_first_prep,
    _forced_outcome,
    _start_battle_feed,
    _walk_to,
)

import sr_od.application.currency_war.sim.cw_sim_backend as backend_mod
from sr_od.application.currency_war.kernel.cw_action_report.pick_invest_strategy import (
    report_action_pick_invest_strategy_param,
)
from sr_od.application.currency_war.kernel.cw_action_report.start_battle import (
    report_action_start_battle_param,
)
from sr_od.application.currency_war.kernel.cw_economy import XP_TO_NEXT_LEVEL
from sr_od.application.currency_war.kernel.cw_game_state import (
    SCREEN_SHOP_PANEL,
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_world_decl import WorldDecl
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    CW_SKIP_SCOPE_BATTLE_ONLY_ASSUMPTION,
    CW_SKIP_SETTLEMENT_SEMANTICS_PENDING,
    SCREEN_PREP,
    SCREEN_SETTLE,
    SCREEN_SHOP,
    SimBackend,
    uninstall_backend,
)

_GOLD_CARD = '成长基金'
_EQUIP_CARD = '钻石商人'
_EQUIP = '财富宝钻'
_SKIP_CARD = STRATEGY_EFFECTS['免战牌']


def _counting_force_settle(monkeypatch: pytest.MonkeyPatch,
                           won: bool = True) -> list[tuple[int, int]]:
    """强制胜负结算 + 调用计数(步行局防随机败局;计数面 = 「恢复常规
    结算」锁的证据——跳过消费拍零调用、常规出战拍 +1)。"""
    calls: list[tuple[int, int]] = []

    def _fake(rng, *, plane: int, round_num: int) -> object:
        calls.append((plane, round_num))
        return _forced_outcome(won)

    monkeypatch.setattr(backend_mod, 'settle_battle', _fake)
    return calls


def _skip_feed(b: SimBackend) -> WorldDecl:
    """免战跳过上报 + 声明喂入(session = sim 状态容器本体直通——递减与
    状态副本消费同状态容器;上报后一行喂入 = 动作 op 同形)。返回声明供幂等
    重放用例直喂(重放面 = sim 消费守卫,不经上报重复递减)。"""
    out = report_action_start_battle_param(
        b.gs, SimpleNamespace(), _SIG, session=b.gs, skip_substate=True)
    assert out.applied, f'跳过上报未落账: {out.reason!r}'
    cw_sim_ports.declare_world(out.world_decl)
    return out.world_decl


def _dismiss_offer(b: SimBackend) -> None:
    """策略 offer 屏落卡回窗(op 同形:P1r3 固定日程首槽,跳过点击前
    窗内选卡先收尾;选卡落状态副本链与跳过锁无涉,卡名取首槽)。"""
    opts = b.gs.invest_strategy_opts.value or []
    out = report_action_pick_invest_strategy_param(
        b.gs, SimpleNamespace(norm_name=opts[0]), _SIG,
        session=SimpleNamespace())
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)


def _wrap_ring_offer(gs, monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """结算环入环口 + 遭遇经验表追加调用记录(透传真实现;跳过拍零入环
    锁的证据面)。"""
    offers: list[object] = []
    real_offer = gs.settlement_ring.offer
    real_append = gs.encounter_log.append

    def rec_offer(row) -> str:
        offers.append(row)
        return real_offer(row)

    def rec_append(row) -> None:
        offers.append(row)
        real_append(row)

    monkeypatch.setattr(gs.settlement_ring, 'offer', rec_offer)
    monkeypatch.setattr(gs.encounter_log, 'append', rec_append)
    return offers


def _record_writes(gs, monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic/write_logic_rand/observe 记录
    (通道, 字段名, evidence, sig, value, produced_by) 写序(透传真实现
    零行为变化;同目录到级装备腿锁 _record_writes 同形副本)。"""
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


@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(沿同目录同名 fixture 先例,fixture 不可跨文件
    import 故本文件自带同语义副本)。"""
    consume_defect_sink()
    yield
    set_defect_sink(None)
    consume_defect_sink()


def test_skip_walk_zero_battle_faces_then_normal_resolve(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """sim 跳过 walk 锁(锁 3 + xp 真值):连续两次 battle_skip → 消费拍
    hp/streak 零写、无结算收入落账(被跳节点无结算环帧行/无难度记录/
    hp 轨迹零追加)、被跳节点经验 +2 照常入账、uses 逐次递减、下一节点
    窗轮首收入照常发生;uses 用尽后第三次战斗节点常规出战恢复
    _resolve_battle(结算计数 +1、结算屏呈现)。"""
    settle_calls = _counting_force_settle(monkeypatch, won=True)
    b = _backend(seed=44)
    try:
        _drive_to_first_prep(b)
        _walk_to(b, 1, 3)
        gs = b.gs
        assert gs.node.value is not None \
            and gs.node.value.kind == 'battle', '前置:(1,3) 战斗节点窗'
        _dismiss_offer(b)   # (1,3) = 固定日程首槽,offer 屏先收尾
        gs.effects.register_strategy(_SKIP_CARD, acquired_key=(1, 3))
        gs.observe(gs.level, 3, sig=_SIG_OBS)
        gs.observe(gs.xp, (0, XP_TO_NEXT_LEVEL[3]), sig=_SIG_OBS)
        hp0 = int(gs.hp.value or 0)
        streak0 = gs.streak.value
        b.disclosures.clear()   # 只看本局新增(开局初始值披露剔除)
        # —— 第一跳:(1,3) → (1,4) ——
        settle0 = len(settle_calls)   # 步行局已消耗 (1,1)/(1,2) 两次常规结算
        offers = _wrap_ring_offer(gs, monkeypatch)
        n_difficulty0 = len(b.difficulty_records)
        trail0 = len(b.hp_trail)
        _skip_feed(b)
        assert len(settle_calls) == settle0, '跳过消费拍走了常规结算'
        assert offers == [], '跳过消费拍写了结算环帧行/遭遇经验表(T-33 面)'
        assert len(b.difficulty_records) == n_difficulty0, '跳过拍写难度记录'
        assert len(b.hp_trail) == trail0, '跳过拍追加了 hp 轨迹'
        assert int(gs.hp.value or 0) == hp0, '跳过拍 hp 被写'
        assert gs.streak.value == streak0, '跳过拍连胜被写'
        assert gs.pending_loss.value is None, '跳过拍登记败局待办'
        assert gs.xp.value == (2, XP_TO_NEXT_LEVEL[3]), \
            f'被跳节点经验未入账: {gs.xp.value}'
        assert gs.level.value == 3
        assert gs.node.value is not None \
            and (gs.node.value.plane, gs.node.value.round_num) == (1, 4), \
            f'状态副本未直进下一节点: {gs.node.value}'
        entry = gs.effects.first(_SKIP_CARD.id)
        assert entry is not None and entry.remaining_uses == 1, 'uses 未递减'
        assert b.disclosures.get(CW_SKIP_SCOPE_BATTLE_ONLY_ASSUMPTION) \
            == 'battle_only_v0', '辖域假设披露键未发射'
        assert b.disclosures.get(CW_SKIP_SETTLEMENT_SEMANTICS_PENDING) \
            == 'hp_streak_income_untouched_v0', '结算语义披露键未发射'
        assert b.screen_identity() == SCREEN_SHOP, \
            f'下一节点窗稳态非开商店档: {b.screen_identity()}'
        # —— 第二跳:(1,4) → (1,5) 补给窗(轮首收入照常发生)——
        gold_before = int(gs.gold.value or 0)
        _skip_feed(b)
        assert len(settle_calls) == settle0
        entry = gs.effects.first(_SKIP_CARD.id)
        assert entry is None, '用尽未移除'
        assert gs.node.value is not None \
            and (gs.node.value.plane, gs.node.value.round_num) == (1, 5)
        assert int(gs.gold.value or 0) > gold_before, \
            '下一节点窗轮首收入未照常发生'
        assert int(gs.hp.value or 0) == hp0 and gs.streak.value == streak0
        # —— 第三战:(1,6) 常规出战恢复结算(uses 已尽,出战按钮恢复)——
        _walk_to(b, 1, 6)
        assert gs.node.value is not None \
            and gs.node.value.kind == 'battle'
        assert b.visible(SCREEN_SHOP, '按钮-出战') is True, \
            'uses 用尽后出战按钮未恢复'
        n_difficulty1 = len(b.difficulty_records)
        trail1 = len(b.hp_trail)
        _start_battle_feed(gs)
        assert len(settle_calls) == settle0 + 1 \
            and settle_calls[-1] == (1, 6), '常规出战未恢复 _resolve_battle'
        assert b.screen_identity() == SCREEN_SETTLE, '常规结算屏未呈现'
        assert len(b.difficulty_records) == n_difficulty1 + 1, \
            '常规结算未写难度记录(与跳过拍对照)'
        assert len(b.hp_trail) == trail1 + 1, '常规结算未追加 hp 轨迹'
    finally:
        uninstall_backend()


def test_skip_idempotent_zero_double_account(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """幂等锁(锁 4):_settled_key 零双账 + 后到 node_advance 空转。
    可锁形态(声明不携节点身份,跨节点重放与真实新跳过按声明形状
    不可分辨,同节点窗 = 守卫辖域):①同节点 resolve→skip 对——battle
    节点常规结算后(状态副本驻留该节点)再喂 battle_skip 声明 → 守卫空转,
    零二次结算零推进;②skip 后直喂 node_advance 声明(补推形态)→
    序位守卫空转零双账。"""
    _counting_force_settle(monkeypatch, won=True)
    b = _backend(seed=45)
    try:
        _drive_to_first_prep(b)
        _walk_to(b, 1, 3)
        gs = b.gs
        # ① 同节点 resolve→skip:常规结算驻留 (1,3) → skip 声明空转
        _start_battle_feed(gs)
        assert b.screen_identity() == SCREEN_SETTLE
        assert b._settled_key == (1, 3), '前置:常规结算已记账'
        hp0 = int(gs.hp.value or 0)
        n_difficulty0 = len(b.difficulty_records)
        trail0 = len(b.hp_trail)
        b.advance(WorldDecl(next_screen='货币战争-备战-开商店',
                            trigger='battle_skip'))
        assert (int(gs.hp.value or 0), len(b.difficulty_records),
                len(b.hp_trail)) == (hp0, n_difficulty0, trail0), \
            '同节点 skip 补结算双账'
        assert (gs.node.value.plane, gs.node.value.round_num) == (1, 3), \
            '同节点 skip 误推进'
        # 结算确认 → 正常推进 (1,4)
        from test.sr_od.application.currency_war.sim.test_sim_backend import (
            _node_advance_feed,
        )
        _node_advance_feed(gs, trigger='settle_confirm')
        assert (gs.node.value.plane, gs.node.value.round_num) == (1, 4)
        # ② skip (1,4) → 状态副本 (1,5);node_advance 声明直喂空转
        gs.effects.register_strategy(_SKIP_CARD, acquired_key=(1, 4))
        decl = _skip_feed(b)
        assert (gs.node.value.plane, gs.node.value.round_num) == (1, 5)
        xp0 = gs.xp.value
        entered0 = b._entered_pos
        b.advance(WorldDecl(next_screen=SCREEN_SHOP_PANEL,
                            trigger='node_advance'))
        assert gs.xp.value == xp0, 'node_advance 双账'
        assert b._entered_pos == entered0, 'node_advance 双推进'
        assert b._settled_key == (1, 4), 'skip 守卫键漂移'
        assert decl.next_screen == '货币战争-补给', \
            f'跳过声明推导漂移: {decl.next_screen!r}'
    finally:
        uninstall_backend()


def test_visible_button_substitute_states(monkeypatch:
                                          pytest.MonkeyPatch) -> None:
    """visible 子态锁(锁 5):reward 节点出辖域 → 现役语义维持(出战恒
    可见);battle 持卡余量>0 → 出战 False/跳过 True(开商店叠加帧与
    备战档两屏);用尽移除(entry 离场)→ 出战 True/跳过 False。"""
    _counting_force_settle(monkeypatch, won=True)
    b = _backend(seed=46)
    try:
        _drive_to_first_prep(b)
        gs = b.gs
        assert gs.node.value is not None \
            and gs.node.value.kind == 'reward', '前置:P1r1 奖励节点'
        gs.effects.register_strategy(_SKIP_CARD, acquired_key=(1, 1))
        assert b.visible(SCREEN_PREP, '按钮-出战') is True, \
            '出辖域节点(reward)出战按钮被误替换'
        _walk_to(b, 1, 3)
        _dismiss_offer(b)   # (1,3) 固定日程首槽,offer 屏先收尾回窗
        assert gs.node.value.kind == 'battle'
        assert b.visible(SCREEN_SHOP, '按钮-出战') is False
        assert b.visible(SCREEN_SHOP, '按钮-跳过') is True
        _close_shop_feed(b)
        assert b.screen_identity() == SCREEN_PREP
        assert b.visible(SCREEN_PREP, '按钮-出战') is False, \
            '备战档未替换(出战 op 双屏查找同构面)'
        assert b.visible(SCREEN_PREP, '按钮-跳过') is True
        # 用尽移除:递减归零(entry 离场)→ 出战恢复/跳过消失
        gs.effects.consume_use(_SKIP_CARD.id)
        gs.effects.consume_use(_SKIP_CARD.id)
        assert gs.effects.first(_SKIP_CARD.id) is None, '前置:用尽未移除'
        assert b.visible(SCREEN_PREP, '按钮-出战') is True, \
            '用尽后出战按钮未恢复'
        assert b.visible(SCREEN_PREP, '按钮-跳过') is False, \
            '用尽后跳过按钮未消失'
    finally:
        uninstall_backend()


def test_skip_cross_level_gold_grant_mirror(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """跳过拍跨级到级金腿镜像锁(REVIEW-T161 特别核查①):直构 level=8
    + xp 贴阈(8→9 门槛 72)持成长基金,skip 跨 9 → 金腿双通道写
    (gold observe 独立笔 + done 一次性标志位 logic 笔),发放拍 = 被跳节点经验
    入账之后。"""
    _counting_force_settle(monkeypatch, won=True)
    b = _backend(seed=47)
    try:
        _drive_to_first_prep(b)
        _walk_to(b, 1, 3)
        gs = b.gs
        _dismiss_offer(b)
        gs.observe(gs.active_strategies, [_GOLD_CARD],
                   evidence='test:hold', sig=_SIG_OBS)
        gs.observe(gs.level, 8, sig=_SIG_OBS)
        gs.observe(gs.xp, (71, 72), sig=_SIG_OBS)
        calls = _record_writes(gs, monkeypatch)
        _skip_feed(b)
        assert gs.level.value == 9, f'跨级未发生: {gs.level.value}'
        gold_legs = [c for c in calls
                     if c[1] == 'gold'
                     and c[2] == f'sim:engine:strategy:level_gold:'
                                 f'{_GOLD_CARD}']
        latch_legs = [c for c in calls
                      if c[1] == 'strategy_conditional_done'
                      and c[2] == f'strategy:level_gold:{_GOLD_CARD}']
        assert len(gold_legs) == 1, f'金腿 observe 笔漂移: {gold_legs}'
        assert len(latch_legs) == 1, f'done 一次性标志位写笔漂移: {latch_legs}'
        assert latch_legs[0][4] == (_GOLD_CARD,), \
            f'一次性标志位值漂移: {latch_legs[0]}'
        # 发放拍 = 经验入账后(跨级事件拍,先于新节点窗轮首收入)
        idx_xp = next(i for i, c in enumerate(calls)
                      if c[1] == 'level'
                      and c[2] == 'sim:engine:xp:node')
        assert idx_xp < calls.index(gold_legs[0]), '发放拍早于经验入账'
    finally:
        uninstall_backend()


def test_skip_cross_level_equip_grant_world_coupling(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """跳过拍跨级到级装备腿镜像锁 + 宝钻状态副本联动:直构 level=8 + xp 贴阈
    持钻石商人,skip 跨 9 → equips 随机态写 + 一次性标志位写一笔(producer 专名),
    宝钻回调三写(diamond_count +1 / deploy_cap = level+钻数 /
    back_layout +1);发放拍 = 经验入账后。"""
    _counting_force_settle(monkeypatch, won=True)
    b = _backend(seed=48)
    try:
        _drive_to_first_prep(b)
        _walk_to(b, 1, 3)
        gs = b.gs
        _dismiss_offer(b)
        gs.observe(gs.active_strategies, [_EQUIP_CARD],
                   evidence='test:hold', sig=_SIG_OBS)
        gs.observe(gs.level, 8, sig=_SIG_OBS)
        gs.observe(gs.xp, (71, 72), sig=_SIG_OBS)
        back_before = int(gs.back_layout.value)
        calls = _record_writes(gs, monkeypatch)
        _skip_feed(b)
        assert gs.level.value == 9, f'跨级未发生: {gs.level.value}'
        legs = [c for c in calls
                if c[2] in (f'strategy_level_grant:{_EQUIP_CARD}#equip',
                            f'strategy_level_grant:{_EQUIP_CARD}')]
        assert len(legs) == 2, f'装备腿/一次性标志位写笔数漂移: {legs}'
        equip_leg, latch_leg = legs
        assert equip_leg[:2] == ('rand', 'equips'), \
            f'发放通道漂移: {equip_leg[:2]}'
        assert equip_leg[4] == [_EQUIP], f'发放值漂移: {equip_leg[4]!r}'
        assert equip_leg[5] == 'strategy_level_equip_grant', \
            f'producer 漂移: {equip_leg[5]!r}'
        assert latch_leg[:2] == ('logic', 'strategy_conditional_done'), \
            f'一次性标志位通道漂移: {latch_leg[:2]}'
        assert latch_leg[4] == (_EQUIP_CARD,), f'一次性标志位值漂移: {latch_leg}'
        # 宝钻状态副本联动三写
        assert int(gs.diamond_count.value) == 1, 'diamond_count 未 +1'
        assert int(gs.deploy_cap.value) == 9 + 1, \
            f'deploy_cap 漂移: {gs.deploy_cap.value!r}'
        assert int(gs.back_layout.value) == min(9, back_before + 1), \
            'back_layout 未 +1'
        # 发放拍 = 经验入账后
        idx_xp = next(i for i, c in enumerate(calls)
                      if c[1] == 'level'
                      and c[2] == 'sim:engine:xp:node')
        assert idx_xp < calls.index(equip_leg), '发放拍早于经验入账'
    finally:
        uninstall_backend()
