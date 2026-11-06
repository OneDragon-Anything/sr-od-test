"""策略卡条件节点序列改写决策锁(镜像 src = kernel/cw_gain_chain.py 的
check_strategy_node_rewrite 纯决策函数 + 改写词分派 + kernel/cw_game_state.py
的 strategy_conditional_done 纯卡名一次性标志位读面)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-318-jueyi-yule-xingqiu.md §4 锁 2/3/4(REVIEW-T318 §五④):

- 锁 2 真值表:持卡 ∧ 当前槽 kind=='battle' ∧ gold≥180 → 改写形(当前位
  与 boss 位保留,其余槽位 → reward);gold<180 → None;未持卡 → None;
  非 battle 位(reward/encounter/supply/boss)触发 → None(裁决点 2 类型
  读法默认案);
- 锁 3 改写合法性:输出值元素 ∈ NODE_KINDS 词表;
- 锁 4 一次性标志位只置一次:纯卡名一次性标志位置位后函数返回 None;他卡一次性标志位键不误伤(纯卡名
  键域精确匹配)。
构造 = 状态容器直置直调纯函数(零写零 rng;场字段 None = 未注册态回退默认表
为已登记契约,单列边界锁;已注册修饰场字段为权威现值,单列边界锁)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_NODE_REWRITE_TRIGGERS,
)
from sr_od.application.currency_war.kernel.cw_node_schedule import (
    NODE_KINDS,
)

_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')

_CARD = '决议:娱乐星球'

#: 默认地面真值(P1/P2/P3,cw_node_schedule 同值;测试侧直书禁 import
#: 断言双源,断言面 = 改写形逐槽值)。
_P1 = ('reward', 'reward', 'battle', 'battle', 'supply', 'battle',
       'encounter', 'reward', 'boss')
_P2 = ('battle', 'battle', 'supply', 'battle', 'encounter', 'reward', 'boss')
_P3 = _P2


def _gs(*, card: str | None = _CARD,
        done: tuple[str, ...] = (),
        seqs: dict[int, tuple[str, ...]] | None = None) -> GameState:
    """持卡/一次性标志位/场字段直置直构域(纯函数零写,seed 初始值非必需)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if card is not None:
        gs.write_logic(gs.active_strategies, (card,),
                       produced_by='test-seed', evidence='t:card',
                       sig=_LSIG)
    if done:
        gs.write_logic(gs.strategy_conditional_done, done,
                       produced_by='test-seed', evidence='t:done',
                       sig=_LSIG)
    if seqs is not None:
        gs.write_logic(gs.node_seq_by_plane, seqs,
                       produced_by='test-seed', evidence='t:seqs',
                       sig=_LSIG)
    return gs


def _expected_rewrite(pos: tuple[int, int]) -> dict[int, tuple[str, ...]]:
    """期望改写形(当前序位之后非 boss → reward;当前位与 boss 位保留)。"""
    out: dict[int, tuple[str, ...]] = {}
    for plane, seq in ((1, _P1), (2, _P2), (3, _P3)):
        out[plane] = tuple(
            k if (plane < pos[0] or k == 'boss'
                  or (plane == pos[0] and i < pos[1]))
            else 'reward'
            for i, k in enumerate(seq))
    return out


def test_hit_battle_gold_ok_rewrites_remaining_non_boss() -> None:
    """锁 2 主条:P1r3(battle)窗开 gold=180 → 改写形 = 当前位(r3 保持
    battle)与 boss 位保留,r4 起补给/遭遇/奖励位全换 reward(P2/P3 全域
    展平;当前位置之前槽位原值不动)。"""
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        check_strategy_node_rewrite,
    )
    got = check_strategy_node_rewrite(_gs(), pos=(1, 3), gold=180)
    assert got == _expected_rewrite((1, 3)), f'改写形漂移: {got!r}'
    assert got is not None and got[1][2] == 'battle', '当前位保留'
    assert got is not None and got[1][8] == 'boss' and got[2][6] == 'boss' \
        and got[3][6] == 'boss', 'boss 位保留'


def test_hit_plane_first_battle_rewrites_rest_only() -> None:
    """锁 2 展平域:P2r1(battle 位面首)窗开 → P1 全程原样(「剩余」= 当前
    序位之后),P2 自当前位起改写,P3 全域展平。"""
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        check_strategy_node_rewrite,
    )
    got = check_strategy_node_rewrite(_gs(), pos=(2, 1), gold=200)
    assert got is not None and got[1] == _P1, '前位面原样复用'
    assert got is not None and got[2][0] == 'battle', '当前位保留'
    assert got is not None and got[2][1:] == tuple(
        'reward' if k != 'boss' else 'boss' for k in _P2[1:]), 'P2 余位改写'
    assert got is not None and got[3] == tuple(
        'reward' if k != 'boss' else 'boss' for k in _P3), 'P3 全域展平'


def test_gold_below_threshold_returns_none() -> None:
    """锁 2 短路(gold<180):battle 位 + 179 → None(表值门槛)。"""
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        check_strategy_node_rewrite,
    )
    assert check_strategy_node_rewrite(_gs(), pos=(1, 3), gold=179) is None


