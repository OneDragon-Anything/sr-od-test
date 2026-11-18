"""observe_full heavy 装备域产物测试(坐标伴随域派生面)。

锁的设计约定(装备库存观察采集):
- 同一次 read_equips 产出派生双键:owned_equips 名单 + owned_equip_xy
  坐标伴随域(名 → 格心坐标列表;同名多条 = 列表多元素,序 = 识别命中
  序 = 发出面「同名按出现序游标消费」的出现序口径),零额外识别开销;
- 资源未就绪(模板库/装备区 rect 缺失)→ owned_equip_xy 不置键
  (消费面 .get() 得 None → 装配点零写保现值,宁缺勿造)。

识别层经 monkeypatch 打桩(被测对象 = 组装层派生逻辑,非识别本体)。
"""

import types

from sr_od.application.currency_war.obs import cw_observe_full


def _stub_ready(monkeypatch, hits: list) -> None:
    """识别层打桩:资源就绪分支(read_equips 命中集可控)。"""
    monkeypatch.setattr(cw_observe_full, 'ensure_portrait_templates',
                        lambda ctx: None)
    monkeypatch.setattr(cw_observe_full, 'read_game_state',
                        lambda ctx, frame, screen_name: types.SimpleNamespace(
                            gold=5))
    monkeypatch.setattr(cw_observe_full, 'read_node_sequence',
                        lambda ctx, frame: None)
    monkeypatch.setattr(cw_observe_full, 'read_shop_cards',
                        lambda ctx, frame: None)
    monkeypatch.setattr(cw_observe_full, 'ensure_equip_sift_templates',
                        lambda ctx: object())
    monkeypatch.setattr(cw_observe_full, 'ensure_equip_tm_templates',
                        lambda ctx: None)
    monkeypatch.setattr(cw_observe_full, '_area_rect',
                        lambda ctx, name, screen=None: types.SimpleNamespace(
                            x1=1620, y1=90, x2=1918, y2=710))
    monkeypatch.setattr(cw_observe_full, 'read_equips',
                        lambda frame, templates, equip_rect=None: hits)


def test_heavy_product_derives_xy_map(monkeypatch) -> None:
    """heavy 产物含 owned_equip_xy:同名两件两坐标 + 异名单条目。"""
    _stub_ready(monkeypatch, hits=[
        ('量产型装甲', (1740, 210), 50),
        ('量产型装甲', (1700, 300), 48),
        ('折叠小刀', (1760, 400), 47),
    ])
    out = cw_observe_full.observe_full(None, frame=None, tier='heavy',
                                       source='test')
    assert out['owned_equips'] == ['量产型装甲', '量产型装甲', '折叠小刀']
    assert out['owned_equip_xy'] == {
        '量产型装甲': [(1740, 210), (1700, 300)],
        '折叠小刀': [(1760, 400)],
    }


def test_not_ready_branch_omits_xy_key(monkeypatch) -> None:
    """资源未就绪(模板库未加载)→ 双键缺省:名单 None、xy 不置键。"""
    monkeypatch.setattr(cw_observe_full, 'ensure_portrait_templates',
                        lambda ctx: None)
    monkeypatch.setattr(cw_observe_full, 'read_game_state',
                        lambda ctx, frame, screen_name: types.SimpleNamespace(
                            gold=5))
    monkeypatch.setattr(cw_observe_full, 'read_node_sequence',
                        lambda ctx, frame: None)
    monkeypatch.setattr(cw_observe_full, 'read_shop_cards',
                        lambda ctx, frame: None)
    monkeypatch.setattr(cw_observe_full, 'ensure_equip_sift_templates',
                        lambda ctx: None)
    monkeypatch.setattr(cw_observe_full, 'ensure_equip_tm_templates',
                        lambda ctx: None)
    out = cw_observe_full.observe_full(None, frame=None, tier='heavy',
                                       source='test')
    assert out['owned_equips'] is None
    assert 'owned_equip_xy' not in out
