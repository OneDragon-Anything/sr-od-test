"""息帽覆写链落码测试(息帽死链修复;单一源 = aggregate 聚合)。

出处(测试纪律:新测试必引设计出处):
- ADR-0598(息帽死链修复:cap_resolved_of_session 消费
  ``aggregate_economy(session.active_strategies).interest_cap_override``,
  旧 ``MandateState.cw4_cap_override`` 全仓零写点死通道退役);
- ADR-0131(EconomyEffect 聚合语义:cap 并持取宽 max,买断制 0 单独
  持有时生效)、ADR-0516(cap 三源归一:判据链不读 registry 旋钮);
- cw_investments.STRATEGY_ECONOMY 注册表直调(开源节流 9/利息上调 10/
  买断制 0——测试值一律注册表名,禁裸 override 数字)。

测试面(方案审验收 ④-⑤ 编号):
1. ①注册表直调三卡已登记 → cap 联动(kernel 链 + 预算面 R* + 换线可负担窗;
   前置锚 = 三卡覆写值已登记直调;回落面 = 未登记 → DEFAULT);
2. ④None/0 区分测试(最高危陷阱):买断制 override=0 不得被 ``or`` 真值
   折叠回 5——判别只认 None;
3. ⑤并持 max 语义测试(ADR-0131):开源节流+利息上调 → 10;
   买断制+开源节流 → 9。
(原 5 墓碑 grep 测试已删:源码扫描形态,README 禁止清单。)
"""
from __future__ import annotations

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box as _bridge,
)

from sr_od.application.currency_war.kernel.cw_economy import (
    DEFAULT_INTEREST_CAP,
    cap_resolved_of_session,
    in_launch_spend_zone,
    in_must_spend_zone,
    interest,
    saturation_line,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_ECONOMY,
    EconomyEffect,
    aggregate_economy,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)

#: 注册表可达息帽覆写值域(测试只许经注册表名注入,禁裸数字——值与
#: 标签错配是五犯实证错误类,attack 纪律:数值锚点注册表直调)。
_CAP_CARD_BY_VALUE: dict[int, str] = {
    eff.interest_cap_override: name
    for name, eff in STRATEGY_ECONOMY.items()
    if isinstance(eff, EconomyEffect)
    and eff.interest_cap_override is not None
}


def _sess_with(*names: str) -> StrategySession:
    """session 桩:active_strategies 注入面(终态契约 §B:单一源 = 容器,
    持卡经 write_logic 直写 gs——两写点公共权威)。"""
    s = StrategySession()
    from sr_od.application.currency_war.kernel.cw_game_state import (
        ChannelSig,
        game_state_of,
    )
    game_state_of(s).write_logic(
        game_state_of(s).active_strategies, list(names),
        produced_by='test',
        sig=ChannelSig(family='logic_action', actor='CwLoop',
                       screen='', mode='compute'))
    return s


def test_three_cap_cards_linkage() -> None:
    """测试①:注册表直调三卡已登记 → cap 联动(resolved 链单点)。前置锚:
    三卡覆写值直调已登记(9/10/0;表缺任一 = 本文件全部按名注入的测试失去
    锚点,先修注册表再谈测试)。回落面:未登记 → DEFAULT_INTEREST_CAP
    (裸 session/None/未注册名三形态;回落问题实际形态 = 从未持有,
    append-only)。"""
    # 前置锚(原可达性测试迁并):三卡覆写值已登记直调
    assert {9: '开源节流', 10: '利息上调', 0: '买断制'}.items() \
        <= _CAP_CARD_BY_VALUE.items()
    for cap, name in _CAP_CARD_BY_VALUE.items():
        assert cap_resolved_of_session(_sess_with(name)) == cap, name
    # 回落三形态(原回落测试迁并)
    assert cap_resolved_of_session(None) == DEFAULT_INTEREST_CAP
    assert cap_resolved_of_session(StrategySession()) == DEFAULT_INTEREST_CAP
    assert cap_resolved_of_session(_sess_with('未注册卡名')) \
        == DEFAULT_INTEREST_CAP


