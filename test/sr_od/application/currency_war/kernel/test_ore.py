"""晶矿域测试(机制主题文件;席自由派生 → 容器逻辑态 → 奖励附着生成 →
点矿兑现全链)。

被测机制(按节;详设出处见各节 docstring):
- **席自由槽派生读口**:``_ore_bench_free`` 改容器派生读口
  ``bench_free_slots``(旧黑板独立记账退役)——free 由容器 bench 槽位表
  派生、宝箱/典籍占席经 ``slot_occupies`` 口径自动计入、bench 未观察
  → BENCH_CAPACITY 保守(宁多收晶矿不误卖);
- **容器逻辑态**:``ore_click_targets_of`` 读口还原 +
  CwActionCollectOreParam 容器逻辑态(载荷坐标精确摘除/陈旧提案零写/
  空读零目标);
- **奖励附着生成与声明通道**(迭代 2026-10-10-ore-reward-attach 3.1;
  详设 details/ore-reward-channel.md §1-§5):生成函数声明金先占席、
  注册表构建校验、容差配对轨迹继承(≤12px 零重掷)、生成集与步序写行、
  入队电平与过期清理、种子与快照恢复类型不变;
- **点矿随机态兑现**(logic-rand-sampling 3.2 → ore-reward-attach 3.2;
  详设 details/ore-click-consume.md §1/§4):采样器支撑集、附着命中
  零掷骰写序、角色分支 3合1 连锁、席满即止、缺项兜底、None 边界。

(sim 接入调用测试 = 后端侧测试 test_sim_backend.py;观察收尾等值静默/
差异 logic_rand_outcome = 基座测试
test_game_state.py::test_write_logic_rand_and_observe_random_outcome,
不重复。)
"""
from __future__ import annotations

import random

import pytest
from test.sr_od.application.currency_war._cw_helpers import cw4_session

import sr_od.application.currency_war.kernel.cw_action_report as cw_action_report_pkg
import sr_od.application.currency_war.kernel.cw_ore_reward as cw_ore_reward_mod
from sr_od.application.currency_war.data.cw_chars import CHARACTER_ROSTER
from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_action_report import (
    collect_ore as collect_ore_mod,
)
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_collect_ore_param,
)
from sr_od.application.currency_war.kernel.cw_exec_state import (
    BENCH_CAPACITY,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    NodeKey,
    OreSight,
    Unit,
    bench_units_of,
    deployed_rows_of_view,
    game_state_of,
    restore_state_snapshot,
    seed_opening_state,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)
from sr_od.application.currency_war.kernel.cw_ore_channel import (
    check_ore_declared_level,
    report_spheres_observed,
)
from sr_od.application.currency_war.kernel.cw_ore_reward import (
    _SIMPLE_EQUIP_POOL,
    OreReward,
    generate_ore_rewards,
    roll_ore_reward,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    ore_click_targets_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionCollectOreParam,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.entry import (
    _ore_bench_free,
)

_SIG_SEED = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_LOGIC_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep')
_COLLECT_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep',
                          group_id='g1')
# live 挂接写 sig 形态(详设 §5:logic_hook 族,group_id 'prep:ore-channel')
_SIG_HOOK = ChannelSig(family='logic_hook', actor='CwScreenPrep',
                       group_id='prep:ore-channel')


def _ore(color: str, x: int, y: int, r: int = 30) -> tuple[str, int, int, int]:
    return (color, x, y, r)


# ============================================================ 席自由槽派生读口


def _write_bench(session, kinds: list[str]) -> None:
    """按 kind 清单写容器 bench 槽位表('unit' 槽带占位身份)。"""
    gs = game_state_of(session)
    slots = [BenchSlot(kind='empty') for _ in kinds]
    for i, kind in enumerate(kinds):
        if kind == 'unit':
            slots[i] = BenchSlot(kind='unit', unit=Unit(
                char_id=f'c{i}', star=1, equips=[]))
        elif kind in ('supply_box', 'tome'):
            slots[i] = BenchSlot(kind=kind)
    gs.observe(gs.bench, BenchView(slots=slots, capacity=len(kinds)),
               sig=_SIG_SEED)


