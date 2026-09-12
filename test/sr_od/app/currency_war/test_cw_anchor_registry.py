"""流程转点观测锚·登记机制锁(统一观察架构 §12,实现批 T-221)。

被测机制 = ``kernel/cw_anchor.py``(ANCHOR_REGISTRY 封闭集 + 锚行七字段封装
AnchorEvent + 载体接线 emit_anchor + 观测-only 守卫)。设计正本 =
``docs/develop/sr_od/application/currency_war/design/统一观察架构-画面op基类设计.md`` §12
(锚点事件集总表 §12.2 / 数据面 schema §12.3 / 测试锁五条 §12.4-B /
对抗审发现 6/7 的锁④拆分与 effect_ref 结构锁,折入设计正本 §12.4-B 锁编号对照)。

本批辖域申报:

- 只登记 §12.2 以「实机先行」标记的 8 锚(buy_landed/sell_landed/
  refresh_landed/levelup_landed/battle_start/node_enter/plane_enter/
  settlement);实机-only 三锚(box_opened/event_choice/encounter 刷新发射)
  与缓立/出辖行不在本批闭集。
- 机制面 = 惰性纯登记(零生产调用点,test_cw_anchor_mechanism_lazy 钉死):
  触发口接线归后续批(buy/refresh 触发口随 §6.4 执行器收编批 R-J;boundary
  触发口候 H6 终裁,禁静默选型);sim 侧零动(sim 桶零 import 锁钉死)。

锁编号对照 §12.4-B:①封闭集锁 / ②触发时点型申报锁(+H1 裁决锁)/
③幂等唯一锁 / ④写向隔离锁 / ⑤读向隔离锁 + effect_ref 恒空结构锁;
另有 sell 渠道闭集值域 + 枚举单一源锁(§12.5-4)与载体接线锁。
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

_SRC_CW = (Path(__file__).resolve().parents[5] / 'src' / 'sr_od'
           / 'application' / 'currency_war')

#: §12.2 以「实机先行」标记的锚(本批闭集全集,封闭集锁的期望值面)。
LIVE_FIRST_ANCHORS: frozenset[str] = frozenset({
    'buy_landed', 'sell_landed', 'refresh_landed', 'levelup_landed',
    'battle_start', 'node_enter', 'plane_enter', 'settlement',
})

#: §6.4 触发时点轴三型(锚面扩展申报,v10)。
TRIGGER_AXIS: frozenset[str] = frozenset({'landed', 'emitted', 'boundary'})

#: 各锚申报的触发时点型(§12.2 逐行;emitted 型在册成员 = 实机-only,
#: 不在本批闭集,故本表无 emitted 行)。
DECLARED_TRIGGER: dict[str, str] = {
    'buy_landed': 'landed',
    'sell_landed': 'landed',
    'refresh_landed': 'landed',
    'levelup_landed': 'landed',
    'battle_start': 'landed',
    'node_enter': 'boundary',
    'plane_enter': 'boundary',
    'settlement': 'boundary',
}


@pytest.fixture()
def anchor_env(monkeypatch: pytest.MonkeyPatch):
    """武装 telemetry 出口槽(捕获行)+ 复位幂等键集(测试零真实落盘)。

    被测生产路径含模块级全局(出口槽/幂等键集),setup 一并桩化/清零
    (测试纪律:隔离整条副作用链)。
    """
    from sr_od.application.currency_war.kernel import cw_anchor, cw_telemetry_exit

    rows: list[dict] = []

    def _capture(round_num, kind, detail='', state=None, choice=None):
        rows.append({'round_num': round_num, 'kind': kind,
                     'detail': detail, 'choice': choice})

    # 删除波 1:出口真实现槽(_record_exogenous)已随 exogenous 流写入端
    # 退役删除,出口访问器 = no-op 桩——捕获改锚桩(挂本文件捕获面,防
    # 真实台账落盘;锚路由本身的候裁归宿归 §5-7)。原生产上行断言随退役
    # 移除,本捕获仅证明「发射链不炸、可观测点仍可挂」。
    monkeypatch.setattr(cw_telemetry_exit, 'record_exogenous', _capture)
    monkeypatch.setattr(cw_telemetry_exit, '_run_id_provider',
                        lambda: 'run-anchor-test')
    cw_anchor.reset_anchor_dedupe()
    return rows


# ===== 锁① 登记表封闭集(集外锚 = 红)=====

def test_registry_closed_set_exactly_eight_live_first_anchors():
    """封闭集 = §12.2 实机先行 8 锚,不多不少;逐行 sim 适用域申报一致。"""
    from sr_od.application.currency_war.kernel.cw_anchor import (
        ANCHOR_REGISTRY,
    )
    assert set(ANCHOR_REGISTRY) == set(LIVE_FIRST_ANCHORS), (
        '登记表封闭集漂移(集外新增或实机先行缺员):'
        f'{set(ANCHOR_REGISTRY) ^ set(LIVE_FIRST_ANCHORS)}')
    for anchor_id, spec in ANCHOR_REGISTRY.items():
        assert spec.anchor_id == anchor_id
        assert spec.sim_domain == '实机先行', (
            f'{anchor_id} sim 适用域申报与本批切分不符:{spec.sim_domain!r}')


def test_emit_rejects_unregistered_anchor(anchor_env):
    """集外锚发射 = 红(单一入口防线,sell_gate 枚举外拒收同款)。"""
    from sr_od.application.currency_war.kernel.cw_anchor import emit_anchor
    with pytest.raises(ValueError, match='ANCHOR_REGISTRY'):
        emit_anchor('shop_opened', plane=1, round_num=2, payload={},
                    scope='global', produced_by='Test')
    assert anchor_env == []


def test_levelup_landed_kind_revoked_no_double_row_regrowth():
    """禁双行回归守卫(对抗审发现 3 修复面,申报否决折入设计正本
    §12.2 levelup_landed 行):被撤的 kind='levelup_landed'
    不得以任何行的载体 kind 回潮(现役行 = kind='level_up' 复用)。"""
    from sr_od.application.currency_war.kernel.cw_anchor import (
        ANCHOR_REGISTRY,
    )
    assert 'levelup_landed' in ANCHOR_REGISTRY          # 锚名在册(登记名)
    carriers = {s.carrier_kind for s in ANCHOR_REGISTRY.values()}
    assert 'levelup_landed' not in carriers, (
        '载体 kind=levelup_landed 回潮 = 与现役 level_up 行构成同事件两行'
        '(违指标 3;申报否决见 §12.2 levelup_landed 行)')
    assert ANCHOR_REGISTRY['levelup_landed'].carrier_kind == 'level_up'


# ===== 锁② 触发时点型申报(未申报型 = 红;含 H1 裁决锁)=====

def test_trigger_type_axis_declared_per_row():
    """逐锚显式申报触发时点型(禁静默选型,EMIT 同款纪律):轴三型封闭 +
    逐行与 §12.2 申报一致。"""
    from sr_od.application.currency_war.kernel.cw_anchor import (
        ANCHOR_REGISTRY,
        validate_registry,
    )
    validate_registry()   # 轴内校验(非法型 / 空申报 = 红)
    for anchor_id, spec in ANCHOR_REGISTRY.items():
        assert spec.trigger_type in TRIGGER_AXIS
        assert spec.trigger_type == DECLARED_TRIGGER[anchor_id], (
            f'{anchor_id} 触发时点型与 §12.2 申报不符')


def test_registry_validation_rejects_unknown_trigger_type():
    """登记校验:未知触发时点型登记 = 红(对齐 register_outcome_hook
    的 trigger 校验守卫形态,cw_screen_op_base 同款炸错不静默收下)。"""
    from sr_od.application.currency_war.kernel import cw_anchor
    from sr_od.application.currency_war.kernel.cw_anchor import AnchorSpec
    bad = {'rogue': AnchorSpec(
        anchor_id='rogue', trigger_type='verify', host='x', carrier_kind='k',
        sim_domain='实机先行', evidence_required=False, prerequisite='',
        source='测试构造')}
    with pytest.raises(ValueError, match='触发时点型'):
        cw_anchor.validate_registry(bad)


def test_boundary_declaration_surface_is_registry_type_column():
    """H1 裁决锁:boundary 申报面 = ANCHOR_REGISTRY 行触发时点型列,
    不另立 BOUNDARY_TRIGGERED_DECLARED 独立表、不动既有 EMIT 表(该表归
    基类文件,T-218 在飞面禁碰)。裁决理由 = 设计已定锚登记行必带触发
    时点型字段(§12.3 末段),第二申报面即双源。"""
    from sr_od.application.currency_war.kernel.cw_anchor import (
        ANCHOR_REGISTRY,
    )
    boundary = {k for k, s in ANCHOR_REGISTRY.items()
                if s.trigger_type == 'boundary'}
    assert boundary == {'node_enter', 'plane_enter', 'settlement'}
    # 定义面扫描(赋值形态);散文提及(如本裁决的记录文字)不算回潮。
    decl = re.compile(r'\bBOUNDARY_TRIGGERED_DECLARED\s*[:=]')
    hits: list[str] = []
    for path in _SRC_CW.rglob('*.py'):
        if decl.search(path.read_text(encoding='utf-8')):
            hits.append(str(path))
    assert not hits, f'boundary 独立申报面回潮:{hits}'


def test_refresh_landed_carrier_routing_deferred(anchor_env):
    """refresh_landed 载体 = 原三写点面(宿主写点已随删除波 1 退役,
    归宿候裁挂 retirement.md §2;非单一 ExogenousEvent kind),锚行落盘
    路由候 H2 申报——本批发射口对该锚拒绝路由(如实申报,不假装有单一
    载体 kind)。"""
    from sr_od.application.currency_war.kernel.cw_anchor import emit_anchor
    with pytest.raises(ValueError, match='载体'):
        emit_anchor('refresh_landed', plane=1, round_num=1, payload={},
                    scope='unit', produced_by='X')
    assert anchor_env == []


# ===== 锁③ 幂等唯一(夹具双 fire 零双行)=====

def test_emit_idempotent_double_fire_zero_duplicate_rows(anchor_env):
    """同幂等键双 fire = 零双行(第二发丢弃并返 False);异 event_key =
    两行(单元内多次同名事件不误伤);node_enter 型(无 event_key)同
    (plane,round) 唯一 = 指标 3 的 (plane,round) 去重语义。"""
    from sr_od.application.currency_war.kernel.cw_anchor import emit_anchor

    kw = {'plane': 1, 'round_num': 3, 'payload': {}, 'scope': 'unit',
          'node_seq': 4, 'unit_seq': 2, 'produced_by': 'TestOp'}
    assert emit_anchor('buy_landed', event_key='slot3#1',
                       summary='第一次', **kw) is True
    assert emit_anchor('buy_landed', event_key='slot3#1',
                       summary='重试路径双触发', **kw) is False
    assert emit_anchor('buy_landed', event_key='slot3#2',
                       summary='同单元第二买', **kw) is True
    assert len(anchor_env) == 2, '双 fire 必须恰两行(零双行、零误吞)'
    # node_enter 同 (plane,round) 唯一(设计 §12.4-3 申报语义)
    nk = {'plane': 2, 'round_num': 5, 'payload': {}, 'scope': 'plane',
          'produced_by': 'Loop'}
    assert emit_anchor('node_enter', **nk) is True
    assert emit_anchor('node_enter', **nk) is False
    assert len([r for r in anchor_env if r['kind'] == 'node_enter']) == 1


# ===== 锁④ 写向隔离(锚机制禁触 run 状态与决策域)=====

_ANCHOR_MODULE_FORBIDDEN: tuple[str, ...] = (
    'stop_running', 'last_state', 'run_context')


def test_anchor_mechanism_write_direction_isolation():
    """写向隔离锁(§12.4-B④):①机制 API 面无 ctx/session/op 入参
    (拿不到就写不了,结构性隔离);②机制源面零停机/决策域写入词
    (锚钩子体调 stop_running = 红;观察写入 API 之外写决策域 = 红;
    BoardState 观察写入合法面归未来钩子体,机制面零涉)。扫描根 =
    本批锚机制文件;触发口接线批落钩子体时同批扩根(先例 = ADR-0571
    grep 守卫扩面纪律)。"""
    import sr_od.application.currency_war.kernel.cw_anchor as cw_anchor

    params = set(inspect.signature(cw_anchor.emit_anchor).parameters)
    touching = params & {'ctx', 'session', 'op', 'self'}
    assert not touching, f'锚机制 API 混入宿主对象入参:{sorted(touching)}'
    src = Path(cw_anchor.__file__).read_text(encoding='utf-8')
    hits = [k for k in _ANCHOR_MODULE_FORBIDDEN if k in src]
    assert not hits, f'锚机制源面出现决策域/停机写入词:{hits}'
    # 变异自检:守卫判据对合成坏形必须可检出(防扫描根失准假绿)。
    assert [k for k in _ANCHOR_MODULE_FORBIDDEN
            if k in 'x.stop_running(y)'] == ['stop_running']


def test_emit_side_effect_is_single_row(anchor_env):
    """行为面写向隔离:一次发射的全部副作用 = 经出口槽落一行
    (锚是记录面,永不触碰 run 状态,§12.5-3)。"""
    from sr_od.application.currency_war.kernel.cw_anchor import emit_anchor
    assert emit_anchor('battle_start', plane=1, round_num=1, payload={},
                       scope='plane', produced_by='PrepOp') is True
    assert len(anchor_env) == 1


# ===== 锁⑤ 读向隔离(决策/跟踪代码禁读锚行)+ effect_ref 恒空 =====

_ANCHOR_READ_KEYS: tuple[str, ...] = ('cw_anchor', 'emit_anchor',
                                      'ANCHOR_REGISTRY', 'AnchorEvent',
                                      'effect_ref')


def _anchor_read_guard_hits(text: str) -> list[str]:
    """守卫判据单一实现(主扫描与变异自检共用,防自检复刻判据)。"""
    return [name for name in _ANCHOR_READ_KEYS if name in text]


def test_decision_surface_forbidden_from_reading_anchor_rows():
    """读向隔离锁(§12.4-B⑤,方向沿 ADR-0577 先例 = 决策代码禁读遥测行
    的 grep 子串守卫):策略决策/跟踪面(strategies/impl 全子树)禁现
    锚行标识——决策消费锚行 = 效果通道回流的开口(锁⑤防的正是它);
    零白名单;盲区自检 + 变异自检沿 hp_pay 守卫先例
    (test_cw_hp_assembly §⑩)。"""
    root = _SRC_CW / 'strategies' / 'impl'
    sentinel = root / 'mandate_v1' / 'mandate.py'
    assert sentinel.is_file(), f'扫描根解析失准:{root}'
    scanned = list(root.rglob('*.py'))
    assert len(scanned) >= 20, f'扫描文件数异常({len(scanned)}),根可能错位'
    assert _anchor_read_guard_hits("x(cw_anchor.emit_anchor)") == \
        ['cw_anchor', 'emit_anchor'], '变异自检未命中'
    offenders: dict[str, str] = {}
    for path in scanned:
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding='utf-8')
        for name in _anchor_read_guard_hits(text):
            offenders[f'{rel}:{name}'] = name
    assert not offenders, (
        '锚行标识被决策面引用(禁令 = §12.4-B⑤:决策/跟踪代码禁读锚行,'
        f'effect_ref 消费须先过用户裁决并同步改造守卫):{offenders}')


def test_sim_bucket_zero_import_of_anchor_mechanism():
    """sim 侧零动(本批切分申报的机器可验面):sim 全子树零引用锚机制
    ——「实机先行」= sim 域锚行落盘面候批(R11:禁把 sim 无锚误读成
    事件未发生;本锁防的是反向:sim 提前私接锚机制)。"""
    root = _SRC_CW / 'sim'
    sentinel = root / 'runner.py'
    assert sentinel.is_file(), f'扫描根解析失准:{root}'
    scanned = list(root.rglob('*.py'))
    assert len(scanned) >= 5, f'扫描文件数异常({len(scanned)})'
    offenders = [p.relative_to(root).as_posix() for p in scanned
                 if 'cw_anchor' in p.read_text(encoding='utf-8')]
    assert not offenders, f'sim 桶出现锚机制引用(实机先行切分被破坏):{offenders}'


def test_effect_ref_slot_always_empty(anchor_env):
    """effect_ref 恒空结构锁(§12.0/锁⑤):非空 = 红;落行 payload 恒带
    effect_ref=None 槽位(效果施加批消费该槽须先过用户裁决并改守卫)。"""
    from sr_od.application.currency_war.kernel.cw_anchor import emit_anchor
    with pytest.raises(ValueError, match='effect_ref'):
        emit_anchor('sell_landed', plane=1, round_num=2, payload={
            'slot': 3, 'effect_ref': 'm4_fuel_sell'},
            scope='unit', produced_by='ShopOp')
    assert anchor_env == []
    assert emit_anchor('sell_landed', plane=1, round_num=2, payload={'slot': 3},
                       scope='unit', produced_by='ShopOp') is True
    row = anchor_env[0]['choice']['anchor']['payload']
    assert row['effect_ref'] is None and set(row) == {'slot', 'effect_ref'}


# ===== sell 渠道闭集值域 + 枚举/归一映射单一源(§12.5-4)=====

def test_sell_channel_domain_declaration_resolves_to_single_source():
    """渠道闭集值域:登记面以符号名锚申报('sell_gate.SELL_CHANNELS',
    kernel 禁第二枚举),测试侧解析 = 真闭集(单一源在 sell_gate,
    符号名锚纪律)。"""
    from sr_od.application.currency_war.kernel.cw_anchor import (
        PAYLOAD_DOMAIN_REFS,
    )
    assert PAYLOAD_DOMAIN_REFS == {
        'sell_landed': {'channel': 'sell_gate.SELL_CHANNELS'}}, (
        'payload 值域申报面漂移(新增申报须随 H2 schema 修订批)')
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        sell_gate,
    )
    assert frozenset({
        'interest', 'funding', 'm4_fuel', 'line_switch', 'projection'}) == sell_gate.SELL_CHANNELS


def test_sell_channel_domain_guard_armed_rejects_non_member(anchor_env):
    """值域守卫(显式接通,缺省关):接通后渠道枚举外值 = 红,
    闭集内值放行(kernel 零上层依赖 = 值由装配点注入,不在 kernel 重抄)。"""
    from sr_od.application.currency_war.kernel import cw_anchor
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        sell_gate,
    )
    cw_anchor.register_payload_domain_values(
        'sell_gate.SELL_CHANNELS', sell_gate.SELL_CHANNELS)
    with pytest.raises(ValueError, match='SELL_CHANNELS'):
        cw_anchor.emit_anchor('sell_landed', plane=1, round_num=2, payload={
            'slot': 3, 'channel': 'not_a_channel'},
            scope='unit', produced_by='ShopOp')
    assert anchor_env == []
    assert cw_anchor.emit_anchor('sell_landed', plane=1, round_num=2, payload={
        'slot': 3, 'channel': 'm4_fuel'},
        scope='unit', produced_by='ShopOp') is True


def test_channel_cause_enumeration_single_source_scan():
    """渠道/买因枚举单一源(SELL_CHANNELS/LAUNCH_CAUSES 定义点唯一
    = sell_gate.py;归一映射宿主随 H2 钉死,本锁先围栅栏防第二枚举
    孳生——§12.5-4 禁第二套渠道/买因枚举)。"""
    decl = re.compile(r'\b(SELL_CHANNELS|LAUNCH_CAUSES)\s*[:=]')
    owners: dict[str, set[str]] = {}
    for path in _SRC_CW.rglob('*.py'):
        rel = path.relative_to(_SRC_CW).as_posix()
        for m in decl.finditer(path.read_text(encoding='utf-8')):
            owners.setdefault(m.group(1), set()).add(rel)
    assert owners == {
        'SELL_CHANNELS': {'strategies/impl/mandate_v1/sell_gate.py'},
        'LAUNCH_CAUSES': {'strategies/impl/mandate_v1/sell_gate.py'},
    }, f'枚举定义点漂移(第二枚举/散点手搓映射孳生):{owners}'


# ===== 载体接线 + 观测-only 核验 =====

def test_emit_routes_through_exogenous_carrier_with_seven_fields(anchor_env):
    """锚行七字段封装经 ExogenousEvent 载体落行(§12.3 载体一):kind =
    登记表载体 kind(单一源);choice['anchor'] 携七字段组
    (anchor_id/trigger_type/时点键/payload/scope/evidence_refs/
    produced_by);局外(run_id 空)= no-op 返 False 不写假行。"""
    from sr_od.application.currency_war.kernel import cw_anchor, cw_telemetry_exit

    assert cw_anchor.emit_anchor(
        'buy_landed', plane=2, round_num=4, payload={'card': 'x', 'cost': 3},
        scope='unit', node_seq=7, unit_seq=1, produced_by='BuyWaveOp',
        event_key='slot5#1', summary='买牌落地') is True
    row = anchor_env[0]
    assert row['kind'] == cw_anchor.ANCHOR_REGISTRY['buy_landed'].carrier_kind
    assert 'anchor:' in row['detail'] or 'buy_landed' in row['detail']
    a = row['choice']['anchor']
    assert a['anchor_id'] == 'buy_landed'
    assert a['trigger_type'] == 'landed'
    assert a['run_id'] == 'run-anchor-test'
    assert (a['plane'], a['round'], a['node_seq'], a['unit_seq']) == \
        (2, 4, 7, 1)
    assert a['scope'] == 'unit' and a['produced_by'] == 'BuyWaveOp'
    assert a['evidence_refs'] == []
    assert a['ts']
    # 局外 no-op:run_id 提供者撤除 → 不写假行
    monkey_none = cw_telemetry_exit
    orig = monkey_none._run_id_provider
    monkey_none._run_id_provider = lambda: ''
    try:
        cw_anchor.reset_anchor_dedupe()
        assert cw_anchor.emit_anchor(
            'buy_landed', plane=1, round_num=1, payload={}, scope='unit',
            produced_by='X') is False
        assert len(anchor_env) == 1
    finally:
        monkey_none._run_id_provider = orig


def test_scope_value_domain_and_evidence_gate(anchor_env):
    """scope 口径域封闭(global|plane|unit,§12.3)+ evidence_required
    留证门(判定事实型锚 evidence_refs 非空,指标 5;初判全 false 由
    封闭集锁面覆盖,本锁用临时登记验证门本体)。"""
    import dataclasses

    from sr_od.application.currency_war.kernel import cw_anchor
    from sr_od.application.currency_war.kernel.cw_anchor import (
        AnchorEvent,
        AnchorSpec,
    )
    with pytest.raises(ValueError, match='scope'):
        cw_anchor.emit_anchor('buy_landed', plane=1, round_num=1, payload={},
                              scope='round', produced_by='X')
    # evidence 门:临时登记表(不污染真封闭集,monkeypatch 还原)
    gated = dict(cw_anchor.ANCHOR_REGISTRY)
    gated['judge_frame'] = AnchorSpec(
        anchor_id='judge_frame', trigger_type='landed', host='测试构造',
        carrier_kind='judge_frame', sim_domain='实机先行',
        evidence_required=True, prerequisite='', source='测试构造')
    orig_spec = cw_anchor.ANCHOR_REGISTRY
    cw_anchor.ANCHOR_REGISTRY = gated
    try:
        with pytest.raises(ValueError, match='evidence'):
            cw_anchor.emit_anchor('judge_frame', plane=1, round_num=1,
                                  payload={}, scope='global',
                                  produced_by='X')
        assert cw_anchor.emit_anchor('judge_frame', plane=1, round_num=1,
                                     payload={}, scope='global',
                                     produced_by='X',
                                     evidence_refs=[{'shot': 'a.png'}]) is True
    finally:
        cw_anchor.ANCHOR_REGISTRY = orig_spec
    assert AnchorEvent is not None and dataclasses.is_dataclass(AnchorEvent)


def test_unknown_payload_domain_ref_arming_rejected():
    """值域守卫武装纪律:未申报的符号名锚拒收(武装面必须先在
    PAYLOAD_DOMAIN_REFS 申报——防绕申报面私注值域)。"""
    from sr_od.application.currency_war.kernel import cw_anchor
    with pytest.raises(ValueError, match='PAYLOAD_DOMAIN_REFS'):
        cw_anchor.register_payload_domain_values('elsewhere.SET', frozenset())


#: 惰性面字面豁免(本锁 docstring 预留「随批申报扩展」通道的扩展;
#: 逐条依据见锁 docstring 语义重推)。
#: - kernel/cw_telemetry_exit.py:出口桩 docstring 持久指针(T-272 申报);
#: - operations/cw_screen/cw_screen_boss_briefing.py:T-8 五相位屏迁移批,
#:   模块 docstring 指向判别单一源在册锁文件(test_cw_anchor_exclusion)
#:   作持久索引——散文提及 ≠ import/调用(同 cw_telemetry_exit 豁免语义;
#:   该屏零锚机制消费,本批迁移只改宿主类)。
_LAZY_FACE_MENTION_WHITELIST: frozenset[str] = frozenset({
    'kernel/cw_telemetry_exit.py',
    'operations/cw_screen/cw_screen_boss_briefing.py',
})


def test_anchor_mechanism_lazy_zero_production_call_sites():
    """零生产消费守卫(cw_game_ports 批 0 同款):本批机制 = 惰性纯登记
    文件,src 全树除机制文件自身零引用 = 零行为变更的机器可验面。触发口
    接线批落调用点时,本锁白名单随批申报扩展(先改锁再接线)。

    白名单语义重推(T-272 修正批申报):kernel/cw_telemetry_exit.py 的
    record_exogenous 出口桩 = 锚机制自身的合法上行出口(依赖方向
    cw_anchor → record_exogenous,单向,非消费方);该文件含「cw_anchor」
    字面是出口桩 docstring 按注释规范必须携带的持久指针(模块路径),
    散文提及 ≠ import/调用,锁意图(机制面零生产消费、接线先改锁)未破
    ——子串扫描对「散文提及」过近似,按预留通道豁免该文件。"""
    offenders: list[str] = []
    for path in _SRC_CW.rglob('*.py'):
        rel = path.relative_to(_SRC_CW).as_posix()
        if rel.replace('\\', '/').endswith('kernel/cw_anchor.py'):
            continue
        if rel in _LAZY_FACE_MENTION_WHITELIST:
            continue
        if 'cw_anchor' in path.read_text(encoding='utf-8'):
            offenders.append(rel)
    assert not offenders, (
        f'锚机制出现生产引用(惰性面被破坏,须先过触发口批申报):{offenders}')
