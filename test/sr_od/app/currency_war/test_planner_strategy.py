# -*- coding: utf-8 -*-
"""test_planner_strategy 主题锁。

2026-09-03 拆分归档批:自混合文件 test_cw_strategy_planner.py 按 member 拆回独立文件(纯移动,断言零改动;原合并文件消亡)。"""
from __future__ import annotations



import sys
from pathlib import Path as _test_planner_strategy_Path

sys.path.insert(0, 'src')
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

from sr_od.application.currency_war.kernel.cw_events import PlannerOption, decide_planner
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState as _test_planner_strategy_GameState

SHOT = r'.debug\sr_od_mcp\screenshot\screenshot_20260819_220156_428969.png'
# r104b fixtures(测试仓归档,与 .debug 解耦;局29 五态实拍)
FIX_DIR = _test_planner_strategy_Path(__file__).resolve().parents[4] / 'screens' / 'cw_planner'
FIX_EVENT = FIX_DIR / 'event_two_cards.webp'           # 事件态:左=破解芯片(弱化)/右=升费
FIX_EVENT_AGAIN = FIX_DIR / 'event_two_cards_again.webp'   # 二次事件态(内容同首次,未消费证)
FIX_DETAIL = FIX_DIR / 'detail_panel_open.webp'        # 详情面板态(点卡上半部触发)
FIX_SELECTED = FIX_DIR / 'card_selected_confirm_ready.webp'  # 选中态(右卡选中+确认亮)


def _ocr_cards(path: str) -> tuple[list[str], list[str]]:
    """离线复刻 handler 的 OCR 卡文字提取(左/右)——框架 OnnxOcrMatcher(模型路径自动解析)。

    实测(局29 存档画面):左=「使后续节点【弱化】，降低敌人属性。/破解芯片」、
    右=「提升费用至4费，变为1星银」——y 300-420 过滤带 + x<960 分流正确。
    """
    import cv2
    import numpy as np
    try:
        from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher
        m = OnnxOcrMatcher()
    except Exception:
        return [], []
    img = cv2.imdecode(np.fromfile(path, dtype='uint8'), cv2.IMREAD_COLOR)
    res = m.run_ocr(img)
    left, right = [], []
    LO, HI = 300, 420
    for t, mr in (res or {}).items():
        if mr.max is None:
            continue
        cy = mr.max.center.y
        cx = mr.max.center.x
        if LO <= cy <= HI and cx < 1750:   # 右侧详情面板数值列(1413+)不进卡文字
            (left if cx < 960 else right).append(t)
    return left, right


def test_planner_strategy_upgrade_wolf_line():
    """银狼线 ⇒ 升费档内升档(100+30=130,ADR-0524 档位语义)> 弱化档 55 → 选升费。"""
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    tgt = next(c for c in COMP_LIBRARY if c.name == '狼尊欢愉')
    st = _test_planner_strategy_GameState(hp=80)
    st.bench = [BenchChar(slot=1, char_id='银狼LV.999', faction='?', star=2, position_pref='front')]
    opts = [PlannerOption(idx=0, text='提升费用至4费,变为1星银狼'),
            PlannerOption(idx=1, text='使后续节点【弱化】,降低敌人属性。')]
    pick = decide_planner(opts, st, tgt)
    assert pick.idx == 0 and '升费' in pick.reason


def test_planner_strategy_weaken_low_hp():
    """非银狼线+银狼不在场 ⇒ 升费降档(100-60=40,ADR-0524 降档语义)< 弱化档 55 → 弱化。
    (原注释「弱化 55+20=75」的 +20 低血钩子已随 ADR-0519 C15 退役,弱化恒 55。)"""
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    tgt = next(c for c in COMP_LIBRARY if c.name == '反甲白厄')
    st = _test_planner_strategy_GameState(hp=30)
    st.bench = [BenchChar(slot=1, char_id='白厄', faction='?', star=1, position_pref='front')]
    opts = [PlannerOption(idx=0, text='提升费用至4费,变为1星银狼'),
            PlannerOption(idx=1, text='使后续节点【弱化】,降低敌人属性。')]
    pick = decide_planner(opts, st, tgt)
    assert pick.idx == 1, f'低血非银狼线应选弱化,实得 {pick.reason}'


def test_planner_strategy_both_equipment():
    """5费升2星:两卡全装备 → 装备分值定(非升费字样)。"""
    st = _test_planner_strategy_GameState(hp=60)
    opts = [PlannerOption(idx=0, text='火力风暴潮 进阶装备'),
            PlannerOption(idx=1, text='轮滑鞋 简易装备')]
    pick = decide_planner(opts, st, None)
    assert pick.reason.startswith('装备'), f'装备局 reason 应为装备,实得 {pick.reason}'


