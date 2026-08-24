"""r279 退局 op 分支③测试(战斗中→暂停→撤退)。

画面档:货币战争-战斗暂停(新,2026-08-23 实证)。
"""
from __future__ import annotations

from sr_od.application.currency_war.operations.entry.exit_currency_war_match import (
    ExitCurrencyWarMatch,
)


def test_op_exists_and_named() -> None:
    assert ExitCurrencyWarMatch.STATUS_AT_LOBBY == '已返回货币战争大厅'


def test_battle_pause_screen_onboarded() -> None:
    """战斗暂停画面档存在(分支③的识别地基)。"""
    import yaml

    p = 'assets/game_data/screen_info/currency_war_battle_pause.yml'
    with open(p, encoding='utf-8') as f:
        d = yaml.safe_load(f)
    names = {a['area_name'] for a in d['area_list']}
    assert '标识-战斗暂停' in names
    assert '按钮-撤退' in names
    assert '按钮-继续战斗' in names


def test_retreat_branch_in_op() -> None:
    """op 源码含战斗暂停→撤退分支(r279 增补)。"""
    import inspect

    src = inspect.getsource(ExitCurrencyWarMatch.exit_match)
    assert '货币战争-战斗暂停' in src
    assert '按钮-撤退' in src
    assert '(1843, 42)' in src   # 战斗中右上角 X 实证坐标


def test_no_round_retry_tail() -> None:
    """战斗中不再落入 retry 死循环(旧版尾分支)。"""
    import inspect

    src = inspect.getsource(ExitCurrencyWarMatch.exit_match)
    assert 'round_retry' not in src.split('战斗中(未暂停态)')[0].split(
        '标识-战斗暂停')[0] or True   # r279 后 retry 移除,战斗中走 X
    assert 'round_retry' not in src, 'r279: 全分支消化,无 retry 尾'


# ===== W62 件3(ADR-0329):投资策略屏「左卡+确认」点击落地修复锁 =====


def test_invest_strategy_confirm_area_onboarded() -> None:
    """件3 画面档地基:投资策略屏「按钮-确认」area 建档且中心 ≈ 手动解锁点 (978,984)。

    修复依赖的定位源(screen_info area 中心)——area 缺失/漂移会让修复失效。
    """
    import yaml

    from one_dragon.base.geometry.rectangle import Rect

    p = 'assets/game_data/screen_info/currency_war_invest_strategy.yml'
    with open(p, encoding='utf-8') as f:
        d = yaml.safe_load(f)
    areas = {a['area_name']: a for a in d['area_list']}
    assert '按钮-确认' in areas, '投资策略屏应有「按钮-确认」area(件3 修复定位源)'
    assert '标识-请选择投资策略' in areas, 'r303b 分支识别锚'
    rect = Rect(*areas['按钮-确认']['pc_rect'])
    c = rect.center
    assert abs(c.x - 978) <= 2 and abs(c.y - 983) <= 2, (
        f'确认按钮中心应 ≈ (978,983)(手动解锁 (978,984)),实际 ({c.x:.0f},{c.y:.0f})')


def test_invest_strategy_branch_uses_area_center_not_ocr() -> None:
    """件3 修复锁:r303b 分支确认点击改用 area 中心(非全屏 OCR 搜「确认」)。

    旧 round_by_ocr_and_click 对 stylized 按钮静默失配 → 点不落地 → 卡行 748s;
    修复后与 HandleInvestStrategy 生产路径同源(area 中心 + bug#1 mouse_move)。
    """
    import inspect

    src = inspect.getsource(ExitCurrencyWarMatch.exit_match)
    # 分支仍在(r303b 语义:左卡+确认,未删)
    assert '标识-请选择投资策略' in src
    assert '左卡' in src
    # 确认点击走 area 定位:area_center(..., '按钮-确认', ...) + 兜底常量
    assert "area_center(self.ctx, '按钮-确认', '货币战争-投资策略')" in src
    assert 'Point(978, 983)' in src
    # 不再依赖全屏 OCR 搜「确认」点击(r303b 卡点根因;注释里的旧代码字样不算)
    branch = src.split('标识-请选择投资策略')[1].split('round_wait')[0]
    assert "self.round_by_ocr_and_click(scr2" not in branch
    assert "self.round_by_ocr_and_click(" not in branch
