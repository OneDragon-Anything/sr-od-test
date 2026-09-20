"""T-52 · P1 单体系点火渐进通道锁面(配方锁两体系组合目标)。

出处链(锁的设计出处,锁存在性纪律):
- kernel 成型线 = ``cw_battle_calib._transition_formed``(四体系两两组合
  = 成型,「单个体系点火不等于成型」);
- 玩法判定尺 [20](user_playstyle:过渡=两两组合配方渐进,变体按来牌选;
  transition_combos 定义行);
- 病灶 = sim 批 ``sim_20260918_072900_000_n320`` 问题 1(65.6% 局终态
  配方锁停在单体系;单体系 2 人即 form_ok=true → [13] 停手提前 → 板面
  永不向第二体系渐进,严格口径 ④ 22.8% vs 宽松 85.6%;个案 s98054
  R1 点火后 8 轮零消费动作死时 165 金)。

锁的语义(四条,锁意图不锁牌面):
1. 渐进填充选向 = kernel ``e_rounds`` 单一估计器 argmin(在店货架/概率峰/
   板面进度三判据的承载式,零新常数);构造判别态断言选向随证据移动;
2. 端到端:单体系点火帧 pair 升级两体系、**不冻结**(病灶直锁:点火
   不再休眠;readiness 随两档 AND 自动对齐 kernel 成型线);
3. 窗口关闭(估计器判不可达)→ 渐进候选被既有可行性门拒 → 保持单体系
   对且单体系冻结(= 旧行为;[13] 停手只在无可达渐进时成立);
4. 既有支零漂移:Q 内满支持挑战者填充(chall 非空)不产候选对、照旧
   直写;真两体系成型帧照旧冻结(成型停手语义不变)。

希儿系不参选渐进填充的依据见 ``_progressive_second_seat`` docstring
(E 估计器对它结构性失真 + carry 单卡依赖),由测试 1 的排除断言承载。
"""
from __future__ import annotations

import math

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box,
)

from sr_od.application.currency_war.kernel import cw_intention as intention_mod
from sr_od.application.currency_war.kernel.cw_game_state import Unit
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    pair_target_comp,
    update_intention,
)
from sr_od.application.currency_war.kernel.cw_launch_admission import (
    readiness_form_ok,
)
from sr_od.application.currency_war.kernel.cw_line_switch import e_rounds


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
    dep = [Unit(char_id='桑博', star=1, slot=1),
           Unit(char_id='艾丝妲', star=1, slot=2)]
    board = {'持续伤害': 2}
    for _ in range(train_n):
        dep.append(Unit(char_id='三月七', star=1, slot=len(dep) + 1))
        board['列车同行'] = board.get('列车同行', 0) + 1
    return dep, board


def test_ignited_pair_upgrades_to_estimator_argmin_second_seat() -> None:
    """锁 1+2:渐进填充按估计器 argmin 选向;点火帧 pair 升级两体系且不冻结。

    构造判别态:板上 2 DOT(点火)+ 1 列车件(进度 1/2,支持 0.5 不入
    Q,chall 空)——列车距离 1 < 仙舟距离 3,估计器应选列车。先直算两
    候选 E 作判别力守卫(表漂移时此处响亮失败,不锁巧合),再断言:
    pair 升级为两体系、第二席 = argmin 胜者、无单体系冻结(form_ok 在
    两档 AND 语义下为 False = readiness 对齐 kernel 成型线)。"""
    dep, board = _ignite_dot_board(train_n=1)
    gs = _seed_gs(deployed=dep, board=board)
    e_train = e_rounds(pair_target_comp(('持续伤害', '列车同行')), gs)
    e_xz = e_rounds(pair_target_comp(('持续伤害', '仙舟')), gs)
    assert e_train < e_xz, '判别态失守:构造的列车应劣于仙舟的 E(表漂移?)'

    ist = IntentionState()
    ist.p1_pair = ('持续伤害',)
    update_intention(gs, ist, None)
    assert len(ist.p1_pair) == 2, '点火帧必须升级两体系目标(渐进通道)'
    assert ist.p1_pair == ('持续伤害', '列车同行'), \
        f'第二席应为估计器 argmin(列车),got {ist.p1_pair}'
    assert not ist.p1_pair_frozen, '单体系点火不得触发方向冻结(病灶直锁)'
    # readiness 对齐(direction b):单体系齐 ≠ form_ok(两档 AND)
    assert not readiness_form_ok(gs, pair_target_comp(ist.p1_pair))


