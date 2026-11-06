"""check_strategy_perfect_rescue 完胜判定改写检查测试(镜像 src =
kernel/cw_env_grants.py 的该被测函数;同模块完胜判据族测试 =
本目录 test_check_env_deploy_lock_perfect.py 等,本文件按拆目录规范
落位)。

测试面依据 = 迭代设计 designs/T-412-doushi-zhejiade-cuo.md §2.2 三件套
+ §4 锁 3-6:
- **判据真值表**(读法 A = 救援仅覆盖「胜利∧损血」):胜∧损血∧徽携带∧
  配额>0 → 救援(瞬时位 True + 配额一次性标志位 +1 + sim 出售腿);胜∧无损血 →
  零救援;败局 → 零救援;环 <2 行 → 不判定;配额 0 → 零救援不扣;
  徽不在 deployed → 零救援不扣。**用例系纯注入形态声明**:「胜∧损血∧
  徽携带」在现码状态副本不可自然发生——sim 双重休眠(部署单位 unit.equips
  恒空 + sim 结算帧胜利不掉血)+ live 无 sim 写,注入形性质防误当
  自然路径回归;
- **env consult**(锁 4):救援置位后 check_env_deploy_lock_perfect 判据
  放宽触发(损血局锁回退发生);未置位(None)行为与现状逐字节等价
  (零回归,存量判据测试全绿即证,本文件补置位/None 两态对照);
- **出售腿**(锁 5,sim 形态直测):槽置 None 定长保持 + 退款 =
  ``sell_refund(star, bench_char_cost(u, gs))`` 口径 + 装备回收第三笔;
  live 形态零写断言(sim 门关 → deployed/gold/equips 零写);
- **零 rng**(锁 6):救援全确定,同输入两次执行状态逐位相同。

环行经生产单一写端 record_settlement_row 构造(与生产同口,先例 =
本目录 test_check_env_deploy_lock_perfect.py)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_economy import (
    bench_char_cost,
    sell_refund,
)
from sr_od.application.currency_war.kernel.cw_encounter_selection import (
    record_settlement_row,
)
from sr_od.application.currency_war.kernel.cw_env_grants import (
    check_env_deploy_lock_perfect,
    check_strategy_perfect_rescue,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_performance import (
    RoundOutcome,
)
from sr_od.application.currency_war.sim import cw_sim_ports

_CARD = '都是这家伙的错！'
_EM = '命运圣杯星徽'
_LATCH_1 = f'perfect_rescue#{_CARD}#1'

_SIG = ChannelSig(family='logic_action', actor='CwOpSettleConfirm',
                  mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='T')
_SIG_SEED = ChannelSig(family='logic_action', actor='test-seed',
                       mode='compute')


def _make_gs(*, held: bool = True, done: tuple = (),
             front: tuple = (), back: tuple = (),
             gold: int | None = 50) -> GameState:
    """直构状态容器:生效序位观察锚定(settle_confirm 分支内 = 战斗后继第一
    节点);持卡/一次性标志位域/部署视图/金经写原语播种(测试自造输入;部署单位
    注入 unit.equips = 纯注入形,见模块 docstring 声明)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.node_pos, (1, 3), sig=_SIG_OBS)
    if held:
        gs.write_logic(gs.active_strategies, [_CARD],
                       produced_by='test-seed', sig=_SIG_SEED)
    if done:
        gs.write_logic(gs.strategy_conditional_done, tuple(done),
                       produced_by='test-seed', sig=_SIG_SEED)
    if front or back:
        f_slots: list[Unit | None] = [
            Unit(char_id=n, star=s, equips=list(e)) for n, s, e in front]
        f_slots += [None] * (4 - len(f_slots))
        b_slots: list[Unit | None] = [
            Unit(char_id=n, star=s, equips=list(e)) for n, s, e in back]
        b_slots += [None] * (6 - len(b_slots))
        gs.write_logic(gs.deployed,
                       DeployedView(front_slots=f_slots, back_slots=b_slots),
                       produced_by='test-seed', sig=_SIG_SEED)
    if gold is not None:
        gs.observe(gs.gold, gold, sig=_SIG_OBS)
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


def _seed_rescuable(gs: GameState) -> Unit | None:
    """可救援态:胜∧损血两帧 + 前排首槽徽携带者(注入形;部署视图未播种
    时返回 None = 调用方不需要持有者引用)。"""
    _settle_frame(gs, 1, 2, killed=True, hp_after=80)
    _settle_frame(gs, 1, 3, killed=True, hp_after=57)
    view = gs.deployed.value
    return view.front_slots[0] if view is not None else None


def _sim_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """sim 门开(出售腿状态副本写通道;monkeypatch 自动还原)。"""
    monkeypatch.setattr(cw_sim_ports, 'sim_backend_installed', lambda: True)