def test_free_counts_units_and_items():
    """3 角色 + 1 箱 + 1 典籍 = 占 5 席 → free = 4(箱/典籍自动计入)。"""
    session = cw4_session()
    _write_bench(session, ['unit', 'unit', 'unit', 'supply_box', 'tome',
                           'empty', 'empty', 'empty', 'empty'])
    assert _ore_bench_free(game_state_of(session)) == 4


def test_free_unobserved_conservative_capacity():
    """bench 未观察(None = 不确定)→ BENCH_CAPACITY 保守(宁多收晶矿)。"""
    session = cw4_session()
    assert _ore_bench_free(game_state_of(session)) == BENCH_CAPACITY


# ============================================================ 容器逻辑态(读口还原 + 精确摘除)


def _write_spheres(session, points: tuple) -> None:
    """按容器域形态写 spheres(观察写端同款 OreSight 载荷)。"""
    gs = game_state_of(session)
    gs.observe(gs.spheres, OreSight(
        count=len(points),
        colors=tuple(dict.fromkeys(p[0] for p in points)),
        points=points), sig=_SIG_SEED)


def test_ore_click_targets_roundtrip():
    """读口还原:(color,x,y,r) 平铺 → (color, Point, r) 形态逐项对应。"""
    session = cw4_session()
    gs = game_state_of(session)
    _write_spheres(session, (('gold', 100, 200, 30), ('blue', 300, 400, 20)))
    targets = ore_click_targets_of(gs)
    assert [(c, p.x, p.y, r) for c, p, r in targets] == \
        [('gold', 100, 200, 30), ('blue', 300, 400, 20)]


def test_collect_ore_container_precise_drop():
    """容器逻辑态:CwActionCollectOreParam 载荷坐标精确摘除(未被点的晶矿保留);
    count/colors 随载荷同步重算;附着兑现开成即同点移除该键(未被点的
    附着保全)。(logic-rand-sampling 迭代:摘除写改随机态,bench/level
    前置守卫已登记——未观察整批拒。)"""
    session = cw4_session()
    gs = game_state_of(session)
    _write_spheres(session, (('gold', 100, 200, 30), ('blue', 300, 400, 20)))

    gs.observe(gs.bench, BenchView(
        slots=[BenchSlot(kind='empty') for _ in range(9)], capacity=9),
        sig=_SIG_SEED)
    gs.observe(gs.level, 5, sig=_SIG_SEED)
    gs.write_logic_rand(
        gs.ore_rewards,
        {'100,200': OreReward(kind='gold', gold=2),
         '300,400': OreReward(kind='gold', gold=6)},
        produced_by='test-seed', sig=_LOGIC_SIG)
    report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=((300, 400),)), sig=_LOGIC_SIG)
    view = gs.spheres.value
    assert view.points == (('gold', 100, 200, 30),)
    assert view.count == 1 and view.colors == ('gold',)
    assert gs.spheres.source == 'logic_rand', '摘除写属采样状态副本(随机态)'
    assert '300,400' not in gs.ore_rewards.value, '开成即键移除'
    assert '100,200' in gs.ore_rewards.value, '未被点的附着保全'


def test_collect_ore_stale_payload_zero_write():
    """陈旧提案守卫:载荷与容器现值无交集(晶矿已被观察回补) → 零写。"""
    session = cw4_session()
    gs = game_state_of(session)
    _write_spheres(session, (('gold', 100, 200, 30),))
    report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=((999, 999),)), sig=_LOGIC_SIG)
    assert gs.spheres.value.points == (('gold', 100, 200, 30),)


def test_ore_empty_read_yields_no_targets():
    """空读上报语义测试:count=0/points=() 空载荷
    → 读口空列——空读照写语义兑现,防上一帧残留假晶矿坐标喂进点击载荷。"""
    session = cw4_session()
    gs = game_state_of(session)
    _write_spheres(session, ())
    assert ore_click_targets_of(gs) == []


# ============================================================ 奖励附着生成与声明通道

_ENV = '增发货币'


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


