"""批3 通道建模 + 外循环分支序锁(T-120 sim 重设计 批 3 验收载体)。

出处 = T-120 方案 v2(``.debug/temp/currency_war/_archive_20260908/
t120_sim_redesign/方案.md``)§6.2 批 3 行 + 批 2 验收(T-120-batch2-r1.md)
申报的发射面外循环分支序(战斗等待/位面过渡/pick 族)与裂口①概率条
建模义务(批 1 落地审 §2.1①「归批 3 概率条建模」);批 3 任务书 =
`.debug/temp/currency_war/T-120-batch3-交付报告.md` 同目录任务书面。

锁的语义(测试纪律 7 自检):

- **典籍通道锁** = 获取(投资策略「秘密典籍」发放:金随件 =
  ``economy_effect_of`` 单一源直读,占备战席 1 槽)→ 登记(obs.tomes
  真值直出 → 真 prep 决策环发射 OpenTome)→ 消耗(开典籍腾席 + 星徽
  四选一浮层 → 真 0i op ``CwScreenBookcard`` 选卡 → 星徽入装备库存,
  ``board_state.chosen_tome`` 生产写点在环)。红 = 通道断链/旁路写。
- **装备进阶通道锁** = 供给节点真 op(``CwScreenSupplyNode``)选装
  落账(engine ``EQUIP_GRANT`` 校准族直调为发放单一源)+ 穿着即合成
  (同角色两基础件按 ``cw_synthesis`` 配方图谱自动合成为进阶,不耗金;
  机制原文 = research/equipment_mechanics.md §1)。红 = 发放第二源/
  合成规则缺失。
- **外循环分支序锁** = 批 2 申报归批 3 的分支(0i 星徽秘典/0e1 补给/
  战斗窗/0q 位面过渡)在假环境逐分支经真画面 op 可达,分发序遵守
  outer_loop.md §2.2 序位纪律(浮层先于备战双锚);位面 1→2 过渡的
  进场继承与 sim-wiring P2 段注记一致(hp/gold/board/bench/deployed/
  equips 原样带过)。红 = 分支不可达 / 序位倒置 / 继承语义漂移。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from test.conftest import SrTestContext
from test.harness.fixture_controller import enter_running_state, reset_running_state

_SEED: int = 20260911


# ============================================================ 典籍通道


def test_tome_channel_acquisition_registration_consumption(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path) -> None:
    """典籍获取→登记→消耗全链(机制原文:投资策略「秘密典籍」给红金
    典籍道具占备战席 1 槽;点开腾席 + 星徽四选一由 loop 0i 接管选卡)。

    获取 = 金随件入账( EconomyEffect.instant_gold 单一源直读,8/12)+
    典籍占席;登记 = obs.tomes 真值直出 → 真 prep 决策环发射 OpenTome
    (entry 编排 prep_tome 臂);消耗 = OpenTome 腾席 + 星徽四选一浮层
    → 真 CwScreenBookcard 选卡 → 星徽入 state.equips(owned += 星徽)
    + board_state.chosen_tome 生产写点在环。
    """
    from fixtures.cw_harness import fake_p1_run

    enter_running_state(test_context)
    try:
        with fake_p1_run(test_context, monkeypatch, tmp_path, _SEED,
                         node_sequence=['battle'], initial_gold=10,
                         archive_dir_name='tome_channel') as run:
            m = run.match
            # —— 获取:金随件 + 占席 ——
            gold_pre = m.state.gold
            slot = m.spawn_tome('秘密典籍')
            assert slot is not None, '典籍未落席(获取链断)'
            from sr_od.application.currency_war.kernel.cw_investments import (
                economy_effect_of,
            )
            assert m.state.gold == gold_pre + economy_effect_of(
                '秘密典籍').instant_gold, (
                '典籍获取金未按 EconomyEffect 单一源入账')
            tome_slot = m.tomes[0]
            # —— 登记:观察面直出 → 真 prep 环发射 OpenTome ——
            from fixtures.cw_fake_game.fake_ports import FakeCwObserver
            prep_obs = FakeCwObserver(m).observe_prep(None, 'prep_clean').prep
            assert [t[0] for t in prep_obs.tomes] == [tome_slot], (
                '典籍未入观察面(登记链断)')
            phase = run.run_prep_phase(monkeypatch)
            tome_lands = [e for e in run.prep_audit
                          if e['action'].startswith('OpenTome')
                          and e['applied']]
            assert tome_lands, (
                f'真 prep 决策环未发射 OpenTome(prep_tome 臂断;'
                f'落地序列 {[e["action"] for e in run.prep_audit]})')
            assert m.tomes == [], '开典籍后仍占观察面(腾席规则缺)'
            assert m.top_overlay('star_tome') is not None, (
                '开典籍未压星徽四选一浮层')
            assert phase['visits'] >= 1
            # —— 消耗:真 0i op 选卡 → 星徽入库存 + 生产写点 ——
            equips_pre = list(m.state.equips)
            run.run_star_tome_pick(monkeypatch)
            assert m.top_overlay('star_tome') is None, '选卡后浮层未消'
            assert len(m.state.equips) == len(equips_pre) + 1, (
                '星徽未入装备库存(owned += 星徽 断)')
            picked = (set(m.state.equips) - set(equips_pre)).pop()
            assert picked.endswith('星徽'), f'消耗产物非星徽件: {picked}'
            # 生产写点:GameState chosen_tome(CwScreenBookcard 写端)
            from sr_od.application.currency_war.kernel.cw_game_state import (
                board_state_of,
            )
            bs = board_state_of(run.cw_match.session)
            assert bs.chosen_tome.value, (
                'chosen_tome 生产写点未落(CwScreenBookcard 写端断)')
    finally:
        reset_running_state(test_context, test_context.cw_match)


# ============================================================ 装备进阶通道


def test_supply_node_op_lands_equipment_grant(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path) -> None:
    """供给节点真 op 选装落账(装备进阶通道的获取端)。

    真 ``CwScreenSupplyNode``(decide_supply 真策略决策 → 点卡+确认 →
    出口验真)驱动;选中装备入 state.equips(基础件池,engine 供给校准
    段同构);追加件常量 = engine ``EQUIP_GRANT`` 校准族直调(import
    身份断言,禁第二源)。
    """
    from fixtures.cw_harness import fake_p1_run

    enter_running_state(test_context)
    try:
        with fake_p1_run(test_context, monkeypatch, tmp_path, _SEED,
                         node_sequence=['supply'], initial_gold=10,
                         archive_dir_name='supply_channel') as run:
            m = run.match
            equips_pre = list(m.state.equips)
            disp = run.run_round_branch_order(monkeypatch)
            # 分发序:补给节点直接进补给屏(outer_loop §3 备战分支第 7 步
            # 分流语义:补给轮不驻留备战交互),0e1 处理后本节点收口。
            assert disp['dispatch'][0] == '0e1_supply', (
                f'补给节点分发序非 0e1 先行: {disp["dispatch"]}')
            assert len(m.state.equips) >= len(equips_pre) + 1, (
                f'供给选装未落账({equips_pre} → {m.state.equips})')
            granted = (set(m.state.equips) - set(equips_pre)).pop()
            # 选项池 = 基础件池(engine 供给校准段:基础件 8 名均匀池)
            from sr_od.application.currency_war.data.cw_synthesis import (
                RESERVED_COMPONENTS,
            )
            assert granted in RESERVED_COMPONENTS, (
                f'供给发放偏离基础件池: {granted}')
            # 追加件常量单一源 = engine EQUIP_GRANT 校准族直调
            import fixtures.cw_fake_game.rules as rules

            from sr_od.application.currency_war.sim import engine_p1
            assert rules.EQUIP_GRANT_BONUS_P is \
                engine_p1.EQUIP_GRANT_BONUS_P, '追加件概率第二源'
            assert rules.EQUIP_GRANT_BONUS_ADV_SHARE is \
                engine_p1.EQUIP_GRANT_BONUS_ADV_SHARE, '追加件进阶占比第二源'
            assert m.top_overlay('star_tome') is None
    finally:
        reset_running_state(test_context, test_context.cw_match)


def test_wear_trigger_synthesis_advances_equipment() -> None:
    """穿着即合成:同角色两基础件按配方图谱自动合成进阶(不耗金)。

    机制原文 = research/equipment_mechanics.md §1(穿着触发:两件简易
    穿到同一角色身上游戏自动合成,无确认无日志,合成不耗金;合成落点 =
    产物占最左简易槽)。假游戏在穿戴落账后执行同规则;配方判定单一源 =
    ``cw_synthesis.synthesize_target``/``self_advance``。
    """
    from fixtures.cw_fake_game.fake_match import FakeMatch

    from sr_od.application.currency_war.data.cw_synthesis import (
        SYNTHESIS_BASES,
        synthesize_target,
    )
    from sr_od.application.currency_war.kernel.cw_vocab import (
        BenchChar,
    )

    m = FakeMatch(seed=43, node_sequence=['battle'])
    m.state.bench = [None] * 9
    m.state.deployed = [None] * 10
    # 场景:前排角色已穿基础件 a(商店角色自带装备通道,机制 §3);
    # 库存有可配对基础件 b → 有意配对穿戴(生产分配器例外①「想要的
    # 配对,core 上穿着合成=快路径」ADR-0391;comp=None 的保守分配会
    # 拦配对——那是 bot 纪律,非游戏规则,游戏规则 = 配对即合成)。
    # deployed 元素 = BenchChar(deployed 容器无独立类型;
    # 站位 = position_pref)。
    a = sorted(SYNTHESIS_BASES)[0]
    cross = next((b for b in sorted(SYNTHESIS_BASES)
                  if b != a and synthesize_target(a, b) is not None), None)
    assert cross is not None, '场景前置:未找到可交叉配对的基础件'
    expected = synthesize_target(a, cross)
    d = BenchChar(slot=1, char_id='希儿', faction='量子',
                  position_pref='front')
    d.equips = [a]
    m.state.deployed[0] = d
    m.state.equips = [cross]
    comp = SimpleNamespace(key_equips=[expected], core_chars=['希儿'],
                           plaza_carry='希儿')
    gold_pre = m.state.gold
    m.wear_inventory_equips(comp)
    assert d.equips == [expected], (
        f'穿着即合成未生效: {d.equips}(期望 {expected})')
    assert cross not in m.state.equips, '合成组件未出库存'
    assert m.state.gold == gold_pre, '合成耗金(机制原文:合成不耗金)'


# ============================================================ 外循环分支序


def test_outer_loop_branch_order_reaches_deferred_branches(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path) -> None:
    """批 2 申报归批 3 的分支逐支可达且序位合规(outer_loop §2.2)。

    剧本 = prep(battle 节点,注入典籍)→ supply 节点 → 日程耗尽位面
    过渡。判据:①0i 星徽秘典浮层在 prep 访问前接管(浮层先于备战双锚);
    ②0e1 补给真 op 消费;③战斗窗分支在发射后驱动(等结算→结算处理→
    白名单完成);④0q 位面过渡真 op 消费;⑤位面 1→2 进场继承与
    sim-wiring P2 段注记一致。
    """
    from fixtures.cw_harness import fake_p1_run

    enter_running_state(test_context)
    try:
        with fake_p1_run(test_context, monkeypatch, tmp_path, _SEED,
                         node_sequence=['battle', 'supply'],
                         initial_gold=30,
                         archive_dir_name='branch_order') as run:
            m = run.match
            m.spawn_tome('秘密典籍')
            disp = run.run_round_branch_order(monkeypatch)
            dd = disp['dispatch']
            # 典籍获取于备战访问内发射 OpenTome(入口 prep 段),浮层压栈
            # 后备战环让位 → 0i 接管(§2.2:浮层分支先于备战双锚,发生在
            # 下一次循环重判;环让位重入契约 §3-12),0i 消费后备战恢复段
            # 才继续 → 发射 → 战斗窗。
            assert dd[0] == '1_prep', f'备战分支未先行:{dd}'
            assert '0i_star_tome' in dd, f'星徽秘典浮层分支未驱动:{dd}'
            assert dd.index('0i_star_tome') < len(dd) - 1, (
                f'0i 后无恢复段(序位断裂):{dd}')
            assert '1_prep' in dd, '备战分支未驱动'
            assert '2_battle_window' in dd, (
                '战斗窗分支未驱动(批 2 申报归批 3 面未落位)')
            assert dd[-1] == '2_battle_window', f'回合尾非战斗窗:{dd}'
            assert disp['launched'], '发射未发生(战斗窗前置缺)'
            assert '0e1_supply' not in dd, '战斗节点误入补给分支'
            # ②发射后战斗窗分支(等结算→结算处理→白名单完成);③结算处理推进节点
            # ④0e1(第二节点)
            disp2 = run.run_round_branch_order(monkeypatch)
            assert disp2['dispatch'][0] == '0e1_supply', (
                f'补给节点分发序非 0e1: {disp2["dispatch"]}')
            # ⑤日程耗尽 → 0q 位面过渡 → P2 进场继承
            hp_pre = m.state.hp
            gold_pre = m.state.gold
            bench_pre = [b.slot for b in m.state.bench if b is not None]
            disp3 = run.run_round_branch_order(monkeypatch)
            assert '0q_plane_transition' in disp3['dispatch'], (
                f'位面过渡分支未驱动:{disp3["dispatch"]}')
            assert m.state.plane == 2, f'位面未推进:{m.state.plane}'
            assert m.state.hp == hp_pre and m.state.gold == gold_pre, (
                'P2 进场继承漂移(sim-wiring P2 段:hp/gold 原样带过)')
            assert [b.slot for b in m.state.bench if b is not None] \
                == bench_pre, 'P2 进场 bench 未继承'
            assert m.state.round_num == 1, 'P2 轮次未按位面重置'
    finally:
        reset_running_state(test_context, test_context.cw_match)
