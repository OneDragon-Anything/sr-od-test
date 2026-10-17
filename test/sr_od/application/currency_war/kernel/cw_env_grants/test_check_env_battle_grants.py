"""check_env_battle_grants 同战共现条件发放测试(镜像 src =
kernel/cw_env_grants.py 的该被测函数;同模块兄弟触发函数测试 =
kernel/test_env_grants.py〔超限只读复用〕与本目录按被测方法拆分文件,
本文件按拆目录规范落位)。

测试面依据 = 迭代 T-30 星核猎手契约设计(v2.1 定稿,
.designs/T-30-xinghe-lieshou-qiyue.md,迭代目录
.debug/progress/2026-09-23-invest-effects-calc)§2.3 + §4:
- **条件矩阵**(八序短路):env 空链/不在册/已 done(一次性封账)/
  deployed 缺读/bench 缺读(均缓发不标 done,宁缺勿造)/生效序位缺读/
  共现不齐 → 零写;
- **四笔写契约**:发号(uid)+ 角色链(gain_character rand=False,1★
  先验,uid 随行)+ 锁域追加 + done battle_co_presence 键,evidence
  **前缀共享** `env_grant#<env>#battle`(发号笔 = 前缀+`#uid`,链内
  展开行 = 前缀+`#place`/`#mergeN`——禁按全等断言),同 sig 同
  produced_by 相邻;
- **组语义**:AND-of-ORs——组内任一名在场即该组满足,组间全满足才
  发放;参与 = 上阵(deployed 现读),bench 不算;
- **解锁序位**:发放刻生效序位沿节点日程表步进 K=2 步(X+1 → X+3,
  锁 X+1..X+K 两个备战期);跨位面滚动;P3 末步进遇 None 停留;
- **快照存续**:锁域/发号计数器/done 随快照往返无损(锁域 tuple 化
  rebuild 登记),恢复局重查零写,续发号从存续值续号不撞号。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_env_grants import (
    BATTLE_CO_PRESENCE_KEY,
    check_env_battle_grants,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
    restore_state_snapshot,
)

_ENV = '星核猎手契约'
_REWARD = '流萤'
_PREFIX = f'env_grant#{_ENV}#battle'

_SIG_HOOK = ChannelSig(family='logic_hook', actor='CwScreenBattleWait',
                       group_id='battle-wait:env-grant')
_SIG_SIM = ChannelSig(family='logic_action', actor='SimBackend',
                      mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_SIG_SEED = ChannelSig(family='logic_action', actor='test-seed',
                       mode='compute')

_PRODUCER = 'env_conditional_grant'


def _make_gs(*, env: str | None = _ENV,
             deployed: list[str] | None = None,
             bench: list[tuple[str, int]] | None = None,
             bench_units: list[Unit] | None = None,
             node_pos: tuple[int, int] | None = (1, 7),
             done: tuple[tuple[str, str], ...] | None = None,
             ) -> GameState:
    """观察面按参组装(None = 保持未写形态;done/发号计数器经 logic
    直写播种)。``deployed`` = 上阵角色名简写(1★);``bench_units`` 优先
    于 ``bench``(可携带 uid 的完整单位)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if env is not None:
        gs.observe(gs.active_env, env, sig=_SIG_OBS)
    if deployed is not None:
        front = [Unit(char_id=c, star=1) for c in deployed]
        front += [None] * (4 - len(front))
        gs.observe(gs.deployed,
                   DeployedView(front_slots=front, back_slots=[None] * 6),
                   sig=_SIG_OBS)
    if bench is not None or bench_units is not None:
        units = (bench_units if bench_units is not None
                 else [Unit(char_id=c, star=s) for c, s in bench])
        slots: list[BenchSlot | None] = [BenchSlot(kind='empty')] * 9
        for i, u in enumerate(units):
            slots[i] = BenchSlot(kind='unit', unit=u)
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9),
                   sig=_SIG_OBS)
    if node_pos is not None:
        # 生效序位观察锚定(发放刻基准;settle_confirm 分支内 = 战斗
        # 后继第一节点,直测以观察态等价注入)
        gs.observe(gs.node_pos, node_pos, sig=_SIG_OBS)
    if done is not None:
        gs.write_logic(gs.env_grants_done, tuple(done),
                       produced_by='test-seed', sig=_SIG_SEED)
    return gs


