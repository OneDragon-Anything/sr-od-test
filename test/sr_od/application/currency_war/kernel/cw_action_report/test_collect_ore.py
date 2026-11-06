"""collect_ore 上报合并升星触发发放分支测试(镜像 src =
kernel/cw_action_report/collect_ore.py;晶矿域存量测试 =
kernel/test_ore.py 已超行限,本文件按镜像规范落新位)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-26-liangzi-tongpin-qiyue.md(定稿)§2.4 条 3 + §4.6:晶矿角色入账分支的
inline 级联采集升星事实,整批全部写毕后收尾发火(发火时序与买牌分支
同构)——bench 终态 = 合并产物 + 发放角色并存。
"""
from __future__ import annotations

import random
from collections.abc import Iterator

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_session,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_collect_ore_param,
    set_action_rng_provider,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    OreSight,
    Unit,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_ore_reward import (
    OreReward,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionCollectOreParam,
)

_POOL = ('符玄', '希儿')

_SEED_SIG = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')
_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep',
                  group_id='g1')

_XY = (100, 200)


@pytest.fixture
def seeded_provider() -> Iterator[None]:
    """注确定 rng 提供槽(固定种子,期望名可现算钉名),必达复位。"""
    set_action_rng_provider(lambda tool: random.Random(20261016))
    try:
        yield None
    finally:
        set_action_rng_provider(None)


def _make_gs():
    """晶矿角色入账分支场景:1 颗晶矿(附着角色奖励 = 1★花火,零掷骰兑现)+
    2×1★花火在席 + 量子同频契约激活(附着眼 = 逻辑写种子)。"""
    gs = game_state_of(cw4_session())
    gs.observe(gs.spheres, OreSight(count=1, colors=('gold',),
                                    points=(('gold', *_XY, 30),)),
               sig=_SEED_SIG)
    slots = [BenchSlot(kind='unit', unit=Unit(char_id='花火', star=1))
             for _ in range(2)]
    slots += [BenchSlot(kind='empty')] * 7
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SEED_SIG)
    gs.observe(gs.active_env, '量子同频契约', sig=_SEED_SIG)
    gs.write_logic(gs.ore_rewards,
                   {f'{_XY[0]},{_XY[1]}': OreReward(kind='char',
                                                    char_id='花火',
                                                    char_star=1)},
                   produced_by='test-seed', sig=_SIG)
    return gs


def test_collect_ore_char_reward_fires_grant(seeded_provider) -> None:
    """晶矿角色入账分支发火时序锁(T-26 设计 §4.6 同构分支):角色奖励补齐三连
    → 级联合并 2★ 产物;整批写毕后发火 → bench 终态 = 产物 + 发放角色
    并存(发放名 = 注入槽种子现算;spheres 摘除与附着键移除照常)。"""
    expected = random.Random(20261016).choice(list(_POOL))
    gs = _make_gs()
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=(_XY,)), sig=_SIG)
    assert out.applied, f'晶矿开成: {out.reason}'
    units = [(s.unit.char_id, s.unit.star) for s in gs.bench.value.slots
             if s is not None and s.kind == 'unit' and s.unit is not None]
    assert units == [('花火', 2), (expected, 1)], \
        f'合并产物 + 发放角色并存: {units}'
    assert f'{_XY[0]},{_XY[1]}' not in gs.ore_rewards.value, \
        '开成即附着键移除(既有语义不变)'


# ============================================================ 晶矿开启计数分支 + 战技点契约触发分支
# (T-29 战技点契约,设计 = 迭代 2026-09-23-invest-effects-calc designs/
# T-29-zhanjidian-qiyue.md §2.4 + §4 锁 5/锁 7:计数先入账后检查、
# 「点开才计数」、窗序 = 矿奖励 → 计数 → 触发分支。)

_SP_ENV = '战技点契约'

# 三点批坐标(spheres 点形 = (色, x, y, 半径),载荷只喂 (x, y))
_PTS = (('gold', 100, 200, 30), ('gold', 300, 400, 30),
        ('gold', 500, 600, 30))
_XYS = ((100, 200), (300, 400), (500, 600))


