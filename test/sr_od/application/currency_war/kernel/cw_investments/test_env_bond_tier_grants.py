"""ENV_BOND_TIER_GRANTS 注册表构建校验测试(T-41 特邀专家:加拉赫击破
档分支;镜像 src = kernel/cw_investments.py 写状态副本发放注册表区)。

被测面 = 原稿锁面 §2.2 四条(import 即炸语义,注入 + 直调,沿
test_env_grants.py 的 ENV_STREAK/ENV_REFRESH 校验测试惯用法):
① 孤儿键 ⊆ INVESTMENT_ENVS;② 羁绊名 ∈ 羁绊注册表(trait_by_name);
③ 装备名 ∈ EQUIPMENTS;④ 卡面档位对拍闸(trait_by_name tiers 串 ⊆
effect 原文)。

v4.7 换赛季退役态:唯一条目「特邀专家:加拉赫」已随羁绊消费点迁移批
退役(击破档位谱换代 2/4/6/9→2/4/6/8,卡面效果待投资域 v4.7 重采)
——现表断言 = 空表退役态;四漂移哨结构保留,行为锁面经注入条目延续
(v4.7 新条目重采后按原语义恢复登记,哨防线原样生效)。
"""
from __future__ import annotations

import dataclasses

import pytest

from sr_od.application.currency_war.data.cw_traits_data import (
    trait_by_name,
)
from sr_od.application.currency_war.kernel import cw_investments

_ENV = '特邀专家:加拉赫'
_ROW = ('击破', '以太钻头')


def test_registry_current_value_and_validation_passes() -> None:
    """现表 = v4.7 退役态空表 + 直调校验器零异常(条目退役声明见
    src 表头注释;新条目登记时本断言即红灯强制复审,沿 ENV_STREAK_
    GRANTS 测试惯用法)。"""
    assert cw_investments.ENV_BOND_TIER_GRANTS == {}
    cw_investments._validate_env_bond_tier_grants()


def test_orphan_key_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """① 孤儿键(版本更新改名/移除环境后静默失联 → 构建期炸)。"""
    bad = dict(cw_investments.ENV_BOND_TIER_GRANTS)
    bad['不存在环境'] = _ROW
    monkeypatch.setattr(cw_investments, 'ENV_BOND_TIER_GRANTS', bad)
    with pytest.raises(ValueError, match='孤儿键'):
        cw_investments._validate_env_bond_tier_grants()


def test_bond_drift_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """② 羁绊名漂移(羁绊注册表版本改名 → 档位单一源失联 = 判据失效,
    构建期炸)。"""
    bad = dict(cw_investments.ENV_BOND_TIER_GRANTS)
    bad[_ENV] = ('不存在的羁绊', '以太钻头')
    monkeypatch.setattr(cw_investments, 'ENV_BOND_TIER_GRANTS', bad)
    with pytest.raises(ValueError, match='羁绊名漂移'):
        cw_investments._validate_env_bond_tier_grants()


def test_equip_drift_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """③ 装备名漂移(发放写出库存里不存在的名字 = 假身份混进 equips)。"""
    bad = dict(cw_investments.ENV_BOND_TIER_GRANTS)
    bad[_ENV] = ('击破', '不存在的装备')
    monkeypatch.setattr(cw_investments, 'ENV_BOND_TIER_GRANTS', bad)
    with pytest.raises(ValueError, match='装备名漂移'):
        cw_investments._validate_env_bond_tier_grants()


def test_card_tier_cross_check_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """④ 卡面档位对拍闸:羁绊注册表 tiers 单侧改档(版本改档)而卡面
    原文未随 → 构建期炸强制人工复审(防双源漂移静默错发;Trait 冻结
    dataclass 且 tiers 为 layers 派生 property——经 dataclasses.replace
    换 layers 造改档实例,monkeypatch.setitem 换注册表条目,自动还原)。
    篡改值取非子串形态——子串包含对拍的极端同形假通过(如改 (4,6),
    串 '4/6' 仍 ⊆ 原文 '2/4/6/9')是设计登记的可接受边界,闸目的 =
    漂移可见性非精确解析。"""
    bad = dict(cw_investments.ENV_BOND_TIER_GRANTS)
    bad[_ENV] = _ROW
    monkeypatch.setattr(cw_investments, 'ENV_BOND_TIER_GRANTS', bad)
    from sr_od.application.currency_war.data.cw_traits_data import TraitLayer
    _drifted_layers = tuple(
        TraitLayer(layer=n, quality=0, trait_desc='')
        for n in (1, 2, 3))
    drifted = dataclasses.replace(trait_by_name['击破'],
                                  layers=_drifted_layers)
    monkeypatch.setitem(trait_by_name, '击破', drifted)
    with pytest.raises(ValueError, match='卡面档位对拍失同步'):
        cw_investments._validate_env_bond_tier_grants()
