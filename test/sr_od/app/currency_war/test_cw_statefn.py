"""cw4 statefn 换核步 2 验收测试(状态函数层/审计载体/资格谓词三验收域;
换核迁移序原文已删档,取回口径=ADR-0644)。

覆盖:①statefn 对拍锚属步 2 项(P47 递推 / p̄ 精确口径 / V_comp 表 / Δ息流
闭式 / 第三口封装)②schedule_of 单一源消费静态断言(禁新建长度常量)
③λ 表启动必载损坏守卫(R2-4)④22 项状态量「每项只实现一次」静态断言
⑤前置半步 0 挂后台效果资格谓词(例外①/读装备态/载体缺口;
生锈两态由装配端到端测承接)⑥audit
载体(provisional fail-closed / proof_consts 白名单 / derived 登记)。

对拍锚脚本经 sys.path 注入 tools/cw/proofs(锚=证明件自检脚本本体,
与 statefn 实现零共享代码路径,交叉验证)。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from sr_od.application.currency_war.strategies.impl.mandate_v1.audit import (
    derived,
    proof_consts,
    provisional,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
    horizon,
    interest,
    odds,
    predicates,
    vopt,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
    lambda_death as ld,
)

_PROOFS = Path(__file__).resolve().parents[5] / 'tools' / 'cw' / 'proofs'
for _p in (_PROOFS, _PROOFS / 'p16'):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import p47_check  # noqa: E402
import pbar_exact  # noqa: E402

CW4_DIR = Path(ld.__file__).parent


# ==================== ① §5.3 对拍锚(步 2 项) ====================

class TestP47Recursion:
    """P47 L 递推对拍:statefn.interest vs p47_check.loss_exact 全档位。"""

    def test_grid_matches_anchor(self) -> None:
        for g in (50, 45, 40, 30, 25, 20):
            for d in (2, 4, 6, 10, 15, 20, 30):
                if d > g:
                    continue
                for r in (1, 3, 6, 9):
                    for inc in (6, 7, 9):
                        assert interest.loss_exact(g, d, r, inc) == \
                            p47_check.loss_exact(g, d, r, inc), (g, d, r, inc)

    def test_cap_parameterized(self) -> None:
        # cap=10(息律升帽局):饱和线 100,近饱和线同档花金零跨档损失
        # (95→91 同在 9 档,且两轨迹随后同钉死 100)
        assert interest.loss_exact(95, 4, 9, 7, cap=10) == 0
        # cap=0(买断制):息恒 0,任何花金零息损(语义:无可守)
        assert interest.loss_exact(50, 30, 9, 7, cap=0) == 0
        # 默认局还原 p47 锚(cap=5)
        assert interest.loss_exact(50, 20, 9, 7) == p47_check.loss_exact(50, 20, 9, 7)
        assert interest.saturation_line(5) == 50
        assert interest.saturation_line(0) == 0


class TestPbarExact:
    """p̄ 精确口径对拍:statefn.odds vs pbar_exact.exact_multinom(多项×超几何)。"""

    @pytest.mark.parametrize('tag', ['持续伤害', '银河学者', '仙舟'])
    @pytest.mark.parametrize('level', [5, 6, 7])
    def test_matches_anchor(self, tag: str, level: int) -> None:
        ours = odds.p_bar_exact(tag, level)
        anchor = pbar_exact.exact_multinom(tag, level)
        assert abs(ours - anchor) < 1e-12, (tag, level, ours, anchor)
        # 旧 union bound 口径高估已勘误(P16 瑕疵 A):精确值 < 并集上界
        assert ours <= pbar_exact.union_bound(tag, level) + 1e-12


class TestVCompTable:
    """V_comp 表对拍(R2-11):二维表 ±2%(DGOLD_TRUTH 誊录,全 (费档,等级)
    格覆盖)。原 p49 三格宽锚带(demo anchors)已被本表 ±2% 在同三格上
    严格覆盖(0.268∈[0.24,0.30] 等),零独立判别力,冗余删除(rule 7)。"""

    DGOLD_TRUTH = {
        1: {4: 0.048, 5: 0.070, 6: 0.105, 7: 0.165, 8: 0.174, 9: 0.209, 10: 0.628},
        2: {4: 0.126, 5: 0.095, 6: 0.078, 7: 0.105, 8: 0.126, 9: 0.157, 10: 0.314},
        3: {4: 1.071, 5: 0.536, 6: 0.428, 7: 0.268, 8: 0.335, 9: 0.428, 10: 0.536},
        4: {5: 5.357, 6: 2.143, 7: 1.071, 8: 0.487, 9: 0.357, 10: 0.268},
        5: {7: 60.000, 8: 20.000, 9: 6.000, 10: 2.400},
    }

    def test_2d_table_within_2pct(self) -> None:
        table = vopt.v_comp_table()
        for cost, row in self.DGOLD_TRUTH.items():
            for level, truth in row.items():
                val = table[cost][level]
                assert abs(val - truth) / truth < 0.02, (cost, level, val, truth)


def _trajectory_delta_interest(g: int, refund: int, rounds: int,
                               net_income: int, cap: int) -> int:
    """模拟轨迹逐轮息账真值 Σ_t Δ息_t(对拍锚 §5.3「Δ息流对拍」行):
    卖出帧 refund 入账后,双轨迹(卖/不卖)同收入演化,逐轮息差求和。"""
    gold_cap = 10 * cap

    def intr(x: int) -> int:
        return min(max(x, 0) // 10, cap)

    kept = min(g, gold_cap)
    sold = min(g + refund, gold_cap)
    total = 0
    for _ in range(rounds):
        total += intr(sold) - intr(kept)
        kept = min(kept + net_income + intr(kept), gold_cap)
        sold = min(sold + net_income + intr(sold), gold_cap)
    return total


class TestDeltaInterestFlow:
    """Δ息流̂ 闭式对拍(R6-8/R9-3/R63-1):生产式 ≥ 轨迹真值 ∧ ≤ 复合安全界
    ∧ cap_sup 口径(现值 cap 组装即红)∧ R_截=1 共模现金流反例。"""

    def test_upper_bound_directions(self) -> None:
        for g in (8, 25, 45, 60):
            for r in (1, 3, 6, 14, 56):
                for rounds in (1, 2, 3, 5):
                    for inc in (6, 7, 9):
                        for cap in (5, 10):
                            prod = horizon.delta_interest_flow(r, cap, rounds)
                            truth = _trajectory_delta_interest(
                                g, r, rounds, inc, cap)
                            assert prod >= truth, (g, r, rounds, inc, cap)
                            assert prod <= cap * rounds

    def test_r63_1_upcap_injection_anchor(self) -> None:
        # R63-1 ①:决策帧 cap=5、g=45、同帧拟卖 Σr=56,注入利息上调(cap→10)
        # 后首息 tick:真值 Δ息_1 = min(⌊101/10⌋,10) − min(⌊45/10⌋,10) = 6
        truth1 = _trajectory_delta_interest(45, 56, 1, 7, 10)
        assert truth1 == 6, truth1
        # 旧现值式(cap=5)首项=5 < 真值 ⇒ 现值口径红;修正式按 cap_sup=10:
        prod = horizon.delta_interest_flow(56, cap_sup=10, trunc=3)
        assert prod >= truth1
        # 首项=min(⌈56/10⌉,cap_sup)=6 ≥ 真值 6;按现值 cap=5 组装=5<6 即红

    def test_r9_3_common_mode_cashflow(self) -> None:
        # R_截=1 含共模现金流 X≠0 反例回归锚:cap=5/g=8/r=1/X=1(收入到账后
        # 结算息的时点约定):真值 Δ息_1 = min(⌊(8+1+1)/10⌋,5) −
        # min(⌊(8+1)/10⌋,5) = 1 − 0 = 1;生产式首项 min(⌈1/10⌉,5)=1 ≥ 真值
        truth1 = min((8 + 1 + 1) // 10, 5) - min((8 + 1) // 10, 5)
        assert truth1 == 1, truth1
        assert horizon.delta_interest_flow(1, cap_sup=5, trunc=1) >= truth1


class TestThirdPort:
    """第三口封装对拍(R16-5):输出数值 ≡ d̂×(g+Ī×R_剩余) 水平值;
    R29-3:d̂=同格 CI 宽度;运算白名单=add/compare 仅两种(R19-3)。"""

    KEY = 'D1|hp>40|P2+|battle'  # v3.3 主表 C 集合 #21:CI [0.290, 0.905]

    def test_value_equals_authoritative_form(self) -> None:
        ci = ld.lambda_ci(self.KEY)
        assert ci is not None
        g, ibar, r_rem = 50, 7, 15
        comp = ld.differential_composite(self.KEY, g, ibar, r_rem)
        assert comp is not None
        expected = max(0.0, ci[1] - ci[0]) * (g + ibar * r_rem)
        # 只经白名单比较断言逐帧相等(R16-5:测试代码消费内部源不受收口辖,
        # 这里同样只用白名单形态验证)
        assert comp >= expected
        assert comp <= expected

    def test_zero_width_ci_frame(self) -> None:
        # d̂=0 帧(点估计退化)输出=0(R16-5 覆盖项)——用 CI 宽度 0 的格
        comp = ld.ExposureComposite(0.0)
        assert comp >= 0.0 and comp <= 0.0
        assert (comp + 0) <= 0.0

    def test_out_of_domain_fail_closed(self) -> None:
        # 域外/禁用格 → None(fail-closed,R6-5 同款方向):
        # D1|hp<=15|P2+|encounter 系 n=2 CI 锁死禁用格
        assert ld.differential_composite('D1|hp<=15|P2+|encounter', 50, 7, 15) is None
        assert ld.differential_composite(None, 50, 7, 15) is None
        assert ld.differential_composite('D9|hp>40|P9|battle', 50, 7, 15) is None

    def test_ops_whitelist(self) -> None:
        comp = ld.differential_composite(self.KEY, 50, 7, 15)
        assert comp is not None
        with pytest.raises(TypeError):
            _ = comp - 1  # type: ignore[operator]
        with pytest.raises(TypeError):
            _ = comp * 2  # type: ignore[operator]
        with pytest.raises(TypeError):
            _ = comp / 2  # type: ignore[operator]
        with pytest.raises(TypeError):
            float(comp)  # type: ignore[arg-type]
        # 白名单内:add + compare 正常
        assert comp + comp >= 0.0
        assert comp + 10 >= 10.0


# ==================== ② schedule_of 单一源消费静态断言 ====================

class TestScheduleSingleSource:
    """禁新建长度常量(§6.1):PLANE_LENGTHS_TRUTH 冻结元组形态处死。
    (旧「horizon 源码含 schedule_of/import 行」肯定式在场锁已删——单一源
    纪律由本类墓碑扫描 + r_global session 真值行为锁 + QUANTITY_OWNERS
    r_global cw4 内唯一实现条目三面承载,在场锁零独立判别力,rule 8 影子锁。)"""

    def test_no_length_constants_in_cw4(self) -> None:
        # 静态断言按代码符号(ast)而非原文 grep——horizon docstring 里的
        # 「PLANE_LENGTHS_TRUTH 已处死」历史注记属合法说明,不算新建常量
        for py in CW4_DIR.rglob('*.py'):
            tree = ast.parse(py.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                targets: list[ast.expr] = []
                if isinstance(node, ast.Assign):
                    targets = list(node.targets)
                elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                    targets = [node.target]
                for t in targets:
                    if isinstance(t, ast.Name):
                        assert not any(
                            s in t.id for s in
                            ('PLANE_LENGTHS', 'NODES_PER_PLANE', 'TOTAL_NODES')), \
                            (py, t.id)

    def test_r_global_uses_session_truth(self) -> None:
        class _Sess:  # duck-typed session(脏表守卫夹 [1,9])
            plane_lengths_seen = [9, 7]
        # P1 中段(第 5 节点):9−4 + 7 + 9(未揭晓回退上端)= 21
        assert horizon.r_global(_Sess(), 1, 5) == 21
        # 空表 → 全回退(9,9,9)
        class _Empty:
            plane_lengths_seen = []
        assert horizon.r_global(_Empty(), 1, 1) == 27
        # 脏表超长夹 9
        class _Dirty:
            plane_lengths_seen = [12, 7, 9]
        assert horizon.r_global(_Dirty(), 3, 9) == 1


# ==================== ③ λ 表启动必载损坏守卫(R2-4) ====================

class TestLambdaTableGuard:

    def test_startup_loaded(self) -> None:
        assert ld.table_loaded()
        assert len(ld.consumable_keys()) == 21  # C 集合 21 格(v3.3 Part 8)

    def test_corruption_guard_alarms(self, tmp_path: Path,
                                     monkeypatch: pytest.MonkeyPatch) -> None:
        # 直接驱动 _load_table(reload 会重置模块全局,monkeypatch 后 reload
        # 即失效——守卫路径的单元入口即 _load_table 本体)
        bad = tmp_path / 'bad.json'
        bad.write_text('{not json', encoding='utf-8')
        monkeypatch.setattr(ld, '_TABLE_PATH', bad)
        monkeypatch.setattr(ld, '_ALARM_FIRED', False)
        table = ld._load_table()
        assert table == {}
        assert ld._ALARM_FIRED is True  # 报警确发(守卫探针)
        # 损坏态查表恒 None(域外同判):模拟空表挂载
        monkeypatch.setattr(ld, '_LAMBDA_TABLE', {})
        assert ld.lambda_ci('D0|hp>40|P1|battle') is None
        assert ld.differential_composite('D0|hp>40|P1|battle', 50, 7, 15) is None
        assert ld.exposure_ge('D0|hp>40|P1|battle', 100, 10.0, 0.0) is None


# ==================== ④ 22 项状态量每项只实现一次(静态断言) ====================

#: NMF §2 状态量 → 唯一实现符号(模块,函数)。判据模块(cw4 内 criteria/
#: mandate/proof;mandate 面随策略器批 1 迁移落位)禁自算——本断言辖 cw4
#: 全包:同名 def 全包唯一。
QUANTITY_OWNERS: dict[str, tuple[str, str]] = {
    'g 存量金(黑板直读,无独立算子;实现下沉 kernel/cw_economy)': ('', 'interest'),
    'level/xp_cur(cw_state 权威,消费不重建)': ('s_line', 'b_target'),
    'R_全局(实现下沉 kernel/cw_plane_table)': ('', 'r_global'),
    'R_剩余(实现下沉 kernel/cw_plane_table)': ('', 'r_remaining'),
    'Ī 净收入率(实现下沉 kernel/cw_economy)': ('', 'net_income'),
    'L 息档损失(实现下沉 kernel/cw_economy)': ('', 'loss_exact'),
    'λ_death PL 键表': ('lambda_death', 'lambda_ci'),
    'floor_eff(arm2 守息门)': ('lambda_death', 'floor_eff'),
    '区间敞口比较(W 消费形态)': ('lambda_death', 'exposure_ge'),
    '第三口差分复合项': ('lambda_death', 'differential_composite'),
    'Δ息流̂ 增量算子': ('horizon', 'delta_interest_flow'),
    'ΔW_trunc 增量敞口': ('horizon', 'delta_w_increment'),
    'ρ 整买价值率': ('s_line', 'rho'),
    'S 动态目标线': ('s_line', 's_line'),
    'B 批成本': ('s_line', 'b_target'),
    'n̄ 自然 XP 流': ('s_line', 'nbar'),
    'q 槽级命中': ('odds', 'slot_q'),
    'P_shop': ('odds', 'p_shop'),
    'p̄ 换线命中率': ('odds', 'p_bar_exact'),
    'V_opt 囤件期权': ('vopt', 'v_opt'),
    'V_slot bench 槽价': ('vopt', 'v_slot'),
    'V_comp 压缩价值表': ('vopt', 'v_comp_table'),
    'ΔV_streak 连胜账': ('vopt', 'delta_v_streak'),
    'ΔP̂ 完成概率增量': ('vopt', 'delta_p_hat'),
    'T_search 档匹配谓词': ('vopt', 'tier_match'),
    'refund_full_star_ok 星级纪律': ('vopt', 'refund_full_star_ok'),
    '板满/等待件谓词(arm1_existence)': ('predicates', 'arm1_existence'),
    '目标线 K': ('predicates', 'line_members'),
    '零重叠': ('predicates', 'zero_overlap'),
    '挂后台效果资格谓词(半步0)': ('predicates', 'bench_effect_qualified'),
    # D-dup 可部署战力谓词条目已删:RunDeploy 发射门重写(ADR-0517 决策2/
    # dd-037 接线)后该独立谓词折叠进 kernel/cw_deploy_logic.has_deployable
    # 的同源去重,不再是 statefn 独立数量(随 ADR-0519 清账批删除)。
    'resolved 息帽(实现下沉 kernel/cw_economy)': ('', 'interest_cap_resolved'),
}



# ADR-0516 下沉批:interest/net_income/loss_exact/r_global/r_remaining/
# interest_cap_resolved 的实现下沉 kernel(cw_economy/cw_plane_table,
# kernel 判据消费需保持桶依赖矩阵);上表对应条目期望 owners=[]——
# statefn 模块只剩 import 重定向(单一源在 kernel,本断言辖「cw4 内
# 零第二实现」,kernel 侧唯一性由重定向 import + ruff F401 守)。


class TestSingleImplementation:

    def test_each_quantity_defined_exactly_once(self) -> None:
        # 全包 def/赋值符号收集(ast,静态)
        defs: dict[str, list[str]] = {}
        for py in CW4_DIR.rglob('*.py'):
            tree = ast.parse(py.read_text(encoding='utf-8'))
            mod = py.stem if py.parent.name == 'statefn' else ''
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    defs.setdefault(node.name, []).append(mod)
        for quantity, (mod, func) in QUANTITY_OWNERS.items():
            owners = defs.get(func, [])
            expected = [mod] if mod else []   # mod='' = 实现已下沉 kernel,
            # statefn 只剩重定向(cw4 内零第二实现;见 QUANTITY_OWNERS 注)
            assert owners == expected, \
                f'{quantity}: 符号 {func} 期望仅实现于 statefn/{mod},实际 {owners}'

    def test_registry_functions_not_reimplemented(self) -> None:
        # E[refreshes]/refresh_prob 系 cw_shop_odds 注册表单一源(【注】),
        # cw4 只 import 消费——全包禁出现同名 def(重算=第二观测源,④-5)
        defs: set[str] = set()
        for py in CW4_DIR.rglob('*.py'):
            tree = ast.parse(py.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    defs.add(node.name)
        assert 'expected_refreshes' not in defs
        assert 'refresh_prob' not in defs
        assert 'streak_gold' not in defs
        assert 'sell_refund' not in defs

    def test_no_private_phi_export(self) -> None:
        # R5-7/R6-4 墓碑守卫:全量 Φ 数值不进对外输出列(horizon.__all__ 无
        # Φ 项),且其他 cw4 模块禁引用私有 Φ̂ 名(裸 Φ̂ 消费位=模式审计红;
        # 私有名在场断言已删——_phi_hat 现为死码零调用点,在场锁零判别力)
        for name in horizon.__all__:
            assert 'phi' not in name.lower()
        for py in CW4_DIR.rglob('*.py'):
            if py.name == 'horizon.py':
                continue
            src = py.read_text(encoding='utf-8')
            assert '_phi_hat' not in src, py


# ==================== ⑤ 前置半步 0:挂后台效果资格谓词三测试位 ====================

class TestBenchEffectPredicate:
    """前置半步 0 测试位(§6.4 步 1 原文):①黑塔语境件不走 fuel_sell 等
    三消费位(谓词=资格载体,消费位随批 1 落地——本批锁谓词语义);③读
    装备态分支两态;载体缺口闭合(无载体字段单位恒不资格)。
    (原②「生锈词缀局未穿排除/已穿照常」由本文件
    TestBenchEffectContextAssembly::test_rust_from_enemy_affixes 经生产
    装配链端到端承接——同一真值格择超集保留,rule 7。)"""

    def test_h1_herta_context_protects(self) -> None:
        # ①星级供强语境:小黑塔保持资格(不走 fuel_sell/不进凑息/入桶不动子集)
        on = predicates.BenchEffectContext(herta_star_supply=True)
        assert predicates.bench_effect_qualified('黑塔', on)
        # 语境不在场:星级供强无承载对象,回归燃料类(类级默认不再静默放行)
        off = predicates.BenchEffectContext()
        assert not predicates.bench_effect_qualified('黑塔', off)

    def test_h3_equipped_branch_two_states(self) -> None:
        # ③读装备态分支:生锈不在场时穿/未穿两态均资格成立(合取条件左支真)
        for equipped in (False, True):
            ctx = predicates.BenchEffectContext(
                herta_star_supply=True, rust_affix_present=False, equipped=equipped)
            assert predicates.bench_effect_qualified('黑塔', ctx)

    def test_unknown_unit_no_carrier(self) -> None:
        # 无载体字段单位恒不资格(载体缺口闭合:字段不存在≠默认放行)
        assert not predicates.bench_effect_qualified(
            '飞霄', predicates.BenchEffectContext(herta_star_supply=True))
        assert predicates.RUST_AFFIX_NAME == '库藏生锈'


# ==================== ⑥ audit 载体 ====================

class TestAuditCarriers:

    def test_provisional_none_fail_closed(self) -> None:
        # 缺省全 None=fail-closed(断言对象 = 登记表缺省态)。setup 先
        # reset 做全局态隔离(测试纪律:被测载体含模块级全局):标定批
        # T-278/ADR-0639 起,生产构造位(MandateV1Strategy.__init__ →
        # calibration.apply)会合法注入 Δ/ε₂,裸断言对测试序不再鲁棒;
        # reset 后全 None = 缺省表无预置值,原语义不变。
        provisional.reset()
        for name in provisional.slot_names():
            assert provisional.is_none(name), name  # 缺省全 None=fail-closed

    def test_provisional_inject_and_reset(self) -> None:
        provisional.inject('THETA', provisional.CalibValue(
            1.0, injected_form=True))  # R24-2 注入形态(非生产开闸口径)
        got = provisional.get('THETA')
        assert got is not None and got.value == 1.0 and got.injected_form
        provisional.reset('THETA')
        assert provisional.get('THETA') is None

    def test_v_bar_sealed(self) -> None:
        with pytest.raises(ValueError):
            provisional.inject('V_BAR', provisional.CalibValue(1.0))
        assert provisional.get('V_BAR') is None  # 类型级封印族(R10-2)

    def test_proof_consts_whitelist(self) -> None:
        assert proof_consts.LAMBDA3_WINDOW == 3
        assert proof_consts.KAPPA_WINDOW == 3
        assert proof_consts.LAMBDA_SEGMENT_BOUND == 0.1  # 退役存档态,禁消费
        assert 'LAMBDA_SEGMENT_BOUND' in proof_consts.RETIRED
        assert frozenset(
            {'LAMBDA3_WINDOW', 'KAPPA_WINDOW'}) == proof_consts.ACTIVE

    def test_derived_registry_resolves(self) -> None:
        entries = derived.entry_points()
        assert len(entries) == len(derived.ENTRIES)
        assert callable(entries['L_loss_exact'])
        # 子形态:难度 interim 系【推·语料拟合】(R29-6),禁与机制推导量混列
        assert derived.subtag_of('difficulty_interim') == '语料拟合'
        assert derived.subtag_of('L_loss_exact') == ''


# ==================== 附:income/λ 查表口径速锁 ====================

class TestIncomeAndLookup:

    def test_net_income_schedule(self) -> None:
        from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
            income,
        )
        assert income.net_income(1, 0) == 3 + 1  # 1-1 轮基础 3 + streak(0)=1
        assert income.net_income(5, 3, 'battle') == 5 + 2 + 2
        assert income.net_income(3, 6) == 5 + 4  # 连胜表尾 4

    def test_pl_key_lookup(self) -> None:
        assert ld.make_key(104, 10, 1, 'battle') == 'D0|hp<=15|P1|battle'
        assert ld.make_key(None, 10, 1, 'battle') is None
        # 主表最大 λ_U 格(R4-N2):D1×hp≤15×P2+×battle λ_U=1.000
        ci = ld.lambda_ci('D1|hp<=15|P2+|battle')
        assert ci is not None and ci[1] == 1.000
        # 全表 CI 下端最小值 0.197(R35-3:v3.3 主表 min λ_L,格=
        # D0×hp>40×P1×noncombat)——0.1 死阈值恒空的实证前提
        ci_min = ld.lambda_ci('D0|hp>40|P1|noncombat')
        assert ci_min is not None and abs(ci_min[0] - 0.197) < 0.005

    def test_exposure_ge(self) -> None:
        key = 'D1|hp>40|P2+|battle'  # λ_U=0.905
        assert ld.exposure_ge(key, 100, 10.0, 90.0) is True   # 0.905×110≥90
        assert ld.exposure_ge(key, 10, 10.0, 90.0) is False
        assert ld.exposure_ge(None, 100, 10.0, 90.0) is None  # 域外 None


# ==================== ⑦ R200 修复批数值锁(IMPL_ADV_R200)====================

class TestPCompleteTail:
    """症1:P(命中 ≥ m) 尾概率 off-by-one 数值锁(出处=P38 闭式带
    尾概率式;旧实现求和含 x=m 项 ⇒ 算成 P(≥m+1),如 (m=1,q=0.5,
    n=1) 返 0.0——锁红即回归)。"""

    def test_tail_basic(self) -> None:
        assert vopt.p_complete([(1, 0.5)], 1) == 0.5
        assert vopt.p_complete([(2, 0.5)], 2) == 0.25

    def test_tail_boundary_m_over_refreshes(self) -> None:
        # m>refreshes:B(n) 支撑 [0,n] ⇒ P(≥m)=0(乘零短路,非 1−Σ 伪值)
        assert vopt.p_complete([(3, 0.5)], 2) == 0.0
        assert vopt.p_complete([(1, 0.5), (3, 0.5)], 2) == 0.0

    def test_tail_multi_factor(self) -> None:
        # 乘积式:m=1,q=0.5,n=3 两因子 ⇒ (1−0.125)²
        assert abs(vopt.p_complete([(1, 0.5), (1, 0.5)], 3)
                   - 0.875 ** 2) < 1e-12

    def test_q_zero_short_circuit(self) -> None:
        assert vopt.p_complete([(1, 0.0)], 5) == 0.0


class TestSlotQDenominator:
    """症2:slot_q 分母与注册表 _refresh_dist 同式 va−j−c(分子分母
    同扣 j;旧分母漏扣 j ⇒ 持牌越多 q 越低估)。"""

    def test_denominator_matches_registry_form(self) -> None:
        from sr_od.application.currency_war.data.cw_shop_odds import (
            DISTINCT_CARDS_PER_COST as V,
        )
        from sr_od.application.currency_war.data.cw_shop_odds import (
            POOL_COPIES_PER_CARD as A,
        )
        from sr_od.application.currency_war.data.cw_shop_odds import (
            refresh_prob,
        )
        level, cost, j, c = 6, 1, 5, 7
        expected = refresh_prob(level, cost) * (A[cost] - j) \
            / (V[cost] * A[cost] - j - c)
        assert abs(odds.slot_q(level, cost, j, c) - expected) < 1e-15
        # j 增大 ⇒ 分子分母同减,分母显著大于分子侧衰减前形态
        assert odds.slot_q(level, cost, j, c) \
            < odds.slot_q(level, cost, 0, c)

    def test_exhausted_pool_zero(self) -> None:
        assert odds.slot_q(6, 1, 27, 0) == 0.0   # a−j=0 构造性 0


class TestSearchWindows:
    """搜索窗口运行时确定性查表(ADR-0516 重锚:塌缩带锚——费档在窗内
    ⟺ 该级命中率 ≥ ω×峰值级命中率,ω=DEFAULT_REGISTRY.
    omega_collapse_ratio(0.1,ADR-0475 同源);档级口径=refresh_prob,
    单卡口径=p_shop 满池。旧 V̄ 门式(P57 双读法/e2_24.7 对拍锚)随
    V̄ 链退役作废;下表按 REFRESH_PROB 表值 + 峰值查表
    (1费峰 lv3/2费峰 lv6/3费峰 lv7/4费峰 lv9/5费峰 lv9)第三方可重算:
    例 lv10 1费 0.05 < 0.1×1.0 ⇒ 出窗;lv6 4费 0.05 = 0.1/2×峰值
    0.3?否——0.05/(0.3)=0.167 ≥ 0.1 ⇒ 在窗。"""

    #: ω 锚全表(tier 口径;DEFAULT_REGISTRY.omega_collapse_ratio=0.1)
    TIER_OMEGA: dict[int, frozenset[int]] = {
        1: frozenset({1}), 2: frozenset({1}), 3: frozenset({1}),
        4: frozenset({1, 2, 3}), 5: frozenset({1, 2, 3}),
        6: frozenset({1, 2, 3, 4}), 7: frozenset({1, 2, 3, 4}),
        8: frozenset({1, 2, 3, 4, 5}), 9: frozenset({1, 2, 3, 4, 5}),
        10: frozenset({2, 3, 4, 5}),
    }
    #: ω 锚全表(card 口径,p_shop 满池)
    CARD_OMEGA: dict[int, frozenset[int]] = {
        1: frozenset({1}), 2: frozenset({1}), 3: frozenset({1}),
        4: frozenset({1, 2, 3}), 5: frozenset({1, 2, 3}),
        6: frozenset({1, 2, 3, 4}), 7: frozenset({1, 2, 3, 4, 5}),
        8: frozenset({1, 2, 3, 4, 5}), 9: frozenset({1, 2, 3, 4, 5}),
        10: frozenset({2, 3, 4, 5}),
    }

    def test_full_table_omega_anchor(self) -> None:
        """全表对拍(ω 锚 × 全等级 1-10,两口径)。"""
        for lv in range(1, 11):
            assert odds.tier_search_window(lv) == self.TIER_OMEGA[lv], lv
            assert odds.card_search_window(lv) == self.CARD_OMEGA[lv], lv

    def test_collapse_excludes_far_below_peak(self) -> None:
        """塌缩排除例:lv10 1费(0.05 < 0.1×峰值 1.0)出窗;lv4 4费
        (p=0,该级不出)出窗。"""
        assert 1 not in odds.tier_search_window(10)
        assert 4 not in odds.tier_search_window(4)

    def test_omega_param_tightens_window(self) -> None:
        """ω 参数化收紧:ω=1(只放峰值级自身)窗口收窄到该费档恰在
        峰值级的行(结构性烟测,不锁分布数值)。"""
        t1 = odds.tier_search_window(8, 1.0)
        assert t1 <= odds.tier_search_window(8)


class TestBenchEffectContextAssembly:
    """症3:三消费位共享语境装配(可观测来源+缺省保守端)。
    通道级消费锁(fuel_sell/凑息/支付支撑)在 test_cw_mandate_v1。"""

    @staticmethod
    def _unit(name: str = '黑塔', equipped: bool = False):
        from sr_od.application.currency_war.kernel.cw_vocab import BenchChar
        bc = BenchChar(slot=1, char_id=name)
        bc.equips = ['装备X'] if equipped else []
        return bc

    @staticmethod
    def _state(active_strategies=None, enemy_affixes=None, deployed=None):
        from sr_od.application.currency_war.kernel.cw_vocab import CwWorkFrame
        st = CwWorkFrame()
        st.active_strategies = list(active_strategies or [])
        st.enemy_affixes = list(enemy_affixes or [])
        st.deployed = list(deployed or [])
        return st

    def test_herta_via_augment_and_board(self) -> None:
        # 黑塔纪元 augment 局 ⇒ 语境在场(单一源=proof.DIRECT_LINE_
        # SIGNAL_STRATEGIES)
        ctx = predicates.bench_effect_context(
            self._state(active_strategies=['黑塔纪元']), self._unit())
        assert ctx.herta_star_supply and not ctx.rust_affix_present
        # 板面存在承载对象「大黑塔」⇒ 语境在场
        from sr_od.application.currency_war.kernel.cw_vocab import BenchChar
        ctx2 = predicates.bench_effect_context(
            self._state(deployed=[BenchChar(slot=1, char_id='大黑塔')]),
            self._unit())
        assert ctx2.herta_star_supply
        # 线内含承载对象 ⇒ 语境在场(换线过渡期)
        ctx3 = predicates.bench_effect_context(
            self._state(), self._unit(), k_members=('大黑塔',))
        assert ctx3.herta_star_supply
        # 语境缺场(空 state)⇒ 星级供强无承载对象
        ctx4 = predicates.bench_effect_context(self._state(), self._unit())
        assert not ctx4.herta_star_supply

    def test_rust_from_enemy_affixes(self) -> None:
        aff = ['库藏生锈']
        ctx = predicates.bench_effect_context(
            self._state(enemy_affixes=aff), self._unit())
        assert ctx.rust_affix_present
        assert not predicates.bench_effect_qualified('黑塔', ctx)  # 未穿排除
        # 已穿 + 语境在场(例外①②均过)⇒ 照常入桶不动子集
        ctx_eq = predicates.bench_effect_context(
            self._state(enemy_affixes=aff, active_strategies=['黑塔纪元']),
            self._unit(equipped=True))
        assert ctx_eq.equipped
        assert predicates.bench_effect_qualified('黑塔', ctx_eq)

    def test_state_none_conservative_end(self) -> None:
        """缺读保守端:state=None ⇒ 按保护端处置(herta 在场 ∧ 生锈
        不在场 ⇒ 载体件资格成立;申报行为,影响面=仅 bench_effect 载体件)。"""
        ctx = predicates.bench_effect_context(None, self._unit())
        assert not ctx.rust_affix_present and ctx.herta_star_supply
        assert predicates.bench_effect_qualified('黑塔', ctx)
