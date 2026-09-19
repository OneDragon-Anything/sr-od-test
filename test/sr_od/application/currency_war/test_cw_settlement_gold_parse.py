"""结算屏金面板解析回归锁(T-42 读端加固批)。

病理(2026-09-18 两实机局 journal+停局截图定谳):胜局结算页金面板
「存量 <N>」OCR 读失败率连续两局 100%(parse_settlement_assets 返 None
→ apply_settlement_cover gold=None),金真值只能靠边界闩窗吸收兜底。
加固 = 存量锚词与数值被 OCR 拆成相邻两 token 的分词形态兜底(同
parse_settlement_progress 的分离 token 先例);锚词缺失不猜(宁缺勿造
口径不变)。

锁依据 = parse_settlement_assets docstring 证据口径(「存量 <当前>」
= 当前金币;金币总览=本节点获得量,两者不可混取)。

定点读数(read_settle_gold_opt)= 真值入口主路径:当前版本结算布局
无「存量」token(2026-09-18 结算帧亲读实证),战后金真值挂右上角货币
计数;本文件锁其「不猜」契约(area 缺失/越界/异常 → None)与稳定门
取末帧语义(纪律单一源 = cw_observation.read_gold_settled)。
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from one_dragon.base.geometry.rectangle import Rect

import sr_od.application.currency_war.obs.cw_settlement_obs as settle_mod
from sr_od.application.currency_war.obs.cw_settlement_obs import (
    parse_settlement_assets,
    read_settle_gold_opt,
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


# ===== 定点读数 read_settle_gold_opt(真值入口主路径)=====

def _stub_ctx(ocr_values: list, controller=None) -> SimpleNamespace:
    """最小 ctx 桩:ocr_service 依次弹出 ocr_values;controller 缺省 None
    (无稳定门,单帧读即全部能力——与生产离线/单测分支同形)。"""
    calls = {'n': 0}

    def _ocr(**k):
        v = ocr_values[min(calls['n'], len(ocr_values) - 1)]
        calls['n'] += 1
        return [SimpleNamespace(data=v)]

    return SimpleNamespace(ocr_service=SimpleNamespace(
        get_ocr_result_list=_ocr), controller=controller)


def test_settle_gold_reader_basics(monkeypatch) -> None:
    """「不猜」契约四态:area 缺失 / OCR 越界 / 帧不可下标 → None;
    正常读数 → int。"""
    frame = np.zeros((40, 100, 3), dtype=np.uint8)
    # area 缺失(screen_info 无该 area)→ None,连 OCR 都不碰。
    monkeypatch.setattr(settle_mod, '_area_rect', lambda *a, **k: None)
    assert read_settle_gold_opt(_stub_ctx(['11']), frame) is None
    # area 在场 + 读数越界(>GOLD_MAX)→ None 不冒认。
    monkeypatch.setattr(settle_mod, '_area_rect',
                        lambda *a, **k: Rect(0, 0, 100, 40))
    assert read_settle_gold_opt(_stub_ctx(['9999']), frame) is None
    # 正常读数。
    assert read_settle_gold_opt(_stub_ctx(['11']), frame) == 11
    # 帧不可下标(观测面异常,如 battle_wait 测试的帧哨兵)→ None 不毒化。
    monkeypatch.setattr(settle_mod, '_area_rect',
                        lambda *a, **k: Rect(0, 0, 100, 40))
    assert read_settle_gold_opt(_stub_ctx(['11']), object()) is None


def test_settle_gold_reader_gate_takes_last(monkeypatch) -> None:
    """稳定门:帧间不一致(计数器入账滚动中)取末帧 = 入账后真值;
    帧间一致即采信(零额外成本)。"""
    monkeypatch.setattr(settle_mod, 'SETTLE_GOLD_INTERVAL_S', 0)
    monkeypatch.setattr(settle_mod, '_area_rect',
                        lambda *a, **k: Rect(0, 0, 100, 40))
    frame = np.zeros((40, 100, 3), dtype=np.uint8)
    ctl = SimpleNamespace(screenshot=lambda: frame)
    # 9 → 13 不一致:采末帧 13(165656 局实证形态:结算展示期仍在入账)。
    assert read_settle_gold_opt(_stub_ctx(['9', '13'], ctl), frame) == 13
    # 9 → 9 一致:即采信,不耗满补采。
    assert read_settle_gold_opt(_stub_ctx(['9', '9'], ctl), frame) == 9
