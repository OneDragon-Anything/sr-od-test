"""test_cw_round_flow 主题锁(轮流程族:退局 op / 结算观测 / 过渡定型 / 位面轮读 / 金稳定门 / 部署点火)。

按机制归并的主题文件,成员来自 8 个已删除的 round/工作项命名历史文件
(r279_exit_op / r317_exit_op / r366_settlement_node_type / w40_settlement_damage /
transition / false_win_guard / gold_settle_gate / r404_ignition_order,出处见 git 历史)。
结构合并批曾机械拼接(来源前缀别名 / 重复 sys.path 块),瘦身批已按覆盖关系对账收敛并清疤。
"""
from __future__ import annotations

import inspect
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import sr_od.application.currency_war.kernel.cw_observe as obs_mod
import sr_od.application.currency_war.obs.cw_observation as observation
from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    ignition_gain,
    select_deployments,
)
from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState
from sr_od.application.currency_war.kernel.cw_transition import (
    FRAMEWORK_FACTIONS,
    FRAMEWORKS,
    TRANSITION_PACK,
    CommitSignals,
    transition_score,
)
from sr_od.application.currency_war.obs.cw_observation import read_phase_round
from sr_od.application.currency_war.obs.cw_settlement_obs import (
    parse_settlement_damage,
    parse_settlement_node_type,
    read_round_outcome,
)
from sr_od.application.currency_war.operations.cw_entry.cw_entry_exit import CwEntryExit
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.telemetry import recorder
from sr_od.application.currency_war.telemetry.query import read_jsonl
from sr_od.application.currency_war.telemetry.recorder import TelemetryRecorder
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

# 仓根锚定:fixture 图(_TEST_REPO)与生产源码墓碑扫描(_MAIN_REPO)用。
# sr_od 的导入路径由主仓 pyproject [tool.pytest.ini_options] pythonpath=['src']
# 装载,本文件不再自插 sys.path(结构合并批遗留的三处 sys.path 块已清)。
_TEST_REPO = Path(__file__).resolve().parents[4]   # sr-od-test/
_MAIN_REPO = Path(__file__).resolve().parents[5]   # 主仓根(src/ 所在)


# ==================== 退局 op(r279/r302/r303b/r317)====================


class _ExitFixtureController(FixtureController):
    """补真机控制器才有的 stub:btn_tap/mouse_move(纯 op 流程测试用)。"""

    def btn_tap(self, key: str) -> None:
        pass

    def mouse_move(self, game_pos: Point) -> None:
        pass


class _WatchedExit(WatchdogOperationMixin, CwEntryExit):
    """带看门狗的退局 op(防 WAIT 段死循环)。"""


def test_battle_pause_screen_onboarded() -> None:
    """战斗暂停画面档存在(分支③的识别地基)。"""
    import yaml

    p = 'assets/game_data/screen_info/currency_war_battle_pause.yml'
    with open(p, encoding='utf-8') as f:
        d = yaml.safe_load(f)
    names = {a['area_name'] for a in d['area_list']}
    assert '标识-战斗暂停' in names
    assert '按钮-撤退' in names
    assert '按钮-继续战斗' in names


