"""T-171 批2:希儿系支持度分级公式单帧锁(支持度端口降档)。

设计出处:T-171 设计方案 §5.1/§6.3-4(账本任务 T-171,辅助出处 =
.debug/temp/currency_war/attacks/t171_xierie_criteria/设计方案.md);
判据源 = docs/game/currency_war/research/transition_combos.md:27
(希儿系 = 希儿在场 AND(量≥2 ∨ 贝≥2))+ combo_methodology.md:138
(希儿到手 ≠ 希儿线成型)+ 注册表锚 cw_chars.CHARACTERS['希儿']
(factions=('贝洛伯格',), flows=('量子同频',),data/cw_chars.py「希儿」行)。

锁的是设计语义(§6.3-4 锁清单),不锁具体卡面;被取代的旧语义
「希儿在手二元 1.0 即锁」(ADR-0519 C2 post-state)的锁红重推记录
见 test_cw_lock_path_obs_keys.py::test_frozen_pair_snapshot_lifecycle
docstring。变异验证已实跑:公式回退「到手即 1.0」时本文件单卡组
断言必红(TestSeeleSupportFormula 五格)。
"""
from __future__ import annotations

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel import cw_intention as ci
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState


def _bc(name: str, slot: int, star: int = 1) -> BenchChar:
    """BenchChar 构造 helper(与 test_cw_lock_path_obs_keys 同式)。"""
    ch = CHARACTERS[name]
    return BenchChar(slot=slot, char_id=name,
                     faction=(ch.factions or ['?'])[0],
                     position_pref=ch.position_pref(), star=star)


def _p1_state(bench: list[BenchChar]) -> GameState:
    """P1 支持度直调态(plane/round 仅为 GameState 必要字段)。"""
    st = GameState()
    st.plane = 1
    st.round_num = 3
    st.bench = bench
    return st


class TestSeeleSupportFormula:
    """§6.3-4 支持度分级锁(去重成员计数,含星级态)。

    每格断言 support 值 + 消费面行为(_derive_p1_pair 锁线/p1_gap_window
    空窗),三者同源共锁,防「公式对、消费面断线」的双源形态。
    """

    def test_single_seele_1star_half_support_not_lockable(self):
        """1★ 希儿单卡 = 0.5:开线候选(>0 可进 top-2 排序)但不满足
        锁线门槛 1.0(不再即锁),gap_window=True(K 回退囤货门开)。
        出处 = T-171 设计方案 §5.1 行为性质 + §6.3-4 第 4 格第 1 项;
        文档语义 = 「希儿到手 ≠ 希儿线成型」(combo_methodology.md:138)。"""
        st = _p1_state([_bc('希儿', 0)])
        sup = ci._p1_system_support(st)
        assert sup[ci.SEELE_SYSTEM] == 0.5
        assert ci._derive_p1_pair(st) == ()      # 不锁(门槛 1.0 未达)
        assert ci.p1_gap_window(st) is True      # 空窗回退门开

    def test_single_seele_2star_half_support_synthesis_neutral(self):
        """2★ 希儿单卡仍 = 0.5(F5 的 2★ 矛盾格,方案审 F5 裁决锚):
        去重成员计数对合成零扰动——星级提升不抬高支持度,单张 2★ 零
        放大器不满锁(当量原语 Σ3^(star−1) 下会 1.0 满锁,被 F5 否决)。"""
        st = _p1_state([_bc('希儿', 0, star=2)])
        assert ci._p1_system_support(st)[ci.SEELE_SYSTEM] == 0.5
        assert ci._derive_p1_pair(st) == ()

    def test_seele_plus_one_amplifier_full_support_lockable(self):
        """希儿 + 任 1 去重放大器 = 1.0(锁线证据成立):两腿对称验——
        量子腿(希儿+缇宝)与贝腿(希儿+桑博)各达文档 OR 档位之一
        (÷2 档位 + max 取最好腿的 OR 结构,transition_combos.md:27)。"""
        for amp in ('缇宝', '桑博'):
            st = _p1_state([_bc('希儿', 0), _bc(amp, 1)])
            sup = ci._p1_system_support(st)
            assert sup[ci.SEELE_SYSTEM] == 1.0, f'腿 {amp} 未满支持'
            pair = ci._derive_p1_pair(st)
            assert ci.SEELE_SYSTEM in pair, f'腿 {amp} 未进锁对'

    def test_seele_plus_three_copies_same_amplifier_dedup_full(self):
        """「希儿 + 3×1★ 同名放大器」态 = 1.0(设计 §6.3-4 第 4 格):
        去重后成员 = {希儿, 该件} = 2,贝腿激活证据成立——与合并后
        部署的板面语义一致(合成前后支持度不变,去重中性的直接验证)。"""
        st = _p1_state([_bc('希儿', 0), _bc('桑博', 1),
                        _bc('桑博', 2), _bc('桑博', 3)])
        assert ci._p1_system_support(st)[ci.SEELE_SYSTEM] == 1.0

    def test_amplifier_cap_at_full_support(self):
        """支持度封顶 1.0:希儿 + 4 名去重量子放大器(c_量=5)不超 1.0
        (min 封顶;超额成员不产生超额支持度,与三羁绊系逐副本可 >1.0
        的口径分界在 _seele_system_support docstring 坐标系声明)。"""
        st = _p1_state([_bc('希儿', 0), _bc('缇宝', 1), _bc('花火', 2),
                        _bc('符玄', 3), _bc('银狼', 4)])
        assert ci._p1_system_support(st)[ci.SEELE_SYSTEM] == 1.0

    def test_mixed_pools_full_support(self):
        """希儿 + 两池各 1 件 = 1.0:量/贝两腿同时达档,OR-max 语义下
        与单腿达档同值(双腿齐不叠加、不超 1.0)。"""
        st = _p1_state([_bc('希儿', 0), _bc('缇宝', 1), _bc('桑博', 2)])
        assert ci._p1_system_support(st)[ci.SEELE_SYSTEM] == 1.0

    def test_no_seele_amplifiers_not_independent(self):
        """无希儿 + 任意多放大器 = 0(不独立,§6.3-4 第 4 格第 4 项):
        量/贝不能独立当过渡(含希儿 28 帖无一缺希儿独立成线);锁线
        与空窗判定均不因纯放大器资产翻转。"""
        st = _p1_state([_bc('缇宝', 0), _bc('花火', 1),
                        _bc('桑博', 2), _bc('佩拉', 3)])
        sup = ci._p1_system_support(st)
        assert sup[ci.SEELE_SYSTEM] == 0.0
        assert ci._derive_p1_pair(st) == ()
        assert ci.p1_gap_window(st) is True


