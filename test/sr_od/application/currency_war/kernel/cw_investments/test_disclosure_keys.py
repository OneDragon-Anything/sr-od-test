"""cw_investments 披露键常量域测试(镜像 src = kernel/cw_investments.py,
按拆目录规范落位):披露键 = 纯声明态常量,不进任何判定分支——锁存在性
与值形(全元组精确比对,披露键静态在册断言家族形),防「常量被静默删
改」;删除即红,提示删除者先清披露语义再动键。"""

from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_HIRING_LETTER_UNMODELED_ASSUMPTION_KEYS,
)


def test_hiring_letter_unmodeled_keys_registered() -> None:
    """披露键静态常量在册断言(聘用书授予族道具腿零建模申报,键 = 族卡
    名):首卡招聘资金在列。家族随族卡实现批追加(招聘资金+/专家招募/
    专家招募+ 各自批并入元组),本断言随批扩员——申报面扩员即红一次,
    批内顺手更新即绿。"""
    assert STRATEGY_HIRING_LETTER_UNMODELED_ASSUMPTION_KEYS == (
        '招聘资金',
    )
