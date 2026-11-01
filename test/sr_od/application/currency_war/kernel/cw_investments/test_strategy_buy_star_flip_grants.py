"""策略卡购买翻星登记表测试(镜像 src = kernel/cw_investments.py 的
STRATEGY_BUY_STAR_FLIP_GRANTS + 构建校验)。

测试面依据 = 迭代设计 designs/T-187-sifei-jinsheng.md(定稿)§2.1/§4 锁 1
+ REVIEW-T187 §3.2③/§四.4(卡面官方原文:「你购买的下1个4费角色将立刻
升到2星。获得12金币。」;直构形态先例 = 同目录
test_strategy_first_buy_xp_grants.py):
- 登记单一源:行值 = 卡面直读(四费晋升 id 202201:费用过滤档 4,目标
  星级 2);键 ∈ 策略注册表且 id 对拍(防改名/换 id 后静默错挂);
- 构建校验负控:孤儿键 + 值域合法性三哨(费用档域/目标星级域/顾问型
  零冲突——错值运行期实况 = 谓词静默永不匹配,import 期哨是唯一响亮
  拦截面;纯笔误类值形查按 2026-10-28 治理不加,行值防线 = 本锁精确
  断言 + id 对拍)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_BUY_STAR_FLIP_GRANTS,
    STRATEGY_GRANTS,
    _validate_strategy_buy_star_flip_grants,
)

_CARD = '四费晋升'
_ROW = (4, 2)


def test_registry_row_single_source() -> None:
    """登记单一源(锁 1):键集 = 族现役首例(同族后续卡各自独立批,
    禁顺手代登记);行值 = 卡面两维直读(费用过滤档 4/目标星级 2);
    键 ∈ 策略注册表且 id 对拍 plaza:202201。"""
    assert set(STRATEGY_BUY_STAR_FLIP_GRANTS) == {_CARD}, \
        '注册面 = 族现役首例'
    assert STRATEGY_BUY_STAR_FLIP_GRANTS[_CARD] == _ROW, \
        f'行值漂移: {STRATEGY_BUY_STAR_FLIP_GRANTS!r}'
    assert _CARD in INVESTMENT_STRATEGIES, '键必须在策略注册表'
    assert INVESTMENT_STRATEGIES[_CARD].source == 'plaza:202201', \
        '注册行 id 对拍(202201,改名/换 id 漂移哨现值通过)'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验①(孤儿哨):键不在策略注册表 → ValueError(import 即炸
    语义;直调校验函数锁同款行为)。"""
    monkeypatch.setitem(STRATEGY_BUY_STAR_FLIP_GRANTS, '不存在的卡', _ROW)
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_buy_star_flip_grants()


def test_validator_cost_domain_raises(monkeypatch) -> None:
    """构建校验②(费用档域哨):费用过滤档 ∉ 1..5 → ValueError(错档
    运行期 = 谓词静默永不匹配,无台账无失败行)。"""
    monkeypatch.setitem(STRATEGY_BUY_STAR_FLIP_GRANTS, _CARD, (0, 2))
    with pytest.raises(ValueError, match='费用档域'):
        _validate_strategy_buy_star_flip_grants()


def test_validator_target_star_domain_raises(monkeypatch) -> None:
    """构建校验③(目标星级域哨):目标 ∉ {2, 3} → ValueError(1 =
    「升到1星」自相矛盾,4+ 越游戏星级上限)。"""
    monkeypatch.setitem(STRATEGY_BUY_STAR_FLIP_GRANTS, _CARD, (4, 1))
    with pytest.raises(ValueError, match='目标星级域'):
        _validate_strategy_buy_star_flip_grants()


def test_validator_advisor_conflict_raises(monkeypatch) -> None:
    """构建校验④(顾问型冲突哨):键 = STRATEGY_GRANTS 顾问行
    (advisor=True)→ ValueError(顾问卡获得走特邀专家付费期权通道,
    普通购买过滤判据语义不适配,双登记 = 机制冲突防呆)。停云顾问 =
    顾问行现值成员,先验在册再入负控。"""
    assert getattr(STRATEGY_GRANTS.get('停云顾问'), 'advisor', False) is \
        True, '前置:停云顾问 = 顾问行现值成员'
    monkeypatch.setitem(STRATEGY_BUY_STAR_FLIP_GRANTS, '停云顾问', _ROW)
    with pytest.raises(ValueError, match='顾问型冲突'):
        _validate_strategy_buy_star_flip_grants()