def test_rescue_full_chain_sim(monkeypatch: pytest.MonkeyPatch) -> None:
    """救援全链正例(锁 3 成立面 + 锁 5 sim 出售腿):瞬时位 True + 配额
    一次性标志位 +1 + 槽置 None 定长保持 + 退款金 sell_refund 口径 + 装备回收第三笔;
    效果串一条 strategy_perfect_rescue:<出售角色名>。"""
    _sim_on(monkeypatch)
    gs = _make_gs(front=((('希儿'), 2, (_EM,)), (('卡芙卡'), 1, ())))
    sold = _seed_rescuable(gs)
    effects = check_strategy_perfect_rescue(gs, _SIG)
    assert effects == ('strategy_perfect_rescue:希儿',), '效果串一条'
    assert gs.settlement_perfect_rescue.value is True, '瞬时位置位'
    assert gs.strategy_conditional_done.value == (_LATCH_1,), '配额一次性标志位 +1'
    view = gs.deployed.value
    assert len(view.front_slots) == 4 and len(view.back_slots) == 6, \
        '定长保持'
    assert view.front_slots[0] is None, '出售槽置 None(不移位)'
    assert view.front_slots[1] is not None, '余槽不动'
    assert gs.gold.value == 50 + sell_refund(2, bench_char_cost(sold, gs)), \
        '退款 = sell_refund(star, bench_char_cost) 卖价公式口径'
    assert gs.equips.value == [_EM], '装备回收第三笔(徽回库存)'


