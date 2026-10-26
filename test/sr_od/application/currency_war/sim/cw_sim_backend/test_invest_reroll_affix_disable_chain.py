"""sim 全链敌后破坏追加获得腿测试(镜像 src 主断言对象 = kernel 删除腿
经 sim 后端 T-14 蓝海追加链全链;按流程级测试落位本目录,引擎驱动
助手 import 自 sim/test_sim_backend.py〔在册超限拆分债文件,禁追加,只
import 复用不改;先例 = 本目录 test_env_deploy_lock_sim_chain.py〕)。

测试面依据 = T-45 敌后破坏设计(.debug/progress/2026-09-23-invest-effects-
calc/designs/T-45-dihou-pohuai.md)§1 条 6 + §2.3 + §4 锁 7(限 sim 端,
attack-v2 S1):sim 蓝海追加获得敌后破坏 → 世界掷骰二次入链
(cw_sim_backend._on_invest_picked 原语复用)→ 删除腿自动触发一次——
词缀名单长度 -1、来源 logic_rand;HP 词缀回调同步重算(write_prior,
开局 62 → 删「开局不利」后 82)。live 端无二次入链(零删除腿触发),
锁面不覆盖 live 追加态(设计披露键 6)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_pick_invest_env_param,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    ENV_REROLL_NAMES,
    INVESTMENT_ENVS,
)
from sr_od.application.currency_war.kernel.cw_opening_hp import (
    OPENING_HP_BASE,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SCREEN_INVEST_ENV,
    SCREEN_PREP,
    SimBackend,
    install_backend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_ports import declare_world
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig
from sr_od.application.currency_war.sim.cw_sim_streams import stream_rng


def _reroll_seed_hitting(target: str) -> int:
    """追加腿世界掷骰命中目标的 seed(现算单一来源:同引擎公式
    `pool[stream_rng(seed, 'M02/env-reroll').randrange(len(pool))]`,
    探针 = 首个命中 seed,不手抄魔数)。"""
    pool = sorted(n for n in INVESTMENT_ENVS if n not in ENV_REROLL_NAMES)
    assert target in pool, f'{target} 不在追加池(注册表漂移?)'
    return next(s for s in range(1000)
                if pool[stream_rng(s, 'M02/env-reroll').randrange(len(pool))]
                == target)


def _pick_reroll_env(seed: int) -> SimBackend:
    """开局选蓝海的装配后端(调用方负责 uninstall;追加腿由后端世界
    掷骰二次入链,seed 经现算钉住卷中敌后破坏)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True,
        enemy_affixes=('开局不利',)))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    assert b.screen_identity() == SCREEN_INVEST_ENV
    from sr_od.application.currency_war.kernel.cw_game_state import (
        ChannelSig,
    )
    sig = ChannelSig(family='logic_action', actor='SimBackendTest',
                     mode='compute')
    b.gs.write_logic(b.gs.invest_env_opts,
                     ['蓝海', '轮岗', '头彩'],
                     produced_by='Test', evidence='t:opts', sig=sig)
    out = report_action_pick_invest_env_param(
        b.gs, SimpleNamespace(idx=0), sig)
    assert out.applied
    declare_world(out.world_decl)
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP, '选卡确认交回备战'
    return b


def test_reroll_affix_disable_deletion_leg_fires_once(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """追加链触发一次(T-45 设计 §4 锁 7 sim 端):选蓝海 → 世界掷骰
    卷中敌后破坏 → 二次入链删除腿自动触发——词缀名单 ('开局不利',) →
    [](删尽态)、来源 logic_rand(模型猜测口径,sim 内下游直读零消费门);
    HP 词缀回调同步重算:开局 62(开局不利 −20)→ write_prior 82,
    与词缀现值一致(设计 §2.3 sim 缺口随回调机制消解)。"""
    seed = _reroll_seed_hitting('敌后破坏')
    b = _pick_reroll_env(seed)
    try:
        gs = b.gs
        assert gs.active_env.value == '敌后破坏', '追加腿卷中名落 active_env'
        assert gs.enemy_affixes.value == [], '删除腿触发:名单删尽'
        assert gs.enemy_affixes.source == 'logic_rand', '删除写 = 随机态'
        assert gs.hp.value == OPENING_HP_BASE, \
            'HP 回调重算 = 无「开局不利」基线(62 → 82)'
        assert gs.hp.source == 'prior', '重算走 write_prior 通道'
    finally:
        uninstall_backend()


def test_reroll_same_seed_replay_deterministic(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """同 seed 重放逐位确定(追加腿世界掷骰 = 流键 rng 世界真值;删除腿
    采样走动作腿注入槽 = 同一确定性链):双跑词缀终态/HP 逐位一致。"""

    def _run() -> tuple[list[str] | None, str, int | None, str]:
        b = _pick_reroll_env(_reroll_seed_hitting('敌后破坏'))
        try:
            gs = b.gs
            return (list(gs.enemy_affixes.value or []),
                    gs.enemy_affixes.source,
                    gs.hp.value, gs.hp.source)
        finally:
            uninstall_backend()

    assert _run() == _run(), '同 seed 重放逐位确定'
