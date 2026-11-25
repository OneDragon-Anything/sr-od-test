"""穿戴装备小图标读链（``cw_equipment.read_equipped_below``）回归。

锁的设计约定：历史正常帧不回退——10 张 ``equipped_*`` 整帧样本按已入库模板名单的读数与改前逐格相同。
命中判据（峰分 + 峰尖锐度两道门，标定依据见 src cw_equipment.py「穿戴装备识别」常量区块注释）不在
本文件的断言范围内。

模板从主仓 ``assets/template/currency_war/equip_plaza`` 现读并按下方写死的已入库名单过滤——目录里其余
png 是他批在飞件，否定断言对每张模板都敏感。缺样本 / 缺模板 → skip。
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils import cv2_utils
from one_dragon.utils.file_utils import get_project_root
from sr_od.application.currency_war.obs import cw_equipment as ce
from sr_od.application.currency_war.obs.cw_identity_obs import avatar_to_below

_SCREEN_NAME = '货币战争-备战'
_SCREEN_DIR = '货币战争-备战'

#: 已入库模板名单 = ``git -c core.quotepath=false ls-files assets/template/currency_war/equip_plaza``
#: （定稿时 52 个）。后续入库的模板要补进来。
_TRACKED_TMPL: tuple[str, ...] = (
    '以太钻头', '信心注入器', '光能电池', '光能盾牌', '光速螺旋桨', '冷笑话引擎', '击破星徽', '动能激发剑',
    '反卫星狙击枪', '反重力皮靴', '和平手枪', '垃圾袋', '天基轨道炮', '幸运星', '很硬的甲', '战场进化手册',
    '折叠小刀', '持续伤害星徽', '掩体生成枪', '斩首行动', '星间旅人星徽', '杀红眼', '欢愉星徽', '武器大师',
    '永动机', '治疗星徽', '流星飞翼', '火力风暴潮', '热血沸腾拳', '物质分解液', '生命之环', '生命之花',
    '电磁弹射器', '痛觉阻断芯片', '碎星斩舰刀', '红钻', '绝对热量', '群攻星徽', '胜利之旗', '能量星徽',
    '蓄能帆', '蓝钻', '虫洞掘进钻头', '行星钻地弹', '财富宝钻', '轮滑鞋', '追击星徽', '追逐星辰',
    '量产型装甲', '闪光手榴弹', '随便骰子', '高周波电锯',
)

#: ``equipped_*`` 整帧样本 → 期望读数 = 改前读数（按已入库名单）；未列出的槽位都不在返回里。
#: 前排 3 号位 / 后排 3 号位的「星核猎手星徽」模板未入库，按名单滤掉后读空。
_EQUIPPED_EXPECT: dict[str, dict[str, list[str]]] = {
    'equipped_front1_feixiao_0': {'F2': ['光能电池'], 'F4': ['治疗星徽']},
    'equipped_front1_feixiao_1': {'F2': ['光能电池'], 'F4': ['治疗星徽']},
    'equipped_front1_feixiao_2': {'F2': ['光能电池'], 'F4': ['治疗星徽']},
    'equipped_front1_feixiao_synth': {'F2': ['光能电池'], 'F4': ['治疗星徽']},
    'equipped_front1_feixiao_3': {'F1': ['光能电池'], 'F4': ['治疗星徽']},
    'equipped_back1_feixiao_2': {'F2': ['光能电池'], 'F4': ['治疗星徽']},
    'equipped_back1_feixiao_3': {'B1': ['光能电池'], 'F4': ['治疗星徽']},
    'equipped_back4_feixiao_3': {'B4': ['光能电池'], 'F4': ['治疗星徽']},
    'equipped_back6_feixiao_3': {'B5': ['治疗星徽'], 'B6': ['光能电池']},
    'equipped_back_235': {'B2': ['光能电池'], 'B5': ['治疗星徽']},
}

_SLOT_KINDS: tuple[tuple[str, str, int], ...] = (('F', '前排', 4), ('B', '后排', 6), ('Z', '备战栏', 9))


def _screens_dir() -> Path:
    return get_project_root() / 'sr-od-test' / 'screens' / _SCREEN_DIR


def _load(name: str) -> object | None:
    for suffix in ('.webp', '.png'):
        f = _screens_dir() / f'{name}{suffix}'
        if f.is_file():
            return cv2_utils.read_image(str(f))
    return None


@pytest.fixture(scope='module')
def tmpl_grays() -> dict[str, object]:
    """52 张模板的解码 + 灰度转换整模块只做一次，全部样本共用。"""
    base = get_project_root() / 'assets' / 'template' / 'currency_war' / 'equip_plaza'
    if not base.is_dir():
        pytest.skip('装备模板目录缺失')
    grays = ce.load_equip_tm_grays(base)
    return {n: g for n, g in grays.items() if n in _TRACKED_TMPL}


@pytest.fixture(autouse=True)
def _stub_cw_io(monkeypatch: pytest.MonkeyPatch) -> None:
    """读链只记日志 / 截图名；打桩保证测试零真实副作用。"""
    monkeypatch.setattr(ce, 'cw_log', lambda *args, **kwargs: None)
    monkeypatch.setattr(ce, 'cw_shot', lambda image, name: name)


def _slot_rects() -> list[tuple[str, Rect]]:
    """备战画面 19 个槽位的 below-avatar 搜索区（画面档 → 头像 rect → ``avatar_to_below``）。"""
    merged = get_project_root() / 'assets' / 'game_data' / 'screen_info' / '_od_merged.yml'
    data = yaml.safe_load(merged.read_text(encoding='utf-8'))
    screen = next(s for s in data if s.get('screen_name') == _SCREEN_NAME)
    areas = {a['area_name']: a['pc_rect'] for a in screen['area_list'] if 'pc_rect' in a}
    return [(f'{k}{i}', avatar_to_below(Rect(*areas[f'{prefix}-{i}'])))
            for k, prefix, count in _SLOT_KINDS for i in range(1, count + 1)]


@pytest.mark.parametrize('name', sorted(_EQUIPPED_EXPECT))
def test_equipped_frames_no_regression(name: str, tmpl_grays: dict[str, object]) -> None:
    img = _load(name)
    if img is None:
        pytest.skip(f'样本缺失 {name}')
    rects = [(key, rect) for key, rect in _slot_rects()]
    out = ce.read_equipped_below(img, tmpl_grays, rects)
    assert out == _EQUIPPED_EXPECT[name], name