def test_retreat_branch_clicks_retreat_on_pause_frame(
    test_context: SrTestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """行为锁(替代旧 2 条源码字面锁「'货币战争-战斗暂停' in src /
    '按钮-撤退' in src」,r279 增补):战斗暂停 fixture 帧 → 真 exit_match
    链识别暂停画面 → 点击「按钮-撤退」area 中心(pc_alt)推进,不点右上角
    X 兜底坐标、不按 esc、不误点「继续战斗」(r302/r317 误配史)。失守场景 =
    撤退分支被删/锚失效退化为尾部点 X 死循环(r279 修复的战斗中 retry 死
    循环形态)时本锁红。

    撤退是退局 op 全分支里唯一无行为覆盖的出口——本锁补齐该防线;
    画面档地基由 test_battle_pause_screen_onboarded 守。
    """
    frames = [
        ('货币战争-战斗暂停', 'paused'),
        ('货币战争-大厅', 'lobby'),
    ]
    for screen_name, state in frames:
        if not test_context.has_screen(screen_name, state):
            pytest.skip(f'fixture 缺失:screens/{screen_name}/{state}.webp')

    phases = [
        {   # 战斗暂停帧:点「按钮-撤退」area 中心才推进(错点不推进)
            'frame': ('货币战争-战斗暂停', 'paused'),
            'exit': ('on_click_in', '货币战争-战斗暂停', '按钮-撤退'),
        },
        {   # 撤退后中断挑战弹窗的「放弃并结算」由既有分支接管 → 大厅(terminal)
            'frame': ('货币战争-大厅', 'lobby'),
        },
    ]
    ctrl = _ExitFixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    ctrl.set_phases(phases)
    monkeypatch.setattr(test_context, 'controller', ctrl)

    op = _WatchedExit(test_context)
    op._init_watchdog()  # type: ignore[attr-defined]

    enter_running_state(test_context)
    try:
        with fast_sleep():
            result = op.execute()
    finally:
        reset_running_state(test_context, op)

    assert result.success, (
        f'战斗暂停帧应经撤退回大厅:status={result.status};'
        f'phase_idx={ctrl.phase_idx}'
    )
    assert ctrl.click_hit_area('货币战争-战斗暂停', '按钮-撤退'), (
        f'应点击「按钮-撤退」area 内,实际点击={ctrl.recorded_clicks}')
    # 不走其他出口:不点右上角 X 兜底 (1843,42),不按 esc(撤退分支专用出口)
    assert not any(abs(p.x - 1843) <= 5 and abs(p.y - 42) <= 5
                   for p in ctrl.recorded_clicks), (
        f'不得点右上角 X 兜底坐标(全分支 miss 形态),实际点击={ctrl.recorded_clicks}')
    assert ctrl.recorded_btn_taps.count('esc') == 0, (
        f'撤退分支不得按 esc,实际按键={ctrl.recorded_btn_taps}')


def test_no_round_retry_tail() -> None:
    """战斗中不再落入无界 retry 尾(旧版尾分支;否定墓碑,r279 退役背书)。

    K1(验证废除批 2026-09-10)改写:overlay 分支 round_wait → round_retry
    (计节点 retry 预算,node_max_retry_times=30,耗尽框架原生 FAIL)——
    本锁防线语义收窄为「全分支 miss 不落入无上界重试」:①尾部兜底(战斗中
    右上 X)仍是有界形态(全分支 miss 计数 _miss_rounds ≥10 → fail,无
    retry 尾);②overlay 分支的 retry 为节点预算有界,非 r279 防的无界尾。
    """
    src = inspect.getsource(CwEntryExit.exit_match)
    tail = src.split('战斗中右上 X')[1] if '战斗中右上 X' in src else ''
    assert "round_retry" not in tail or "_miss_rounds" in tail, (
        'r279: 全分支 miss 尾分支不得引入无界 retry(须由 _miss_rounds 有界化)')
    # overlay 分支 retry 必须自述预算有界依据(K1 改形备注),防退化为裸 retry 尾
    overlay_retry = src.split('_overlay_branch(')[0].count('round_retry')
    assert 'node_max_retry_times=30' in src, (
        'overlay 分支 retry 化的预算锚(exit_match 节点预算 30)必须在场')


# ===== W62 件3(ADR-0329):投资策略屏「左卡+确认」点击落地修复锁 =====


def test_invest_strategy_confirm_area_onboarded() -> None:
    """件3 画面档地基:投资策略屏「按钮-确认」area 建档且中心 ≈ 手动解锁点 (978,984)。

    修复依赖的定位源(screen_info area 中心)——area 缺失/漂移会让修复失效。
    """
    import yaml

    from one_dragon.base.geometry.rectangle import Rect

    p = 'assets/game_data/screen_info/currency_war_invest_strategy.yml'
    with open(p, encoding='utf-8') as f:
        d = yaml.safe_load(f)
    areas = {a['area_name']: a for a in d['area_list']}
    assert '按钮-确认' in areas, '投资策略屏应有「按钮-确认」area(件3 修复定位源)'
    assert '标识-请选择投资策略' in areas, 'r303b 分支识别锚'
    rect = Rect(*areas['按钮-确认']['pc_rect'])
    c = rect.center
    assert abs(c.x - 978) <= 2 and abs(c.y - 983) <= 2, (
        f'确认按钮中心应 ≈ (978,983)(手动解锁 (978,984)),实际 ({c.x:.0f},{c.y:.0f})')


def test_invest_strategy_branch_uses_area_center_not_ocr() -> None:
    """墓碑锁(r303b 卡点根因 / W62 件3,ADR-0329):投资策略分支不得回退
    全屏 OCR 搜「确认」点击。

    旧 round_by_ocr_and_click 对 stylized 按钮静默失配 → 点不落地 → 卡行
    748s;修后走 area 中心(area_center + 兜底 Point(978,983))。分支的
    行为面(选卡+确认点击序列、不点「返回备战界面」)由
    test_invest_strategy_screen_takes_select_confirm_path 端到端守,
    定位源(screen_info「按钮-确认」area 中心)由
    test_invest_strategy_confirm_area_onboarded 守——本锁只辖「OCR 点击
    通道退役」墓碑(肯定式在场断言已按源码锁三档判据删除)。
    """
    src = inspect.getsource(CwEntryExit.exit_match)
    branch = src.split('标识-请选择投资策略')[1].split('round_wait')[0]
    assert "self.round_by_ocr_and_click(" not in branch


# ==================== r317_exit_op(投资策略屏退局顺序/area 化)====================


def test_invest_strategy_branch_before_return_btn() -> None:
    """顺序锁:投资策略分支(选卡+确认)必须在「返回备战界面」分支之前。

    回归防:若「返回备战界面」(全屏 OCR)被放回前面,投资策略屏会先被它命中
    并点击落空 → 死循环复现(r317 根修点 ②③)。顺序即语义(README 纪律 8
    容忍档,记债:分支派发次序本身就是行为,无更便宜观测点)。
    """
    src = inspect.getsource(CwEntryExit.exit_match)
    pos_invest = src.index("'标识-请选择投资策略'")
    pos_return = src.index("'返回备战界面'")
    assert pos_invest < pos_return, (
        '投资策略分支必须在「返回备战界面」之前(投资策略屏正确退出=选卡+确认,'
        '非点返回按钮;r317 根修点 ②③)'
    )


# 逐 OCR 调用 lcs_percent=0.8 参数字面断言(test_settlement_ocr_lcs_tightened)
# 已按源码锁瘦身删除——参数字面形状锁随实现写法漂移,语义由
# test_battle_prep_detection_area_based 的裸 OCR 退役墓碑锁并守。


def test_battle_prep_detection_area_based() -> None:
    """T#103 化债锁:「备战阶段」检测走 screen_info area(标识-备战阶段),
    裸 OCR 调用退役。

    r317 曾以 lcs=0.8 收紧裸 OCR(默认 0.5 在投资策略屏误命中「返回备战界面」);
    T#103 建 positional rect 后误配面被结构性消灭,回归面 = 别再退回全屏扫。
    """
    src = inspect.getsource(CwEntryExit.exit_match)
    assert "'标识-备战阶段'" in src, (
        '「备战阶段」检测应使用 screen_info 标识-备战阶段 area(T#103)'
    )
    assert "round_by_ocr(screen, '备战阶段'" not in src, (
        '「备战阶段」不应再走全屏 OCR(r317 误配史:T#103 已 area 化,勿回退)'
    )


def test_invest_strategy_screen_takes_select_confirm_path(
    test_context: SrTestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """集成锁:投资策略屏 fixture → op 走「选卡+确认」,不点「返回备战界面」。

    剧本:投资策略屏(默认态)→ 点左卡推进 → 投资策略屏(已选卡)→ 点确认推进
    → 大厅(terminal)。断言:点击序列含左卡 (460,475) 与确认 area 中心
    (978,983),且无任何点击落在「返回备战界面」按钮区(右上角 x>1700)。
    """
    phases = [
        {  # 投资策略屏默认态:点左卡 (460,475) 选中 → 推进
            'frame': ('货币战争-投资策略', 'default'),
            'exit': ('on_click_in', [400, 450, 520, 500]),
        },
        {  # 投资策略屏已选卡:点确认 (978,983) → 推进
            'frame': ('货币战争-投资策略', 'card1_selected'),
            'exit': ('on_click_in', '货币战争-投资策略', '按钮-确认'),
        },
        {  # 大厅:terminal(退局完成)
            'frame': ('货币战争-大厅', 'lobby'),
        },
    ]
    for screen_name, state in (p['frame'] for p in phases):
        if not test_context.has_screen(screen_name, state):
            pytest.skip(f'fixture 缺失:screens/{screen_name}/{state}.webp')

    ctrl = _ExitFixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    ctrl.set_phases(phases)
    monkeypatch.setattr(test_context, 'controller', ctrl)

    op = _WatchedExit(test_context)
    op._init_watchdog()  # type: ignore[attr-defined]

    enter_running_state(test_context)
    try:
        with fast_sleep():
            result = op.execute()
    finally:
        reset_running_state(test_context, op)

    assert result.success, (
        f'投资策略屏退局应成功回大厅:status={result.status};'
        f'phase_idx={ctrl.phase_idx}'
    )
    # 选卡+确认路径点击(area 中心/手动实证点)
    clicks = ctrl.recorded_clicks
    assert any(
        abs(p.x - 460) <= 20 and abs(p.y - 475) <= 20 for p in clicks
    ), f'应点击左卡 (460,475),实际点击={clicks}'
    assert any(
        abs(p.x - 978) <= 20 and abs(p.y - 983) <= 20 for p in clicks
    ), f'应点击确认 area 中心 (978,983),实际点击={clicks}'
    # 不应点击「返回备战界面」按钮区(右上角)——r317 根修点 ②③
    assert not any(p.x > 1700 and p.y < 120 for p in clicks), (
        f'不应点击右上角「返回备战界面」按钮区(点击落空死循环根因),实际点击={clicks}'
    )


# ==================== r366_settlement_node_type ====================

# 局48 实拍(逐 token 原样,含 OCR 噪声)
R1_REWARD = ['挑战成功', '奖励', 'Lv.3', '214', '小队生命值82i',
             '获得金币总览', '数据统计', '基础奖励', '6.5万', '连胜×0',
             '掉落晶矿', '继续挑战']
R3_BATTLE = ['挑战成功', '1-3X点', '战斗', '火热连胜×1', 'Lv.4', '0/20',
             '小队生命值86i', '获得金币总览', '数据统计', '基础奖励']
R7_ENCOUNTER = ['挑战结束', '遭遇', '火热连胜×0', '10/20',
                '小队生命值80i', '获得金币总览', '8', '数据统计']
BOSS_HDR = ['35', '挑战结束', '1-6', '战斗', '4/20', '小队命值45i',
            '获得金币总览', '数据统计', '基础奖励', '5']   # 局47 放弃局帧


def test_reward_node() -> None:
    assert parse_settlement_node_type(R1_REWARD) == '奖励'


def test_battle_node_with_noisy_round_token() -> None:
    """'1-3X点'(OCR 噪声)后仍取到「战斗」。"""
    assert parse_settlement_node_type(R3_BATTLE) == '普通战斗'


def test_encounter_after_end_header() -> None:
    assert parse_settlement_node_type(R7_ENCOUNTER) == '遭遇'


def test_boss_header_layout() -> None:
    assert parse_settlement_node_type(BOSS_HDR) == '普通战斗'


def test_no_header_returns_none() -> None:
    assert parse_settlement_node_type(['备战阶段', '1-6', '战斗']) is None


# (test_base_reward_no_false_hit 已删:与 test_compound_word_not_matched
#  输入与断言面逐字等价(['挑战成功','基础奖励','5','利息'] → None)——
#  r366b 前缀白名单机制下两者走同一路径,等价择一(README 纪律 7)。)


# r361b(review A 守卫)形态锁;r366b 追加粘着/emoji/复合词三测
def test_glued_header_token() -> None:
    """OCR 把头部与类型词粘成一个 token('挑战成功战斗')也能解。"""
    texts = ['挑战成功战斗', '火热连胜×1', '小队生命值86']
    assert parse_settlement_node_type(texts) == '普通战斗'


def test_emoji_prefixed_boss() -> None:
    """'👩首领'(emoji 前缀,局48 r9 实拍)后缀匹配 → boss。"""
    texts = ['挑战成功', '👩首领', '火热连胜×1', '小队生命值84']
    assert parse_settlement_node_type(texts) == 'boss'


def test_compound_word_not_matched() -> None:
    """「基础奖励」后缀命中「奖励」但前缀「基础」不在白名单 → 拒。

    r260 全屏搜「奖励」误中金币区的旧顾虑,由邻位窗口 + 精确匹配根除;
    r366b 起拒绝机制 = 前缀白名单(修饰词前缀不匹配,非长度门)。"""
    texts = ['挑战成功', '基础奖励', '5', '利息']
    assert parse_settlement_node_type(texts) is None


# ==================== w40_settlement_damage ====================


class _Item(SimpleNamespace):
    """OCR 结果桩(data/x/y/width/height;坐标取自 fixture 实测 OCR)。"""


def _items(spec: list[tuple[str, int, int, int, int]]) -> list[_Item]:
    return [_Item(data=t, x=x, y=y, width=w, height=h)
            for t, x, y, w, h in spec]


# sr-od-test/screens/货币战争-结算/win.webp 全屏 OCR 实测(token, x, y, w, h)
WIN_FRAME = _items([
    ('挑战成功', 831, 192, 256, 73), ('1-8', 887, 270, 44, 28),
    ('奖励', 981, 269, 55, 30), ('Lv.5', 1110, 367, 85, 66),
    ('4/20', 1127, 427, 55, 25), ('小队命值20i', 646, 479, 226, 43),
    ('获得金币总览', 530, 553, 146, 28), ('10', 1042, 555, 31, 26),
    ('数据统计', 1120, 554, 98, 29), ('基础奖励', 530, 604, 98, 28),
    ('5', 1051, 605, 22, 25), ('试用', 1144, 601, 47, 25),
    ('396.3万', 1198, 635, 81, 25), ('利息', 527, 653, 56, 31),
    ('4', 1057, 660, 13, 17), ('试用', 1144, 678, 48, 26),
    ('连胜×0', 528, 702, 113, 35), ('6.4万', 1196, 712, 58, 26),
    ('掉落晶矿', 528, 771, 100, 32), ('5', 1058, 780, 8, 14),
    ('继续挑战', 910, 878, 100, 31),
])

# ended.webp(挑战结束态)同布局;伤害列 137.0万 + 1.1万
ENDED_DAMAGE = _items([
    ('挑战结束', 831, 191, 257, 73), ('数据统计', 1120, 554, 98, 29),
    ('试用', 1144, 601, 48, 25), ('137.0万', 1198, 635, 80, 25),
    ('试用', 1144, 678, 48, 26), ('1.1万', 1196, 712, 56, 26),
])


# ===== 纯函数:parse_settlement_damage =====

def test_win_fixture_damage_sum() -> None:
    """win.webp 伤害列 396.3万 + 6.4万 → 4027000(左列金币裸数字 10/5/4 不入)。"""
    assert parse_settlement_damage(WIN_FRAME) == 4_027_000


def test_ended_fixture_damage_sum() -> None:
    """ended.webp(挑战结束态)同布局:137.0万 + 1.1万 → 1381000。"""
    assert parse_settlement_damage(ENDED_DAMAGE) == 1_381_000


def test_damage_token_outside_stat_column_ignored() -> None:
    """「万」形 token 落在左列区(位置守卫)→ 不计;全无命中 → None。"""
    items = _items([('6.5万', 600, 650, 50, 25), ('基础奖励', 530, 604, 98, 28)])
    assert parse_settlement_damage(items) is None


def test_no_damage_token_returns_none() -> None:
    """无「万」token(面板不可见/OCR 漏)→ None,不冒认 0。"""
    items = _items([('挑战成功', 831, 192, 256, 73), ('10', 1042, 555, 31, 26)])
    assert parse_settlement_damage(items) is None


# ===== read_round_outcome 集成(同帧产 hp + damage) =====

def _ctx_with_items(items: list[_Item]) -> SimpleNamespace:
    return SimpleNamespace(ocr_service=SimpleNamespace(
        get_ocr_result_list=lambda image, rect=None, crop_first=False: items))


def test_read_round_outcome_produces_damage() -> None:
    """结算帧 → RoundOutcome 同帧产 hp_after=20 + damage_dealt=4027000。"""
    obs = read_round_outcome(_ctx_with_items(WIN_FRAME), None,
                             plane=1, round_num=8, comp_tag='c')
    assert obs.hp_after == 20
    assert obs.damage_dealt == 4_027_000
    assert obs.killed is True


def test_read_round_outcome_damage_none_without_panel() -> None:
    """无伤害行的帧(战斗中/面板被遮)→ damage_dealt=None(旧 schema 默认不破坏)。"""
    items = _items([('挑战成功', 831, 192, 256, 73),
                    ('小队生命值86i', 646, 479, 226, 43)])
    obs = read_round_outcome(_ctx_with_items(items), None,
                             plane=1, round_num=3, comp_tag='c')
    assert obs.damage_dealt is None
    assert obs.hp_after == 86


def test_outcome_record_damage_roundtrip(tmp_path) -> None:
    """OutcomeRecord.damage_dealt 落盘往返;默认行(None)旧锁兼容。"""
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    rec.record_outcome('r1', RoundOutcome(
        round_num=8, plane=1, node_type='奖励', comp_tag='c',
        hp_after=20, hp_confidence=1.0, damage_dealt=4_027_000))
    rec.record_outcome('r1', RoundOutcome(
        round_num=9, plane=1, node_type='boss', comp_tag='c', hp_after=1))
    lines = read_jsonl(tmp_path / 'outcomes.jsonl')
    assert lines[0]['damage_dealt'] == 4_027_000
    assert lines[1]['damage_dealt'] is None


# ===== cw_screen_battle_wait 接线(结算帧 → record_outcome 携带 damage_dealt) =====
# (W971 05-battle §1 P4:结算链自 cw_loop 收编 CwScreenBattleWait,本测试随迁。)

def test_loop_outcome_carries_damage(monkeypatch) -> None:
    """②段路径:真实 read_round_outcome(不桩)喂 win 形帧 → 遥测行带 damage。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_battle_wait as bwo,
    )

    captured: list[dict] = []
    monkeypatch.setattr(recorder, 'record_outcome',
                        lambda outcome, source='': captured.append(
                            {'outcome': outcome, 'source': source}))
    monkeypatch.setattr(recorder, 'record_exogenous',
                        lambda *a, **k: None)
    monkeypatch.setattr(bwo, 'read_phase_round', lambda ctx, screen: (1, 8))

    class _Op(bwo.CwScreenBattleWait):
        def __init__(self):  # noqa: D107  桩:bypass SrOperation.__init__
            self._st = bwo.SettlementState(
                run_start_ts=time.monotonic() - 9999.0,   # 超宽限:正常行
                is_new_match=True)
            self._unknown_streak = 0
            # 观察半直写面(ADR-0583):真实 StrategySession 承载(字段齐备)
            from sr_od.application.currency_war.strategies.impl.cw_strategy import (
                StrategySession as _SS,
            )
            _sess = _SS()
            _sess.last_state = GameState()
            state_of(_sess)
            self.ctx = SimpleNamespace(
                cw_match=SimpleNamespace(
                    session=_sess,
                    strategy=SimpleNamespace(),
                ),
                ocr_service=SimpleNamespace(
                    get_ocr_result_list=lambda image, rect=None,
                    color_range=None, crop_first=False: WIN_FRAME),
            )
            self._cw_config = None

        def round_by_ocr(self, screen, word, **kw):
            return SimpleNamespace(is_success=False)

        def round_by_find_area(self, screen, screen_name, area_name, **kw):
            return SimpleNamespace(is_success=False)   # T#103:boss 判定改 area(标识-首领)

    op = _Op()
    op._record_round_outcome(screen=None)
    assert len(captured) == 1
    assert captured[0]['source'] == ''
    assert captured[0]['outcome'].damage_dealt == 4_027_000
    assert captured[0]['outcome'].round_num == 8
    # 结算观察半供给半环锁(ADR-0583 拆两半;落地审低2,纪律 13):
    # 真实 op 回路走完 → 观察半经生产调用线已写(performance.history 增行 +
    # last_streak 直写)+ 策略半已入 pending 槽——删 op 内调用线全集即红。
    _sess = op.ctx.cw_match.session
    assert len(_sess.performance.history) == 1, (
        'op 回路必须触发结算观察半直写(供给半环;删调用线 = 红)')
    assert _sess.last_streak == captured[0]['outcome'].streak
    assert len(_sess.pending_round_outcomes) == 1, (
        '策略半必须同点入 pending 槽(决策入口 drain 的供给前提)')


def test_branch3_records_before_continue_click() -> None:
    """顺序锁:②段采样点在「继续挑战」点击前(结算停留期先读后点)。

    顺序即语义(README 纪律 8 容忍档,记债):读点先于点击 = 读的是点击前
    同帧,无更便宜观测点(经 wait() 全链重放需整套结算 fixture)。锚取
    wait() 内单次出现的调用名,不锚缩进/换行形状(合法重排不假红)。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_battle_wait,
    )
    src = inspect.getsource(cw_screen_battle_wait.CwScreenBattleWait.wait)
    i_read = src.index('_record_round_outcome(screen)')
    i_click = src.index('round_by_find_and_click_area')
    assert i_read < i_click





# ==================== transition ====================


def test_pack_covers_data_driven_cards() -> None:
    """plaza 实证牌全在包内且归属正确框架。"""
    for name in ('藿藿', '丹恒·饮月', '爻光', '卡芙卡', '椒丘'):
        assert TRANSITION_PACK[name][0] == '仙舟', f'{name} 应属仙舟框架'
    for name in ('三月七', '姬子·启行', '花火'):
        assert TRANSITION_PACK[name][0] == '列车', f'{name} 应属列车框架'
    assert TRANSITION_PACK['千冶·刃'][0] == '通用'


def test_framework_factions_defined() -> None:
    """三框架的目标羁绊(仙舟+DOT / 列车 / 量子+贝;r102 统一化)。"""
    assert set(FRAMEWORKS) == {'仙舟', '列车', '量子'}
    assert '仙舟' in FRAMEWORK_FACTIONS['仙舟']
    assert '列车同行' in FRAMEWORK_FACTIONS['列车']
    assert '量子同频' in FRAMEWORK_FACTIONS['量子']


def test_same_framework_bonus() -> None:
    """同框架牌 > 通用插件 > 散件(集中买一包)。"""
    assert transition_score('藿藿', 'x', '仙舟') > transition_score('千冶·刃', 'x', '仙舟')
    assert transition_score('千冶·刃', 'x', '仙舟') > transition_score('艾丝妲', 'x', '仙舟')
    # 跨框架:藿藿在列车框架下无加成
    assert transition_score('藿藿', 'x', '列车') < transition_score('藿藿', 'x', '仙舟')


def test_carry_beats_drop_same_tier_base() -> None:
    """同框架内 carry > drop。"""
    assert transition_score('藿藿', 'x', '仙舟') > transition_score('卡芙卡', 'x', '仙舟')


# (test_early_phase_gate 已随 in_early_phase 退役删除——调用点唯一=dv 框架
#  启动分支,ADR-0468;Early 判定语义由消费方内联,无独立函数可锁。)


# ===== r39 定型信号管线(ADR-0519 重锚)=====
# 信号定型门(ready/COMMIT_SIGNAL_THRESHOLD/COMMIT_MIN_T/t_of)已随「未证即退役」
# 删除且全库零生产消费(定型权威 = cw_intention.committed_authority);CommitSignals
# 保留为遥测累积器,本节锁其累积数学与「无决策接口」形态。

def test_commit_signals_accumulate_and_lead() -> None:
    """信号累积数学(遥测载体):源权重 × 归一化分累加,leader 取最大。"""
    sig = CommitSignals()
    sig.add('briefing_affix', {'列车同行': 0.8, 'DOT队': 0.3})   # 1.5×1.0 = 1.5
    sig.add('invest_strategy', {'列车同行': 0.9, 'DOT队': 0.1})  # 2.0×1.0 = 2.0
    lead = sig.leader()
    assert lead is not None and lead[0] == '列车同行'
    assert abs(lead[1] - 3.5) < 1e-9
    sig.add('invest_env', {'列车同行': 1.0, 'DOT队': 0.2})       # +1.0 = 4.5
    sig.add('supply_reward', {'列车同行': 1.0})                  # +0.8 = 5.3
    lead = sig.leader()
    assert lead is not None and abs(lead[1] - 5.3) < 1e-9


def test_commit_signals_has_no_decision_interface() -> None:
    """ADR-0519 退役锁:CommitSignals 只剩 add/leader(遥测),无 ready 决策门。"""
    assert not hasattr(CommitSignals(), 'ready')
    import sr_od.application.currency_war.kernel.cw_transition as _ct
    assert not hasattr(_ct, 't_of')
    assert not hasattr(_ct, 'COMMIT_SIGNAL_THRESHOLD')
    assert not hasattr(_ct, 'COMMIT_MIN_T')


# (test_commit_boundary_plane_gate_only 已删:committed_authority 的三断言
#  (P1 高分未锁 False / P1 意向锁 True / P2 恒 True)是
#  test_cw_migration_direction_layer.py::test_committed_predicate_frame_by_frame_
#  vs_old(帧 3/4/5 同构造)的真子集——对拍锁为超集(另辖 both_false 帧 +
#  旧谓词镜像),跨文件等价择一保留超集(README 纪律 7)。)


# ==================== test_false_win_guard ====================


class _FakeOcr:
    def __init__(self, blob: str):
        self.blob = blob

    def __call__(self, ctx, screen, rect):
        class _R:
            data = self.blob
        return [_R()]


class _Ctx:
    pass


def test_phase_round_rejects_plane_out_of_range(monkeypatch) -> None:
    """plane=8(A8 难度泄漏)必须拒——M70 假 win 根因。"""
    import sr_od.application.currency_war.obs.cw_observation as obs
    monkeypatch.setattr(obs, '_last_phase_round', None)
    monkeypatch.setattr(obs, '_ocr', _FakeOcr('A8 8-8'))
    monkeypatch.setattr(obs, '_area_rect', lambda ctx, name: None)
    # OCR blob 抓 "8-8" → 值域守卫拒(不进缓存)
    got = read_phase_round(_Ctx(), None)
    assert got == (1, 1), f'plane=8 应被值域守卫拒(回退 1,1),实得 {got}'


def test_phase_round_digits_fallback_only_accepts_one(monkeypatch) -> None:
    """非格式读数(单数字错源如 "Lv.8")不得产出非默认值。

    旧语义「数字 fallback 分支拒非 1」已随 w891 延迟审计候选③退役:该分支
    唯一合法产出 (1,1) 与无历史兜底完全重合(结构零信息),整段删除 = 治本。
    本锁改钉删除后语义:错源单数字走无匹配路径 → last-known/默认兜底 (1,1),
    不再产生 fallback 冲突留证。"""
    import sr_od.application.currency_war.obs.cw_observation as obs
    monkeypatch.setattr(obs, '_last_phase_round', None)
    monkeypatch.setattr(obs, '_ocr', _FakeOcr('Lv.8'))
    monkeypatch.setattr(obs, '_area_rect', lambda ctx, name: None)
    got = read_phase_round(_Ctx(), None)
    assert got == (1, 1), f'单数字 8 应拒(非开局),实得 {got}'


def test_phase_round_normal_parse_unaffected(monkeypatch) -> None:
    """正常 "1-3" 解析不受影响。"""
    import sr_od.application.currency_war.obs.cw_observation as obs
    monkeypatch.setattr(obs, '_last_phase_round', None)
    monkeypatch.setattr(obs, '_ocr', _FakeOcr('回合 1-3'))
    monkeypatch.setattr(obs, '_area_rect', lambda ctx, name: None)
    assert read_phase_round(_Ctx(), None) == (1, 3)


def test_phase_round_digits_fallback_branch_removed() -> None:
    """源码锁:数字 fallback 分支已删(ocr_digits_fallback 全消失)。

    出处:w891 延迟审计候选③——该分支结构零信息(唯一合法产出与默认兜底
    重合),近两日 868 次被拒全为纯浪费;治本 = 删段,不留在证面。"""
    src = (_MAIN_REPO / 'src' / 'sr_od' / 'application'
           / 'currency_war' / 'obs' / 'cw_observation.py').read_text(encoding='utf-8')
    assert 'ocr_digits_fallback' not in src


def test_phase_round_wrong_source_digit_keeps_last_known(monkeypatch) -> None:
    """有历史时错源单数字 → 保旧(last-known),不产 (1,1) 毒化。"""
    import sr_od.application.currency_war.obs.cw_observation as obs
    monkeypatch.setattr(obs, '_last_phase_round', (2, 3))
    monkeypatch.setattr(obs, '_ocr', _FakeOcr('Lv.8'))
    monkeypatch.setattr(obs, '_area_rect', lambda ctx, name: None)
    assert read_phase_round(_Ctx(), None) == (2, 3)


# ===== 回退修正确认通道(分诊 F 根修) =====
# 根因:前帧错读(如 5→6)过单调守卫被缓存,守卫又把真值 5 每帧拒掉 = 错读固化
# (分诊 §2:9/10 冲突帧同 [x,6]→[x,5] 模式)。守卫语义对齐 hp 下行守卫:
# 锁「非机制性跳变」(单帧倒退=OCR 噪声,仍拒),不锁「修正」(跨帧复现的
# 同值倒退=前值固化错读,确认后采新)。确认帧数=2 依据:hp 下行复现确认
# (HP_SUSPECT_CONFIRM_FRAMES=2)与 star 回退防抖「连续 2 次」同族先例。

def _stub_phase_round_obs(monkeypatch, blob: str) -> None:
    import sr_od.application.currency_war.obs.cw_observation as obs
    monkeypatch.setattr(obs, '_last_phase_round', (1, 6))
    monkeypatch.setattr(obs, '_phase_round_suspect', None)
    monkeypatch.setattr(obs, '_ocr', _FakeOcr(blob))
    monkeypatch.setattr(obs, '_area_rect', lambda ctx, name: None)
    monkeypatch.setattr(obs, 'obs_conflict', lambda *a, **kw: None)


# (test_phase_round_backward_blip_rejected 已删:同一桩下「首帧防抖保旧」
#  断言是 test_phase_round_backward_confirmed_two_frames 首行的真子集
#  (README 纪律 18 子集断言),确认测的超集断言面(防抖→确认→缓存换新)保留。)


def test_phase_round_backward_confirmed_two_frames(monkeypatch) -> None:
    """连续 2 帧同值倒退 = 前值固化错读的修正 → 采新换缓存。"""
    _stub_phase_round_obs(monkeypatch, '回合 1-5')
    assert read_phase_round(_Ctx(), None) == (1, 6)    # 首帧:防抖保旧
    assert read_phase_round(_Ctx(), None) == (1, 5)    # 第二帧:确认修正
    assert read_phase_round(_Ctx(), None) == (1, 5)    # 修正后缓存已换新


def test_phase_round_forward_read_clears_suspect(monkeypatch) -> None:
    """倒退消失(正常前进读)→ 防抖挂起自愈清零;后续新倒退重新从首帧起算。"""
    _stub_phase_round_obs(monkeypatch, '回合 1-5')
    assert read_phase_round(_Ctx(), None) == (1, 6)    # 首帧倒退:防抖挂起
    import sr_od.application.currency_war.obs.cw_observation as obs
    monkeypatch.setattr(obs, '_ocr', _FakeOcr('回合 1-7'))
    assert read_phase_round(_Ctx(), None) == (1, 7)    # 前进:自愈清挂起
    monkeypatch.setattr(obs, '_ocr', _FakeOcr('回合 1-5'))
    assert read_phase_round(_Ctx(), None) == (1, 7)    # 新单帧倒退:重新首帧防抖


def test_phase_round_reset_clears_suspect(monkeypatch) -> None:
    """新局 reset 同步清回退修正确认态(防跨局复用)。"""
    import sr_od.application.currency_war.obs.cw_observation as obs
    monkeypatch.setattr(obs, '_phase_round_suspect', {'value': (1, 5), 'count': 1})
    obs.reset_phase_round_cache()
    assert obs._phase_round_suspect is None


# ==================== gold_settle_gate ====================


class _RecordingLog:
    """替身 logger:记录 warning 调用(真实 log_utils 写全局文件,不便断言)。"""

    def __init__(self):
        self.warnings: list[str] = []

    def warning(self, msg, *args):
        self.warnings.append(msg % args if args else msg)

    def info(self, msg, *args):
        pass


class _FakeController:
    """按序吐预置帧的假控制器(screenshot() 返回队列头,空则复用末帧)。"""

    def __init__(self, frames):
        self.frames = list(frames)

    def screenshot(self):
        return self.frames.pop(0) if self.frames else self.frames[-1] if self.frames else None


class _GoldCtx:
    def __init__(self, controller=None):
        self.controller = controller


# ===== read_gold_settled 稳定门 =====


def test_gold_settled_no_controller_single_read(monkeypatch):
    """无控制器(离线/单测)→ 单帧读原值,不轮询(行为与修前一致)。"""
    reads = iter([75])
    monkeypatch.setattr(observation, 'read_gold_opt', lambda ctx, screen: next(reads))
    assert observation.read_gold_settled(_GoldCtx(controller=None), None) == 75


def test_gold_settled_static_two_frames_agree(monkeypatch):
    """静止屏:第二帧一致 → 直接采信(无冲突行、无告警)。"""
    monkeypatch.setattr(observation, 'read_gold_opt', lambda ctx, screen: 60)
    conflicts: list[tuple] = []
    monkeypatch.setattr(observation, 'obs_conflict', lambda *a, **kw: conflicts.append(a))
    monkeypatch.setattr(observation, 'time', type('T', (), {'sleep': staticmethod(lambda s: None)}))
    ctx = _GoldCtx(controller=_FakeController([None, None, None]))
    assert observation.read_gold_settled(ctx, None) == 60
    assert conflicts == []


def test_gold_settled_ticking_takes_last_and_conflicts(monkeypatch):
    """漂移帧复现锁:首帧 75(入账前)→ 末帧 115(入账后)= 实机 P3 r1 漂移序列。

    采末帧 + obs_conflict 留证(不静默给错值:采了哪个值判读侧可见)。
    """
    monkeypatch.setattr(observation, 'read_gold_opt',
                        lambda ctx, screen: ctx.controller.screenshot())
    conflicts: list[tuple] = []
    monkeypatch.setattr(observation, 'obs_conflict', lambda *a, **kw: conflicts.append(a))
    monkeypatch.setattr(observation, 'time', type('T', (), {'sleep': staticmethod(lambda s: None)}))
    ctx = _GoldCtx(controller=_FakeController([75, 115, 115]))
    assert observation.read_gold_settled(ctx, None) == 115, '计数器在跳时取末帧(入账后真值)'
    assert len(conflicts) == 1
    assert conflicts[0][0] == 'gold' and conflicts[0][1] == 75 and conflicts[0][2] == 115


def test_gold_settled_ticking_timeout_still_takes_last(monkeypatch):
    """计数器跳满补采窗仍未停 → 仍取末帧并留证(不无限轮询)。"""
    seq = iter([75, 90, 100, 110])
    monkeypatch.setattr(observation, 'read_gold_opt', lambda ctx, screen: next(seq))
    conflicts: list[tuple] = []
    monkeypatch.setattr(observation, 'obs_conflict', lambda *a, **kw: conflicts.append(a))
    monkeypatch.setattr(observation, 'time', type('T', (), {'sleep': staticmethod(lambda s: None)}))
    ctx = _GoldCtx(controller=_FakeController([]))
    assert observation.read_gold_settled(ctx, None) == 110
    assert len(conflicts) == 1


# ===== gold_delta 分级告警 =====


def _run_conflict(monkeypatch, tmp_path, old, new):
    """跑一次真实 obs_conflict(落盘指到 tmp_path),返回告警行列表。"""
    fake_log = _RecordingLog()
    monkeypatch.setattr(obs_mod, '_log', fake_log)
    monkeypatch.setattr(obs_mod, '_CONFLICT_JOURNAL', tmp_path / 'conf.jsonl')
    obs_mod.obs_conflict('gold_delta', old, new, None,
                         verdict='留证-动作账vs读数不等', source='shop_spend_audit')
    return fake_log.warnings


def test_gold_delta_big_gap_alarms(monkeypatch, tmp_path):
    """|gap|>10 → warning 告警行(检索锚 [cw!][alarm][gold_delta]),W489 实测大额漂移 39→79。"""
    warns = _run_conflict(monkeypatch, tmp_path, 39, 79)
    assert len(warns) == 1
    assert '[cw!][alarm][gold_delta]' in warns[0]
    assert 'gap=40' in warns[0]


def test_gold_delta_small_gap_stays_evidence_only(monkeypatch, tmp_path):
    """|gap|≤10 维持留证不告警(边界 gap=10 不告警,gap=11 告警)。"""
    assert _run_conflict(monkeypatch, tmp_path, 5, 7) == []
    assert _run_conflict(monkeypatch, tmp_path, 32, 42) == []
    warns = _run_conflict(monkeypatch, tmp_path, 32, 44)
    assert len(warns) == 1 and '[cw!][alarm][gold_delta]' in warns[0]


def test_gold_delta_none_values_no_alarm(monkeypatch, tmp_path):
    """非数值(None 等)不告警也不崩(best-effort hook 契约)。"""
    assert _run_conflict(monkeypatch, tmp_path, None, 20) == []


# ===== 3 位数金读取能力锁(漂移方向防线) =====


def test_gold_opt_reads_3_digit_value():
    """历史帧锁:备战帧 3 位数金(201)完整读出,不被裁成 2 位。

    帧 = sr-od-test/screens/currency_war/gold_3digit_prep.png(实机备战屏存档,
    离线回放 read_gold_opt=201;防未来 area 收紧/OCR 回归把 3 位数金读低 ——
    W489 漂移方向即「金被读低」)。
    """
    from one_dragon.base.geometry.rectangle import Rect
    from one_dragon.base.matcher.ocr.ocr_service import OcrService
    from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher
    from one_dragon.utils import cv2_utils as cvu

    screen = cvu.read_image(str(_TEST_REPO / 'screens/currency_war/gold_3digit_prep.png'))
    assert screen is not None

    class _A:
        def __init__(self, name, rect):
            self.area_name = name
            self.pc_rect = rect

    class _SI:
        area_list = [_A('文本-金币数', Rect(1610, 890, 1690, 945))]

    class _Loader:
        def get_screen(self, screen_name):
            return _SI()

    class _Ctx:
        def __init__(self):
            self.ocr_service = OcrService(OnnxOcrMatcher())
            self.screen_loader = _Loader()

    ctx = _Ctx()
    ctx.ocr_service.ocr_matcher.init_model()
    v = observation.read_gold_opt(ctx, screen)
    assert v == 201, f'3 位数金被误读为 {v}(裁首位/OCR 回归)'


# ==================== r404_ignition_order ====================


def test_ignition_gain_semantics() -> None:
    """点火增量:恰好凑满体系 tier 的那张=1;冗余/无关=0。"""
    dep = {'仙舟': 2, '持续伤害': 2}
    # 第3仙舟 → 仙舟3 点火
    assert ignition_gain({'仙舟'}, dep) == 1
    # 第4仙舟(已 3) → 冗余
    assert ignition_gain({'仙舟'}, {'仙舟': 3}) == 0
    # 列车第2人 → 列车2 点火
    assert ignition_gain({'列车同行'}, {'列车同行': 1}) == 1
    # 无关节
    assert ignition_gain({'欢愉'}, dep) == 0


def test_ignition_beats_redundant_target() -> None:
    """r404-A1 探针④:vacancy=1,点火 rest 件 > 冗余 tgt 件。"""
    bench = [
        BenchChar(char_id='三月七', faction='列车同行', slot=1),  # 点火
        BenchChar(char_id='彦卿', faction='仙舟', slot=2),        # 冗余tgt
        BenchChar(char_id='赛飞儿', faction='夜之半神', slot=3),
    ]
    deployed_fac = {'仙舟': 3, '减益': 1, '星核猎手': 1,
                    '持续伤害': 2, '列车同行': 1, '夜之半神': 1}
    up, _ = select_deployments(
        bench, deployed_cids={'藿藿', '丹恒·饮月', '爻光', '椒丘', '卡芙卡'},
        deployed_fac=deployed_fac, board=dict(deployed_fac), cap=6,
        target_factions=frozenset({'仙舟', '持续伤害'}))
    assert up and bench[up[0]].char_id == '三月七', \
        '点火件(列车第2人)应先于冗余第4仙舟'


def test_ignition_in_target_sorts_first() -> None:
    """tgt 内部:点火件排首(探针①:爻光第3仙舟最优先)。"""
    bench = [
        BenchChar(char_id='爻光', faction='仙舟', slot=1),
        BenchChar(char_id='彦卿', faction='仙舟', slot=2),  # 同tgt冗余
    ]
    up, _ = select_deployments(
        bench, deployed_cids={'藿藿', '丹恒·饮月'},
        deployed_fac={'仙舟': 2, '持续伤害': 2},
        board={'仙舟': 2, '持续伤害': 2}, cap=6,
        target_factions=frozenset({'仙舟'}))
    assert up and bench[up[0]].char_id == '爻光'


def test_locked_line_core_beats_ignition_filler() -> None:
    """W65/ADR-0323:cap 竞争(1 空位)时锁定线核心(target_cores)优先于
    点火过渡件——旧序 ignite_rest 压 tgt,三月七(列车1→2 点火)先占坑,
    万敌(ig0)被挤留 bench(W64 seed 13 r5 形态);修后「同 cap 内先核心
    后填充」([21] 变阵窗口语义),不扩 cap。"""
    bench = [
        BenchChar(char_id='三月七', faction='列车同行', slot=1),  # 点火过渡件
        BenchChar(char_id='万敌', faction='夜之半神', slot=2),    # 锁定线核心(ig0)
    ]
    deployed_fac = {'列车同行': 1, '夜之半神': 1}
    up, _ = select_deployments(
        bench, deployed_cids={'藿藿', '丹恒·饮月', '爻光', '卡芙卡', '桑博'},
        deployed_fac=deployed_fac, board=dict(deployed_fac), cap=6,
        target_factions=frozenset({'夜之半神', '燃血'}),
        target_cores=frozenset({'万敌', '千冶·刃'}))
    assert up and bench[up[0]].char_id == '万敌', \
        '锁定线核心(target_cores)应先于点火过渡件(同 cap 内先核心后填充)'
