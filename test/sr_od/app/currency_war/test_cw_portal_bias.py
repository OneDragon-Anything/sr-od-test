"""r100e portal 偏置测试:概念股/邀请环境 → 框架计数偏置;可被来牌翻越。

出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
import sys

sys.path.insert(0, 'src')

from sr_od.application.currency_war.kernel.cw_transition import pick_framework


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


def test_early_cards_count_selects_framework():
    """早期计数(迁自 test_cw_quantum_hoard 前身 test_quantum_not_early_without_cards
    的残余有效断言):无 portal 时按实际持有计框架——2 张仙舟件即达阈值
    选仙舟;量子配方 3 费出得晚,早期持有计数起不来,自然不选量子
    (空持有 + 无关 portal 返 '' 由 test_portal_unrelated_no_bias 辖定)。"""
    assert pick_framework([_BC('藿藿'), _BC('丹恒·饮月')], []) == '仙舟'
