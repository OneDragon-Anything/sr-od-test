"""test_cw_sim_piggy 主题锁——扑满环境注入采集面(T-143)。

覆盖面(承重件):
- 变体表锁:PIGGY_VARIANT_ENVS 与 kernel/cw_env_economy 估算参数键族
  ``reward_node_bonus_{variant}`` 双向对齐(防单侧改名 = 参数查询恒 miss
  的哑臂漂移;C 类通道消费端单一源 = cw_env_economy._REWARD_BONUS_VARIANTS);
- 注入链 e2e:注入过热环境 → ``piggy_reward`` 标记在奖励帧精确为 True
  (写点 = mandate_v1 shop/mandate 两栈,判据单一源 kernel/cw_reward_node;
  shop 栈写点曾因旧 ``CwWorkFrame.node_type`` 属性失联 = T-143 修复对象,
  本锁即其回归门);基线臂(无环境)恒零污染;
- 批入口:run_piggy_batch 落账本 + manifest(seeds 键 = 占用段对账锚,
  sim-testing 种子段纪律)+ 报告结构(baseline_zero_piggy 闸)。

出处:被测模块 = sim/cw_sim_piggy.py;注入机制 = sim/cw_sim_invest.py
(W162/ADR-0364)与 sim/engine_p1.py 注入写点;辖域边界(sim 不建模扑满
战利品金流,样本 = 识别面)见被测模块 docstring。
"""
from __future__ import annotations

import json

import pytest

from sr_od.application.currency_war.kernel.cw_reward_node import PIGGY_ENV_NAMES
from sr_od.application.currency_war.sim.cw_sim_piggy import (
    PIGGY_VARIANT_ENVS,
    aggregate_arm,
    piggy_profile,
)
from sr_od.application.currency_war.sim.engine_p1 import SimResult

# ==================== 变体表锁(与估算参数键族对齐) ====================


def test_piggy_variant_table_locks_economy_estimate_keys() -> None:
    """变体表 ↔ C 类估算参数键族双向锁。

    cw_env_economy._REWARD_BONUS_VARIANTS 是 C 类通道参数查询的单一源
    (经济过热→normal/经济严重过热→super);sim 侧注入表变体键若与之
    漂移,采出的样本将对不上落参键名 = 哑臂。双向断言防单侧改名。
    """
    from sr_od.application.currency_war.kernel.cw_env_economy import (
        _REWARD_BONUS_VARIANTS,
    )

    # 注入臂(非基线)与通道变体映射完全一致(kernel 表方向 = 环境→变体,
    # 反转后双向对齐)
    inject = {v: e for v, e in PIGGY_VARIANT_ENVS.items() if e}
    kernel_by_env = {e: v for v, e in _REWARD_BONUS_VARIANTS.items()}
    assert inject == kernel_by_env, (
        f'注入表与 C 类参数变体映射漂移: inject={inject} '
        f'kernel={dict(_REWARD_BONUS_VARIANTS)}')
    # 基线臂存在且环境为空(零污染对照的结构前提)
    assert PIGGY_VARIANT_ENVS.get('baseline') == '', (
        'baseline 臂缺失或环境非空:受控对照失去零污染基准')
    # 注入臂环境必须在扑满名单内(模块构建校验的同判据复核)
    for env in inject.values():
        assert env in PIGGY_ENV_NAMES, f'{env!r} 不在 PIGGY_ENV_NAMES'


def test_piggy_profile_build_and_unknown_variant() -> None:
    """剧本构建正反向:各变体 active_env 与表一致;未知变体显式炸错。"""
    for variant, env in PIGGY_VARIANT_ENVS.items():
        assert piggy_profile(variant).active_env == env
    with pytest.raises(ValueError):
        piggy_profile('bogus')


# ==================== 注入链 e2e(识别面回归门) ====================

_E2E_CACHE: dict[str, SimResult] = {}


def _one_game(variant: str) -> SimResult:
    """单局 sim(同次测试运行内每变体只跑一遍,多条断言共享;README 第 11 条)。"""
    if variant not in _E2E_CACHE:
        from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
        _E2E_CACHE[variant] = simulate_p1(
            42000, pool='snapshot', invest=piggy_profile(variant))
    return _E2E_CACHE[variant]


