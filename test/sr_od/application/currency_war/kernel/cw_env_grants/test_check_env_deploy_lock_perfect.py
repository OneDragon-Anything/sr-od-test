"""check_env_deploy_lock_perfect 完胜提前检查测试(镜像 src =
kernel/cw_env_grants.py 的该被测函数;同模块兄弟触发函数测试 =
kernel/test_env_grants.py 与本目录按被测方法拆分文件,本文件按拆目录
规范落位)。

测试面依据 = 迭代 T-33 英雄登场设计(.debug/progress/2026-09-23-
invest-effects-calc/designs/T-33-yingxiong-dengchang.md)§2.4 + §4 锁
6/7/8(宁缺勿造半边):
- **判据**(用户裁定 2026-10-18:结算胜利 ∧ 本节点未损失小队生命值):
  环尾行 killed=True(killed 单一语义 = 「挑战成功」胜利标志)∧ 尾行
  hp_after 与前一行持平(相邻两结算帧差分 = 本场损血);killed 非 True
  (败局/读缺)或 hp_after 下降 → 零改写;
- **宁缺勿造**:环不足两行(首战)或任一侧 hp_after None → 不判定;
- **作用域隔离**:只回退 done 内 deploy_lock_uid# 键集的 uid,T-30
  流萤记录(异 uid,不在键集)与已解锁记录(unlock ≤ 生效序位)不动;
  本卡未发放(done 空键集)→ 零改写零效果串;
- **改写原语**:解锁序位沿序列表前驱回退一步(sequence_prev),多次
  完胜累积逐帧递减;效果串 env_deploy_lock_perfect:<名>@<位>-<轮>。

环行经生产单一写端 record_settlement_row 构造(与生产同口,先例 =
strategies/impl/mandate_v1/test_encounter_pick.py)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_encounter_selection import (
    record_settlement_row,
)
from sr_od.application.currency_war.kernel.cw_env_grants import (
    check_env_deploy_lock_perfect,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_performance import (
    RoundOutcome,
)

_SIG = ChannelSig(family='logic_action', actor='CwOpSettleConfirm',
                  mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='T')
_SIG_SEED = ChannelSig(family='logic_action', actor='test-seed',
                       mode='compute')


def _make_gs(*, node_pos: tuple[int, int] = (1, 3),
             locks: tuple = (),
             done: tuple = ()) -> GameState:
    """直构状态容器:生效序位观察锚定(settle_confirm 分支内 = 战斗后继第一
    节点);锁域/done 经 logic 直写播种(测试自造输入)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.node_pos, node_pos, sig=_SIG_OBS)
    if locks:
        gs.write_logic(gs.env_grant_deploy_locks, tuple(locks),
                       produced_by='test-seed', sig=_SIG_SEED)
    if done:
        gs.write_logic(gs.env_grants_done, tuple(done),
                       produced_by='test-seed', sig=_SIG_SEED)
    return gs


def _settle_frame(gs: GameState, plane: int, round_num: int, *,
                  killed: bool | None, hp_after: int | None) -> None:
    """生产同口入一行结算环帧(完胜判定取数源)。"""
    record_settlement_row(
        gs, RoundOutcome(round_num=round_num, plane=plane,
                         node_type='普通战斗', comp_tag='',
                         killed=killed, hp_after=hp_after),
        plane=plane, round_num=round_num, node_type='普通战斗',
        difficulty_node=None, encounter_tier=None)


