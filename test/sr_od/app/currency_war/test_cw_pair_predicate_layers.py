"""T-166 批1:ADR-0616 四层谓词结构单帧锁(门槛先行/排序维/燃料剔除/
在任优先/可行性门,逐层分立)。

设计出处(全部断言的单一出处,零拟合常数):
- 设计正本 = ADR-0616(docs/develop/sr_od/application/currency_war/decisions/
  0616-t166-pair-direction-predicate-ontology.md)§2.1 命题 1a(在任优先
  单席易手,严格大于,平手保持)/§2.3 命题 2(门槛过滤先行双量纲 +
  排除谓词 Ex_I + 排序维星级当量 + 第④格换算式)/§2.4 命题 3(可行性门
  E(alt)≤R_rem 后置合取,门拒 = 保持原对 + pair_gate 拒因分键);
- 方案正本 = .debug/temp/currency_war/T-166-方案v2.md §3.1(落码批 1
  规格);检测器豁免裁决 = §3.3 裁决②(编排者解除 ledger.py 零改动
  条款);early_pair 并批裁决 = §3.3 裁决①(编排者,T-166 批1 任务书
  前置裁决记录)。
- 数据锚 = 三批 sim 档案重演(重演 27→12→8 形态;残余 8/250 → prereg
  上界钉 ADR-0616 §6)。

四象限行为钉死(ADR-0616 §2.3,单帧锁钉死):①排序第一∧门槛达标 →
锁第一席;②星级当量第一∧门槛不达标 → 被门槛过滤剔除不入对;③排序
第二∧门槛达标 → 入第二席;④全不达标 → 空窗 ()。恒自洽式
pair≠() ⟺ Q≠∅ ⟺ gap_window=False 矛盾帧不存在(格 3)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel import cw_intention as ci
from sr_od.application.currency_war.kernel.cw_board_state import (
    BoardState,
    board_state_bridge,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
)

_PAIR_A = '持续伤害'
_PAIR_B = '列车同行'
_CHALL = '仙舟'   # 三系场景的挑战体系(与 A/B 无标签交叉的纯成员)


def _tags(name: str) -> set[str]:
    ch = CHARACTERS[name]
    return set(ch.factions or ()) | set(ch.flows or ())


def _sys_tagset(tag: str) -> set[str]:
    """体系键 → 板面羁绊键集(希儿系展开=量子同频+贝洛伯格,与
    ``_pair_bond_keys`` 同口径)。"""
    return {'量子同频', '贝洛伯格'} if tag == ci.SEELE_SYSTEM else {tag}


_TRANSITION_KEYS: tuple[str, ...] = ('仙舟', '列车同行', '持续伤害',
                                     ci.SEELE_SYSTEM)


def _pure_members(tag: str, k: int) -> list[str]:
    """体系纯成员名前 k 个:带该体系键 ∧ 不带其它三过渡体系键
    (系统外语标签——减益/欢愉等——无害,不影响四体系返回值;
    注册表演化导致前提不成立时由 _require_pure 显式红,禁静默漂移)。"""
    want = _sys_tagset(tag)
    forbid: set[str] = set()
    for other in _TRANSITION_KEYS:
        if other != tag:
            forbid |= _sys_tagset(other)
    return [n for n in CHARACTERS
            if want & _tags(n) and not forbid & _tags(n)][:k]


def _bc(names: list[str], stars: list[int] | None = None) -> list[BenchChar]:
    stars = stars or [1] * len(names)
    return [BenchChar(slot=i + 1, char_id=n, star=s)
            for i, (n, s) in enumerate(zip(names, stars, strict=False))]


def _p1_state(bench: list[BenchChar],
              board: dict | None = None) -> BoardState:
    """W6 波3:方向层谓词已切容器签名,旧 GameState 构面经过渡桥装箱。
    board 须随帧装箱(桥产出容器 Field 形态,装箱后裸 dict 覆写 = 打穿
    Field 契约,消费面 ``bs.board.value`` 必炸)。"""
    st = GameState(gold=10, level=5, plane=1, round_num=5, hp=100)
    st.bench = bench
    st.deployed = []
    if board:
        st.board = dict(board)
    return board_state_bridge(st)


def _require_pure(tag: str, k: int) -> list[str]:
    names = _pure_members(tag, k)
    assert len(names) >= k, \
        f'锁前提失效:注册表 {tag} 纯成员不足 {k} 个(注册表演化,先重推本锁)'
    return names


def _amp_members(k: int) -> list[str]:
    """希儿系放大器成员(量子同频∨贝洛伯格键 ∧ 不带三羁绊键 ∧ 非希儿;
    ADR-0608 放大器池口径)。"""
    forbid = {'仙舟', '列车同行', '持续伤害'}
    return [n for n in CHARACTERS
            if n != '希儿'
            and ({'量子同频', '贝洛伯格'} & _tags(n))
            and not forbid & _tags(n)][:k]


# ===== 层一:门槛过滤先行(命题 2 组合谓词的 Q 面) =====

class TestGateFirstLayer:
    """门槛先行:两席都查 1.0,第二席零资格不再入对(ADR-0616 §2.1
    边缘帧申报「有意行为变更」;四象限②/④)。"""

    def test_single_qualified_system_yields_unit_pair(self) -> None:
        """|Q|=1 → 1 元对(ADR 在册边缘帧):Q 恰一系时派生单系对,
        禁造第二席(旧「ranked[:2] 直取」语义已被门槛先行政写,
        重推记录 = test_cw_seele_support 旧仙舟垫位格 docstring)。"""
        names = _require_pure(_PAIR_A, 2)
        st = _p1_state(_bc(names[:2]))
        pair = ci._derive_p1_pair(st)
        assert pair == (_PAIR_A,)
        assert ci.p1_gap_window(st) is False

    def test_second_seat_zero_qualification_excluded(self) -> None:
        """四象限②:排序/旧支持度第二但门槛不达标 → 不入对
        (宁可空席不提前承诺,ADR-0519 C2 保守方向同向)。"""
        a = _require_pure(_PAIR_A, 2)
        c = _require_pure(_CHALL, 1)
        st = _p1_state(_bc(a[:2] + c[:1]))
        sup = ci._p1_system_support(st)
        assert sup[_PAIR_A] >= 1.0 and sup[_CHALL] < 1.0   # 前提
        pair = ci._derive_p1_pair(st)
        assert pair == (_PAIR_A,) and _CHALL not in pair

    def test_gap_window_equivalence_invariant(self) -> None:
        """恒自洽式 pair≠() ⟺ Q≠∅ ⟺ gap_window=False(四象限④;
        矛盾帧不存在由同源派生保证,ADR-0616 §2.3)。"""
        a = _require_pure(_PAIR_A, 2)
        st_sub = _p1_state(_bc(a[:1]))       # 单成员:门槛维 0.5 < 1.0
        assert ci._derive_p1_pair(st_sub) == ()
        assert ci.p1_gap_window(st_sub) is True
        st_ok = _p1_state(_bc(a[:2]))
        assert ci._derive_p1_pair(st_ok) != ()
        assert ci.p1_gap_window(st_ok) is False


# ===== 层二:排序维(星级当量,合成中性) =====

class TestOrderingDimensionLayer:
    """排序维 = Σ3^(star−1)/tier(三羁绊系逐副本)+ 第④格换算式
    (希儿系);与门槛维双量纲分立,原语禁互换(ADR-0616 §2.3,
    坐标系声明 = ADR-0608 + _seele_system_support docstring)。"""

    def test_synthesis_neutral(self) -> None:
        """3×1★ → 1×2★ 排序维不变(合成中性;治「合成被记为倒退」
        的信号损坏,24/26 污染通道的合成半边)。仙舟 tier=3:
        3×1★ 与 1×2★ 的星级当量同为 3 → 排序维同为 1.0。"""
        names = _require_pure(_CHALL, 3)
        st_three = _p1_state(_bc(names[:3], [1, 1, 1]))
        st_merged = _p1_state(_bc(names[:1], [2]))
        o_three = ci._p1_system_ordering(st_three, ())
        o_merged = ci._p1_system_ordering(st_merged, ())
        assert o_three[_CHALL] == o_merged[_CHALL] == 1.0

    def test_normalized_ratio_full_tier_cross_system(self) -> None:
        """满档 = 1.0 跨体系可比(归一化比值,消绝对当量偏置);
        2★ 成员抬排序维超 1.0(无帽,超满档可 >1.0)。"""
        a = _require_pure(_PAIR_A, 2)
        assert ci._p1_system_ordering(_p1_state(_bc(a)), ())[_PAIR_A] == 1.0
        c = _require_pure(_CHALL, 3)
        st = _p1_state(_bc(c, [2, 1, 1]))
        assert ci._p1_system_ordering(st, ())[_CHALL] \
            == pytest.approx((3 + 1 + 1) / 3)

    def test_seele_fourth_quadrant_formula(self) -> None:
        """第④格换算式:min(1.0, max(u_量/2, u_贝/2)),u = 去重成员
        星级当量(ADR-0616 §2.3 五项推导链)。"""
        amps = _amp_members(1)
        assert amps, '锁前提失效:注册表无放大器成员(注册表演化,先重推)'
        amp = amps[0]
        # 希儿 1★ 单卡:u_量=u_贝=1 → 0.5(与 ADR-0608 推导后果一致)
        st_half = _p1_state(_bc(['希儿']))
        assert ci._p1_system_ordering(st_half, ())[ci.SEELE_SYSTEM] == 0.5
        # 希儿+1 放大器:u=2 → 封顶 1.0
        st_full = _p1_state(_bc(['希儿', amp]))
        assert ci._p1_system_ordering(st_full, ())[ci.SEELE_SYSTEM] == 1.0
        # 希儿 2★ 单卡:u=3 → min(1.0, 1.5)=1.0(厚度语义,门槛维仍 0.5)
        st_star2 = _p1_state(_bc(['希儿'], [2]))
        assert ci._p1_system_ordering(st_star2, ())[ci.SEELE_SYSTEM] == 1.0
        assert ci._p1_system_support(st_star2)[ci.SEELE_SYSTEM] == 0.5
        # 无希儿:排序维恒 0(与门槛维「不独立」同构)
        st_no_seele = _p1_state(_bc([amp]))
        assert ci._p1_system_ordering(st_no_seele, ())[ci.SEELE_SYSTEM] == 0.0

    def test_ordering_gate_independent_dims(self) -> None:
        """双量纲分立直证:同板面门槛维并列(1.0/1.0)、排序维分层
        (2★ 厚度只在排序维可见)——门槛维答「羁绊激活几成」、排序维
        答「投入叠了多少」(坐标系声明,禁互换)。"""
        a = _require_pure(_PAIR_A, 2)
        c = _require_pure(_CHALL, 3)
        st = _p1_state(_bc(a + c, [1, 1, 2, 1, 1]))
        sup = ci._p1_system_support(st)
        assert sup[_PAIR_A] == 1.0 and sup[_CHALL] == 1.0   # 门槛维并列
        ordv = ci._p1_system_ordering(st, ())
        assert ordv[_PAIR_A] == 1.0
        assert ordv[_CHALL] == pytest.approx(5 / 3)         # 排序维分层


# ===== 层三:燃料剔除(排除谓词 Ex_I) =====

class TestFuelExclusionLayer:
    """排除谓词 Ex_I(P41② 燃料类单一源):1★ ∧ 全额可退 ∧ ∉K(I)
    的副本不携带方向证据(命题 2 封闭性 (i)「排序维逐系计数对燃料类
    增量封闭」);卫语句 I=() ⟹ Ex≡False。"""

    def test_fuel_increment_closed_with_incumbent(self) -> None:
        """在任对存在期,1★ 非成员燃料到货 → 排序维逐系零变化
        (s661 型「离对买入推高挑战系」的计票端切断)。"""
        a = _require_pure(_PAIR_A, 2)
        b = _require_pure(_PAIR_B, 2)
        c = _require_pure(_CHALL, 2)
        inc = (_PAIR_A, _PAIR_B)
        st_base = _p1_state(_bc(a + b))
        st_fuel = _p1_state(_bc(a + b + c))
        assert ci._p1_system_ordering(st_base, inc) \
            == ci._p1_system_ordering(st_fuel, inc), \
            '燃料类增量未被封闭:排序维随 1★ 非成员到货漂移'

    def test_incumbent_member_1star_counts(self) -> None:
        """K(I) 成员的 1★ 副本照计(排除谓词第三合取支 ∉K(I) 的
        反向格:在任体系自身补员不是燃料)。"""
        a = _require_pure(_PAIR_A, 3)
        inc = (_PAIR_A,)
        base = ci._p1_system_ordering(_p1_state(_bc(a[:2])), inc)
        grown = ci._p1_system_ordering(_p1_state(_bc(a[:3])), inc)
        assert grown[_PAIR_A] > base[_PAIR_A]

    def test_twostar_non_member_counts(self) -> None:
        """2★ 非成员照计(排除谓词 star==1 合取支:星级纪律只剔
        1★ 全额可退件,2★ 已沉淀合成成本不再是燃料,ADR-0580 口径):
        同一非成员件 1★ 时被剔除(排序维 0),升 2★ 后计入 3/tier。"""
        c = _require_pure(_CHALL, 1)
        inc = (_PAIR_A,)
        st_1star = _p1_state(_bc(c[:1]))
        st_2star = _p1_state(_bc(c[:1], [2]))
        assert ci._p1_system_ordering(st_1star, inc)[_CHALL] == 0.0
        assert ci._p1_system_ordering(st_2star, inc)[_CHALL] \
            == pytest.approx(1.0)

    def test_empty_incumbent_guard_no_exclusion(self) -> None:
        """卫语句:I=() ⟹ Ex≡False(空窗期 1★ 全额可退件照计——
        无此卫则空窗被误排除,与空窗语义相反;命题方案审 F11)。"""
        c = _require_pure(_CHALL, 2)
        st = _p1_state(_bc(c))
        assert ci._p1_system_ordering(st, ())[_CHALL] \
            == pytest.approx(2 / 3)

    def test_refund_full_clause_is_load_bearing(self, monkeypatch) -> None:
        """refund_full 合取支显式在判据(P41② 类资格条款):退金表
        改动(1★ 不再全额可退)时排除自动失配退出——禁静默失配
        (ADR-0616 §2.3;kernel 侧与买侧同源读 sell_refund)。"""
        c = _require_pure(_CHALL, 2)
        inc = (_PAIR_A,)
        st = _p1_state(_bc(c))
        closed = ci._p1_system_ordering(st, inc)[_CHALL]
        real_refund = ci.sell_refund

        def _half_refund(star: int, cost: int) -> int:
            # 模拟退金表改动:1★ 只退半价(不再全额可退)
            return max(cost // 2, 0) if star == 1 else real_refund(star, cost)

        monkeypatch.setattr(ci, 'sell_refund', _half_refund)
        open_dim = ci._p1_system_ordering(st, inc)[_CHALL]
        assert closed == 0.0 and open_dim > 0.0


# ===== 层四:在任优先单席易手(命题 1a 夺席算子) =====

class TestIncumbentEasementLayer:
    """T(ord, I, Q):平手保持(严格大于)/只换最弱席/每帧至多一席/
    空席填充无条件(ADR-0616 §2.1;支配性论证消参数,零新数值)。"""

    def _two_system_board(self, a_stars: list[int],
                          b_stars: list[int]) -> GameState:
        a = _require_pure(_PAIR_A, len(a_stars))
        b = _require_pure(_PAIR_B, len(b_stars))
        return _p1_state(_bc(a + b, a_stars + b_stars))

    def test_tie_keeps_incumbent(self) -> None:
        """挑战者排序维并列 → 不易手(平手 = 零优势证据,不换席弱支配
        换席;严格大于门,零参数滞回域 = 全部平手域)。"""
        inc = (_PAIR_A, _PAIR_B)
        st = self._two_system_board([1, 1], [1, 1])
        pair, cand = ci._p1_pair_eased(st, inc)
        assert pair == inc and cand is None

    def test_strictly_greater_displaces_weakest_only(self) -> None:
        """挑战者严格超出最弱席 → 产出换席候选:留任强席 + 挑战者
        (单席易手 = 支配性论证直接闭包,并集读法无独立辩护);
        候选由调用方过命题 3 门后生效(本层只锁算子本体)。"""
        inc = (_PAIR_A, _PAIR_B)
        # 在任:DOT 弱(2×1★=1.0)、列车强(2★+1★=2.0);
        # 挑战:仙舟 2★+2★+1★(1★ 燃料剔除)→ ord = 6/3 = 2.0 > 1.0
        a = _require_pure(_PAIR_A, 2)
        b = _require_pure(_PAIR_B, 2)
        c = _require_pure(_CHALL, 3)
        st = _p1_state(_bc(a + b + c, [1, 1, 2, 1, 2, 2, 1]))
        ordv = ci._p1_system_ordering(st, inc)
        assert ordv[_PAIR_A] == pytest.approx(1.0)      # 最弱席(前提)
        assert ordv[_PAIR_B] == pytest.approx(2.0)      # 强席(前提)
        assert ordv[_CHALL] == pytest.approx(2.0)       # 严格超出最弱席
        pair, cand = ci._p1_pair_eased(st, inc)
        assert pair == inc                              # 算子只产候选不落对
        assert cand == (_CHALL, _PAIR_B)                # 强席保持,弱席让位
        assert len(cand) == 2 and len(set(cand) ^ set(inc)) == 2  # 恰一席易手

    def test_empty_seat_fill_unconditional_no_gate(self) -> None:
        """|I∩Q|=1:留任席无条件保持 + 最佳挑战者填空席(不触动已占用
        席 = §2.3(iv) 申报帧类;不辖可行性门,ADR-0616 §2.4 辖域)。"""
        a = _require_pure(_PAIR_A, 2)
        b = _require_pure(_PAIR_B, 2)
        st = _p1_state(_bc(a + b))
        pair, cand = ci._p1_pair_eased(st, (_PAIR_A,))
        assert pair == (_PAIR_A, _PAIR_B) and cand is None

    def test_empty_window_entry_takes_ordering_top2(self) -> None:
        """|I∩Q|=0 空窗进入:按 (−ord, PREF) 取前 min(2,|Q|) 席
        (排序维定序,平手 PREF 只定确定性)。"""
        a = _require_pure(_PAIR_A, 3)
        b = _require_pure(_PAIR_B, 2)
        # DOT 2★+1★+1★ → ord 2.5;列车 2×1★ → ord 1.0;两系门槛均过
        st = _p1_state(_bc(a + b, [2, 1, 1, 1, 1]))
        pair, cand = ci._p1_pair_eased(st, ())
        assert pair == (_PAIR_A, _PAIR_B) and cand is None

    def test_unfrozen_swap_events_and_gate_wiring(self, monkeypatch) -> None:
        """状态机接线(门拒 = 保持原对 + pair_gate 拒因分键;过门换席 =
        pair_gate 路由子键;ADR-0616 §2.4/§4 事件分键三子键之二)。"""
        inc = (_PAIR_A, _PAIR_B)
        a = _require_pure(_PAIR_A, 2)
        b = _require_pure(_PAIR_B, 2)
        c = _require_pure(_CHALL, 3)
        st = _p1_state(_bc(a + b + c, [1, 1, 2, 1, 2, 2, 1]))
        ist = ci.IntentionState(p1_pair=inc)
        monkeypatch.setattr(ci, '_p1_pair_gate',
                            lambda pair, state, registry=None, session=None:
                            (False, 99.0, 3))
        ist = ci.update_intention(st, ist)
        assert ist.p1_pair == inc                       # 门拒 = 保持原对
        assert ist.last_event.startswith('pair_gate:deny'), ist.last_event
        monkeypatch.setattr(ci, '_p1_pair_gate',
                            lambda pair, state, registry=None, session=None:
                            (True, 1.5, 19))
        ist = ci.update_intention(st, ist)
        assert ist.p1_pair == (_CHALL, _PAIR_B)   # PREF 序:仙舟在前
        assert ist.last_event.startswith('pair_gate:route:'), ist.last_event

    def test_gate_not_consulted_on_entry_and_fill(self, monkeypatch) -> None:
        """门辖域(§2.4):不辖空窗首进帧、不辖空席填充帧——门被咨询
        即红(哨兵注入;禁把门漏进非辖帧类)。"""
        def _forbidden(*_a, **_k):
            raise AssertionError('可行性门辖了非辖帧类(空窗首进/空席填充)')

        a = _require_pure(_PAIR_A, 2)
        b = _require_pure(_PAIR_B, 2)
        monkeypatch.setattr(ci, '_p1_pair_gate', _forbidden)
        pair, cand = ci._p1_pair_eased(_p1_state(_bc(a + b)), ())
        assert pair == (_PAIR_A, _PAIR_B) and cand is None
        pair, cand = ci._p1_pair_eased(_p1_state(_bc(a + b)), (_PAIR_A,))
        assert pair == (_PAIR_A, _PAIR_B) and cand is None

    def test_gate_reads_overwindow_single_source(self) -> None:
        """门 = 超窗出口同一比较单一源(取反薄壳;E/R_rem 读法零第二
        估计器,ADR-0616 §2.4 与 P84 五条款 2 共享测量单一源)。"""
        st = _p1_state(_bc(_require_pure(_PAIR_A, 2)))
        over, e_f, r_rem = ci._p1_pair_overwindow((_PAIR_A,), st)
        ok, e_g, r_g = ci._p1_pair_gate((_PAIR_A,), st)
        assert ok == (not over) and e_g == e_f and r_g == r_rem

    def test_single_effective_write_per_field_per_frame(self, monkeypatch) -> None:
        """单帧每字段至多一次有效变更(P84 五条款 4 本件侧自缚;
        写点全集行为面扫描 = 闩→抑制→出口→封印保持→门拒→过门换席)。
        按真子集建 = 假红源(ADR-0616 §2.2),故扫全序列逐帧断言。"""
        watched = ('p1_pair', 'p1_pair_frozen', 'p1_pair_frozen_pair',
                   'p1_pair_refreeze_hold', 'transition_pair')

        class _Watch(ci.IntentionState):
            def __setattr__(self, name, value):
                if name in watched:
                    old = getattr(self, name, None)
                    if old != value:
                        changes = self.__dict__.setdefault('_chg', {})
                        changes[name] = changes.get(name, 0) + 1
                object.__setattr__(self, name, value)

        a = _require_pure(_PAIR_A, 2)
        b = _require_pure(_PAIR_B, 2)
        c = _require_pure(_CHALL, 3)
        over_flag = [False]
        monkeypatch.setattr(
            ci, '_p1_pair_overwindow',
            lambda pair, state, session=None, registry=None:
            (over_flag[0], 99.0, 3))
        # 帧1 闩(板满 fp=1)/帧2 冻结抑制/帧3 超窗出口+封印/
        # 帧4 封印保持(fp=1 不回落,事件 hold)/帧5 门拒换席(fp<1 回落
        # 解封)/帧6 过门换席(over 关 → 门放行)
        form_ok = {'board': {_PAIR_A: 2, _PAIR_B: 2}}
        swap_bench = _bc(a + b + c, [1, 1, 2, 1, 2, 2, 1])
        # 板面字典随帧装箱(W6 波3:桥产物是容器 Field 形态,禁装箱后
        # 裸 dict 覆写);空板帧不喂 board = 未观察(读口 ``or {}`` 同判)。
        frames = [
            (_p1_state(_bc(a + b), form_ok), False),
            (_p1_state(_bc(a + b), form_ok), False),
            (_p1_state(_bc(a + b), form_ok), True),
            (_p1_state(_bc(a + b), form_ok), True),
            (_p1_state(swap_bench), True),
            (_p1_state(swap_bench), False),
        ]
        ist = _Watch()
        object.__setattr__(ist, '_chg', {})   # dataclass 构造期写入不计
        for fi, (st, over) in enumerate(frames):
            over_flag[0] = over
            ist = ci.update_intention(st, ist)
            chg = getattr(ist, '_chg', {})
            for name in watched:
                assert chg.get(name, 0) <= 1, \
                    f'帧{fi + 1} 字段 {name} 有效变更 ' \
                    f'{chg.get(name, 0)} 次 >1(写点全集自缚)'
            object.__setattr__(ist, '_chg', {})


# ===== 层五:p1_early_pair 并批(§3.3 裁决①) =====

class TestEarlyPairMergeLayer:
    """early_pair 并入在任纪律:同一易手算子作用于无门槛合格集
    (裁决①);玩法论证 = cw_intention.p1_early_pair docstring。"""

    def test_locked_frame_fields_take_priority(self) -> None:
        """锁定帧优先意向字段(既有语义零改动):transition_pair >
        p1_pair > 现场派生。"""
        st = _p1_state([])
        ist = ci.IntentionState(p1_pair=(_PAIR_A, _PAIR_B))
        assert ci.p1_early_pair(st, ist) == (_PAIR_A, _PAIR_B)
        ist2 = ci.IntentionState(transition_pair=(_PAIR_B, _CHALL))
        assert ci.p1_early_pair(st, ist2) == (_PAIR_B, _CHALL)

    def test_subgate_entry_uses_ordering_dim(self) -> None:
        """sub-gate 帧方向 = 排序维 top-2(无门槛合格集):与旧门槛维
        top-2 的集合差异直证(排序维分层可见,门槛维不可见)。"""
        a = _require_pure(_PAIR_A, 2)
        b = _require_pure(_PAIR_B, 3)
        c = _require_pure(_CHALL, 3)
        # DOT [2★,1★]:sup 1.0 / ord 2.0;列车 [1★×3]:sup 1.5 / ord 1.5;
        # 仙舟 [2★,1★,1★]:sup 1.0 / ord 5/3(I=() 无燃料剔除)
        st = _p1_state(_bc(a + b + c, [2, 1, 1, 1, 1, 2, 1, 1]))
        # 门槛维序:列车 1.5 > DOT 1.0 = 仙舟 1.0(PREF 取仙舟)
        sup = ci._p1_system_support(st)
        assert sup[_PAIR_B] == pytest.approx(1.5)
        assert sup[_PAIR_A] == 1.0 and sup[_CHALL] == 1.0
        # 排序维序:DOT 2.0 > 仙舟 5/3 ≈1.67 > 列车 1.5
        ordv = ci._p1_system_ordering(st, ())
        assert ordv[_PAIR_A] == pytest.approx(2.0)
        assert ordv[_CHALL] == pytest.approx(5 / 3)
        assert ordv[_PAIR_B] == pytest.approx(1.5)
        pair = ci.p1_early_pair(st, None)
        assert pair == (_CHALL, _PAIR_A), \
            f'early 方向未按排序维 top-2 并批: {pair}'


if __name__ == '__main__':
    import pytest
    raise SystemExit(pytest.main([__file__, '-v']))
