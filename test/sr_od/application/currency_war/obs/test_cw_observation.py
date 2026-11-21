"""read_shop_cards 试用形态分流测试(灰带闭环 + 正常亮度试用形态)。

锁的设计约定(试用形态识别批,证据 fixture 见 sr-od-test/screens/
货币战争-备战-开商店/ 目录):
- 「试用」标签检查对内容亮度域(≥50)无条件执行——同一试用形态有灰暗化
  (亮度落 50-60 灰带)与正常亮度(≥60)两种渲染,标签是唯一跨形态判别:
  灰带 + 标签命中 → trial=True 放行既有 SIFT 链(试用景元灰带帧);
  正常亮度 + 标签命中 → trial=True(正常亮度试用四连帧,四卡同帧);
  灰带无标签 → 维持 unknown 不猜(防线不放松,放行仅限标签确证的
  试用形态);
- TM 阈值下界样本:preview_star 帧槽5 标签 TM=0.750(跨卡渲染方差最低
  实测点,阈值 0.68 上方)仍须命中——标签底为半透明,透出卡面背景致
  底色随卡浮动,阈值依据见 cw_observation 形态裁决注释;
- extras 序列化(_shop_slots_to_json)透传 trial 键(MCP agent 消费面)。

fixture = 同目录「试用景元灰带帧.webp」(第六跑停机现场:槽5 试用景元,
亮度 52.4)+「标签抹除合成」帧(标签区替换为其自身均值色平面:全槽亮度
不变保持灰带、标签 TM 确定 miss、SIFT 本可识别——构造「灰带无标签」
目标形态)+「正常亮度试用四连帧.webp」(槽1 正卡飞霄 + 槽2-5 试用乱破/
托帕&账账/赛飞儿/忘归人,亮度 87-112)。

识别层依赖经 monkeypatch 打桩(area rect 查表 / 模板真加载 / 遥测
record_defect 缺省 no-op 零副作用);收起识别标志门经假全帧 OCR token
直过(同源判定路径,二值化重判分支不触发)。
"""

import types

import cv2
import numpy as np
import pytest

from sr_od.application.currency_war.obs import cw_observation as obs
from sr_od.application.currency_war.obs.recognizers.shop_open_recognizer import (
    _shop_slots_to_json,
)

#: screen_info「货币战争-备战-开商店」商店牌区 rect(建档坐标,fixture 全帧同坐标系)
_RECTS = {
    '商店牌-1': (377, 70, 605, 260), '商店牌-2': (646, 70, 874, 260),
    '商店牌-3': (914, 70, 1142, 260), '商店牌-4': (1183, 70, 1411, 260),
    '商店牌-5': (1452, 70, 1680, 260),
    '商店牌-1-费用': (536, 284, 605, 322), '商店牌-2-费用': (805, 284, 873, 322),
    '商店牌-3-费用': (1074, 284, 1142, 322), '商店牌-4-费用': (1343, 284, 1411, 322),
    '商店牌-5-费用': (1611, 284, 1680, 322),
}

#: 收起识别标志假全帧 OCR token(bbox 中心落在「按钮-收起」rect 内)
_FAKE_FULL_OCR = [types.SimpleNamespace(
    data='收起', x=1598, y=967, w=47, h=27)]

_FIXTURE_DIR = ('screens', '货币战争-备战-开商店')


@pytest.fixture(scope='module')
def trial_frame(request) -> np.ndarray:
    """存证帧全帧(RGB;读盘一次供本模块共用)。"""
    from one_dragon.utils.file_utils import get_project_root
    p = get_project_root() / 'sr-od-test' / _FIXTURE_DIR[0] / _FIXTURE_DIR[1] \
        / '试用景元灰带帧.webp'
    img = cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
    assert img is not None, f'fixture 缺失: {p}'
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


@pytest.fixture(scope='module')
def synth_no_badge_frame(request) -> np.ndarray:
    """标签抹除合成帧全帧(RGB;读盘一次供本模块共用)。"""
    from one_dragon.utils.file_utils import get_project_root
    p = get_project_root() / 'sr-od-test' / _FIXTURE_DIR[0] / _FIXTURE_DIR[1] \
        / '试用景元灰带帧-标签抹除合成.webp'
    img = cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
    assert img is not None, f'fixture 缺失: {p}'
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


@pytest.fixture(scope='module')
def bright_trial_frame(request) -> np.ndarray:
    """正常亮度试用四连帧全帧(RGB;读盘一次供本模块共用)。"""
    from one_dragon.utils.file_utils import get_project_root
    p = get_project_root() / 'sr-od-test' / _FIXTURE_DIR[0] / _FIXTURE_DIR[1] \
        / '正常亮度试用四连帧.webp'
    img = cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
    assert img is not None, f'fixture 缺失: {p}'
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


@pytest.fixture(scope='module')
def portrait_templates(request) -> dict:
    """角色立绘模板(贵加载,本模块只算一次)。"""
    from one_dragon.utils.file_utils import get_project_root
    from sr_od.application.currency_war.obs.currency_war_char_id import (
        load_avatar_templates,
    )
    return load_avatar_templates(
        get_project_root() / 'assets' / 'template' / 'currency_war'
        / 'character_avatar')