def test_no_card_returns_none() -> None:
    """锁 2 短路(未持卡):表外零条目 → None。"""
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        check_strategy_node_rewrite,
    )
    assert check_strategy_node_rewrite(_gs(card=None), pos=(1, 3),
                                       gold=500) is None


def test_non_battle_node_returns_none() -> None:
    """锁 2 短路(类型读法):reward/encounter/supply/boss 位窗开 → None
    (「进入战斗」仅 kind=='battle';reward 位窗开在 sim 亦走战斗结算,
    词面体系排除论证 = 注册表头注释,轴取舍直接决定首触发点位次)。"""
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        check_strategy_node_rewrite,
    )
    for r, kind in enumerate(_P1, start=1):
        if kind == 'battle':
            continue
        got = check_strategy_node_rewrite(_gs(), pos=(1, r), gold=500)
        assert got is None, f'P1r{r}({kind}) 误触发'


def test_latched_card_returns_none() -> None:
    """锁 4 一次性标志位只置一次:纯卡名一次性标志位 ∈ strategy_conditional_done → None(改写
    一局至多一次)。"""
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        check_strategy_node_rewrite,
    )
    gs = _gs(done=(_CARD,))
    assert check_strategy_node_rewrite(gs, pos=(1, 3), gold=500) is None


def test_foreign_latch_key_no_false_block() -> None:
    """锁 4 键域精确:他卡一次性标志位键(复合键/他卡名)在场不误伤本卡(纯卡名键
    域匹配,与 strategy_grants_done 复合串一次性标志位分域纪律的对偶面)。"""
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        check_strategy_node_rewrite,
    )
    gs = _gs(done=('迷之旅人#faction_count', '另卡'))
    got = check_strategy_node_rewrite(gs, pos=(1, 3), gold=500)
    assert got == _expected_rewrite((1, 3)), '他卡一次性标志位键误短路'


def test_output_values_within_node_kinds() -> None:
    """锁 3 改写合法性:输出值元素 ∈ NODE_KINDS 词表(改写产物是节点
    类型,消费面 node_sequence_of/观察锚定直用)。"""
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        check_strategy_node_rewrite,
    )
    for pos in ((1, 3), (2, 1), (3, 4)):
        got = check_strategy_node_rewrite(_gs(), pos=pos, gold=500)
        assert got is not None
        for seq in got.values():
            assert set(seq) <= NODE_KINDS, f'{pos} 改写产出集外词: {seq!r}'


def test_unregistered_field_falls_back_to_default_tables() -> None:
    """锁 2 边界(场字段 None = 未注册态):回退默认表评估当前槽 kind,
    改写产出 = 默认表基座的全 dict(消费方回退无窗契约的写端镜像)。"""
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        check_strategy_node_rewrite,
    )
    gs = _gs()
    assert gs.node_seq_by_plane.value is None, '前置:未注册态'
    got = check_strategy_node_rewrite(gs, pos=(1, 3), gold=500)
    assert got == _expected_rewrite((1, 3)), '未注册回退基座漂移'


def test_registered_field_is_authoritative_base() -> None:
    """锁 2 边界(场字段已注册 = 权威现值):修饰局序列(env 注册写落
    全量)为改写基座——非默认表形(人身意外险 P1=10)照现值改写。"""
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        check_strategy_node_rewrite,
    )
    from sr_od.application.currency_war.kernel.cw_node_schedule import (
        resolve_plane_node_seqs,
    )
    seqs = resolve_plane_node_seqs('人身意外险')
    assert len(seqs[1]) == 10, '前置:修饰表 P1=10'
    got = check_strategy_node_rewrite(_gs(seqs=seqs), pos=(1, 3), gold=500)
    assert got is not None
    for plane, seq in seqs.items():
        expect = tuple(
            k if (plane < 1 or k == 'boss' or (plane == 1 and i < 3))
            else 'reward'
            for i, k in enumerate(seq))
        assert got[plane] == expect, f'修饰基座 P{plane} 改写形漂移'


def test_word_dispatch_unknown_word_raises_key_error(monkeypatch) -> None:
    """改写词分派笔误形态:表值改写词不在分派表 → KeyError 响亮(2026-
    10-28 治理口径:闭集哨删,分派 KeyError 即唯一拦截面)。"""
    from sr_od.application.currency_war.kernel import cw_gain_chain
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        _NODE_REWRITE_WORD_IMPLS,
        check_strategy_node_rewrite,
    )
    assert set(_NODE_REWRITE_WORD_IMPLS) == {
        STRATEGY_NODE_REWRITE_TRIGGERS[_CARD][2]}, '分派表与注册词表对拍'
    monkeypatch.setitem(cw_gain_chain.STRATEGY_NODE_REWRITE_TRIGGERS, _CARD,
                        ('battle_entry', 180, '词表外改写词'))
    with pytest.raises(KeyError):
        check_strategy_node_rewrite(_gs(), pos=(1, 3), gold=500)
