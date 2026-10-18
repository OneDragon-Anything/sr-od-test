"""on_env_gained 持续伤害契约分支测试:即时腿回归 + 锚键腿(镜像 src =
kernel/cw_gain_chain.py 的该被测函数,按拆目录规范落位;同函数兄弟测试 =
kernel/test_gain_chain.py ENV_GIFTS 分道段〔超限只读复用〕)。

测试面依据 = T-28 设计稿(迭代 2026-09-23-invest-effects-calc,
designs/T-28-chixu-shanghai-qiyue.md)§2.1/§2.4 + §4.3:
- **即时腿回归**:获得环境当刻 gain_character 发椒丘+卡芙卡(desc 无
  数量/星级词,单数缺省 1★ 先验族)——本批零改动,回归锁;
- **锚键腿**:'dot_anchor#<位面>-<轮>' 纯登记件非门控,获得刻与即时腿
  同窗相邻 write_logic 直写(同 evidence 同 sig);节点未知不写且须显式
  判 node——``_node_frame`` 未观察返回空串,照抄会产出 'dot_anchor#-'
  畸形键;开局三选一获取时 sim 节点未进窗 → 缺锚 = 预期形态。

追加面 = T-33 英雄登场设计(.debug/progress/2026-09-23-invest-effects-
calc/designs/T-33-yingxiong-dengchang.md)§2.3 + §4 锁 2/3/4/9/11:
随机赠卡锁腿(采样发卡 + 发号 + 锁域写 + 完胜作用域键 done,四笔同窗)
/ 未锚定窗防御基准 / rng 链确定性 / 溢出解耦 / 表外环境安静。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war.kernel.cw_env_grants import (
    DOT_CONTRACT_ENV,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    GAIN_CHAIN_PRODUCER,
    on_env_gained,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    NodeKey,
    Unit,
)

_ENV = DOT_CONTRACT_ENV
_SIG = ChannelSig(family='logic_action', actor='CwGainChain', mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_EVIDENCE = f'on_env_gained:{_ENV}'


def _make_gs(*, node: bool = False) -> GameState:
    """直构容器(bench = 开局种子底座 9 空槽);``node`` = 节点窗已开。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench, BenchView(slots=[BenchSlot(kind='empty')] * 9,
                                   capacity=9), sig=_SIG_OBS)
    if node:
        gs.observe(gs.node, NodeKey(plane=1, round_num=3, kind='battle'),
                   sig=_SIG_OBS)
    return gs


def _bench_units(gs: GameState) -> list[tuple[str, int]]:
    return [(s.unit.char_id, s.unit.star) for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]


def _record_writes(gs: GameState,
                   monkeypatch) -> list[tuple]:
    """包装 write_logic_rand/write_logic 记录 (字段名, evidence, 通道,
    sig, produced_by) 写行(先例 = kernel/test_gain_chain.py 同族 helper)。"""
    calls: list[tuple[str, str | None, str, ChannelSig, str]] = []

    def _wrap(real, channel: str):
        def rec(target, value, *, produced_by, evidence=None, sig, note=''):
            calls.append((gs._field_name(target), evidence, channel, sig,
                          produced_by))
            real(target, value, produced_by=produced_by, evidence=evidence,
                 sig=sig, note=note)
        return rec

    monkeypatch.setattr(gs, 'write_logic_rand',
                        _wrap(gs.write_logic_rand, 'rand'))
    monkeypatch.setattr(gs, 'write_logic', _wrap(gs.write_logic, 'logic'))
    return calls


