"""session 职责分离批锁(ADR-0563;kernel 访问口/工厂钩子/桩面存储)。

锁面:
- T-76:ExecState 桩面存储挂 session 对象自身属性(生命周期随对象)——
  id() 旁表只作不可弱引用且属性不可写对象(__slots__ 族)的最后兜底,
  兜底条目进程内驻留、随测试会话(进程)结束消亡;桩 GC 后 id 复用串号
  通道在主路径消除,兜底分支收窄非消除(ADR-0563 决策-3 收敛口径,
  声明+残留风险如实)。
- 策略状态工厂注入槽(_STATE_FACTORY 模块级全局,测试纪律第 4 条:
  setup 一并 monkeypatch 桩化防跨测试串染):未注册 → None 不代建 /
  注册 → 惰性冷建写回、幂等复用与覆盖语义。
- B4 None 契约两形态(单一源 = strategy_state_of docstring):判据/
  披露面防御 getattr 退缺省不炸;行为面解引用 AttributeError 显式炸错。
- ADR-0563 决策-2:mandate_v1 create_state 覆写在位,create_session
  接线产出当局 MandateState(manager/sim/replay/直调全路径同源);工厂
  契约 = 容忍 config=None(sim 注入桩面);工厂不携带 live 初值
  (v3_phase='FORM' 由 create_session 唯一冷建口写入,ADR-0583;
  sim 直构 session 读数保真 '')。
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace


def _es_mod():
    from sr_od.application.currency_war.kernel import cw_exec_state
    return cw_exec_state


def _strategy_cls():
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        StrategySession,
    )
    return StrategySession


# ===== T-76:ExecState 桩面存储(挂对象属性,id 旁表只作最后兜底)=====

def test_stub_exec_state_stored_on_object() -> None:
    """不可弱引用桩(SimpleNamespace 族)的 ExecState 挂对象自身属性:
    同实例回读、id() 键旁表不承载属性可写桩(T-25 串号通道关闭的机制锁)。"""
    es_mod = _es_mod()
    stub = SimpleNamespace()
    ex = es_mod.exec_state_of(stub)
    assert isinstance(ex, es_mod.ExecState)
    assert getattr(stub, es_mod._EXEC_STATE_ATTR, None) is ex, (
        '桩面 ExecState 必须挂在 session 对象自身(生命周期随对象)')
    assert es_mod.exec_state_of(stub) is ex   # 同实例回读
    assert es_mod._EXEC_BY_SESSION_ID == {}, (
        '属性可写桩不得落 id() 键旁表(条目永不清理 = T-25 假红根因)')


def test_stub_states_isolated_and_bind_override() -> None:
    """桩间状态按对象隔离(id 复用也不串号);bind_exec_state 幂等覆写走
    同一桩面(局首绑定单一调用点的桩面路径)。"""
    es_mod = _es_mod()
    a, b = SimpleNamespace(), SimpleNamespace()
    ea = es_mod.exec_state_of(a)
    eb = es_mod.exec_state_of(b)
    assert ea is not eb, '不同桩对象必须各得独立载体'
    ea.megastar_candidate_clicked = True
    assert eb.megastar_candidate_clicked is False, (
        '对象属性寻址下 id 复用不可能串号(旧 id 旁表形态的假红面)')
    fresh = es_mod.ExecState()
    assert es_mod.bind_exec_state(a, fresh) is fresh
    assert es_mod.exec_state_of(a) is fresh, '显式绑定后访问口须解析到绑定实例'
    assert es_mod._EXEC_BY_SESSION_ID == {}


def test_real_session_uses_weak_table_not_attr() -> None:
    """真 StrategySession(可弱引用)走弱引用旁表,不污染对象属性面。"""
    es_mod = _es_mod()
    sess = _strategy_cls()()
    ex = es_mod.exec_state_of(sess)
    assert es_mod.exec_state_of(sess) is ex
    assert getattr(sess, es_mod._EXEC_STATE_ATTR, None) is None, (
        '可弱引用对象不得走桩面属性路径(单一机制,防双源)')


def test_none_session_returns_throwaway_no_cache() -> None:
    """session=None → 一次性空载体(不缓存不共享)。

    None 的 id() 恒定,按 id 缓存 = 全局共享哑载体(跨调用写入串染 +
    id 旁表永久驻留,全量套件顺序下的机制锁污染源实证);正常调用方
    上游守卫,无 match 注册的 best-effort 观测行(snapshot_expected_paths)
    走本分支不落任何旁表条目。"""
    es_mod = _es_mod()
    a = es_mod.exec_state_of(None)
    b = es_mod.exec_state_of(None)
    assert isinstance(a, es_mod.ExecState) and isinstance(b, es_mod.ExecState)
    assert a is not b, 'None 调用间不得共享载体(旧 id(None) 缓存形态 = 串染源)'
    a.expected_state = {'k': object()}
    assert b.expected_state is None, '一次性载体的写入不得跨调用可见'


# ===== ADR-0563 决策-2:工厂钩子落位 =====

def test_mandate_v1_create_state_override() -> None:
    """mandate_v1 覆写 create_state 返回 MandateState(决策-2 申报面):
    工厂容忍 config=None(sim 注入桩面),且不携带 live 初值
    (v3_phase FORM 由 create_session 唯一冷建口写入,ADR-0583;
    sim 直调工厂产物恒 '' 保 sim 旧读数)。"""
    from sr_od.application.currency_war.strategies.impl.flow import CwFlowStrategy
    from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
        MandateV1Strategy,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
        MandateState,
    )
    ms = MandateV1Strategy().create_state(None)
    assert isinstance(ms, MandateState)
    assert ms.v3_phase == '', '工厂产物不得携带 live 初值 FORM(归冷建口)'
    # 覆写落点 = CwFlowStrategy(流程核;本类留 abstract,经类直调验实现)
    assert isinstance(
        CwFlowStrategy.create_state(SimpleNamespace(), None), MandateState)


def test_create_session_sole_cold_build_entry_l4() -> None:
    """L4 冷建唯一口锁(出处 = ADR-0583 §2.3/§1.3 双冷建重叠消除):
    create_session 后 strategy_state 为 MandateState 且 v3_phase='FORM'
    (live 初值随唯一冷建口落位);二次 create_session 全量重建(新对象、
    新状态,工厂恰走一次);生命周期钩子 on_match_start/on_match_end 已删
    (残留调用点 = 墓碑锁辖,test_cw_w971_blackboard L6 空间守卫)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
        MandateV1Strategy,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
        MandateState,
    )
    strat = MandateV1Strategy()
    sess1 = strat.create_session(None)
    assert isinstance(sess1.strategy_state, MandateState)
    assert sess1.strategy_state.v3_phase == 'FORM', (
        'live 相位初值必须随唯一冷建口(旧 on_match_start 写点语义收编)')
    calls: list[object] = []
    real_create_state = strat.create_state

    def _counting(config):
        calls.append(object())
        return real_create_state(config)

    strat.create_state = _counting   # 局部实例计数,不入 session
    sess2 = strat.create_session(None)
    assert sess2 is not sess1
    assert sess2.strategy_state is not sess1.strategy_state, (
        '二次 create_session = 全量重建(不复用上局引用)')
    assert sess2.strategy_state.v3_phase == 'FORM'
    assert len(calls) == 1, '每局状态冷建恰经工厂一次(双冷建重叠消除)'


