"""CW 意向/方向层测试面(P1 单体系点火渐进通道 + committed 权威判定 +
局23 型帧商店线哨兵)。

两节归并自原两个主题文件(测试函数名全量保留,原文件已删):

1. 渐进配对(原 test_cw_pair_progressive.py):
   出处链 = kernel 成型线 ``cw_battle_calib._transition_formed``(四体系
   两两组合 = 成型)+ 玩法判定尺 [20](口述条目 20,登记簿已退役:过渡 = 两两组合
   配方渐进);病灶 = sim 批 ``sim_20260918_072900_000_n320`` 问题 1
   (65.6% 局终态配方锁停在单体系,板面永不向第二体系渐进)。
2. committed 权威 + 局23 哨兵(原 test_cw_migration_direction_layer.py;
   该文件系 W628 重构迁移批测试面,迁移对拍半边已随旧判定式退役,现役
   内容 = 权威序直测 + 商店线行为直测,非迁移对照):
   - D2 缺供给保守 False 直测在 p1_unarmed 一案;D3 息线 grep 测试(源码
     扫描形态)已删且不恢复,interest_floor 裸属性读禁令归 review 面;
   - 局23 哨兵复活说明:曾以「并入 w633」为名删除,并入目标经核查不存在
     = 指针失真,后按现行商店线决策面复活;息线供给恒等/不死守可辨收敛
     两面由主题文件承载(test_cw_realizable_interest_floor /
     test_cw_statefn / test_cw_session_separation / test_cw_shop_line)。
"""
from __future__ import annotations

import math
from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box,
    cw4_gs,
)

from sr_od.application.currency_war.kernel import cw_intention as intention_mod
from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
from sr_od.application.currency_war.kernel.cw_game_state import Unit
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    committed_authority,
    pair_target_comp,
    update_p1_recipe,
)
from sr_od.application.currency_war.kernel.cw_launch_admission import (
    readiness_form_ok,
)
from sr_od.application.currency_war.kernel.cw_line_switch import e_rounds
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
    CwActionCloseShopParam,
    CwActionRefreshShopParam,
    ShopCard,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
    decide_shop_action,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
    line_members,
)

# ============================================================
# 1. P1 单体系点火渐进通道(配方锁两体系组合目标)
# ============================================================


def _seed_gs(*, deployed, gold: int = 100, level: int = 5, r: int = 5,
             board: dict | None = None) -> object:
    """P1 备战场景种子(容器域直写;board 显式给,与 deployed 行一致;
    deployed = 行域 Units,槽号 1 基信息位)。"""
    return cw4_box(plane=1, round_num=r, gold=gold, level=level, hp=80,
                   shop_refresh_cost=2, node='reward',
                   front_row=list(deployed[:4]), back_row=list(deployed[4:]),
                   board=board or None)


def _ignite_dot_board(train_n: int = 0) -> tuple[list, dict]:
    """DOT 点火态(桑博+艾丝妲;DOT 支持 = 2/2 = 1.0 → 在任席在 Q 内),
    外加 train_n 个列车件(三/四月七占位;1 件 = 支持 0.5 不入 Q)。"""
    dep = [Unit(char_id='桑博', star=1),
           Unit(char_id='艾丝妲', star=1)]
    board = {'持续伤害': 2}
    for _ in range(train_n):
        dep.append(Unit(char_id='三月七', star=1 + 1))
        board['列车同行'] = board.get('列车同行', 0) + 1
    return dep, board


