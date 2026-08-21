"""r106 补测试:量子预囤路径 + 1.5 边界(此前一次调用返回 '' 是旧进程缓存,
重跑确认 1+0.5=1.5 边界通过)。"""
import sys

sys.path.insert(0, 'src')

from sr_od.application.currency_war.cw_transition import pick_framework


class BC:
    def __init__(self, n):
        self.char_id = n


class Card:
    def __init__(self, n):
        self.name = n


def test_quantum_hoard_boot_boundary():
    """量子 1 持有 + 1 在售 = 1.5 → 启动(浮点边界)。"""
    assert pick_framework([BC('希儿')], [], [Card('缇宝')]) == '量子'


def test_quantum_two_owned():
    assert pick_framework([BC('希儿'), BC('缇宝')], []) == '量子'


def test_xianzhou_beats_quantum_tie():
    """量子2 vs 仙舟2 平局 → 仙舟(dict 序主流先验,r102 审计③)。"""
    bench = [BC('希儿'), BC('缇宝'), BC('藿藿'), BC('丹恒·饮月')]
    assert pick_framework(bench, []) == '仙舟'
