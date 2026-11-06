"""sim 位面 3 胜利终局与战争边疆对拍 · 测试面(cw_sim_backend)。

设计依据 = invest-effects-calc 迭代 designs/T-18-zhanzheng-bianjiang.md
§9.2/§9.3(用户裁定 2026-10-15「过了位面3就是胜利」):推进超出位面 3
(3-7 boss 结算存活)= 胜利终局(披露键 `run_complete`);hp 归零 =
败局语义不变。测试面:

- 胜利终局:默认局全链走完位面 3(seed 37 探针锚)→ done ∧
  `DISCLOSURE_RUN_COMPLETE` 披露 ∧ 退役键 `DISCLOSURE_P3_UNOBSERVED`
  不再现 ∧ 终点 (3,7) ∧ hp > 0;
- 败局:结算恒败桩 → hp 归零死亡分支 → done ∧ 无 run_complete(胜负
  判别单一源 = 披露集);
- 对拍(设计裁决点 2 主锁):战争边疆局 vs 默认局同 seed——P1/P2 节点
  kind 与 hp 轨迹逐值同、P3 仅 3-1/3-2/3-4 分化为遭遇、双方零
  `DECL_SCREEN_DRIFT` 且同达胜利终局。结构依据:sim 结算流键 =
  ``(位面, 轮)`` 维度与节点 kind 无关(``settle_battle`` 不读 kind),
  故替换不改 hp 轨迹——任何人给战争边疆误装域内通道(经济/发放)或
  P3 序列/替换规则漂移,本组对拍先红。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_pick_encounter_param,
    report_action_pick_invest_env_param,
    report_action_pick_invest_strategy_param,
    report_action_pick_megastar_param,
    report_action_pick_planner_param,
    report_action_pick_supply_param,
    report_action_start_battle_param,
)
from sr_od.application.currency_war.kernel.cw_action_report.close_shop import (
    report_action_close_shop_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    report_node_advance,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionCloseShopParam,
)
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    DECL_SCREEN_DRIFT,
    DISCLOSURE_P3_UNOBSERVED,
    DISCLOSURE_RUN_COMPLETE,
    SCREEN_BRIEFING,
    SCREEN_ENCOUNTER,
    SCREEN_INVEST_ENV,
    SCREEN_INVEST_STRATEGY,
    SCREEN_PREP,
    SCREEN_SETTLE,
    SCREEN_SHOP,
    SCREEN_SUPPLY,
    SimBackend,
    install_backend,
    stream_rng,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_base import ChannelSig
from sr_od.application.currency_war.sim.cw_sim_battle import (
    SIM_BATTLE_FACE,
    BattleOutcome,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_SIG = ChannelSig(family='logic_action', actor='T18WinTest', mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='T18WinTest')

#: 对拍定向种子(探针实测:两局同达胜利终局,hp=1 走满 23 节点)。
_AB_SEED: int = 37


def _drive_step(b: SimBackend, rng_seed: int) -> None:
    """单步驱动(backend 直驱;按呈现屏分派到对应真实写端,动作 op 同形
    = 上报 + 声明喂入;先例 = test_sim_backend._drive_step)。
    2026-10-29 流程模型对齐:补给确认零推进(选完关模态回备战自动弹店,
    节点推进归出战动作 supply_finish);商店档 = 关店动作单轨回备战。"""
    screen = b.screen_identity()
    gs = b.gs
    if screen == SCREEN_SUPPLY:
        opts = gs.supply.value.options
        gs.write_logic(gs.chosen_supply,
                       ('', (opts[0].equip, *opts[0].extra_equips)),
                       produced_by='Test', evidence='t:chosen', sig=_SIG)
        out = report_action_pick_supply_param(
            gs, SimpleNamespace(idx=0, char_name='', norm_item=opts[0].equip),
            _SIG)
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == SCREEN_SHOP:
        out = report_action_close_shop_param(gs, CwActionCloseShopParam(),
                                             _SIG)
        assert out.applied, out.reason
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == SCREEN_INVEST_STRATEGY:
        opts = gs.invest_strategy_opts.value
        out = report_action_pick_invest_strategy_param(
            gs, SimpleNamespace(norm_name=opts[0]), _SIG,
            rng=stream_rng(rng_seed, 'M11/pick/part'),
            session=SimpleNamespace())
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == SCREEN_SETTLE:
        out = report_node_advance(gs, trigger='settle_confirm')
        assert out.applied, out.reason
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == '货币战争-位面过渡':
        b._handle_click_source('货币战争-位面过渡', '区域-空白点击')
    elif screen == '货币战争-BOSS简报':
        b._handle_click_source('货币战争-BOSS简报', '区域-空白点击')
    elif screen == SCREEN_ENCOUNTER:
        out = report_action_pick_encounter_param(
            gs, SimpleNamespace(idx=0), _SIG)
        assert out.applied
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == '货币战争-盛会之星':
        out = report_action_pick_megastar_param(gs, SimpleNamespace(), _SIG)
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == '货币战争-银狼升星':
        out = report_action_pick_planner_param(gs, SimpleNamespace(), _SIG)
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == SCREEN_PREP:
        out = report_action_start_battle_param(gs, SimpleNamespace(), _SIG)
        cw_sim_ports.declare_world(out.world_decl)
    else:
        raise AssertionError(f'未知呈现屏 {screen}')


def _run_full(seed: int, env_name: str = '') -> dict:
    """整局驱动到终局(装配缝完整收尾:返回终局快照 dict,后端在退出前
    必卸——进程内单装配,对拍连跑两局不撞装配槽)。"""
    cfg = RunConfig(selected_difficulty='A8', enemy_difficulty=108,
                    env_present=bool(env_name))
    b = SimBackend(seed=seed, cfg=cfg)
    install_backend(b)
    kinds: dict[tuple[int, int], str] = {}
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        if env_name:
            assert b.screen_identity() == SCREEN_INVEST_ENV
            b.gs.observe(b.gs.invest_env_opts,
                         ('头彩', env_name, '轮岗'),
                         evidence='test:synthesized', sig=_SIG_OBS)
            out = report_action_pick_invest_env_param(
                b.gs, SimpleNamespace(idx=1), _SIG)
            assert out.applied
            cw_sim_ports.declare_world(out.world_decl)
        b._maybe_finish_wait()
        for _ in range(4096):
            if b.done:
                break
            node = b.gs.node.value
            if node is not None:
                kinds[(node.plane, node.round_num)] = node.kind
            _drive_step(b, seed)
        assert b.done, '4096 步内未收尾(流程异常)'
        res = b.result()
        node = b.gs.node.value
        return {
            'end': (node.plane, node.round_num),
            'hp': res.final_hp,
            'hp_trail': res.hp_trail,
            'kinds': kinds,
            'win': DISCLOSURE_RUN_COMPLETE in res.unmodeled,
            'floor_used': bool(b.gs.hp_floor_triggered.value),
            'drift': b.disclosures.get(DECL_SCREEN_DRIFT),
            'retired_p3_key': DISCLOSURE_P3_UNOBSERVED in b.disclosures,
        }
    finally:
        uninstall_backend()


def test_full_walk_p3_survive_is_win_terminal() -> None:
    """胜利终局:默认局走完位面 3 = done + run_complete 披露;退役键
    p3_unobserved 不再现;终点 = 3-7 boss。"""
    r = _run_full(_AB_SEED)
    assert r['win'], '胜利终局披露'
    assert not r['retired_p3_key'], 'p3_unobserved 已退役不再发射'
    assert r['end'] == (3, 7), '默认局终点 = P3 r7 boss'
    assert r['hp'] > 0, '存活终局 hp > 0'
    assert r['kinds'][(3, 1)] == 'battle' and r['kinds'][(3, 7)] == 'boss', \
        '默认 P3 序列(战斗开场/boss 收尾)'
    assert r['drift'] is None, r['drift']


def test_hp_zero_death_is_loss_without_win_disclosure(monkeypatch) -> None:
    """败局:结算恒败桩 → hp 归零死亡分支收尾,无 run_complete(胜负
    判别单一源在披露集;hp 归零败局语义不变)。"""
    import sr_od.application.currency_war.sim.cw_sim_backend as sb

    def _always_lose(rng, *, plane: int, round_num: int) -> BattleOutcome:
        return BattleOutcome(won=False, progress=0.5, base_damage=None,
                             progress_damage=None, hp_delta=-100,
                             face=SIM_BATTLE_FACE)

    monkeypatch.setattr(sb, 'settle_battle', _always_lose)
    r = _run_full(_AB_SEED)
    assert r['hp'] == 0, 'hp 归零死亡'
    assert not r['win'], '死亡分支不经胜利分支'
    assert r['floor_used'], '保底已用后归零'


def test_war_frontier_vs_default_ab_p3_kind_divergence_only() -> None:
    """战争边疆 vs 默认局对拍(主锁):P1/P2 节点 kind 逐值同、hp 轨迹
    全程逐值同(结算流键与 kind 无关);P3 仅 3-1/3-2/3-4 分化为遭遇;
    两局同达胜利终局且零 DECL_SCREEN_DRIFT。"""
    default_r = _run_full(_AB_SEED)
    war_r = _run_full(_AB_SEED, env_name='战争边疆')
    for pos in sorted(set(default_r['kinds']) | set(war_r['kinds'])):
        if pos[0] <= 2:
            assert default_r['kinds'][pos] == war_r['kinds'][pos], \
                f'P1/P2 逐值同违反于 {pos}'
    for pos in ((3, 1), (3, 2), (3, 4)):
        assert war_r['kinds'][pos] == 'encounter', f'P3 替换槽 {pos}'
        assert default_r['kinds'][pos] == 'battle'
    for pos in ((3, 3), (3, 5), (3, 6), (3, 7)):
        assert default_r['kinds'][pos] == war_r['kinds'][pos], \
            f'替换域外槽逐值同 {pos}'
    assert default_r['hp_trail'] == war_r['hp_trail'], \
        'hp 轨迹全程逐值同(替换不改结算流)'
    assert default_r['win'] and war_r['win'], '两局同达胜利终局'
    assert default_r['drift'] is None
    assert war_r['drift'] is None, war_r['drift']
