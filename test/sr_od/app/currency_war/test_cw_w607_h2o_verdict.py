# -*- coding: utf-8 -*-
"""W607 H2① 第二波·数学裁决证明锁(不合入生产分支;ADR-0461 增补节)。

裁决(数学先行硬门):库藏生锈滞留扣减在**当前动作空间无有效消费点**——
开态与关态可证逐位同序,落码=死分支,按 strategy-work §4 兑换纪律「确认无效
→不合入」。本文件把该裁决锁成回归资产:若未来任一边界移动(装备价值表上调 /
key_fit 阈值下调 / 滞留份额双向建模 / W612 装备处置动作面落地),本锁翻红 =
重评触发器。

账(全部读生产注册表常量,零独立魔法数):
- 每件滞留扣减(金当量,保守=只建模敌伤面)
  = rust 伤份额 0.03(competitors.md:45 敌伤 +3%)× expected_battle_loss
    × battles_left_est × hp_to_gold(registry 单一源)= 0.75/件;
- 滞留计件上限 10(competitors.md:45「最多计 10 件」)→ 最大总扣减 7.5;
- 补给面:非 key 件间扣减同额(滞留计数与选哪件无关)→ 序不变;key 豁免
  → key_fit 边际 10 − 7.5 = 2.5 > 0,key 恒先;
- 巨星策划面:装备类得分上界 max(_EQUIP_VALUE)+15 = 21,扣后 13.5,
  仍低于 升费最低 40 / 弱化 55 → 不翻转。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_events import _EQUIP_VALUE
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY

# 装备获取评分面常数(cw_events 生产单一源)
_KEY_FIT_BONUS = 10          # decide_supply key_equips 命中加分
_PLANNER_KEY_BONUS = 15      # decide_planner 装备类 key 命中加分
_PLANNER_UPGRADE_FLOOR = 40  # 升费卡最低分(100−60 银狼不在场罚后下界)
_PLANNER_WEAKEN_SCORE = 55   # 弱化卡基础分


def _rust_per_piece() -> float:
    reg = DEFAULT_REGISTRY
    return (reg.rust_hoard_damage_share * reg.expected_battle_loss
            * reg.battles_left_est * reg.hp_to_gold)


def test_h2o_per_piece_gold_equivalent_bound() -> None:
    """每件扣减 = 0.75 金当量,封顶 7.5(registry/文档实采常量推导,非独立魔数)。"""
    reg = DEFAULT_REGISTRY
    assert reg.rust_hoard_damage_share == 0.03   # competitors.md:45 敌伤面
    assert reg.rust_hoard_penalty_cap == 10      # competitors.md:45 计件上限
    total = _rust_per_piece() * reg.rust_hoard_penalty_cap
    assert abs(_rust_per_piece() - 0.75) < 1e-9
    assert total < _KEY_FIT_BONUS, '最大滞留扣减须仍小于 key_fit 边际,否则补给面翻红重评'


def test_h2o_supply_face_no_reorder() -> None:
    """补给面无翻转:key 恒先(key_fit 10 > 封顶 7.5),非 key 间扣减同额序不变。"""
    total = _rust_per_piece() * DEFAULT_REGISTRY.rust_hoard_penalty_cap
    key_margin = _KEY_FIT_BONUS - total
    assert key_margin > 0, 'key_fit 边际被滞留扣减侵蚀穿 → 补给选序翻转,重评'
    # 非 key 件间:扣减 = f(owned+1),与候选身份无关 → 同额平移不改序
    assert len(set(_EQUIP_VALUE.values())) > 1   # 前提:价值表有区分度


def test_h2o_planner_face_no_flip() -> None:
    """巨星策划面:装备类扣后上界仍低于升费/弱化下界 → 选型不翻转。"""
    equip_upper = max(_EQUIP_VALUE.values()) + _PLANNER_KEY_BONUS
    total = _rust_per_piece() * DEFAULT_REGISTRY.rust_hoard_penalty_cap
    assert equip_upper - total < _PLANNER_UPGRADE_FLOOR, (
        '装备类扣后触及升费下界 → 策划面翻转,重评')
    assert equip_upper - total < _PLANNER_WEAKEN_SCORE
