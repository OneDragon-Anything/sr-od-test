"""ESC 清零批(2026-09-08)自有测试锁:退局链零 ESC 三锁。

ESC-4 落地审条件 F1 的三条锁(落地审批报告出处暂记,行为正本 = 持久索引:
cw_entry_exit.py 文件头与各分支注释、docs/game/screens/currency_war_
interrupt_dialog.md、runtime-ops「运行坑」ESC 绝对禁令)。三锁分工:
① 源级禁 ESC 墓碑——cw_entry_exit.py 全文零 ESC 发射形态,红 = 回潮
  (此前的行为级否定墓碑只覆盖撤退分支,回填 btn_tap('esc') 照样全绿);
② OVERLAY_ACTION_MAX 梯子算术——overlay 未命中场景恰 5 次动作后
  round_fail,不多不少,fail 文案算术与常量同源;
③ yml 中心锁——门形「按钮-退出对局」建档中心 =(61,63)±2、goto 边含
  中断挑战弹窗,防建档漂移(先例 = test_invest_strategy_confirm_area_
  onboarded 直读 yml 形态)。
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

from one_dragon.base.operation.operation_round_result import (
    OperationRoundResultEnum,
)
from sr_od.application.currency_war.operations.cw_entry.cw_entry_exit import (
    CwEntryExit,
)
from test.conftest import SrTestContext
from test.harness.fixture_controller import fast_sleep

# 主仓根(src/ 所在):yml/源码扫描锚定,不依赖 pytest 运行 CWD
_MAIN_REPO = Path(__file__).resolve().parents[5]


# ==================== 锁① 源级禁 ESC 墓碑 ====================

# ESC 发射形态(全文扫描,含大小写变体):
# - 引号包住的 esc 字面量:btn_tap('esc') / key_tap("ESC") / 键名映射 'esc'
# - .esc 属性/枚举访问(controller.esc(...) / Key.esc)
# 注释与文案里的裸「ESC」叙述(如「零 ESC」「ESC 已禁用」)不是发射,不入模式;
# 全文扫描不剔注释 = 墓碑从宽(引用旧 ESC 写法的注释也该被看见再删)。
_ESC_TOMBSTONE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"['\"]esc['\"]", re.IGNORECASE),
    re.compile(r'\.esc\b', re.IGNORECASE),
)


def test_entry_exit_source_has_zero_esc_emission() -> None:
    """源级墓碑锁:cw_entry_exit.py 全文零 ESC 发射形态,红 = ESC 回潮。

    出处:ESC 清零批(2026-09-08)把备战/overlay 两处 ESC 换建档点击
    (替代依据见该文件头与各分支注释;ESC 禁令 = runtime-ops「运行坑」:
    ESC 语义随画面漂移,无面板时落备战误弹中断挑战弹窗)。缺失场景 =
    有人回退实现补回 btn_tap('esc'),既有行为测试全绿也必须在此红。
    """
    src_file = Path(inspect.getsourcefile(CwEntryExit))
    assert src_file is not None and src_file.exists(), 'CwEntryExit 源文件定位失败'
    src = src_file.read_text(encoding='utf-8')
    for pattern in _ESC_TOMBSTONE_PATTERNS:
        hit = pattern.search(src)
        assert hit is None, (
            f'cw_entry_exit.py 出现 ESC 发射形态 {pattern.pattern!r}'
            f'(命中 {hit.group(0)!r})——该通道已随 ESC 清零批退役,'
            f'回潮 = 违反 runtime-ops ESC 绝对禁令,须改建档点击'
        )


# ==================== 锁② OVERLAY_ACTION_MAX 梯子算术 ====================


def test_overlay_action_ladder_exact_max_then_fail(
    test_context: SrTestContext,
) -> None:
    """梯子算术锁:overlay 未命中场景恰 OVERLAY_ACTION_MAX 次动作后 round_fail。

    出处:overlay 兜底分支自带上界(依据 = cw_entry_exit.py OVERLAY_ACTION_MAX
    字段注释:定向点击后分支每轮重命中、不计尾部 _miss_rounds,success 边
    循环不消耗节点 retry 预算,必须自带计数上界)。构造 = act 桩恒 True
    (动作已发但画面未推进 = overlay 未命中,分支下轮重命中),直调
    _overlay_branch 复现「分支自命中但动作无效」形态。

    断言:①前 MAX 次调用每次发 1 个动作并 WAIT(交画面推进);②第 MAX+1 次
    调用在发动作**之前** fail(动作数恰 = MAX,不多不少——fail 那次再发动作
    = off-by-one);③fail 文案「连续 {MAX} 次」与常量同源推导(文案算术
    streak-1);④键隔离:耗尽的子态键不影响另一子态键的独立预算。
    红 = 梯子算术被改(off-by-one / 上界失效 → success 边死循环复发)。
    """
    max_actions = CwEntryExit.OVERLAY_ACTION_MAX
    # 钉死设计值:上界数值本身是 ESC 清零批语义(≤5 次动作 ≈10s+ 慢转场余量),
    # 改值 = 设计变更,须同步重推本锁断言与 fail 文案算术,禁机械跟绿
    assert max_actions == 5, (
        f'OVERLAY_ACTION_MAX 设计值 = 5,现值 {max_actions}——改值须重推'
        f'梯子算术锁与 fail 文案算术(esc4 落地审 §4 核实口径)'
    )

    op = CwEntryExit(test_context)
    act_calls: list[str] = []

    def _act() -> bool:
        act_calls.append('click')
        return True   # 点击已发但浮层未关 = 未命中,分支下轮重命中

    results: list[OperationRoundResultEnum] = []
    fail_status: str | None = None
    with fast_sleep():   # round_wait(wait=2) 的轮间等待在测试环境纯属空转
        for _ in range(max_actions + 2):   # 多调 2 次:双向夹出恰一次 fail
            r = op._overlay_branch('补给阶段', _act)
            if r.result == OperationRoundResultEnum.FAIL:
                fail_status = r.status
                break
            results.append(r.result)

    assert len(results) == max_actions, (
        f'前 {max_actions} 次调用应全 WAIT、第 {max_actions + 1} 次 fail,'
        f'实际 WAIT {len(results)} 次(结果序={[r.name for r in results]})')
    assert results == [OperationRoundResultEnum.WAIT] * max_actions, (
        f'动作未生效期间每次都该 WAIT(交画面推进重观察),实际={results}')
    assert len(act_calls) == max_actions, (
        f'恰 {max_actions} 次动作(不多不少),实际 {len(act_calls)} 次——'
        f'fail 那次调用不得再发动作(动作先于上界判定 = off-by-one)')

    # fail 文案算术与常量同源:第 MAX+1 次调用时 streak=MAX+1,文案报 streak-1=MAX
    assert fail_status is not None, '第 MAX+1 次调用应以 FAIL 收口'
    assert f'连续 {max_actions} 次' in fail_status, (
        f'fail 文案应含「连续 {max_actions} 次」(streak-1 算术,落地审 §4'
        f' off-by-one 核验口径),实际文案={fail_status!r}')

    # 键隔离:按 overlay 子态键独立计数,耗尽的键不吞别的子态预算
    # (必须同入 fast_sleep 窗口:本轮 round_wait(wait=2) 在加速窗外走真睡,
    # 实测 4×0.5s 切片 = 恰 2s/call,白付慢桶成本)
    with fast_sleep():
        r_other = op._overlay_branch('遭遇其一', _act)
    assert r_other.result == OperationRoundResultEnum.WAIT, (
        f'另一子态键首轮应 WAIT(独立预算),实际={r_other.result}')
    assert len(act_calls) == max_actions + 1, (
        f'另一子态键首轮应发 1 次动作,实际动作总数 {len(act_calls)}')


# ==================== 锁③ yml 中心锁(防建档漂移)====================


def test_exit_door_area_center_and_goto_edge_onboarded() -> None:
    """建档中心锁:门形「按钮-退出对局」中心 =(61,63)±2,goto 边含中断挑战弹窗。

    出处:ESC 清零批退局发起 = 点备战左上门形图标替代旧 ESC(两入口实测 =
    docs/game/screens/currency_war_interrupt_dialog.md,手动链点左上
    ~(100,70) 落本 area 热区右缘)。中心是退局链的唯一点击落点——建档
    rect 漂移会让点击落空(门分支每轮重命中烧梯子预算至 fail)或误触相邻
    「按钮-敌人难度」(rect x≥95 与本 area 有重叠条带史,点它弹敌方信息
    浮层)。goto 边 = 「点门 → 弹窗」转场语义的建档声明半边,漂移 = 转场
    语义失真。锚值 (61,63) 独立于 yml(外部门形图标实测读数),非自证。
    """
    import yaml

    from one_dragon.base.geometry.rectangle import Rect

    p = (_MAIN_REPO / 'assets' / 'game_data' / 'screen_info'
         / 'currency_war_battle_prep.yml')
    with open(p, encoding='utf-8') as f:
        d = yaml.safe_load(f)
    areas = {a['area_name']: a for a in d['area_list']}
    assert '按钮-退出对局' in areas, (
        '货币战争-备战应有「按钮-退出对局」area(退局发起唯一落点,'
        '删除 = 退局链 fail-closed 常态红)')
    rect = Rect(*areas['按钮-退出对局']['pc_rect'])
    c = rect.center
    assert abs(c.x - 61) <= 2 and abs(c.y - 63) <= 2, (
        f'门形图标中心应 =(61,63)±2,实际 ({c.x:.0f},{c.y:.0f})——'
        f'漂移先对相邻「按钮-敌人难度」rect(左缘 95,重叠条带史)'
    )
    goto = areas['按钮-退出对局'].get('goto_list') or []
    assert '货币战争-中断挑战弹窗' in goto, (
        f'goto_list 应含「货币战争-中断挑战弹窗」(点门 → 弹窗转场边),'
        f'实际={goto}')
