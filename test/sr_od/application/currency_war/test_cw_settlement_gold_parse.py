"""结算屏金面板解析回归锁(T-42 读端加固批)。

病理(2026-09-18 两实机局 journal+停局截图定谳):胜局结算页金面板
「存量 <N>」OCR 读失败率连续两局 100%(parse_settlement_assets 返 None
→ apply_settlement_cover gold=None),金真值只能靠边界闩窗吸收兜底。
加固 = 存量锚词与数值被 OCR 拆成相邻两 token 的分词形态兜底(同
parse_settlement_progress 的分离 token 先例);锚词缺失不猜(宁缺勿造
口径不变)。

锁依据 = parse_settlement_assets docstring 证据口径(「存量 <当前>」
= 当前金币;金币总览=本节点获得量,两者不可混取)。
"""
from __future__ import annotations

from sr_od.application.currency_war.obs.cw_settlement_obs import (
    parse_settlement_assets,
)


def test_same_token_form_regression() -> None:
    """存量与数值同 token(原形态回归):'存量：52' / '存量52' 两形都读。"""
    assert parse_settlement_assets(
        ['挑战成功', '存量：52', 'Lv.3'])['gold'] == 52
    assert parse_settlement_assets(
        ['挑战成功', '存量 47', 'Lv.3'])['gold'] == 47


def test_adjacent_token_form_fallback() -> None:
    """分词形态兜底:「存量」锚词 token 与纯数字 token 被拆成相邻两 token
    → 紧邻后随纯数字才取(锚词缺失/非纯数字不猜)。"""
    assert parse_settlement_assets(
        ['挑战成功', '存量', '52', 'Lv.3'])['gold'] == 52
    assert parse_settlement_assets(
        ['挑战成功', '存量：', '47', 'Lv.3'])['gold'] == 47
    # 下一 token 非纯数字(金币总览数值等)→ 不取,宁缺勿造。
    assert parse_settlement_assets(
        ['挑战成功', '存量', '金币总览', 'Lv.3'])['gold'] is None


def test_missing_anchor_stays_none() -> None:
    """锚词缺失(面板不在场/OCR 整段漏)→ None,不冒认(负例回归)。"""
    assert parse_settlement_assets(
        ['挑战成功', '小队生命值71', '连胜×0'])['gold'] is None
    assert parse_settlement_assets([])['gold'] is None