def test_immediate_leg_and_anchor_same_window(
        monkeypatch) -> None:
    """即时腿 + 锚键腿同窗(设计稿 §2.4/§2.1):节点窗已开时获得环境 →
    bench 增椒丘+卡芙卡(1★ 确定发放,即时腿零改动回归)+ done 追加锚键
    'dot_anchor#1-3'(纯登记非门控,与即时腿同 evidence 同 sig 相邻,
    write_logic 直写登记事实)。"""
    gs = _make_gs(node=True)
    calls = _record_writes(gs, monkeypatch)
    effects = on_env_gained(gs, None, _ENV, rand=False, sig=_SIG)
    assert effects == ('env_gift:椒丘', 'env_gift:卡芙卡'), '即时腿效果串'
    assert _bench_units(gs) == [('椒丘', 1), ('卡芙卡', 1)], '两名 1★ 入席'
    assert gs.env_grants_done.value == ((_ENV, 'dot_anchor#1-3'),), \
        '锚键纯登记(帧 = 位面-轮)'
    done_rows = [(c[0], c[1], c[2], c[4]) for c in calls
                 if c[0] == 'env_grants_done']
    assert done_rows == [('env_grants_done', _EVIDENCE, 'logic',
                          GAIN_CHAIN_PRODUCER)], f'锚键单笔直写: {done_rows}'
    assert calls[-1][3] == _SIG, '锚键与即时腿同 sig(同窗相邻)'


def test_anchor_skipped_when_node_not_in_window(monkeypatch) -> None:
    """节点未知不写(设计稿 §2.1 显式判 node + §4.1⑥ 缺锚形态):开局
    三选一获取时 sim 节点尚未进窗(node None)→ 即时腿照常、零锚键零
    畸形键(缺锚不影响猜测写/计数/证实,check_env_dot_grants 门控 =
    active_env)。"""
    gs = _make_gs(node=False)
    calls = _record_writes(gs, monkeypatch)
    effects = on_env_gained(gs, None, _ENV, rand=False, sig=_SIG)
    assert effects == ('env_gift:椒丘', 'env_gift:卡芙卡'), '即时腿照常'
    assert not gs.env_grants_done.value, '零锚键(开局形态预期)'
    assert all('dot_anchor' not in (c[1] or '') for c in calls), \
        '无畸形键痕迹(禁 dot_anchor#- 形态)'


def test_skill_point_contract_immediate_leg_regression(monkeypatch) -> None:
    """战技点契约即时腿回归(T-29 设计 §1/§4 锁 8):获得环境当刻
    chars_immediate 逐名确定发放(1★,desc 无数量/星级词单数缺省)→
    bench 增丹恒·饮月+花火各 1——现役通道逐位不变,锁不被晶矿开启
    条件腿批次扰动;获得刻零晶矿触发 done(条件腿归
    check_env_ore_open_grants,打开晶矿计数达标才发,获得刻零预登记)。"""
    gs = _make_gs()
    calls = _record_writes(gs, monkeypatch)
    effects = on_env_gained(gs, None, '战技点契约', rand=False, sig=_SIG)
    assert effects == ('env_gift:丹恒·饮月', 'env_gift:花火'), '即时腿效果串'
    assert _bench_units(gs) == [('丹恒·饮月', 1), ('花火', 1)], \
        '两名 1★ 入席(确定发放)'
    assert gs.env_grants_done.value is None, '获得刻零晶矿触发 done'
    assert all('ore_open' not in (c[1] or '') for c in calls), \
        '零 ore_open 写行痕迹(条件腿不随获得刻触发)'


def test_stellar_hunter_contract_immediate_leg_regression() -> None:
    """星核猎手契约即时腿回归(T-30 设计 §4 锁 8):获得环境当刻
    chars_immediate 确定发放(卡芙卡 1★,desc 无数量/星级词单数缺省)
    → bench 增卡芙卡 1——现役通道逐位不变;其 **uid 恒 None**(即时腿
    不传 uid 形参,实例号仅条件腿发放刻赋号)。"""
    gs = _make_gs()
    effects = on_env_gained(gs, None, '星核猎手契约', rand=False, sig=_SIG)
    assert effects == ('env_gift:卡芙卡',), '即时腿效果串'
    placed = [s.unit for s in gs.bench.value.slots
              if s is not None and s.kind == 'unit' and s.unit is not None]
    assert [(u.char_id, u.star, u.uid) for u in placed] == \
        [('卡芙卡', 1, None)], '1★ 入席且无实例号(锁域零记录)'
    assert not gs.env_grant_deploy_locks.value, '即时腿零锁记录'
    assert not gs.env_grant_uid_seq.value, '即时腿零发号'


# ============================================================ 随机赠卡锁腿
# (环境「随机赠卡+上场锁」登记表发放腿;迭代 2026-09-23-invest-effects-
# calc T-33 英雄登场设计 §2.3 + §4 锁 2/3/4/9/11。解锁位数学:获得刻生效
# 序位 (1,1) 沿默认表步进 19 步 = (3,4)(序 20)。)

