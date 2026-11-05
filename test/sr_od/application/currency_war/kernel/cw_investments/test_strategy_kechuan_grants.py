"""策略卡完美通关穿戴 + 周期离场登记表测试(镜像 src = kernel/
cw_investments.py 的 STRATEGY_KECHUAN_WEAR_GRANTS / STRATEGY_KECHUAN_
LEAVE_GRANTS + 构建校验)。

测试面依据 = 迭代设计 designs/T-368-peipei-kechuan.md §9.2(v3.1,
2026-11-05 用户裁定 B 转正 + 穿戴/离场两效果条目真实建模;两表随本卡
立项,后继同形卡 +1 行复用;值域校验按 2026-10-28 治理判据不设——手抄
常量纯笔误类;孤儿键一哨全落,直构形态先例 =
test_strategy_boss_battle_grants.py / test_strategy_win_gold_grants.py):
- 穿戴表:行值 = (装备类别词, 件数),类别词 = roll_random_equip 采样
  参数语义(装备注册表类别)——与 STRATEGY_BOSS_BATTLE_GRANTS 表值同形
  异义(先例表 = 占席道具箱名前缀语义,消费端发箱),两表消费动作异构
  分表(设计稿 9.5-1 类别词两义申报);
- 离场表:行值 = 离场后继节点数(卡文「5个节点」直读),计数口径 =
  后继 N(拿卡节点不计入,人才激励/偶像经济延迟支线两在码刻度同口径);
- 镜像一致性:两表成员与登记面 STRATEGY_GRANTS['佩佩客串'] /
  cw_gain_effects._STRATEGY_CHAR_GRANTS['佩佩客串'] 同卡同名(登记面
  三处独立字面量的漂移唯此锁可暴露)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    _KECHUAN_UNIT_IDENTITY,
)
from sr_od.application.currency_war.kernel.cw_gain_effects import (
    _STRATEGY_CHAR_GRANTS,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_GRANTS,
    STRATEGY_KECHUAN_LEAVE_GRANTS,
    STRATEGY_KECHUAN_WEAR_GRANTS,
    _validate_strategy_kechuan_leave_grants,
    _validate_strategy_kechuan_wear_grants,
    equips_by_category,
)

_CARD = '佩佩客串'


def test_wear_registry_closed_set_and_row() -> None:
    """穿戴表登记面闭集 + 行值单一源:族现役首例佩佩客串(卡文「每完美
    通关一个战斗节点,佩佩就会穿戴一件进阶装备」→ (进阶, 1);禁顺手代
    登记,同族后续卡各自独立批);类别池非空(数据性质锁,池派生单一源 =
    equips_by_category 注册表派生);键 ∈ 策略注册表(孤儿哨现值通过 =
    import 过闸即证,显式对拍防静默漂移)。"""
    assert set(STRATEGY_KECHUAN_WEAR_GRANTS) == {_CARD}, \
        f'注册面漂移: {sorted(STRATEGY_KECHUAN_WEAR_GRANTS)!r}'
    assert STRATEGY_KECHUAN_WEAR_GRANTS[_CARD] == ('进阶', 1), \
        f'行值漂移(卡面明写每完美通关 1 件随机进阶): ' \
        f'{STRATEGY_KECHUAN_WEAR_GRANTS!r}'
    assert _CARD in INVESTMENT_STRATEGIES, '键必须在策略注册表'
    assert len(equips_by_category('进阶')) > 0, '进阶池必须非空(数据性质)'


def test_leave_registry_closed_set_and_row() -> None:
    """离场表登记面闭集 + 行值单一源:佩佩客串离场后继节点数 5(卡文
    「进入5个节点后」直读;后继 N 口径 = 拿卡节点不计入);键 ∈ 策略
    注册表(孤儿哨显式对拍)。"""
    assert set(STRATEGY_KECHUAN_LEAVE_GRANTS) == {_CARD}, \
        f'注册面漂移: {sorted(STRATEGY_KECHUAN_LEAVE_GRANTS)!r}'
    assert STRATEGY_KECHUAN_LEAVE_GRANTS[_CARD] == 5, \
        f'行值漂移(卡文「5个节点」直读): {STRATEGY_KECHUAN_LEAVE_GRANTS!r}'
    assert _CARD in INVESTMENT_STRATEGIES, '键必须在策略注册表'


def test_member_matches_registration_faces() -> None:
    """镜像一致性:两表成员卡与登记面同卡同名同发放对象——登记行
    chars_immediate = ('佩佩',)/工厂表 ('佩佩', 1)/触发身份常量三者
    对拍(卡面「佩佩闪亮登场…佩佩就会穿戴…接走佩佩们」同句同单位,
    多处独立字面量的漂移唯此锁可暴露;win 金计数单位同款纪律)。"""
    assert STRATEGY_GRANTS[_CARD].chars_immediate == (_KECHUAN_UNIT_IDENTITY,), \
        '登记行发放对象 = 佩佩'
    assert _STRATEGY_CHAR_GRANTS[_CARD] == (_KECHUAN_UNIT_IDENTITY, 1), \
        '工厂镜像行发放对象 = 佩佩×1'
    assert _KECHUAN_UNIT_IDENTITY == '佩佩'


def test_wear_validator_orphan_key_raises(monkeypatch) -> None:
    """穿戴表构建校验(孤儿哨):键不在策略注册表 → ValueError(import
    即炸语义;直调校验函数锁同款行为,防哨被再删)。"""
    monkeypatch.setitem(STRATEGY_KECHUAN_WEAR_GRANTS, '不存在的卡',
                        ('进阶', 1))
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_kechuan_wear_grants()


def test_leave_validator_orphan_key_raises(monkeypatch) -> None:
    """离场表构建校验(孤儿哨):键不在策略注册表 → ValueError(import
    即炸语义;直调校验函数锁同款行为,防哨被再删)。"""
    monkeypatch.setitem(STRATEGY_KECHUAN_LEAVE_GRANTS, '不存在的卡', 5)
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_kechuan_leave_grants()
