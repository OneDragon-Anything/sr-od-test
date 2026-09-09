"""cw4 判据契约层测试(R198 批:assume-guarantee 契约化,IMPL_DESIGN §4.2.2)。

目标形态覆盖面(2026-09-09 重建批,TARGET_SPEC #17「契约层核+事件接线」):
- ①CONTRACTS 注册完备性静态断言(criteria 全公开函数 + 第七面 proof 判据位
  + 三先例非 criteria 消费位,漏登记=红);
- ②先例前提谓词代表行 + fail-closed(未登记键与谓词异常均弃权+计数,不抛);
- ③arm1 板满 cap 口径谓词数学 + M3「板未满不发射」decide 链反面锁;
- ④禁绕过 ensure_contract 直调的 AST 守卫(主测+裸名直调负测);
- ⑤arm1 消费位事件接线正反(常数 cap 喂入=违例计数+弃权 / state 派生链
  喂入=零违例+照发)。

来源指针:本文件原地收核(契约层核主体留位);arm1 板满段 2026-09-09 合并批
自 test_cw_zero_refresh 迁入(D27 指认);跨角色阵营共享腿由
test_cw_prep_flag_machine 的 S3 纯函数翻转锁分辖。
其余历史锁已退役(git 可复活),退役面墓碑:
- 先例② r2_gold_minus_reserve / r1_commitment 恒真前提 / K 空窗回退前提
  (P86 六例形态)——谓词正反测同类多条,择代表行保留;
- shop/entry 接线核验点正反测(ev_buy 弃权/空窗波/正常波/骨架波零违例锚);
- AST 守卫负测 basename 逃逸腿与全限定白名单正例腿(主测+裸名负测已辖
  守卫本体,负测留一)。
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    LevelUpShop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import proof
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    buy,
    contracts,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    equipment as crit_equipment,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    levelup as crit_levelup,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    refresh as crit_refresh,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    sell as crit_sell,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    stockpile as crit_stockpile,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import predicates
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_comp as _comp,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_decide as _decide,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_session as _session,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_state as _state,
)

# ===== ① 注册完备性静态断言(表覆盖=criteria 全公开函数)=====

#: criteria 七面中的六模块(第七面「换线」= proof 判据位,另行断言)
_FACE_MODULES = {
    'buy': buy, 'sell': crit_sell, 'levelup': crit_levelup,
    'refresh': crit_refresh, 'stockpile': crit_stockpile,
    'equipment': crit_equipment,
}


class TestRegistryCompleteness:

    def test_covers_all_criteria_public_functions(self):
        """criteria 六模块全公开函数逐一在册(漏登记=红)。"""
        missing: list[tuple[str, str]] = []
        for mod_name, mod in _FACE_MODULES.items():
            for attr_name, obj in vars(mod).items():
                if attr_name.startswith('_'):
                    continue
                if inspect.isfunction(obj) \
                        and inspect.getmodule(obj) is mod:
                    if (mod_name, attr_name) not in contracts.CONTRACTS:
                        missing.append((mod_name, attr_name))
        assert not missing, f'判据漏登记契约: {missing}'

    #: 零调用面墓碑键(函数已物理删除、登记行保留枚举完备性;先例 =
    #: criteria/__init__.py BYPASS_TABLE refresh.r1_start 墓碑注)。
    #: 唯一在册成员 = equipment.affix_allocation:判据出处纠错批删除
    #: (孤儿第二实现+死键,生产单一源 = cw_equip_env
    #: .resolve_affix_priority_order),禁为保绿恢复死代码。
    _TOMBSTONED_KEYS: frozenset[tuple[str, str]] = frozenset({
        ('equipment', 'affix_allocation'),
    })

    def test_contract_entries_reference_existing_functions(self):
        """在册键(除三先例非 criteria 消费位)必须对应真实判据函数;
        零调用面墓碑键豁免(函数已删、登记行保留,docstring 记删除原因)。"""
        sources = dict(_FACE_MODULES)
        sources.update({'proof': proof, 'predicates': predicates})
        for (mod_name, fn_name) in contracts.CONTRACTS:
            mod = sources.get(mod_name)
            if mod is None:
                continue        # mandate 邻接位(先例① dominance 消费位)
            if (mod_name, fn_name) in self._TOMBSTONED_KEYS:
                continue
            assert hasattr(mod, fn_name), \
                f'契约键 ({mod_name}, {fn_name}) 无对应函数'

    def test_proof_face_and_precedent_keys_registered(self):
        """第七面 proof 判据位 + 三先例消费位 + K 空窗回退消费位
        显式在册。"""
        for key in (('proof', 'stop_buy'), ('proof', 'should_switch'),
                    ('proof', 'signal_arm'),
                    ('mandate', 'dominance_buy'),
                    ('mandate', 'core_single_card_buy_eligible'),
                    ('predicates', 'arm1_existence'),
                    ('shop', 'k_projection')):
            assert key in contracts.CONTRACTS, f'{key} 未登记'

    def test_unconditional_entries_declare_scope(self):
        """前提恒真(None)也须显式辖域声明 + 规格锚(禁空串)。"""
        for key, c in contracts.CONTRACTS.items():
            assert c.scope, f'{key} 辖域声明缺失'
            assert c.anchor, f'{key} 规格锚缺失'


# ===== ② 先例前提谓词代表行 + fail-closed =====

class TestPrecedentPredicates:

    def test_precedent1_s_reserve_line_formed(self):
        """先例①(S 预留辖域):目标线成型放行;未成型弃权+计数。"""
        ct: dict = {}
        assert contracts.ensure_contract(
            ('buy', 'ev_buy_candidates'),
            contracts.ContractCtx(k_members=('a', 'b')), ct)
        assert 'criteria_contract_violation:buy.ev_buy_candidates' not in ct
        assert not contracts.ensure_contract(
            ('buy', 'ev_buy_candidates'),
            contracts.ContractCtx(k_members=()), ct)
        assert ct['criteria_contract_violation:buy.ev_buy_candidates'] == 1

    def test_precedent3_arm1_cap_level_driven(self):
        """先例③(arm1 口径):cap 现读放行;None(固定常数兜底)弃权+计数。"""
        ct: dict = {}
        assert contracts.ensure_contract(
            ('predicates', 'arm1_existence'),
            contracts.ContractCtx(deploy_cap=5), ct)
        assert not contracts.ensure_contract(
            ('predicates', 'arm1_existence'),
            contracts.ContractCtx(deploy_cap=None), ct)
        assert ct['criteria_contract_violation:predicates.arm1_existence'] == 1

    def test_unknown_key_and_predicate_error_fail_closed(self, monkeypatch):
        """fail-closed:未登记键与谓词异常均弃权+计数,不抛异常。"""
        ct: dict = {}
        assert not contracts.ensure_contract(
            ('buy', 'no_such_fn'), contracts.ContractCtx(), ct)
        assert ct['criteria_contract_violation:buy.no_such_fn'] == 1

        def _boom(_ctx: contracts.ContractCtx) -> bool:
            raise RuntimeError('predicate crash')

        # 注入 fixture 键 = 现存契约键(P25 占位接管批,ADR-0569:旧键
        # ('buy','p2_lock_buy') 随生产行删除成死语义锚,不测死对象)。
        fake = {('sell', 'sell_for_interest'): contracts.Contract(
            _boom, '测试注入位', '测试')}
        monkeypatch.setattr(contracts, 'CONTRACTS', fake)
        assert not contracts.ensure_contract(
            ('sell', 'sell_for_interest'), contracts.ContractCtx(), ct)
        assert ct['criteria_contract_violation:sell.sell_for_interest'] == 1


# ===== ②b arm1 板满 cap 口径(承 test_cw_zero_refresh 迁入,2026-09-09)=====
# 原壳「病灶2」零刷新事故修复的谓词数学正反锁 + M3 decide 链反面锁;
# 壳退役后按 D27 指认落位本文件(cap 喂入契约 TestMandateArm1Wiring 与
# 前提谓词 TestPrecedentPredicates::precedent3 均已在此,同主题归并)。

class TestArm1CapSemantics:
    """arm1_existence 板满 cap 口径(谓词数学直调;cap 口径直调主载体——
    跨角色阵营共享腿由 test_cw_prep_flag_machine 的
    TestS3NoVariable::test_m3_predicate_flips_with_input 分辖)。"""

    def test_board_full_at_level_cap_triggers(self):
        """板满=当前 cap(等级驱动)而非固定槽表 10:deployed==cap(5)
        + bench 等待件共享阵营/流派 ⇒ 真(修复点:旧语义此帧恒 False)。"""
        board = [_bc('爻光') for _ in range(5)]
        bench = [_bc('爻光')]
        assert predicates.arm1_existence(
            5, [b.char_id for b in bench],
            [d.char_id for d in board], deploy_cap=5) is True

    def test_board_not_full_below_cap_no_trigger(self):
        """板未满(deployed < cap)⇒ 假——升级前应先部署(M1 优先)。"""
        board = [_bc('爻光') for _ in range(3)]
        bench = [_bc('爻光')]
        assert predicates.arm1_existence(
            3, [b.char_id for b in bench],
            [d.char_id for d in board], deploy_cap=5) is False

    def test_m3_silent_when_board_below_cap(self):
        """反面:板未满(deployed=3/cap=5)同 bench/金 ⇒ M3 不发射
        (升级价值以「有等待件上不了场」为前提)。

        decide 链级唯一反面锁:shop_line 侧反面为「板满+整批不够」与
        「等级帽」两形(亲读证实无板未满帧),本锁辖「谓词假 ⇒ 零
        LevelUpShop 发射」的消费位接线。"""
        comp = _comp()
        deployed = [_bc('爻光', slot=i + 1) for i in range(3)]
        bench = [_bc('爻光', slot=1)]
        st = _state(gold=8, bench=bench, deployed=deployed,
                    level=3, deploy_cap=5, xp=(0, 4))
        acts = _decide(st, _session(comp))
        assert not [a for a in acts if isinstance(a, LevelUpShop)]


# ===== ④ 静态守卫:禁绕过 ensure_contract 直调判据(FIX_REVIEW 防线硬化)=====
# 【R200-F1 重写】旧正则守卫两盲区(REWORK_REVIEW_20260903 §3 F1 实证):
# ①只捕 ``<alias>.<fn>(`` 模块属性形态——``from ...criteria.levelup
# import lv9_stop`` 后裸名直调漏网;②白名单按 basename 豁免——任意
# 目录下同名 shop.py/entry.py/mandate.py 逃逸。本版改 AST 分析(import
# 绑定名+调用名联合解析)且白名单改**路径全限定**,两盲区各配负测试。

#: 判据函数 → 实现模块的 import 尾径(cw4 包内点分尾径;调用点只要
#: 绑定到该模块即入扫描面——与 CONTRACTS 键集+四判据位对齐;六面
#: 清单单一源 = 上方 _FACE_MODULES,禁另抄字面量)
_FN_OWNER_TAIL: dict[str, str] = {}
for (_mod, _fn) in contracts.CONTRACTS:
    if _mod in _FACE_MODULES:
        _FN_OWNER_TAIL[_fn] = f'criteria.{_mod}'
    elif _mod == 'proof':
        _FN_OWNER_TAIL[_fn] = 'proof'
    elif _mod == 'predicates':
        _FN_OWNER_TAIL[_fn] = 'statefn.predicates'

#: 已接线消费位白名单(路径全限定,相对 src 根;三文件的判据调用均经
#: ensure_contract 门或为其辖下接线;criteria/statefn/proof 定义文件与
#: 测试仓不在此约束面)。sim/checks/ledger.py = 离线回放对账消费位:
#: 对历史对局档案按同一判据函数复算做对拍,属回放对拍防线本体,
#: 与生产旁路禁令不同域。
_WIRED_CALLER_PATHS: frozenset[str] = frozenset({
    'sr_od/application/currency_war/strategies/impl/mandate_v1/shop.py',
    'sr_od/application/currency_war/strategies/impl/mandate_v1/entry.py',
    'sr_od/application/currency_war/strategies/impl/mandate_v1/mandate.py',
    'sr_od/application/currency_war/sim/checks/ledger.py',
})

#: 豁免路径前缀(判据定义面:criteria 包内部互调/谓词实现/proof 实现)
_EXEMPT_PREFIXES: tuple[str, ...] = (
    'sr_od/application/currency_war/strategies/impl/mandate_v1/criteria/',)
_EXEMPT_PATHS: frozenset[str] = frozenset({
    'sr_od/application/currency_war/strategies/impl/mandate_v1/statefn/predicates.py',
    'sr_od/application/currency_war/strategies/impl/mandate_v1/proof.py',
})

#: 判据函数可绑定的源模块(import 尾径,点分;绑定来自这些模块的
# import 才算判据调用点)——从 _FN_OWNER_TAIL 值集推导(mandate/shop
# 等非判据位键不入表,与旧手抄集内容恒等),禁另抄字面量。
_OWNER_TAILS: frozenset[str] = frozenset(_FN_OWNER_TAIL.values())

#: 扫描面(守卫出慢桶批收窄):守卫保护对象 = currency_war 子树。
#: 判据函数定义面(criteria 六面/proof/statefn.predicates)与全部
#: 已接线消费位均住该子树,src 树内子树外对 mandate_v1 零引用
#: (收窄时全树 grep 实证)——遍历收窄只减「保护对象外的扫描」,
#: 子树内检查项逐位不变;offender 路径与白名单匹配恒按 src 根
#: 全限定口径,与扫描面解耦。捕获力两道独立证据:负测试三例
#: (盲区①/②/白名单正例,与生产同参调用形状)+ 金丝雀验证
#: (子树内临时注入裸名直调违例 → 守卫主测报红 → 移除)。
_CRITERIA_SCAN_SUBDIR: tuple[str, ...] = ('sr_od', 'application',
                                          'currency_war')


def _find_criteria_direct_calls(src_root: Path,
                                scan_subdir: tuple[str, ...] | None = None
                                ) -> list[str]:
    """AST 扫描:白名单外文件中「绑定到判据模块的函数」调用点。

    解析规则(import 绑定名+调用名联合):
    - ``from <cw4.criteria.buy> import lv9_stop`` / ``... import buy``
      / ``import <...criteria.buy> as b`` → 记录本地名→import 尾径;
    - 调用 ``lv9_stop(...)``(裸名,盲区①)/ ``b.lv9_stop(...)`` /
      ``mod.attr.lv9_stop(...)``(点链)→ 绑定解析命中且函数属主一致
      = 判据直调点。白名单豁免按**全限定文件路径**(堵 basename 逃逸,
      盲区②)。

    扫描面:``scan_subdir`` 给定时只遍历 ``src_root`` 下该子树
    (生产入口传 _CRITERIA_SCAN_SUBDIR,即守卫保护对象;缺省全树,
    供临时目录复用分析本体)。``rel`` 恒按 ``src_root`` 计算——
    白名单是全限定路径,匹配口径不随扫描面收窄变化。
    """
    offenders: list[str] = []
    scan_root = src_root.joinpath(*scan_subdir) if scan_subdir else src_root
    cw4_prefix = 'sr_od.application.currency_war.strategies.impl.mandate_v1.'
    for py in sorted(scan_root.rglob('*.py')):
        rel = py.relative_to(src_root).as_posix()
        if rel in _WIRED_CALLER_PATHS or rel in _EXEMPT_PATHS:
            continue
        if rel.startswith(_EXEMPT_PREFIXES):
            continue
        try:
            tree = ast.parse(py.read_text(encoding='utf-8'))
        except SyntaxError:
            continue
        # 本地名 → import 尾径(判据源模块**及其包前缀**的绑定入表——
        # 包级绑定 ``from <cw4.criteria> import levelup`` 经 _owns 通配)
        def _admitted(tail: str) -> bool:
            if tail == '':
                return True    # cw4 包本体(from <cw4> import proof)
            return any(t == tail or t.startswith(tail + '.')
                       for t in _OWNER_TAILS)

        bound: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ''
                if not mod.startswith(cw4_prefix):
                    continue
                tail = mod[len(cw4_prefix):]
                if not _admitted(tail):
                    continue
                for alias in node.names:
                    bound[alias.asname or alias.name] = tail
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name or ''
                    if not mod.startswith(cw4_prefix):
                        continue
                    tail = mod[len(cw4_prefix):]
                    if _admitted(tail):
                        bound[alias.asname or alias.name] = tail

        def _dotted(node: ast.AST) -> str | None:
            # Name / Attribute 点链 → 顶层本地名(判定绑定解析够用)
            parts: list[str] = []
            while isinstance(node, ast.Attribute):
                parts.append(node.attr)
                node = node.value
            if not isinstance(node, ast.Name):
                return None
            parts.append(node.id)
            return '.'.join(reversed(parts))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fname: str | None = None
            root_expr: ast.AST | None = None
            if isinstance(node.func, ast.Name):
                fname, root_expr = node.func.id, node.func
            elif isinstance(node.func, ast.Attribute):
                fname, root_expr = node.func.attr, node.func.value
            if fname is None or fname not in _FN_OWNER_TAIL:
                continue
            owner_tail = _FN_OWNER_TAIL[fname]
            # 包级绑定通配:from <cw4> import proof / from <cw4.criteria>
            # import levelup(子模块名导入)⇒ 绑定尾径是属主的包前缀
            def _owns(tail: str | None, _owner: str = owner_tail) -> bool:
                if tail is None:
                    return False
                return (tail == '' or _owner == tail
                        or _owner.startswith(tail + '.'))

            if isinstance(node.func, ast.Name):
                # 裸名直调:本地名即函数名且绑定到属主模块
                if _owns(bound.get(fname)):
                    offenders.append(f'{rel}: 裸名直调 {fname}()')
                continue
            # 属性调用:<绑定名>.<fn> / 点链——解析顶层名
            dotted = _dotted(root_expr)
            if dotted is None:
                continue
            top = dotted.split('.')[0]
            if _owns(bound.get(top)):
                offenders.append(f'{rel}: {dotted}.{fname}()')
    return offenders


class TestNoBypassDirectCalls:

    @staticmethod
    def _src_root() -> Path:
        # proof.py 位于 src/sr_od/application/currency_war/strategies/impl/
        # mandate_v1/ 下 7 层 ⇒ parents[6] 即 src 根。【R200-F1 勘误】旧式
        # ``parents[N] / 'src'`` 解析到 src/src(不存在)⇒ rglob 恒空、
        # 守卫形同虚设(零 offender 恒绿)——修复后 src 根直取 parents[N]。
        # (统一迁移批:proof 自 decision/cw4 迁入 strategies/impl/mandate_v1,
        # 层深 6→7,N 随之 5→6。)
        return Path(proof.__file__).resolve().parents[6]

    def test_criteria_public_calls_whitelisted(self):
        """静态守卫(AST 版):currency_war 子树内判据函数调用点只允许
        出现在已接线消费位(全限定路径白名单)——防新增消费位绕过
        ensure_contract 直调。扫描面 = 守卫保护对象子树
        (_CRITERIA_SCAN_SUBDIR,收窄理由与零损失证据见其注释);
        AST 解析 import 绑定名+调用名,覆盖裸名直调与模块属性两
        形态(旧正则守卫的盲区①,REWORK_REVIEW_20260903 F1)。"""
        offenders = _find_criteria_direct_calls(self._src_root(),
                                                _CRITERIA_SCAN_SUBDIR)
        assert not offenders, \
            f'判据直调点绕过 ensure_contract(白名单外): {offenders}'

    def test_guard_catches_bare_name_direct_call(self, tmp_path):
        """负测试(盲区①=红):from-import 裸名直调 ``lv9_stop(3)`` 在
        旧正则守卫下漏网(正则只捕 ``<alias>.<fn>(`` 形态)——AST 版
        经 import 绑定名解析必须报红。"""
        src = tmp_path / 'src'
        subtree = src.joinpath(*_CRITERIA_SCAN_SUBDIR)
        (subtree / 'decision').mkdir(parents=True)
        (subtree / 'decision' / 'new_consumer.py').write_text(
            'from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria'
            '.levelup import lv9_stop\n'
            'def f() -> None:\n    lv9_stop(3)\n', encoding='utf-8')
        offenders = _find_criteria_direct_calls(src, _CRITERIA_SCAN_SUBDIR)
        assert any('裸名直调 lv9_stop' in o for o in offenders), offenders


# ===== ⑤ R1 接线正反测(mandate arm1 消费位;FIX_REVIEW 场景 A 复验)=====

class TestMandateArm1Wiring:

    def _frame(self, deploy_cap):
        from sr_od.application.currency_war.kernel.cw_state import (
            DEPLOYED_CAPACITY,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import mandate
        bench = [BenchChar(slot=i + 1, char_id='爻光')
                 for i in range(DEPLOYED_CAPACITY)]
        board = [BenchChar(slot=i + 1, char_id='爻光')
                 for i in range(DEPLOYED_CAPACITY)]
        return mandate.MandateFrame(
            gold=200, level=3, bench=bench, deployed=board,
            deploy_cap=deploy_cap, node_type='normal', stop_flag=False,
            k_members=('爻光',), round_num=2)

    def test_constant_cap_feed_violates_and_abstains(self):
        """对抗场景 A 复验:固定槽表常数 cap 喂入(无 state 派生链)
        ⇒ 违例计数 + M3 弃权(修复前=零计数+M3 照发,旁路实证形态)。"""
        from sr_od.application.currency_war.kernel.cw_state import (
            DEPLOYED_CAPACITY,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import mandate
        sess = _session(('爻光',))
        out = mandate.run_mandate(self._frame(DEPLOYED_CAPACITY), sess)
        assert state_of(sess).cw4_counters.get(
            'criteria_contract_violation:predicates.arm1_existence', 0) >= 1
        assert not any(type(e.action).__name__ == 'LevelUp' for e in out)

    def test_state_derived_cap_emits_without_violation(self):
        """正向:state.max_units() 派生链喂入 ⇒ 零违例;板满(cap=板量)
        ⇒ M3 照发(接线不误伤)。(夹具补 hp=100:候选③批起 M3 消费
        血预算停升级门,hp 无真值帧 fail-closed 拒升级——真值帧才是本锁
        要钉的语义。)"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import mandate
        st = _state(gold=200, level=3, hp=100)
        st.deployed = [BenchChar(slot=1, char_id='爻光'),
                       BenchChar(slot=2, char_id='桑博'),
                       BenchChar(slot=3, char_id='丹恒·饮月')]
        st.bench = [BenchChar(slot=1, char_id='停云')]
        frame = mandate.MandateFrame(
            gold=200, level=3, bench=list(st.bench),
            deployed=list(st.deployed),
            deploy_cap=st.max_units(), node_type='normal', stop_flag=False,
            k_members=('爻光',), round_num=2)
        sess = _session(('爻光',))
        out = mandate.run_mandate(frame, sess, state=st)
        assert state_of(sess).cw4_counters.get(
            'criteria_contract_violation:predicates.arm1_existence', 0) == 0
        assert any(type(e.action).__name__ == 'LevelUp' for e in out)


if __name__ == '__main__':
    pytest.main([__file__])
