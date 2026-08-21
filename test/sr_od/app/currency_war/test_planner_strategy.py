"""r104:策划事件选项识别 + decide_planner 策略测试(用局29 存档画面)。

存档画面:screenshot_20260819_220156(升费 vs 破解芯片态)——OCR 离线跑
analyze 同款链路(卡文字 y 过滤 + 左右分流),验证 decide_planner 选升费。
"""
import sys
from pathlib import Path

sys.path.insert(0, 'src')
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

from sr_od.application.currency_war.cw_events import PlannerOption, decide_planner
from sr_od.application.currency_war.cw_state import BenchChar, GameState

SHOT = r'.debug\sr_od_mcp\screenshot\screenshot_20260819_220156_428969.png'
# r104b fixtures(测试仓归档,与 .debug 解耦;局29 五态实拍)
FIX_DIR = Path(__file__).resolve().parents[4] / 'screens' / 'cw_planner'
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
    """银狼线:升费 100+30=130 > 弱化 55 → 选升费。"""
    from sr_od.application.currency_war.cw_comps import COMP_LIBRARY
    tgt = next(c for c in COMP_LIBRARY if c.name == '狼尊欢愉')
    st = GameState(hp=80)
    st.bench = [BenchChar(slot=1, char_id='银狼LV.999', faction='?', star=2, position_pref='front')]
    opts = [PlannerOption(idx=0, text='提升费用至4费,变为1星银狼'),
            PlannerOption(idx=1, text='使后续节点【弱化】,降低敌人属性。')]
    pick = decide_planner(opts, st, tgt)
    assert pick.idx == 0 and '升费' in pick.reason


def test_planner_strategy_weaken_low_hp():
    """非银狼线+银狼不在场+低血:升费 100-60=40 < 弱化 55+20=75 → 弱化。"""
    from sr_od.application.currency_war.cw_comps import COMP_LIBRARY
    tgt = next(c for c in COMP_LIBRARY if c.name == '反甲白厄')
    st = GameState(hp=30)
    st.bench = [BenchChar(slot=1, char_id='白厄', faction='?', star=1, position_pref='front')]
    opts = [PlannerOption(idx=0, text='提升费用至4费,变为1星银狼'),
            PlannerOption(idx=1, text='使后续节点【弱化】,降低敌人属性。')]
    pick = decide_planner(opts, st, tgt)
    assert pick.idx == 1, f'低血非银狼线应选弱化,实得 {pick.reason}'


def test_planner_strategy_both_equipment():
    """5费升2星:两卡全装备 → 装备分值定(非升费字样)。"""
    st = GameState(hp=60)
    opts = [PlannerOption(idx=0, text='火力风暴潮 进阶装备'),
            PlannerOption(idx=1, text='轮滑鞋 简易装备')]
    pick = decide_planner(opts, st, None)
    assert pick.reason.startswith('装备'), f'装备局 reason 应为装备,实得 {pick.reason}'


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
    pick = decide_planner(opts, GameState(hp=80), None)
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
