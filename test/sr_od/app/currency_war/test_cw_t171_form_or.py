"""T-171 批序 1:形态端口 OR 语义单帧锁(希儿系成型判据按文档口径放宽)。

出处(全部文档/注册表定义量,零拟合常数):
- 文档口径 = transition_combos.md:27 希儿系定义表行「希儿在场 AND
  (量子同频≥2 OR 贝洛伯格≥2)」+ combo_methodology.md:133「凑到任一=
  成型」/:138「希儿到手 ≠ 希儿线成型」/:143「放大器不需要最大档,有就
  行」——AND 全档口径(借 cw_recipe 完全体档)被 ADR-0613 取代(先例 =
  ADR-0608→0519 post-state 取代形态);
- 命题/方案审 = .debug/temp/currency_war/attacks/t171_xierie_criteria/
  命题_批序1_形态端口OR.md + 方案审_批序1.md(放行附 5 低项,F1-F5 随批
  吸收进 ADR-0613);单帧锁清单 = 设计方案 §6.3-1/2/3(形态端口批辖域);
- 辖域切分(机械可检验,见 TestPortSeparation):形态端口读板面羁绊
  计数(board → form_progress),支持度端口(批序 2)读 owned 去重成员
  计数(_seele_system_support)——form 链禁出现支持度消费。

变异红证(OR 退 AND):把 pair_target_comp 希儿对分支改回「放大器档进
form_tiers(and 账)」→ test_or_leg_achieves_form_ok(量2 达成帧)与
test_nested_inclusion_grid(包含格)红;亲测红证记录见 ADR-0613 §验收。
"""
from __future__ import annotations

import itertools

import pytest

from sr_od.application.currency_war.kernel.cw_comps import form_progress
from sr_od.application.currency_war.kernel.cw_intention import (
    SEELE_CARRY_CHAR,
    SEELE_OR_LEGS,
    pair_target_comp,
)
from sr_od.application.currency_war.kernel.cw_launch_admission import (
    readiness_form_ok,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
)

_SEELE_PAIR: tuple[str, ...] = ('列车同行', '希儿系')
_OTHER_PAIR: tuple[str, ...] = ('仙舟', '持续伤害')


def _frame(board: dict[str, int], deployed: tuple[str, ...] = ()) -> GameState:
    """最小对局帧:board 羁绊计数 + 在板名单(判据只读这两样)。"""
    st = GameState(gold=10, level=5, plane=1, round_num=5, hp=100)
    st.board = dict(board)
    st.deployed = [BenchChar(slot=i + 1, char_id=n, star=1)
                   for i, n in enumerate(deployed)]
    return st


@pytest.fixture(scope='module')
def seele_comp():
    return pair_target_comp(_SEELE_PAIR)


# ===== §6.3-1 伪 comp 构造锁(含非希儿对零漂移锚)=====

class TestPseudoCompShape:
    def test_seele_pair_shape(self, seele_comp) -> None:
        """希儿系对:form_tiers 只含他体系档 + or_legs 两放大器腿 +
        required_deployed=carry;板面键集仍含量/贝(部署/评分视图不盲)。"""
        assert seele_comp is not None
        assert seele_comp.form_tiers == {'列车同行': 2}
        assert list(seele_comp.or_legs) == [('量子同频', 2), ('贝洛伯格', 2)]
        assert seele_comp.required_deployed == ('希儿',)
        assert set(seele_comp.factions) == {'列车同行', '量子同频', '贝洛伯格'}
        assert '希儿' in seele_comp.core_chars

    def test_or_legs_constant_single_source(self) -> None:
        """or_legs 档位来自模块常量单一源(候选档切换点;禁消费位另写档)。"""
        assert tuple(SEELE_OR_LEGS) == (('量子同频', 2), ('贝洛伯格', 2))
        assert SEELE_CARRY_CHAR == '希儿'

    def test_non_seele_pair_byte_identical(self) -> None:
        """非希儿对产物零漂移:桥池档照旧、无 OR/carry 字段(缺省空)。"""
        comp = pair_target_comp(_OTHER_PAIR)
        assert comp.form_tiers == {'仙舟': 3, '持续伤害': 2}
        assert comp.or_legs == []
        assert comp.required_deployed == ()
        comp2 = pair_target_comp(('列车同行', '持续伤害'))
        assert comp2.form_tiers == {'列车同行': 2, '持续伤害': 2}
        assert comp2.or_legs == [] and comp2.required_deployed == ()


