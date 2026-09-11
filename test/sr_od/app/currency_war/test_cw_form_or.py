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
test_grid_fp_iff_ok_and_nested_inclusion(包含格)红;亲测红证记录见
ADR-0613 §验收。

静态套覆盖(T-171 批序4,ADR-0621):验收局实弹实证 P2+ 锁线路径
(flow 消费 COMP_LIBRARY 静态套「希儿量子」)form_ok 恒 False——静态
条目 AND 完全体(量4∧贝2,无 OR/carry)vs 文档 OR 口径分裂,量子3+
希儿在场帧按文档已成型而旧折法 fp=0.625(ADR-0613「全 COMP_LIBRARY
逐字节不变」声明的覆盖缺口,静态套在两批均未立项)。修法 = 静态条目
挂 SEELE_OR_LEGS/SEELE_CARRY_CHAR(与 pair 路径同构,单一折法 =
form_progress 增「OR 组承接同键档位」规则)+ 单一源接线守卫(常量
真源 cw_comps,cw_intention 改指批已落地);变异红证
见 TestStaticSeeleFormOk/TestOrOwnershipFold 各锁「变异必红」注。
"""
from __future__ import annotations

import itertools

import pytest

from sr_od.application.currency_war.kernel import cw_comps
from sr_od.application.currency_war.kernel.cw_board_state import (
    board_state_bridge as _bridge,
)
from sr_od.application.currency_war.kernel.cw_comps import (
    Comp,
    form_progress,
    get_comp,
)
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


def _frame(board: dict[str, int], deployed: tuple[str, ...] = (),
           bench: tuple[str, ...] = ()) -> GameState:
    """最小对局帧:board 羁绊计数 + 在板名单 + 可选 bench 名单(bench
    负例帧用;成型判据只读 board/deployed,bench 供部署维度区分格)。"""
    st = GameState(gold=10, level=5, plane=1, round_num=5, hp=100)
    st.board = dict(board)
    st.deployed = [BenchChar(slot=i + 1, char_id=n, star=1)
                   for i, n in enumerate(deployed)]
    st.bench = [BenchChar(slot=i + 1, char_id=n, star=1)
                for i, n in enumerate(bench)]
    return st


@pytest.fixture(scope='module')
def seele_comp():
    return pair_target_comp(_SEELE_PAIR)


# ===== §6.3-1 伪 comp 构造锁(含非希儿对零漂移锚)=====

class TestPseudoCompShape:
    def test_seele_pair_shape(self, seele_comp) -> None:
        """希儿系对:form_tiers 只含他体系档 + or_legs 两放大器腿 +
        required_deployed=carry;板面键集仍含量/贝(部署/评分视图不盲)。
        档位/期望值自模块常量现算(纪律第 9 条禁手抄双源;T-171 三审
        T3)——常量换档(候选档切换点)时本锁随常量重推,不跟绿。"""
        assert seele_comp is not None
        assert seele_comp.form_tiers == {'列车同行': 2}
        assert list(seele_comp.or_legs) == list(SEELE_OR_LEGS)
        assert seele_comp.required_deployed == (SEELE_CARRY_CHAR,)
        assert set(seele_comp.factions) == {'列车同行', '量子同频', '贝洛伯格'}
        assert '希儿' in seele_comp.core_chars

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
        fp = form_progress(seele_comp, _bridge(st))
        assert fp == pytest.approx(1.0, abs=1e-9)
        assert readiness_form_ok(_bridge(st), seele_comp) is True

    def test_belobog_leg_alone_also_achieves(self, seele_comp) -> None:
        """贝 2 达成(无量)同为 OR 满腿(两腿对等)。"""
        st = _frame({'列车同行': 2, '贝洛伯格': 2}, ('希儿',))
        assert form_progress(seele_comp, _bridge(st)) == pytest.approx(1.0, abs=1e-9)
        assert readiness_form_ok(_bridge(st), seele_comp) is True

    def test_half_amp_legs_fail_with_fp(self, seele_comp) -> None:
        """量1∧贝1(他档满、希儿在板)→ False,OR 虚拟腿=0.5,
        fp=(1+0.5+1)/3(半成品如实贡献,不冒充达标)。"""
        st = _frame({'列车同行': 2, '量子同频': 1, '贝洛伯格': 1}, ('希儿',))
        fp = form_progress(seele_comp, _bridge(st))
        assert readiness_form_ok(_bridge(st), seele_comp) is False
        assert fp == pytest.approx((1.0 + 0.5 + 1.0) / 3.0, abs=1e-9)

    def test_carry_absent_fails_with_fp(self, seele_comp) -> None:
        """【轴③锁】放大器齐但希儿不在板 → False,fp=2/3(carry 虚拟
        腿 0;镜像/armed/[28] 读数全经 fp<1.0 显影——单一源链可见性
        核心格)。bench 在手不算在场(deployed 口径,末帧实测 bench 维)。"""
        st_board_only = _frame({'列车同行': 2, '量子同频': 2}, ())
        assert readiness_form_ok(_bridge(st_board_only), seele_comp) is False
        assert form_progress(seele_comp, _bridge(st_board_only)) \
            == pytest.approx(2.0 / 3.0, abs=1e-9)
        # 希儿在 bench(在手)不在 deployed、桑博占 deployed 位 → False
        # (帧形态/变量名失实修正,落地审 B-4:原 st_on_bench 帧实为
        # 「桑博在板、希儿完全不在场」,未测 bench 维度)
        st_carry_on_bench = _frame({'列车同行': 2, '量子同频': 2},
                                   ('桑博',), bench=('希儿',))
        assert readiness_form_ok(_bridge(st_carry_on_bench), seele_comp) is False

    def test_other_leg_still_and(self, seele_comp) -> None:
        """他体系档未达 → False 即便 OR 腿满(跨体系 AND 保留,防半对冒充)。"""
        st = _frame({'列车同行': 1, '贝洛伯格': 2}, ('希儿',))
        assert readiness_form_ok(_bridge(st), seele_comp) is False
        assert form_progress(seele_comp, _bridge(st)) \
            == pytest.approx((0.5 + 1.0 + 1.0) / 3.0, abs=1e-9)


# ===== 单卡不算开线保持锁(:138 语义在形态端口的投影)=====
# (test_support_port_unchanged_independent 已删(T-171 三审可删清单):
#  支持度端口三格值断言由批序 2 文件 test_cw_seele_support.py 全覆盖
#  且其为超集(同格值 + 锁线/gap 消费面),重复断言源 = 双处跟绿点;
#  支持度语义变更时该文件红,本文件不再二次报。)

class TestSingleCarryNotFormed:
    def test_single_carry_never_form_ok(self, seele_comp) -> None:
        """希儿单卡在板 + 他档满、零放大器 → 不成型(fp=2/3)——
        「希儿到手 ≠ 希儿线成型」的形态端口判据面。"""
        st = _frame({'列车同行': 2}, ('希儿',))
        assert readiness_form_ok(_bridge(st), seele_comp) is False
        assert form_progress(seele_comp, _bridge(st)) \
            == pytest.approx((1.0 + 0.0 + 1.0) / 3.0, abs=1e-9)


# ===== §6.3-3 半成品进度与单一源不变式 =====

class TestProgressFolding:
    def test_best_leg_monotonic_no_reset(self, seele_comp) -> None:
        """OR 虚拟腿取组内 max:量 0→1→2 单调抬升;量 2 后贝腿追加
        不回落(换最好腿无重置,进度连续性)。"""
        seq = [_frame({'列车同行': 2, '量子同频': k}, ('希儿',))
               for k in (0, 1, 2)]
        vals = [form_progress(seele_comp, _bridge(s)) for s in seq]
        assert vals[0] < vals[1] < vals[2] == pytest.approx(1.0, abs=1e-9)
        st_both = _frame({'列车同行': 2, '量子同频': 2, '贝洛伯格': 2},
                         ('希儿',))
        assert form_progress(seele_comp, _bridge(st_both)) \
            == pytest.approx(1.0, abs=1e-9)

    def test_grid_fp_iff_ok_and_nested_inclusion(self, seele_comp) -> None:
        """36 格网格锁(4×3×3,一次帧构造断言两组事实,T-171 三审 T4 并格;
        docstring 分行声明):
        ① 单一源契约:每格 fp=1.0 ⟺ form_ok(三腿折法扩展后不变式);
        ② 条件域(希儿在板)嵌套包含:旧 AND 谓词(量≥3∧贝≥2∧他档满)
        成 ⟹ 新 OR 谓词必成,且存在严格反向格(量2贝0:新成旧不成)。
        (原两锁各自独立遍历 36 帧成本翻倍,并格后断言面逐格等价。)"""
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
            new_ok = readiness_form_ok(_bridge(st), seele_comp)
            fp = form_progress(seele_comp, _bridge(st))
            assert (fp >= 1.0) == new_ok, \
                f'单一源契约违反: q={q} b={b} t={t}'           # ①
            if old_code_ok(st):
                assert new_ok, f'包含违反: q={q} b={b} t={t}'   # ②
            if new_ok and not old_code_ok(st):
                strict_reverse_found = True
        assert strict_reverse_found, '条件域上包含须为严格(反向格存在)'

    def test_registry_comps_zero_drift(self) -> None:
        """空字段 comp(全注册表)逐位同旧式均值:追击飞霄
        (form_tiers={追击:3})三态单调,均值折法不变。"""
        from sr_od.application.currency_war.kernel.cw_comps import get_comp
        comp = get_comp('追击飞霄')
        assert comp.or_legs == [] and comp.required_deployed == ()
        assert form_progress(comp, _bridge(GameState(board={}))) == 0.0
        assert form_progress(comp, _bridge(GameState(board={'追击': 2}))) \
            == pytest.approx(2.0 / 3.0, abs=1e-9)
        assert form_progress(comp, _bridge(GameState(board={'追击': 3}))) == 1.0

    def test_lightweight_board_only_state_tolerated(self, seele_comp) -> None:
        """轻量假想面板(仅 board 视图,mandate 部署差额折算消费形)不炸:
        carry 缺读按 0 计(保守向,缺读≠满成)。"""
        from types import SimpleNamespace
        fp = form_progress(seele_comp, SimpleNamespace(
            board=SimpleNamespace(value={'列车同行': 2, '量子同频': 2})))
        assert fp == pytest.approx((1.0 + 1.0 + 0.0) / 3.0, abs=1e-9)


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


# ===== 静态套「希儿量子」OR 挂腿(P2+ 锁线路径覆盖;T-171 批序4,ADR-0621)=====

def _static_seele_comp() -> Comp:
    """静态套条目(注册表单一源直读,禁自构造副本——防测自抄复刻)。"""
    comp = get_comp('希儿量子')
    assert comp is not None
    return comp


def _static_expected_fp(board: dict[str, int], *, deployed: bool) -> float:
    """静态套 fp 期望值现算(纪律第 9 条推导锚定,禁手抄期望常数):
    AND 腿 0 条(双档全被 OR 组承接)+ 1 条 OR 虚拟腿(max)+ carry
    0/1;分母 = 腿数和。折法改变时本helper 与生产同判据重推,不跟绿。"""
    comp = _static_seele_comp()
    best = max(min(board.get(f, 0), t) / t
               for f, t in cw_comps.SEELE_OR_LEGS)
    carry = 1.0 if deployed else 0.0
    return (best + carry) / (1 + len(comp.required_deployed))


class TestStaticSeeleCompShape:
    """静态条目构造锁 + 单一源接线守卫。

    单一源状态(ADR-0621):真源归位 cw_comps(注册表数据层,静态条目
    import 期消费,反向 import 成环);cw_intention 经顶部 import 消费
    (改指批已落地,双定义恒等态关闭)。原「值相等恒等锁」随改指成为
    恒真式,已改形为接线守卫(对象身份 ``is``):cw_intention 本地第二份
    定义复发(值可等、对象必异)即红,守卫其形态端口注「禁再写本地
    第二份」的裁定。
    """

    def test_entry_carries_or_and_carry(self) -> None:
        """静态条目 or_legs/required_deployed 与模块常量恒等(登记门:
        玩家裁定量 2/量 3 改档时本锁随常量重推,不跟绿)。"""
        comp = _static_seele_comp()
        assert list(comp.or_legs) == list(cw_comps.SEELE_OR_LEGS)
        assert comp.required_deployed == (cw_comps.SEELE_CARRY_CHAR,)

    def test_constants_single_source_wiring(self) -> None:
        """【单一源接线守卫】cw_intention 的希儿系判据常量必须是
        cw_comps 真源**同一对象**(re-import 别名,``is`` 身份而非值等)
        ——本地第二份定义(值等对象异)= 双定义复发,本锁红(改指批
        落地前的过渡恒等锁改形继承其守卫位,防回退)。"""
        from sr_od.application.currency_war.kernel import cw_intention
        assert cw_intention.SEELE_OR_LEGS is cw_comps.SEELE_OR_LEGS
        assert cw_intention.SEELE_CARRY_CHAR is cw_comps.SEELE_CARRY_CHAR

    def test_form_tiers_keys_stay_carriers(self) -> None:
        """【结构载体锁;清键即红】静态条目 form_tiers 键面保持
        {量子同频:4, 贝洛伯格:2}——承接折法只免其 AND 账,不禁其结构
        消费:囤货采购集羁绊成员展开(cw_intention._line_hoard)、锁定
        体系集(locked_faction_scope)、晋升候选键面交集、换线距离账均读
        此键面;清空键面 = 银狼/佩拉/桑博等放大器成员掉出锁定线采购集
        (判据即本锁回归语义)。"""
        assert _static_seele_comp().form_tiers \
            == {'量子同频': 4, '贝洛伯格': 2}


class TestStaticSeeleFormOk:
    """静态套 form_ok 行为锁(判据 = transition_combos.md:27 文档 OR
    口径;fp 期望值经 _static_expected_fp 自常量现算)。

    变异红证锚:M1(静态腿回退 or_legs=[],required=())→ 本类除
    结构载体锁外全红;M2(承接规则删除,同键档位回 AND 账)→ 本类
    绝对 fp 格全红 + 网格包含红;还原后全绿,亲测记录见批报告/ADR-0621。
    """

    def test_acceptance_frame_quantum3_seele_deployed(self) -> None:
        """【行为锁;变异必红】量子3+贝1+希儿在板(验收局 P2 实弹帧形态)
        → form_ok=True fp=1.0——文档 OR 口径(量腿满 + carry);旧 AND
        完全体折法同帧 fp=0.625 恒 False(批序4 病灶本体帧)。"""
        comp = _static_seele_comp()
        board = {'量子同频': 3, '贝洛伯格': 1}
        st = _frame(board, ('希儿',))
        fp = form_progress(comp, _bridge(st))
        assert readiness_form_ok(_bridge(st), comp) is True
        assert fp == pytest.approx(
            _static_expected_fp(board, deployed=True), abs=1e-9)

    def test_belobog_leg_alone_forms(self) -> None:
        """【变异必红】贝2 板(娜塔莎/佩拉/桑博类)+希儿在板 → True
        fp=1.0(两腿对等;旧 AND 要求量4 不得成型)。"""
        comp = _static_seele_comp()
        board = {'贝洛伯格': 2}
        st = _frame(board, ('希儿',))
        assert readiness_form_ok(_bridge(st), comp) is True
        assert form_progress(comp, _bridge(st)) == pytest.approx(
            _static_expected_fp(board, deployed=True), abs=1e-9)

    def test_half_legs_fail_with_fp(self) -> None:
        """量1∧贝1+希儿在板 → False,OR 虚拟腿=0.5(半成品如实贡献,
        不冒充达标)。"""
        comp = _static_seele_comp()
        board = {'量子同频': 1, '贝洛伯格': 1}
        st = _frame(board, ('希儿',))
        fp = form_progress(comp, _bridge(st))
        assert readiness_form_ok(_bridge(st), comp) is False
        assert fp == pytest.approx(
            _static_expected_fp(board, deployed=True), abs=1e-9)

    def test_single_carry_never_form_ok(self) -> None:
        """希儿单卡在板零放大器 → False(fp=0.5)——「希儿到手 ≠ 希儿线
        成型」(combo_methodology.md:138)在静态套的投影:无放大器腿
        fp<1.0 不成型。"""
        comp = _static_seele_comp()
        st = _frame({}, ('希儿',))
        assert readiness_form_ok(_bridge(st), comp) is False
        assert form_progress(comp, _bridge(st)) == pytest.approx(
            _static_expected_fp({}, deployed=True), abs=1e-9)

    def test_carry_absent_fails_with_fp(self) -> None:
        """【轴③锁】量3+贝2 齐但希儿不在板 → False——bench 在手不算
        在场(deployed 口径),与 pair 路径同判据。"""
        comp = _static_seele_comp()
        board = {'量子同频': 3, '贝洛伯格': 2}
        st = _frame(board, ())
        assert readiness_form_ok(_bridge(st), comp) is False
        assert form_progress(comp, _bridge(st)) == pytest.approx(
            _static_expected_fp(board, deployed=False), abs=1e-9)

    def test_carry_on_bench_not_deployed_fails(self) -> None:
        """【判别性负例(落地审 B-4)】放大器齐(量2贝2)+希儿在 bench
        不在 deployed → False(fp=0.5)——required_deployed 口径 =
        **在板**,bench 在手不算在场(「希儿到手 ≠ 希儿线成型」
        combo_methodology.md:138 的部署维度投影;防「在手≈在场」放水)。"""
        comp = _static_seele_comp()
        board = {'量子同频': 2, '贝洛伯格': 2}
        st = _frame(board, (), bench=('希儿',))
        fp = form_progress(comp, _bridge(st))
        assert readiness_form_ok(_bridge(st), comp) is False
        assert fp == pytest.approx(
            _static_expected_fp(board, deployed=False), abs=1e-9)

    def test_lightweight_board_only_state_tolerated(self) -> None:
        """轻量假想面板(仅 board 视图,mandate 部署差额折算消费形)不炸:
        carry 缺读按 0 计(保守向)——量2 满腿亦因 carry 0 不成型。"""
        from types import SimpleNamespace
        comp = _static_seele_comp()
        fp = form_progress(comp, SimpleNamespace(
            board=SimpleNamespace(value={'量子同频': 2})))
        assert fp == pytest.approx(
            _static_expected_fp({'量子同频': 2}, deployed=False), abs=1e-9)
        assert fp < 1.0

    def test_grid_fp_iff_ok_and_conditional_inclusion(self) -> None:
        """网格锁(量 0..4 × 贝 0..2 × 希儿 在/不在板,一次构造两组断言):
        ① 单一源契约:每格 fp=1.0 ⟺ form_ok(承接折法下不变式保持);
        ② 条件域(希儿在板,ADR-0613 F3 同款限定)嵌套包含:旧 AND 完全体
        谓词(量≥4∧贝≥2)成 ⟹ 新 OR 谓词必成,且严格反向格存在(量3贝1:
        新成旧不成)——新口径是旧口径在条件域上的严格放宽。"""
        comp = _static_seele_comp()

        def old_full_form_ok(st: GameState) -> bool:
            # 被取代的旧 AND 完全体口径(仅本锁内联重构作对照,非第二判定):
            # 量≥4 ∧ 贝≥2(静态条目旧 form_tiers 全档;量 3 是 pair 路径
            # 借 cw_recipe 的档,非静态旧档,勿混——落地审 B-2 锚位修正)。
            return (st.board.get('量子同频', 0) >= 4
                    and st.board.get('贝洛伯格', 0) >= 2)

        strict_reverse_found = False
        for q, b, dep in itertools.product(range(5), range(3),
                                           ((), ('希儿',))):
            st = _frame({'量子同频': q, '贝洛伯格': b}, dep)
            ok = readiness_form_ok(_bridge(st), comp)
            fp = form_progress(comp, _bridge(st))
            assert (fp >= 1.0) == ok, \
                f'单一源契约违反: q={q} b={b} dep={dep}'          # ①
            if dep and old_full_form_ok(st):
                assert ok, f'条件域包含违反: q={q} b={b}'          # ②
            if ok and not (dep and old_full_form_ok(st)):
                strict_reverse_found = True
        assert strict_reverse_found, '条件域上包含须为严格(反向格存在)'


class TestOrOwnershipFold:
    """承接折法机械锁(合成 comp;ADR-0621 承接规则三格)。

    变异红证锚:M2(承接规则删除)→ 本类三格全红(同键档位回 AND 账);
    pair 路径锁不动其绿(伪 comp 两键集恒不相交,承接规则对其零差)。
    """

    @staticmethod
    def _mixed_comp() -> Comp:
        # 合成样例:A=非承接键(纯 AND 档)、B=承接键(档 4 由 OR 腿档 1 承接);
        # 键名用占位符,判据只读 form_tiers/or_legs/required_deployed/board。
        return Comp(name='折法锁样例', factions=['A', 'B'], core_chars=['x'],
                    form_tiers={'A': 2, 'B': 4}, strength='A',
                    form_difficulty='easy', or_legs=[('B', 1)])

    def test_owned_bond_tier_not_required(self) -> None:
        """【变异必红】B 键由 OR 组承接:tier-4 档不再要求,B≥1(OR 腿)
        即满该键,A2 满档 → 成型 fp=1.0。"""
        comp = self._mixed_comp()
        st = _frame({'A': 2, 'B': 1})
        assert form_progress(comp, _bridge(st)) == pytest.approx(1.0, abs=1e-9)
        assert readiness_form_ok(_bridge(st), comp) is True

    def test_unowned_bond_still_and(self) -> None:
        """非承接键 A 仍是 AND 硬档:A1 即便 OR 满 → False(防半套冒充,
        与 pair 路径「跨体系 AND 保留」同构)。"""
        comp = self._mixed_comp()
        st = _frame({'A': 1, 'B': 1})
        assert readiness_form_ok(_bridge(st), comp) is False
        assert form_progress(comp, _bridge(st)) == pytest.approx(0.75, abs=1e-9)

    def test_owned_tier_out_of_denominator(self) -> None:
        """【变异必红】分子分母同免:B2 帧 fp=(A1.0+OR1.0)/2=1.0;若承接
        键仍入 AND 账该帧 fp=(1+0.5+1)/3<1.0——B 的 2★ 加深不再压低成型
        读数(完全体加深与「已成型」判读分离)。"""
        comp = self._mixed_comp()
        st = _frame({'A': 2, 'B': 2})
        assert form_progress(comp, _bridge(st)) == pytest.approx(1.0, abs=1e-9)


class TestBridgePoolAmpSeal:
    """桥池无放大器键不变量(落地审 B-5;ADR-0621 §已知边界)。

    form_progress docstring「pair 伪 comp 两键集恒不相交」依赖数据不变量:
    BRIDGE_POOL∪BRIDGE_POOL_P2 全部条目 engine_bonds 键集与 ``SEELE_OR_LEGS``
    放大器键(量子同频/贝洛伯格)不相交。若未来桥池数据更新收录含量/贝键
    条目、且键集恰与某希儿系对展开键集相等,pair_target_comp 分支①精确
    匹配(cw_intention.py:914-917)会产出 or_legs=[] 的纯 AND 伪 comp
    (完全体桥档、无 carry)——ADR-0613 语义静默回归,承接规则无 or_legs
    可承接救不了。封存依据 = ADR-0350(狼狩/贝洛伯格不入桥池,四体系
    封闭裁定)。本锁红时:先判「有意解封 or 误收录」——解封须同步改
    pair_target_comp 剥离逻辑与本锁语义,禁机械跟绿。
    """

    def test_bridge_pools_contain_no_amplifier_bonds(self) -> None:
        """登记门:桥池全条目 engine_bonds 键 ∩ 放大器键 = ∅;红 = 封存
        面被数据更新触碰,处置语义见类 docstring。"""
        from sr_od.application.currency_war.kernel.cw_bridge_pool import (
            BRIDGE_POOL,
            BRIDGE_POOL_P2,
        )
        amp_keys = {bond for bond, _t in cw_comps.SEELE_OR_LEGS}
        for pool, label in ((BRIDGE_POOL, 'P1'), (BRIDGE_POOL_P2, 'P2')):
            for combo in pool:
                hit = amp_keys & set(combo.engine_bonds)
                assert not hit, (
                    f'桥池{label}条目收录放大器键 {sorted(hit)}:'
                    f'pair 精确匹配分支将产出纯 AND 伪 comp'
                    f'(封存裁定 = ADR-0350;解封须改 pair_target_comp '
                    f'剥离逻辑,禁机械跟绿)')
