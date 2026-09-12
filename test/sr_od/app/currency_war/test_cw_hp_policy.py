"""hp 施门 kernel 政策层读口专项锁(波 2 落地卡 criteria 输入;T-95)。

锁面四族(设计件定稿 §4;T-5 卡注挂账义务兑现):
- **L1 门语义等价锁**:`apply_hp_freshness_gate` 窗口语义全夹具
  (gap∈{0,1,2,3,4}×current_readable×锚缺席组合)+ 幂等断言(门后值再过门
  不变)+ None 穿透断言;
- **L2 决策消费同门锁**:波 2 后 kernel 决策簇全模块(cw_economy /
  cw_discipline_rules 全量)grep `.hp` 字段直读 = 0(仅政策层读口内部);
  挂账申报位(cw_comps.maybe_pivot / cw_performance.is_run_dead)带
  「挂账读点」在码申报;
- **L3 可信位单一源锁**:hp_decision_trusted_of 唯一实现
  (hp_decision_trusted 容器形态委托之)+ 容器消费面 `hp_readable or
  hp_trusted` 手写双位模式 grep=0 + sig.quality['hp'] 词表封闭断言
  (三值全集 real_read/prior/same_node_carried);
- **L4 薄委托零漂移锁**:strategies/impl gated_hp 任意输入委托输出 ==
  kernel 门本体输出(防委托层再长肉);decision_hp 装配序逐分支
  (NodeKey 缺席=恒等支/锚缺席=恒等支/时基同式派生/None 语义)。

**锁生命周期注**:L1/L4 的等价参照 = 门本体语义(原 strategies gated_hp
函数体)——该旧函数体随旧链(统一 state 迁移末段 last_state 链)删除后,
L1/L4 改钉 :func:`decision_hp` 单一形态(改钉时删去 gated_hp 委托腿);
L4 内对策略层既有调用点的行为锁随旧链删除退役。
"""
from __future__ import annotations

import copy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sr_od.application.currency_war.kernel.cw_board_state import (
    BS_SCHEMA_VERSION,
    BoardState,
    ChannelSig,
    NodeKey,
)
from sr_od.application.currency_war.kernel.cw_hp_policy import (
    HP_FRESH_GAP_TRUSTED,
    HP_FRESH_GAP_UNTRUSTED_MAX,
    apply_hp_freshness_gate,
    decision_hp,
    hp_decision_trusted_of,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    StrategySession,
    gated_hp,
)

_KERNEL_BASE = (Path(__file__).parents[5] / 'src' / 'sr_od' / 'application'
                / 'currency_war' / 'kernel')


def _sig() -> ChannelSig:
    """测试写入签名(本测试只辖 hp 读口,渠道面字段的合法性由写入口校验)。"""
    return ChannelSig(family='obs', actor='cw_observation', mode='read')


