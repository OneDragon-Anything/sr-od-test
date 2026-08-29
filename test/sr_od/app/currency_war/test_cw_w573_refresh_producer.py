# -*- coding: utf-8 -*-
"""刷新期望 producer 接线锁。

锁两层:
1. 源码锁——shop.py 刷新波集成的接线不变量(契约单一源=prep_director.
   build_refresh_expect docstring;源码锁先例=test_cw_w564_shop_wire 的
   test_shop_pool_wire_source_locks):
   - 惰性 import 契约件(防改回模块级硬 import 触发循环依赖);
   - 期望构建用裸 ``state.shop_refresh_cost``(None 口径;波内花销账的
     ``or 2`` 只许存在于 _refresh_fee 花销行,不进期望);
   - 消费段 kind=refresh_expect_mismatch 落台账(surface='shop');
   - 金腿读数用 read_gold_opt(None 口径,非 stylized read_gold)。
2. 行为冒烟——按接线同款调用形态走一遍 纯函数链(build_refresh_expect →
   refresh_reconcile_mismatches),锁「波前现读元组 → 期望 → 判据」的形状
   不漂移(纯函数本体真值表归 W564 17 锁,此处不重复)。

op 级行为锁(两帧一致门/op 生命期 mock)欠账:测试基建不存在,登记进度树
待后续批补;本文件只锁接线与形状。
"""

from pathlib import Path

from sr_od.application.currency_war.prep_director import (
    build_refresh_expect,
    refresh_reconcile_mismatches,
)
from sr_od.application.currency_war.cw_state import ShopCard

_SHOP_PATH = (Path(__file__).resolve().parents[5] / 'src' / 'sr_od'
              / 'application' / 'currency_war' / 'operations' / 'prep'
              / 'shop.py')


def _shop_source() -> str:
    return _SHOP_PATH.read_text(encoding='utf-8')


class TestW573RefreshProducerSourceLocks:
    """刷新波集成接线不变量(源码锁,防 None 口径回流/硬 import 回流)。"""

    def test_lazy_import_contract_functions(self):
        """契约件必须惰性 import(模块级硬 import = 循环依赖回归)。"""
        src = _shop_source()
        assert 'from sr_od.application.currency_war.prep_director import' in src
        assert 'build_refresh_expect' in src
        assert 'refresh_reconcile_mismatches' in src

    def test_expect_uses_raw_refresh_cost(self):
        """期望构建必须传裸 state.shop_refresh_cost(None 口径)。

        波内花销账允许 ``or 2``(既有 _refresh_fee 行),但期望调用的
        实参必须是裸值——本锁钉住调用形参形状。
        """
        src = _shop_source()
        assert 'build_refresh_expect(\n                            _pre_gold, state.shop_refresh_cost,' in src, \
            '期望构建实参必须是裸 state.shop_refresh_cost(禁 or-2 进期望)'

    def test_gold_leg_uses_none_able_reader(self):
        """期望金腿读数用 read_gold_opt(int|None),非 stylized read_gold。"""
        src = _shop_source()
        assert 'read_gold_opt' in src
        # 金腿读数行(read_gold_opt),不与花销账既有 read_gold 行混淆
        assert '_pre_gold = read_gold_opt(self.ctx, self.screenshot())' in src
        assert '_gold_after = read_gold_opt(self.ctx, self.screenshot())' in src

    def test_defect_row_kind_and_surface(self):
        """违例落台账 surface='shop' / kind='refresh_expect_mismatch'。"""
        src = _shop_source()
        assert "'shop', 'refresh_expect_mismatch'" in src


class TestW573WiringShapeSmoke:
    """按接线同款调用形态走纯函数链,锁形状不漂移(本体真值表归 W564)。"""

    def test_producer_call_shape_roundtrip(self):
        """build(裸金,裸刷费,旧五张元组) → expect;reconcile → 行集。"""
        cards_old = [(c.name, c.star) for c in [
            ShopCard(x=0, faction='量子同频', name='希儿', cost=3, star=1),
            ShopCard(x=1, faction='量子同频', name='希儿', cost=3, star=1),
            ShopCard(x=2, faction='?', name='', cost=0, star=1),
        ]]
        built = build_refresh_expect(10, 2, cards_old, plane=1, round_num=5)
        assert built is not None
        expect, plane, round_num = built
        assert (plane, round_num) == (1, 5)
        # 金腿:点后实读 8 = 10-2 → 无票
        assert refresh_reconcile_mismatches(expect, 8, 3) == []
        # 金不符 → gold 票;牌腿:0 张有身份 → cards 票
        rows = refresh_reconcile_mismatches(expect, 5, 0)
        assert {r['domain'] for r in rows} == {'gold', 'cards'}

    def test_producer_none_cost_short_circuit(self):
        """刷费 None(面板失读)→ build 返 None = 波内跳过对账(禁 or-2)。"""
        assert build_refresh_expect(10, None, [('希儿', 1)], 1, 5) is None
        assert build_refresh_expect(None, 2, [('希儿', 1)], 1, 5) is None
