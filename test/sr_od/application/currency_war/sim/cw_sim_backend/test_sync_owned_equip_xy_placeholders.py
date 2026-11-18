"""SimBackend 装备库存坐标伴随域占位同步测试。

锁的设计约定(穿装参数面迁移:sim 穿装链保活的环境快照首写端):
- sim 局伴随域无初始化路径(开局种子不种、观察链生成器直出不产本键)
  → 占位同步即环境快照首写端:None 空表起算,首个 advance 步界即把
  名单条目映射为唯一占位坐标(终审 F1 回归锁:None 短路会让占位恒不
  生效,穿装需求帧陷入坐标全缺席自愈循环);
- 占位唯一化:同名多件逐差额 append 界外哨兵,坐标↔条目一一对应,
  反查(记账路径总契约)可命中;
- 等值零写幂等:名单无新增差额 → 不重写(evidence 不变,与板面真值
  观察同纪律);
- 名单未就绪(None)→ 跳过。

被测单一源 = ``cw_sim_backend.SimBackend._sync_owned_equip_xy_placeholders``。
"""

from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    Field,
    resolve_item_by_xy,
)
from sr_od.application.currency_war.sim.cw_sim_backend import SimBackend
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_OBS = ChannelSig(family='obs', actor='test')

#: 开局 HP 查表唯一实证档(RunConfig 字段注释;sim 构造期校验按档查表)。
_CFG = RunConfig(selected_difficulty='A8', enemy_difficulty=108)


def _make_backend() -> SimBackend:
    """真后端构造(开局序列纯内存,含 seed_opening_state 的开局种子面)。"""
    return SimBackend(seed=0, cfg=_CFG)


def test_none_first_write_appends_resolvable_placeholders() -> None:
    """None 空表起算:首步把名单条目映射为唯一占位,反查可命中。"""
    backend = _make_backend()
    # 终审 F1 前提锁:sim 局伴随域无任何初始化路径(开局种子不种本域)
    assert backend.gs.owned_equip_xy.value is None
    backend.gs.observe(backend.gs.equips,
                       ['量产型装甲', '量产型装甲'], sig=_OBS)
    backend._sync_owned_equip_xy_placeholders()
    xy = backend.gs.owned_equip_xy.value
    assert xy == {'量产型装甲': [(-1001, -1000), (-1002, -1000)]}
    # 同名两件占位坐标互异且均可反查命中(唯一化前提 + 记账全链通)
    assert resolve_item_by_xy(backend.gs, -1001, -1000) == '量产型装甲'
    assert resolve_item_by_xy(backend.gs, -1002, -1000) == '量产型装甲'


def test_equal_value_zero_write_idempotent() -> None:
    """名单无新增差额 → 等值零写(value 与 evidence 均不变)。"""
    backend = _make_backend()
    backend.gs.observe(backend.gs.equips, ['量产型装甲'], sig=_OBS)
    backend._sync_owned_equip_xy_placeholders()
    first = backend.gs.owned_equip_xy
    backend._sync_owned_equip_xy_placeholders()
    assert backend.gs.owned_equip_xy is first
    assert backend.gs.owned_equip_xy.value == {
        '量产型装甲': [(-1001, -1000)]}


def test_unobserved_equips_skipped(monkeypatch) -> None:
    """名单未就绪(None)→ 跳过(伴随域现值与 evidence 均不动)。"""
    backend = _make_backend()
    backend.gs.observe(backend.gs.equips, ['量产型装甲'], sig=_OBS)
    backend._sync_owned_equip_xy_placeholders()
    before = backend.gs.owned_equip_xy
    monkeypatch.setattr(backend.gs, 'equips', Field())   # 未观察 None
    backend._sync_owned_equip_xy_placeholders()
    assert backend.gs.owned_equip_xy is before