def _mk_bs(hp: int | None = None, *, source: str = 'observation',
           plane: int | None = 1, round_num: int | None = 1) -> BoardState:
    """hp 决策帧构造器:值写入按来源三态;node 写入按需(NodeKey 缺席分支
    传 plane=None)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    if hp is not None:
        if source == 'observation':
            bs.observe(bs.hp, hp, sig=_sig())
        elif source == 'carried':
            bs.observe(bs.hp, hp, sig=_sig())
            bs.carry(bs.hp, frame='p1-r3', sig=_sig())
        elif source == 'prior':
            bs.write_prior(bs.hp, hp, evidence='prior:adr-0559', sig=_sig())
        else:
            raise ValueError(f'未知 source {source!r}')
    if plane is not None and round_num is not None:
        bs.observe(bs.node, NodeKey(plane=plane, round_num=round_num,
                                    kind='prep'), sig=_sig())
    return bs


def _sess(last_hp: int | None, last_t: int | None) -> Any:
    sess = StrategySession()
    sess.last_hp = last_hp
    sess.last_hp_t = last_t
    return sess


# ============================================================ L1 门语义等价锁

class TestL1GateSemanticsEquivalence:
    """窗口政策全夹具(锚全时 gap 域×readable)+ 锚缺席组合 + 幂等 + None。"""

    def test_window_grid_matches_gated_semantics(self) -> None:
        """gap∈{0,1,2,3,4}×readable 全组合:可信窗仅 gap==1;放宽窗仅
        (unreadable ∧ 1<gap≤3);窗外恒现读。期望值直接按语义表钉死
        (L1 等价参照 = 门本体语义表,与旧 gated_hp 函数体逐位一致)。"""
        for gap in (0, 1, 2, 3, 4):
            now_t, last_t = 10, 10 - gap
            for readable in (True, False):
                expect = (40 if (gap == HP_FRESH_GAP_TRUSTED
                                 or (not readable and
                                     HP_FRESH_GAP_TRUSTED < gap
                                     <= HP_FRESH_GAP_UNTRUSTED_MAX))
                          else 75)
                got = apply_hp_freshness_gate(75, 40, last_t, now_t, readable)
                assert got == expect, \
                    f'gap={gap} readable={readable}: 期望 {expect},实得 {got}'

    def test_anchor_missing_identity_branch(self) -> None:
        """锚缺任一(last_hp/last_t/now_t)→ 恒等返回 current_hp(逐支)。"""
        assert apply_hp_freshness_gate(75, None, 3, 10, True) == 75
        assert apply_hp_freshness_gate(75, 40, None, 10, True) == 75
        assert apply_hp_freshness_gate(75, 40, 3, None, True) == 75
        assert apply_hp_freshness_gate(None, 40, 3, None, False) is None

    def test_none_current_covered_in_window_not_identity_exempt(self) -> None:
        """None 现读非恒等豁免:锚全时在窗内同样被结算值覆盖(门只决定
        「是否被结算值覆盖」,不产兜底值);窗外 None 穿透。"""
        assert apply_hp_freshness_gate(None, 40, 9, 10, True) == 40   # gap==1
        assert apply_hp_freshness_gate(None, 40, 9, 11, False) == 40  # 放宽窗
        assert apply_hp_freshness_gate(None, 40, 3, 10, True) is None  # gap7 窗外

    def test_gate_idempotent(self) -> None:
        """幂等:门后值再过门不变(读口叠加施门不判分叉的前提)。"""
        for gap in (0, 1, 2, 3, 4):
            for readable in (True, False):
                now_t, last_t = 10, 10 - gap
                once = apply_hp_freshness_gate(75, 40, last_t, now_t, readable)
                twice = apply_hp_freshness_gate(once, 40, last_t, now_t,
                                                readable)
                assert once == twice, \
                    f'gap={gap} readable={readable}: 门不幂等({once}→{twice})'


# ============================================================ L4 薄委托零漂移

class TestL4ThinDelegationZeroDrift:
    """strategies gated_hp 薄委托 == kernel 门本体(防委托层再长肉)。"""

    def test_delegation_equals_kernel_gate_on_grid(self) -> None:
        """任意输入委托输出逐位一致(gap 网格×锚缺席×None 现读全夹具)。"""
        cases = [(75, 40, 10 - gap, 10, readable)
                 for gap in (0, 1, 2, 3, 4) for readable in (True, False)]
        cases += [(75, None, 3, 10, True), (75, 40, None, 10, False),
                  (None, 40, 9, 10, True), (None, 40, 3, 10, False)]
        for cur, last_hp, last_t, now_t, readable in cases:
            sess = _sess(last_hp, last_t)
            assert gated_hp(cur, sess, now_t,
                            current_readable=readable) == \
                apply_hp_freshness_gate(cur, last_hp, last_t, now_t, readable), \
                f'薄委托漂移: cur={cur} last=({last_hp},{last_t}) t={now_t} ' \
                f'readable={readable}'

    def test_constants_extracted_verbatim(self) -> None:
        """窗口政策两常量值 = 旧 gated_hp 现行字面(可信窗 1/放宽窗上界 3;
        数值零迁移申报)。"""
        assert HP_FRESH_GAP_TRUSTED == 1
        assert HP_FRESH_GAP_UNTRUSTED_MAX == 3


# ============================================================ decision_hp 装配序

class TestDecisionHpAssembly:
    """决策读口装配逐分支(NodeKey 缺席/锚缺席/时基同式/来源位/readable)。"""

    def test_node_key_absent_identity_branch(self) -> None:
        """NodeKey 缺席 → now_t=None → 恒等支(设计契约:与现役 adapter
        形态在锚在场时 gap≤0 判负同回 current_hp,行为等价)。"""
        bs = _mk_bs(75, source='observation', plane=None, round_num=None)
        assert decision_hp(bs, _sess(40, 9)) == 75
        assert decision_hp(bs, _sess(None, None)) == 75

    def test_anchor_absent_identity_branch(self) -> None:
        """session 结算锚缺席(鸭子读 None)→ 恒等支(sim 无结算锚同构)。"""
        bs = _mk_bs(75, source='observation', plane=2, round_num=2)
        assert decision_hp(bs, StrategySession()) == 75
        assert decision_hp(bs, SimpleNamespace()) == 75

    def test_timebase_derivation_and_windows(self) -> None:
        """时基 = (plane-1)*9+round(与结算锚写点同式,禁单侧改式):锚 t 按
        同式回推 gap 精确落窗;窗内覆盖/窗外保持按 L1 语义表。"""
        # p2r2 → t=11;锚 t=10 → gap=1 可信窗覆盖
        bs = _mk_bs(75, source='observation', plane=2, round_num=2)
        assert decision_hp(bs, _sess(40, 10)) == 40
        # 锚 t=8 → gap=3:真读帧窗外保持
        assert decision_hp(bs, _sess(40, 8)) == 75
        # 沿用帧(source=carried)→ readable False → 放宽窗 gap∈2..3 覆盖
        bs_carry = _mk_bs(75, source='carried', plane=2, round_num=2)
        assert decision_hp(bs_carry, _sess(40, 9)) == 40    # gap=2 放宽窗
        assert decision_hp(bs_carry, _sess(40, 8)) == 40    # gap=3 放宽窗
        assert decision_hp(bs_carry, _sess(40, 7)) == 75    # gap=4 窗外

    def test_none_truth_passthrough_fail_closed(self) -> None:
        """bs.hp 未写(值 None)穿门:无锚 → None 恒等;锚全在窗内 → 结算
        值覆盖(ADR-0495 消费侧保守兜底)。"""
        bs = _mk_bs(None, plane=1, round_num=4)
        assert decision_hp(bs, _sess(None, None)) is None
        assert decision_hp(bs, _sess(40, 3)) == 40   # p1r4 t=4,gap=1 可信窗


# ============================================================ L2 决策消费同门锁

_L2_DIRECT_READ_FILES = ('cw_economy.py', 'cw_discipline_rules.py')
_L2_LEDGER_SITES = (('cw_comps.py', 'maybe_pivot', '挂账读点'),
                    ('cw_performance.py', 'is_run_dead', '挂账读点'))


def _attr_hits(rel: str, attrs: tuple[str, ...]) -> list[str]:
    """AST 级属性访问扫描(注释/docstring 字样不计——判据辖代码面)。
    返回命中行号列表。"""
    import ast
    tree = ast.parse((_KERNEL_BASE / rel).read_text(encoding='utf-8'))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in attrs:
            hits.append(f'L{node.lineno}')
    return hits


def _container_fn_hp_hits(rel: str) -> list[str]:
    """AST 级扫描:容器签名函数(首参名 bs,BoardState 形态约定)函数体内
    零 `.hp` 属性访问(注释/docstring 不计;GameState 形态旧函数的 state.hp
    读不属容器决策分支,随各自波次/退役批消亡,不在本锁辖域)。
    返回 [函数名, 行号, ...] 命中清单。"""
    import ast
    tree = ast.parse((_KERNEL_BASE / rel).read_text(encoding='utf-8'))
    hits: list[str] = []

    def _scan_fn_body(fn: ast.FunctionDef) -> None:
        for node in ast.walk(fn):
            if node is fn or isinstance(node, (ast.FunctionDef,
                                               ast.AsyncFunctionDef)):
                continue
            if isinstance(node, ast.Attribute) and node.attr == 'hp':
                hits.append(f'{fn.name}() L{node.lineno}')

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.args.args \
                and node.args.args[0].arg == 'bs':
            _scan_fn_body(node)
    return hits


class TestL2DecisionConsumptionSameGate:
    """波 2 后 kernel 决策簇 hp 直读零旁路(设计件 §4-L2)。"""

    def test_kernel_decision_cluster_zero_direct_hp_read(self) -> None:
        """cw_economy / cw_discipline_rules 全量:容器签名决策函数零 `.hp`
        直读(hp 决策消费仅经政策层读口 cw_hp_policy;AST 级扫描,注释/
        docstring 字样不判);GameState 形态旧函数(state.hp 读)不属容器
        决策分支,不在本锁辖域。"""
        for rel in _L2_DIRECT_READ_FILES:
            hits = _container_fn_hp_hits(rel)
            assert hits == [], f'{rel}: 容器决策函数残留 hp 直读 {hits}'
            src = (_KERNEL_BASE / rel).read_text(encoding='utf-8')
            assert 'cw_hp_policy' in src, \
                f'{rel}: 未接政策层读口(单一源缺席)'

    def test_ledger_sites_declared_in_code(self) -> None:
        """挂账申报位(maybe_pivot/is_run_dead)带「挂账读点」在码申报
        (重挂生产消费必经政策层读口的在码自申报,防按旧注释直读)。"""
        for rel, func, marker in _L2_LEDGER_SITES:
            src = (_KERNEL_BASE / rel).read_text(encoding='utf-8')
            assert marker in src, f'{rel}: 缺挂账申报标记'
            assert 'decision_hp' in src and 'hp_decision_trusted_of' in src, \
                f'{rel}: 挂账申报缺政策层读口指路'
            start = src.index(f'def {func}(')
            end = src.find('\ndef ', start + 1)
            body = src[start:end if end > 0 else len(src)]
            assert marker in body and 'decision_hp' in body, \
                f'{rel}.{func}: 挂账申报不在函数体内'


# ============================================================ L3 可信位单一源锁

class TestL3TrustedBitSingleSource:
    """可信位单一实现 + 手写双位 grep=0 + quality 词表封闭。"""

    def test_container_mapping_truth_table(self) -> None:
        """定谳二映射:observation/carried → True;prior → False(fail-closed)。"""
        assert hp_decision_trusted_of(
            _mk_bs(80, source='observation')) is True
        assert hp_decision_trusted_of(_mk_bs(80, source='carried')) is True
        assert hp_decision_trusted_of(_mk_bs(80, source='prior')) is False

    def test_discipline_helper_delegates_single_implementation(self) -> None:
        """hp_decision_trusted(容器形态)= 委托 hp_decision_trusted_of
        (同对象级单一源,非第二实现)。"""
        from sr_od.application.currency_war.kernel import (
            cw_discipline_rules,
            cw_hp_policy,
        )
        assert cw_discipline_rules.hp_decision_trusted_of \
            is cw_hp_policy.hp_decision_trusted_of
        bs = _mk_bs(80, source='prior')
        assert cw_discipline_rules.hp_decision_trusted(bs) == \
            cw_hp_policy.hp_decision_trusted_of(bs) is False

    def test_no_handwritten_dual_bit_pattern(self) -> None:
        """kernel 决策簇全量手写双位模式 grep=0(W393 A1.1 单一源纪律):
        cw_economy/cw_discipline_rules 代码面(AST 级)零 `hp_readable` /
        `hp_trusted` 属性访问——可信位判定只经政策层读口;GameState 侧
        旧实现已随容器切换消亡。"""
        for rel in _L2_DIRECT_READ_FILES:
            hits = _attr_hits(rel, ('hp_readable', 'hp_trusted'))
            assert hits == [], f'{rel}: 手写双位模式复潮(行号 {hits})'

    def test_discipline_dispatch_dual_form_no_int_leak(self) -> None:
        """三审阻断回归锁:GameState/裸 int-hp 帧穿 hp_decision_trusted
        不得漏入 hp_decision_trusted_of 的 bs.hp.source 直读(三审实测
        AttributeError 'int' object has no attribute 'source')。

        分派语义(双形态过渡,GameState 支随 W8 消亡):
        - 容器帧(hp 为 Field 载体)→ hp_decision_trusted_of 单一源;
        - GameState/桩帧(hp 为标量)→ 旧双位读法 hp_readable or hp_trusted,
          值语义与切换前逐位一致(真读/沿用放行,双 False 拒)。
        读口本体 hp_decision_trusted_of 保持严格容器形态零防御——裸帧
        直穿它必须炸错暴露调用点,禁静默缺省(血线决策漂移最危险域)。"""
        import pytest as _pytest

        from sr_od.application.currency_war.kernel.cw_discipline_rules import (
            hp_decision_trusted,
        )
        from sr_od.application.currency_war.kernel.cw_state import GameState
        # GameState 真读帧 → 旧双位语义(与切换前逐位一致)
        st_real = GameState(hp=80)
        st_real.hp_readable = True
        assert hp_decision_trusted(st_real) is True
        # GameState 双 False 帧 → 拒(fail-closed 语义零回归)
        st_ghost = GameState(hp=100)
        st_ghost.hp_readable = False
        st_ghost.hp_trusted = False
        assert hp_decision_trusted(st_ghost) is False
        # 桩帧(裸 int hp + 显式位)→ 旧双位,不漏容器支
        stub = SimpleNamespace(hp=100, hp_readable=False, hp_trusted=False)
        assert hp_decision_trusted(stub) is False
        stub_ok = SimpleNamespace(hp=10, hp_readable=False, hp_trusted=True)
        assert hp_decision_trusted(stub_ok) is True
        # 读口本体保持严格:裸 int-hp 帧直穿 hp_decision_trusted_of 必炸
        # (AttributeError=调用点未桥接的显式暴露,禁静默防御)
        with _pytest.raises(AttributeError):
            hp_decision_trusted_of(stub)

    def test_hp_quality_vocabulary_closed(self) -> None:
        """sig.quality['hp'] 词表封闭断言(三值全集
        real_read/prior/same_node_carried;新写端扩词表须随批登记申报)。
        判据 = src 内 quality={'hp': ...} 字面全集 ⊆ 封闭集。"""
        import re
        allowed = {'real_read', 'prior', 'same_node_carried'}
        src_root = _KERNEL_BASE.parents[0]
        found: set[str] = set()
        for py in src_root.rglob('*.py'):
            for m in re.finditer(r"quality=\{'hp':\s*'([a-z_]+)'\}",
                                 py.read_text(encoding='utf-8')):
                found.add(m.group(1))
        assert found, 'hp quality 写端零命中 = 锁面失效(写端搬家须随批改锁)'
        assert found <= allowed, \
            f'词表集外值 {found - allowed}(扩词表须随批登记申报改本锁)'


# ============================================================ 挂账读点零行为

def _tracker_with_trend(loss: float) -> Any:
    """trend 注入:两条高置信结算行(普通战斗,EXPECTED_DROP=1.0)成对差分
    trend = loss/1.0。"""
    from sr_od.application.currency_war.kernel.cw_performance import (
        PerformanceTracker,
        RoundOutcome,
    )
    tracker = PerformanceTracker()
    tracker.record(RoundOutcome(round_num=1, plane=1, node_type='普通战斗',
                                comp_tag='T', hp_after=100,
                                hp_confidence=1.0))
    tracker.record(RoundOutcome(round_num=2, plane=1, node_type='普通战斗',
                                comp_tag='T', hp_after=100 - int(loss),
                                hp_confidence=1.0))
    return tracker


class TestLedgerHpReadPointsZeroBehavior:
    """挂账读点(maybe_pivot 保命分位 / is_run_dead 死局门)hp 直读形态
    行为锁(本波零改动面;重挂生产消费时本组随读口切换重钉)。"""

    def test_is_run_dead_none_hp_never_dead(self) -> None:
        """bs.hp 未写(值 None)→ 恒 False(trend 高也不误判死;None 保守)。"""
        from sr_od.application.currency_war.kernel.cw_performance import (
            is_run_dead,
        )
        bs = _mk_bs(None, plane=2, round_num=3)
        tracker = _tracker_with_trend(50.0)
        assert is_run_dead(bs, tracker, 'boss') is False

    def test_is_run_dead_low_hp_high_trend_locked_node(self) -> None:
        """三门全中(hp<20 ∧ trend 高 ∧ 锁不住血节点)→ True;普通关节点
        → False;trend 冷启动(None)→ False。"""
        from sr_od.application.currency_war.kernel.cw_performance import (
            DEAD_HP,
            TREND_THRESHOLD,
            PerformanceTracker,
            is_run_dead,
        )
        bs = _mk_bs(DEAD_HP - 1, plane=2, round_num=3)
        hot = _tracker_with_trend(50.0)
        assert hot.recent_hp_loss_trend(window=3) > TREND_THRESHOLD
        assert is_run_dead(bs, hot, 'boss') is True
        assert is_run_dead(bs, hot, 'battle') is False
        assert is_run_dead(bs, PerformanceTracker(), 'boss') is False

    def test_maybe_pivot_threshold_reads_container_frame(self) -> None:
        """保命分位阈值经容器帧直算(_HpShim 已消亡):构造 P2r1 lv7 帧,
        阈值 = int(0.75 × effective_hp_threshold(bs)) 逐位一致
        (等价参照 = 阈值函数单帧锁 test_cw_two_state_unification)。"""
        from sr_od.application.currency_war.kernel.cw_state import (
            effective_hp_threshold,
        )
        bs = _mk_bs(30, source='observation', plane=2, round_num=1)
        bs.observe(bs.level, 7, sig=_sig())
        expected = int(0.75 * effective_hp_threshold(bs))
        assert expected == 55   # base 40 ×1.85≈74 → int(0.75×74)=55
        # hp 低于阈值=保命分支触发前提;门后值 None 保守(无锚恒等)
        assert bs.hp.value < expected
        assert decision_hp(copy.deepcopy(bs), SimpleNamespace()) == 30