def test_none_zero_distinction_buyout() -> None:
    """测试④(最高危):买断制 override=0 是有效覆写,不得被 ``or`` 真值
    折叠回 5(聚合器 caps 非空才 replace,interest_cap_resolved 只认
    None——三层任一回退,本测试红)。语义出口:g*=0、息恒 0、两溢余域
    任意金位恒 False(§2.1 买断制出辖)。"""
    sess = _sess_with('买断制')
    assert aggregate_economy(['买断制']).interest_cap_override == 0
    assert cap_resolved_of_session(sess) == 0
    assert saturation_line(cap_resolved_of_session(sess)) == 0
    assert interest(999, cap_resolved_of_session(sess)) == 0
    for gold in (0, 1, 50, 51, 999):
        assert in_must_spend_zone(gold, sess) is False, gold
        assert in_launch_spend_zone(gold, sess) is False, gold


def test_multi_hold_takes_widest() -> None:
    """测试⑤:并持取宽 = ADR-0131(游戏取宽值,保守建模取 max 非 min)。
    开源节流(9)+利息上调(10)→ 10;买断制(0)+开源节流(9)→ 9
    ——0 与 None 不同层,并持 0 不折叠。"""
    assert cap_resolved_of_session(_sess_with('开源节流', '利息上调')) == 10
    assert cap_resolved_of_session(_sess_with('买断制', '开源节流')) == 9
    assert cap_resolved_of_session(_sess_with('利息上调', '买断制')) == 10


def test_budget_face_reserve_floor_linkage() -> None:
    """测试①预算面随批接入调用:R* 守息线分量 = resolved 链(ADR-0598)——
    买断制局刷新授权车道不再被 50 金地板压死(囤金车道收尾),利息
    上调局守息线抬到 100。registry 旋钮不辖本链(ADR-0516 归一)。"""
    from sr_od.application.currency_war.kernel.cw_economy import reserve_cap

    def _boxed_gs(gold: int):
        """排程关闭态容器种子(bench 空、等级已到峰值):R* = 守息线分量
        裸值(桥配方 = 帧缺省 + 空店离屏)。"""
        return _bridge(plane=1, round_num=5, gold=gold, level=9, hp=80,
                       shop_refresh_cost=2, node='battle')

    base = reserve_cap(_boxed_gs(30), StrategySession())
    assert base == saturation_line(DEFAULT_INTEREST_CAP)
    buyout_sess = _sess_with('买断制')
    assert reserve_cap(_boxed_gs(30), buyout_sess) == 0
    rich_sess = _sess_with('利息上调')
    assert reserve_cap(_boxed_gs(30), rich_sess) \
        == saturation_line(10)


def test_line_switch_affordable_window_linkage() -> None:
    """测试①换线可负担窗随批接入调用:e_rounds 的可负担刷数守息线 = resolved
    链(ADR-0598)——买断制局 affordable 从 (g−50)//刷价 放宽到 (g−0)
    //刷价;session=None 调用形态退注册表派生值(既有桩零漂移)。"""
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    from sr_od.application.currency_war.kernel.cw_line_switch import e_rounds

    comp = next(c for c in COMP_LIBRARY if c.core_faction_reqs)
    axes = {'plane': 2, 'round_num': 2, 'gold': 55, 'level': 7, 'hp': 60,
            'shop_refresh_cost': 2, 'node': 'battle'}
    e_base = e_rounds(comp, _bridge(**axes), session=StrategySession())
    e_buyout = e_rounds(comp, _bridge(**axes), session=_sess_with('买断制'))
    assert e_buyout < e_base   # 可负担刷数变多 → E_rounds 变小(单调)
    # 换算核:affordable 差 = 息线差 50 金 / 刷价 2 = 25 刷(帽前);
    # 单调判 + 同 session 双调幂等即可,禁在此复算第二套账(单一源)。
    assert e_rounds(comp, _bridge(**axes), session=_sess_with('买断制')) == e_buyout


# (原墓碑 grep 测试 test_grep_lock_no_cw4_cap_override_in_src 删:源码扫描
#  形态,README 禁止清单无例外——「死通道防回流」归 review 与代码规范;
#  注入通道唯一合法形态由本文件测试①③⑤行为测试辖。伴随 _mandate_state_
#  docstring_lines 助手同删,ast/re/Path/_SRC 导入清。头注测试面清单同步。)
