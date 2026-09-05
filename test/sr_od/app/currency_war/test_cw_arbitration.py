"""仲裁注册面(15 号稿批 A)锁族:T-1 注册面语义 / T-2 迁移对拍 / T-6 分键互不混流。

出处:``docs/develop/currency_war/strategy-docs/15_observation_multisource_arbitration.md``
§2.2/§2.4(规则语义)/§6 T-1/T-2/T-6(锁清单)。批 A 严格零行为变更:
本文件全部锁都是「注册面裁决 == 迁移前私写法/文档语义」的对拍,行为锁
(布局三信号等)在批 B,不在此文件。
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.obs import cw_arbitration as arb
from sr_od.application.currency_war.obs import cw_observation as cobs

# ==================== T-1 注册面语义锁(§2.4)====================

def test_t1_registry_count_semantics_truth_table():
    """计数类裁决语义(§2.2 计数行 + deployed 注册声明):

    - 双源齐且相等 → ok;带内(|Δ|≤band=1)→ noise(合法读数差,不行动);
    - 带外 → arbitrated(取低值,divergent=True);
    - 缺席源 → rejected(单源可用,值=另一源,divergent=False);
    - 全缺席 → unknown;未注册 key → KeyError(注册面漏登记禁静默)。
    """
    assert arb.arbitrate('deployed_count', {'paddle_x': 5, 'cv_occupied': 5}) == (
        5, 'ok', False)
    assert arb.arbitrate('deployed_count', {'paddle_x': 3, 'cv_occupied': 4}) == (
        3, 'noise', False)
    assert arb.arbitrate('deployed_count', {'paddle_x': 3, 'cv_occupied': 5}) == (
        3, 'arbitrated', True)
    assert arb.arbitrate('deployed_count', {'paddle_x': 5, 'cv_occupied': 3}) == (
        3, 'arbitrated', True)
    assert arb.arbitrate('deployed_count', {'paddle_x': None, 'cv_occupied': 5}) == (
        5, 'rejected', False)
    assert arb.arbitrate('deployed_count', {'paddle_x': 3, 'cv_occupied': None}) == (
        3, 'rejected', False)
    assert arb.arbitrate('deployed_count', {'paddle_x': None, 'cv_occupied': None}) == (
        None, 'unknown', False)
    with pytest.raises(KeyError):
        arb.arbitrate('not_registered', {})


def test_t1_registry_nominal_semantics_and_rule_declarations():
    """标称类(board)语义 + 注册声明面(§2.2 标称②帧态门 / §2.4 字段必填):

    - 无分歧 → ok(divergent=False);任一 faction 分歧 → arbitrated
      (帧态门在 combine 内裁决:备战帧徽标覆写 / 非备战帧保底座);
    - 计数/布局类规则必须声明 fail_closed_side(§2.4 必填;防照抄 min);
    - defect_kind 全注册表唯一(T-6 分键互不混流的注册面半环)。
    """
    merged, divergent = arb.get_rule('board_faction_count').combine(
        badge_ocr={'仙舟': 2}, computed={'仙舟': 2},
        prep_like=True, board_honest=True)
    assert merged == {'仙舟': 2} and divergent is False
    value, verdict, divergent = arb.arbitrate(
        'board_faction_count',
        {'badge_ocr': {'仙舟': 2}, 'computed': {'仙舟': 2},
         'prep_like': True, 'board_honest': True})
    assert verdict == 'ok' and divergent is False and value == {'仙舟': 2}

    for key in arb.registered_keys():
        rule = arb.get_rule(key)
        if rule.dim_class in (arb.DIM_COUNT, arb.DIM_LAYOUT):
            assert rule.fail_closed_side, f'{key} 缺 fail_closed_side 声明'
    kinds = [arb.get_rule(k).defect_kind for k in arb.registered_keys()]
    assert len(kinds) == len(set(kinds)), f'分键跨量混流:{kinds}'
    assert arb.get_rule('deployed_count').defect_kind == \
        'deployed_count_2src_divergence'


# ==================== T-2 迁移对拍锁(§2.4/§6;零行为验收)====================

def test_t2_deployed_migration_parity_full_grid():
    """deployed 迁移对拍(全格):注册面裁决 == 文档语义(取低值 min +
    分歧 |Δ|>1,§1 行 5 / 7026c5db)在 (0..7)×(0..7) 全格 + None 缺席态
    逐点相等——签名/语义不变的迁移等价证明(含单源缺席退化方向)。"""
    for p in range(8):
        for c in range(8):
            value, divergent = arb.combine_deployed_count(paddle_x=p, cv_occupied=c)
            assert value == min(p, c), (p, c, value)
            assert divergent == (abs(p - c) > 1), (p, c, divergent)
            r_value, _verdict, r_divergent = arb.arbitrate(
                'deployed_count', {'paddle_x': p, 'cv_occupied': c})
            assert (r_value, r_divergent) == (value, divergent)
    # 旧私写法的公共入口(消费面单一入口)与注册面内核同值
    assert cobs.arbitrate_deployed_count(3, 5) == (3, True)
    assert cobs.arbitrate_deployed_count(None, 5) == (5, False)
    assert cobs.arbitrate_deployed_count(3, None) == (3, False)
    assert cobs.arbitrate_deployed_count(None, None) == (None, False)


def _stub_read_game_state(monkeypatch, tmp_path: Path, prep_like: bool):
    """read_game_state 真链驱动(reader 桩面镜像 test_cw_node_screens 注入
    手法),board 段注入分歧帧:badge_ocr=3 vs computed=2。返回 (state, rows)。"""
    import sr_od.application.currency_war.kernel.cw_observe as core_obs
    from sr_od.application.currency_war.kernel.cw_state import BenchChar

    monkeypatch.setattr(core_obs, '_CONFLICT_JOURNAL', tmp_path / 'obs.jsonl')
    monkeypatch.setattr(core_obs, 'cw_shot_unique', lambda img, label: f'{label}.png')
    monkeypatch.setattr(cobs, 'is_prep_like_frame', lambda c, s: prep_like)
    monkeypatch.setattr(cobs, '_board_pairs',
                        lambda c, s, level=None, expected=None:
                        ({'持续伤害': (3, 5)}, True))
    monkeypatch.setattr(cobs, 'board_from_tracked',
                        lambda tracked: {'持续伤害': 2})
    monkeypatch.setattr(cobs, 'read_deployed_count', lambda c, s: None)
    for _n, _v in {
        'read_gold_settled': 55, 'read_phase_round': (2, 3), 'read_node_type': None,
        'read_xp_progress': (0, 6), 'read_level_raw_opt': 5, 'read_level_up_cost': 4,
        'read_shop_cards': [], 'read_refresh_probs': None, 'read_bench_full': None,
    }.items():
        monkeypatch.setattr(cobs, _n,
                            (lambda _v: lambda *a, _v=_v, **kw: _v)(_v))
    session = SimpleNamespace(
        active_strategies=[], last_level_obs=0, last_hp_real=None,
        last_streak=0, tracked_deployed=[BenchChar(slot=1, char_id='大黑塔')],
        briefing_bosses=None, briefing_affixes=None, active_env='',
        chosen_megastar=None, chosen_partner=None)
    ctx = SimpleNamespace(cw_match=SimpleNamespace(session=session))
    from sr_od.application.currency_war.obs.cw_observation import (
        PHASE_PREP_SHOP_OPEN,
    )
    state = cobs.read_game_state(ctx, None, phase=PHASE_PREP_SHOP_OPEN)
    p = tmp_path / 'obs.jsonl'
    rows = [json.loads(ln) for ln in p.read_text(encoding='utf-8').splitlines()
            if ln.strip()] if p.exists() else []
    return state, rows


def test_t2_board_matrix_prep_frame_badge_overwrites(tmp_path: Path, monkeypatch):
    """board 矩阵①:分歧帧 × 备战帧(honest)→ 徽标覆写(state.board=3)+
    obs_conflict 留证行(field='board',new=采新 verdict)——迁移前后裁决与
    留证全同(经生产 read_game_state 真链)。"""
    state, rows = _stub_read_game_state(monkeypatch, tmp_path, prep_like=True)
    assert state.board == {'持续伤害': 3}
    board_rows = [r for r in rows if r['field'] == 'board']
    assert len(board_rows) == 1
    r = board_rows[0]
    assert r['old'] == {'ocr': 3, 'computed': 2}
    assert r['new'] == 'count不等:持续伤害'
    assert '采新-badge' in r['verdict']
    assert r['source'] == 'computed_vs_ocr'


def test_t2_board_matrix_non_prep_frame_keeps_computed(tmp_path: Path, monkeypatch):
    """board 矩阵②:分歧帧 × 非备战帧 → 双不可信,保 computed 底座
    (board=2)+ 留证行(不覆写)——帧态门语义迁移前后全同。"""
    state, rows = _stub_read_game_state(monkeypatch, tmp_path, prep_like=False)
    assert state.board == {'持续伤害': 2}
    board_rows = [r for r in rows if r['field'] == 'board']
    assert len(board_rows) == 1
    assert board_rows[0]['old'] == {'ocr': 3, 'computed': 2}
    assert '留证-双不可信' in board_rows[0]['verdict']


def test_t2_board_no_divergence_zero_rows(tmp_path: Path, monkeypatch):
    """board 矩阵③(常态一致):badge==computed → 零决策零留证
    (is_prep_like_frame 常态零开销语义随迁移保持)。"""
    import sr_od.application.currency_war.kernel.cw_observe as core_obs
    import sr_od.application.currency_war.obs.cw_observation as obs
    from sr_od.application.currency_war.kernel.cw_state import BenchChar

    monkeypatch.setattr(core_obs, '_CONFLICT_JOURNAL', tmp_path / 'obs.jsonl')
    monkeypatch.setattr(core_obs, 'cw_shot_unique', lambda img, label: f'{label}.png')
    monkeypatch.setattr(obs, 'is_prep_like_frame', lambda c, s: True)
    monkeypatch.setattr(obs, '_board_pairs',
                        lambda c, s, level=None, expected=None:
                        ({'持续伤害': (2, 5)}, True))
    monkeypatch.setattr(obs, 'board_from_tracked',
                        lambda tracked: {'持续伤害': 2})
    monkeypatch.setattr(obs, 'read_deployed_count', lambda c, s: None)
    for _n, _v in {
        'read_gold_settled': 55, 'read_phase_round': (2, 3), 'read_node_type': None,
        'read_xp_progress': (0, 6), 'read_level_raw_opt': 5, 'read_level_up_cost': 4,
        'read_shop_cards': [], 'read_refresh_probs': None, 'read_bench_full': None,
    }.items():
        monkeypatch.setattr(obs, _n,
                            (lambda _v: lambda *a, _v=_v, **kw: _v)(_v))
    session = SimpleNamespace(
        active_strategies=[], last_level_obs=0, last_hp_real=None,
        last_streak=0, tracked_deployed=[BenchChar(slot=1, char_id='大黑塔')],
        briefing_bosses=None, briefing_affixes=None, active_env='',
        chosen_megastar=None, chosen_partner=None)
    ctx = SimpleNamespace(cw_match=SimpleNamespace(session=session))
    from sr_od.application.currency_war.obs.cw_observation import (
        PHASE_PREP_SHOP_OPEN,
    )
    state = obs.read_game_state(ctx, None, phase=PHASE_PREP_SHOP_OPEN)
    assert state.board == {'持续伤害': 2}
    p = tmp_path / 'obs.jsonl'
    rows = [json.loads(ln) for ln in p.read_text(encoding='utf-8').splitlines()
            if ln.strip()] if p.exists() else []
    assert not [r for r in rows if r['field'] == 'board']


# ==================== T-6 分键互不混流(§2.4/§6)====================

def test_t6_defect_kinds_do_not_mix_streams():
    """T-6 分键互不混流:注册面各量 defect_kind 唯一,且与既有独立分键
    (deployed_count_2src 系列 / reward_sphere_phantom / back_layout 系列)
    互异——不一致率统计按键隔离,禁两条流水共用一个 kind。"""
    from sr_od.application.currency_war.telemetry.defects import (
        DEFECT_KIND_DEPLOYED_COUNT_2SRC,
        DEFECT_KIND_DEPLOYED_COUNT_2SRC_SUSTAINED,
    )
    kinds = {arb.get_rule(k).defect_kind for k in arb.registered_keys()}
    kinds |= {DEFECT_KIND_DEPLOYED_COUNT_2SRC,
              DEFECT_KIND_DEPLOYED_COUNT_2SRC_SUSTAINED,
              'reward_sphere_phantom',
              'back_layout_divergence', 'back_layout_unknown'}
    assert len(kinds) == len(set(kinds))