def test_perfect_win_rewinds_scoped_lock(monkeypatch: pytest.MonkeyPatch
                                         ) -> None:
    """完胜改写正例(T-33 设计 §4 锁 6):尾行 killed=True ∧ hp 持平 →
    作用域内 uid 锁记录回退一步 (1,5)→(1,4)+ 效果串;同窗写单笔全量
    回写(evidence env_deploy_lock_perfect)。"""
    gs = _make_gs(locks=(('某角色', 7, (1, 5)),),
                  done=(('英雄登场', 'deploy_lock_uid#7'),))
    _settle_frame(gs, 1, 1, killed=True, hp_after=80)
    _settle_frame(gs, 1, 2, killed=True, hp_after=80)
    calls: list[tuple] = []
    real = gs.write_logic

    def rec(target, value, *, produced_by, evidence=None, sig, note=''):
        calls.append((gs._field_name(target), evidence))
        real(target, value, produced_by=produced_by, evidence=evidence,
             sig=sig, note=note)

    monkeypatch.setattr(gs, 'write_logic', rec)
    effects = check_env_deploy_lock_perfect(gs, _SIG)
    assert effects == ('env_deploy_lock_perfect:某角色@1-4',), '效果串'
    assert gs.env_grant_deploy_locks.value == (('某角色', 7, (1, 4)),), \
        '解锁序位回退一步'
    assert calls == [('env_grant_deploy_locks',
                      'env_deploy_lock_perfect')], f'单笔全量回写: {calls}'


def test_zero_rewrite_non_win_or_hp_drop(monkeypatch: pytest.MonkeyPatch
                                         ) -> None:
    """零改写两形态(T-33 设计 §4 锁 6 反半边):①尾行 killed 非 True
    (败局 False / 读缺 None);②尾行 hp_after 低于前一行(本帧损血)
    → 均零改写零容器写零效果串。"""
    for label, k1, hp1, k2, hp2 in (
            ('败局', True, 80, False, 80),
            ('读缺', True, 80, None, 80),
            ('本帧损血', True, 80, True, 57),
    ):
        gs = _make_gs(locks=(('某角色', 7, (1, 5)),),
                      done=(('英雄登场', 'deploy_lock_uid#7'),))
        _settle_frame(gs, 1, 2, killed=k1, hp_after=hp1)
        _settle_frame(gs, 1, 3, killed=k2, hp_after=hp2)
        calls: list[tuple] = []
        real = gs.write_logic

        def rec(target, value, *, produced_by, evidence=None, sig, note='',
                _gs=gs, _real=real, _calls=calls):
            _calls.append(_gs._field_name(target))
            _real(target, value, produced_by=produced_by, evidence=evidence,
                  sig=sig, note=note)

        monkeypatch.setattr(gs, 'write_logic', rec)
        effects = check_env_deploy_lock_perfect(gs, _SIG)
        assert effects == (), f'{label} 零效果串'
        assert not calls, f'{label} 零容器写: {calls}'
        assert gs.env_grant_deploy_locks.value == (('某角色', 7, (1, 5)),), \
            f'{label} 锁记录零改'


