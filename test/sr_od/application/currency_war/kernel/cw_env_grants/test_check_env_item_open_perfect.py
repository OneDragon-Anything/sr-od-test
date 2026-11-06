"""check_env_item_open_perfect 完胜回退检查测试(镜像 src =
kernel/cw_env_grants.py 的该被测函数;同模块兄弟触发函数测试 =
kernel/test_env_grants.py 与本目录按被测方法拆分文件,本文件按拆目录
规范落位)。

测试面依据 = 迭代 T-34 命运礼物设计(.debug/progress/2026-09-23-
invest-effects-calc/designs/T-34-mingyun-liwu.md)§2.5 + §4 锁 8 +
锁 6 跨调用点时序半边:
- **判据**(用户裁定 2026-10-18 口径,check_env_deploy_lock_perfect 同
  判据已登记):环尾行 killed=True ∧ 尾行 hp_after 与前一行持平;killed
  非 True(败局/读缺)或 hp_after 下降 → 零改写;
- **宁缺勿造**:环不足两行(首战)或任一侧 hp_after None → 不判定;
  生效序位缺读(eff None)→ 零改写;
- **作用域**:done 含 (命运礼物, delayed_open_accel) 才回退本表件名
  条目;异卡条目(件名不在作用域)与已到点条目(unlock ≤ 生效序位)
  不动;
- **改写原语**:解锁位沿序列表前驱回退一步(sequence_prev),多次完胜
  累积逐帧递减;效果串 item_open_perfect:<名>@<位>-<轮>;
- **跨调用点时序**(锁 6 集成半边):settle_confirm 完胜回退先于 sim 进
  节点收尾——回退后 unlock ≤ eff 的条目同窗到点正常弹除,零互扰。

环行经生产单一写端 record_settlement_row 构造(与生产同口,先例 =
同目录 test_check_env_deploy_lock_perfect.py)。

追加面 = 偶像经济策略道段(迭代 2026-09-23-invest-effects-calc
designs/REVIEW-T329.md §五④ 锁 4/5/9;写状态副本发放域键域扩展 = 环境 ∪ 策略,
机制按键查表卡名无关,表 +1 条目自动覆盖):策略道完胜回退正例/混族并存
零互扰/两道作用域隔离/跨调用点时序策略道并入。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_encounter_selection import (
    record_settlement_row,
)
from sr_od.application.currency_war.kernel.cw_env_grants import (
    check_env_item_open_perfect,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    discharge_due_item_opens,
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


def _make_gs(*, node_pos: tuple[int, int] | None = (1, 3),
             queue: tuple = (), done: tuple = ()) -> GameState:
    """直构容器:生效序位观察锚定(settle_confirm 分支内 = 战斗后继第一
    节点);队列/done 经 logic 直写播种(测试自造输入)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if node_pos is not None:
        gs.observe(gs.node_pos, node_pos, sig=_SIG_OBS)
    if queue:
        gs.write_logic(gs.pending_item_opens, tuple(queue),
                       produced_by='test-seed', evidence='t:queue',
                       sig=_SIG_SEED)
    if done:
        gs.write_logic(gs.env_grants_done, tuple(done),
                       produced_by='test-seed', evidence='t:done',
                       sig=_SIG_SEED)
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


