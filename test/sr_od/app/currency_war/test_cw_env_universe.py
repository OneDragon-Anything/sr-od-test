"""T-127 投资环境迭代 3.1 候选全集门 · 预注册单帧锁(U1-U6)。

锁面出处 = docs/develop/sr_od/application/currency_war/changes/2026-09-12-invest-env/
design.md §2.1(全集派生/落码面·形态 B)/§2.7(全集门锁表 U1-U6);用户裁定
2026-09-12「我们有对应的终局阵容定义,才选对应的投资环境……不在候选阵容里的
投资环境选了肯定也没用」。机器单一源 = ``candidate_faction_universe``
(kernel/cw_comps.py,COMP_LIBRARY 派生;阵营维 = 环境门与策略卡门共用的同一台
机器,消费方禁二次建模);落码面 = decide_event env 分支裸分前置谓词 +
``env-off-universe`` 失格归因 + 循环外全集单帧单读。

fixture 直调核验(design §2.1.1 全集核对表 + §2.7 锁表帧值;模块导入即验,
COMP_LIBRARY/环境注册表漂移先红于此——漂移 = 修库后重核全集咬合面,不是改断言
保绿):
- 全集 20 阵容(design §2.1.1 核对表逐名)与 COMP_LIBRARY 规模;
- 门咬合面恰 4 条环境(狼狩概念股/狼狩邀请/公司契约/盛会之星邀请;公司与
  盛会之星仅以 flex_factions 出现于候选套,按「flex 不入全集」裁定落集外——
  本断言同时反证 flex_factions 未混入全集);
- 追击 exclusivity(U3 动态收窄语义前提:追击阵营独占于追击飞霄);
- U 锁帧实卡裸分值与 faction(design §2.7 锁表括号值)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_game_state import (
    board_state_bridge,
)
from sr_od.application.currency_war.kernel.cw_comps import (
    COMP_LIBRARY,
    candidate_faction_universe,
)
from sr_od.application.currency_war.kernel.cw_events import decide_event
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_ENVS,
    get_env,
)
from sr_od.application.currency_war.kernel.cw_vocab import CwWorkFrame, PickEvent

# ===== fixture 前提直调核验(锁语义依赖的注册表事实;漂移先红于此)=====

_DESIGN_UNIVERSE = frozenset({
    '列车同行', '命运圣杯', '减益', '星核猎手', '欢愉', '星间旅人', '量子同频',
    '贝洛伯格', '巡海游侠', '击破', '战技点', '能量', '群攻', '银河学者',
    '昼之半神', '追击', '夜之半神', '燃血', '持续伤害', '仙舟',
})
assert candidate_faction_universe() == _DESIGN_UNIVERSE, (
    '全集核对表漂移(design §2.1.1):COMP_LIBRARY 核心羁绊变更,重核全集门咬合面')
assert len(COMP_LIBRARY) == 20, 'COMP_LIBRARY 规模漂移,全集核对表须随批重核'

_OFF_UNIVERSE_ENVS = frozenset(
    name for name, e in INVESTMENT_ENVS.items()
    if e.faction and e.faction not in _DESIGN_UNIVERSE)
assert frozenset(
    {'狼狩概念股', '狼狩邀请', '公司契约', '盛会之星邀请'}) == _OFF_UNIVERSE_ENVS, (
    f'全集外咬合面漂移(design §2.1.1 实测恰 4 条),实得 {sorted(_OFF_UNIVERSE_ENVS)}')

assert {c.name for c in COMP_LIBRARY if '追击' in c.factions} == {'追击飞霄'}, (
    'U3 动态收窄前提漂移:追击阵营应独占于追击飞霄')

# U 锁帧实卡(名, 裸分, faction)——design §2.7 锁表括号值逐卡直调
for _n, _pv, _f in [
    ('狼狩概念股', 40, '狼狩'), ('狼狩邀请', 30, '狼狩'),
    ('公司契约', 48, '公司'), ('盛会之星邀请', 30, '盛会之星'),
    ('战力提升', 38, ''), ('成功经验', 36, ''), ('仙舟概念股', 48, '仙舟'),
    ('敌后破坏', 46, ''), ('专家研讨会', 34, ''), ('追击概念股', 52, '追击'),
    ('增发货币', 48, ''), ('人身意外险', 48, ''), ('彩虹时代', 72, ''),
    ('深井角斗场', 42, ''), ('火药味', 28, ''),
]:
    _e = get_env(_n)
    assert _e is not None and _e.pick_value == _pv and _e.faction == _f, (
        f'fixture 实卡漂移:{_n} 期望 pv={_pv} faction={_f!r},实得 {_e}')


def _cfg(**overrides) -> SimpleNamespace:
    base: dict = {'strategy_priority': [], 'strategy_forbid': []}
    base.update(overrides)
    return SimpleNamespace(**base)


_STATE = CwWorkFrame(board={}, hp=100, hp_readable=True)


def _pick(options: list[str], cfg=None, **kw) -> PickEvent:
    """kernel 纯函数直调(空板帧:无 D* 信号/无 DoT 惩罚;容器桥沿 invest_refresh 先例)。"""
    return decide_event(options, cfg if cfg is not None else _cfg(),
                        board_state_bridge(_STATE), **kw)


# ===== U1 全集外失格(design §2.7 行 1;行为变化锚点:改门前本帧选狼狩概念股)=====


def test_u1_off_universe_fails_gate() -> None:
    """U1:全集外 faction 环境跳过裸分支(分数 0 天然垫底)→ 全集内裸分者胜出。
    归因串可见性(落码面条款)随锁:全失格帧胜出者 reason = env-off-universe。"""
    p = _pick(['狼狩概念股', '战力提升', '成功经验'])
    assert p.option_idx == 1, (
        f'狼狩在全集外应失格,战力提升(38)胜出,实得 {p.reason}')
    assert 'env-eval' in p.reason, f'胜出者应走 env 裸分支,实得 {p.reason}'
    # 全无用帧:三候选全在全集外 → 首序胜出,失格归因可见(观测面)
    p2 = _pick(['狼狩概念股', '狼狩邀请', '盛会之星邀请'])
    assert p2.option_idx == 0 and 'env-off-universe' in p2.reason, (
        f'全失格帧胜出者应带 env-off-universe 归因,实得 {p2.reason}')


# ===== U2 全集内保留(design §2.7 行 2;门不误伤)=====


def test_u2_in_universe_bare_score_kept() -> None:
    """U2:全集内 faction 环境(D*=∅ 无 floor)照常走裸分支 → 裸分最高者胜出。
    reason 断言防「全死帧首序胜出」假绿(门误杀全集内时 idx 巧合不变)。"""
    p = _pick(['仙舟概念股', '敌后破坏', '专家研讨会'])
    assert p.option_idx == 0, f'仙舟在全集内不应被门误伤(48 胜出),实得 {p.reason}'
    assert 'env-eval' in p.reason, f'胜出应来自裸分支(48),实得 {p.reason}'


# ===== U3 evicted 动态收窄(design §2.7 行 3;独占阵营随阵容退出全集)=====


def test_u3_evicted_narrows_universe() -> None:
    """U3:缺省全集含追击 → 追击概念股(52)胜出;evicted={'追击飞霄'} 后追击
    退出全集(独占阵营)→ 追击概念股失格,增发货币(48,首序)胜出。"""
    base = ['追击概念股', '增发货币', '人身意外险']
    p0 = _pick(base)
    assert p0.option_idx == 0, f'缺省全集含追击,52 应胜出,实得 {p0.reason}'
    p1 = _pick(base, evicted={'追击飞霄'})
    assert p1.option_idx == 1, (
        f"evicted 追击飞霄后追击概念股应失格,增发货币(48)胜出,实得 {p1.reason}")


# ===== U4 faction 空不受门影响(design §2.7 行 4;门谓词前半支)=====


def test_u4_factionless_env_untouched() -> None:
    """U4:faction 空(时代/经济等阵容无关型)恒放行 → 裸分竞争不变。"""
    p = _pick(['增发货币', '彩虹时代', '深井角斗场'])
    assert p.option_idx == 1, f'faction 空环境不受门影响,彩虹时代(72)胜出,实得 {p.reason}'


# ===== U5 steering 次序保留(design §2.7 行 5;priority 在门后叠加)=====


def test_u5_steering_priority_still_lifts_off_universe() -> None:
    """U5:无用环境被 user-priority 抬升仍可胜过低裸分有用环境(用户配置最高
    语义,门只辖裸分支不改 steering 次序):无 priority → 火药味(28);
    priority 点名狼狩概念股 → 0+30=30 > 28 胜出。"""
    base = ['狼狩概念股', '狼狩邀请', '火药味']
    p0 = _pick(base)
    assert p0.option_idx == 2, f'无 priority 时火药味(28)胜出,实得 {p0.reason}'
    p1 = _pick(base, cfg=_cfg(env_priority=['狼狩概念股']))
    assert p1.option_idx == 0, (
        f'priority 应把全集外环境抬到 28 之上(0+30),实得 {p1.reason}')


# ===== U6 floor 正交回归(design §2.7 行 6;D* ⊆ 全集,floor 永不咬全集外)=====


def test_u6_floor_orthogonal_to_gate() -> None:
    """U6:锁线帧(D*① = 景元仙舟)下仙舟概念股走阵营 floor(align-locked),
    全集门与 floor 门无交集——floor 不被门扰动,行为与改门前一致。"""
    p = _pick(['仙舟概念股', '火药味', '人身意外险'], locked_comp='景元仙舟')
    assert p.option_idx == 0, f'锁线帧仙舟概念股应胜出,实得 {p.reason}'
    assert 'align-locked' in p.reason, f'胜出归因应为阵营 floor,实得 {p.reason}'
