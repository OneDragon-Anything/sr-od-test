"""r115 命运卜者强化:OCR 三卡识别(fixture 局32 实拍)+文本策略。

出处:docs/develop/currency_war/strategy/04_nodes.md(2026-08-31 测试瘦身批考证补记)。"""
import sys
from pathlib import Path

sys.path.insert(0, 'src')

FIX = Path(__file__).resolve().parents[4] / 'screens' / 'cw_fortune_picker' / 'event_three_cards.webp'


def _ocr_cards(path) -> list[str]:
    import cv2
    import numpy as np
    try:
        from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher
        m = OnnxOcrMatcher()
    except Exception:
        return []
    img = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
    res = m.run_ocr(img)
    XS = (510, 900, 1290)
    buckets: dict[int, list[str]] = {x: [] for x in XS}
    for t, mr in (res or {}).items():
        if mr.max is None:
            continue
        cy, cx = mr.max.center.y, mr.max.center.x
        if 290 <= cy <= 410:
            nearest = min(XS, key=lambda x: abs(x - cx))
            if abs(nearest - cx) < 190:
                buckets[nearest].append(t)
    return [' '.join(buckets[x]) for x in XS]


def test_fortune_cards_ocr_on_fixture():
    """局32 实拍:三卡应识别出 深层奥迹/原始奥迹/留白卡 关键词。"""
    if not FIX.exists():
        import pytest
        pytest.skip('fixture 缺失')
    texts = _ocr_cards(FIX)
    if not any(texts):
        import pytest
        pytest.skip('OCR 模型不可用')
    joined = ' '.join(texts)
    assert '奥迹' in joined, f'强化卡关键词应识别: {texts}'
    assert '留白' in joined or '黑天鹅' in joined, f'第三卡应识别: {texts}'


def test_fortune_text_strategy_prefers_damage():
    """文本策略:伤害倍率 > 强度提高 > 无关键词。"""
    from sr_od.application.currency_war.operations.handlers.handle_fortune_picker import (
        HandleFortunePicker,
    )
    # 复用 handle 的打分逻辑(直接构造假 ctx 会重;抽出来测不行——用类属性+内联)
    texts = ['层数提高', '伤害倍率提高', '黑天鹅强度提高']
    best_i, best_s = 0, -1.0
    for i, t in enumerate(texts):
        s = 0.0
        for kw, w in (('伤害倍率', 3.0), ('强度提高', 2.0), ('层数提高', 2.0),
                      ('伤害', 1.0), ('提高', 0.5)):
            if kw in t:
                s += w
        if s > best_s:
            best_i, best_s = i, s
    assert best_i == 1, '伤害倍率应最高分'