def _stub_read_chain(monkeypatch, templates: dict) -> None:
    """读链依赖打桩:area rect 查表 / 模板注入 / 局外 game state None。"""
    monkeypatch.setattr(obs, '_area_rect',
                        lambda ctx, name, screen=None: types.SimpleNamespace(
                            x1=_RECTS[name][0], y1=_RECTS[name][1],
                            x2=_RECTS[name][2], y2=_RECTS[name][3])
                        if name in _RECTS else None)
    monkeypatch.setattr(obs, 'ensure_portrait_templates',
                        lambda ctx: templates)
    monkeypatch.setattr(obs, 'game_state_from_ctx', lambda ctx: None)


def _fake_ctx(frame: np.ndarray) -> types.SimpleNamespace:
    """最小 ctx:收起识别标志画面档 + 截屏恒返当前帧(稳定门重读同帧)。"""
    collapse = types.SimpleNamespace(
        area_name='按钮-收起', text='收起',
        rect=types.SimpleNamespace(x1=1599, y1=967, x2=1646, y2=994))
    si = types.SimpleNamespace(area_list=[collapse])
    return types.SimpleNamespace(
        screen_loader=types.SimpleNamespace(get_screen=lambda name: si),
        controller=types.SimpleNamespace(
            screenshot=lambda: (0.0, frame)))


def test_trial_card_grayband_recognized_with_badge(
        monkeypatch, trial_frame, portrait_templates) -> None:
    """灰带 + 试用标签 → content(name=景元, trial=True);空槽维持 empty。"""
    _stub_read_chain(monkeypatch, portrait_templates)
    slots = obs.read_shop_cards(_fake_ctx(trial_frame), trial_frame,
                                full_ocr=_FAKE_FULL_OCR)
    assert slots is not None
    kinds = [s.kind for s in slots]
    assert kinds == ['empty', 'empty', 'empty', 'empty', 'content']
    card = slots[4].card
    assert card is not None
    assert card.name == '景元'
    assert card.trial is True
    assert card.slot == 5


def test_grayband_without_badge_stays_unknown(
        monkeypatch, synth_no_badge_frame, portrait_templates) -> None:
    """灰带无标签 → unknown(防线不放松;标签是放行唯一依据)。"""
    _stub_read_chain(monkeypatch, portrait_templates)
    slots = obs.read_shop_cards(_fake_ctx(synth_no_badge_frame),
                                synth_no_badge_frame,
                                full_ocr=_FAKE_FULL_OCR)
    assert slots is not None
    assert slots[4].kind == 'unknown'
    assert slots[4].card is None


def test_brightness_trial_cards_flagged_by_badge(
        monkeypatch, bright_trial_frame, portrait_templates) -> None:
    """正常亮度(≥60)试用形态 ×4 → trial=True,正卡 trial=False。

    锁「标签检查对内容亮度域无条件执行」:四张试用卡亮度 87-112 不落
    灰带,标签命中必须照标 trial(旧逻辑亮度门把标签检查锁在灰带分支内,
    正常亮度试用卡恒 trial=false——缺陷现场回归)。
    费用徽章读取打桩(本帧槽4 字形模板分类不出,慢路 OCR 需真引擎;
    费用链非本测试锁点,真值由真帧探查与 analyze 端到端辖)。"""
    _stub_read_chain(monkeypatch, portrait_templates)
    monkeypatch.setattr(obs, 'read_shop_card_cost',
                        lambda ctx, screen, slot: None)
    slots = obs.read_shop_cards(_fake_ctx(bright_trial_frame),
                                bright_trial_frame,
                                full_ocr=_FAKE_FULL_OCR)
    assert slots is not None
    kinds = [s.kind for s in slots]
    assert kinds == ['content'] * 5
    trials = [s.card.trial for s in slots]
    assert trials == [False, True, True, True, True]
    names = [s.card.name for s in slots]
    assert names == ['飞霄', '乱破', '托帕&账账', '赛飞儿', '忘归人']


def test_trial_badge_lowest_variance_sample_still_hits(
        bright_trial_frame) -> None:
    """TM 阈值下界样本(preview_star 帧槽5 标签 TM≈0.750)仍命中。

    纯 CV 快路径,不跑 SIFT:跨卡标签渲染方差最低实测点在阈值 0.68
    上方,防未来阈值回调把边界样本切掉(阈值依据 =
    cw_observation 形态裁决注释)。"""
    from one_dragon.utils.file_utils import get_project_root
    p = get_project_root() / 'sr-od-test' / _FIXTURE_DIR[0] / _FIXTURE_DIR[1] \
        / 'shop_open_preview_star.webp'
    img = cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
    assert img is not None, f'fixture 缺失: {p}'
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    x1, y1, x2, y2 = _RECTS['商店牌-5']
    assert obs._trial_badge_hit_in_crop(rgb[y1:y2, x1:x2]) is True


def test_shop_slots_to_json_carries_trial(monkeypatch) -> None:
    """extras 序列化透传 trial 键(MCP agent 消费面)。"""
    card = obs.ShopCard(x=1566, slot=5, faction='云上五骁', name='景元',
                        cost=1, star=1, cost_source='roster_fallback',
                        trial=True)
    out = _shop_slots_to_json([types.SimpleNamespace(
        kind='content', card=card)])
    assert out[0]['card']['trial'] is True
    no_trial = _shop_slots_to_json([types.SimpleNamespace(
        kind='content',
        card=obs.ShopCard(x=100, slot=1, faction='仙舟舰队', name='桂乃芬'))])
    assert no_trial[0]['card']['trial'] is False