def test_piggy_injection_fires_flag_on_reward_rows() -> None:
    """注入过热环境:奖励行 piggy_reward 全 True,确认数与奖励容器一致。

    回归门 = shop 栈写点(node_kind_of 判读)失联修复:写点断链时本锁
    红恒现形(旧形态 = 全语料恒 False,P8 零观测卡点根因)。
    """
    res = _one_game('normal')
    assert res.invest_env == PIGGY_VARIANT_ENVS['normal'], (
        '注入环境未进局:invest_env 与剧本不符')
    reward_rows = [r for r in res.ledger
                   if (r.get('sim') or {}).get('node') == 'reward']
    assert reward_rows, '该局无奖励行:P1 节点序列回归,先查引擎'
    flagged = [r for r in res.ledger if r.get('piggy_reward')]
    confirmed = [r for r in flagged
                 if (r.get('sim') or {}).get('node') == 'reward']
    assert confirmed == reward_rows, (
        f'奖励行扑满标记不齐:reward={len(reward_rows)} '
        f'confirmed={len(confirmed)}')
    stats = aggregate_arm('normal', [res])
    assert stats.piggy_frames_total == len(reward_rows)
    assert stats.piggy_leak_rows == len(flagged) - len(confirmed)
    assert stats.games_with_piggy == 1


def test_piggy_baseline_arm_zero_pollution() -> None:
    """基线臂(无环境):全部账本行 piggy_reward 恒 False(零污染闸)。

    双向面补全:写点若把无环境局误标(守卫过宽),本锁红。
    """
    res = _one_game('baseline')
    assert res.invest_env == ''
    assert not any(r.get('piggy_reward') for r in res.ledger), (
        '基线局出现扑满标记:识别面环境污染')


def test_super_variant_fires_same_slot_surface() -> None:
    """严重过热变体同面点亮(变体键不分家:两变体共用识别通路)。"""
    res = _one_game('super')
    confirmed = [r for r in res.ledger
                 if r.get('piggy_reward')
                 and (r.get('sim') or {}).get('node') == 'reward']
    assert confirmed, '严重过热局零确认帧:super 变体注入链断'


# ==================== 批入口(落账本 + 报告契约) ====================


def test_run_piggy_batch_reports_and_writes_ledgers(
        tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """批入口 e2e:三臂同 seed 段,账本/manifest 落盘,报告契约齐。

    副作用隔离:SIM_RUNS_DIR 重定向 tmp_path(测试零真实 .debug 副作用;
    滚动清理桩化为 no-op,清理判据不属本锁)。
    """
    from sr_od.application.currency_war.sim import runner as sim_runner
    from sr_od.application.currency_war.sim.cw_sim_piggy import run_piggy_batch

    monkeypatch.setattr(sim_runner, 'SIM_RUNS_DIR', tmp_path)
    monkeypatch.setattr(sim_runner, '_prune_sim_runs', lambda: None)

    report = run_piggy_batch(n=2, seed_base=424242, pool='snapshot')

    # 报告契约:占用段披露 + 基线零污染闸
    assert report['seed_segment'] == [424242, 424244]
    assert report['baseline_zero_piggy'] is True
    # 跨臂同池指纹(受控对照公平闸)
    assert report['pool_fingerprint']
    # 三臂目录落盘:manifest(seeds 键 = 占用段)+ decisions 流
    for variant, dirname in report['batch_dirs'].items():
        bdir = tmp_path / dirname
        manifest = json.loads((bdir / 'manifest.json').read_text(
            encoding='utf-8'))
        assert manifest['seeds'] == [424242, 424243], (
            f'{variant} 臂 manifest seeds ≠ 占用段(种子段对账锚断)')
        assert (bdir / 'decisions.jsonl').is_file()
    # 逐臂统计:注入臂确认帧 = 奖励容器(逐行精确口径);基线臂全零
    for variant in ('normal', 'super'):
        arm = report['arms'][variant]
        assert arm['n_games'] == 2
        assert arm['piggy_frames_total'] == arm['reward_frames_total'], (
            f'{variant} 确认帧 ≠ 奖励容器:逐行精确口径回归')
        assert arm['games_with_piggy'] == 2
    baseline = report['arms']['baseline']
    assert baseline['piggy_frames_total'] == 0
    assert baseline['reward_frames_total'] > 0, (
        '基线臂无奖励行:对照面失去容器分母')
    assert baseline['piggy_leak_rows'] == 0
