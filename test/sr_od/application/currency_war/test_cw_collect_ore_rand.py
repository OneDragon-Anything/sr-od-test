"""点晶矿随机态上报锁(logic-rand-sampling 迭代 3.2;design §2.3-§2.5)。

锁面:
- 采样器支撑集(定种子):gold ∈ 1..5 / equip ∈ 简易池 / char ∈ 注册表,
  种子可复现(同种子同序列);
- 三分支写序:spheres 摘除 → 未抽中域标记 → 奖励应用,evidence 点序
  ``#ore<k>``,全部来源 logic_rand,同组 group_id;
- 角色分支:落位 + 3合1 连锁(载体在场上 = 双域变更,受影响域各落
  一行,evidence ``proj_ore_merge#<级>#ore<k>``);
- 席满即止:前点奖励耗席后后续点留在 spheres(不摘不采);混合批出参
  ``ore_partial_open_skipped``;全席满 = ``bench_full_no_open`` 零写;
- None 边界:None 域跳写不标记;bench 未观察 / level 缺读整批拒;
- sim 接线:前置分派拦截(apply_player_action 不被触达)、ore_uses
  拒分支不耗序、流键 group_id ``act:sim@M1x/ore/{uses}``。

观察收口(等值静默/差异 logic_rand_outcome)= 基座锁
test_cw_game_state.py::test_write_logic_rand_and_observe_random_outcome,不重复。
"""
from __future__ import annotations

import random
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTER_ROSTER
from sr_od.application.currency_war.kernel.cw_action_report import (
    collect_ore as collect_ore_mod,
)
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_collect_ore_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    OreSight,
    Unit,
    bench_slots_of,
)
from sr_od.application.currency_war.kernel.cw_ore_reward import (
    _SIMPLE_EQUIP_POOL,
    OreReward,
    roll_ore_reward,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionCollectOreParam,
)

_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep',
                  group_id='g1')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')


def _ore(color: str, x: int, y: int, r: int = 10) -> tuple[str, int, int, int]:
    return (color, x, y, r)


def _bench(units: list[tuple[str, int]]) -> BenchView:
    slots = [BenchSlot(kind='unit',
                       unit=Unit(char_id=c, star=s, slot=i + 1))
             for i, (c, s) in enumerate(units)]
    while len(slots) < 9:
        slots.append(BenchSlot(kind='empty'))
    return BenchView(slots=slots, capacity=9)


def _make_gs(*, bench: list[tuple[str, int]] | None = None,
             front: list[Unit] | None = None,
             gold: int | None = 30,
             equips: list[str] | None = None,
             level: int | None = 5,
             ores: list[tuple[str, int, int, int]] | None = None,
             board: dict | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察,供 None 边界腿)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if ores is not None:
        gs.observe(gs.spheres, OreSight(
            count=len(ores), colors=tuple(dict.fromkeys(o[0] for o in ores)),
            points=tuple(ores)), sig=_SIG_OBS)
    if bench is not None:
        gs.observe(gs.bench, _bench(bench), sig=_SIG_OBS)
    if level is not None:
        gs.observe(gs.level, level, sig=_SIG_OBS)
    if gold is not None:
        gs.observe(gs.gold, gold, sig=_SIG_OBS)
    if equips is not None:
        gs.observe(gs.equips, list(equips), sig=_SIG_OBS)
    if front is not None:
        gs.observe(gs.front_row, list(front), sig=_SIG_OBS)
        gs.observe(gs.back_row, [], sig=_SIG_OBS)
    if board is not None:
        gs.observe(gs.board, dict(board), sig=_SIG_OBS)
    return gs


def _seq_rewards(*rewards: OreReward):
    """按序吐出预置采样结果(写序锁用,隔离真采样分布)。"""
    it = iter(rewards)

    def fake(rng: random.Random, level: int) -> OreReward:
        return next(it)

    return fake


