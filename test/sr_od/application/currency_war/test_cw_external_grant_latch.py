"""外部授予置闩幂等回归锁。

病理:置闩挂点原形 ``+=`` 累加且先于确认点击——确认点击落空(overlay
未关)时 op 机械交回、下一轮重入重走决策再选同卡,同卡二次累加使
pending 虚高,放宽 ``_absorb_external_grant`` 的「差额 ≤ 待吸收数」闸,
虚额残留期内任意正向 bench/equips 失配(含真推算 bug)被误吸收。
修法 = 置闩收敛 kernel 单一源 ``latch_external_grants``(同卡登记不
叠加;不同卡各自累加不受影响——多卡授予形态合法,各卡 pending 并存
叠加,吸收按「差额 ≤ 两闩总额」闸精确扣减)。

锁依据 = ExecBooks.external_grant_latched_cards 字段注释 +
latch_external_grants docstring(幂等契约)。改锁先重推语义:本锁钉的
是「同卡重入不叠加/未申报卡零动作/不同卡定额并存累加」,禁为保绿
机械跟绿。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel import cw_mismatch_policy as _policy
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    Unit,
    game_state_of,
    latch_external_grants,
    register_sig_actors,
)

register_sig_actors('TestGrantLatchWriter')

_SIG = ChannelSig(family='logic_action', actor='TestGrantLatchWriter',
                  mode='compute')


class _FakeSession:
    """局身份桩(game_state_of 裸对象挂载形态;每实例独立容器)。"""


def _bench_view(unit_names: tuple[str, ...], capacity: int = 9) -> BenchView:
    """名字序列 → BenchView(1 星单位前缀占槽,余槽 empty)。"""
    slots = [BenchSlot(kind='unit',
                       unit=Unit(char_id=name, star=1, slot=i + 1))
             for i, name in enumerate(unit_names)]
    while len(slots) < capacity:
        slots.append(BenchSlot(kind='empty'))
    return BenchView(slots=slots, capacity=capacity)


def _seed_gs() -> tuple[object, object]:
    session = _FakeSession()
    gs = game_state_of(session)
    gs.write_logic(gs.bench, _bench_view(('甲',)),
                   produced_by='TestGrantLatchWriter', sig=_SIG)
    gs.write_logic(gs.equips, ['生命之花'],
                   produced_by='TestGrantLatchWriter', sig=_SIG)
    return session, gs


# ============================================================ 幂等:重入不叠加


def test_latch_same_card_reentry_no_double_count():
    """重入不叠加主锁:同卡第二次置闩 = (0, 0),pending 保持一次定额
    (确认点击落空重入形态不再放宽吸收闸);不同卡各自累加不受影响。
    定额期望从申报表现算(``_policy`` 两表现算,卡文改版 → 表更新 →
    期望自动跟随,行为与表偏离才红)。"""
    session, gs = _seed_gs()
    bench_n = _policy.EXTERNAL_BENCH_GRANTS['武装支援']
    equip_n = _policy.EXTERNAL_EQUIP_GRANTS['武装支援']

    n1 = latch_external_grants(gs, '武装支援', actor='T')

    assert n1 == (bench_n, equip_n), '武装支援定额 = 申报表现算'
    assert gs.exec_books.external_bench_grant_pending == bench_n
    assert gs.exec_books.external_equip_grant_pending == equip_n

    n2 = latch_external_grants(gs, '武装支援', actor='T')

    assert n2 == (0, 0), '同卡重入 = 零置入'
    assert gs.exec_books.external_bench_grant_pending == bench_n, \
        '重入不叠加(bench 保持定额,不累加翻倍)'
    assert gs.exec_books.external_equip_grant_pending == equip_n

    jin_bench_n = _policy.EXTERNAL_BENCH_GRANTS['人才引进']
    n3 = latch_external_grants(gs, '人才引进', actor='T')

    assert n3 == (jin_bench_n,
                  _policy.EXTERNAL_EQUIP_GRANTS.get('人才引进', 0)), \
        '不同卡各自累加不受幂等登记影响'
    assert gs.exec_books.external_bench_grant_pending == bench_n + jin_bench_n


def test_latch_unregistered_card_is_noop():
    """未申报卡(排除项)= 零置入 + 不登记(不占用幂等名单)。"""
    session, gs = _seed_gs()

    n = latch_external_grants(gs, '摸个鱼吧III', actor='T')

    assert n == (0, 0), '未申报卡 = (0, 0)'
    assert gs.exec_books.external_bench_grant_pending == 0
    assert gs.exec_books.external_equip_grant_pending == 0
    assert not gs.exec_books.external_grant_latched_cards, '零动作不登记'