def test_window_closed_keeps_single_pair_and_freezes(monkeypatch) -> None:
    """锁 3:渐进窗口关闭 → 候选被可行性门拒 → 保持单体系对 + 单体系冻结。

    估计器判不可达(E=inf)经 monkeypatch 注入模块级 ``e_rounds``
    (渐进填充与可行性门共用该单一源名,一 patch 两处同义)——门拒 =
    E > R_rem 的确定性构造。保持单体系冻结 = 旧行为(窗口关了没有可做
    的渐进,停手战是对的),本锁钉的是「门拒不写 pair」的保守方向。"""
    dep, board = _ignite_dot_board()
    gs = _seed_gs(deployed=dep, board=board)
    monkeypatch.setattr(intention_mod, 'e_rounds',
                        lambda *a, **k: math.inf)
    ist = IntentionState()
    ist.p1_pair = ('持续伤害',)
    update_intention(gs, ist, None)
    assert ist.p1_pair == ('持续伤害',), '门拒帧保持单体系对(不写 pair)'
    assert ist.p1_pair_frozen, '窗口关闭 → 单体系冻结(停手战,旧行为)'
    # 事件面申报:同帧先 pair_gate:deny 后被 freeze 事件覆写(现有事件
    # 先序 = freeze 后写获胜,非本批引入;门拒观测归分键/板面态双锁)。


def test_q_challenger_fill_path_unchanged() -> None:
    """锁 4a:chall 非空支零漂移——满支持挑战者照旧从 Q 直填(无候选对、
    不走可行性门),真两体系成型照旧冻结(成型停手语义不变)。"""
    dep = [Unit(char_id='桑博', star=1, slot=1), Unit(char_id='艾丝妲', star=1, slot=2), Unit(char_id='三月七', star=1, slot=3), Unit(char_id='丹恒·饮月', star=1, slot=4)]
    board = {'持续伤害': 2, '列车同行': 2}
    gs = _seed_gs(deployed=dep, board=board)
    ist = IntentionState()
    ist.p1_pair = ('持续伤害',)
    update_intention(gs, ist, None)
    assert ist.p1_pair == ('持续伤害', '列车同行')
    assert str(ist.last_event).startswith('p1_pair:'), \
        f'Q 填充走 p1_pair 事件(非 pair_gate 路由),got {ist.last_event!r}'
    assert ist.p1_pair_frozen, '真两体系成型照旧冻结([13] 停手语义不变)'
    assert readiness_form_ok(gs, pair_target_comp(ist.p1_pair)), \
        '两档齐 = form_ok(kernel 成型线)'


def test_seele_system_never_progressive_pick() -> None:
    """锁 1(排除腿):零证据态(仅 DOT 点火,无任何第二体系资产)下,
    渐进填充不得选出希儿系(E 对它结构性失真:距离恒 0 虚假;carry
    单卡依赖),只在三桥体系内选。"""
    dep, board = _ignite_dot_board()
    gs = _seed_gs(deployed=dep, board=board)
    ist = IntentionState()
    ist.p1_pair = ('持续伤害',)
    update_intention(gs, ist, None)
    assert len(ist.p1_pair) == 2
    assert '希儿系' not in ist.p1_pair


def test_empty_window_still_empty() -> None:
    """锁 4b:空窗支零漂移——零资产帧派生对恒空。"""
    gs = _seed_gs(deployed=[])
    ist = IntentionState()
    update_intention(gs, ist, None)
    assert ist.p1_pair == (), '空窗恒空对(既有语义)'
