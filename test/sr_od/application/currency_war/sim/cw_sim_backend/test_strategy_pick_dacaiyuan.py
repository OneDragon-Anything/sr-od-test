"""sim 大裁员选卡落地全链 walk 测试(镜像 src = sim/cw_sim_backend.py
出售发牌腿判据细分 + kernel 获得链只登记不写状态的实现分支双桥;驱动助手 import 复用
test_sim_sell_all_deal 同形文件,只 import 复用不改——先例 =
test_strategy_pick_gudinglicai.py 跨测试模块复用声明)。

测试面依据 = 迭代设计 designs/T-186-dacaiyuan.md §2/§4(锁 3/锁 3b)
+ 强制实现要点(T-120 发牌判据细分):发牌腿是人力重组卡文附加面、
非出售语义固有,判据集 = 具发牌腿语义值派生——素出售卡(大裁员)
不入集;撤销细分则素出售卡自动入列,sim 局误发 5 只 2★(世界假单位
污染),本目录锁 3b 必红(红验在批内执行在案)。

- 锁 3(全链主锁):decl 分派选大裁员 → 出售面(deployed/bench 清空
  + 基础公式退款恰 3)+ 刷腿(free_refresh_left +6)一拍落地;
- 锁 3b(发牌判据细分锁):大裁员 ∉ 发牌判据集 → bench 零新增单位
  (零假发牌);人力重组路径零扰 = 存量锁 test_sim_sell_all_deal.py
  原样绿。
"""
from __future__ import annotations

from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
    _SIG_OBS,
)
from test.sr_od.application.currency_war.sim.test_sim_sell_all_deal import (
    _backend,
    _bench_units,
    _drive_to_strategy_offer,
    _pick_card,
)

from sr_od.application.currency_war.kernel.cw_economy import (
    bench_char_cost,
    sell_refund,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    Unit,
    deployed_rows_of_view,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)
from sr_od.application.currency_war.sim import cw_sim_backend
from sr_od.application.currency_war.sim.cw_sim_backend import (
    uninstall_backend,
)

_OPTS = ['大裁员', '躺平', '淘金客']
_SOLD = ('三月七', 2)   # 预种 2★1 费:cost=1 无手续费,×2 两候选口径同值
                        #(恰 3 精确锚在容器受控的 kernel 只登记不写状态的实现分支锁 4)


def _seed_sold_unit(b) -> None:
    """预种一枚 2★1 费到前台(退款公式的确定性输入)。"""
    b.gs.observe(b.gs.deployed,
                 _dvs([Unit(char_id=_SOLD[0], star=_SOLD[1])], []),
                 sig=_SIG_OBS)


def _board_refund(gs) -> int:
    """现板面全额退款预演算(单一源公式与桥同源;开局单位在席,
    退款断言 = 全板面公式值,非单枚锚)。"""
    front, back = deployed_rows_of_view(gs.deployed.value)
    bench = [s.unit for s in gs.bench.value.slots
             if s.kind == 'unit' and s.unit is not None]
    return sum(sell_refund(int(u.star), bench_char_cost(u, gs))
               for u in front + back + bench)


# ============================================================ 锁 3:全链主锁

def test_pick_dacaiyuan_full_chain_sell_and_burst() -> None:
    """decl 分派全链:选大裁员 → 出售面(场清空+退款恰 = 选卡拍板面
    全额公式预演)+ 刷腿(free_refresh_left +6)一拍落地;bench 清空且
    零新增单位(素出售无发牌面)。"""
    b = _backend(7)
    try:
        _drive_to_strategy_offer(b)
        gs = b.gs
        _seed_sold_unit(b)
        expected_refund = _board_refund(gs)
        assert expected_refund > 0, '预演前提:选卡拍板面非空'
        gs.write_logic(gs.invest_strategy_opts, _OPTS,
                       produced_by='Test', evidence='t:opts', sig=_SIG)
        gold_before = int(gs.gold.value or 0)
        _pick_card(b, '大裁员')
        _f, _bk = deployed_rows_of_view(gs.deployed.value)
        assert (_f, _bk) == ([], []), '场清空(出售面,实机和模拟器两边同链)'
        assert int(gs.gold.value or 0) - gold_before == expected_refund, \
            '退款 = 板面全额公式值(单一源 cw_economy;×2 修饰缺口低估' \
            '申报,观察覆盖)'
        assert gs.free_refresh_left.value == 6, '刷新发放 +6(只登记不写状态的实现分支 burst 桥)'
        assert _bench_units(gs) == [], 'bench 清空且零新增(素出售无发牌面)'
    finally:
        uninstall_backend()


# ==================================================== 锁 3b:发牌判据细分

def test_pick_dacaiyuan_zero_deal_leg_criterion_split() -> None:
    """发牌判据细分锁:大裁员不入发牌判据集(素出售语义值)→ sim 局
    选大裁员 bench 零新增单位。撤销细分(判据回退素出售值过滤)则素
    出售卡自动入集、发牌腿误发 5 只 2★,本锁必红。"""
    assert '大裁员' not in cw_sim_backend.SELL_ALL_REWRITE_STRATEGIES, \
        '素出售卡不入发牌判据集(语义值细分)'
    assert '人力重组' in cw_sim_backend.SELL_ALL_REWRITE_STRATEGIES, \
        '具发牌腿卡在集(判据派生前提,存量路径零扰)'
    b = _backend(7)
    try:
        _drive_to_strategy_offer(b)
        gs = b.gs
        _seed_sold_unit(b)
        gs.write_logic(gs.invest_strategy_opts, _OPTS,
                       produced_by='Test', evidence='t:opts', sig=_SIG)
        _pick_card(b, '大裁员')
        _f, _bk = deployed_rows_of_view(gs.deployed.value)
        assert (_f, _bk) == ([], []), '出售面照走(实机和模拟器两边同链)'
        assert _bench_units(gs) == [], \
            '零发牌(撤销细分即误发 5 只 2★,本断言必红)'
    finally:
        uninstall_backend()
