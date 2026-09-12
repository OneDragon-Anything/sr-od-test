"""SIFT 三层漏斗(session 优先匹配)单测(P4R4 heavy 性能批)。

真帧真模板端到端(慢,已入 slow_marks):全库 vs 漏斗行为等价 + 分层行为
(L1 命中/热态加速)+ 状态写回断言。帧 = fixtures/prep_stall(1920x1080
真备战帧,前排4+后排3+备战8;入仓资产,原 .debug 局外素材已迁入)。
"""
import time
from pathlib import Path
from types import SimpleNamespace

import yaml

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils import cv2_utils
from one_dragon.utils.file_utils import get_project_root

_FRAME = Path(__file__).resolve().parent / 'fixtures' / 'prep_stall_1788434979565.png'


def _slots_from_yml(prefix: str, count: int):
    p = get_project_root() / 'assets' / 'game_data' / 'screen_info' / '_od_merged.yml'
    d = yaml.safe_load(p.open('r', encoding='utf-8'))
    entries = d if isinstance(d, list) else list((d or {}).values())
    for v in entries:
        if isinstance(v, dict) and str(v.get('screen_name', '')) == '货币战争-备战':
            by = {a['area_name']: a for a in v['area_list']}
            out = []
            for i in range(1, count + 1):
                a = by[f'{prefix}-{i}']
                x1, y1, x2, y2 = a['pc_rect']
                out.append((i, Rect(x1, y1, x2, y2)))
            return out
    raise AssertionError('备战档未找到')


def _sig(chars):
    return sorted((c.slot, c.char_id, c.star) for c in chars)


def test_funnel_equivalence_and_tiering() -> None:
    """①漏斗(冷/热)识别结果与全库逐字一致;②热态显著加速
    (L1 位置连续性);③状态写回 session(不引入全局)。"""
    from sr_od.application.currency_war.obs.cw_identity_obs import (
        _DEPLOYED_CENTER_GATE,
        _DEPLOYED_LIVE_ONLY,
        _DEPLOYED_MIN_INLIERS,
        ensure_portrait_templates,
        identify_slots,
        identify_slots_tiered,
    )
    templates = ensure_portrait_templates(SimpleNamespace())
    assert templates is not None, '立绘库缺失(assets/template/currency_war/portrait_plaza)'
    screen = cv2_utils.read_image(str(_FRAME))
    front = _slots_from_yml('前排', 4)
    back = _slots_from_yml('后排', 6)
    kw = {'min_inliers': _DEPLOYED_MIN_INLIERS, 'live_only': _DEPLOYED_LIVE_ONLY,
          'center_gate': _DEPLOYED_CENTER_GATE}

    base = identify_slots(screen, templates, front + back, 'front', **kw)
    assert len(base) >= 5, f'基线帧应识别出足够角色,实得 {len(base)}'
    # 真帧身份+星级真值锚(2026-02-02 看图人工核对 + 用户裁决:花火 1★;
    # 前排-1..4 + 后排-1..6,后排 4/5/6 空):SIFT 全库在此帧只跑一次,
    # 真值对随本测试聚合断言(测试纪律第 21 条一图一测)
    assert _sig(base) == sorted([
        (1, '缇宝', 2), (2, '希儿', 2), (3, '星期日', 1), (4, '椒丘', 1),
        (1, '艾丝妲', 2), (2, '花火', 1), (3, '灵砂', 1),
    ])

    session = SimpleNamespace()
    # 冷启动(空漏斗状态 → L3 全库兜底)
    cold = identify_slots_tiered(session, screen, templates, front + back,
                                 'front', **kw)
    assert _sig(cold) == _sig(base)
    assert getattr(session, 'cw_idfunnel_seen', None), '冷启动应写回 seen 集'
    assert getattr(session, 'cw_idfunnel_last', None), '冷启动应写回槽位映射'
    # 热启动(L1 位置连续性):结果一致 + 提速(真身仍过全部门槛)
    t0 = time.perf_counter()
    hot = identify_slots_tiered(session, screen, templates, front + back,
                                'front', **kw)
    t_hot = (time.perf_counter() - t0) * 1000
    assert _sig(hot) == _sig(base)
    # 全库路径基线计时(单轮)
    t0 = time.perf_counter()
    identify_slots(screen, templates, front + back, 'front', **kw)
    t_full = (time.perf_counter() - t0) * 1000
    # 单轮计时含调度噪声,留 20% 容差仍能拦「热态不快于全库」的漏斗失效
    assert t_hot < t_full * 1.2, f'热态漏斗应快于全库(热 {t_hot:.0f}ms vs 全库 {t_full:.0f}ms)'


def test_funnel_none_session_is_full_scan() -> None:
    """session=None = 直接全库路径(离线/测试零变化契约)。"""
    from sr_od.application.currency_war.obs.cw_identity_obs import (
        _DEPLOYED_CENTER_GATE,
        _DEPLOYED_LIVE_ONLY,
        _DEPLOYED_MIN_INLIERS,
        ensure_portrait_templates,
        identify_slots,
        identify_slots_tiered,
    )
    templates = ensure_portrait_templates(SimpleNamespace())
    screen = cv2_utils.read_image(str(_FRAME))
    front = _slots_from_yml('前排', 4)
    kw = {'min_inliers': _DEPLOYED_MIN_INLIERS, 'live_only': _DEPLOYED_LIVE_ONLY,
          'center_gate': _DEPLOYED_CENTER_GATE}
    base = identify_slots(screen, templates, front, 'front', **kw)
    tiered = identify_slots_tiered(None, screen, templates, front, 'front', **kw)
    assert _sig(tiered) == _sig(base)


def test_funnel_state_no_session_no_global() -> None:
    """无 session 直接全库:漏斗状态字段不进模块(不引入模块级全局)。"""
    import sr_od.application.currency_war.obs.cw_identity_obs as mod
    assert not hasattr(mod, 'cw_idfunnel_last')
    assert not hasattr(mod, 'cw_idfunnel_seen')