def test_ignited_pair_upgrades_to_estimator_argmin_second_seat() -> None:
    """测试 1+2:渐进填充按估计器 argmin 选向;点火帧 pair 升级两体系且不冻结。

    构造判别态:板上 2 DOT(点火)+ 1 列车件(进度 1/2,支持 0.5 不入
    Q,chall 空)——列车距离 1 < 仙舟距离 3,估计器应选列车。先直算两
    候选 E 作判别力守卫(表漂移时此处响亮失败,不断言巧合),再断言:
    pair 升级为两体系、第二席 = argmin 胜者、无单体系冻结(form_ok 在
    两档 AND 语义下为 False = readiness 对齐 kernel 成型线)。"""
    dep, board = _ignite_dot_board(train_n=1)
    gs = _seed_gs(deployed=dep, board=board)
    e_train = e_rounds(pair_target_comp(('持续伤害', '列车同行')), gs)
    e_xz = e_rounds(pair_target_comp(('持续伤害', '仙舟')), gs)
    assert e_train < e_xz, '判别态失守:构造的列车应劣于仙舟的 E(表漂移?)'

    ist = IntentionState()
    ist.p1_pair = ('持续伤害',)
    update_p1_recipe(gs, ist, None)
    assert len(ist.p1_pair) == 2, '点火帧必须升级两体系目标(渐进通道)'
    assert ist.p1_pair == ('持续伤害', '列车同行'), \
        f'第二席应为估计器 argmin(列车),got {ist.p1_pair}'
    assert not ist.p1_pair_frozen, '单体系点火不得触发方向冻结(病灶直测)'
    # readiness 对齐(direction b):单体系齐 ≠ form_ok(两档 AND)
    assert not readiness_form_ok(gs, pair_target_comp(ist.p1_pair))


def test_window_closed_keeps_single_pair_and_freezes(monkeypatch) -> None:
    """测试 3:渐进窗口关闭 → 候选被可行性门拒 → 保持单体系对 + 单体系冻结。

    估计器判不可达(E=inf)经 monkeypatch 注入模块级 ``e_rounds``
    (渐进填充与可行性门共用该单一源名,一 patch 两处同义)——门拒 =
    E > R_rem 的确定性构造。保持单体系冻结 = 旧行为(窗口关了没有可做
    的渐进,停手战是对的),本测试钉的是「门拒不写 pair」的保守方向。"""
    dep, board = _ignite_dot_board()
    gs = _seed_gs(deployed=dep, board=board)
    monkeypatch.setattr(intention_mod, 'e_rounds',
                        lambda *a, **k: math.inf)
    ist = IntentionState()
    ist.p1_pair = ('持续伤害',)
    update_p1_recipe(gs, ist, None)
    assert ist.p1_pair == ('持续伤害',), '门拒帧保持单体系对(不写 pair)'
    assert ist.p1_pair_frozen, '窗口关闭 → 单体系冻结(停手战,旧行为)'
    # 事件面申报:同帧先 pair_gate:deny 后被 freeze 事件覆写(现有事件
    # 先序 = freeze 后写获胜,非本批引入;门拒观测归分键/板面态两个测试)。


def test_q_challenger_fill_path_unchanged() -> None:
    """测试 4a:chall 非空支零漂移——满支持挑战者照旧从 Q 直填(无候选对、
    不走可行性门),真两体系成型照旧冻结(成型停手语义不变)。"""
    dep = [Unit(char_id='桑博', star=1), Unit(char_id='艾丝妲', star=1), Unit(char_id='三月七', star=1), Unit(char_id='丹恒·饮月', star=1)]
    board = {'持续伤害': 2, '列车同行': 2}
    gs = _seed_gs(deployed=dep, board=board)
    ist = IntentionState()
    ist.p1_pair = ('持续伤害',)
    update_p1_recipe(gs, ist, None)
    assert ist.p1_pair == ('持续伤害', '列车同行')
    assert str(ist.last_event).startswith('p1_pair:'), \
        f'Q 填充走 p1_pair 事件(非 pair_gate 路由),got {ist.last_event!r}'
    assert ist.p1_pair_frozen, '真两体系成型照旧冻结([13] 停手语义不变)'
    assert readiness_form_ok(gs, pair_target_comp(ist.p1_pair)), \
        '两档齐 = form_ok(kernel 成型线)'


def test_seele_system_never_progressive_pick() -> None:
    """测试 1(排除腿):零证据态(仅 DOT 点火,无任何第二体系资产)下,
    渐进填充不得选出希儿系(E 对它结构性失真:距离恒 0 虚假;carry
    单卡依赖),只在三桥体系内选。"""
    dep, board = _ignite_dot_board()
    gs = _seed_gs(deployed=dep, board=board)
    ist = IntentionState()
    ist.p1_pair = ('持续伤害',)
    update_p1_recipe(gs, ist, None)
    assert len(ist.p1_pair) == 2
    assert '希儿系' not in ist.p1_pair