def test_insufficient_rows_or_none_hp_no_judgment(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """宁缺勿造(T-33 设计 §4 锁 8 检查半边):环仅 1 行(首战)/ 尾行
    hp_after None / 前一行 hp_after None → 零动作(不判定,禁造基准)。"""
    for label, rows in (
            ('仅 1 行', [(True, 80)]),
            ('尾行 hp None', [(True, 80), (True, None)]),
            ('前一行 hp None', [(True, None), (True, 80)]),
    ):
        gs = _make_gs(locks=(('某角色', 7, (1, 5)),),
                      done=(('英雄登场', 'deploy_lock_uid#7'),))
        for i, (k, hp) in enumerate(rows, start=1):
            _settle_frame(gs, 1, i + 1, killed=k, hp_after=hp)
        calls: list[tuple] = []
        real = gs.write_logic

        def rec(target, value, *, produced_by, evidence=None, sig, note='',
                _gs=gs, _real=real, _calls=calls):
            _calls.append(_gs._field_name(target))
            _real(target, value, produced_by=produced_by, evidence=evidence,
                  sig=sig, note=note)

        monkeypatch.setattr(gs, 'write_logic', rec)
        effects = check_env_deploy_lock_perfect(gs, _SIG)
        assert effects == (), f'{label} 零效果串'
        assert not calls, f'{label} 零容器写: {calls}'


def test_scope_isolation_and_unlocked_untouched(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """作用域隔离 + 已解锁不动(T-33 设计 §4 锁 6 隔离半边):同窗三
    记录——作用域 uid(回退)/ T-30 流萤记录(异 uid,不在 done 键集,
    零改)/ 已解锁记录(unlock ≤ 生效序位,零改);完胜仅前一条回退。"""
    gs = _make_gs(
        node_pos=(1, 3),
        locks=(('英雄赠卡', 7, (1, 5)),       # 作用域内:回退
               ('流萤', 99, (1, 6)),          # T-30 异 uid:零改
               ('早解锁', 7, (1, 2))),        # unlock ≤ effective:零改
        done=(('星核猎手契约', 'battle_co_presence'),
              ('英雄登场', 'deploy_lock_uid#7')))
    _settle_frame(gs, 1, 2, killed=True, hp_after=80)
    _settle_frame(gs, 1, 3, killed=True, hp_after=80)
    calls: list[tuple] = []
    real = gs.write_logic

    def rec(target, value, *, produced_by, evidence=None, sig, note=''):
        calls.append(gs._field_name(target))
        real(target, value, produced_by=produced_by, evidence=evidence,
             sig=sig, note=note)

    monkeypatch.setattr(gs, 'write_logic', rec)
    effects = check_env_deploy_lock_perfect(gs, _SIG)
    assert effects == ('env_deploy_lock_perfect:英雄赠卡@1-4',), \
        '仅作用域记录回退'
    assert gs.env_grant_deploy_locks.value == (
        ('英雄赠卡', 7, (1, 4)),
        ('流萤', 99, (1, 6)),
        ('早解锁', 7, (1, 2))), '隔离与已解锁记录逐位不动'
    assert calls == ['env_grant_deploy_locks'], '恰一笔全量回写'


def test_empty_scope_zero_action(monkeypatch: pytest.MonkeyPatch) -> None:
    """作用域空集(T-33 设计 §4 锁 7):本卡未发放(done 无
    deploy_lock_uid# 键)时完胜帧 → 零改写零效果串零容器写。"""
    gs = _make_gs(locks=(('某角色', 7, (1, 5)),),
                  done=(('星核猎手契约', 'battle_co_presence'),))
    _settle_frame(gs, 1, 2, killed=True, hp_after=80)
    _settle_frame(gs, 1, 3, killed=True, hp_after=80)
    calls: list[tuple] = []
    real = gs.write_logic

    def rec(target, value, *, produced_by, evidence=None, sig, note=''):
        calls.append(gs._field_name(target))
        real(target, value, produced_by=produced_by, evidence=evidence,
             sig=sig, note=note)

    monkeypatch.setattr(gs, 'write_logic', rec)
    effects = check_env_deploy_lock_perfect(gs, _SIG)
    assert effects == (), '零效果串'
    assert not calls, f'零容器写: {calls}'


def test_consecutive_perfect_wins_accumulate() -> None:
    """多次完胜累积(T-33 设计 §4 锁 12 递减半边):连续两帧完胜 →
    unlock 逐帧递减两步 (1,5)→(1,4)→(1,3);hp 在上一帧下降本帧持平
    = 完胜(差分基准 = 相邻两结算帧间 hp 差,非全场累计)。"""
    gs = _make_gs(locks=(('某角色', 7, (1, 5)),),
                  done=(('英雄登场', 'deploy_lock_uid#7'),))
    _settle_frame(gs, 1, 2, killed=False, hp_after=57)   # 败局掉血帧
    _settle_frame(gs, 1, 3, killed=True, hp_after=57)    # 本帧未损血 = 完胜
    assert check_env_deploy_lock_perfect(gs, _SIG) == \
        ('env_deploy_lock_perfect:某角色@1-4',)
    assert gs.env_grant_deploy_locks.value == (('某角色', 7, (1, 4)),)
    _settle_frame(gs, 1, 4, killed=True, hp_after=57)    # 再完胜
    assert check_env_deploy_lock_perfect(gs, _SIG) == \
        ('env_deploy_lock_perfect:某角色@1-3',)
    assert gs.env_grant_deploy_locks.value == (('某角色', 7, (1, 3)),), \
        '逐帧累积递减'
