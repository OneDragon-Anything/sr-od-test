"""外部授予置闩幂等化 + 闩窗口上界回归锁(三审应修补丁①/存疑③收口)。

病理:置闩挂点原形 ``+=`` 累加且先于确认点击——确认点击落空(overlay
未关)时 op 机械交回、下一轮重入重走决策再选同卡,同卡二次累加使
pending 虚高,放宽 ``_absorb_external_grant`` 的「差额 ≤ 待吸收数」闸,
虚额残留期内任意正向 bench/equips 失配(含真推算 bug)被误吸收。
修法 = 置闩收敛 kernel 单一源 ``latch_external_grants``(同卡登记不
叠加;不同卡各自累加不受影响)。同批给闩加窗口上界:等值观察(实读
== 逻辑态,授予未入账)不消费会让闩跨多备战帧存续,达
``EXTERNAL_GRANT_EQUAL_OBS_LIMIT`` 次销闩 + ``external_grant_expired``
台账行——误销后果 = 真实授予迟到时照真失配停(响亮),不销后果 =
静默吞真 bug。

锁依据 = ExecBooks.external_grant_latched_cards / external_grant_equal_
obs 字段注释 + latch_external_grants docstring(幂等契约)+ GameState.
_tick_external_grant_window docstring(计数粒度/销闩联动)。改锁先重
推语义:本锁钉的是「同卡重入不叠加/未申报卡零动作/达限销闩留证/
吸收复位计数」,禁为保绿机械跟绿。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel import cw_mismatch_policy as _policy
from sr_od.application.currency_war.kernel.cw_game_state import (
    EXTERNAL_GRANT_EQUAL_OBS_LIMIT,
    BenchSlot,
    BenchView,
    ChannelSig,
    Unit,
    consume_defect_sink,
    game_state_of,
    latch_external_grants,
    register_sig_actors,
    set_defect_sink,
)

register_sig_actors('TestGrantLatchWriter')

_SIG = ChannelSig(family='logic_action', actor='TestGrantLatchWriter',
                  mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep',
                      screen='货币战争-备战', mode='read',
                      quality={'bench': 'real_read'})


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
    (确认点击落空重入形态不再放宽吸收闸);不同卡各自累加不受影响。"""
    session, gs = _seed_gs()

    n1 = latch_external_grants(gs, '武装支援', actor='T')

    assert n1 == (2, 1), '武装支援 = bench+2/equips+1(申报表定额)'
    assert gs.exec_books.external_bench_grant_pending == 2
    assert gs.exec_books.external_equip_grant_pending == 1

    n2 = latch_external_grants(gs, '武装支援', actor='T')

    assert n2 == (0, 0), '同卡重入 = 零置入'
    assert gs.exec_books.external_bench_grant_pending == 2, \
        '重入不叠加(bench 保持定额,不累加成 4)'
    assert gs.exec_books.external_equip_grant_pending == 1

    n3 = latch_external_grants(gs, '人才引进', actor='T')

    assert n3 == (1, 0), '不同卡各自累加不受幂等登记影响'
    assert gs.exec_books.external_bench_grant_pending == 3


def test_latch_unregistered_card_is_noop():
    """未申报卡(排除项)= 零置入 + 不登记(不占用幂等名单)。"""
    session, gs = _seed_gs()

    n = latch_external_grants(gs, '摸个鱼吧III', actor='T')

    assert n == (0, 0), '未申报卡 = (0, 0)'
    assert gs.exec_books.external_bench_grant_pending == 0
    assert gs.exec_books.external_equip_grant_pending == 0
    assert not gs.exec_books.external_grant_latched_cards, '零动作不登记'


# ============================================================ 窗口上界:等值观察达限销闩


def test_grant_latch_expires_after_equal_obs_limit(monkeypatch):
    """闩过期作废锁:置闩后连续等值观察达限 → 两闩销(bench/equips 联动)
    + external_grant_expired 台账行留证(非真失配行,安灯零触发)。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    session, gs = _seed_gs()
    latch_external_grants(gs, '武装支援', actor='T')
    equal_view = _bench_view(('甲',))   # 与逻辑态等值的实读

    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        for i in range(EXTERNAL_GRANT_EQUAL_OBS_LIMIT - 1):
            gs.observe(gs.bench, equal_view, sig=_SIG_OBS)
            assert gs.exec_books.external_bench_grant_pending == 2, \
                f'第 {i + 1} 次等值观察未达限,闩还在'
            assert gs.exec_books.external_equip_grant_pending == 1
        gs.observe(gs.bench, equal_view, sig=_SIG_OBS)   # 达限次
    finally:
        set_defect_sink(None)
        consume_defect_sink()

    assert gs.exec_books.external_bench_grant_pending == 0, '达限销闩(bench)'
    assert gs.exec_books.external_equip_grant_pending == 0, '达限销闩(equips 联动)'
    assert gs.exec_books.external_grant_equal_obs == 0, '销闩即窗口关闭'
    assert [r['kind'] for r in rows] == ['external_grant_expired'], \
        '作废落台账行留证'
    assert fired == [], '作废非真失配,安灯零触发'


# ============================================================ 吸收复位计数


def test_absorb_resets_window_counter():
    """吸收复位锁:等值计数在非等值观察(失配吸收)时归零——残留闩
    不因旧计数毒化,新窗口需重新攒满等值次数才销。"""
    session, gs = _seed_gs()
    latch_external_grants(gs, '武装支援', actor='T')
    gs.observe(gs.bench, _bench_view(('甲',)), sig=_SIG_OBS)   # 等值 ×1
    assert gs.exec_books.external_grant_equal_obs == 1
    # 等值观察后字段来源已转 observation;失配分流闸只认 logic 来源,
    # 备战帧对账链会把实读播种回 logic(observe→reconcile 播种序,吸收
    # 闸的既有运作前提),此处重播种模拟之。
    gs.write_logic(gs.bench, _bench_view(('甲',)),
                   produced_by='TestGrantLatchWriter', sig=_SIG)

    # 失配观察:实读多出 2 单位(差额 2 ≤ 待吸收 2)→ 精确吸收
    absorbed_view = _bench_view(('乙', '丙', '甲'))

    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        gs.observe(gs.bench, absorbed_view, sig=_SIG_OBS)
    finally:
        set_defect_sink(None)
        consume_defect_sink()

    assert [r['kind'] for r in rows] == ['external_grant_absorbed']
    assert gs.exec_books.external_bench_grant_pending == 0, 'bench 腿已吸收'
    assert gs.exec_books.external_equip_grant_pending == 1, 'equips 腿残留'
    assert gs.exec_books.external_grant_equal_obs == 0, \
        '非等值观察 = 窗口有了结进展,计数归零'

    # 残留闩在新计数下重新攒:2 次等值不足销,旧计数(1)不继承
    for _ in range(EXTERNAL_GRANT_EQUAL_OBS_LIMIT - 1):
        gs.observe(gs.equips, ['生命之花'], sig=_SIG_OBS)
    assert gs.exec_books.external_equip_grant_pending == 1, \
        '残留闩按新计数重新攒,未达限不销'