def test_base_create_state_default_none() -> None:
    """基类非 abstract 缺省 None(B4 收缩口径:缺省不炸构造与
    create_session;经类直接调基类实现,免实现 12 个 abstract 钩子)。"""
    from sr_od.application.currency_war.strategies.impl.cw_strategy import CwStrategy
    assert CwStrategy.create_state(SimpleNamespace(), None) is None


def test_create_session_wires_state() -> None:
    """create_session 接线(session.md §5.1):产出 session 即带当局
    MandateState(manager/sim/replay/直调全创建路径同源)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
        MandateV1Strategy,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
        MandateState,
    )
    sess = MandateV1Strategy().create_session(None)
    assert isinstance(sess.strategy_state, MandateState)


# ===== 策略状态工厂注入槽(_STATE_FACTORY 模块级全局;测试纪律第 4 条)=====

def test_factory_slot_unregistered_returns_none_no_writeback(monkeypatch) -> None:
    """工厂未注册 → 读路径 None、不代建不写回(第三方策略面保守跳过)。

    出处 = ADR-0563 决策-4(kernel 写路径经 strategy_state_lazy 惰性兜底,
    工厂未注册 = 保守跳过)+ ``ensure_strategy_state_attached`` docstring。
    _STATE_FACTORY 是 mandate_v1 包导入即全局安装的模块级全局(同会话
    其他测试 import 后恒为 MandateState 工厂),按测试纪律第 4 条 setup
    必须 monkeypatch 桩化(自动还原,防跨测试串染)。本测试同时直锁
    mandate_v1 装配副作用契约(出处 = mandate_v1/__init__ docstring
    「装配副作用(本包被导入即生效)」+ ADR-0563 决策-4 注册点声明):
    包导入即全局安装,_STATE_FACTORY is MandateState(先于桩化断言,
    自带导入保证与测试顺序无关)。"""
    from sr_od.application.currency_war.kernel import cw_strategy_session as ss_mod
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        MandateState,
    )
    assert ss_mod._STATE_FACTORY is MandateState, (
        'mandate_v1 包导入即全局安装工厂(装配副作用直锁)')
    monkeypatch.setattr(ss_mod, '_STATE_FACTORY', None)
    sess = _strategy_cls()()
    assert ss_mod.ensure_strategy_state_attached(sess) is None
    assert ss_mod.strategy_state_lazy(sess) is None
    assert sess.strategy_state is None, '未注册工厂不得代建写回(第三方面保守跳过)'


def test_factory_slot_lazy_build_writes_back_once(monkeypatch) -> None:
    """工厂注册 → 惰性冷建并写回 session;同 session 再取复用已写回实例
    (工厂只调一次)。出处 = ``install_strategy_state_factory`` 幂等覆盖
    契约 + ``ensure_strategy_state_attached`` 读+惰性附着语义。"""
    from sr_od.application.currency_war.kernel import cw_strategy_session as ss_mod
    calls: list[object] = []

    def _factory() -> object:
        calls.append(object())
        return calls[-1]

    monkeypatch.setattr(ss_mod, '_STATE_FACTORY', _factory)
    sess = _strategy_cls()()
    st = ss_mod.ensure_strategy_state_attached(sess)
    assert st is not None and sess.strategy_state is st
    assert ss_mod.ensure_strategy_state_attached(sess) is st, (
        '已写回后不得重复冷建(工厂只调一次)')
    assert len(calls) == 1
    # install 幂等覆盖:注册新工厂即替换旧槽(mandate_v1 装配点同语义;
    # monkeypatch 已持旧值,测试后还原,全局污染不外溢)
    second: list[object] = []

    def _factory2() -> object:
        second.append(object())
        return second[-1]

    ss_mod.install_strategy_state_factory(_factory2)
    sess2 = _strategy_cls()()
    assert ss_mod.ensure_strategy_state_attached(sess2) is second[-1]
    assert sess2.strategy_state is second[-1]
    assert ss_mod.ensure_strategy_state_attached(sess) is st, (
        '已写回实例的 session 不受工厂替换影响(引用已在其上,不回溯重建)')


# ===== B4 None 契约两形态(单一源 = strategy_state_of docstring)=====

def test_none_state_criterion_faces_return_defaults() -> None:
    """判据/披露面:策略器状态 None(未装配)时 kernel 判据函数不炸、
    退缺省/保守值(B4 契约形态一:防御 getattr,与迁移前动态属性缺席
    行为一致)。

    出处 = ADR-0563「B4 第三方兼容承诺收缩」+ strategy_state_of docstring
    两形态划分。判据函数取两条真实 kernel 读点:
    - cap_resolved_of_session(商店线 g* 装配的 cap 现读)→ 回
      DEFAULT_INTEREST_CAP(期望值从同一模块常量现算,非手抄);
    - committed_authority(定型判定权威派生)→ 保守侧 False
      (ist 不可得禁缺省 True,其 docstring 明文,True = 激进侧)。"""
    from sr_od.application.currency_war.kernel.cw_economy import (
        DEFAULT_INTEREST_CAP,
        cap_resolved_of_session,
    )
    from sr_od.application.currency_war.kernel.cw_intention import (
        committed_authority,
    )
    bare = _strategy_cls()()   # strategy_state 缺省 None = 未装配态
    assert cap_resolved_of_session(bare) == DEFAULT_INTEREST_CAP
    assert cap_resolved_of_session(None) == DEFAULT_INTEREST_CAP, (
        '判据面对 None session 同样退缺省')
    assert committed_authority(None, bare) is False, (
        'ist 不可得必须落保守侧 False(True = 激进侧,判据 docstring 明文禁)')


def test_none_state_behavior_face_dereference_raises() -> None:
    """行为面读点:未装配 session(strategy_state=None)直接解引用 =
    AttributeError 显式炸错(mis-assembly 信号,不静默产 None 假数据;
    B4 契约形态二)。访问函数本身对 None/未装配态不炸、恒返回 None
    ——契约的炸点在解引用,不在访问口(两形态划分的机制锚)。"""
    import pytest

    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        strategy_state_of,
    )
    bare = _strategy_cls()()
    assert strategy_state_of(bare) is None, '未装配 session 经访问口读出 None'
    assert strategy_state_of(None) is None, (
        'None session 经访问口读出 None(不代建,炸点留给解引用)')
    with pytest.raises(AttributeError):
        _ = strategy_state_of(bare).target_comp   # 行为面形态:直接解引用


# ===== 策略字段 session 形态访问墓碑(跨行扫描;ADR-0563 决策-4)=====

# 策略器字段族(v3_/v2_/cw4_ 前缀)已整体迁出 session(ADR-0563:策略器
# 52 项迁 MandateState、执行侧迁 ExecState;StrategySession 现存字段无此
# 前缀)。session 形态的 getattr/setattr 残留 = 读恒缺省假数据(账本差分
# 恒 0 / 遥测 extra 失真,不炸不挡跑),唯一防线是本扫描。
# 扫描边界(如实申报):变量名限定 sess/_sess/session 及其属性链形态
# (调用形态 self._session() 与非此前缀的退役字段不在辖内——后者全集
# 归 session.md §6.2-3 完成判据的流程 grep,不进本锁)。
_RESIDUE_PAT = re.compile(
    r"(?:get|set)attr\(\s*(?:[\w.]+\.)?_?sess(?:ion)?\s*,\s*['\"]"
    r"(?:v3_|v2_|cw4_)\w+['\"]")
# 变异自检样本:含 C1 批四读口的实漏形态——`getattr(` 后换行的跨行形状
# (单行 grep 系统性抓不到,session.md §6.2-3 判据被违反的根因)。
_RESIDUE_SAMPLES = (
    "getattr(sess, 'v3_formed_stop', False)",
    "getattr(\n    sess, 'v3_blood_budget_refresh_rejects', 0)",
    "bool(getattr(\n                    _sess, 'v3_formed_stop', False))",
    "1 if getattr(\n    sess, 'v3_remedy_abandoned', 0) > 0 else 0",
    "setattr(session, 'cw4_counters', {})",
    "getattr(match.session, 'v3_intention', None)",
)
_RESIDUE_NEGATIVE_SAMPLES = (
    # 合法读口:经访问函数(与残留形态区分的机制面)
    "getattr(strategy_state_of(sess), 'v3_formed_stop', False)",
    "getattr(exec_state_of(session), 'defer_count', 0)",
    # session 合法观察字段(未退役,不在墓碑域)
    "getattr(sess, 'last_state', None)",
    "getattr(_sess, 'node_type_current', '')",
)


def test_strategy_fields_no_session_form_access_residue() -> None:
    """策略字段(v3_/v2_/cw4_ 族)session 形态读写点全子树 = 0(墓碑锁,
    否定式 + ADR-0563 退役背书)。四处 C1 读口(blood_budget_refresh_
    rejects/handoff_hp_proj/remedy_abandoned/formed_stop)任一回退即红。

    出处 = ADR-0563 决策-4(消费点全换访问函数)+ session.md §6.2-3
    「session 形态访问归零」完成判据;扫描正则用空白类跨行匹配(\\s*
    匹配换行)——C1 批
    四处残留全是 `getattr(` 后换行的跨行形态,单行 grep 系统性漏网,
    本锁即该判据的常驻操作化。变异自检 = 实漏形状样本必须全部命中、
    合法读口与观察字段必须全部不命中(防正则失效假绿)。"""
    cw_root = (Path(__file__).resolve().parents[5] / 'src' / 'sr_od'
               / 'application' / 'currency_war')
    # 盲区自检:扫描根解析失准则 rglob 恒空 = 假绿(判例 test_cw4_contracts
    # 「parents[N] 解析到不存在路径,守卫形同虚设」),先证根在且非空。
    assert (cw_root / 'kernel' / 'cw_exec_state.py').is_file(), (
        f'扫描根解析失准:{cw_root}')
    scanned = list(cw_root.rglob('*.py'))
    assert len(scanned) >= 50, f'扫描文件数异常({len(scanned)}),根可能错位'
    # 变异自检:正则对已知坏形必须命中、合法形必须不命中。
    for sample in _RESIDUE_SAMPLES:
        assert _RESIDUE_PAT.search(sample), f'变异自检未命中:{sample!r}'
    for sample in _RESIDUE_NEGATIVE_SAMPLES:
        assert not _RESIDUE_PAT.search(sample), (
            f'负样本误命中(正则过宽):{sample!r}')
    offenders: dict[str, str] = {}
    for path in scanned:
        text = path.read_text(encoding='utf-8')
        for m in _RESIDUE_PAT.finditer(text):
            line_no = text.count('\n', 0, m.start()) + 1
            offenders[f'{path.relative_to(cw_root)}:{line_no}'] = m.group(0)
    assert not offenders, (
        '策略字段 session 形态访问残留(读=恒缺省假数据,应换 '
        f'strategy_state_of/exec_state_of 读口):{offenders}')
