"""ENV_BOND_TIER_GRANTS 注册表构建校验测试(T-41 特邀专家:加拉赫击破
档分支;镜像 src = kernel/cw_investments.py 世界发放注册表区)。

被测面 = T-41 设计稿 §2.2 四条(import 即炸语义,注入 + 直调,沿
test_env_grants.py 的 ENV_STREAK/ENV_REFRESH 校验测试惯用法):
① 孤儿键 ⊆ INVESTMENT_ENVS;② 羁绊名 ∈ FACTIONS;③ 装备名 ∈
EQUIPMENTS;④ 卡面档位对拍闸(FACTIONS tiers 串 ⊆ effect 原文);
现值过闸('2/4/6/9' ⊆「激活2/4/6/9击破羁绊时」)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.data.cw_factions import FACTIONS
from sr_od.application.currency_war.kernel import cw_investments

_ENV = '特邀专家:加拉赫'


def test_registry_current_value_and_validation_passes() -> None:
    """现表与卡面 id 142 同源全等 + 直调校验器零异常(加行/改行漏改本
    测试即红灯,沿 ENV_STREAK_GRANTS 测试惯用法)。"""
    assert cw_investments.ENV_BOND_TIER_GRANTS == {_ENV: ('击破', '以太钻头')}
    cw_investments._validate_env_bond_tier_grants()


def test_orphan_key_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """① 孤儿键(版本更新改名/移除环境后静默失联 → 构建期炸)。"""
    bad = dict(cw_investments.ENV_BOND_TIER_GRANTS)
    bad['不存在环境'] = ('击破', '以太钻头')
    monkeypatch.setattr(cw_investments, 'ENV_BOND_TIER_GRANTS', bad)
    with pytest.raises(ValueError, match='孤儿键'):
        cw_investments._validate_env_bond_tier_grants()


def test_bond_drift_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """② 羁绊名漂移(FACTIONS 版本改名 → 档位单一源失联 = 判据失效,
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
    """④ 卡面档位对拍闸:FACTIONS tiers 单侧改档(版本改档,2/4/6/9 →
    2/4/6/8)而卡面原文未随 → 构建期炸强制人工复审(防双源漂移静默错发;
    monkeypatch.setattr 自动还原共享 FactionInfo)。篡改值取非子串形态
    ——子串包含对拍的极端同形假通过(如改 (4,6),串 '4/6' 仍 ⊆ 原文
    '2/4/6/9')是设计登记的可接受边界,闸目的 = 漂移可见性非精确解析。"""
    monkeypatch.setattr(FACTIONS['击破'], 'tiers', (2, 4, 6, 8))
    with pytest.raises(ValueError, match='卡面档位对拍失同步'):
        cw_investments._validate_env_bond_tier_grants()
