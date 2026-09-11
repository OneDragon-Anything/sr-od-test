"""息帽覆写链落码锁(T-160 息帽死链修复;单一源 = aggregate 聚合)。

出处(锁纪律:新锁必引设计出处):
- ADR-0598(息帽死链修复:cap_resolved_of_session 消费
  ``aggregate_economy(session.active_strategies).interest_cap_override``,
  旧 ``MandateState.cw4_cap_override`` 全仓零写点死通道退役);
- ADR-0131(EconomyEffect 聚合语义:cap 并持取宽 max,买断制 0 单独
  持有时生效)、ADR-0516(cap 三源归一:判据链不读 registry 旋钮);
- cw_investments.STRATEGY_ECONOMY 注册表直调(开源节流 9/利息上调 10/
  买断制 0——测试值一律注册表名,禁裸 override 数字)。

锁面(方案审验收 ④-⑤ 编号):
1. ①注册表直调三卡在册 → cap 联动(kernel 链 + 预算面 R* + 换线可负担窗);
2. ②不在册 → 回落 DEFAULT(裸 session/None session/未注册名);
3. ④None/0 区分锁(最高危陷阱):买断制 override=0 不得被 ``or`` 真值
   折叠回 5——判别只认 None;
4. ⑤并持 max 语义锁(ADR-0131):开源节流+利息上调 → 10;
   买断制+开源节流 → 9;
5. 墓碑 grep 锁:``cw4_cap_override`` 在 src 生产面零命中(死通道
   退役后防回流,旧读点/新写点出现即违规)。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from sr_od.application.currency_war.kernel.cw_board_state import (
    board_state_bridge as _bridge,
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
from sr_od.application.currency_war.kernel.cw_state import GameState
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)

_SRC = (Path(__file__).parents[5] / 'src' / 'sr_od' / 'application'
        / 'currency_war')

#: 注册表可达息帽覆写值域(测试只许经注册表名注入,禁裸数字——值与
#: 标签错配是五犯实证错误类,attack 纪律:数值锚点注册表直调)。
_CAP_CARD_BY_VALUE: dict[int, str] = {
    eff.interest_cap_override: name
    for name, eff in STRATEGY_ECONOMY.items()
    if isinstance(eff, EconomyEffect)
    and eff.interest_cap_override is not None
}


def _sess_with(*names: str) -> StrategySession:
    """session 桩:active_strategies 注入面(session 级字段=两写点公共
    权威——实机 handler 确认后 append / sim 注入臂 append+镜像)。"""
    s = StrategySession()
    s.active_strategies = list(names)
    return s


def test_registry_override_values_are_reachable() -> None:
    """前置锚:注册表三卡覆写值直调在册(9/10/0;表缺任一 = 本文件
    全部按名注入的锁失去锚点,先修注册表再谈锁)。"""
    assert {9: '开源节流', 10: '利息上调', 0: '买断制'}.items() \
        <= _CAP_CARD_BY_VALUE.items()


def test_three_cap_cards_linkage() -> None:
    """锁①:注册表直调三卡在册 → cap 联动(resolved 链单点)。"""
    for cap, name in _CAP_CARD_BY_VALUE.items():
        assert cap_resolved_of_session(_sess_with(name)) == cap, name


def test_default_fallback_without_cards() -> None:
    """锁②:不在册 → 回落 DEFAULT_INTEREST_CAP(裸 session/None/
    未注册名三形态;回落问题实际形态 = 从未持有,append-only)。"""
    assert cap_resolved_of_session(None) == DEFAULT_INTEREST_CAP
    assert cap_resolved_of_session(StrategySession()) == DEFAULT_INTEREST_CAP
    assert cap_resolved_of_session(_sess_with('未注册卡名')) \
        == DEFAULT_INTEREST_CAP


def test_none_zero_distinction_buyout() -> None:
    """锁④(最高危):买断制 override=0 是有效覆写,不得被 ``or`` 真值
    折叠回 5(聚合器 caps 非空才 replace,interest_cap_resolved 只认
    None——三层任一回退,本锁红)。语义出口:g*=0、息恒 0、两溢余域
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
    """锁⑤:并持取宽 = ADR-0131(游戏取宽值,保守建模取 max 非 min)。
    开源节流(9)+利息上调(10)→ 10;买断制(0)+开源节流(9)→ 9
    ——0 与 None 不同层,并持 0 不折叠。"""
    assert cap_resolved_of_session(_sess_with('开源节流', '利息上调')) == 10
    assert cap_resolved_of_session(_sess_with('买断制', '开源节流')) == 9
    assert cap_resolved_of_session(_sess_with('利息上调', '买断制')) == 10