def _make_sp_gs(*, bench_units: list[tuple[str, int]],
                ore_open_total: int = 0):
    """战技点契约采晶矿场景(直构状态容器,观察种子):三点批 + 附着值
    (点1 金 / 点2 角色〔银狼,与种子单位异名防合并〕/ 点3 金——席满
    场景第 3 点恒跳过不采);bench 按参组装;计数经唯一入口函数播种。"""
    gs = game_state_of(cw4_session())
    gs.observe(gs.active_env, _SP_ENV, sig=_SEED_SIG)
    slots = [BenchSlot(kind='unit', unit=Unit(char_id=c, star=s))
             for c, s in bench_units]
    slots += [BenchSlot(kind='empty')] * (9 - len(slots))
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SEED_SIG)
    gs.observe(gs.spheres, OreSight(count=3, colors=('gold',), points=_PTS),
               sig=_SEED_SIG)
    gs.write_logic(gs.ore_rewards,
                   {'100,200': OreReward(kind='gold', gold=3),
                    '300,400': OreReward(kind='char', char_id='银狼',
                                         char_star=1),
                    '500,600': OreReward(kind='gold', gold=3)},
                   produced_by='test-seed', sig=_SIG)
    if ore_open_total:
        gs.effects.record_ore_open(ore_open_total)
    return gs


def _sp_record_writes(gs,
                      monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic_rand/write_logic 记录 (字段名, evidence, 通道)
    写行(先例 = 同目录 test_shop_projection_logic 同族 helper)。"""
    calls: list[tuple[str, str | None, str]] = []

    def _wrap(real, channel: str):
        def rec(target, value, *, produced_by, evidence=None, sig, note=''):
            calls.append((gs._field_name(target), evidence, channel))
            real(target, value, produced_by=produced_by, evidence=evidence,
                 sig=sig, note=note)
        return rec

    monkeypatch.setattr(gs, 'write_logic_rand',
                        _wrap(gs.write_logic_rand, 'rand'))
    monkeypatch.setattr(gs, 'write_logic', _wrap(gs.write_logic, 'logic'))
    return calls


def test_full_bench_skip_points_not_counted() -> None:
    """席满跳点不入账(T-29 设计 §4 锁 5):批含 2 开成点(金/角色)+
    1 席满跳点 → ore_open_total +2 非 +3,第 3 矿留 spheres(现行为
    回归);计数 2 < 首阈值 → 零触发零晶矿 done。种子单位每名至多
    2 只(互异 4 名 × 2)——防角色奖励落位的全池 3合1 扫描合并腾席,
    保证点 3 时真席满。"""
    gs = _make_sp_gs(bench_units=[('停云', 1)] * 2 + [('刃', 1)] * 2
                     + [('桑博', 1)] * 2 + [('佩拉', 1)] * 2)
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=_XYS), sig=_SIG)
    assert out.applied and out.reason == 'ore_partial_open_skipped', \
        f'混合批出参: {out.reason}'
    assert gs.effects.ore_open_total == 2, '跳点不计(只入开成点)'
    assert gs.spheres.value is not None \
        and (('gold', 500, 600, 30) in gs.spheres.value.points), \
        '席满跳点矿留 spheres'
    assert not any(k.startswith('ore_open')
                   for _e, k in (gs.env_grants_done.value or ())), \
        '计数未达标零触发零晶矿 done'


def test_mixed_batch_missing_level_skip_not_counted(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """缺项∧level 缺读跳点不入账(T-29 设计 §4 锁 5 后半):混合批 =
    2 开成点(附着命中,不需 level)+ 1 缺项跳点(无附着键 ∧ level
    缺读,兜底掷不可行)+ 1 席满跳点 → ore_open_total 只计开成点
    (+2 非 +4),两类跳点均不入账、两矿留 spheres(下帧挂接入口
    补生成后再点);出参 reason = 缺项跳点具体原因(优先于席满表达,
    零写跳点的唯一可断言通道)。直构状态容器(不经种子 session)保 level
    缺读;种子单位每名至多 2 只防合并腾席(同席满半边锁前提)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    sig_seed = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')
    gs.observe(gs.active_env, _SP_ENV, sig=sig_seed)
    slots = [BenchSlot(kind='unit', unit=Unit(char_id=c, star=1))
             for c in ('停云', '停云', '刃', '刃', '桑博', '桑博',
                       '佩拉', '佩拉')]
    slots.append(BenchSlot(kind='empty'))
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=sig_seed)
    pts = (('gold', 100, 200, 30), ('gold', 300, 400, 30),
           ('gold', 500, 600, 30), ('gold', 700, 800, 30))
    gs.observe(gs.spheres, OreSight(count=4, colors=('gold',), points=pts),
               sig=sig_seed)
    # 点 300,400 无附着键 + level 未观察 = 缺项∧level 缺读跳点形态
    gs.write_logic(gs.ore_rewards,
                   {'100,200': OreReward(kind='gold', gold=3),
                    '500,600': OreReward(kind='char', char_id='银狼',
                                         char_star=1),
                    '700,800': OreReward(kind='gold', gold=3)},
                   produced_by='test-seed', sig=_SIG)
    assert gs.level.value is None, '前置:level 缺读(直构状态容器无种子)'
    calls = _sp_record_writes(gs, monkeypatch)
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(
            points=((100, 200), (300, 400), (500, 600), (700, 800))),
        sig=_SIG)
    assert out.applied \
        and out.reason == 'ore_reward_attach_missing_level', \
        f'缺项跳点 reason 优先表达: {out.reason}'
    assert gs.effects.ore_open_total == 2, '两类跳点均不入账(只计开成点)'
    sphere_pts = gs.spheres.value.points if gs.spheres.value else ()
    assert (('gold', 300, 400, 30) in sphere_pts
            and ('gold', 700, 800, 30) in sphere_pts), \
        '缺项跳点与席满跳点矿均留 spheres'
    assert not any(k.startswith('ore_open')
                   for _e, k in (gs.env_grants_done.value or ())), \
        '零触发零晶矿 done'
    assert not any((c[1] or '').startswith('env_grant#') for c in calls), \
        '触发分支零写行'


