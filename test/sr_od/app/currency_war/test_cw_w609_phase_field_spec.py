# -*- coding: utf-8 -*-
"""W609 阶段化字段规格锁(规范入口序列「先清场、再识别、后动作」;ADR-0462)。

- 阶段 gate 生效锁:每阶段只调读取集 reader、跳过集 reader 零调用(mock 计数);
- 未知阶段 fail-open 锁:未注册阶段名 → 全量(现行为),不猜不炸;
- paddle 合并单读等价锁:resolve_paddle_pair 与 read_deploy_cap_debounced 同防抖核;
- 噪声判定位锁:obs_conflict 证据行带 obs_phase 阶段键,读取结束阶段位清零;
- P0 清场注册表健康锁:ENTRY_OVERLAY_CLOSE 的画面/按钮 area 均已建档,
  交互 overlay(投资环境/策略等)不在注册表;
- prep_director 清场段接线锁。

测试纪律:零真实副作用——obs_conflict 的落盘路径/遥测旁路全部 monkeypatch 到
tmp_path/桩;OCR 全部计数桩(不加载真模型)。
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from sr_od.application.currency_war import cw_observation as obs
from sr_od.application.currency_war.kernel import cw_observe
from sr_od.application.currency_war.cw_observation_gate import (
    ENTRY_OVERLAY_CLOSE,
    PHASE_BATTLE_OR_TRANSIT,
    PHASE_FIELD_SPEC,
    PHASE_PREP_CLEAN,
    PHASE_PREP_SHOP_OPEN,
)
from sr_od.application.currency_war.kernel.cw_obs_core import UPPER_SCREENS

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
    monkeypatch.setattr(cw_observe, 'bypass_noop', True, raising=False)
    # 遥测旁路/消费面全部静默(session 缺省 None 已走空路径,防御性再桩)
    from sr_od.application.currency_war import cw_telemetry
    monkeypatch.setattr(cw_telemetry, 'bypass_obs_conflict_to_defect',
                        lambda rec: None)
    monkeypatch.setattr(cw_telemetry, 'current_run_id', lambda: None)
    yield c


# ------------------------------------------------- 阶段 gate 生效锁

_FULL_KEYS = {
    'read_gold_settled', 'read_phase_round', 'read_node_type',
    'read_xp_progress', 'read_level_raw_opt', 'read_deploy_cap_debounced',
    'read_enemy_difficulty', 'read_level_up_cost', 'read_streak',
    '_board_pairs', 'read_deployed_count', 'read_shop_cards',
    'read_refresh_probs', 'read_bench_full',
}


def test_phase_none_is_full_baseline(gated_env):
    """phase=None = 全量路径(现行为):全量 reader 全调用,合并单读不启用。"""
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
    assert st.hp == 100 and st.hp_readable is False   # 对账沿用/兜底,零 OCR


def test_hp_skip_single_source():
    """6fc1fd4c hp 死读跳过已收编进规格:hp OCR 只在 'hp' ∈ spec 时发生。"""
    src = inspect.getsource(obs.read_game_state)
    assert "read_hp_opt(ctx, screen) if (_spec is not None and 'hp' in _spec) else None" \
        in src, 'hp 读取门必须由 PHASE_FIELD_SPEC 单一来源驱动'
    # hp 只出现在 prep_clean 规格里(真读主路径),其余阶段=对账沿用
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
    obs.read_game_state(_DummyCtx(), None, phase='no_such_phase')
    assert set(gated_env.calls) == _FULL_KEYS
    assert any('no_such_phase' in w for w in warned), 'fail-open 必须显式告警'


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
    '货币战争-投资环境', '货币战争-投资策略', '货币战争-选择伙伴',
    '货币战争-盛会之星', '货币战争-祈愿试炼',
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
    src_loop = inspect.getsource(prep_director.PrepDirector._run_loop)
    assert '_clear_entry_overlays()' in src_loop, \
        '环入口未接 P0 清场段'
    # 清场段调用必须在 gate 调用之前(先清场、再识别);
    # 锚=gate 入口日志行(首次 wait_stable_frame 出现在 import 块,不可作序锚)
    assert src_loop.index('_clear_entry_overlays()') \
        < src_loop.index("path=new(director")
    src_clear = inspect.getsource(prep_director.PrepDirector._clear_entry_overlays)
    assert 'except Exception' in src_clear, '清场段必须 fail-open(离线契约)'