def test_budget_face_reserve_floor_linkage() -> None:
    """锁①预算面随批接线:R* 守息线分量 = resolved 链(ADR-0598)——
    买断制局刷新授权车道不再被 50 金地板压死(囤金车道收口),利息
    上调局守息线抬到 100。registry 旋钮不辖本链(ADR-0516 归一)。"""
    from sr_od.application.currency_war.kernel.cw_economy import reserve_cap
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        strategy_state_of,
    )

    def _frame(gold: int, session: StrategySession) -> GameState:
        # 排程关闭态帧(bench 空、等级已到峰值):R* = 守息线分量裸值
        st = GameState(plane=1, round_num=5, gold=gold, level=9, hp=80,
                       shop_refresh_cost=2, deployed=[],
                       bench=[None] * 10, shop=[], node_type='battle',
                       board={})
        strategy_state_of(session)   # 状态面触达(与生产读口同形)
        return st

    base = reserve_cap(_frame(30, StrategySession()), StrategySession())
    assert base == saturation_line(DEFAULT_INTEREST_CAP)
    buyout_sess = _sess_with('买断制')
    assert reserve_cap(_frame(30, buyout_sess), buyout_sess) == 0
    rich_sess = _sess_with('利息上调')
    assert reserve_cap(_frame(30, rich_sess), rich_sess) \
        == saturation_line(10)


def test_line_switch_affordable_window_linkage() -> None:
    """锁①换线可负担窗随批接线:e_rounds 的可负担刷数守息线 = resolved
    链(ADR-0598)——买断制局 affordable 从 (g−50)//刷价 放宽到 (g−0)
    //刷价;session=None 调用形态退注册表派生值(既有桩零漂移)。"""
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    from sr_od.application.currency_war.kernel.cw_line_switch import e_rounds

    comp = next(c for c in COMP_LIBRARY if c.form_tiers)
    st = GameState(plane=2, round_num=2, gold=55, level=7, hp=60,
                   shop_refresh_cost=2, deployed=[],
                   bench=[None] * 10, shop=[], node_type='battle',
                   board={})
    e_base = e_rounds(comp, _bridge(st), session=StrategySession())
    e_buyout = e_rounds(comp, _bridge(st), session=_sess_with('买断制'))
    assert e_buyout < e_base   # 可负担刷数变多 → E_rounds 变小(单调)
    # 换算核:affordable 差 = 息线差 50 金 / 刷价 2 = 25 刷(帽前);
    # 单调判 + 同 session 双调幂等即可,禁在此复算第二套账(单一源)。
    assert e_rounds(comp, _bridge(st), session=_sess_with('买断制')) == e_buyout


def _mandate_state_docstring_lines(path: Path) -> set[int]:
    """mandate_state.py 全部 docstring 的行号集(ast 解析,模块/类/函数级)。

    墓碑扫描的豁免面 = 该文件的退役叙事行本身(docstring/注释)——整文件
    豁免会让真实代码行(读点/写点)在叙事文件内静默回流不红,故收窄到
    叙事行(DEBTS D76)。"""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    spans: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef,
                             ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                spans.update(range(body[0].value.lineno,
                                   body[0].value.end_lineno + 1))
    return spans


def test_grep_lock_no_cw4_cap_override_in_src() -> None:
    """墓碑 grep 锁:``cw4_cap_override`` 在生产面(src)零代码命中——
    死通道退役(ADR-0598)后任何读点/写点回流即违规(注入通道唯一
    合法形态 = session.active_strategies,锁①③⑤已辖)。豁免 =
    mandate_state.py 的 docstring/注释行(墓碑注与模块迁移账本叙述所在
    文件,w628 锁豁免定义文件同款先例;原整文件豁免已收窄到叙事行,
    代码行回流即违规)+ 各文件注释行。"""
    pat = re.compile(r'cw4_cap_override')
    doc_lines = _mandate_state_docstring_lines(
        _SRC / 'strategies' / 'impl' / 'mandate_v1' / 'mandate_state.py')
    offenders = {}
    for path in _SRC.rglob('*.py'):
        spans = doc_lines if path.name == 'mandate_state.py' else set()
        hits = sum(1 for no, line in
                   enumerate(path.read_text(encoding='utf-8').splitlines(),
                             start=1)
                   if pat.search(line)
                   and not line.lstrip().startswith('#')
                   and no not in spans)
        if hits:
            offenders[str(path.relative_to(_SRC))] = hits
    assert offenders == {}, offenders
