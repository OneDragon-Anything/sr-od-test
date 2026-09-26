"""买入死库存防线 + dominance_buy 席位外部性否决的资格门单测。

出处与语义单一源:
- ``mandate.dead_stock_pair_buy_reject_reason``(方向②:G-S1 买侧
  对偶——非定向 1★ 买入禁制造同名 1★×2 死库存对,拒因键
  ``dead_stock_pair``);
- ``mandate.dominance_buy_eligible`` 的 ADR-0616 命题 4 收紧(bench_free
  ≤ 1 带席位外部性 fail-closed 否决,bench_free ≥ 2 域零干涉)。

锁的都是资格谓词的真值边界(设计意图),不锁任何分布数值。
"""
import pytest

from sr_od.application.currency_war.kernel.cw_game_state import BenchSlot, Unit
from sr_od.application.currency_war.strategies.impl.mandate_v1 import mandate


def _bench_char(char_id: str, star: int = 1, slot: int = 1) -> BenchSlot:
    """构造最小 bench 占席条目(容器形状;仅 char_id/star 参与判据;
    slot = 备战栏 1-based 物理槽,判据不消费)。"""
    return BenchSlot(kind='unit', unit=Unit(char_id=char_id, star=star))


class TestDeadStockPairBuyReject:
    """死库存买入防线:拒因键真值边界(逐 C 值一格,合并真值表)。"""

    def test_reject_reason_truth_table(self):
        """拒因真值表(七格并一):C=0 首张放行(买入后 C=1,单张全额
        可退零锁席);C=1 第二张拒(拒因键 dead_stock_pair,买入后成 ×2
        死对);C=2 第三张买入即满 3 自动合成 2★(消对)放行禁误伤;
        线内名(义务基座成员)同名对 = 合法合成素材任意 C 放行;辖星
        = 1,2★ 直出不成对恒放行;计数域 = bench∪deployed(deployed 域
        同名 1★ 同样构成 C=1);空名(装备/纯标签件无同名语义)放行
        防误伤。"""
        # C=0 首张放行
        bench = [_bench_char('阿格莱雅')]
        assert mandate.dead_stock_pair_buy_reject_reason(
            '缇宝', 1, bench, [], ()) == ''
        # C=1 第二张拒
        bench1 = [_bench_char('阿格莱雅'), _bench_char('缇宝')]
        deployed1 = [Unit(char_id='青雀', star=2)]
        assert mandate.dead_stock_pair_buy_reject_reason(
            '阿格莱雅', 1, bench1, deployed1, ()) == 'dead_stock_pair'
        # C=2 第三张(合成消对)放行
        bench2 = [_bench_char('阿格莱雅'), _bench_char('阿格莱雅')]
        assert mandate.dead_stock_pair_buy_reject_reason(
            '阿格莱雅', 1, bench2, [], ()) == ''
        # 线内名对放行
        k = ('停云',)
        bench_line = [_bench_char('停云')]
        assert mandate.dead_stock_pair_buy_reject_reason(
            '停云', 1, bench_line, [], k) == ''
        # 2★ 恒放行
        bench_star2 = [_bench_char('阿格莱雅', star=2)]
        assert mandate.dead_stock_pair_buy_reject_reason(
            '阿格莱雅', 2, bench_star2, [], ()) == ''
        # deployed 域计数
        deployed = [Unit(char_id='阿格莱雅', star=1)]
        assert mandate.dead_stock_pair_buy_reject_reason(
            '阿格莱雅', 1, [], deployed, ()) == 'dead_stock_pair'
        # 空名放行
        assert mandate.dead_stock_pair_buy_reject_reason(
            '', 1, [_bench_char('阿格莱雅')], [], ()) == ''


class TestDominanceBuyEligibleSeatBand:
    """ADR-0616 命题 4:dominance_buy 席位外部性否决带边界。

    支配论证锚(ADR-0611 换锚重写,mandate.dominance_buy_eligible
    docstring):1★ 全额退净成本 0 的金维支配性与 g*=10×cap_resolved
    参数化金位门不变,本组只锁席位维带界。
    """

    def test_seat_band_truth_table(self):
        """席位带真值表(四格并一):金 ≤ g* 恒不可发射(金维门原样,
        与席位维无关);V_slot>0 带(bench_free=1)fail-closed 否决;
        bench_free=0 原物理门语义保留(否决带含边界);bench_free ≥ 2
        域 P41② 支配论证原样有效零干涉(集成锁留 wiring 侧)。"""
        assert mandate.dominance_buy_eligible(30, 5, cap_resolved=4) is False
        assert mandate.dominance_buy_eligible(80, 1, cap_resolved=4) is False
        assert mandate.dominance_buy_eligible(80, 0, cap_resolved=4) is False

    @pytest.mark.parametrize('bench_free', [2])
    def test_bench_free_two_plus_untouched(self, bench_free: int):
        """bench_free ≥ 2 域:P41② 支配论证原样有效,零干涉(参数化
        收敛为带界代表值;带宽语义由谓词本体与集成锁承压)。"""
        assert mandate.dominance_buy_eligible(
            80, bench_free, cap_resolved=4) is True
