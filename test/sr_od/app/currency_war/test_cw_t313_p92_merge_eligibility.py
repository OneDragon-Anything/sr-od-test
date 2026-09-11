"""T-313 P92 ④通道资格维对齐锁(合成完备购假可达修复落码)。

锁依据(锁的存在性纪律:新锁必引设计出处):
- 方案正本 = .debug/temp/currency_war/T-313-交付报告.md §③(装配面
  补资格维对齐 M2b + 形态维单一源 helper ``_merge_pair_names``);
  对抗审凭据 = .debug/progress/2026-09-06-currency-war-redesign/
  reviews/T-313-方案对抗审.md(6 项发现随实施批吸收,本文件锁 A/D
  docstring 标注对应发现号);
- 病灶 = P92 ④装配(shop.py ``_p92_pairs``)不滤 buy_members:∉采购集
  的 1★×2 对被算「④可达」→ 全通道死帧族假可达放行(T-295 对抗审
  问题 6 转正);命题语义域 = 决策机器全部买入通道(math_proofs.md
  P92 行)——helper 谓词 = 机器口径(merge_mechanics.md §2 主例为
  机制全集,机器未实现 1★×2 与 ≥2★ 并存的买三张通道,详见 helper
  docstring 残余申报);
- 与既有锁正交:test_cw_t263_exit_margin.py 钉判定尺真值表与「无
  1★×2 对」的全死帧拦刷;本文件钉「有 1★×2 对时的资格维/形态维
  过滤行为」,互补不重叠。判定尺本体零改动,既有两锁零漂移。

fixture 说明:角色名/费用全部注册表现查(CHARACTERS/pair_target_
comp),帧构造前提以 refresh_prob 断言守卫(注册表费档表变动时本
文件红在前提而非行为断言,禁静默漂移)。
"""
from __future__ import annotations

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.data.cw_shop_odds import refresh_prob
from sr_od.application.currency_war.kernel.cw_state import (
    BuyCard,
    GameState,
    RefreshShop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.refresh import (
    all_channel_buy_exists,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
    _merge_pair_names,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_decide as _decide,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_members as _members,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_session as _session,
)


def _pair_comp():
    from sr_od.application.currency_war.kernel.cw_intention import (
        pair_target_comp,
    )
    return pair_target_comp(('仙舟', '持续伤害'))


# ===== 锁 D:helper 形态谓词真值表(判据层直调)=====

class TestMergePairNamesPredicate:
    """``_merge_pair_names`` 真值表(方案稿 §④ 锁 D;发现 4 转正:
    归一化 ``(c.star or 1)`` 与计数键 ``(c.char_id or '')`` 逐字符同
    ``_cnt``,star=None 用例钉死等价声明的实现翻转点)。helper 为纯
    形态谓词(不触注册表),合成名合法。"""

    def test_truth_table(self):
        f = _merge_pair_names
        # 恰 2 全 1★(bench/deployed 跨容器合计计数宇宙)→ 命中
        assert f([_bc('甲', star=1)], [_bc('甲', star=1)]) == {'甲'}
        # 1★×3 → 非对(满 3 已合成形态,机器单跳口径不含)
        assert f([_bc('甲', star=1), _bc('甲', star=1),
                  _bc('甲', star=1)], []) == set()
        # 1★×2 + 2★×1 → 非对(机器未实现买三张通道,helper docstring 残余申报)
        assert f([_bc('甲', star=1), _bc('甲', star=1)],
                 [_bc('甲', star=2)]) == set()
        # 1★×2 + 3★×1 → 非对(方案稿 §3.3-2 形态维收窄面)
        assert f([_bc('甲', star=1), _bc('甲', star=1)],
                 [_bc('甲', star=3)]) == set()
        # 单张 → 非对;空局面 → 空集
        assert f([_bc('甲', star=1)], []) == set()
        assert f([], []) == set()

    def test_star_none_normalized_as_one_star(self):
        """star 缺读(None)视同 1★——旧 M2b 循环 ``(c.star or 1) >= 2``
        对 None 同样放行,等价改写后行为必须一致(发现 4:实现若写成
        ``c.star == 1`` 在此处翻转,本用例红)。"""
        assert _merge_pair_names([_bc('甲', star=1), _bc('甲')],
                                 []) == {'甲'}
        assert _merge_pair_names([_bc('甲'), _bc('甲')], []) == {'甲'}

    def test_criterion_fourth_channel_gold_gate(self):
        """④死条件金维(发现 3 转正,判定尺直调补钉):gold < base ⇒
        ④死——锁 A 集成面 gold 被 r1 账/r2 预算门顶到 g* 之上,金维
        死条件只能在判定尺层钉(gold=base 边界恰好存活为对照)。"""
        base = {'g_star': 50, 'cap_resolved': 5, 'bench_free': 0,
                'seat_recoverable': False, 'missing_costs': [],
                'stockpile_costs': [], 'merge_pair_costs': [2],
                'level': 5, 'ev_face_open': False, 'window_nonempty': False}
        assert all_channel_buy_exists(gold=1, **base) is False
        assert all_channel_buy_exists(gold=2, **base) is True


# ===== 锁 A/B/C:资格维 × 形态维集成帧(P92 门行为)=====

def _elig_names():
    """帧名字组(注册表现查,禁手抄):W = 1 费线成员(r1 账合格集
    承载);X = 4 费线成员(lv4 不可刷档 ⇒ 修复后④对 X 死);Y0 =
    线外 2 费无后台件(资格维病灶名)。"""
    comp = _pair_comp()
    members = list(_members(comp))
    w = next(m for m in members if CHARACTERS[m].cost == 1)
    x = next(m for m in members if CHARACTERS[m].cost == 4)
    y0 = next(n for n, c in CHARACTERS.items()
              if c.cost == 2 and n not in members
              and not getattr(c, 'bench_effect', ''))
    return comp, members, w, x, y0


def _elig_frame(y: str, *, y_third_star3: bool = False):
    """P92 ④资格维集成帧(方案稿 §④ 锁 A 构造,发现 3 修订后口径):

    - gold=100 > g*=50 过 r1 账/r2 预算门直达 P92 位(发现 3:金维
      ``gold<cost`` 在集成面不可达——r1 账要求 gold>g*,故 X 的④死
      改由「该级不可刷档」承载,金维死条件由锁 D 判定尺直调补钉);
    - X 对(∈buy_members)1★×2 + W 单张 1★(账合格集非空承载)+
      Y 对 1★×2 + 2★ 线外件补满 ⇒ bench 满 9;
    - 全局面零燃料件(1★ 非对名即线内零重叠排除,对名走 G-S1 拒入)
      ⇒ liquid_refund=0 ⇒ seat_recoverable=False ⇒ dominance/②死;
      EV 生产 fail-closed 死 ⇒ 修复后④是唯一可能活通道;
    - ``y_third_star3=True``:Y 追加 3★×1 上阵(全局面 3 副本)——
      修复前装配 ``_cnt(n,1)==2 ∧ _cnt(n,2)==0`` 仍算④可达、机器
      M2b 从不触发(len==3 skip)的形态维分叉面(锁 C)。
    """
    comp, members, w, x, _y0 = _elig_names()
    assert refresh_prob(4, CHARACTERS[x].cost) == 0.0   # X 该级不可刷(④对 X 死)
    assert refresh_prob(4, CHARACTERS[w].cost) > 0.0    # W r1 账合格集承载
    assert refresh_prob(4, CHARACTERS[y].cost) > 0.0    # Y 刷出维开着(④活性必要面)
    s = _session(comp, plane_lengths=[9, 5, 7], line_state=False)
    st = GameState(gold=100, level=4, plane=1, round_num=2,
                   node_type='reward', hp=100)
    formed = [m for m in members
              if m not in (w, x, y) and CHARACTERS[m].cost <= 3]
    st.deployed = [_bc(m, star=2, slot=i + 1)
                   for i, m in enumerate(formed[:5])]
    bench = [_bc(x, star=1, slot=1), _bc(x, star=1, slot=2),
             _bc(w, star=1, slot=1),
             _bc(y, star=1, slot=1), _bc(y, star=1, slot=2)]
    bench += [_bc(m, star=2, slot=1) for m in formed[5:]]
    if y_third_star3:
        st.deployed.append(_bc(y, star=3, slot=6))
    pool = iter(n for n, c in CHARACTERS.items()
                if n not in members and n != y
                and not getattr(c, 'bench_effect', ''))
    while len(bench) < 9:
        bench.append(_bc(next(pool), star=2, slot=1))
    assert len(bench) == 9   # 席满是 dominance/②死条件的承载前提
    st.bench = bench
    st.shop = []
    return st, s


class TestP92MergeEligibility:

    def test_out_of_line_pair_blocked_after_fix(self):
        """锁 A(病灶帧直锁):线外 1★×2 对(Y ∉buy_members)不再算
        ④可达,X 费档该级不可刷 ⇒ 四通道全死 ⇒ 拦刷 + 分键开火。
        修复前该帧恒放行(Y 费档 lv4 可刷 0.25 且 gold 足额,
        s10003 p2r1 同型,T-295 对抗审问题 6 转正)。"""
        _comp, members, _w, _x, y0 = _elig_names()
        assert y0 not in members   # 前提:Y 线外(资格维病灶成立)
        st, s = _elig_frame(y0)
        acts = _decide(st, s)
        assert not [a for a in acts if isinstance(a, RefreshShop)], acts
        assert not [a for a in acts if isinstance(a, BuyCard)], acts
        cnt = state_of(s).cw4_counters
        assert cnt.get('p92_no_buy_refresh_blocked', 0) >= 1
        assert cnt.get('must_spend_r1_no_buy_blocked', 0) >= 1

    def test_in_line_pair_refresh_passes(self):
        """锁 B(零误杀对照,发现/方案稿 §④-1-B):同构帧但 Y ∈
        buy_members(线成员 1★×2 对,费档该级可刷)⇒ ④真实可达 ⇒
        刷新放行、拦键恒零——资格维过滤不误杀采购集内真通道
        (ADR-0635「零合法支出被拦」后果线的保全锚)。"""
        _comp, members, _w, _x, _y0 = _elig_names()
        y = next(m for m in members if CHARACTERS[m].cost == 2)
        assert y in members      # 前提:Y 线内(真可达对照成立)
        st, s = _elig_frame(y)
        acts = _decide(st, s)
        assert [a for a in acts if isinstance(a, RefreshShop)], acts
        cnt = state_of(s).cw4_counters
        assert cnt.get('p92_no_buy_refresh_blocked', 0) == 0

    def test_pair_with_high_star_copy_blocked(self):
        """锁 C(形态维边角,方案稿 §3.3-2):Y ∈ buy_members 且全局面
        1★×2 + 3★×1(3 副本)——资格维放行后形态维是唯一防线:修复前
        装配按分星计数(``_cnt(n,1)==2 ∧ _cnt(n,2)==0``)算④可达,而
        机器 M2b 从不触发(len==3 skip)——形态条件两处复述的分叉面;
        修复后形态单一源判「非恰 2 全 1★」⇒ ④死 ⇒ 全死帧拦刷。
        helper 形态条件中性化(恰 2 放宽为 ≥2)本锁红(Y 取线内名,
        线外名会被资格维先行剔除而掩蔽形态变异——变异红证实测修正)。"""
        _comp, members, _w, _x, _y0 = _elig_names()
        y = next(m for m in members if CHARACTERS[m].cost == 2)
        assert y in members      # 前提:Y 线内(形态维为唯一防线)
        st, s = _elig_frame(y, y_third_star3=True)
        acts = _decide(st, s)
        assert not [a for a in acts if isinstance(a, RefreshShop)], acts
        cnt = state_of(s).cw4_counters
        assert cnt.get('p92_no_buy_refresh_blocked', 0) >= 1