_DEPLOY_ENV = '英雄登场'


def _make_gs_node_pos(node_pos: tuple[int, int] | None) -> GameState:
    """直构容器(bench 9 空槽);``node_pos`` 非 None = 观察锚定生效序位
    (check_env_battle_grants 测试同款直测注入)。"""
    gs = _make_gs()
    if node_pos is not None:
        gs.observe(gs.node_pos, node_pos, sig=_SIG_OBS)
    return gs


def test_deploy_lock_grant_leg_seeded_roll_full_writes(
        monkeypatch) -> None:
    """赠卡锁腿四笔同窗写(T-33 设计 §4 锁 2):固定种子 → bench 追加
    1 张 2★ 且名 ∈ 5 费规格池、uid 非空(发号 0→1);锁记录 =
    ((名, uid, (3,4)),)(默认表,(1,1) 步进 19);done 含
    deploy_lock_uid#<uid>;效果串两行(env_gift_random:/env_deploy_lock:
    前缀);期望名从同 seed 现算(单一来源,不手抄)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        ENV_DEPLOY_LOCK_GRANTS,
        random_char_pool,
    )
    spec = ENV_DEPLOY_LOCK_GRANTS[_DEPLOY_ENV].spec
    pool = random_char_pool(spec)
    expected = random.Random(20261018).choice(pool)
    gs = _make_gs_node_pos((1, 1))
    calls = _record_writes(gs, monkeypatch)
    effects = on_env_gained(gs, None, _DEPLOY_ENV, rand=False, sig=_SIG,
                            rng=random.Random(20261018))
    assert effects == (f'env_gift_random:{expected}@2star',
                       f'env_deploy_lock:{expected}#uid1@3-4'), '效果串两行'
    placed = [(s.unit.char_id, s.unit.star, s.unit.uid)
              for s in gs.bench.value.slots
              if s is not None and s.kind == 'unit' and s.unit is not None]
    assert placed == [(expected, 2, 1)], '2★ 入席且实例号随行(发号 0→1)'
    assert gs.env_grant_uid_seq.value == 1, '发号计数器落账'
    assert gs.env_grant_deploy_locks.value == \
        ((expected, 1, (3, 4)),), '锁记录 = (名, uid, (1,1)+19 步)'
    assert gs.env_grants_done.value == \
        ((_DEPLOY_ENV, 'deploy_lock_uid#1'),), '完胜作用域键落 done'
    # 四笔相邻写序:发号 → bench 链 → 锁域 → done(同 sig 同 producer)
    assert [c[0] for c in calls] == [
        'env_grant_uid_seq', 'bench', 'env_grant_deploy_locks',
        'env_grants_done'], f'四笔相邻写: {calls}'
    assert calls[0][1] == f'on_env_gained:{_DEPLOY_ENV}#uid', '发号笔 evidence'
    assert calls[2][1] == f'env_deploy_lock:{_DEPLOY_ENV}', '锁域 evidence'
    assert calls[3][1] == (f'env_deploy_lock:{_DEPLOY_ENV}'
                           f'#accel_scope'), '作用域键 evidence'
    assert all(c[3] == _SIG for c in calls), '同 sig(同窗相邻)'
    assert all(c[4] == GAIN_CHAIN_PRODUCER for c in calls), '同 produced_by'


def test_deploy_lock_grant_leg_unanchored_window_default_base() -> None:
    """未锚定窗防御(T-33 设计 §4 锁 3):生效序位 None(开局段结构性,
    环境选择先于节点锚定)→ 解锁序位仍 (3,4)(防御基准 (1,1) 步进
    19);赠卡与发号照常。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        ENV_DEPLOY_LOCK_GRANTS,
        random_char_pool,
    )
    pool = random_char_pool(ENV_DEPLOY_LOCK_GRANTS[_DEPLOY_ENV].spec)
    expected = random.Random(3).choice(pool)
    gs = _make_gs_node_pos(None)
    effects = on_env_gained(gs, None, _DEPLOY_ENV, rand=False, sig=_SIG,
                            rng=random.Random(3))
    assert effects == (f'env_gift_random:{expected}@2star',
                       f'env_deploy_lock:{expected}#uid1@3-4'), \
        '未锚定窗解锁位 = (1,1) 基准 + 19 步'
    assert gs.env_grant_deploy_locks.value == ((expected, 1, (3, 4)),)


