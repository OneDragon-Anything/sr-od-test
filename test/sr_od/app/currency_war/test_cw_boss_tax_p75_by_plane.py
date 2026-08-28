"""boss 税 p75 位面锚(boss_tax_p75_by_plane)结构预埋锁。

结构预埋不激活:plane 1 = 现值逐位零漂移;plane 2 槽位存在但默认值
=现值(P2 sim 观测真值只进注释,扰动未评估前不换数);消费点
(decision_v2.filters 投影安全带)按位面取值。三锁:plane1 零漂移 /
plane2 槽位存在(值=现值 + 注释真值锚)/ 消费点位面取数。
"""

from types import SimpleNamespace

from sr_od.application.currency_war.decision_v2.filters import (
    c1_directed_active,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)

# 当前生效值(=boss_tax_p75 现值;P2 换数前两键必须同值)
_CURRENT_VALUE = 34.0
# sim 侧位面观测真值(cw_coarse_battle 标定 manifest hp_events_by_plane:
# P2 boss n=90 均损 −21.63 vs P1 −19.54)——只作注释锚,不做断言值


def test_plane1_value_zero_drift() -> None:
    """plane1 零漂移锁:与 boss_tax_p75 现值逐位一致。"""
    assert DEFAULT_REGISTRY.boss_tax_p75_by_plane[1] == _CURRENT_VALUE
    assert DEFAULT_REGISTRY.boss_tax_p75_by_plane[1] \
        == DEFAULT_REGISTRY.boss_tax_p75


def test_plane2_slot_exists_same_value() -> None:
    """plane2 槽位存在锁:槽位在、默认值仍=现值(未激活)。"""
    assert set(DEFAULT_REGISTRY.boss_tax_p75_by_plane) == {1, 2}
    assert DEFAULT_REGISTRY.boss_tax_p75_by_plane[2] == _CURRENT_VALUE


def test_boss_tax_scalar_unchanged() -> None:
    """旧标量锚不变:posture_release 等禁触消费点仍读现值(零漂移底座)。"""
    assert DEFAULT_REGISTRY.boss_tax_p75 == _CURRENT_VALUE


def test_consumption_reads_plane_dim(monkeypatch) -> None:
    """消费点锁:投影安全带取数行走位面维 dict。

    手法:stub 掉 posture_release 的可信位与末窗相位门(两者均由
    filters 函数体内懒导入解析,monkeypatch 模块属性即可拦截),
    用 d 门两侧的 hp 值 + 改写 plane1 槽位值,证明短路读的是 dict
    而非旧标量——d≥emergency 侧穿门到达 stub 返回 True,d<emergency
    侧短路返回 False。
    """
    import sr_od.application.currency_war.decision_v2.posture_release as pr
    from dataclasses import replace

    from sr_od.application.currency_war.decision_v2.registry import (
        DecisionV2Registry,
    )

    monkeypatch.setattr(pr, 'hp_decision_trusted', lambda state: True)
    monkeypatch.setattr(pr, 'boss_first_buy_phase',
                        lambda state, session, registry: True)
    sess = SimpleNamespace()
    state = SimpleNamespace(plane=1, hp=58, gold=60)

    # 默认 dict:值=34,d=24<25 → 投影入应急带短路,C1 让位
    assert c1_directed_active(
        state, sess,
        replace(DecisionV2Registry(), c1_directed_spend_enabled=True),
    ) is False

    # plane1 槽位值改写生效(消费点读 dict 的直接证据):值=0,
    # d=58≥25 穿过 d 门与金门,到达相位 stub → True
    registry = replace(
        DecisionV2Registry(),
        c1_directed_spend_enabled=True,
        boss_tax_p75_by_plane={1: 0.0, 2: 34.0},
    )
    assert c1_directed_active(state, sess, registry) is True
