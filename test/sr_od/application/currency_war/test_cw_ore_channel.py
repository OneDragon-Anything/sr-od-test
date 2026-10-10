"""晶矿奖励附着通道锁(迭代 2026-10-10-ore-reward-attach 3.1;详设
details/ore-reward-channel.md §1-§5)。

锁面:
- 生成函数:声明金先占席(rng.choice 不放回)+ 其余逐矿采样 + 掷序确定
  (同种子同输出);声明数超坐标数 ValueError;level 错档沿 roll_ore_reward
  显式炸;12 金档在此单测覆盖(sim 第一期位面 3 不可达);
- 注册表三条构建校验:孤儿键 / 值形(长度 3 逐项正整数)/ 双源同值
  (ENV_ECONOMY.gold_per_plane_start 改一处金额即炸);
- 容差配对轨迹继承:漂移 ≤12px 连续帧命中 = 键重挂值不变**零重掷**
  (roll 调用计数为零),声明金在坐标抖动下保全;越门(13px)= 消失清洗
  + 新现重掷;
- 生成集 = 无附着现役身份(level 缺读帧不生成,补读后自动再进生成集);
  消费 = pending 移除 + done 追加;
- 入队电平规则(pending+done 双守卫幂等)与过期电平清理(逐旧位面留痕);
- 种子底座(三域恒非 None)与快照→恢复类型不变(OreReward / tuple-of-tuple)。

点击兑现(collect_ore 改造)= 3.2 辖,sim/live 接线 = 3.3/3.4 辖,不在此。
"""
from __future__ import annotations

import random

import pytest