def test_perfect_win_rewinds_scoped_entries(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """完胜回退正例(T-34 设计 §4 锁 8):尾行 killed=True ∧ hp 持平 →
    作用域条目解锁位回退一步 (1,5)→(1,4)+ 效果串;同窗写单笔全量回写
    (evidence env_item_open_perfect)。"""
    gs = _make_gs(queue=(('惊喜盒', (1, 5)),),
                  done=(('命运礼物', 'delayed_open_accel'),))
    _settle_frame(gs, 1, 2, killed=True, hp_after=80)
    _settle_frame(gs, 1, 3, killed=True, hp_after=80)
    calls: list[str] = []
    real = gs.write_logic

    def rec(target, value, *, produced_by, evidence=None, sig, note='',
            _calls=calls, _gs=gs, _real=real):
        _calls.append(_gs._field_name(target))
        _real(target, value, produced_by=produced_by, evidence=evidence,
              sig=sig, note=note)

    monkeypatch.setattr(gs, 'write_logic', rec)
    effects = check_env_item_open_perfect(gs, _SIG)
    assert effects == ('item_open_perfect:惊喜盒@1-4',), '效果串'
    assert gs.pending_item_opens.value == (('惊喜盒', (1, 4)),), \
        '解锁位回退一步'
    assert calls == ['pending_item_opens'], f'单笔全量回写: {calls}'


def test_zero_rewrite_non_win_hp_drop_or_missing(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """零改写族(T-34 设计 §4 锁 8 反半边):①败局(killed False)/
    读缺(killed None)②本帧损血(hp 下降)③环仅 1 行 ④尾行/前一行
    hp None ⑤生效序位缺读(eff None)→ 均零改写零容器写零效果串。"""
    cases = [
        ('败局', (1, 3), [(True, 80), (False, 80)]),
        ('killed 读缺', (1, 3), [(True, 80), (None, 80)]),
        ('本帧损血', (1, 3), [(True, 80), (True, 57)]),
        ('仅 1 行', (1, 3), [(True, 80)]),
        ('尾行 hp None', (1, 3), [(True, 80), (True, None)]),
        ('前一行 hp None', (1, 3), [(True, None), (True, 80)]),
        ('eff None', None, [(True, 80), (True, 80)]),
    ]
    for label, node_pos, rows in cases:
        gs = _make_gs(node_pos=node_pos,
                      queue=(('惊喜盒', (1, 5)),),
                      done=(('命运礼物', 'delayed_open_accel'),))
        for i, (k, hp) in enumerate(rows, start=2):
            _settle_frame(gs, 1, i, killed=k, hp_after=hp)
        calls: list[str] = []
        real = gs.write_logic

        def rec(target, value, *, produced_by, evidence=None, sig, note='',
                _calls=calls, _gs=gs, _real=real):
            _calls.append(_gs._field_name(target))
            _real(target, value, produced_by=produced_by, evidence=evidence,
                  sig=sig, note=note)

        monkeypatch.setattr(gs, 'write_logic', rec)
        effects = check_env_item_open_perfect(gs, _SIG)
        assert effects == (), f'{label} 零效果串'
        assert not calls, f'{label} 零容器写: {calls}'
        assert gs.pending_item_opens.value == (('惊喜盒', (1, 5)),), \
            f'{label} 队列零改'


def test_scope_isolation_and_due_entries_untouched(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """作用域隔离 + 已到点不动(T-34 设计 §4 锁 8):同窗三条目——作用域
    内(回退)/ 异卡条目(件名不在作用域,零改)/ 已到点(unlock ≤ 生效
    序位,零改);done 无加速键(作用域空集)时完胜帧零动作。"""
    gs = _make_gs(
        node_pos=(1, 3),
        queue=(('惊喜盒', (1, 5)),      # 作用域内:回退
               ('异卡件', (1, 6)),      # 异卡条目:零改
               ('惊喜盒', (1, 2))),     # unlock ≤ eff(已到点):零改
        done=(('命运礼物', 'delayed_open_accel'),))
    _settle_frame(gs, 1, 2, killed=True, hp_after=80)
    _settle_frame(gs, 1, 3, killed=True, hp_after=80)
    effects = check_env_item_open_perfect(gs, _SIG)
    assert effects == ('item_open_perfect:惊喜盒@1-4',), '仅作用域条目回退'
    assert gs.pending_item_opens.value == (
        ('惊喜盒', (1, 4)),
        ('异卡件', (1, 6)),
        ('惊喜盒', (1, 2))), '隔离与已到点条目逐位不动'
    # 作用域空集半边:done 无 delayed_open_accel 键 → 零改写
    gs2 = _make_gs(queue=(('惊喜盒', (1, 5)),),
                   done=(('命运礼物', 'first_streak'),))
    _settle_frame(gs2, 1, 2, killed=True, hp_after=80)
    _settle_frame(gs2, 1, 3, killed=True, hp_after=80)
    assert check_env_item_open_perfect(gs2, _SIG) == (), \
        '作用域空集零改写'
    assert gs2.pending_item_opens.value == (('惊喜盒', (1, 5)),)


def test_consecutive_perfect_wins_accumulate() -> None:
    """多次完胜累积(T-34 设计 §4 锁 8):连续两帧完胜 → 解锁位逐帧
    递减两步 (1,5)→(1,4)→(1,3);hp 在上一帧下降本帧持平 = 完胜(差分
    基准 = 相邻两结算帧间 hp 差,非全场累计)。"""
    gs = _make_gs(queue=(('惊喜盒', (1, 5)),),
                  done=(('命运礼物', 'delayed_open_accel'),))
    _settle_frame(gs, 1, 2, killed=False, hp_after=57)   # 败局掉血帧
    _settle_frame(gs, 1, 3, killed=True, hp_after=57)    # 本帧未损血 = 完胜
    assert check_env_item_open_perfect(gs, _SIG) == \
        ('item_open_perfect:惊喜盒@1-4',)
    assert gs.pending_item_opens.value == (('惊喜盒', (1, 4)),)
    _settle_frame(gs, 1, 4, killed=True, hp_after=57)    # 再完胜
    assert check_env_item_open_perfect(gs, _SIG) == \
        ('item_open_perfect:惊喜盒@1-3',)
    assert gs.pending_item_opens.value == (('惊喜盒', (1, 3)),), \
        '逐帧累积递减'


def test_settle_rollback_then_window_discharge_same_pos() -> None:
    """跨调用点时序(T-34 设计 §4 锁 6 集成半边):settle_confirm 完胜
    回退先于 sim 进节点收尾——回退把解锁位 (1,4) 压到生效序位 (1,3)
    持平后,同窗开盒原语正常命中弹除(回退与开盒零互扰;开盒零席位写
    = 队列弹除零消耗分支)。"""
    gs = _make_gs(node_pos=(1, 3),
                  queue=(('惊喜盒', (1, 4)),),
                  done=(('命运礼物', 'delayed_open_accel'),))
    _settle_frame(gs, 1, 2, killed=True, hp_after=80)
    _settle_frame(gs, 1, 3, killed=True, hp_after=80)
    effects = check_env_item_open_perfect(gs, _SIG)
    assert effects == ('item_open_perfect:惊喜盒@1-3',), '完胜回退一步'
    opened = discharge_due_item_opens(gs, rand=False, sig=_SIG)
    assert opened == ('item_opened:惊喜盒',), '回退后同窗到点正常弹除'
    assert gs.pending_item_opens.value == (), '队列清空,零滞留'
    assert gs.bench.value is None, '零席位写(直构域未观察即零写形态)'


# ============================================================ 策略道段
# (写状态副本发放域键域扩展首例 = 偶像经济火花礼盒;迭代 2026-09-23-invest-
# effects-calc designs/REVIEW-T329.md §五④ 锁 4/5/9。机制面按键查表
# 卡名无关——表 +1 条目自动覆盖,本段锁策略道条目的作用域/混族/时序
# 行为面。)

_IDOL = '偶像经济'


def test_perfect_win_rewinds_strategy_scoped_entry(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """策略道完胜回退正例(REVIEW-T329 §五④ 锁 4):done 含
    (偶像经济, delayed_open_accel) ∧ 完胜帧 → 火花礼盒条目解锁位回退
    一步 + 效果串。"""
    gs = _make_gs(queue=(('火花礼盒', (1, 5)),),
                  done=((_IDOL, 'delayed_open_accel'),))
    _settle_frame(gs, 1, 2, killed=True, hp_after=80)
    _settle_frame(gs, 1, 3, killed=True, hp_after=80)
    effects = check_env_item_open_perfect(gs, _SIG)
    assert effects == ('item_open_perfect:火花礼盒@1-4',), '策略道条目回退'
    assert gs.pending_item_opens.value == (('火花礼盒', (1, 4)),)


def test_mixed_family_entries_independent(monkeypatch: pytest.MonkeyPatch
                                          ) -> None:
    """混族并存 + 多次完胜累积(REVIEW-T329 §五④ 锁 5):惊喜盒@X +
    火花礼盒@Y 两族条目独立回退零互扰(done 含两卡键,同帧各回退一步,
    效果串两行);第二次完胜逐帧累积各再回退一步。"""
    gs = _make_gs(queue=(('惊喜盒', (1, 5)), ('火花礼盒', (1, 7))),
                  done=(('命运礼物', 'delayed_open_accel'),
                        (_IDOL, 'delayed_open_accel')))
    _settle_frame(gs, 1, 2, killed=True, hp_after=80)
    _settle_frame(gs, 1, 3, killed=True, hp_after=80)
    effects = check_env_item_open_perfect(gs, _SIG)
    assert effects == ('item_open_perfect:惊喜盒@1-4',
                       'item_open_perfect:火花礼盒@1-6'), '两族独立回退'
    assert gs.pending_item_opens.value == \
        (('惊喜盒', (1, 4)), ('火花礼盒', (1, 6))), '零互扰'
    _settle_frame(gs, 1, 4, killed=True, hp_after=80)
    check_env_item_open_perfect(gs, _SIG)
    assert gs.pending_item_opens.value == \
        (('惊喜盒', (1, 3)), ('火花礼盒', (1, 5))), '多次完胜累积'


def test_scope_isolation_between_strategy_and_env(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """作用域隔离(REVIEW-T329 §五④ 锁 4,字段名与 done 键查表卡名
    无关——scope = 表条目 ∧ accel ∧ done 键件名集,T-34 锁 8 原式):
    done 不含 (命运礼物, accel) 时惊喜盒条目不动;done 不含 (偶像经济,
    accel) 时火花礼盒条目不动。"""
    # done 只含偶像经济 → 火花礼盒回退、惊喜盒不动
    gs = _make_gs(queue=(('惊喜盒', (1, 5)), ('火花礼盒', (1, 5))),
                  done=((_IDOL, 'delayed_open_accel'),))
    _settle_frame(gs, 1, 2, killed=True, hp_after=80)
    _settle_frame(gs, 1, 3, killed=True, hp_after=80)
    assert check_env_item_open_perfect(gs, _SIG) == \
        ('item_open_perfect:火花礼盒@1-4',), '仅策略道条目回退'
    assert gs.pending_item_opens.value == \
        (('惊喜盒', (1, 5)), ('火花礼盒', (1, 4))), '惊喜盒不动'
    # done 只含命运礼物 → 惊喜盒回退、火花礼盒不动
    gs2 = _make_gs(queue=(('惊喜盒', (1, 5)), ('火花礼盒', (1, 5))),
                   done=(('命运礼物', 'delayed_open_accel'),))
    _settle_frame(gs2, 1, 2, killed=True, hp_after=80)
    _settle_frame(gs2, 1, 3, killed=True, hp_after=80)
    assert check_env_item_open_perfect(gs2, _SIG) == \
        ('item_open_perfect:惊喜盒@1-4',), '仅环境道条目回退'
    assert gs2.pending_item_opens.value == \
        (('惊喜盒', (1, 4)), ('火花礼盒', (1, 5))), '火花礼盒不动'


def test_strategy_entry_rollback_then_window_discharge(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """跨调用点时序策略道并入(REVIEW-T329 §五④ 锁 9):策略道条目回退后
    到点同窗正常弹除(存量命运礼物版同式的策略道回归域)。"""
    gs = _make_gs(node_pos=(1, 3),
                  queue=(('火花礼盒', (1, 4)),),
                  done=((_IDOL, 'delayed_open_accel'),))
    _settle_frame(gs, 1, 2, killed=True, hp_after=80)
    _settle_frame(gs, 1, 3, killed=True, hp_after=80)
    assert check_env_item_open_perfect(gs, _SIG) == \
        ('item_open_perfect:火花礼盒@1-3',), '完胜回退一步'
    opened = discharge_due_item_opens(gs, rand=False, sig=_SIG)
    assert opened == ('item_opened:火花礼盒',), '回退后同窗到点正常弹除'
    assert gs.pending_item_opens.value == (), '队列清空,零滞留'