def test_planner_strategy_tier_order_and_key_equip():
    """三层档位定序锁(ADR-0524,16 号稿 §1.7):升费档 > 弱化档 > 装备档;
    key_equip +15 = 装备域内命中优先键(域内排前,不跨域压弱化档);
    银狼不在场降档(40)< 弱化档的层间关系即「降档」语义本体。"""
    from sr_od.application.currency_war.kernel.cw_comps import Comp
    st = _test_planner_strategy_GameState(hp=60)
    # 升费档 > 弱化档(无银狼线;bench 空 = 在场信息缺失 → 不降权,保守)
    opts = [PlannerOption(idx=0, text='使后续节点【弱化】,降低敌人属性。'),
            PlannerOption(idx=1, text='提升费用至4费,变为1星银狼')]
    pick = decide_planner(opts, st, None)
    assert pick.idx == 1 and '升费' in pick.reason, '升费档 > 弱化档'
    # key_equip 命中在装备域内排前(风暴潮 6+15 > 轮滑鞋 4)
    tgt = Comp(name='tk', factions=[], core_chars=[], form_tiers={}, strength='A',
               form_difficulty='medium', key_equips=['火力风暴潮'])
    opts2 = [PlannerOption(idx=0, text='轮滑鞋 简易装备'),
             PlannerOption(idx=1, text='火力风暴潮 进阶装备')]
    pick2 = decide_planner(opts2, st, tgt)
    assert pick2.idx == 1 and '+key_equip' in pick2.reason, f'key_equip 域内优先,实得 {pick2.reason}'
    # 装备档(21)不跨域压弱化档(55)
    opts3 = [PlannerOption(idx=0, text='火力风暴潮 进阶装备'),
             PlannerOption(idx=1, text='使后续节点【弱化】,降低敌人属性。')]
    pick3 = decide_planner(opts3, st, tgt)
    assert pick3.idx == 1, '弱化档 > 装备档(key_equip 命中不跨域)'


def test_planner_ocr_on_archive_shot():
    """存档画面(局29)选项识别:左右卡文字提取 + 策略结论=升费。
    OCR 模型不可用时 skip(环境限制)。"""
    left, right = _ocr_cards(SHOT)
    if not left and not right:
        import pytest
        pytest.skip('离线 OCR 模型不可用')
    ltxt, rtxt = ' '.join(left), ' '.join(right)
    # 局29 实测:升费在右卡
    assert '提升费用' in rtxt or '提升费用' in ltxt, f'升费卡应被识别: L={ltxt!r} R={rtxt!r}'
    assert '弱化' in (rtxt + ltxt), '弱化卡应被识别'
    opts = [PlannerOption(idx=0, text=ltxt), PlannerOption(idx=1, text=rtxt)]
    pick = decide_planner(opts, _test_planner_strategy_GameState(hp=80), None)
    assert '升费' in pick.reason
    assert pick.idx == (1 if '提升费用' in rtxt else 0), '选升费卡那侧'


def test_planner_fixtures_event_two_cards():
    """fixture:事件二卡态——左右卡文字识别正确(升费右/弱化左)+策略选右。"""
    if not FIX_EVENT.exists():
        import pytest
        pytest.skip('fixture 缺失')
    left, right = _ocr_cards(str(FIX_EVENT))
    if not left and not right:
        import pytest
        pytest.skip('离线 OCR 模型不可用')
    ltxt, rtxt = ' '.join(left), ' '.join(right)
    assert '提升费用' in rtxt, f'升费卡应在右: R={rtxt!r}'
    assert '弱化' in ltxt, f'弱化卡应在左: L={ltxt!r}'


def test_planner_fixtures_event_again_same_content():
    """fixture:二次事件态(23:27)——内容与首次一致(事件未消费的证据画面),
    识别结论应相同:识别链对该态稳定。"""
    if not FIX_EVENT_AGAIN.exists():
        import pytest
        pytest.skip('fixture 缺失')
    left, right = _ocr_cards(str(FIX_EVENT_AGAIN))
    if not left and not right:
        import pytest
        pytest.skip('离线 OCR 模型不可用')
    assert '提升费用' in ' '.join(right), '二次态升费卡仍识别'


def test_planner_fixtures_detail_panel_detectable():
    """fixture:详情面板态——handler 的 3b 分支依据「属性详情」OCR 检测;
    该态下卡文字应不可读(被面板盖)或面板标题可读,二者至少其一。"""
    if not FIX_DETAIL.exists():
        import pytest
        pytest.skip('fixture 缺失')
    import cv2
    import numpy as np
    try:
        from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher
        m = OnnxOcrMatcher()
    except Exception:
        import pytest
        pytest.skip('离线 OCR 模型不可用')
    img = cv2.imdecode(np.fromfile(str(FIX_DETAIL), np.uint8), cv2.IMREAD_COLOR)
    res = m.run_ocr(img)
    texts = ' '.join((res or {}).keys())
    assert '属性详情' in texts, '详情面板态应能检出「属性详情」(handler 3b 分支依据)'


def test_planner_fixtures_selected_confirm_ready():
    """fixture:选中态——右卡选中后「确认选择」按钮显影(x≈1440-1542,y≈584-615);
    佐证 CONFIRM 坐标(交互实锤):OCR 能在该区域读到「确认选择」。"""
    if not FIX_SELECTED.exists():
        import pytest
        pytest.skip('fixture 缺失')
    import cv2
    import numpy as np
    try:
        from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher
        m = OnnxOcrMatcher()
    except Exception:
        import pytest
        pytest.skip('离线 OCR 模型不可用')
    img = cv2.imdecode(np.fromfile(str(FIX_SELECTED), np.uint8), cv2.IMREAD_COLOR)
    res = m.run_ocr(img)
    hit = None
    for t, mr in (res or {}).items():
        if '确认选择' in t and mr.max is not None:
            hit = (t, mr.max.center.x, mr.max.center.y)
            break
    assert hit is not None, '选中态应有「确认选择」按钮可读'
    _t, cx, cy = hit
    assert 1400 <= cx <= 1580 and 570 <= cy <= 630, \
        f'确认按钮应在右侧偏下(实测 ({cx},{cy});handler CONFIRM=(1491,600))'