def test_rescue_live_sell_leg_zero_write(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """live 形态零写(sim 门关):判定/一次性标志位/瞬时位照常(实机(live)和模拟器(sim)两边同链),出售写状态分支
    三笔(deployed/gold/equips)零写——游戏自执行出售,观察覆盖承接。"""
    gs = _make_gs(front=((('希儿'), 2, (_EM,)),))
    sold = _seed_rescuable(gs)
    effects = check_strategy_perfect_rescue(gs, _SIG)
    assert effects == ('strategy_perfect_rescue:希儿',), '判定成立'
    assert gs.settlement_perfect_rescue.value is True, '瞬时位置位'
    assert gs.strategy_conditional_done.value == (_LATCH_1,), '配额一次性标志位写'
    assert gs.deployed.value.front_slots[0] is sold, 'deployed 零写'
    assert gs.gold.value == 50, '金零写(观察覆盖承接)'
    assert gs.equips.value is None, '装备回收零写'


def test_true_perfect_no_rescue() -> None:
    """真完胜零救援(锁 3 反半边):胜∧无损血(hp 持平)→ 瞬时位 False、
    零配额一次性标志位、零效果串——改写无效果面。"""
    gs = _make_gs(front=((('希儿'), 2, (_EM,)),))
    _settle_frame(gs, 1, 2, killed=True, hp_after=80)
    _settle_frame(gs, 1, 3, killed=True, hp_after=80)
    assert check_strategy_perfect_rescue(gs, _SIG) == ()
    assert gs.settlement_perfect_rescue.value is False, '瞬时位复位'
    assert not gs.strategy_conditional_done.value, '零配额一次性标志位'


@pytest.mark.parametrize(('label', 'k2', 'hp2', 'rows'), [
    ('败局', False, 57, None),
    ('环仅 1 行', True, 57, 1),
    ('尾行 hp None', True, None, None),
])
def test_loss_or_missing_no_rescue(label: str, k2: bool | None,
                                   hp2: int | None,
                                   rows: int | None) -> None:
    """败局/环不足/hp 缺零救援(锁 3 宁缺勿造 + 读法 A 败局零救援):
    瞬时位 False、零配额一次性标志位、零效果串。"""
    gs = _make_gs(front=((('希儿'), 2, (_EM,)),))
    if rows == 1:
        _settle_frame(gs, 1, 3, killed=True, hp_after=57)
    else:
        _settle_frame(gs, 1, 2, killed=True, hp_after=80)
        _settle_frame(gs, 1, 3, killed=k2, hp_after=hp2)
    assert check_strategy_perfect_rescue(gs, _SIG) == (), f'{label} 零效果'
    assert gs.settlement_perfect_rescue.value is False, \
        f'{label} 瞬时位复位'
    assert not gs.strategy_conditional_done.value, f'{label} 零配额一次性标志位'


def test_quota_exhausted_no_rescue() -> None:
    """配额尽零救援零扣(锁 3 配额门):done 预播种 3 一次性标志位键(前缀计数 =
    配额)→ 瞬时位 False、一次性标志位数不变、零效果串——计数形判定只数前缀。"""
    done = tuple(f'perfect_rescue#{_CARD}#{i}' for i in (1, 2, 3))
    gs = _make_gs(done=done, front=((('希儿'), 2, (_EM,)),))
    _seed_rescuable(gs)
    assert check_strategy_perfect_rescue(gs, _SIG) == ()
    assert gs.settlement_perfect_rescue.value is False, '瞬时位复位'
    assert gs.strategy_conditional_done.value == done, '一次性标志位数不变(零扣)'


def test_no_carrier_no_rescue() -> None:
    """徽不携带零救援零扣(锁 3 携带门):deployed 无徽携带者 → 瞬时位
    False、零配额一次性标志位、零 deployed 写(sim 出售腿的前提面不成立)。"""
    gs = _make_gs(front=((('希儿'), 2, ()),))
    _seed_rescuable(gs)
    assert check_strategy_perfect_rescue(gs, _SIG) == ()
    assert gs.settlement_perfect_rescue.value is False, '瞬时位复位'
    assert not gs.strategy_conditional_done.value, '零配额一次性标志位'
    assert gs.deployed.value.front_slots[0] is not None, '零槽写'


def test_deployed_unobserved_no_rescue() -> None:
    """部署视图未观察零救援(宁缺勿造偏严):携带判定无基准禁猜 →
    瞬时位 False、零配额一次性标志位。"""
    gs = _make_gs()
    _seed_rescuable(gs)
    assert check_strategy_perfect_rescue(gs, _SIG) == ()
    assert gs.settlement_perfect_rescue.value is False, '瞬时位复位'
    assert not gs.strategy_conditional_done.value, '零配额一次性标志位'


def test_not_held_zero_action() -> None:
    """未持卡全链零写:瞬时位不写(None 保持 = 旧判语义)、零一次性标志位、零效果——
    门序首位短路。"""
    gs = _make_gs(held=False, front=((('希儿'), 2, (_EM,)),))
    _seed_rescuable(gs)
    assert check_strategy_perfect_rescue(gs, _SIG) == ()
    assert gs.settlement_perfect_rescue.value is None, '瞬时位未判定'
    assert not gs.strategy_conditional_done.value, '零配额一次性标志位'


def test_env_consult_relaxed_after_rescue() -> None:
    """env consult 两态(锁 4):救援置位后完胜判据放宽(损血局 deploy_lock
    锁回退发生 = T-33 完胜提前与游戏「视为完美通关」对齐);None 态损血局
    判据不放宽(零回归,存量判据逐字节等价)。"""
    def _seed_deploy_lock_env(gs: GameState) -> None:
        # deploy_lock 完胜作用域环境(锁记录 + env_grants_done 作用域键,
        # 与配额一次性标志位域 strategy_conditional_done 分域各播)。
        gs.write_logic(gs.env_grant_deploy_locks, (('某角色', 7, (1, 5)),),
                       produced_by='test-seed', sig=_SIG_SEED)
        gs.write_logic(gs.env_grants_done,
                       (('英雄登场', 'deploy_lock_uid#7'),),
                       produced_by='test-seed', sig=_SIG_SEED)

    # 置位态:损血局 + 救援 → 瞬时位 True → deploy_lock 完胜判据过。
    gs = _make_gs(front=((('希儿'), 2, (_EM,)),))
    _seed_deploy_lock_env(gs)
    _seed_rescuable(gs)
    assert check_strategy_perfect_rescue(gs, _SIG) != (), '救援置位'
    effects = check_env_deploy_lock_perfect(gs, _SIG)
    assert effects == ('env_deploy_lock_perfect:某角色@1-4',), \
        '置位后判据放宽:损血局锁回退'
    # None 态:同判据输入但未执行救援(瞬时位 None)→ 判据维持旧形
    # (损血 = 非完胜,零改写)。
    gs2 = _make_gs(front=((('希儿'), 2, (_EM,)),))
    _seed_deploy_lock_env(gs2)
    _seed_rescuable(gs2)
    assert check_env_deploy_lock_perfect(gs2, _SIG) == (), \
        'None 态判据维持旧形(零回归)'


def test_deterministic_zero_rng() -> None:
    """零 rng 确定性(锁 6):同输入两次全新构造执行,效果串/一次性标志位域/瞬时位/
    部署视图逐位相同——救援全确定,seed 无关(无采样面)。"""
    snapshots = []
    for _ in range(2):
        gs = _make_gs(front=((('希儿'), 2, (_EM,)),))
        _seed_rescuable(gs)
        effects = check_strategy_perfect_rescue(gs, _SIG)
        snapshots.append((
            effects,
            gs.settlement_perfect_rescue.value,
            gs.strategy_conditional_done.value,
            gs.deployed.value.front_slots,
            gs.gold.value,
            gs.equips.value,
        ))
    assert snapshots[0] == snapshots[1], '零 rng:两次执行逐位相同'