def _record_writes(gs: GameState,
                   monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic_rand 记录 (字段名, evidence, group_id) 写序。"""
    calls: list[tuple[str, str, str | None]] = []
    real = gs.write_logic_rand

    def rec(target, value, *, produced_by, evidence, sig, note=''):
        calls.append((gs._field_name(target), evidence, sig.group_id))
        real(target, value, produced_by=produced_by, evidence=evidence,
             sig=sig, note=note)

    monkeypatch.setattr(gs, 'write_logic_rand', rec)
    return calls


# ============================================================ 采样器支撑集


def test_sampler_support_set_and_reproducibility() -> None:
    rng = random.Random(123)
    seen_kinds: set[str] = set()
    for _ in range(300):
        r = roll_ore_reward(rng, 4)
        seen_kinds.add(r.kind)
        if r.kind == 'gold':
            assert 1 <= r.gold <= 5, '金区间 1..5(临时口径 v0)'
        elif r.kind == 'equip':
            assert r.equip in _SIMPLE_EQUIP_POOL, '装备 ∈ 简易池全集'
        else:
            assert r.char_id in CHARACTER_ROSTER, '角色 ∈ 注册表'
            assert r.char_star == 1, '星级恒 1(ore_char_star1)'
    assert seen_kinds == {'gold', 'equip', 'char'}, '三形态全部可达'
    a = [roll_ore_reward(random.Random(9), 5) for _ in range(10)]
    b = [roll_ore_reward(random.Random(9), 5) for _ in range(10)]
    assert a == b, '同种子同序列(sim 可复现)'


# ============================================================ 写序与分支


def test_gold_branch_write_sequence(monkeypatch: pytest.MonkeyPatch) -> None:
    """金分支写序:spheres → 未抽中域标记(equips/bench/front/back)→
    奖励金;全部 logic_rand、同组 group_id。"""
    gs = _make_gs(bench=[('阿格莱雅', 1)], front=[Unit(char_id='黑塔', star=1)],
                  equips=[], ores=[_ore('金', 1, 1)])
    calls = _record_writes(gs, monkeypatch)
    monkeypatch.setattr(collect_ore_mod, 'roll_ore_reward',
                        _seq_rewards(OreReward(kind='gold', gold=3)))
    param = CwActionCollectOreParam(points=((1, 1),))
    out = report_action_collect_ore_param(gs, param, _SIG)
    assert out.applied is True
    assert [(n, e) for n, e, _ in calls] == [
        ('spheres', 'proj_collect_ore_drop#ore1'),
        ('equips', 'proj_ore_mark_equips#ore1'),
        ('bench', 'proj_ore_mark_bench#ore1'),
        ('front_row', 'proj_ore_mark_front_row#ore1'),
        ('back_row', 'proj_ore_mark_back_row#ore1'),
        ('gold', 'proj_ore_reward_gold#ore1'),
    ], f'写序不符: {[(n, e) for n, e, _ in calls]}'
    assert {g for _, _, g in calls} == {'g1'}, '同动作同组'
    assert gs.gold.value == 33 and gs.gold.source == 'logic_rand'
    assert gs.equips.value == [] and gs.equips.source == 'logic_rand', \
        '未抽中域值不变仅翻来源'
    assert gs.spheres.value.count == 0, '晶矿已摘除'


def test_char_branch_merge_dual_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    """角色分支·载体在场上:bench 素材置 None + 行域载体升星 = 双域变更,
    merge 级受影响域各落一行(evidence 同号)。board 断言 = 增量为零不写
    (升星不改羁绊标签,派生零差零写;继承机制由 T-1 board 专锁)。"""
    gs = _make_gs(bench=[('A', 1)], front=[Unit(char_id='A', star=1)], board={},
                  ores=[_ore('金', 1, 1)])
    calls = _record_writes(gs, monkeypatch)
    monkeypatch.setattr(collect_ore_mod, 'roll_ore_reward',
                        _seq_rewards(OreReward(kind='char', char_id='A')))
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=((1, 1),)), _SIG)
    assert out.applied is True
    by_ev = {e: n for n, e, _ in calls}
    assert by_ev.get('proj_ore_reward_char#ore1') == 'bench'
    assert by_ev.get('proj_ore_merge#1#ore1') is not None, \
        '一级合并落行(双域同号,行序内断言见下)'
    merge_fields = [n for n, e, _ in calls
                    if e == 'proj_ore_merge#1#ore1']
    assert merge_fields == ['bench', 'front_row', 'back_row'], \
        f'双域变更各落一行(bench 素材清 + 行载体升星 + 对侧行整表): {merge_fields}'
    assert [b.star for b in bench_slots_of(gs) if b is not None] == [], \
        'bench 侧素材全部置 None(载体在场上)'
    assert gs.front_row.value[0].star == 2, '场上载体升 2★'
    board_writes = [c for c in calls if c[0] == 'board']
    assert board_writes == [], \
        '升星不改羁绊标签 → board 增量为零零写(派生量纪律)'


def test_char_branch_bench_carrier_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    """角色分支·载体在备战(3×1★ 备战内合并):bench 两次写(落位行 +
    merge 行),行域未被合成触及 → 步 4 值不变标记。"""
    gs = _make_gs(bench=[('A', 1), ('A', 1)], front=[], ores=[_ore('金', 1, 1)])
    calls = _record_writes(gs, monkeypatch)
    monkeypatch.setattr(collect_ore_mod, 'roll_ore_reward',
                        _seq_rewards(OreReward(kind='char', char_id='A')))
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=((1, 1),)), _SIG)
    assert out.applied is True
    stars = [b.star for b in bench_slots_of(gs) if b is not None]
    assert stars == [2], '3×1★ → 2★ 载体留备战'
    seq = [(n, e) for n, e, _ in calls]
    assert ('bench', 'proj_ore_reward_char#ore1') in seq, '落位行'
    assert ('bench', 'proj_ore_merge#1#ore1') in seq, '合成行'
    assert ('front_row', 'proj_ore_mark_front_row#ore1') in seq, \
        '行域未触及 → 值不变标记'


def test_multi_point_full_bench_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    """全席满:逐点判守卫全跳过 → applied=False 'bench_full_no_open',
    spheres 零写(晶矿全部保留),采样零消耗。"""
    gs = _make_gs(bench=[('A', i + 1) for i in range(9)],
                  ores=[_ore('金', 1, 1), _ore('金', 2, 2)])
    consumed: list[int] = []

    def fake(rng: random.Random, level: int) -> OreReward:
        consumed.append(1)
        return OreReward(kind='gold', gold=1)

    monkeypatch.setattr(collect_ore_mod, 'roll_ore_reward', fake)
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=((1, 1), (2, 2))), _SIG)
    assert out.applied is False and out.reason == 'bench_full_no_open'
    assert consumed == [], '席满点不采样'
    assert gs.spheres.value.count == 2, '晶矿全部保留'


def test_multi_point_partial_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    """混合批:首点角色奖励耗掉最后空位 → 次点席满跳过(留在 spheres),
    出参 'ore_partial_open_skipped',已开点照常入账。"""
    slots = [BenchSlot(kind='unit',
                       unit=Unit(char_id=f'F{i}', star=1, slot=i + 1))
             for i in range(8)] + [BenchSlot(kind='empty')]
    gs = _make_gs(ores=[_ore('金', 1, 1), _ore('金', 2, 2)])
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    calls = _record_writes(gs, monkeypatch)
    monkeypatch.setattr(collect_ore_mod, 'roll_ore_reward',
                        _seq_rewards(OreReward(kind='char', char_id='B')))
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=((1, 1), (2, 2))), _SIG)
    assert out.applied is True and out.reason == 'ore_partial_open_skipped'
    evs = [e for _, e, _ in calls]
    assert 'proj_collect_ore_drop#ore1' in evs, '首点开成'
    assert not any(e.endswith('#ore2') for e in evs), '次点席满不写不采'
    assert gs.spheres.value.count == 1, '未开晶矿留在 spheres'
    names = [b.char_id for b in bench_slots_of(gs) if b is not None]
    assert names.count('B') == 1, '角色奖励已落位(耗掉最后空位)'


# ============================================================ None 边界与拒分支


def test_none_domains_skip_and_level_unread(monkeypatch: pytest.MonkeyPatch) -> None:
    """None 边界:equips 未观察 → 无标记无奖励写(诚实缺失);
    level 缺读 → 整批拒 'level_unread' 零写。"""
    gs = _make_gs(bench=[('A', 1)], gold=30, equips=None, level=None,
                  ores=[_ore('金', 1, 1)])
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=((1, 1),)), _SIG)
    assert out.applied is False and out.reason == 'level_unread'
    assert gs.spheres.value.count == 1, '拒分支先于任何写'

    gs2 = _make_gs(bench=[('A', 1)], gold=30, equips=None, level=5,
                   ores=[_ore('金', 1, 1)])
    calls = _record_writes(gs2, monkeypatch)
    monkeypatch.setattr(collect_ore_mod, 'roll_ore_reward',
                        _seq_rewards(OreReward(kind='equip', equip='幸运星')))
    out2 = report_action_collect_ore_param(
        gs2, CwActionCollectOreParam(points=((1, 1),)), _SIG)
    assert out2.applied is True
    assert not any(n == 'equips' for n, _, _ in calls), \
        '抽中域 None → 跳采样写(等观察),不编 None 值'


def test_bench_unobserved_rejects_whole_batch() -> None:
    """bench 未观察 → 整批拒 'bench_unobserved'(席满守卫与角色落点
    均不可判)。"""
    gs = _make_gs(bench=None, ores=[_ore('金', 1, 1)])
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=((1, 1),)), _SIG)
    assert out.applied is False and out.reason == 'bench_unobserved'
    assert gs.spheres.value.count == 1, '拒分支零写'


# ============================================================ sim 接线


def test_sim_dispatch_intercepts_and_counts_uses(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """sim 接线:_step_prep 前置拦截 CollectOre(主转移函数不被触达)、
    流键 group_id ``act:sim@M1x/ore/{uses}``、拒分支不耗 ore_uses。"""
    from sr_od.application.currency_war.sim import cw_sim_engine as eng_mod

    def _boom(*a, **k):   # pragma: no cover - 被触达即失败
        raise AssertionError('apply_player_action 不应被触达(旁路直调)')

    monkeypatch.setattr(eng_mod, 'apply_player_action', _boom)
    engine = eng_mod.CwSimEngine()

    # 成功腿:ore_uses 0 → 1,group_id 带流键坐标
    gs = _make_gs(bench=[('A', 1)], ores=[_ore('金', 1, 1)])
    feng = SimpleNamespace(seed=7, ore_uses=0, gs=gs)
    calls = _record_writes(gs, monkeypatch)
    out = engine._step_prep(feng, CwActionCollectOreParam(points=((1, 1),)))
    assert out is not None and out.applied is True, '前置分派受理并回执'
    assert feng.ore_uses == 1, '成功耗序'
    assert calls and calls[0][2] == 'act:sim@M1x/ore/1', '流键 group_id'

    # 拒腿(level 缺读):ore_uses 不耗序
    gs2 = _make_gs(bench=[('A', 1)], level=None, ores=[_ore('金', 1, 1)])
    feng2 = SimpleNamespace(seed=7, ore_uses=3, gs=gs2)
    out2 = engine._step_prep(feng2, CwActionCollectOreParam(points=((1, 1),)))
    assert out2 is not None and out2.applied is False
    assert feng2.ore_uses == 3, '拒分支不耗序(与炉先例一致)'
