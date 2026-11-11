"""合成承继实例号测试(镜像 src = kernel/cw_gain_chain.py
_merge_inherit_uid + merge_step_once / kernel/cw_merge_simulate.py
本地同款实现 + merge_simulate)。

测试面依据 = 原稿锁面(§ 号 = 原稿节序)§9.2 个体归属
承载(F1 修,轮 3 对抗立项):合成产物 uid = 素材中已发号 uid 的最小值
(最老个体承继,确定性可复现);素材全未发号 → 产物未发号(None);
锁域豁免 = 承继值命中未解锁上场锁记录 → 弃承继置 None(升星产物可
上场用户裁定口径保留,佩佩族素材恒不在锁域零受扰)。两引擎零 import
独立实现结构(cw_merge_simulate 模块注释「双源收敛」),交叉核对测试
保证一致——本文件即该锁:
- 链端 merge_step_once / 推演端 merge_simulate 同输入产物 uid 一致
  (既有终态交叉核对测试的 uid 面扩展);
- min 规则/全未发号/锁域豁免三形逐验;
- gs=None 纯表形态零豁免(直构/测试形态)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    merge_step_once,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    ChannelSig,
    GameState,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_merge_simulate import (
    merge_simulate,
)

_PP = '佩佩'


def _bench3(uids: list[int | None], name: str = _PP) -> list:
    slots = [BenchSlot(kind='unit',
                       unit=Unit(char_id=name, star=1, uid=u))
             for u in uids]
    return slots + [None] * (9 - len(slots))


def _products(bench: list) -> list[Unit]:
    return [s.unit for s in bench
            if s is not None and s.kind == 'unit' and s.unit is not None]


def _gs() -> GameState:
    return GameState(schema_version=GAME_STATE_SCHEMA_VERSION)


def test_chain_and_simulate_inherit_min_uid() -> None:
    """实机(live)和模拟器(sim)两边一致 + min 规则:三只佩佩 uid 3/1/5 → 产物 2★ 承继 min=1
    (链端与推演端同输入同产物——交叉核对 uid 面);承继后个体仍可被
    离场/穿戴按 uid 命中(「接走佩佩们」卡文不区分星级的承载前提)。"""
    gs = _gs()
    bench_a = _bench3([3, 1, 5])
    result_a = merge_step_once(bench_a, [None] * 10, [], gs=gs)
    assert result_a == (_PP, 2), f'链端升星: {result_a!r}'
    prod_a = _products(bench_a)
    assert [(u.star, u.uid) for u in prod_a] == [(2, 1)], \
        f'链端承继 min(3,1,5)=1: {[(u.star, u.uid) for u in prod_a]!r}'
    bench_b = _bench3([3, 1, 5])
    sim = merge_simulate(bench_b, None, _PP, 1, k=0, gs=gs)
    prod_b = _products(sim.bench_after)
    assert [(u.star, u.uid) for u in prod_b] == [(2, 1)], \
        f'推演端承继一致: {[(u.star, u.uid) for u in prod_b]!r}'


def test_all_unstamped_materials_product_none() -> None:
    """素材全未发号(商店购入形态 uid=None)→ 产物未发号(None,新实体
    现役语义保留;gs=None 纯表形态同)。"""
    gs = _gs()
    bench = _bench3([None, None, None], name='希儿')
    merge_step_once(bench, [None] * 10, [], gs=gs)
    prod = _products(bench)
    assert [(u.star, u.uid) for u in prod] == [(2, None)], \
        f'全未发号产物 None: {[(u.star, u.uid) for u in prod]!r}'


def test_mixed_uids_take_min_of_stamped() -> None:
    """混合素材:已发号 uid 集 = {7} 商店购入 None 不入集 → 产物承继 7
    (min 只取「已发号」面,未发号素材不拉低)。"""
    gs = _gs()
    bench = _bench3([7, None, None])
    merge_step_once(bench, [None] * 10, [], gs=gs)
    prod = _products(bench)
    assert [(u.star, u.uid) for u in prod] == [(2, 7)], \
        f'混合素材承继已发号 min: {[(u.star, u.uid) for u in prod]!r}'


def test_locked_min_uid_waives_inherit_with_gs() -> None:
    """锁域豁免:承继值命中未解锁上场锁记录(env_grant_deploy_locks)→
    弃承继置 None(升星产物可上场用户裁定口径保留);gs=None 时零豁免
    (直构纯表形态承继照常)——两面同输入分叉仅由 gs 在场性决定。"""
    _LSIG = ChannelSig(family='logic_action', actor='TestDriver',
                       mode='compute')
    from sr_od.application.currency_war.kernel.cw_game_state import (
        effective_node_pos,
        seed_opening_state,
    )
    gs = _gs()
    seed_opening_state(gs)
    gs.write_logic(gs.node_pos, (1, 2), produced_by='test-seed',
                   evidence='t:node', sig=_LSIG)
    # 锁记录:uid=1 解锁序位 (2,1)(未解锁,现序 (1,2) < (2,1))
    gs.write_logic(gs.env_grant_deploy_locks,
                   (('流萤', 1, (2, 1)),),
                   produced_by='test-seed', evidence='t:locks',
                   sig=_LSIG)
    eff = effective_node_pos(gs)
    assert eff is None or eff < (2, 1), f'前置:现序未到解锁位 eff={eff!r}'
    bench = _bench3([1, None, None], name='流萤')
    merge_step_once(bench, [None] * 10, [], gs=gs)
    prod = _products(bench)
    assert [(u.star, u.uid) for u in prod] == [(2, None)], \
        f'被锁 min uid 弃承继: {[(u.star, u.uid) for u in prod]!r}'
    # gs=None:零豁免承继照常(交叉核对一致性形态)
    bench2 = _bench3([1, None, None], name='流萤')
    merge_step_once(bench2, [None] * 10, [], gs=None)
    prod2 = _products(bench2)
    assert [(u.star, u.uid) for u in prod2] == [(2, 1)], \
        f'gs=None 零豁免: {[(u.star, u.uid) for u in prod2]!r}'


def test_unlocked_lock_uid_inherits_normally() -> None:
    """已解锁锁记录的 uid 承继照常(豁免只辖「未解锁」——eff >= unlock
    时承继值命中不弃):佩佩族素材恒不在锁域 = 本卡承继零受扰的边界
    证明。"""
    _LSIG = ChannelSig(family='logic_action', actor='TestDriver',
                       mode='compute')
    from sr_od.application.currency_war.kernel.cw_game_state import (
        seed_opening_state,
    )
    gs = _gs()
    seed_opening_state(gs)
    gs.write_logic(gs.node_pos, (2, 1), produced_by='test-seed',
                   evidence='t:node', sig=_LSIG)
    gs.write_logic(gs.env_grant_deploy_locks,
                   (('流萤', 1, (2, 1)),),
                   produced_by='test-seed', evidence='t:locks',
                   sig=_LSIG)
    bench = _bench3([1, None, None], name='流萤')
    merge_step_once(bench, [None] * 10, [], gs=gs)
    prod = _products(bench)
    assert [(u.star, u.uid) for u in prod] == [(2, 1)], \
        f'已解锁 uid 承继照常: {[(u.star, u.uid) for u in prod]!r}'
