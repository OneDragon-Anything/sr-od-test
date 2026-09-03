"""shop_refresh 不变量「全未识别=不定」回归锁(观测自检框架设计 §2.5)。

背景:生产不变量比较的退化解——某局 5/5 牌全未识别时,刷前刷后同为
``['', '', '', '', '']``,集合相等会被误读成「刷新未生效」→ 假阳性停线。
生产判据 :func:`refresh_effective` 任一侧含未识别槽('')即返 None
(cw_op_buy_cards.py:200-204,单一源),写入端只认 ``is False`` 落票
(同文件 :894-897),故该形态在生产不可达——本锁钉住防回流。
真值表其余用例单一源 = test_cw_shop_refresh.py::test_refresh_effective_truth_table
(单槽 ''/空列表彼处已有;本文件只补「全未识别 5/5」形态,勿重复铺开;
字母占位桩禁用——2026-09-03 实证其随测试泄漏曾被误判实机停线)。
"""
from sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards import (
    refresh_effective,
)


def test_all_unrecognized_shop_is_indeterminate() -> None:
    """5/5 全未识别(全空串)→ 不定(None),不得判「未生效」。"""
    assert refresh_effective(['', '', '', '', ''],
                             ['', '', '', '', '']) is None
