"""cw4 判据契约层测试(R198 批:assume-guarantee 契约化,IMPL_DESIGN §4.2.2)。

覆盖:①CONTRACTS 注册完备性静态断言(criteria 全公开函数 + 第七面
proof 判据位 + 三先例非 criteria 消费位,漏登记=红);②三先例前提
谓词正反测(前提成立放行/不成立弃权+``criteria_contract_violation``
分键计数);③接线核验点正反测(shop/entry 消费位,前提不成立 ⇒ 判据
本帧弃权零发射 + 计数;正常帧零违例计数=契约层零误伤锚)。
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY, get_comp
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import proof
from sr_od.application.currency_war.strategies.impl.mandate_v1.audit import provisional
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)
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


def _comp():
    names = [c.name for c in COMP_LIBRARY if getattr(c, 'core_chars', None)]
    return get_comp(names[0])


def _members(comp) -> list[str]:
    ms = list(comp.core_chars) + list(getattr(comp, 'shared_chars', []) or [])
    return list(dict.fromkeys(ms))


def _session(comp=None) -> StrategySession:
    s = StrategySession()
    state_of(s).cw4_counters = {}
    state_of(s).target_comp = comp
    state_of(s).cw4_line_state = proof.LineState()
    return s


def _state(gold: int = 30, shop=None, bench=None, deployed=None,
           level: int = 3, node=None, hp: int = 100) -> GameState:
    st = GameState(gold=gold, level=level, round_num=2, node_type=node,
                   hp=hp)
    st.shop = shop if shop is not None else []
    st.bench = bench if bench is not None else []
    st.deployed = deployed if deployed is not None else []
    return st


def _card(name: str, cost: int = 3, star: int = 1) -> ShopCard:
    return ShopCard(x=100, name=name, cost=cost, star=star)


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _decide(state: GameState, session: StrategySession, cfg=None):
    class _Cfg:
        def __init__(self, ev_arm: str = 'full') -> None:
            self.ev_arm = ev_arm

    from sr_od.application.currency_war.sim.engine_p1 import (
        sim_decision_registry,
    )
    strat = MandateV1Strategy(registry=sim_decision_registry())
    session.shop_state_frame = state
    return strat.decide_shop_screen(session, cfg or _Cfg())


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


# ===== ② 三先例前提谓词正反测 =====

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

    def test_precedent2_r2_gold_minus_reserve(self):
        """先例②(r2 预算门):金−预留语境在场放行;缺输入弃权+计数。"""
        ct: dict = {}
        assert contracts.ensure_contract(
            ('refresh', 'r2_budget'),
            contracts.ContractCtx(gold=10, reserve=0), ct)
        assert not contracts.ensure_contract(
            ('refresh', 'r2_budget'),
            contracts.ContractCtx(gold=10, reserve=None), ct)
        assert ct['criteria_contract_violation:refresh.r2_budget'] == 1
        assert not contracts.ensure_contract(
            ('refresh', 'r2_budget'),
            contracts.ContractCtx(gold=None, reserve=0), ct)
        assert ct['criteria_contract_violation:refresh.r2_budget'] == 2

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

    def test_r1_contract_none_precedent(self):
        """r1 承诺账前提(ADR-0516 形式二重锚):判据输入全为游戏定义量
        (REFRESH_PROB/XP 表/息律),无标定槽位依赖 ⇒ 前提恒真(None
        登记)——旧 ev_slot 核验(V_GAP 槽位现读)随 V̄ 链退役消解;
        r1_start(无生产消费端的纯数函数)保留 ev_slot 核验原锁。"""
        ct: dict = {}
        assert contracts.ensure_contract(
            ('refresh', 'r1_commitment_account'),
            contracts.ContractCtx(), ct)
        assert contracts.ensure_contract(
            ('refresh', 'r1_commitment_account'),
            contracts.ContractCtx(ev_slot=24.7), ct)   # 恒真前提:ctx 不辖
        assert not ct
        assert contracts.ensure_contract(
            ('refresh', 'r1_start'),
            contracts.ContractCtx(ev_slot=None), ct)
        assert not contracts.ensure_contract(
            ('refresh', 'r1_start'),
            contracts.ContractCtx(ev_slot=10.0), ct)
        assert ct['criteria_contract_violation:refresh.r1_start'] == 1

    def test_k_projection_domain_covered_derivable(self):
        """第三病灶(K 空窗回退)前提(可核验派生形态):k_target 非 None
        (锁线世界)或供给缺帧(保守侧)放行;供给在场而回退实解析空集
        (「回退字面量空元组但保留声明」复发形态)弃权+计数。"""
        ct: dict = {}
        # 锁线世界:无回退义务
        assert contracts.ensure_contract(
            ('shop', 'k_projection'),
            contracts.ContractCtx(k_target=object()), ct)
        # 空窗世界+供给在场+回退实解析非空
        assert contracts.ensure_contract(
            ('shop', 'k_projection'),
            contracts.ContractCtx(k_target=None, k_fallback_available=True,
                                  k_fallback_resolved=frozenset({'a'})), ct)
        # 供给缺帧:保守侧不回退(合法 fail 方向)
        assert contracts.ensure_contract(
            ('shop', 'k_projection'),
            contracts.ContractCtx(k_target=None, k_fallback_available=False,
                                  k_fallback_resolved=None), ct)
        # 供给在场而回退解析空集=复发形态
        assert not contracts.ensure_contract(
            ('shop', 'k_projection'),
            contracts.ContractCtx(k_target=None, k_fallback_available=True,
                                  k_fallback_resolved=frozenset()), ct)
        assert ct['criteria_contract_violation:shop.k_projection'] == 1

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


# ===== ③ 接线核验点正反测(shop/entry 消费位)=====

class TestWiringShop:

    def test_ev_buy_abstains_without_target_line(self):
        """接线正反:K 未成型 ⇒ EV 买面弃权(零 ev_buy 发射)+违例计数。

        注入形态(U_X/T_SEARCH_A 开闸)下前提成立与否是唯一差:
        target_comp=None 时契约层必须拦住候选评估。
        """
        comp = _comp()
        off_line = '不存在于任何线的散件_x'
        st = _state(gold=60, shop=[_card(off_line, cost=1, star=1)])
        sess = _session(comp)      # 先证正向:有 K 时契约放行,候选可评估
        try:
            provisional.inject('U_X', provisional.CalibValue(
                value=1.0, injected_form=True))
            provisional.inject('T_SEARCH_A', provisional.CalibValue(
                value=1.0, injected_form=True))
            _decide(st, sess)
            # 线外件是否入选属判据域不在此锁;锁的是契约层零违例
            assert not [k for k in state_of(sess).cw4_counters
                        if k.startswith('criteria_contract_violation')]
            # 反向:同一店面,target_comp=None(目标线未成型)
            sess2 = _session(None)
            acts2 = _decide(_state(gold=60,
                                   shop=[_card(off_line, cost=1, star=1)]),
                            sess2)
            assert not [a for a in acts2 if isinstance(a, BuyCard)
                        and a.reason == 'ev_buy']
            assert state_of(sess2).cw4_counters.get(
                'criteria_contract_violation:buy.ev_buy_candidates', 0) >= 1
        finally:
            provisional.reset('U_X')
            provisional.reset('T_SEARCH_A')

    def test_gap_wave_zero_contract_violations(self):
        """接线正向(K 空窗回退修复批):空窗帧(target_comp=None)
        k_projection 前提放行,零违例计数(契约层零误伤锚)。"""
        from sr_od.application.currency_war.kernel import cw_intention
        from sr_od.application.currency_war.kernel.cw_intention import (
            IntentionState,
        )
        st = _state(gold=30, bench=[_bc('注册表外散件Z', slot=1)])
        sess = _session(None)
        state_of(sess).v3_intention = IntentionState()
        _decide(st, sess)
        assert state_of(sess).cw4_counters.get(
            'criteria_contract_violation:shop.k_projection', 0) == 0
        assert state_of(sess).cw4_counters.get('shop_k_fallback_p1_gap', 0) >= 1
        assert cw_intention.p1_gap_window(st)

    def test_normal_wave_zero_contract_violations(self):
        """零误伤锚:正常决策波(K 成型、金/预留现读)零违例计数。

        前缀全扫覆盖 shop 波全部契约消费位(含 arm1:shop.py 对非抑制
        帧无条件求值 arm1 前提,原 arm1 点名零违例锚的本测子集,已并入
        此处;mandate 域点名锚见 TestMandateArm1Wiring 正向测)。"""
        comp = _comp()
        m = _members(comp)[0]
        st = _state(gold=30, shop=[_card(m, cost=3)])
        sess = _session(comp)
        acts = _decide(st, sess)
        assert any(isinstance(a, BuyCard) for a in acts)
        assert not [k for k in state_of(sess).cw4_counters
                    if k.startswith('criteria_contract_violation')]

    def test_skeleton_wave_zero_contract_violations(self):
        """骨架臂波同样零违例计数(entry 侧 funding 通道契约不误伤)。"""
        from sr_od.application.currency_war.sim.engine_p1 import (
            sim_decision_registry,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import entry
        comp = _comp()
        members = _members(comp)

        class _Obs:
            boxes = ()
            tomes = ()
            spheres = ()
            event_overlay = ''
            bench_chars = ()
            deployed_chars = ()
            deploy_vacancy = 0
            state = _state(gold=5, bench=[_bc(members[0], slot=1)],
                           deployed=[])
            k = None

        class _Turn:
            pass

        sess = _session(comp)
        sess.node_type_current = None
        obs = _Obs()
        out = entry.emit(obs, _Turn(), sess, type('C', (), {'ev_arm':
                                                            'skeleton_only'})(),
                         registry=sim_decision_registry())
        assert isinstance(out, list)
        assert not [k for k in state_of(sess).cw4_counters
                    if k.startswith('criteria_contract_violation')]


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


def _find_criteria_direct_calls(src_root: Path) -> list[str]:
    """AST 扫描:白名单外文件中「绑定到判据模块的函数」调用点。

    解析规则(import 绑定名+调用名联合):
    - ``from <cw4.criteria.buy> import lv9_stop`` / ``... import buy``
      / ``import <...criteria.buy> as b`` → 记录本地名→import 尾径;
    - 调用 ``lv9_stop(...)``(裸名,盲区①)/ ``b.lv9_stop(...)`` /
      ``mod.attr.lv9_stop(...)``(点链)→ 绑定解析命中且函数属主一致
      = 判据直调点。白名单豁免按**全限定文件路径**(堵 basename 逃逸,
      盲区②)。
    """
    offenders: list[str] = []
    cw4_prefix = 'sr_od.application.currency_war.strategies.impl.mandate_v1.'
    for py in sorted(src_root.rglob('*.py')):
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
        """静态守卫(AST 版):src 树内判据函数调用点只允许出现在已接线
        消费位(全限定路径白名单)——防新增消费位绕过 ensure_contract
        直调。AST 解析 import 绑定名+调用名,覆盖裸名直调与模块属性两
        形态(旧正则守卫的盲区①,REWORK_REVIEW_20260903 F1)。"""
        offenders = _find_criteria_direct_calls(self._src_root())
        assert not offenders, \
            f'判据直调点绕过 ensure_contract(白名单外): {offenders}'

    def test_guard_catches_bare_name_direct_call(self, tmp_path):
        """负测试(盲区①=红):from-import 裸名直调 ``lv9_stop(3)`` 在
        旧正则守卫下漏网(正则只捕 ``<alias>.<fn>(`` 形态)——AST 版
        经 import 绑定名解析必须报红。"""
        src = tmp_path / 'src'
        (src / 'decision').mkdir(parents=True)
        (src / 'decision' / 'new_consumer.py').write_text(
            'from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria'
            '.levelup import lv9_stop\n'
            'def f() -> None:\n    lv9_stop(3)\n', encoding='utf-8')
        offenders = _find_criteria_direct_calls(src)
        assert any('裸名直调 lv9_stop' in o for o in offenders), offenders

    def test_guard_catches_basename_whitelist_escape(self, tmp_path):
        """负测试(盲区②=红):白名单外目录下同名 shop.py(旧守卫按
        basename 豁免即逃逸)——全限定路径白名单下模块属性直调必须
        报红。"""
        src = tmp_path / 'src'
        (src / 'somewhere' / 'else').mkdir(parents=True)
        (src / 'somewhere' / 'else' / 'shop.py').write_text(
            'from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria'
            ' import levelup\n'
            'def f() -> None:\n    levelup.lv9_stop(3)\n', encoding='utf-8')
        offenders = _find_criteria_direct_calls(src)
        assert any('somewhere/else/shop.py' in o for o in offenders), \
            offenders

    def test_guard_allows_fully_qualified_whitelisted_path(self, tmp_path):
        """正测试:全限定白名单路径(决策/cw4/shop.py 全径)内的判据调用
        不报(接线消费位豁免按路径精确匹配,basename 逃逸修复的另一
        半边——不同目录同名文件不再共享豁免)。"""
        src = tmp_path / 'src'
        wired = src / 'sr_od/application/currency_war/strategies/impl/mandate_v1'
        wired.mkdir(parents=True)
        (wired / 'shop.py').write_text(
            'from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria'
            ' import levelup\n'
            'def f() -> None:\n    levelup.lv9_stop(3)\n', encoding='utf-8')
        assert _find_criteria_direct_calls(src) == []


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