class TestNonSeeleZeroDrift:
    """非希儿对支持度路径零触碰直调锁(设计 §5.2 零漂移申报的实现锚)。

    断言钉值 = 改动前直调实测基线(探针 .debug/temp/t171_support_probe.py
    改动前后两跑对拍,非希儿态逐键相等);三羁绊系腿逐副本计数的现状
    语义一并钉住(含同名双副本合成态与 per-copy >1.0 形态)——未来任何
    对三羁绊系口径的变更必须先重推本组锁,禁机械跟绿。
    """

    def test_dot_full_support_unchanged(self):
        """桑博+卡芙卡(DOT 满员)= 1.0:三羁绊系腿口径不变(ADR-0519
        满员当量),希儿系 0,pair 仍含仙舟垫位(基线 A 态逐键值)。"""
        st = _p1_state([_bc('桑博', 0), _bc('卡芙卡', 1)])
        assert ci._p1_system_support(st) == {
            '仙舟': 0.0, '列车同行': 0.0, '希儿系': 0.0, '持续伤害': 1.0}
        assert list(ci._derive_p1_pair(st)) == ['仙舟', '持续伤害']
        assert ci.p1_gap_window(st) is False

    def test_duplicate_copies_per_copy_counting_unchanged(self):
        """同名双副本合成态(桑博 1★+2★):三羁绊系腿仍逐副本计数
        (DOT = 2/2 = 1.0),希儿系缺席恒 0——本批只动希儿系两腿,
        逐副本/去重两口径在非希儿态零交叉(基线 D 态逐键值)。"""
        st = _p1_state([_bc('桑博', 0), _bc('桑博', 1, star=2)])
        assert ci._p1_system_support(st) == {
            '仙舟': 0.0, '列车同行': 0.0, '希儿系': 0.0, '持续伤害': 1.0}

    def test_pure_amplifier_board_gap_unchanged(self):
        """纯放大器板面(基线 B 态):希儿系 0、仙舟 1/3(符玄双标签)、
        gap=True——空窗判定不因支持度降档批变化。"""
        st = _p1_state([_bc('缇宝', 0), _bc('花火', 1),
                        _bc('符玄', 2), _bc('银狼', 3)])
        assert ci._p1_system_support(st) == {
            '仙舟': 1 / 3, '列车同行': 0.0, '希儿系': 0.0, '持续伤害': 0.0}
        assert ci.p1_gap_window(st) is True

    def test_seele_plus_amplifier_full_state_unchanged(self):
        """希儿+3×1★ 同名放大器全帧(基线 H 态):希儿系去重 = 1.0 与
        旧二元值同格(变化只在单卡态),三羁绊系 per-copy 可 >1.0
        (DOT = 3/2 = 1.5)的现有口径如实钉住——同一返回 dict 内两套
        计数口径并存的可见样本。"""
        st = _p1_state([_bc('希儿', 0), _bc('桑博', 1),
                        _bc('桑博', 2), _bc('桑博', 3)])
        assert ci._p1_system_support(st) == {
            '仙舟': 0.0, '列车同行': 0.0, '希儿系': 1.0, '持续伤害': 1.5}
        assert list(ci._derive_p1_pair(st)) == ['持续伤害', '希儿系']


class TestConsumerFacesIntermediateBand:
    """消费面行为锁(设计 §5.2 消费面三处的前两处语义改善锚;
    p1_early_pair 属排序值变化,其 top-2 序由 _P1_PAIR_PREF 既有
    平手序承载,不另锁序——序常数锁归 _P1_PAIR_PREF 既有锚)。"""

    def test_gap_window_true_for_single_seele(self):
        """K 空窗回退门:希儿单卡帧 gap=True(旧码 False)——空窗期
        囤货回退 hoard 全集的判定按文档口径走(支持度 < 门槛 1.0)。"""
        st = _p1_state([_bc('希儿', 0)])
        assert ci.p1_gap_window(st) is True

    def test_lock_pair_requires_full_support(self):
        """锁线派生:单卡 0.5 不产锁对;+1 去重放大器(贝腿 桑博)即
        产锁对且含希儿系——锁点 = 开线点,与文档「引擎达成那一刻切
        希儿直通模式」同构(设计 §5.1 行为性质)。"""
        single = _p1_state([_bc('希儿', 0)])
        assert ci._derive_p1_pair(single) == ()
        paired = _p1_state([_bc('希儿', 0), _bc('桑博', 1)])
        pair = ci._derive_p1_pair(paired)
        assert ci.SEELE_SYSTEM in pair
        assert ci.p1_gap_window(paired) is False


if __name__ == '__main__':
    import pytest
    raise SystemExit(pytest.main([__file__, '-v']))