import sr_od.application.currency_war.kernel.cw_action_report as cw_action_report_pkg
import sr_od.application.currency_war.kernel.cw_ore_reward as cw_ore_reward_mod
from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    NodeKey,
    OreSight,
    restore_state_snapshot,
    seed_opening_state,
)
from sr_od.application.currency_war.kernel.cw_ore_channel import (
    check_ore_declared_level,
    report_spheres_observed,
)
from sr_od.application.currency_war.kernel.cw_ore_reward import (
    OreReward,
    generate_ore_rewards,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
# live 挂接写 sig 形态(详设 §5:logic_hook 族,group_id 'prep:ore-channel')
_SIG_HOOK = ChannelSig(family='logic_hook', actor='CwScreenPrep',
                       group_id='prep:ore-channel')
_ENV = '增发货币'


def _ore(color: str, x: int, y: int, r: int = 30) -> tuple[str, int, int, int]:
    return (color, x, y, r)


def _sight(ores: list[tuple[str, int, int, int]]) -> OreSight:
    return OreSight(count=len(ores),
                    colors=tuple(dict.fromkeys(o[0] for o in ores)),
                    points=tuple(ores))


def _make_gs(*, plane: int | None = 1, level: int | None = 5,
             env: str | None = None,
             pending: tuple[tuple[str, int, int], ...] = (),
             done: tuple[tuple[str, int], ...] = ()) -> GameState:
    """观察面按参组装(None = 保持未观察);声明域经 logic 直写播种。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if plane is not None:
        gs.observe(gs.node, NodeKey(plane=plane, round_num=1, kind='prep'),
                   sig=_SIG_OBS)
    if level is not None:
        gs.observe(gs.level, level, sig=_SIG_OBS)
    if env is not None:
        gs.observe(gs.active_env, env, sig=_SIG_OBS)
    if pending:
        gs.write_logic(gs.ore_declared_pending, tuple(pending),
                       produced_by='test-seed', sig=_SIG_HOOK)
    if done:
        gs.write_logic(gs.ore_declared_done, tuple(done),
                       produced_by='test-seed', sig=_SIG_HOOK)
    return gs


def _record_writes(gs: GameState,
                   monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic_rand/write_logic 记录 (字段名, evidence, 通道) 写行。"""
    calls: list[tuple[str, str | None, str]] = []

    def _wrap(real, channel: str):
        def rec(target, value, *, produced_by, evidence=None, sig, note=''):
            calls.append((gs._field_name(target), evidence, channel))
            real(target, value, produced_by=produced_by, evidence=evidence,
                 sig=sig, note=note)
        return rec

    monkeypatch.setattr(gs, 'write_logic_rand',
                        _wrap(gs.write_logic_rand, 'rand'))
    monkeypatch.setattr(gs, 'write_logic',
                        _wrap(gs.write_logic, 'logic'))
    return calls


def _count_rolls(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """roll_ore_reward 调用计数(透传真实现,零行为变化)。"""
    calls = [0]
    real = cw_ore_reward_mod.roll_ore_reward

    def counting(rng: random.Random, level: int) -> OreReward:
        calls[0] += 1
        return real(rng, level)

    monkeypatch.setattr(cw_ore_reward_mod, 'roll_ore_reward', counting)
    return calls


# ============================================================ 生成函数


def test_generate_declared_first_then_sampling() -> None:
    """声明金逐个先占席(rng.choice 不放回),其余坐标逐矿采样;返回键
    'x,y';同种子同输出(掷序确定 = sim 流键确定性的前提)。"""
    coords = ((100, 100), (300, 300), (500, 500), (700, 700))
    a = generate_ore_rewards((6, 8), coords, 5, random.Random(42))
    b = generate_ore_rewards((6, 8), coords, 5, random.Random(42))
    assert a == b, '同种子同输出'
    assert set(a) == {'100,100', '300,300', '500,500', '700,700'}, \
        f'键制 = x,y 全坐标覆盖: {sorted(a)}'
    golds = sorted(r.gold for r in a.values() if r.kind == 'gold')
    assert golds == [6, 8], f'声明金逐个占席(值原样入 OreReward): {a}'
    others = [r for k, r in a.items() if r.kind != 'gold']
    assert len(others) == 2, '非声明坐标走 roll_ore_reward 采样'
    # 12 金档在此单测覆盖(sim 第一期 plane>2 raise,位面 3 不可达)
    full = generate_ore_rewards((6, 8, 12), coords[:3], 5, random.Random(1))
    assert sorted(r.gold for r in full.values()) == [6, 8, 12]


def test_generate_guards_raise() -> None:
    """声明数超坐标数 ValueError(静默丢声明 = 声明金蒸发);level 错档沿
    roll_ore_reward 显式 ValueError(口径错档禁静默兜底)。"""
    with pytest.raises(ValueError, match='超矿批坐标数'):
        generate_ore_rewards((6, 8), ((100, 100),), 5, random.Random(0))
    # 全部坐标被声明占满时无采样发生,level 不参与判定(不炸)
    generate_ore_rewards((6,), ((100, 100),), 99, random.Random(0))
    with pytest.raises(ValueError, match='不在概率表档'):
        generate_ore_rewards((6,), ((100, 100), (300, 300)), 99,
                             random.Random(0))


# ============================================================ 注册表构建校验


def test_env_ore_grants_registry_and_validation(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """三条构建校验(import 即炸语义,注入 + 直调,沿 ENV_GIFTS 测试惯用法):
    孤儿键 / 值形 / 双源同值(改一处金额即炸);现表默认通过。"""
    # 现表(与 ENV_ECONOMY 同出卡面 id 103):直调校验器零异常
    assert cw_investments.ENV_ORE_GRANTS == {_ENV: (6, 8, 12)}
    cw_investments._validate_env_ore_grants()

    bad = dict(cw_investments.ENV_ORE_GRANTS)
    bad['不存在环境'] = (6, 8, 12)
    monkeypatch.setattr(cw_investments, 'ENV_ORE_GRANTS', bad)
    with pytest.raises(ValueError, match='孤儿键'):
        cw_investments._validate_env_ore_grants()
    monkeypatch.undo()

    for bad_value in ((6, 8), (6, 0, 12), [6, 8, 12]):
        bad = dict(cw_investments.ENV_ORE_GRANTS)
        bad[_ENV] = bad_value
        monkeypatch.setattr(cw_investments, 'ENV_ORE_GRANTS', bad)
        with pytest.raises(ValueError, match='值形'):
            cw_investments._validate_env_ore_grants()
        monkeypatch.undo()

    # 双源同值:ENV_ECONOMY 侧改一处金额(6,8,12)→(6,8,11)即炸
    drifted = dict(cw_investments.ENV_ECONOMY)
    from dataclasses import replace as _dc_replace
    drifted[_ENV] = _dc_replace(drifted[_ENV], gold_per_plane_start=(6, 8, 11))
    monkeypatch.setattr(cw_investments, 'ENV_ECONOMY', drifted)
    with pytest.raises(ValueError, match='双源失同步'):
        cw_investments._validate_env_ore_grants()
    monkeypatch.undo()

    # 双源同值检查辖「非空 gold_per_plane_start」:估值面无该通道则不比对
    no_econ = {k: v for k, v in drifted.items() if k != _ENV}
    monkeypatch.setattr(cw_investments, 'ENV_ECONOMY', no_econ)
    cw_investments._validate_env_ore_grants()


# ============================================================ 容差配对轨迹继承


def test_pairing_hit_no_reroll_declared_gold_survives(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """声明金在「坐标漂移 ≤12px 连续两帧」下保全:配对命中 = 键重挂、
    值不变、roll 调用计数为零(不重掷);首帧生成即含声明附着,消费 =
    pending 移除 + done 追加。"""
    monkeypatch.setattr(cw_action_report_pkg, '_ACTION_RNG_PROVIDER',
                        lambda tool: random.Random(7))
    gs = _make_gs(plane=1, level=5, env=_ENV,
                  pending=((_ENV, 1, 6),))
    rolls = _count_rolls(monkeypatch)

    # 首帧:声明入队已由电平检查完成(此处直播种);新现生成即含声明附着
    report_spheres_observed(gs, _sight([_ore('金', 100, 100)]),
                            obs_sig=_SIG_OBS, hook_sig=_SIG_HOOK,
                            evidence='prep')
    assert gs.ore_rewards.value is not None
    assert gs.ore_rewards.value.get('100,100') == OreReward(kind='gold',
                                                            gold=6), \
        '声明金占席生成(归属 rng 掷,本帧唯一坐标即占)'
    assert gs.ore_declared_pending.value == (), '消费 = pending 移除'
    assert gs.ore_declared_done.value == ((_ENV, 1),), '消费 = done 追加'

    # 次帧:坐标漂移 ≤12px(双轴独立)→ 配对命中,继承附着零重掷
    calls = _record_writes(gs, monkeypatch)
    report_spheres_observed(gs, _sight([_ore('金', 108, 105)]),
                            obs_sig=_SIG_OBS, hook_sig=_SIG_HOOK,
                            evidence='prep')
    assert rolls[0] == 0, f'配对命中不得重掷(roll 调用 {rolls[0]} 次)'
    assert '108,105' in (gs.ore_rewards.value or {}) \
        and '100,100' not in (gs.ore_rewards.value or {}), '键重挂'
    assert gs.ore_rewards.value['108,105'] == OreReward(kind='gold', gold=6), \
        '声明金保全(值不变)'
    assert ('ore_rewards', 'ore_gen_rekey#p1', 'rand') in calls, \
        f'重挂写行 evidence: {calls}'


def test_pairing_boundary_and_miss_reroll(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """配对门边界:双轴独立 ≤12px——漂移恰 12px 命中(同门语义与
    filter_persistent_ores);越门 13px = 消失清洗 + 新现重掷(键换、
    值重采样,ore_gen_cleanup 留痕)。"""
    monkeypatch.setattr(cw_action_report_pkg, '_ACTION_RNG_PROVIDER',
                        lambda tool: random.Random(7))
    gs = _make_gs(plane=1, level=5)
    report_spheres_observed(gs, _sight([_ore('金', 100, 100)]),
                            obs_sig=_SIG_OBS, hook_sig=_SIG_HOOK,
                            evidence='')
    attached = gs.ore_rewards.value['100,100']

    # 恰 12px(x 轴)命中:继承不重掷
    report_spheres_observed(gs, _sight([_ore('金', 112, 100)]),
                            obs_sig=_SIG_OBS, hook_sig=_SIG_HOOK,
                            evidence='')
    assert gs.ore_rewards.value.get('112,100') == attached, \
        '漂移恰 12px = 配对门内,继承附着'

    # 越门 13px(x 轴)= 未配对消失 + 新现:旧键清洗、新键重采样
    calls = _record_writes(gs, monkeypatch)
    rolls = _count_rolls(monkeypatch)
    report_spheres_observed(gs, _sight([_ore('金', 125, 100)]),
                            obs_sig=_SIG_OBS, hook_sig=_SIG_HOOK,
                            evidence='')
    assert rolls[0] == 1, '越门新现 = 未配对新现,重掷一次'
    assert '112,100' not in (gs.ore_rewards.value or {}), '消失清洗'
    assert '125,100' in (gs.ore_rewards.value or {}), '新现重采样'
    assert ('ore_rewards', 'ore_gen_cleanup', 'rand') in calls, \
        f'清洗写行留痕: {calls}'


# ============================================================ 生成集与步序写行


def test_generation_set_level_missing_then_recover(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """生成集 = 无附着现役身份:level 缺读帧不生成(声明留队、身份无键、
    零 roll),补读帧同坐标自动再进生成集补生成;合并写 evidence
    ore_gen#p{plane}+{n};声明金占席、其余采样。"""
    monkeypatch.setattr(cw_action_report_pkg, '_ACTION_RNG_PROVIDER',
                        lambda tool: random.Random(11))
    gs = _make_gs(plane=2, level=None,
                  pending=((_ENV, 2, 8),))
    rolls = _count_rolls(monkeypatch)

    report_spheres_observed(
        gs, _sight([_ore('金', 200, 200), _ore('蓝', 300, 300)]),
        obs_sig=_SIG_OBS, hook_sig=_SIG_HOOK, evidence='')
    assert gs.ore_rewards.value in (None, {}), 'level 缺读帧不生成'
    assert rolls[0] == 0
    assert gs.ore_declared_pending.value == ((_ENV, 2, 8),), '声明留队'

    gs.observe(gs.level, 5, sig=_SIG_OBS)
    calls = _record_writes(gs, monkeypatch)
    report_spheres_observed(
        gs, _sight([_ore('金', 200, 200), _ore('蓝', 300, 300)]),
        obs_sig=_SIG_OBS, hook_sig=_SIG_HOOK, evidence='')
    assert rolls[0] == 1, \
        '补读帧:声明金 rng.choice 占席(非 roll)+ 其余一矿采样一次'
    assert ('ore_rewards', 'ore_gen#p2+2', 'rand') in calls, \
        f'生成合并写 evidence: {calls}'
    golds = [r for r in gs.ore_rewards.value.values() if r.kind == 'gold']
    assert any(r.gold == 8 for r in golds), '声明金 8(位面 2 档)占席'
    assert gs.ore_declared_pending.value == () \
        and gs.ore_declared_done.value == ((_ENV, 2),), '消费同帧闭合'


def test_entry_step_evidence_sequence(monkeypatch: pytest.MonkeyPatch) -> None:
    """入口步序写行(单帧三写并置):一矿漂移(重挂)∪ 一矿消失(清洗)∪
    一矿新现(生成)——evidence 三段各自落行;零变化帧零写。"""
    monkeypatch.setattr(cw_action_report_pkg, '_ACTION_RNG_PROVIDER',
                        lambda tool: random.Random(3))
    gs = _make_gs(plane=1, level=5)
    report_spheres_observed(
        gs, _sight([_ore('金', 100, 100), _ore('蓝', 900, 900)]),
        obs_sig=_SIG_OBS, hook_sig=_SIG_HOOK, evidence='')

    calls = _record_writes(gs, monkeypatch)
    report_spheres_observed(
        gs, _sight([_ore('金', 105, 103), _ore('灰', 500, 500)]),
        obs_sig=_SIG_OBS, hook_sig=_SIG_HOOK, evidence='')
    evs = [(n, e) for n, e, _c in calls if n == 'ore_rewards']
    assert evs == [('ore_rewards', 'ore_gen_rekey#p1'),
                   ('ore_rewards', 'ore_gen#p1+1'),
                   ('ore_rewards', 'ore_gen_cleanup')], \
        f'重挂 → 生成 → 清洗三写各落一行: {evs}'
    assert '105,103' in gs.ore_rewards.value, '漂移矿重挂后仍在'
    assert '500,500' in gs.ore_rewards.value, '新现矿已生成'
    assert '900,900' not in gs.ore_rewards.value, '消失矿已清洗'

    # 零变化帧(同坐标重报):零配对变化 ∧ 零新现 ∧ 零消失 → 零写
    calls2 = _record_writes(gs, monkeypatch)
    report_spheres_observed(
        gs, _sight([_ore('金', 105, 103), _ore('灰', 500, 500)]),
        obs_sig=_SIG_OBS, hook_sig=_SIG_HOOK, evidence='')
    assert [c for c in calls2 if c[0] == 'ore_rewards'] == [], \
        f'零变化帧 ore_rewards 零写: {calls2}'


# ============================================================ 声明入队/过期电平


def test_check_level_enqueue_idempotent_guards(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """入队电平规则:env ∈ 注册表 ∧ (env,plane) ∉ pending ∧ ∉ done →
    追加 (env, plane, 金额[plane-1]);重复检查不重发(pending 守卫);
    消费后 done 守卫跨环不重发;env 不在册 / node 未锚定零写。"""
    gs = _make_gs(plane=1, env=_ENV)
    calls = _record_writes(gs, monkeypatch)
    check_ore_declared_level(gs, hook_sig=_SIG_HOOK)
    assert gs.ore_declared_pending.value == ((_ENV, 1, 6),), \
        '位面 1 档 = 6 金'
    assert [c for c in calls if c[0].startswith('ore_declared')], '有写'

    calls = _record_writes(gs, monkeypatch)
    check_ore_declared_level(gs, hook_sig=_SIG_HOOK)
    assert gs.ore_declared_pending.value == ((_ENV, 1, 6),), 'pending 守卫不重发'
    assert not [c for c in calls if c[0].startswith('ore_declared')], \
        '守卫命中零写'

    # 消费后(pending 清空 + done 在册):跨环重查不重发
    gs.write_logic(gs.ore_declared_pending, (), produced_by='t', sig=_SIG_HOOK)
    gs.write_logic(gs.ore_declared_done, ((_ENV, 1),), produced_by='t',
                   sig=_SIG_HOOK)
    calls = _record_writes(gs, monkeypatch)
    check_ore_declared_level(gs, hook_sig=_SIG_HOOK)
    assert gs.ore_declared_pending.value == (), 'done 守卫不重发'
    assert not [c for c in calls if c[0].startswith('ore_declared')]

    # 位面 2 档 = 8 金(位面过渡形态)
    gs2 = _make_gs(plane=2, env=_ENV)
    check_ore_declared_level(gs2, hook_sig=_SIG_HOOK)
    assert gs2.ore_declared_pending.value == ((_ENV, 2, 8),)

    # env 不在册(非声明矿环境)/未选环境:零写
    for env in ('蓝海', ''):
        gs3 = _make_gs(plane=1, env=env)
        calls = _record_writes(gs3, monkeypatch)
        check_ore_declared_level(gs3, hook_sig=_SIG_HOOK)
        assert not [c for c in calls if c[0].startswith('ore_declared')], \
            f'{env!r} 非声明矿环境零写'

    # node 未锚定(首锚定前):本帧不检查零写
    gs4 = _make_gs(plane=None, env=_ENV)
    calls = _record_writes(gs4, monkeypatch)
    check_ore_declared_level(gs4, hook_sig=_SIG_HOOK)
    assert not [c for c in calls if c[0].startswith('ore_declared')]


def test_check_level_expiry_cleans_old_plane(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """过期电平清理:位面过渡帧(p1→p2)新声明入队 + 旧位面条目移除
    (pending 与 done 同清理,evidence 逐旧位面留痕
    ore_declared_expired#p1)。"""
    gs = _make_gs(plane=2, env=_ENV,
                  pending=((_ENV, 1, 6),),
                  done=((_ENV, 1),))
    calls = _record_writes(gs, monkeypatch)
    check_ore_declared_level(gs, hook_sig=_SIG_HOOK)
    assert gs.ore_declared_pending.value == ((_ENV, 2, 8),), \
        '旧位面条目移除 + 当前面声明入队'
    assert gs.ore_declared_done.value == (), \
        'done 同清理(位面 2 声明未消费无 done 条目——done 追加在消费刻)'
    expiry = [c for c in calls if c[2] == 'logic'
              and c[0].startswith('ore_declared')
              and c[1] is not None]
    assert len(expiry) == 2, f'pending/done 各一行留痕: {calls}'
    assert all(e == 'ore_declared_expired#p1' for _n, e, _c in expiry), \
        f'过期 evidence 形态: {expiry}'


# ============================================================ 种子与快照恢复


def test_seed_and_restore_type_roundtrip() -> None:
    """开局种子底座:三域恒非 None(空 dict/空元组);快照→恢复类型不变:
    ore_rewards 仍 dict[str, OreReward]、声明两域仍 tuple-of-tuple
    (不登记则 dict-of-dicts/list-of-lists 静默类型漂移)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    seed_opening_state(gs)
    assert gs.ore_rewards.value == {}
    assert gs.ore_declared_pending.value == ()
    assert gs.ore_declared_done.value == ()

    # 填充非平凡值(声明金 + 采样值混排)走快照往返
    gs.write_logic_rand(
        gs.ore_rewards,
        {'100,100': OreReward(kind='gold', gold=6),
         '300,300': OreReward(kind='char', char_id='希儿', char_star=1)},
        produced_by='t', sig=_SIG_HOOK)
    gs.write_logic(gs.ore_declared_pending, ((_ENV, 1, 6),),
                   produced_by='t', sig=_SIG_HOOK)
    gs.write_logic(gs.ore_declared_done, ((_ENV, 1),),
                   produced_by='t', sig=_SIG_HOOK)
    snap = gs.full_state_snapshot()

    restored = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(restored, snap)
    vr = restored.ore_rewards.value
    assert isinstance(vr, dict) and all(isinstance(v, OreReward)
                                        for v in vr.values()), \
        f'恢复后 ore_rewards 值类型仍 OreReward: {vr}'
    assert vr == gs.ore_rewards.value, '值往返无损'
    assert restored.ore_declared_pending.value == ((_ENV, 1, 6),)
    assert restored.ore_declared_done.value == ((_ENV, 1),)
    assert isinstance(restored.ore_declared_pending.value, tuple) \
        and isinstance(restored.ore_declared_pending.value[0], tuple), \
        'tuple-of-tuple 不漂移为 list-of-lists'
    # done 随快照存续 = 恢复局(离线回放)不重发声明:守卫电平天然闭合
    gs2 = _make_gs(plane=1, env=_ENV)
    restore_state_snapshot(gs2, snap)
    check_ore_declared_level(gs2, hook_sig=_SIG_HOOK)
    assert gs2.ore_declared_pending.value == ((_ENV, 1, 6),), \
        '恢复 done 在册 → 不重发(仅恢复的 pending 原样保留)'