def test_window_order_reward_writes_before_trigger_branch(
        monkeypatch: pytest.MonkeyPatch, seeded_provider) -> None:
    """窗序与计数先入账(T-29 设计 §2.4/§4 锁 7):矿奖励写(金)先于
    战技点契约触发分支写(台账序锁);计数入账后检查时现值含本批
    (20+1=21 达标 20 档),done 封账 ``ore_open#20``。"""
    gs = _make_sp_gs(bench_units=[], ore_open_total=20)
    calls = _sp_record_writes(gs, monkeypatch)
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=(_XYS[0],)), sig=_SIG)
    assert out.applied, f'开成: {out.reason}'
    assert gs.effects.ore_open_total == 21, '计数先入账(含本批)'
    assert gs.env_grants_done.value == \
        ((_SP_ENV, 'ore_open#20'),), '触发分支 done 封账'
    evidence = f'env_grant#{_SP_ENV}#ore_open20'
    gold_idx = next(i for i, c in enumerate(calls)
                    if c[1] == 'proj_ore_reward_gold#ore1')
    trigger_idx = next(i for i, c in enumerate(calls)
                       if (c[1] or '').startswith(evidence))
    assert gold_idx < trigger_idx, '矿奖励写先于触发分支写'
    bench_evs = [c[1] for c in calls if c[0] == 'bench'
                 and (c[1] or '').startswith(evidence)]
    assert bench_evs == [evidence + '#place'] * 2, \
        f'触发分支 bench 写两条分支(具名+随机): {bench_evs}'


def test_zero_open_early_return_no_count_no_trigger(
        monkeypatch: pytest.MonkeyPatch, seeded_provider) -> None:
    """opened == 0 早退路径(T-29 设计 §2.4/§4 锁 7):全批席满跳点 →
    applied=False 零容器写、计数不变(零计数)、零触发零 done
    (opened==0 路径保持零写零计数)。"""
    gs = _make_sp_gs(bench_units=[('希儿', 1)] * 9, ore_open_total=20)
    calls = _sp_record_writes(gs, monkeypatch)
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=_XYS), sig=_SIG)
    assert not out.applied and out.reason == 'bench_full_no_open', \
        f'全跳批出参: {out.reason}'
    assert not calls, f'全跳零容器写: {calls}'
    assert gs.effects.ore_open_total == 20, '零计数(opened==0 不入账)'
    assert not any(k.startswith('ore_open')
                   for _e, k in (gs.env_grants_done.value or ())), \
        '零触发零晶矿 done'