def _record_gen_writes(gs: GameState,
                       monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic_rand/write_logic 记录 (字段名, evidence, 通道) 写行
    (声明通道步序断言面)。"""
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


def _count_gen_rolls(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """生成侧 roll_ore_reward 调用计数(透传真实现,零行为变化)。"""
    calls = [0]
    real = cw_ore_reward_mod.roll_ore_reward

    def counting(rng: random.Random, level: int) -> OreReward:
        calls[0] += 1
        return real(rng, level)

    monkeypatch.setattr(cw_ore_reward_mod, 'roll_ore_reward', counting)
    return calls


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


def test_env_ore_grants_registry_and_validation(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """构建校验(import 即炸语义,注入 + 直调,沿 ENV_GIFTS 测试惯用法;
    2026-10-28 治理后只留漂移哨,值形/双源同值随删):孤儿键;
    现表默认通过。"""
    # 现表(与 ENV_ECONOMY 同出卡面 id 103):直调校验器零异常
    assert cw_investments.ENV_ORE_GRANTS == {_ENV: (6, 8, 12)}
    cw_investments._validate_env_ore_grants()

    bad = dict(cw_investments.ENV_ORE_GRANTS)
    bad['不存在环境'] = (6, 8, 12)
    monkeypatch.setattr(cw_investments, 'ENV_ORE_GRANTS', bad)
    with pytest.raises(ValueError, match='孤儿键'):
        cw_investments._validate_env_ore_grants()
    monkeypatch.undo()


def test_pairing_hit_no_reroll_declared_gold_survives(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """声明金在「坐标漂移 ≤12px 连续两帧」下保全:配对命中 = 键重挂、
    值不变、roll 调用计数为零(不重掷);首帧生成即含声明附着,消费 =
    pending 移除 + done 追加。"""
    monkeypatch.setattr(cw_action_report_pkg, '_ACTION_RNG_PROVIDER',
                        lambda tool: random.Random(7))
    gs = _make_gs(plane=1, level=5, env=_ENV,
                  pending=((_ENV, 1, 6),))
    rolls = _count_gen_rolls(monkeypatch)

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
    calls = _record_gen_writes(gs, monkeypatch)
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
    filter_persistent_ores);越门(13px)= 消失清洗 + 新现重掷(键换、
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
    calls = _record_gen_writes(gs, monkeypatch)
    rolls = _count_gen_rolls(monkeypatch)
    report_spheres_observed(gs, _sight([_ore('金', 125, 100)]),
                            obs_sig=_SIG_OBS, hook_sig=_SIG_HOOK,
                            evidence='')
    assert rolls[0] == 1, '越门新现 = 未配对新现,重掷一次'
    assert '112,100' not in (gs.ore_rewards.value or {}), '消失清洗'
    assert '125,100' in (gs.ore_rewards.value or {}), '新现重采样'
    assert ('ore_rewards', 'ore_gen_cleanup', 'rand') in calls, \
        f'清洗写行留痕: {calls}'


def test_generation_set_level_missing_then_recover(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """生成集 = 无附着现役身份:level 缺读帧不生成(声明留队、身份无键、
    零 roll),补读帧同坐标自动再进生成集补生成;合并写 evidence
    ore_gen#p{plane}+{n};声明金占席、其余采样。"""
    monkeypatch.setattr(cw_action_report_pkg, '_ACTION_RNG_PROVIDER',
                        lambda tool: random.Random(11))
    gs = _make_gs(plane=2, level=None,
                  pending=((_ENV, 2, 8),))
    rolls = _count_gen_rolls(monkeypatch)

    report_spheres_observed(
        gs, _sight([_ore('金', 200, 200), _ore('蓝', 300, 300)]),
        obs_sig=_SIG_OBS, hook_sig=_SIG_HOOK, evidence='')
    assert gs.ore_rewards.value in (None, {}), 'level 缺读帧不生成'
    assert rolls[0] == 0
    assert gs.ore_declared_pending.value == ((_ENV, 2, 8),), '声明留队'

    gs.observe(gs.level, 5, sig=_SIG_OBS)
    calls = _record_gen_writes(gs, monkeypatch)
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

    calls = _record_gen_writes(gs, monkeypatch)
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
    calls2 = _record_gen_writes(gs, monkeypatch)
    report_spheres_observed(
        gs, _sight([_ore('金', 105, 103), _ore('灰', 500, 500)]),
        obs_sig=_SIG_OBS, hook_sig=_SIG_HOOK, evidence='')
    assert [c for c in calls2 if c[0] == 'ore_rewards'] == [], \
        f'零变化帧 ore_rewards 零写: {calls2}'


def test_check_level_enqueue_idempotent_guards(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """入队电平规则:env ∈ 注册表 ∧ (env,plane) ∉ pending ∧ ∉ done →
    追加 (env, plane, 金额[plane-1]);重复检查不重发(pending 守卫);
    消费后 done 守卫跨环不重发;env 未登记 / node 未锚定零写。"""
    gs = _make_gs(plane=1, env=_ENV)
    calls = _record_gen_writes(gs, monkeypatch)
    check_ore_declared_level(gs, hook_sig=_SIG_HOOK)
    assert gs.ore_declared_pending.value == ((_ENV, 1, 6),), \
        '位面 1 档 = 6 金'
    assert [c for c in calls if c[0].startswith('ore_declared')], '有写'

    calls = _record_gen_writes(gs, monkeypatch)
    check_ore_declared_level(gs, hook_sig=_SIG_HOOK)
    assert gs.ore_declared_pending.value == ((_ENV, 1, 6),), 'pending 守卫不重发'
    assert not [c for c in calls if c[0].startswith('ore_declared')], \
        '守卫命中零写'

    # 消费后(pending 清空 + done 已登记):跨环重查不重发
    gs.write_logic(gs.ore_declared_pending, (), produced_by='t', sig=_SIG_HOOK)
    gs.write_logic(gs.ore_declared_done, ((_ENV, 1),), produced_by='t',
                   sig=_SIG_HOOK)
    calls = _record_gen_writes(gs, monkeypatch)
    check_ore_declared_level(gs, hook_sig=_SIG_HOOK)
    assert gs.ore_declared_pending.value == (), 'done 守卫不重发'
    assert not [c for c in calls if c[0].startswith('ore_declared')]

    # 位面 2 档 = 8 金(位面过渡形态)
    gs2 = _make_gs(plane=2, env=_ENV)
    check_ore_declared_level(gs2, hook_sig=_SIG_HOOK)
    assert gs2.ore_declared_pending.value == ((_ENV, 2, 8),)

    # env 未登记(非声明矿环境)/未选环境:零写
    for env in ('蓝海', ''):
        gs3 = _make_gs(plane=1, env=env)
        calls = _record_gen_writes(gs3, monkeypatch)
        check_ore_declared_level(gs3, hook_sig=_SIG_HOOK)
        assert not [c for c in calls if c[0].startswith('ore_declared')], \
            f'{env!r} 非声明矿环境零写'

    # node 未锚定(首锚定前):本帧不检查零写
    gs4 = _make_gs(plane=None, env=_ENV)
    calls = _record_gen_writes(gs4, monkeypatch)
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
    calls = _record_gen_writes(gs, monkeypatch)
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


def test_seed_and_restore_type_roundtrip() -> None:
    """开局初始值:三域恒非 None(空 dict/空元组);快照→恢复类型不变:
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
        '恢复 done 已登记 → 不重发(仅恢复的 pending 原样保留)'


# ============================================================ 点矿随机态兑现


def _bench(units: list[tuple[str, int]]) -> BenchView:
    slots = [BenchSlot(kind='unit',
                       unit=Unit(char_id=c, star=s))
             for i, (c, s) in enumerate(units)]
    while len(slots) < 9:
        slots.append(BenchSlot(kind='empty'))
    return BenchView(slots=slots, capacity=9)


def _coll_gs(*, bench: list[tuple[str, int]] | None = None,
             front: list[Unit] | None = None,
             gold: int | None = 30,
             equips: list[str] | None = None,
             level: int | None = 5,
             ores: list[tuple[str, int, int, int]] | None = None,
             board: dict | None = None) -> GameState:
    """点矿兑现测试容器(观测面按参组装,None = 保持未观察,供 None 边界分支)。"""
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
        gs.observe(gs.deployed, _dvs(list(front), []), sig=_SIG_OBS)
    if board is not None:
        gs.observe(gs.board, dict(board), sig=_SIG_OBS)
    return gs


def _attach(gs: GameState, rewards: dict[str, OreReward]) -> None:
    """预置 ore_rewards 附着域(挂接入口同款随机态直写,测试基础数据)。"""
    gs.write_logic_rand(gs.ore_rewards, dict(rewards),
                        produced_by='test-seed', sig=_COLLECT_SIG)


def _count_collect_rolls(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """兑现侧 roll_ore_reward 调用计数(透传真实现零行为变化;命中零掷/
    兜底恰掷一次的断言口)。"""
    calls = [0]
    real = collect_ore_mod.roll_ore_reward

    def counting(rng: random.Random, level: int) -> OreReward:
        calls[0] += 1
        return real(rng, level)

    monkeypatch.setattr(collect_ore_mod, 'roll_ore_reward', counting)
    return calls


def _record_collect_writes(gs: GameState,
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


def test_sampler_support_set_and_reproducibility() -> None:
    """采样器支撑集(定种子):gold ∈ 1..5 / equip ∈ 简易池 / char ∈ 注册表
    且星级恒 1,三形态全部可达;同种子同序列(sim 可复现)。"""
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


def test_gold_branch_write_sequence(monkeypatch: pytest.MonkeyPatch) -> None:
    """金分支写序(附着命中):spheres 摘除 → 附着键移除
    (ore_reward_detach#ore1,随摘除同点随机态写)→ 未抽中域标记
    (equips/bench/front/back)→ 奖励金;全部 logic_rand、同组 group_id;
    命中零掷骰(roll 调用计数为零),开成键从 ore_rewards 移除。"""
    gs = _coll_gs(bench=[('阿格莱雅', 1)], front=[Unit(char_id='黑塔', star=1)],
                  equips=[], ores=[_ore('金', 1, 1)])
    _attach(gs, {'1,1': OreReward(kind='gold', gold=3)})
    calls = _record_collect_writes(gs, monkeypatch)
    rolls = _count_collect_rolls(monkeypatch)
    param = CwActionCollectOreParam(points=((1, 1),))
    out = report_action_collect_ore_param(gs, param, _COLLECT_SIG)
    assert out.applied is True
    assert rolls[0] == 0, '附着命中零掷骰(掷骰已前移到生成侧)'
    assert [(n, e) for n, e, _ in calls] == [
        ('spheres', 'proj_collect_ore_drop#ore1'),
        ('ore_rewards', 'ore_reward_detach#ore1'),
        ('equips', 'proj_ore_mark_equips#ore1'),
        ('bench', 'proj_ore_mark_bench#ore1'),
        ('deployed', 'proj_ore_mark_deployed#ore1'),
        ('gold', 'proj_ore_reward_gold#ore1'),
    ], f'写序不符: {[(n, e) for n, e, _ in calls]}'
    assert {g for _, _, g in calls} == {'g1'}, '同动作同组'
    assert gs.gold.value == 33 and gs.gold.source == 'logic_rand'
    assert gs.equips.value == [] and gs.equips.source == 'logic_rand', \
        '未抽中域值不变仅翻来源'
    assert gs.spheres.value.count == 0, '晶矿已摘除'
    assert gs.ore_rewards.value == {}, '开成即附着键移除'


def test_char_branch_merge_dual_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    """角色分支·载体在场上:bench 素材置 None + 行域载体升星 = 双域变更,
    merge 级受影响域各落一行(evidence 同号)。board 断言 = 增量为零不写
    (升星不改羁绊标签,派生零差零写;继承机制由 board 专测)。"""
    gs = _coll_gs(bench=[('A', 1)], front=[Unit(char_id='A', star=1)], board={},
                  ores=[_ore('金', 1, 1)])
    _attach(gs, {'1,1': OreReward(kind='char', char_id='A')})
    calls = _record_collect_writes(gs, monkeypatch)
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=((1, 1),)), _COLLECT_SIG)
    assert out.applied is True
    by_ev = {e: n for n, e, _ in calls}
    assert by_ev.get('proj_ore_reward_char#ore1') == 'bench'
    assert by_ev.get('proj_ore_merge#1#ore1') is not None, \
        '一级合并落行(双域同号,行序内断言见下)'
    merge_fields = [n for n, e, _ in calls
                    if e == 'proj_ore_merge#1#ore1']
    assert merge_fields == ['bench', 'deployed'], \
        f'双域变更各落一行(bench 素材清 + 行载体升星;行域合卷 = deployed 单行): {merge_fields}'
    assert [u.star for u in bench_units_of(gs)] == [], \
        'bench 侧素材全部置 None(载体在场上)'
    assert deployed_rows_of_view(gs.deployed.value)[0][0].star == 2, '场上载体升 2★'
    board_writes = [c for c in calls if c[0] == 'board']
    assert board_writes == [], \
        '升星不改羁绊标签 → board 增量为零零写(派生量纪律)'


def test_char_branch_bench_carrier_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    """角色分支·载体在备战(3×1★ 备战内合并):bench 两次写(落位行 +
    merge 行),行域未被合成触及 → 步 4 值不变标记。"""
    gs = _coll_gs(bench=[('A', 1), ('A', 1)], front=[], ores=[_ore('金', 1, 1)])
    _attach(gs, {'1,1': OreReward(kind='char', char_id='A')})
    calls = _record_collect_writes(gs, monkeypatch)
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=((1, 1),)), _COLLECT_SIG)
    assert out.applied is True
    stars = [u.star for u in bench_units_of(gs)]
    assert stars == [2], '3×1★ → 2★ 载体留备战'
    seq = [(n, e) for n, e, _ in calls]
    assert ('bench', 'proj_ore_reward_char#ore1') in seq, '落位行'
    assert ('bench', 'proj_ore_merge#1#ore1') in seq, '合成行'
    assert ('deployed', 'proj_ore_mark_deployed#ore1') in seq, \
        '行域未触及 → 值不变标记'


def test_multi_point_full_bench_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    """全席满:逐点判守卫全跳过 → applied=False 'bench_full_no_open',
    spheres 零写(晶矿全部保留),零掷骰,附着键随矿保全(未被兑现)。"""
    gs = _coll_gs(bench=[('A', i + 1) for i in range(9)],
                  ores=[_ore('金', 1, 1), _ore('金', 2, 2)])
    _attach(gs, {'1,1': OreReward(kind='gold', gold=1),
                 '2,2': OreReward(kind='gold', gold=1)})
    rolls = _count_collect_rolls(monkeypatch)
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=((1, 1), (2, 2))), _COLLECT_SIG)
    assert out.applied is False and out.reason == 'bench_full_no_open'
    assert rolls[0] == 0, '席满点不采样'
    assert gs.spheres.value.count == 2, '晶矿全部保留'
    assert set(gs.ore_rewards.value) == {'1,1', '2,2'}, \
        '跳点附着随矿保全(键不提前移除)'


def test_multi_point_partial_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    """混合批:首点角色奖励耗掉最后空位 → 次点席满跳过(留在 spheres),
    出参 'ore_partial_open_skipped',已开点照常入账。"""
    slots = [BenchSlot(kind='unit',
                       unit=Unit(char_id=f'F{i}', star=1))
             for i in range(8)] + [BenchSlot(kind='empty')]
    gs = _coll_gs(ores=[_ore('金', 1, 1), _ore('金', 2, 2)])
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    _attach(gs, {'1,1': OreReward(kind='char', char_id='B')})
    calls = _record_collect_writes(gs, monkeypatch)
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=((1, 1), (2, 2))), _COLLECT_SIG)
    assert out.applied is True and out.reason == 'ore_partial_open_skipped'
    evs = [e for _, e, _ in calls]
    assert 'proj_collect_ore_drop#ore1' in evs, '首点开成'
    assert not any(e.endswith('#ore2') for e in evs), '次点席满不写不采'
    assert gs.spheres.value.count == 1, '未开晶矿留在 spheres'
    assert '1,1' not in (gs.ore_rewards.value or {}), '已开点附着键移除'
    names = [u.char_id for u in bench_units_of(gs)]
    assert names.count('B') == 1, '角色奖励已落位(耗掉最后空位)'


def test_char_reward_preserves_item_slot_kinds(monkeypatch: pytest.MonkeyPatch) -> None:
    """占位件 kind 保留(回归测试):bench 有典籍/书册卡/箱槽时,角色奖励
    整表写不得把它们降级 supply_box——降级会让后续 OpenTome/OpenBookcard
    按 kind 找不到槽(真缺陷,不定态随机抽中角色时触发)。"""
    slots = [BenchSlot(kind='unit', unit=Unit(char_id='A', star=1)),
             BenchSlot(kind='unit', unit=Unit(char_id='A', star=1)),
             BenchSlot(kind='tome'),
             BenchSlot(kind='bookcard'),
             BenchSlot(kind='supply_box')]
    slots += [BenchSlot(kind='empty') for _ in range(4)]
    gs = _coll_gs(ores=[_ore('金', 1, 1)])
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    _attach(gs, {'1,1': OreReward(kind='char', char_id='A')})
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=((1, 1),)), _COLLECT_SIG)
    assert out.applied is True
    kinds = [s.kind for s in gs.bench.value.slots]
    assert kinds[2] == 'tome' and kinds[3] == 'bookcard' \
        and kinds[4] == 'supply_box', f'占位件 kind 不得降级: {kinds}'
    units = [s for s in gs.bench.value.slots if s.kind == 'unit']
    assert len(units) == 1 and units[0].unit.star == 2, '3×1★ → 2★ 载体'


def test_missing_attach_fallback_evidence_prefix(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """缺项兜底路径:无附着键 → roll_ore_reward 兜底恰掷一次(沿现解析
    口,同种子同输出),该点全部写行 evidence 前缀
    'ore_reward_attach_missing#'(含 drop/标记/奖励应用),无 detach 行;
    采样结果照常应用(兜底采样器即原采样器)。"""
    gs = _coll_gs(bench=[('A', 1)], gold=30, equips=[],
                  ores=[_ore('金', 1, 1)])   # 不预置附着域 = 缺项
    calls = _record_collect_writes(gs, monkeypatch)
    rolls = _count_collect_rolls(monkeypatch)
    expected = roll_ore_reward(random.Random(21), 5)
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=((1, 1),)), _COLLECT_SIG,
        rng=random.Random(21))
    assert out.applied is True
    assert rolls[0] == 1, '缺项兜底恰掷一次'
    evs = [(n, e) for n, e, _ in calls]
    assert evs and all(e.startswith('ore_reward_attach_missing#')
                       for _n, e in evs), f'该点全部写行带前缀: {evs}'
    assert ('spheres',
            'ore_reward_attach_missing#proj_collect_ore_drop#ore1') in evs, \
        'drop 行带前缀'
    assert not any('ore_reward_detach' in e for _n, e in evs), \
        '缺项无键可摘,零 detach 行'
    if expected.kind == 'gold':
        assert gs.gold.value == 30 + expected.gold
    elif expected.kind == 'equip':
        assert gs.equips.value == [expected.equip]
    else:
        assert expected.char_id in [u.char_id for u in bench_units_of(gs)]


def test_hit_needs_no_level_and_missing_level_reason_precedence(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """level 语义收窄:附着命中不需 level(level 缺读照开成入账);同批
    缺项点因 level 缺读跳过(矿留 spheres 零写)→ 出参 reason
    'ore_reward_attach_missing_level'(优先于 ore_partial_open_skipped
    表达具体原因),命中点键移除。"""
    gs = _coll_gs(bench=[('A', 1)], gold=30, equips=[], level=None,
                  ores=[_ore('金', 1, 1), _ore('金', 2, 2)])
    _attach(gs, {'1,1': OreReward(kind='gold', gold=4)})
    rolls = _count_collect_rolls(monkeypatch)
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=((1, 1), (2, 2))), _COLLECT_SIG)
    assert out.applied is True \
        and out.reason == 'ore_reward_attach_missing_level'
    assert rolls[0] == 0, '命中点零掷;缺项点因 level 缺读不掷(跳过)'
    assert gs.gold.value == 34, '命中点照常兑现(不需 level)'
    assert gs.spheres.value.count == 1, '缺项点矿留 spheres 不摘'
    assert gs.ore_rewards.value == {}, '命中点键移除(缺项点本无键)'


def test_none_domains_skip_and_missing_level_reason(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """None 边界:equips 未观察 → 无标记无奖励写(诚实缺失);缺项 ∧
    level 缺读 → 该点跳过不采,reason 'ore_reward_attach_missing_level'
    (零写跳过,reason 是唯一可断言通道)。"""
    gs = _coll_gs(bench=[('A', 1)], gold=30, equips=None, level=None,
                  ores=[_ore('金', 1, 1)])
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=((1, 1),)), _COLLECT_SIG)
    assert out.applied is False \
        and out.reason == 'ore_reward_attach_missing_level'
    assert gs.spheres.value.count == 1, '跳过点先于任何写(矿留 spheres)'

    gs2 = _coll_gs(bench=[('A', 1)], gold=30, equips=None, level=5,
                   ores=[_ore('金', 1, 1)])
    _attach(gs2, {'1,1': OreReward(kind='equip', equip='幸运星')})
    calls = _record_collect_writes(gs2, monkeypatch)
    out2 = report_action_collect_ore_param(
        gs2, CwActionCollectOreParam(points=((1, 1),)), _COLLECT_SIG)
    assert out2.applied is True
    assert not any(n == 'equips' for n, _, _ in calls), \
        '抽中域 None → 跳采样写(等观察),不编 None 值'


def test_bench_unobserved_rejects_whole_batch() -> None:
    """bench 未观察 → 整批拒 'bench_unobserved'(席满守卫与角色落点
    均不可判)。"""
    gs = _coll_gs(bench=None, ores=[_ore('金', 1, 1)])
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=((1, 1),)), _COLLECT_SIG)
    assert out.applied is False and out.reason == 'bench_unobserved'
    assert gs.spheres.value.count == 1, '拒分支零写'


def test_corner_mixed_batch_missing_level_reason_precedence(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """三方并存混合批(命中 + 席满 + 缺项∧level 缺读):缺项点因 level
    缺读先跳(彼时席未满),命中角色奖励耗掉最后空位 → 后续点席满跳过
    → 出参 reason 'ore_reward_attach_missing_level'(优先于
    ore_partial_open_skipped 表达具体原因;含席满跳点的混合批同此,
    钉住现状防将来无意翻转)。几何事实:席满判定读 work_bench 现值,
    批内仅角色奖励落位改变之——两类跳点只能在含命中点的混合批并存。"""
    slots = [BenchSlot(kind='unit',
                       unit=Unit(char_id=f'F{i}', star=1))
             for i in range(8)] + [BenchSlot(kind='empty')]
    gs = _coll_gs(level=None, ores=[_ore('金', 1, 1), _ore('金', 2, 2),
                                    _ore('金', 3, 3)])
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    _attach(gs, {'2,2': OreReward(kind='char', char_id='B')})
    rolls = _count_collect_rolls(monkeypatch)
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=((1, 1), (2, 2), (3, 3))), _COLLECT_SIG)
    assert out.applied is True \
        and out.reason == 'ore_reward_attach_missing_level'
    assert rolls[0] == 0, '命中零掷;缺项点 level 缺读不掷(跳过)'
    assert gs.spheres.value.count == 2, '跳点矿留 spheres(缺项点+席满点)'
    assert gs.ore_rewards.value == {}, '命中点开成即键移除'
    names = [u.char_id for u in bench_units_of(gs)]
    assert names.count('B') == 1, '命中角色奖励落位(耗掉最后空位)'


def test_corner_full_bench_masks_missing_level_all_skip(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """全跳批·席满掩蔽:席满守卫先于缺项∧level 判定——席满批内各点
    不达缺项检查(missing_level 恒 0),出参 'bench_full_no_open' 而非
    'ore_reward_attach_missing_level';零写零掷(校验守卫次序)。"""
    gs = _coll_gs(bench=[('A', i + 1) for i in range(9)], level=None,
                  ores=[_ore('金', 1, 1), _ore('金', 2, 2)])
    rolls = _count_collect_rolls(monkeypatch)
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=((1, 1), (2, 2))), _COLLECT_SIG)
    assert out.applied is False and out.reason == 'bench_full_no_open'
    assert rolls[0] == 0, '席满点不采样'
    assert gs.spheres.value.count == 2, '晶矿全部保留'
