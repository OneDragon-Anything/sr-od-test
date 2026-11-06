"""check_env_boss_grants 首领节点条件发放测试(镜像 src =
kernel/cw_env_grants.py 的该被测函数;同文件兄弟触发函数测试 =
kernel/test_env_grants.py,本文件按被测方法拆目录规范落位)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc
designs/T-19-laowu-paiqian-hetong.md(定稿)§2.3 + §4.3-§4.5:
- **全条件矩阵**(八序短路):env 空链/不在册/node_pos None(直构防御,
  live hist 未建禁猜)/本节点已发(done 幂等)/绑定缺失(无快照接管局
  形态,宁缺勿造)/bench 未观察(缓发不标 boss 键)/达标发放;
- **周期性**:序贯两个首领节点坐标(按现役 node_sequence_of 取实际
  boss 位)各发一次;同节点重复调用零新增写;
- **实机(live)和模拟器(sim)两边互斥**:sim 形态 sig(logic_action)与 live 形态 sig(logic_hook)
  先后各调一次,另一路径重调 = done 短路零双发;
- **两写契约**:角色链 + done boss 键同 evidence 同 sig 相邻。
"""
from __future__ import annotations

import random

import pytest

from sr_od.application.currency_war.data.cw_chars import chars_by_faction
from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_env_grants import (
    BOSS_NODE_KEY_PREFIX,
    STAR_GRANT_KEY_PREFIX,
    check_env_boss_grants,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_node_schedule import (
    node_sequence_of,
)

_ENV = '劳务派遣合同'
_BIND_STAR = '列车同行星徽'   # 绑定用星徽(羁绊名 = 去「星徽」后缀)
_FACTION = '列车同行'

_SIG_HOOK = ChannelSig(family='logic_hook', actor='CwScreenBossBriefing',
                       group_id='boss-briefing:env-grant')
_SIG_SIM = ChannelSig(family='logic_action', actor='SimBackend',
                      mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')


def _boss_round(plane: int) -> int:
    """现役序列下该位面首领节点轮号(node_sequence_of 真值表现算,
    默认环境 P1 r9 / P2 r7;不手抄)。"""
    return node_sequence_of(plane).index('boss') + 1


def _make_gs(*, env: str | None = _ENV,
             bench: list[tuple[str, int]] | None = None,
             done: tuple[tuple[str, str], ...] | None = None
             ) -> GameState:
    """观察面按参组装(None = 保持未写形态;done 域经 logic 直写播种)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if env is not None:
        gs.observe(gs.active_env, env, sig=_SIG_OBS)
    if bench is not None:
        from sr_od.application.currency_war.kernel.cw_game_state import Unit
        slots: list[BenchSlot | None] = [BenchSlot(kind='empty')] * 9
        for i, (c, s) in enumerate(bench):
            slots[i] = BenchSlot(kind='unit', unit=Unit(char_id=c, star=s))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    if done is not None:
        gs.write_logic(gs.env_grants_done, tuple(done),
                       produced_by='test-seed',
                       sig=ChannelSig(family='logic_action',
                                      actor='test-seed', mode='compute'))
    return gs


def _record_writes(gs: GameState,
                   monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic_rand/write_logic 记录 (字段名, evidence, 通道, sig)
    写行(先例 = kernel/test_env_grants.py 同名 helper)。"""
    calls: list[tuple[str, str | None, str, ChannelSig]] = []

    def _wrap(real, channel: str):
        def rec(target, value, *, produced_by, evidence=None, sig, note=''):
            calls.append((gs._field_name(target), evidence, channel, sig))
            real(target, value, produced_by=produced_by, evidence=evidence,
                 sig=sig, note=note)
        return rec

    monkeypatch.setattr(gs, 'write_logic_rand',
                        _wrap(gs.write_logic_rand, 'rand'))
    monkeypatch.setattr(gs, 'write_logic',
                        _wrap(gs.write_logic, 'logic'))
    return calls


def _bench_units(gs: GameState) -> list[tuple[str, int]]:
    return [(s.unit.char_id, s.unit.star) for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]


def _seed_done() -> tuple[tuple[str, str], ...]:
    """分支1 绑定态 done 种子(发放名 = 列车同行星徽)。"""
    return ((_ENV, f'{STAR_GRANT_KEY_PREFIX}{_BIND_STAR}'),)


# ============================================================ 条件矩阵


def test_condition_matrix_short_circuits(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """条件矩阵前六序短路(T-19 设计 §2.3 条 1-6,§4.3 全矩阵锁):
    env 空链(None/'')/不在册/node_pos None(直构防御,live hist 未建禁
    猜)/本节点已发(done 幂等)/绑定缺失(无快照接管局形态)→ 全部
    None 且零写。"""
    done_seed = _seed_done()
    boss = _boss_round(1)
    cases: list[tuple[str, GameState, tuple[int, int] | None]] = [
        ('env 未选择(None 形态)', _make_gs(env=None, bench=[], done=done_seed),
         (1, boss)),
        ('env 空链(开局种子形态)', _make_gs(env='', bench=[], done=done_seed),
         (1, boss)),
        ('env 不在册', _make_gs(env='蓝海', bench=[], done=done_seed),
         (1, boss)),
        ('node_pos None(hist 未建禁猜)',
         _make_gs(bench=[], done=done_seed), None),
        ('本节点已发(done 幂等)',
         _make_gs(bench=[],
                  done=done_seed + ((_ENV, f'{BOSS_NODE_KEY_PREFIX}1-{boss}'),)),
         (1, boss)),
        ('绑定缺失(接管局形态)', _make_gs(bench=[], done=()), (1, boss)),
    ]
    for label, gs, pos in cases:
        calls = _record_writes(gs, monkeypatch)
        assert check_env_boss_grants(gs, node_pos=pos, rng=random.Random(1),
                                     sig=_SIG_SIM) is None, label
        assert not calls, f'{label} 零写: {calls}'


def test_binding_missing_no_prefix_key_for_other_env(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """绑定缺失按环境分账:其他环境的 star_grant# 键不算本环境绑定
    (键检查 scoped 到本 env),照缺照零写。"""
    gs = _make_gs(bench=[], done=(('别的环境', f'{STAR_GRANT_KEY_PREFIX}红钻'),))
    calls = _record_writes(gs, monkeypatch)
    assert check_env_boss_grants(gs, node_pos=(1, _boss_round(1)),
                                 rng=random.Random(1), sig=_SIG_SIM) is None
    assert not calls, f'他环境绑定不顶本环境: {calls}'


def test_bench_unobserved_withhold_no_done(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """bench 未观察(直构形态防御,T-19 设计 §2.3 条 7):零写且不标
    boss 键(boss 窗一次性无自动重试 = 该节点漏发,披露面在册)。"""
    gs = _make_gs(bench=None, done=_seed_done())
    assert gs.bench.value is None
    calls = _record_writes(gs, monkeypatch)
    assert check_env_boss_grants(gs, node_pos=(1, _boss_round(1)),
                                 rng=random.Random(1), sig=_SIG_SIM) is None
    assert not calls, f'缓发零写: {calls}'
    assert gs.env_grants_done.value == _seed_done(), '缓发不追加 boss 键'


def test_grant_seeded_roll_two_writes_same_evidence_sig(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """达标发放(T-19 设计 §2.3 条 8):注确定 rng → bench 追加 1 个 1★
    角色且名 ∈ 绑定羁绊采样池(期望名同 seed 现算,不手抄;池 = 生产端
    同源 random_char_pool 现算——分支2 池派生与随机赠卡家族单一源,开拓者
    双形态按角色位合并,采样即发放名恒欢愉);两段写同 evidence 同 sig
    相邻(角色链在前,done boss 键收尾)。"""
    gs = _make_gs(bench=[], done=_seed_done())
    pos = (1, _boss_round(1))
    pool = cw_investments.random_char_pool(
        cw_investments.RandomCharSpec(faction=_FACTION, star=1))
    expected = random.Random(20261015).choice(pool)
    calls = _record_writes(gs, monkeypatch)

    granted = check_env_boss_grants(gs, node_pos=pos,
                                    rng=random.Random(20261015),
                                    sig=_SIG_SIM)

    evidence = f'env_grant#{_ENV}#boss1-{pos[1]}'
    assert granted == expected, '返回角色名(仅日志面消费)'
    assert _bench_units(gs) == [(expected, 1)], '落席 1 个,星级 1★ 先验'
    assert gs.env_grants_done.value == _seed_done() + (
        (_ENV, f'{BOSS_NODE_KEY_PREFIX}1-{pos[1]}'),), 'done 追加 boss 键'
    assert len(calls) == 2, f'两段写: {calls}'
    assert calls[0][0] == 'bench' and calls[0][2] == 'rand', \
        '角色链 = bench 写(采样 → rand 通道)'
    assert calls[1] == ('env_grants_done', evidence, 'logic', _SIG_SIM), \
        f'done 写 evidence/sig 契约: {calls[1]}'
    assert calls[0][1] == f'{evidence}#place', '角色链 evidence = done 前缀'
    assert calls[0][3] == _SIG_SIM, '两写同 sig'


def test_grant_rejects_obs_sig() -> None:
    """sig 单形态契约:obs 族进触发函数即炸渠道族校验(禁 obs_sig,
    streak 通道同款)。"""
    gs = _make_gs(bench=[], done=_seed_done())
    with pytest.raises(ValueError, match='渠道族'):
        check_env_boss_grants(gs, node_pos=(1, _boss_round(1)),
                              rng=random.Random(1), sig=_SIG_OBS)
    assert _bench_units(gs) == [], '炸错前置零写'


# ============================================================ 周期性


def test_periodicity_two_boss_nodes_then_repeat(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """周期性(T-19 设计 §4.4):序贯两个 boss 节点坐标(P1/P2 现役 boss
    位现算)各发一次(done 各记一键);同节点重复调用零新增写(幂等
    短路)。"""
    gs = _make_gs(bench=[], done=_seed_done())
    p1 = (1, _boss_round(1))
    p2 = (2, _boss_round(2))

    first = check_env_boss_grants(gs, node_pos=p1, rng=random.Random(11),
                                  sig=_SIG_SIM)
    second = check_env_boss_grants(gs, node_pos=p2, rng=random.Random(22),
                                   sig=_SIG_SIM)
    assert first is not None and second is not None, '两节点各发一次'
    pool = {c.name for c in chars_by_faction(_FACTION)}
    assert first in pool and second in pool, '各自采样,均落绑定羁绊池'
    assert gs.env_grants_done.value == _seed_done() + (
        (_ENV, f'{BOSS_NODE_KEY_PREFIX}1-{p1[1]}'),
        (_ENV, f'{BOSS_NODE_KEY_PREFIX}2-{p2[1]}')), '两节点两键'

    calls = _record_writes(gs, monkeypatch)
    assert check_env_boss_grants(gs, node_pos=p1, rng=random.Random(11),
                                 sig=_SIG_SIM) is None, '同节点重查零发'
    assert not calls, f'幂等零写: {calls}'


def test_dual_path_done_short_circuit(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """实机和模拟器两边互斥(T-19 设计 §4.5):一端发放后,另一路径(live logic_hook
    形态 / sim logic_action 形态)重调同节点 = done 短路零双发(两形态
    各验一个方向)。"""
    gs = _make_gs(bench=[], done=_seed_done())
    p1 = (1, _boss_round(1))
    p2 = (2, _boss_round(2))

    # sim 形态先发,live 形态重调同节点 → 零写
    assert check_env_boss_grants(gs, node_pos=p1, rng=random.Random(1),
                                 sig=_SIG_SIM) is not None
    calls = _record_writes(gs, monkeypatch)
    assert check_env_boss_grants(gs, node_pos=p1, rng=random.Random(1),
                                 sig=_SIG_HOOK) is None
    assert not calls, f'live 路径重调零写: {calls}'
    monkeypatch.undo()

    # live 形态先发,sim 形态重调同节点 → 零写
    assert check_env_boss_grants(gs, node_pos=p2, rng=random.Random(2),
                                 sig=_SIG_HOOK) is not None
    calls = _record_writes(gs, monkeypatch)
    assert check_env_boss_grants(gs, node_pos=p2, rng=random.Random(2),
                                 sig=_SIG_SIM) is None
    assert not calls, f'sim 路径重调零写: {calls}'


# ============================================================ 登记表联动


def test_binding_pool_consistent_with_registry() -> None:
    """绑定解析链一致性(设计 §2.3 条 8 派生链锁):星徽名去「星徽」后缀
    = 羁绊名,成员池经 chars_by_faction(默认参数含 flows)非空——
    '星徽' 类别池逐件走一遍(注册表现算,22 件全通过)。"""
    for star in cw_investments.equips_by_category('星徽'):
        faction = star[:-len('星徽')]
        assert faction, f'{star} 后缀剥离后羁绊名非空'
        assert chars_by_faction(faction), \
            f'{star} → {faction} 成员池非空(构建期闸同源)'


# ============================================================ 牌库时点池
# (用户裁定 2026-10-28「授予候选 = 当时牌库里存在的角色」,economy.md §8:
# 分支2 采样源 = cw_pool.grant_char_pool,未解锁专家剔除/已解锁专家入候选;
# 示范专家 = 姬子——列车同行域唯一专家成员,factions 轴在域。)


def _gs_with_unlocked(names: tuple[str, ...]) -> GameState:
    """解锁态容器(在 _make_gs 基础上单口直写 unlocked_experts)。"""
    gs = _make_gs(bench=[], done=_seed_done())
    gs.write_logic(gs.unlocked_experts, names, produced_by='test-seed',
                   evidence='test:unlock', sig=_SIG_SIM)
    return gs


def test_boss_leg_deck_time_pool_unlock_expert_reaches_candidates(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """boss 分支2 牌库时点池(economy.md §8 用户裁定 2026-10-28):解锁
    姬子(列车同行域唯一专家)→ seed 9 掷中姬子并落席;同 seed 未解锁
    容器掷星期日(姬子不在候选)——两态对照钉死「已解锁专家 ∈ 授予候选,
    未解锁专家 ∉」。示范专家必须取目标域内专家:停云 ∈ 仙舟/能量不属
    本域,示范不可用(攻击轮 1 F2 防复发约束)。"""
    from sr_od.application.currency_war.kernel.cw_pool import grant_char_pool
    spec = cw_investments.RandomCharSpec(faction=_FACTION, star=1)
    pos = (1, _boss_round(1))
    gs_unlocked = _gs_with_unlocked(('姬子',))
    expected_unlocked = random.Random(9).choice(
        grant_char_pool(gs_unlocked, spec))
    assert expected_unlocked == '姬子', '种子前提:解锁态掷中示范专家'
    calls = _record_writes(gs_unlocked, monkeypatch)
    granted = check_env_boss_grants(gs_unlocked, node_pos=pos,
                                    rng=random.Random(9), sig=_SIG_SIM)
    assert granted == '姬子', '已解锁专家进入分支2候选并被掷中'
    assert _bench_units(gs_unlocked) == [('姬子', 1)], '落席 1★'
    assert calls, '发放有写行'
    monkeypatch.undo()

    gs_locked = _make_gs(bench=[], done=_seed_done())
    expected_locked = random.Random(9).choice(
        grant_char_pool(gs_locked, spec))
    assert expected_locked != '姬子', '种子前提:未解锁态同 seed 掷他名'
    granted_locked = check_env_boss_grants(gs_locked, node_pos=pos,
                                           rng=random.Random(9),
                                           sig=_SIG_SIM)
    assert granted_locked == expected_locked, '未解锁态候选不含专家'