def test_empty_window_still_empty() -> None:
    """测试 4b:空窗支零漂移——零资产帧派生对恒空。"""
    gs = _seed_gs(deployed=[])
    ist = IntentionState()
    update_p1_recipe(gs, ist, None)
    assert ist.p1_pair == (), '空窗恒空对(既有语义)'


# ============================================================
# 2. committed 权威判定直测 + 局23 型帧商店线哨兵
# ============================================================

_JU23_COMP = next(c for c in COMP_LIBRARY if c.name == '列车同行')
_JU23_STOCK_COST = 4     # 压库件卡费(档窗内;与注册表 cost 解耦)


def _sc(name: str, cost: int = _JU23_STOCK_COST, star: int = 1) -> ShopCard:
    return ShopCard(name=name, faction='仙舟罗浮', cost=cost, x=0, star=star)


def _ju23_axes(gold: int, shop: list[ShopCard] | None = None) -> dict:
    """局23 型种子轴:线成型(全员 2★ 上场,前排 4/后排按行内槽号)
    + 备战空 + P1 局中(返回 = ``cw4_gs`` kwargs,feed 配方)。"""
    members = list(line_members(_JU23_COMP))
    return {'plane': 1, 'round_num': 4, 'gold': gold, 'level': 6,
            'hp': 80, 'node': 'battle',
            'front_row': [Unit(char_id=m, star=2)
                          for i, m in enumerate(members) if i < 4],
            'back_row': [Unit(char_id=m, star=2)
                         for i, m in enumerate(members) if i >= 4],
            'shop': shop if shop is not None else []}


def _ju23_session() -> StrategySession:
    sess = StrategySession()
    state_of(sess).target_comp = _JU23_COMP
    return sess


def test_ju23_star2_stock_card_has_no_refund_backing_no_spend():
    """局23 帧 2★ 压库件:无全额可退背书 ⇒ 端到端零支出。

    stockpile_buy 与 dominance 同以 refund_full_star_ok 为背书门:
    2★ 件两条买面都不可发射,溢余滞留(不放行)而非带病买——
    断言「背书门在局23 帧端到端成立」,非单位测试复述。
    商店收缩适配 → 3.6 会话重排再翻转 → 升级转场(迭代
    2026-10-17-levelup-shop-transition T-1,design §2.1):溢余帧
    (gold 100 > 息线)前置升级检查命中且可发射 → 首动作 = 关店
    (升级转场,不置 handled 标记),店内不再发升级动作
    (升级执行位迁备战画面);端到端零支出语义保持(转场关店零花费)。
    """
    cfg = SimpleNamespace(ev_arm='full')
    sess = _ju23_session()
    act = decide_shop_action(cw4_gs(sess, **_ju23_axes(
        100, [_sc('花火', star=2)])), sess, cfg)
    assert not isinstance(act, (CwActionBuyCardParam, CwActionRefreshShopParam))
    assert isinstance(act, CwActionCloseShopParam), (
        f'溢余帧应升级转场关店: {act!r}')
    assert state_of(sess).shop_handled is None, '转场关店不置 handled 标记'
    assert state_of(sess).cw4_counters.get('levelup_transition_close') == 1