def _record_writes(gs: GameState,
                   monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic_rand/write_logic 记录 (字段名, evidence, 通道,
    sig, produced_by) 写行(先例 = test_check_env_interest_grants 同名
    helper)。"""
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


def _bench_units(gs: GameState) -> list[Unit]:
    return [s.unit for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]


_TRIO = ['刃', '卡芙卡', '银狼']


# ============================================================ 条件矩阵


def test_condition_matrix_short_circuits(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """未发放分支逐序零写(设计 §2.3 条件矩阵 1-3):env 空链/不在册/
    已 done → 返回 None 且容器零写行。"""
    for label, gs in (
            ('env 空链', _make_gs(env=None, deployed=_TRIO, bench=[])),
            ('不在册', _make_gs(env='轮岗', deployed=_TRIO, bench=[])),
            ('已 done', _make_gs(deployed=_TRIO, bench=[],
                                 done=((_ENV, BATTLE_CO_PRESENCE_KEY),))),
    ):
        calls = _record_writes(gs, monkeypatch)
        assert check_env_battle_grants(gs, _SIG_HOOK) is None
        assert not calls, f'{label} 零写: {calls}'


def test_carrier_unobserved_defer_without_done(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """deployed/bench 缺读(设计 §2.3 条件 4-5,直构域防御)→ None 且
    **不标 done**(宁缺勿造:done 只在发放同窗登记;结算刻真值到位后
    自动重查)。"""
    for label, gs in (
            ('deployed None', _make_gs(deployed=None, bench=[])),
            ('bench None', _make_gs(deployed=_TRIO, bench=None)),
    ):
        calls = _record_writes(gs, monkeypatch)
        assert check_env_battle_grants(gs, _SIG_HOOK) is None
        assert not calls, f'{label} 零写: {calls}'
        assert gs.env_grants_done.value is None, f'{label} 不标 done'


def test_effective_missing_defer_without_done(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """生效序位缺读(设计 §2.3 条件 6,解锁序位无计算基准)→ None 且
    不标 done(settle_confirm 分支内结构性不可达,直构/测试形态防御)。"""
    gs = _make_gs(deployed=_TRIO, bench=[], node_pos=None)
    calls = _record_writes(gs, monkeypatch)
    assert check_env_battle_grants(gs, _SIG_HOOK) is None
    assert not calls, f'零写: {calls}'
    assert gs.env_grants_done.value is None, '不标 done'


# ============================================================ 组语义


def test_group_semantics_and_or_slots(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """AND-of-ORs 组语义(设计 §4 锁 3):槽内任一名在场即该组满足——
    槽 A 由 刃 **或** 千冶·刃 满足、槽 C 由 银狼 **或** 银狼LV.999 满足,
    三组齐即发放(OR 槽成员互换不改变判定);卡芙卡在 bench 不在
    deployed = 不触发(参与 = 上阵,bench 不算),缺任一组亦不触发。"""
    # 正例:三组齐,OR 槽成员互换均发放
    for label, deployed in (
            ('槽A=刃', ['刃', '卡芙卡', '银狼']),
            ('槽A=千冶·刃', ['千冶·刃', '卡芙卡', '银狼']),
            ('槽C=银狼LV.999', ['刃', '卡芙卡', '银狼LV.999']),
    ):
        gs = _make_gs(deployed=deployed, bench=[])
        calls = _record_writes(gs, monkeypatch)
        assert check_env_battle_grants(gs, _SIG_HOOK) == _REWARD, label
        assert calls, f'{label} 发放有写行'
    # 反例:卡芙卡在 bench 不在 deployed;缺槽 C
    for label, deployed, bench in (
            ('卡芙卡不上阵', ['刃', '银狼'], [('卡芙卡', 1)]),
            ('缺槽C', ['刃', '卡芙卡'], []),
    ):
        gs = _make_gs(deployed=deployed, bench=bench)
        calls = _record_writes(gs, monkeypatch)
        assert check_env_battle_grants(gs, _SIG_HOOK) is None
        assert not calls, f'{label} 零写: {calls}'


# ============================================================ 达标发放


def test_grant_four_adjacent_writes_prefix_evidence(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """达标发放(设计 §2.3 条 8 / §4 锁 2):bench 增 1 个 1★ 流萤**带
    唯一 uid**(发号 0→1)+ 锁域追加 ('流萤', 1, (1,9)) + done 追加
    ('星核猎手契约','battle_co_presence');四笔同 sig 同 produced_by,
    evidence **前缀共享** = `env_grant#星核猎手契约#battle`(发号笔
    +`#uid`、bench 链写 +`#place`,禁按全等断言)。"""
    gs = _make_gs(deployed=_TRIO, bench=[], node_pos=(1, 7))
    calls = _record_writes(gs, monkeypatch)
    granted = check_env_battle_grants(gs, _SIG_HOOK)
    assert granted == _REWARD, '返回发放角色名(日志面消费)'
    units = _bench_units(gs)
    assert [(u.char_id, u.star) for u in units] == [(_REWARD, 1)], \
        '1★ 先验入席'
    assert units[0].uid == 1, '实例号随行(发号器 0→1)'
    assert gs.env_grant_uid_seq.value == 1, '发号计数器落账'
    assert gs.env_grant_deploy_locks.value == ((_REWARD, 1, (1, 9)),), \
        '锁记录 = (发放角色, uid, 解锁序位 X+K+1)'
    assert gs.env_grants_done.value == ((_ENV, BATTLE_CO_PRESENCE_KEY),)
    # 四笔相邻写契约(evidence 前缀共享;写字段序 = 发号→bench 链→
    # 锁域→done;链内落位/合并展开行按链纪律带后缀)
    assert [c[0] for c in calls] == [
        'env_grant_uid_seq', 'bench', 'env_grant_deploy_locks',
        'env_grants_done'], f'四笔相邻写: {calls}'
    for c in calls:
        assert c[1] is not None and c[1].startswith(_PREFIX), \
            f'evidence 前缀共享: {c}'
    assert calls[0][1] == _PREFIX + '#uid', '发号笔 = 前缀+#uid'
    assert calls[1][1].startswith(_PREFIX + '#'), \
        'bench 链写 = 前缀+链纪律后缀(#place/#mergeN)'
    assert calls[2][1] == _PREFIX, '锁域 = 前缀'
    assert calls[3][1] == _PREFIX, 'done = 前缀'
    assert all(c[3] == _SIG_HOOK for c in calls), '同 sig'
    assert all(c[4] == _PRODUCER for c in calls), '同 produced_by'


def test_once_only_no_regrant(monkeypatch: pytest.MonkeyPatch) -> None:
    """一次性语义(设计 §5-5 done 封账):发放后再次共现(阵容不变自然
    满足)重查 = done 短路零写,发号器不再前进(「获得【流萤】」直读
    一次性)。"""
    gs = _make_gs(deployed=_TRIO, bench=[], node_pos=(1, 7))
    assert check_env_battle_grants(gs, _SIG_HOOK) == _REWARD
    calls = _record_writes(gs, monkeypatch)
    assert check_env_battle_grants(gs, _SIG_SIM) is None
    assert not calls, f'再查零写: {calls}'
    assert gs.env_grant_uid_seq.value == 1, 'uid 不再发号'


# ============================================================ 解锁序位


@pytest.mark.parametrize(('eff', 'expected_unlock'), [
    ((1, 7), (1, 9)),    # 战斗 (1,6) 后继 → 步进 2 步 = X+K+1
    ((1, 9), (2, 2)),    # 跨位面:步进经 (2,1) 滚动
    ((3, 7), (3, 7)),    # P3 末:首步即 None → 停留最后合法值
])
def test_unlock_node_pos_stepping(
        monkeypatch: pytest.MonkeyPatch, eff: tuple[int, int],
        expected_unlock: tuple[int, int]) -> None:
    """解锁序位 = 发放刻生效序位沿节点日程表步进 K=2 步(设计 §4 锁 6,
    V2-2 修后口径钉死):字典序跨位面滚动;局终方向无后继停留——锁已无
    消费面。"""
    gs = _make_gs(deployed=_TRIO, bench=[], node_pos=eff)
    assert check_env_battle_grants(gs, _SIG_HOOK) == _REWARD
    assert gs.env_grant_deploy_locks.value == ((_REWARD, 1, expected_unlock),)


def test_unlock_stepping_follows_lock_k(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """步进数随登记表 K(设计 §4 锁 6 收尾句:K 改 1 时锁面随裁决表
    同步)——注入 K=1 条目,unlock = 生效序位 + 1 步。"""
    from sr_od.application.currency_war.kernel import cw_env_grants as eg
    from sr_od.application.currency_war.kernel.cw_investments import (
        ENV_BATTLE_GRANTS,
        EnvBattleGrant,
    )
    orig = dict(ENV_BATTLE_GRANTS)
    monkeypatch.setattr(eg, 'ENV_BATTLE_GRANTS', {
        _ENV: EnvBattleGrant(
            presence_groups=(tuple(orig[_ENV].presence_groups)),
            reward_char=_REWARD, deploy_lock_nodes=1),
    })
    gs = _make_gs(deployed=_TRIO, bench=[], node_pos=(1, 7))
    assert check_env_battle_grants(gs, _SIG_HOOK) == _REWARD
    assert gs.env_grant_deploy_locks.value == ((_REWARD, 1, (1, 8)),)


# ============================================================ 快照存续


def test_snapshot_roundtrip_locks_and_seq_persist(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """快照存续(设计 §4 锁 7):发放完成态快照 → restore 往返,锁域
    (tuple 化 rebuild)/发号计数器/done 逐位相等;deployed 内带 uid 单位
    经 _unit_from_dict 宽容读恢复 uid;恢复局重查零写(done 随快照)。
    无快照接管形态的重发放续号(收尾句:发号从存续值续号不撞号)由
    done 清空形态验证 uid=2 ≠ 恢复锁记录 uid=1。"""
    gs = _make_gs(deployed=_TRIO, bench=[], node_pos=(1, 7))
    assert check_env_battle_grants(gs, _SIG_HOOK) == _REWARD
    # 接管局形态:恢复局常见部署变化 → 把流萤摆上阵(观察覆盖,uid 随行)
    gs.observe(gs.deployed, DeployedView(
        front_slots=[Unit(char_id=_REWARD, star=1, uid=1), None, None, None],
        back_slots=[None] * 6), sig=_SIG_OBS)
    snap = gs.full_state_snapshot()

    restored = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(restored, snap)
    assert restored.env_grant_deploy_locks.value == \
        ((_REWARD, 1, (1, 9)),), '锁域 tuple 化重建'
    assert restored.env_grant_uid_seq.value == 1, '发号计数器随快照存续'
    assert restored.env_grants_done.value == \
        ((_ENV, BATTLE_CO_PRESENCE_KEY),), 'done 随快照存续'
    dep_units = [u for u in restored.deployed.value.front_slots
                 if u is not None]
    assert dep_units[0].uid == 1, 'Unit.uid 经 _unit_from_dict 宽容读恢复'
    calls = _record_writes(restored, monkeypatch)
    restored.observe(restored.active_env, _ENV, sig=_SIG_OBS)
    restored.observe(restored.bench,
                     BenchView(slots=[BenchSlot(kind='empty')] * 9,
                               capacity=9), sig=_SIG_OBS)
    restored.observe(restored.deployed,
                     DeployedView(front_slots=[
                         Unit(char_id=c, star=1) for c in _TRIO]
                         + [None], back_slots=[None] * 6), sig=_SIG_OBS)
    assert check_env_battle_grants(restored, _SIG_HOOK) is None
    assert not calls, f'恢复局 done 在册零写: {calls}'
    # 无快照接管形态(done 空)重发放:发号从存续值续号,不与恢复的
    # 锁记录 uid=1 撞号
    restored.write_logic(restored.env_grants_done, (),
                         produced_by='test-seed', sig=_SIG_SEED)
    calls = _record_writes(restored, monkeypatch)
    assert check_env_battle_grants(restored, _SIG_HOOK) == _REWARD
    new_units = [s.unit for s in restored.bench.value.slots
                 if s is not None and s.kind == 'unit' and s.unit is not None]
    assert new_units[0].uid == 2, '续发号 = 存续值+1,不撞号'
    assert restored.env_grant_deploy_locks.value == (
        (_REWARD, 1, (1, 9)), (_REWARD, 2, (1, 9))), '锁记录追加不覆盖'
