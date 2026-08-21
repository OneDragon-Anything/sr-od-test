"""r100e portal 偏置测试:概念股/邀请环境 → 框架计数偏置;可被来牌翻越。"""
import sys

sys.path.insert(0, 'src')

from sr_od.application.currency_war.cw_transition import pick_framework


class _BC:
    def __init__(self, char_id):
        self.char_id = char_id


class _Shop:
    def __init__(self, name):
        self.name = name


def test_portal_bias_train():
    """列车概念股环境 + 空持有 → 选列车(偏置 3 > 0)。"""
    fw = pick_framework([], [], shop=None, current='', portal='列车同行概念股')
    assert fw == '列车', '概念股应偏置列车框架'


def test_portal_bias_xianzhou():
    assert pick_framework([], [], portal='仙舟概念股') == '仙舟'


def test_portal_overridable_by_cards():
    """偏置可被实际来牌翻越:portal 列车 +3,但买到 4 张仙舟件 → 仙舟。"""
    fw = pick_framework(
        [_BC(n) for n in ('藿藿', '饮月', '爻光', '卡芙卡')], [],
        portal='列车同行概念股')
    assert fw == '仙舟', '4 张实际仙舟件应翻越 +3 偏置(非锁死)'


def test_portal_unrelated_no_bias():
    """无关环境(彩虹时代/火药味等)不偏置任何框架。"""
    assert pick_framework([], [], portal='彩虹时代') == ''
    assert pick_framework([], [], portal='火药味') == ''


def test_no_portal_unchanged():
    """无 portal → 原行为不变(全零返 '')。"""
    assert pick_framework([], []) == ''
