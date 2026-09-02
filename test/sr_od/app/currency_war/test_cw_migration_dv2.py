"""test_cw_migration_dv2 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- w606_switch: test_cw_w606_switch.py
- w609_phase_field_spec: test_cw_w609_phase_field_spec.py
- w612_effect_inventory: test_cw_w612_effect_inventory.py
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations

# ==================== w606_switch ====================
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
    DecisionV2Registry,
)


def test_switch_field_deleted_from_registry():
    """无开关 directive:开臂开关物理消失(语义升格 = 新环唯一路径)。"""
    assert not hasattr(DEFAULT_REGISTRY, 'director_v2_prep_enabled')
    import dataclasses
    names = {f.name for f in dataclasses.fields(DecisionV2Registry)}
    assert 'director_v2_prep_enabled' not in names


def test_adapter_no_longer_exports_enablement_helper():
    import sr_od.application.currency_war.decision.decision_v2.adapter as adapter
    assert not hasattr(adapter, 'director_v2_enabled')


# (影子比对诊断锁已随 shadow_compare 开关族删除——旧方案清退批,
#  清查报告 OLD_MIX_AUDIT §1.3;decision_assembly.shadow_compare_*
#  函数同批删。)
def test_shadow_compare_wiring_deleted():
    import dataclasses

    import sr_od.application.currency_war.decision_assembly as da
    names = {f.name for f in dataclasses.fields(DecisionV2Registry)}
    assert 'director_v2_shadow_compare' not in names
    assert not hasattr(da, 'shadow_compare_enabled')
    assert not hasattr(da, 'shadow_compare_step')


# ==================== w609_phase_field_spec ====================

import inspect
import json
from pathlib import Path

import pytest

from sr_od.application.currency_war.kernel import cw_observe
from sr_od.application.currency_war.kernel.cw_obs_core import UPPER_SCREENS
from sr_od.application.currency_war.obs import cw_observation as obs
from sr_od.application.currency_war.obs.cw_observation_gate import (
    ENTRY_OVERLAY_CLOSE,
    PHASE_BATTLE_OR_TRANSIT,
    PHASE_FIELD_SPEC,
    PHASE_PREP_CLEAN,
    PHASE_PREP_SHOP_OPEN,
)
from sr_od.application.currency_war.telemetry import defects, state

REPO = Path(__file__).resolve().parents[5]


class _DummyCtx:
    """最小 ctx 桩:reader 全部被桩,本对象只承载 getattr(ctx, 'cw_match', None)。"""


# 全量路径会触发的 reader 清单(与 read_game_state 识别段一一对应)
_ALL_READERS = (
    'read_gold_settled', 'read_phase_round', 'read_node_type',
    'read_xp_progress', 'read_level_raw_opt', 'read_deploy_cap_debounced',
    'read_enemy_difficulty', 'read_level_up_cost', 'read_streak',
    '_board_pairs', 'read_deployed_count', 'read_shop_cards',
    'read_refresh_probs', 'read_bench_full', 'read_hp_opt',
)


class _Counters:
    def __init__(self):
        self.calls: dict[str, int] = {}

    def bump(self, name):
        self.calls[name] = self.calls.get(name, 0) + 1
        return None


@pytest.fixture()
def gated_env(monkeypatch):
    """桩掉全部 reader + 遥测旁路;返回计数器。"""
    c = _Counters()

    def _stub(name, ret=None):
        def _fn(*args, **kwargs):
            c.bump(name)
            return ret
        monkeypatch.setattr(obs, name, _fn)

    _stub('read_gold_settled', 55)
    _stub('read_phase_round', (2, 3))
    _stub('read_node_type', None)
    _stub('read_xp_progress', (0, 6))
    _stub('read_level_raw_opt', 5)
    _stub('read_deploy_cap_debounced', 5)
    _stub('read_enemy_difficulty', 42)
    _stub('read_level_up_cost', 4)
    _stub('read_streak', 0)
    _stub('_board_pairs', ({}, False))
    _stub('read_deployed_count', 3)
    _stub('read_shop_cards', [])
    _stub('read_refresh_probs', None)
    _stub('read_bench_full', None)
    _stub('read_hp_opt', 80)
    _stub('resolve_paddle_pair', (3, 5))
    # 冲突留证 no-op(测试零真实副作用,不写 .debug 证据账本);直接 setattr
    # 不经 _stub——留证不是 reader,不进 calls 计数面。
    monkeypatch.setattr(obs, 'obs_conflict', lambda *a, **kw: None)
    monkeypatch.setattr(cw_observe, 'bypass_noop', True, raising=False)
    # 遥测旁路/消费面全部静默(session 缺省 None 已走空路径,防御性再桩)
    monkeypatch.setattr(defects, 'bypass_obs_conflict_to_defect',
                        lambda rec: None)
    monkeypatch.setattr(state, 'current_run_id', lambda: None)
    yield c


# ------------------------------------------------- 阶段 gate 生效锁

_FULL_KEYS = {
    'read_gold_settled', 'read_phase_round', 'read_node_type',
    'read_xp_progress', 'read_level_raw_opt', 'read_deploy_cap_debounced',
    'read_enemy_difficulty', 'read_level_up_cost', 'read_streak',
    '_board_pairs', 'read_deployed_count', 'read_shop_cards',
    'read_refresh_probs', 'read_bench_full', 'read_hp_opt',
}


def test_phase_none_is_full_baseline(gated_env):
    """phase=None = 全量路径:全量 reader 全调用(含 hp 真读——全量调用方
    director heavy/对拍帧多为关店备战帧,hp 可见必须 OCR,6fc1fd4c 旧跳过
    只对「spec 明确不含 hp」的阶段成立);合并单读不启用。"""
    obs.read_game_state(_DummyCtx(), None)
    called = set(gated_env.calls)
    assert called == _FULL_KEYS, f'全量基线漂移: {called ^ _FULL_KEYS}'


def test_phase_prep_shop_open_gate(gated_env):
    """开店动作期:仅买牌决策所需;hp/node_type/cap/deployed/难度/连胜零调用。"""
    obs.read_game_state(_DummyCtx(), None, phase=PHASE_PREP_SHOP_OPEN)
    called = set(gated_env.calls)
    expected = {'read_gold_settled', 'read_phase_round', 'read_xp_progress',
                'read_level_raw_opt', 'read_level_up_cost', '_board_pairs',
                'read_shop_cards', 'read_refresh_probs', 'read_bench_full'}
    assert called == expected, f'读取集漂移: {called ^ expected}'


def test_phase_prep_clean_gate(gated_env):
    """干净备战期:全量基线含 hp 真读 + paddle 合并单读;牌面/概率条跳过。"""
    obs.read_game_state(_DummyCtx(), None, phase=PHASE_PREP_CLEAN)
    called = set(gated_env.calls)
    expected = {'read_gold_settled', 'read_phase_round', 'read_hp_opt',
                'read_node_type', 'read_xp_progress', 'read_level_raw_opt',
                'resolve_paddle_pair', 'read_enemy_difficulty',
                'read_level_up_cost', 'read_streak', '_board_pairs',
                'read_bench_full'}
    assert called == expected, f'读取集漂移: {called ^ expected}'
    # hp 真读主路径在 P1(值=桩 80,非沿用 100)
    assert gated_env.calls.get('read_hp_opt') == 1


def test_phase_battle_transit_minimal(gated_env):
    """战斗/过渡帧:仅位面轮次(恢复对局检测消费面只有 plane/round)。"""
    st = obs.read_game_state(_DummyCtx(), None, phase=PHASE_BATTLE_OR_TRANSIT)
    assert set(gated_env.calls) == {'read_phase_round'}
    assert (st.plane, st.round_num) == (2, 3)
    assert st.hp is None and st.hp_readable is False   # 无真值即 None(ADR-0495),零 OCR 不产真值


def test_hp_skip_single_source():
    """hp 读取门由 PHASE_FIELD_SPEC 单一来源驱动:'hp' ∈ spec 或全量路径
    (phase=None)才 OCR;6fc1fd4c 死读跳过只收编到「spec 明确排除 hp」的
    阶段,不再吞掉全量路径(曾致 director heavy 关店帧 hp 恒 miss)。"""
    src = inspect.getsource(obs.read_game_state)
    assert "read_hp_opt(ctx, screen)" in src \
        and "_spec is None or 'hp' in _spec" in src, \
        'hp 读取门必须由 PHASE_FIELD_SPEC 单一来源驱动(全量路径同读)'
    # spec 阶段里 hp 只出现在 prep_clean(真读主路径),其余阶段=对账沿用
    for phase, spec in PHASE_FIELD_SPEC.items():
        if phase == PHASE_PREP_CLEAN:
            assert 'hp' in spec
        else:
            assert 'hp' not in spec


# ------------------------------------------------- 未知阶段 fail-open

def test_unknown_phase_fail_open(gated_env, monkeypatch):
    """未注册阶段名 → 全量(现行为)+ warning,不抛错不猜。"""
    warned = []
    monkeypatch.setattr(obs.log, 'warning',
                        lambda msg, *a: warned.append(msg % a if a else msg))
    set_calls = []
    monkeypatch.setattr(cw_observe, 'set_obs_phase', lambda p: set_calls.append(p))
    obs.read_game_state(_DummyCtx(), None, phase='no_such_phase')
    assert set(gated_env.calls) == _FULL_KEYS
    assert any('no_such_phase' in w for w in warned), 'fail-open 必须显式告警'
    # 证据行阶段标注只认注册阶段(分诊 E:282 行 obs_phase=no_such_phase 泄漏实证
    # ——fail-open 探针置位把假阶段名打进共享冲突账本),未注册阶段不得置位。
    assert 'no_such_phase' not in set_calls, '未注册阶段不得置位 _OBS_PHASE'


# ------------------------------------------------- paddle 合并单读等价

def test_resolve_paddle_pair_in_domain(monkeypatch):
    """域内:单读产出 (X, cap),防抖核直通。"""
    monkeypatch.setattr(obs, '_read_deploy_paddle', lambda c, s, lv=None: (3, 5))
    x, cap = obs.resolve_paddle_pair(_DummyCtx(), None, 5)
    assert (x, cap) == (3, 5)


def test_resolve_paddle_pair_same_debounce_core(monkeypatch):
    """域外:resolve_paddle_pair 与 read_deploy_cap_debounced 走同一防抖核,
    同输入同输出(语义等价,仅省一次重复管线)。"""
    monkeypatch.setattr(obs, '_read_deploy_paddle',
                        lambda c, s, lv=None: (12, 12))   # cap<level? 不,域外 diff>2
    # 重读帧不可得(桩 controller 缺失)→ 两口同返 None(cap 拒信)
    x, cap = obs.resolve_paddle_pair(_DummyCtx(), None, 5)
    cap2 = obs.read_deploy_cap_debounced(_DummyCtx(), None, 5)
    assert (x, cap) == (12, cap2)


# ------------------------------------------------- 噪声判定位

def test_obs_conflict_carries_phase(tmp_path, monkeypatch):
    """obs_conflict 证据行带 obs_phase 阶段键(按阶段分类噪声的判定位)。"""
    monkeypatch.setattr(cw_observe, '_CONFLICT_JOURNAL', tmp_path / 'c.jsonl')
    monkeypatch.setattr(cw_observe, 'current_run_id', lambda: None, raising=False)
    cw_observe.set_obs_phase(PHASE_PREP_SHOP_OPEN)
    try:
        cw_observe.obs_conflict('board', {'ocr': 1}, 2, None, verdict='t')
    finally:
        cw_observe.set_obs_phase(None)
    rec = json.loads((tmp_path / 'c.jsonl').read_text(encoding='utf-8'))
    assert rec.get('obs_phase') == PHASE_PREP_SHOP_OPEN


def test_read_game_state_resets_obs_phase(gated_env):
    """阶段位随读取结束清零(异常路径外,正常返回必须复位)。"""
    obs.read_game_state(_DummyCtx(), None, phase=PHASE_PREP_CLEAN)
    assert cw_observe.current_obs_phase() is None


# ------------------------------------------------- P0 清场注册表

_INTERACTIVE_OVERLAYS = (
    '货币战争-投资环境', '货币战争-投资策略', '货币战争-列车同行',
    '货币战争-盛会之星', '货币战争-祈愿试炼',
    # 遭遇节点=二选一难度选择(决策语义,专属 handler=handle_encounter)——
    # 曾被误列 ENTRY_OVERLAY_CLOSE 致选择被清场关闭、游戏拒出战停滞终局
    # (2026-08-30 局12/13 实证);入排除列防回归。
    '货币战争-遭遇节点',
    # 星徽秘典/补给=决策 overlay(设计定案 5 decision 化):关闭即丢选卡/
    # 补给选择内容,已从清场派生集移出(改走 0i 选卡 / RunSupplyNode
    # 消化)——入排除列防回流。
    '货币战争-星徽秘典弹窗',
    '货币战争-补给',
)


def test_entry_overlay_close_registry_health():
    """注册表条目:全部属于上层屏名单 + area 已建档;交互 overlay 不进表。"""
    assert ENTRY_OVERLAY_CLOSE, '注册表不应为空'
    for screen_name, area_name in ENTRY_OVERLAY_CLOSE.items():
        assert screen_name in UPPER_SCREENS, \
            f'{screen_name} 不在 UPPER_SCREENS(清场后 gate 排除链断)'
        assert area_name, f'{screen_name} 关闭按钮 area 名为空'
    for s in _INTERACTIVE_OVERLAYS:
        assert s not in ENTRY_OVERLAY_CLOSE, \
            f'{s} 是交互 overlay(决策内容),禁止自动关闭'


def test_entry_overlay_close_areas_exist_in_yml():
    """注册表每个 (画面名, 关闭按钮 area) 在 screen_info yml 中真实存在。"""
    yml_dir = REPO / 'assets' / 'game_data' / 'screen_info'
    found: dict[str, set[str]] = {}
    import yaml
    for fp in yml_dir.glob('*.yml'):
        if fp.name == '_od_merged.yml':
            continue
        data = yaml.safe_load(fp.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or not data.get('screen_name'):
            continue
        areas = {a.get('area_name') for a in (data.get('area_list') or [])
                 if isinstance(a, dict)}
        found[data['screen_name']] = areas
    for screen_name, area_name in ENTRY_OVERLAY_CLOSE.items():
        assert screen_name in found, f'{screen_name} 无画面档'
        assert area_name in found[screen_name], \
            f'{screen_name}.{area_name} 未建档(注册表锚失效)'


def test_prep_director_clear_entry_wired():
    """清场段已接进备战环入口(gate 之前),且 fail-open(异常即返回)。"""
    from sr_od.application.currency_war import prep_director
    src_loop = inspect.getsource(prep_director.PrepDirector.run)
    assert '_clear_entry_overlays()' in src_loop, \
        '环入口未接 P0 清场段'
    # 清场段调用必须在观察之前(先清场、再识别);
    # W971 P3b 拆内环:gate 已除,序锚 = 单轮 heavy 观察行
    assert src_loop.index('_clear_entry_overlays()') \
        < src_loop.index('obs = self._observe(heavy=True)')
    src_clear = inspect.getsource(prep_director.PrepDirector._clear_entry_overlays)
    assert 'except Exception' in src_clear, '清场段必须 fail-open(离线契约)'



# ==================== w612_effect_inventory ====================

import dataclasses
import sys
from pathlib import Path as _w612_effect_inventory_Path

import pytest as _w612_effect_inventory_pytest

_REPO = _w612_effect_inventory_Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.data.cw_invest_data import (
    PLAZA_AUGMENTS,  # noqa: E402
)
from sr_od.application.currency_war.decision.cw_strategy import (
    StrategySession,  # noqa: E402
)
from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_effect_inventory import (  # noqa: E402
    ActiveEffectInventory,
    BattlefieldEffect,
    CounterKey,
    DurationKind,
    EffectKind,
    TriggerKind,
)
from sr_od.application.currency_war.kernel.cw_investments import (  # noqa: E402
    INVESTMENT_STRATEGIES,
    STRATEGY_ECONOMY,
    STRATEGY_EFFECTS,
    EconomyEffect,
)

# ===== T1 · EffectSpec 构造锁 =====

def test_spec_frozen() -> None:
    """frozen 不可变:任一字段赋值抛 FrozenInstanceError。"""
    spec = STRATEGY_EFFECTS['淘金客']
    with _w612_effect_inventory_pytest.raises(dataclasses.FrozenInstanceError):
        spec.trigger = TriggerKind.INSTANT  # type: ignore[misc]


def test_overlay_no_orphans_and_id_match() -> None:
    """孤儿键 + id 双匹配:import 已过 _validate_strategy_effects(同路径再断言一次,
    防构建函数被移除后本锁静默失效)。"""
    cw_investments._validate_strategy_effects()
    for spec in STRATEGY_EFFECTS.values():
        base = INVESTMENT_STRATEGIES[spec.name]
        assert base.source == f'plaza:{spec.id}'


def test_payload_category_consistency() -> None:
    """payload 类型与 category 一致(ECONOMY/STATE→EconomyEffect、
    BATTLEFIELD→BattlefieldEffect、UNIT_BUFF→UnitBuffRef)。"""
    for spec in STRATEGY_EFFECTS.values():
        if spec.category in (EffectKind.ECONOMY, EffectKind.STATE):
            assert isinstance(spec.payload, EconomyEffect), spec.name
        elif spec.category == EffectKind.BATTLEFIELD:
            assert isinstance(spec.payload, BattlefieldEffect), spec.name
        else:
            from sr_od.application.currency_war.kernel.cw_effect_inventory import (
                UnitBuffRef,
            )
            assert isinstance(spec.payload, UnitBuffRef), spec.name


def test_first_batch_structures() -> None:
    """首批条目四元组结构回显锁(锁结构不锁数值;数值在 payload/注册表)。"""
    expect = {
        # (id, trigger, duration, category, duties.predict, pending)
        '301601': (TriggerKind.ON_REFRESH, DurationKind.WHILE_HELD, EffectKind.STATE, False, False),
        '201801': (TriggerKind.PLANE_START, DurationKind.PERMANENT, EffectKind.STATE, False, True),
        '103601': (TriggerKind.CONDITIONAL, DurationKind.WHILE_HELD, EffectKind.ECONOMY, False, True),
        '300201': (TriggerKind.LEVEL_UP, DurationKind.WHILE_HELD, EffectKind.BATTLEFIELD, True, False),
        '204101': (TriggerKind.NODE_ENTER, DurationKind.WHILE_HELD, EffectKind.BATTLEFIELD, True, False),
        '201201': (TriggerKind.ON_REFRESH, DurationKind.WHILE_HELD, EffectKind.BATTLEFIELD, True, False),
        '303101': (TriggerKind.ON_REFRESH, DurationKind.WHILE_HELD, EffectKind.BATTLEFIELD, True, False),
        '102701': (TriggerKind.INSTANT, DurationKind.ONCE, EffectKind.BATTLEFIELD, True, False),
        '102801': (TriggerKind.INSTANT, DurationKind.ONCE, EffectKind.BATTLEFIELD, True, False),
        '102001': (TriggerKind.CONDITIONAL, DurationKind.N_NODES, EffectKind.ECONOMY, False, False),
    }
    assert {s.id for s in STRATEGY_EFFECTS.values()} == set(expect)
    by_id = {s.id: s for s in STRATEGY_EFFECTS.values()}
    for spec_id, (trig, dur, cat, predict, pending) in expect.items():
        spec = by_id[spec_id]
        assert (spec.trigger, spec.duration, spec.category) == (trig, dur, cat), spec_id
        assert spec.duties.predict is predict, spec_id
        assert spec.pending is pending, spec_id


def test_pending_entries_have_conservative_notes_and_verdict_unset() -> None:
    """二义条目:pending=True 必须 notes 写保守支、verdict 保持 None(不猜,等实采)。"""
    for spec in STRATEGY_EFFECTS.values():
        if spec.pending:
            assert spec.verdict is None, spec.name
            assert spec.notes, spec.name
    assert STRATEGY_EFFECTS['固定理财'].pending
    assert STRATEGY_EFFECTS['经验就是财富'].pending


# ===== T2 · inventory 登记/查表/剩余期锁 =====

def _inv_with_all_specs() -> ActiveEffectInventory:
    inv = ActiveEffectInventory()
    for spec in STRATEGY_EFFECTS.values():
        inv.register_strategy(spec, acquired_t=10)
    return inv


def test_register_query_roundtrip() -> None:
    inv = _inv_with_all_specs()
    assert len(inv.entries) == len(STRATEGY_EFFECTS)
    assert len(inv.by_category(EffectKind.BATTLEFIELD)) == 6
    assert len(inv.by_trigger(TriggerKind.ON_REFRESH)) == 3
    assert inv.first('301601') is not None
    assert inv.first('999999') is None


def test_predict_for_level_up_returns_spy_only() -> None:
    """predict_for('level_up') 恰返回商业间谍一条(升级触发族唯一 predict 条目)。"""
    inv = _inv_with_all_specs()
    hits = inv.predict_for('level_up')
    assert [e.spec.id for e in hits] == ['300201']
    # 未知 action 保守返回全部 predict 条目(漏预知=读牌误判,多给不错给)
    assert len(inv.predict_for('unknown_action')) == len(
        [e for e in inv.entries if e.spec.duties.predict])


def test_tangping_remaining_nodes_decrement_and_expiry() -> None:
    """躺平余期:自然数计数 3→递减,第 3 次 tick 移除;第 2 次后 remaining==1 回显。"""
    inv = ActiveEffectInventory()
    inv.register_strategy(STRATEGY_EFFECTS['躺平'], acquired_t=5)
    inv.tick_node()
    inv.tick_node()
    entry = inv.first('102001')
    assert entry is not None and entry.remaining_nodes == 1   # 未过期回显
    inv.tick_node()
    assert inv.first('102001') is None                        # 第 3 次移除


def test_permanent_entries_survive_tick() -> None:
    """WHILE_HELD/PERMANENT 条目 tick 不递减不移除。"""
    inv = _inv_with_all_specs()
    inv.tick_node()
    assert inv.first('301601') is not None    # 淘金客 while_held
    assert inv.first('201801') is not None    # 固定理财 permanent
    assert inv.entries[0].remaining_nodes is None


def test_counters_isolated_per_spec() -> None:
    """计数器按 (spec_id, key) 隔离:两条 ON_REFRESH 策略同 key 不串账。"""
    inv = ActiveEffectInventory()
    inv.register_strategy(STRATEGY_EFFECTS['采购专员·金'], acquired_t=1)
    inv.register_strategy(STRATEGY_EFFECTS['采购专员·彩'], acquired_t=1)
    inv.bump('201201', CounterKey.REFRESH)
    inv.bump('201201', CounterKey.REFRESH)
    inv.bump('303101', CounterKey.REFRESH)
    assert inv.counter('201201', CounterKey.REFRESH) == 2
    assert inv.counter('303101', CounterKey.REFRESH) == 1
    assert inv.counter('201201', CounterKey.BUY) == 0


def test_event_markers_count_only() -> None:
    """on_level_up/on_battle_end 只标记不产效果(P0 语义:效果结算归后续批)。"""
    inv = ActiveEffectInventory()
    inv.on_level_up()
    inv.on_level_up()
    inv.on_battle_end()
    assert inv.event_count('_event_level_up') == 2
    assert inv.event_count('_event_battle_end') == 1
    assert len(inv.entries) == 0   # 不产生/移除任何条目


def test_session_host_field_default() -> None:
    """session 宿主字段:默认工厂给独立实例,两局不共享(局级隔离)。"""
    s1, s2 = StrategySession(), StrategySession()
    assert isinstance(s1.effect_inventory, ActiveEffectInventory)
    assert s1.effect_inventory is not s2.effect_inventory


# ===== T3 · 双源边界锁 =====

def test_strategy_economy_untouched() -> None:
    """STRATEGY_ECONOMY 全量与键集对拍(防实现批顺手改经济值/丢条目)。
    若红:先判锁再判改——可能有合法经济建模修正,禁机械跟绿。"""
    expected_keys = {
        '高效决策', '采购专员·彩', '本金充裕', '开源节流', '利息上调', '买断制',
        '淘金客', '伟大征服', '商业间谍', '返利+', '采购专员·金', '定期福利',
        '加油站', '乱成一锅粥+', '乱成一锅粥', '着眼当下', '搜打撤', '远见',
        '贸易专家:停云', '佩佩驾到', '控制规模', '藏一手', '及时雨', '决议:娱乐星球',
        '公司严选', '节节高升', '本金充裕+', '黄金垃圾', '退化', '停云顾问',
        '加拉赫顾问', '摸个鱼吧II', '摸个鱼吧I', '按劳分配', '专家招募+',
        '专家招募', '大扩招', '五百强', '成本控制', '剩余价值', '四费晋升',
        '小复制+', '小复制', '长期主义+', '长期主义', '大裁员', '嘴硬',
        '秘密典籍+', '秘密典籍', '经验就是财富', '二极管', '免费升舱', '无害垃圾',
        '胜利,还是胜利', '打捞人才库+', '尾款交付', '免费午餐', '特战资金+',
        '特战资金', '返利', '军火贸易', '军火贸易+', '以战养战', '躺平',
        '公司人才流动', '武装支援+', '合并同类项', '无伤通关', '招聘资金',
        '招聘资金+', '溜佩佩', '溜佩佩+', '保险', '成长基金', '成长的快乐',
        '超发货币', '固定理财', '固定理财+', '经验到账', '孪生素数', '狸财经狸',
        '不等价交换', '星际和平保险', '简单模式', '难度修改器', '砂里淘金',
        '星星相印', '武力刷新', '降本增效',
        # 修复项12(2026-08-31,机制修改器审计 F1/F2/F3):概率事件/奋斗协议/市场干预
        # 三件「已消费却无资产」补建——锁键集随之扩(锁语义=键集对拍,新增为合法建模)
        '概率事件', '奋斗协议', '市场干预',
    }
    assert set(STRATEGY_ECONOMY) == expected_keys
    # 本批高频件数值不变(指针引用同一实例的防线:payload 与 overlay 同源)
    assert STRATEGY_EFFECTS['淘金客'].payload is STRATEGY_ECONOMY['淘金客']


def test_only_strategy_source_in_batch() -> None:
    """双源边界:本批数据条目 100% 策略源;环境/词缀源是 W607 辖域不在此建模。
    (source 值在 register 时写死 'strategy';schema 预留值由 ActiveEffect.source
    注释承载,此处锁注册行为。)"""
    inv = _inv_with_all_specs()
    assert {e.source for e in inv.entries} == {'strategy'}


def test_overlay_id_set_matches_registry_ids() -> None:
    """overlay id 全部能在 plaza base 中按 (id, name) 双命中(昵称漂移防线:
    如 Gemi狸 的官方卡名是「双手狸开键盘!」,禁昵称入注册表)。"""
    by_id = {a.id: a.name for a in PLAZA_AUGMENTS}
    for spec in STRATEGY_EFFECTS.values():
        assert by_id.get(spec.id) == spec.name


# ===== T4 · 挂点证据时效锁 =====

def test_hook_points_exist() -> None:
    """四挂点证据时效(HOOKS.md 证据过期即红):
    ①选卡 handler append active_strategies;②battle_loop node_enter 事件;
    ③record_outcome;④升级挂点(prep_actions._level_up 内 inventory 标记 + 'level_up' 事件行)。"""
    import inspect

    import sr_od.application.currency_war.operations.battle_loop as battle_loop
    import sr_od.application.currency_war.operations.handlers.handle_invest_strategy as his
    import sr_od.application.currency_war.prep_actions as prep_actions

    his_src = inspect.getsource(his)
    assert 'active_strategies.append' in his_src
    loop_src = inspect.getsource(battle_loop)
    assert "'node_enter'" in loop_src
    assert 'record_outcome' in loop_src
    prep_src = inspect.getsource(prep_actions)
    assert 'on_level_up' in prep_src
    assert "'level_up'" in prep_src
    # ④ 记录端 kind 枚举补齐(编排者裁决:record_exogenous 支持 level_up)

    from sr_od.application.currency_war.telemetry.recorder import TelemetryRecorder
    assert 'level_up' in inspect.getsource(TelemetryRecorder.record_exogenous)