def test_ju23_full_surface_gold_never_breaks_interest_line():
    """金位不破息线(端到端复合):0-100 金全决策面逐帧走真函数。

    每个起始金位完整走一次店内访问(动作后真值回写再判,ADR-0517
    §8.1 口径):任一 CwActionBuyCardParam/CwActionRefreshShopParam 花后金 ≥ s_reserve(本帧形状
    = 50);息线下(≤50)整访问零支出(无误清);每访问都以 CwActionCloseShopParam
    收束且有界迭代(无死守环)。溢余帧(>50)经升级意图出口转场关店
    收束(2026-10-17 迭代 T-1,design §2.1——店内升级发射退役,
    升级动作不再出现在店内动作面;若复现即 else 分支响亮红)。
    恒买腾席适配(ADR-0580):店卡改用真无关件(局23杂件,非④放行集/
    registry 核心)——原探针花火 ∈ TRANSITION_PACK carry,未锁双轨
    P1 帧会被 ④转线放行臂在息线下买入(1★ 全额退 = 可逆资产,裁定
    408② 的有意取舍);「息线下零支出」不变式对④放行件域已被裁定
    取代,④例外语义由 test_cw_locked_buy_membership_split 重推测试
    承载,本测试在真无关件域保持。"""
    cfg = SimpleNamespace(ev_arm='full')
    # 扫面收窄(审计判决):连续 0..100 → 息线两侧边界 + 两端代表点
    for gold0 in (0, 49, 50, 51, 100):
        st = _ju23_axes(gold0, [_sc('局23杂件')])
        sess = _ju23_session()
        for _ in range(15):
            act = decide_shop_action(cw4_gs(sess, **st), sess, cfg)
            if isinstance(act, CwActionBuyCardParam):
                cost = act.card.cost if act.card.cost else 3
                if gold0 <= 50:
                    assert st['gold'] - cost >= 50, (gold0, st['gold'], cost)
                st['gold'] -= cost
                st['shop'] = [c for c in st['shop'] if c is not act.card]
            elif isinstance(act, CwActionRefreshShopParam):
                if gold0 <= 50:
                    assert st['gold'] - act.cost >= 50, (gold0, st['gold'])
                st['gold'] -= act.cost
            elif isinstance(act, CwActionCloseShopParam):
                break
            else:
                raise AssertionError(f'局23 帧意外动作 {act!r} @ {gold0} 金')
        else:
            raise AssertionError(f'决策不收敛(死守嫌疑)@ {gold0} 金')
        if gold0 <= 50:
            assert st['gold'] == gold0, (gold0, st['gold'])


def _gs_state(plane: int, round_num: int):
    """容器单例构造(真值语义 = 节点 plane/round)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        ChannelSig,
        GameState,
        NodeKey,
    )
    gs = GameState(schema_version=1)
    gs.observe(gs.node, NodeKey(plane=plane, round_num=round_num,
                                kind='普通战斗'),
               sig=ChannelSig(family='obs', actor='cw_observation',
                              mode='read'))
    return gs


@pytest.mark.parametrize('case', [
    'p1_unarmed_conservative', 'locked_committed', 'p1_pair_committed',
    'p2_unlocked_dual_track'],
    ids=['p1-unarmed-conservative', 'locked-committed', 'p1-pair-committed',
         'p2-unlocked-dual-track'])
def test_committed_authority_semantics(case: str):
    """committed 权威判定直测(方向层单一派生源;批 3.7 候选-锁定制
    语义重锚)。

    权威序任一成立即 True:①``st.target_comp`` 非空(锁定线槽——定型
    语义 = 锁定线非空,line_and_upgrade §1.6 判定源迁移)②ist.p1_pair
    非空(P1 配方锁,保留项);缺供给(state/session 缺、未锁线)= 保守
    False——True=已定型=激进侧,攒息门/双轨买门全开(供给点清单 D2)。
    原「plane≥2 恒定型」支已退役(P2 时点兜底锁定替代)——P2 入口至
    兜底锁帧之间的短窗 committed=False(双轨期口径,§1.6 行为差申报,
    p2_unlocked_dual_track 案校验此短窗)。"""
    if case == 'p1_unarmed_conservative':
        assert committed_authority(_gs_state(1, 3), StrategySession()) is False
        return
    if case == 'p2_unlocked_dual_track':
        # P2 未锁帧(兜底锁未触发):committed=False——双轨期口径
        assert committed_authority(_gs_state(2, 1), StrategySession()) is False
        return
    sess = StrategySession()
    if case == 'locked_committed':
        from sr_od.application.currency_war.kernel.cw_comps import get_comp
        state_of(sess).target_comp = get_comp('万敌单C')   # 锁定线槽直种
    else:   # p1_pair_committed
        state_of(sess).v3_intention = IntentionState(p1_pair=('万敌燃血',))
    assert committed_authority(_gs_state(1, 8), sess) is True
