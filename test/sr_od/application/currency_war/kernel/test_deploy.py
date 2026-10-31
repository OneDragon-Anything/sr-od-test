"""部署与换人域测试(机制主题文件;部署决策 → 载荷执行 → 写序契约全链)。

被测机制(按节;设计出处见各节 docstring):
- **部署围栏与占槽物品防线**:占位件(kind ∈ tome/bookcard/supply_box)
  恒 held、拒因 ``item_slot``,先于一切围栏/cap 判定被剔除(benchchar-
  retirement P4 容器槽位 kind 口);
- **板满门三个测试**(事故 match_g_20260918_023823,定谳见
  .debug/temp/incidents/20260918-reconcile/rootcause-reopen.md 案一):
  部署输入改容器现读 + 显式板满门,拒因 ``deploy_cap_full`` 帧级去重;
- **落位策略三级排路由**:comp 站位覆盖 > 注册表派生 > back 兜底;
  后排槽位上限 = back_layout 现值(P2 遗留分歧消除);
- **必需件语义**(判据必要条件支配论证;sim n1000 s91700 两失败局):
  required 成员 cap 竞争首桶序;
- **残余补部署守卫**(P24 结构支配定理,零自由参数):dup 剔除 /
  cap 满停 / 两排皆满停 / cap=None 不设门 + 配方底线门 kernel 直测;
- **载荷与执行语义**(P2 拖拽语义落码):(to_row, to_slot) 直落
  反「首空」、目标槽有人 = 交换(写侧/执行链/sim 三面同源);
- **动作上报单写写序**(合卷契约):一次语义变更 = 恰一次 deployed 写;
  动态容量布局真值辖载荷校验。

(换入臂/双轨对锁期换入通道/发射门三轴测试节已随部署统一批丁丁收编删除:
kernel swap 机器与三轴门退役,场上去留 = 统一部署搜索定型单属——
unified-deploy-order §2.7/§4;残余补部署/配方底线门测试随七桶选人
退役批次处置。)
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_comps import (
    get_comp,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    ChannelSig,
    Unit,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.deploy_plan import (
    deploy_row_pref,
    deploy_slot_plans,
)

_SIG_OBS = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')
_SIG_LOGIC = ChannelSig(family='logic_action', actor='CwScreenPrep')


@pytest.fixture(autouse=True)
def _drain_defect_buffer():
    """测试卫生:主域种子经 observe 覆盖开局种子(logic_rand 通道)会产
    预期内 logic_rand_outcome 行入进程级缓冲——前后双清,防跨用例顺序
    依赖红(同 test_tracked_slot_star_guard / test_effect_inventory
    同款排水纪律)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        consume_defect_sink,
    )
    consume_defect_sink()
    yield
    consume_defect_sink()


# (围栏与占槽物品防线/板满门/必需件 cap 竞争测试节已随部署统一批丁丁批
#  收编删除:七桶选人族(select_deployments)与 _deployable/_emit_
#  deploy_moves/_deploy_cap_full_gate 随选人退役,拒因闭集
#  (item_slot/deploy_cap_full/deploy_emit_held_*)停产——unified-
#  deploy-order §2/§4;占位件不入目标板 = 搜索段 0 剔除,板满帧部署
#  由差分执行器交换交互承载,覆盖面归 test_deploy_search.py。)
# ============================================================ 落位策略三级排路由 + back_layout 槽上限


def _bs(slot: int, char_id: str) -> BenchSlot:
    return BenchSlot(kind='unit', unit=Unit(char_id=char_id, star=1))


def test_comp_position_override_beats_registry_pref() -> None:
    """comp char_positions 覆盖注册表:万敌注册表 flex(派生 back),
    「万敌单C」覆盖为 front → 落位排 = front(逐件路由直接断言 +
    落位计划端到端各一分支)。"""
    comp = get_comp('万敌单C')
    assert comp is not None and comp.char_positions.get('万敌') == 'front', \
        '注册表前置自检:万敌单C 带 char_positions 覆盖'
    assert deploy_row_pref('万敌', None) == 'back', \
        '无 comp 覆盖时:flex 派生 back(③兜底前先走②注册表)'
    assert deploy_row_pref('万敌', comp) == 'front', \
        'comp 覆盖压过注册表派生(①>②)'

    gs = game_state_of(None)   # 行域全空:两排都有空,路由无 fallback 干扰
    bench = [_bs(1, '万敌')]
    moves = deploy_slot_plans(bench, [0], comp, gs)
    assert moves[0][1] == 'front', \
        f'落位计划按覆盖排路由,实得 {moves[0]!r}'


