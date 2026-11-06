"""策略卡损血档位触发发放登记表测试(镜像 src = kernel/cw_investments.py
的 STRATEGY_HP_LOSS_GRANTS + 构建校验 + 建模假设披露键)。

测试面依据 = 迭代设计 designs/T-142-baoxian.md §4 锁 1 +
REVIEW-T142(免裁 8/8;校验面按 2026-10-28 治理裁定收尾为两漂移哨——
孤儿键 + 装备类别漂移;阈值形/金件数形/双源同值 import 校验不加,双源
对账归本文件测试断言把关;直构形态先例 = 同目录
test_strategy_win_gold_grants.py):
- 登记单一源:行值 = 卡面效果原文直读(保险 id 130501:「每损失20点
  小队生命值,获得5金币和1个随机简易装备」→ (20, 5, '简易', 1),
  数值面全 desc 明写);
- 双源同值测试断言(治理归口):本表每档金 ==
  STRATEGY_ECONOMY['保险'].gold_per_20hp_lost(两表面同出卡面同句,
  单侧改数唯此断言可暴露);
- 构建校验 2 条(漂移哨,import 即炸语义经直调校验函数锁定):孤儿键 +
  装备类别漂移(类别名漂移运行期实况 = 池空静默幻影,发放腿零写无
  台账,import 期哨是唯一响亮拦截面)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_ECONOMY,
    STRATEGY_HP_LOSS_BUCKET_ASSUMPTION,
    STRATEGY_HP_LOSS_GRANTS,
    _validate_strategy_hp_loss_grants,
    equips_by_category,
)

_CARD = '保险'
_ROW = (20, 5, '简易', 1)


def test_registry_row_single_source() -> None:
    """登记单一源(设计 §4 锁 1):保险行 = 卡面数值直读(阈值 20/每档
    5 金/类别简易/每档 1 件);键 ∈ 策略注册表(孤儿哨现值通过 = import
    过闸即证,显式对拍防静默漂移);注册面 = 损血触发族现役首例(同族
    后续损血触发卡各自独立批,禁顺手代登记)。"""
    assert set(STRATEGY_HP_LOSS_GRANTS) == {_CARD}, \
        '注册面 = 损血触发族现役首例(同族后续卡各自独立批,禁顺手代登记)'
    assert STRATEGY_HP_LOSS_GRANTS[_CARD] == _ROW, \
        f'行值漂移(卡面明写 20/5/简易/1): {STRATEGY_HP_LOSS_GRANTS!r}'
    assert _CARD in INVESTMENT_STRATEGIES, '键必须在策略注册表'


def test_gold_dual_source_same_value() -> None:
    """双源同值对账(设计 §4 锁 1 测试断言面;2026-10-28 治理裁定
    import 校验不加,对账归测试把关):发放表每档金 == STRATEGY_ECONOMY
    注册行 gold_per_20hp_lost(同出卡面同句「获得5金币」,单侧改数 =
    触发面发 5 金而估值/引擎通道面仍记旧值,唯此断言可暴露)。"""
    assert STRATEGY_HP_LOSS_GRANTS[_CARD][1] \
        == STRATEGY_ECONOMY[_CARD].gold_per_20hp_lost == 5, \
        '发放表与注册行金值漂移(两表面同出卡面同句)'


def test_category_pool_nonempty_premise() -> None:
    """类别池非空前提(登记行类别直连发放池;漂移哨现值通过 = import
    过闸即证,显式对拍锁池派生面):'简易' 池注册表现算非空,装备腿
    采样域存在。"""
    assert len(equips_by_category(STRATEGY_HP_LOSS_GRANTS[_CARD][2])) > 0, \
        '登记行类别池空(发放腿静默幻影面)'


def test_disclosure_key_registered() -> None:
    """披露键常量已登记且值非空(设计 §5 裁决点 7 kernel 面;一键承载三
    假设——桶结转/真值差/触发源域仅战斗结算,消费 = sim disclosures
    setdefault,随局形态由 sim 链锁承载)。"""
    assert isinstance(STRATEGY_HP_LOSS_BUCKET_ASSUMPTION, str)
    assert STRATEGY_HP_LOSS_BUCKET_ASSUMPTION, '披露键值非空'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验(孤儿哨):键不在策略注册表 → ValueError(import 即炸
    语义;直调校验函数锁同款行为)。阈值/金/件数形与双源同值按治理
    裁定不加,无对应锁(校验函数本体不含,防哨复增由评审把关)。"""
    monkeypatch.setitem(STRATEGY_HP_LOSS_GRANTS, '不存在的卡', _ROW)
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_hp_loss_grants()


def test_validator_category_drift_raises(monkeypatch) -> None:
    """构建校验(装备类别漂移哨):类别池空 → ValueError(类别名漂移
    运行期实况 = 池空静默幻影;池非空哨先例 = on_env_gained 随机装备
    支池空防御,本哨前移至 import 期)。"""
    monkeypatch.setitem(STRATEGY_HP_LOSS_GRANTS, _CARD,
                        (20, 5, '不存在的类别', 1))
    with pytest.raises(ValueError, match='装备类别漂移'):
        _validate_strategy_hp_loss_grants()