def test_deploy_lock_grant_leg_rng_explicit_and_replay() -> None:
    """rng 链(T-33 设计 §4 锁 4,继承 T-10 支语义):同 seed 重放同名
    确定(全链掷骰单一来源);显式传入优先(两次不同显式 rng = 各自
    现算期望名,互不一致即证非共享全局源)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        ENV_DEPLOY_LOCK_GRANTS,
        random_char_pool,
    )
    pool = random_char_pool(
        ENV_DEPLOY_LOCK_GRANTS[_DEPLOY_ENV].spec)

    def _pick(seed: int) -> tuple[str, tuple]:
        gs = _make_gs_node_pos((1, 1))
        effects = on_env_gained(gs, None, _DEPLOY_ENV, rand=False,
                                sig=_SIG, rng=random.Random(seed))
        return effects[0].split(':')[1].split('@')[0], \
            gs.env_grant_deploy_locks.value

    n1, locks1 = _pick(11)
    n2, locks2 = _pick(11)
    assert n1 == n2 and locks1 == locks2, '同 seed 重放确定'
    assert n1 in pool, '掷骰名 ∈ 规格池'
    n3, _ = _pick(12)
    expected12 = random.Random(12).choice(pool)
    assert n3 == expected12, '显式 rng 优先(期望名从同 seed 现算)'


def test_deploy_lock_grant_leg_overflow_decoupled(monkeypatch) -> None:
    """溢出解耦(T-33 设计 §4 锁 9):bench 满 + 溢出位被占 →
    gain_character 零写留证(bench/overflow 零新写),锁记录 + done 照写
    (发放事实成立、placed=False 留证,check_env_battle_grants 同口径)。"""
    gs = _make_gs_node_pos((1, 1))
    units = [f'剧本单位{i}' for i in range(9)]
    gs.observe(gs.bench, BenchView(
        slots=[BenchSlot(kind='unit', unit=Unit(char_id=n, star=1))
               for n in units], capacity=9), sig=_SIG_OBS)
    gs.write_logic(gs.overflow_warning, True, produced_by='seed',
                   evidence='t:ovf', sig=_SIG)
    gs.write_logic(gs.overflow_card, '占位道具', produced_by='seed',
                   evidence='t:ovf', sig=_SIG)
    calls = _record_writes(gs, monkeypatch)
    effects = on_env_gained(gs, None, _DEPLOY_ENV, rand=False, sig=_SIG,
                            rng=random.Random(5))
    assert len(effects) == 2, '效果串照常两行(发放事实登记)'
    assert effects[0].startswith('env_gift_random:')
    assert [c[0] for c in calls] == [
        'env_grant_uid_seq', 'env_grant_deploy_locks', 'env_grants_done'], \
        f'bench 拒落下零 bench 写,发号/锁域/done 照写: {calls}'
    assert gs.env_grant_deploy_locks.value[0][2] == (3, 4), '锁记录照写'
    assert gs.env_grants_done.value == ((_DEPLOY_ENV,
                                         'deploy_lock_uid#1'),), 'done 照写'
    kept = [s.unit.char_id for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]
    assert kept == units, 'bench 零写(溢出位被占拒落)'


def test_non_registered_env_stays_quiet(monkeypatch) -> None:
    """表外环境安静不写(T-33 设计 §4 锁 11;早退出口改形回归半边):
    INVESTMENT_ENVS 在册但零登记表命中(轮岗)→ 效果串恒空逐位不变
    (() 形态)、零容器写——赠卡锁腿为表外环境零写径。"""
    gs = _make_gs_node_pos((1, 1))
    calls = _record_writes(gs, monkeypatch)
    seq_before = gs.write_seq
    effects = on_env_gained(gs, None, '轮岗', rand=False, sig=_SIG)
    assert effects == (), '表外环境效果串恒空(() 逐位不变)'
    assert not calls, f'零容器写: {calls}'
    assert gs.write_seq == seq_before, '安静不写'