def test_registry_front_char_seats_front_when_front_has_room() -> None:
    """注册表前排角色(开拓者·记忆,position_pref='front')在前排有空时
    被落位策略排到前排——旧链路恒按后排,本测试钉住派生真实生效。"""
    gs = game_state_of(None)
    bench = [_bs(1, '开拓者·记忆'),
             _bs(2, '花火')]   # 花火 = 注册表 back(对照组)
    moves = deploy_slot_plans(bench, [0, 1], None, gs)
    assert moves[0][:2] == (0, 'front'), \
        f'注册表前排角色落前排,实得 {moves[0]!r}'
    assert moves[1][:2] == (1, 'back'), '注册表后排角色照旧落后排'


def test_unregistered_name_falls_back_to_back() -> None:
    """③兜底:注册表未登记名(识别对齐缺失形态)按后排处理(fail 向
    后排 = 与旧缺省同侧,不因识别缺失翻到前排)。前排预置占位避开
    前排保证强转(前排全空 → back 件被强转前排,是另一条策略规则的
    正确行为,不混入本测试)。"""
    assert deploy_row_pref('未注册角色名', None) == 'back'
    gs = game_state_of(None)
    gs.observe(gs.deployed, _dvs([Unit(char_id='砂金', star=1, equips=[])], []),
               evidence='t', sig=_SIG_OBS)
    bench = [_bs(1, '未注册角色名')]
    moves = deploy_slot_plans(bench, [0], None, gs)
    assert moves[0][1] == 'back', '未注册名兜底后排'


def test_back_slots_capped_by_back_layout_baseline() -> None:
    """back_layout 基线 6:8 个后排候选(前排被占满)→ 后排槽号至多 6,
    永不发射 7-9 号槽(执行面 6 槽,越界载荷 = 静默分歧的消除面)。"""
    gs = game_state_of(None)
    gs.observe(gs.back_layout, 6, evidence='t', sig=_SIG_OBS)
    gs.observe(gs.deployed, _dvs([Unit(char_id=f'前{i}', star=1, equips=[])
                for i in range(1, 5)], []), evidence='t', sig=_SIG_OBS)
    bench = [_bs(i + 1, '花火') for i in range(8)]
    moves = deploy_slot_plans(bench, list(range(8)), None, gs)
    back_slots = [slot for _bi, row, slot in moves if row == 'back']
    assert back_slots == [1, 2, 3, 4, 5, 6], \
        f'后排空槽按 back_layout 现值派生,实得 {back_slots!r}'


def test_back_layout_extended_value_extends_back_slots() -> None:
    """back_layout 扩展局(宝钻 8):后排空槽随实值到 8 号——执行面/表
    随实值,扩展槽在扩展局可达(上限随实值,非恒 6)。前排占满避开
    前排保证强转(不混入本测试)。"""
    gs = game_state_of(None)
    gs.observe(gs.back_layout, 8, evidence='t', sig=_SIG_OBS)
    gs.observe(gs.deployed, _dvs([Unit(char_id=f'前{i}', star=1, equips=[])
                for i in range(1, 5)], []), evidence='t', sig=_SIG_OBS)
    bench = [_bs(i + 1, '花火') for i in range(8)]
    moves = deploy_slot_plans(bench, list(range(8)), None, gs)
    back_slots = [slot for _bi, row, slot in moves if row == 'back']
    assert back_slots == [1, 2, 3, 4, 5, 6, 7, 8], \
        f'扩展局后排空槽达 8 号,实得 {back_slots!r}'


# (残余补部署守卫(P24)与配方底线门/仙舟供给谓词测试节已随部署统一
#  批丁丁批收编删除:七桶选人族与 recipe_floor_holds/xianzhou_supply_
#  exists/residual_fill_plan 随选人退役——unified-deploy-order §2/§4;
#  空槽补位/围栏语义由统一部署搜索 + 差分执行器单测承载
#  (test_deploy_search.py/test_deploy_diff.py)。)
# ============================================================
# (载荷与执行语义/动作上报单写写序两节(旧 CwActionDeployMoveParam/
#  CwActionSwapDeployParam 载体)已随部署统一批戊批收编删除:词表类/
#  执行 op/上报模块同批退役,统一拖动 = CwActionMoveUnitParam 单载体——
#  unified-deploy-order §2.7/§4;写侧单写契约/交换语义/越界拒绝/动态
#  后排容量覆盖面归 cw_action_report/test_move_unit.py 与
#  test_deploy_diff.py(差分执行器)。)

