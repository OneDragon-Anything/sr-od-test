"""cw_game_state 回放守恒测试(镜像 src = kernel/cw_game_state.py 的
restore_state_snapshot._bench_view / full_state_snapshot 往返;同 src 兄弟
测试 = kernel/test_game_state.py 状态容器机制正名主题文件〔已登记文件,主题不同
不混写〕)。

测试面依据 = 迭代 T-39 专家研讨会设计(.debug/progress/2026-09-23-invest-
effects-calc/designs/T-39-zhuanjia-yantaohui.md)§2.3 + §4 锁 11:
- 回放守恒:full_state_snapshot(asdict 全字段落盘)→ restore 往返,
  BenchSlot.item 逐槽保真(unit/empty 槽 None 同保真)——restore 侧只读
  kind/unit 会丢身份,回放判读面身份不可溯即红;
- 旧档形态:槽值无 item 键 → .get 容忍恢复 None,零炸零迁移。

另辖:商店投影写入渠道签名纪律(投影测试 M5)——写入口族校验
(《商店黑板容器化方案》§3.2.4 硬约束 2),主断言对象 = 本镜像 src
的写入口族门。
"""
from __future__ import annotations

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_card as _card,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_gs,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_buy_card_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    ShopActionExecuted,
    Unit,
    restore_state_snapshot,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
)

_SIG_OBS = ChannelSig(family='obs', actor='ReplayTest')


def _mixed_bench_view() -> BenchView:
    """五类槽混合视图(unit/道具三类带名/empty),覆盖 item 全取值形态。"""
    slots = [
        BenchSlot(kind='unit', unit=Unit(char_id='希儿', star=1)),
        BenchSlot(kind='bookcard', item='专家邀请函'),
        BenchSlot(kind='supply_box', item='简易武装箱'),
        BenchSlot(kind='tome', item='星徽秘典'),
        BenchSlot(kind='empty'),
    ]
    return BenchView(slots=slots + [BenchSlot(kind='empty')] * 4, capacity=9)


def test_snapshot_restore_round_trip_item_per_slot() -> None:
    """回放守恒(设计 §2.3 + §4 锁 11):观察写 bench 混合槽位 → 快照含
    bench 域 → restore 往返 item 逐槽保真(道具三类带名 + unit/empty
    None);回放判读面身份可溯。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench, _mixed_bench_view(), sig=_SIG_OBS)
    snap = gs.full_state_snapshot()
    assert 'bench' in snap['values'], 'bench 域进快照'

    restored = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(restored, snap)
    origin = gs.bench.value.slots
    back = restored.bench.value.slots
    assert len(back) == len(origin), '槽数保真'
    for i, (o, b) in enumerate(zip(origin, back, strict=True)):
        assert (b.kind, b.item) == (o.kind, o.item), \
            f'槽{i} kind+item 逐位保真: {(b.kind, b.item)} != {(o.kind, o.item)}'
    assert back[1].item == '专家邀请函' and back[2].item == '简易武装箱' \
        and back[3].item == '星徽秘典', '道具三轴名字逐一已登记'


def test_restore_legacy_slot_without_item_key_tolerated() -> None:
    """旧档形态(设计 §2.3):槽值无 item 键 → 恢复 item=None 零炸
    (零迁移;回放身份不可溯 = 观察界限,设计 §6.3③ 申报口径)。"""
    legacy_slots = [
        {'kind': 'supply_box'},                      # 旧档道具槽无 item 键
        {'kind': 'unit', 'unit': {'char_id': '银狼', 'star': 1,
                                  'equips': []}},
        {'kind': 'empty'},
    ]
    snap = {'values': {'bench': {'slots': legacy_slots, 'capacity': 9}},
            'prov': {}}
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(gs, snap)
    slots = gs.bench.value.slots
    assert [s.kind for s in slots] == ['supply_box', 'unit', 'empty'], \
        'kind 照常恢复'
    assert all(s.item is None for s in slots), '旧档缺键 → item=None 容忍'


# ---- 商店投影写入渠道签名纪律(投影测试 M5)----


def _gs_of(**axes):
    """投影场景种子(原裸帧合成配方承接:节点整域不写、空店离屏;
    域覆盖集与原合成口逐域一致)。"""
    return cw4_gs(node_fill=False, shop_screen='off', **axes)


def test_wrong_family_sig_rejected():
    """渠道签名纪律:非 logic_action 族显式炸(§3.2.4 硬约束 2)。"""
    gs = _gs_of(gold=30, shop=[_card('希儿')])
    with pytest.raises(ValueError):
        report_action_buy_card_param(
            gs, CwActionBuyCardParam(card=_card('希儿')),
            executed=ShopActionExecuted(bought_count=1),
            sig=ChannelSig(family='obs', actor='CwScreenShop'))