# ===== §6.3-2 form_ok 四象限(连同 fp 值;单一源链可见性)=====

class TestFormOkQuadrants:
    def test_or_leg_achieves_form_ok(self, seele_comp) -> None:
        """【OR 达成锁;变异必红】量 2 达成(无贝)即成型 fp=1.0——
        旧 AND 口径要求量子 3,该帧判 False(批序 1 病灶本体)。"""
        st = _frame({'列车同行': 2, '量子同频': 2}, ('希儿',))
        fp = form_progress(seele_comp, st)
        assert fp == pytest.approx(1.0, abs=1e-9)
        assert readiness_form_ok(st, seele_comp) is True

    def test_belobog_leg_alone_also_achieves(self, seele_comp) -> None:
        """贝 2 达成(无量)同为 OR 满腿(两腿对等)。"""
        st = _frame({'列车同行': 2, '贝洛伯格': 2}, ('希儿',))
        assert form_progress(seele_comp, st) == pytest.approx(1.0, abs=1e-9)
        assert readiness_form_ok(st, seele_comp) is True

    def test_half_amp_legs_fail_with_fp(self, seele_comp) -> None:
        """量1∧贝1(他档满、希儿在板)→ False,OR 虚拟腿=0.5,
        fp=(1+0.5+1)/3(半成品如实贡献,不冒充达标)。"""
        st = _frame({'列车同行': 2, '量子同频': 1, '贝洛伯格': 1}, ('希儿',))
        fp = form_progress(seele_comp, st)
        assert readiness_form_ok(st, seele_comp) is False
        assert fp == pytest.approx((1.0 + 0.5 + 1.0) / 3.0, abs=1e-9)

    def test_carry_absent_fails_with_fp(self, seele_comp) -> None:
        """【轴③锁】放大器齐但希儿不在板 → False,fp=2/3(carry 虚拟
        腿 0;镜像/armed/[28] 读数全经 fp<1.0 显影——单一源链可见性
        核心格)。bench 在手不算在场(deployed 口径)。"""
        st_board_only = _frame({'列车同行': 2, '量子同频': 2}, ())
        assert readiness_form_ok(st_board_only, seele_comp) is False
        assert form_progress(seele_comp, st_board_only) \
            == pytest.approx(2.0 / 3.0, abs=1e-9)
        st_on_bench = _frame({'列车同行': 2, '量子同频': 2}, ('桑博',))
        assert readiness_form_ok(st_on_bench, seele_comp) is False

    def test_other_leg_still_and(self, seele_comp) -> None:
        """他体系档未达 → False 即便 OR 腿满(跨体系 AND 保留,防半对冒充)。"""
        st = _frame({'列车同行': 1, '贝洛伯格': 2}, ('希儿',))
        assert readiness_form_ok(st, seele_comp) is False
        assert form_progress(seele_comp, st) \
            == pytest.approx((0.5 + 1.0 + 1.0) / 3.0, abs=1e-9)


# ===== 单卡不算开线保持锁(:138 语义在形态端口的投影)=====

class TestSingleCarryNotFormed:
    def test_single_carry_never_form_ok(self, seele_comp) -> None:
        """希儿单卡在板 + 他档满、零放大器 → 不成型(fp=2/3)——
        「希儿到手 ≠ 希儿线成型」的形态端口判据面。"""
        st = _frame({'列车同行': 2}, ('希儿',))
        assert readiness_form_ok(st, seele_comp) is False
        assert form_progress(seele_comp, st) \
            == pytest.approx((1.0 + 0.0 + 1.0) / 3.0, abs=1e-9)

    def test_support_port_unchanged_independent(self) -> None:
        """支持度端口(批序 2)语义不受本批扰动:希儿单卡支持度仍 0.5
        (不即锁),希儿+1 去重放大器 1.0——两端口各自独立成立。"""
        from sr_od.application.currency_war.kernel.cw_intention import (
            _seele_system_support,
        )
        assert _seele_system_support({'希儿'}) == 0.5
        assert _seele_system_support({'希儿', '桑博'}) == 1.0
        assert _seele_system_support({'桑博', '佩拉'}) == 0.0


# ===== §6.3-3 半成品进度与单一源不变式 =====

class TestProgressFolding:
    def test_best_leg_monotonic_no_reset(self, seele_comp) -> None:
        """OR 虚拟腿取组内 max:量 0→1→2 单调抬升;量 2 后贝腿追加
        不回落(换最好腿无重置,进度连续性)。"""
        seq = [_frame({'列车同行': 2, '量子同频': k}, ('希儿',))
               for k in (0, 1, 2)]
        vals = [form_progress(seele_comp, s) for s in seq]
        assert vals[0] < vals[1] < vals[2] == pytest.approx(1.0, abs=1e-9)
        st_both = _frame({'列车同行': 2, '量子同频': 2, '贝洛伯格': 2},
                         ('希儿',))
        assert form_progress(seele_comp, st_both) \
            == pytest.approx(1.0, abs=1e-9)

    def test_fp_one_iff_form_ok(self, seele_comp) -> None:
        """fp=1.0 ⟺ form_ok 单一源契约(三腿折法扩展后不变式):
        板面网格全格同值。"""
        for q, b, t in itertools.product(range(4), range(3), range(3)):
            st = _frame({'列车同行': t, '量子同频': q, '贝洛伯格': b},
                        ('希儿',))
            fp = form_progress(seele_comp, st)
            assert (fp >= 1.0) == readiness_form_ok(st, seele_comp)

    def test_registry_comps_zero_drift(self) -> None:
        """空字段 comp(全注册表)逐位同旧式均值:追击飞霄
        (form_tiers={追击:3})三态单调,均值折法不变。"""
        from sr_od.application.currency_war.kernel.cw_comps import get_comp
        comp = get_comp('追击飞霄')
        assert comp.or_legs == [] and comp.required_deployed == ()
        assert form_progress(comp, GameState(board={})) == 0.0
        assert form_progress(comp, GameState(board={'追击': 2})) \
            == pytest.approx(2.0 / 3.0, abs=1e-9)
        assert form_progress(comp, GameState(board={'追击': 3})) == 1.0

    def test_lightweight_board_only_state_tolerated(self, seele_comp) -> None:
        """轻量假想面板(仅 board 视图,mandate 部署差额折算消费形)不炸:
        carry 缺读按 0 计(保守向,缺读≠满成)。"""
        from types import SimpleNamespace
        fp = form_progress(seele_comp, SimpleNamespace(
            board={'列车同行': 2, '量子同频': 2}))
        assert fp == pytest.approx((1.0 + 1.0 + 0.0) / 3.0, abs=1e-9)


# ===== 嵌套包含锁(命题 §4-1:条件域上 doc ⊇ code,事件级事实)=====

class TestNestedInclusion:
    def test_nested_inclusion_grid(self, seele_comp) -> None:
        """条件域(希儿在板)网格全格:旧 AND 谓词(量≥3∧贝≥2∧他档满)
        成 ⟹ 新 OR 谓词必成;且存在严格反向格(量2贝0:新成旧不成)。"""
        def old_code_ok(st: GameState) -> bool:
            # 被 ADR-0613 取代的旧口径(仅本锁内联重构作对照,非第二判定):
            # 他档满 ∧ 量子≥3 ∧ 贝≥2(cw_recipe 完全体档 AND)。
            return (st.board.get('列车同行', 0) >= 2
                    and st.board.get('量子同频', 0) >= 3
                    and st.board.get('贝洛伯格', 0) >= 2)

        strict_reverse_found = False
        for q, b, t in itertools.product(range(4), range(3), range(3)):
            st = _frame({'列车同行': t, '量子同频': q, '贝洛伯格': b},
                        ('希儿',))
            new_ok = readiness_form_ok(st, seele_comp)
            if old_code_ok(st):
                assert new_ok, f'包含违反: q={q} b={b} t={t}'
            if new_ok and not old_code_ok(st):
                strict_reverse_found = True
        assert strict_reverse_found, '条件域上包含须为严格(反向格存在)'


# ===== 辖域切分机械锁(form 链禁出现支持度端口消费)=====

class TestPortSeparation:
    def test_support_fn_absent_from_form_chain(self) -> None:
        """两端口切分可机械检验(方案审 §辖域):form_progress 与
        pair_target_comp 的函数源码禁引用 _seele_system_support——
        form 链读板面羁绊计数,不读 owned 去重支持度值。"""
        import inspect
        from sr_od.application.currency_war.kernel import cw_comps, cw_intention
        form_src = inspect.getsource(cw_comps.form_progress)
        pair_src = inspect.getsource(cw_intention.pair_target_comp)
        assert '_seele_system_support' not in form_src
        assert '_seele_system_support' not in pair_src
