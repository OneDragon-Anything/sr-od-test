"""主循环浮层判定序锁矩阵(P4R2 家族性返工)。

背景(第四局 P2 投资策略节点实锤):「浮层叠备战」型画面的分支若排在备战
双锚之后,浮层下的双锚透出命中 → prep bail「交回外循环」→ 外循环又落备战
→ 分发死循环(prep 是正确的发现者,缺口在外循环判定序)。本矩阵把**全部**
浮层分支的「先于备战双锚」序位一次性钉死(源码级 index 断言),新浮层
分支进 loop 时必须同步登记本矩阵(防逐个事故补)。

豁免项(非「叠备战」形态,不入序锁):\n- 无(OpeningSequence 拆解退役后,简报/投资环境已入矩阵 0r/0s 行)。
"""
import inspect

import pytest

# 序锁矩阵:分支名 → (screen, 锚 area / OCR 词, 检测方式)
# 检测方式:'area' = round_by_find_area 锚;'ocr' = round_by_ocr 词。
ORDER_MATRIX: list[tuple[str, str, str, str]] = [
    ('选择装备overlay', '货币战争-选择装备', '标识-请选择1个装备', 'area'),
    ('列车同行(选择伙伴)', '货币战争-列车同行', '标识-选择伙伴', 'area'),
    ('策划事件', '货币战争-骇入策划', '标识-我来当策划', 'area'),
    ('命运卜者强化', '货币战争-命运卜者强化', '标识-命运卜者', 'area'),
    ('位面详情overlay', '货币战争-位面详情', '标识-位面详情标题', 'area'),
    ('巨星强化', '货币战争-盛会之星', '标识-盛会之星', 'area'),
    ('遭遇节点', '货币战争-遭遇节点', '标识-遭遇节点', 'area'),
    ('未达上限警告', '货币战争-未达上限警告', '标识-未达上限警告', 'area'),
    ('投资策略', '货币战争-投资策略', '标识-请选择投资策略', 'area'),
    ('补给阶段', '货币战争-补给', '标识-补给阶段', 'area'),
    ('武装箱弹窗', '货币战争-武装箱弹窗', '标识-简易武装箱', 'area'),
    ('祈愿试炼', '货币战争-祈愿试炼', '标识-祈愿试炼', 'area'),
    ('星徽秘典', '货币战争-星徽秘典弹窗', '标识-星徽秘典', 'area'),
    ('专家邀请函', '货币战争-备战-专家邀请函', '标识-专家邀请函', 'area'),
    ('策略暗色锁定', '货币战争-备战-策略锁定', '按钮-返回投资策略选择', 'area'),
    # 排他关系(P4R3):前台无角色 → 恢复链自带重部署+验前排,不与浮层互斥。
    ('前台无角色提示', '货币战争-提示-前台无角色', '标识-无角色提示', 'area'),
    # 排他关系(P4R3,第五局 1-9 实锤):BOSS简报 ⇄ 位面过渡 共享交互文案
    # 「点击空白处继续」——互斥判据 = 「强敌」片段(is_boss_briefing_texts,
    # 误读「强敌米」鲁棒):boss 帧含共享文案时不进位面过渡(留 0p),
    # 位面过渡帧无「强敌」。两行互为排他对,删任一须同步删排他接线。
    ('BOSS简报', '货币战争-BOSS简报', '标识-强敌来袭', 'area'),
    ('位面过渡', '', '点击空白处继续', 'ocr'),
    # OpeningSequence 拆解退役(用户裁决):简报/投资环境由主循环 0r/0s 分支分发,
    # 接管局由分发器自然续走 —— 两行入矩阵钉序位(先于备战双锚)。
    ('位面简报', '货币战争-简报', '标识-本场对局首领', 'area'),
    ('投资环境', '货币战争-投资环境', '标识-投资环境', 'area'),
]


def _loop_src() -> str:
    from sr_od.application.currency_war.operations import cw_loop
    return inspect.getsource(cw_loop.CwLoop.loop)


def _prep_anchor_index(src: str) -> int:
    """备战双锚判定行 index(序锁基准 = 一切浮层分支必须先于此)。"""
    i = src.find("if (self.round_by_find_area(screen, '货币战争-备战', "
                 "'备战标识-购买经验')")
    assert i >= 0, '备战双锚判定行未找到(源码结构变更,本矩阵须同步)'
    return i


@pytest.mark.parametrize('name,screen,anchor,method', ORDER_MATRIX,
                         ids=[m[0] for m in ORDER_MATRIX])
def test_overlay_dispatch_precedes_prep_anchor(name, screen, anchor, method) -> None:
    """序锁:每个浮层分支的检测行必须先于备战双锚判定行。"""
    src = _loop_src()
    prep_i = _prep_anchor_index(src)
    # 取该锚**首次**出现(= 分支检测处;排除性引用只会更晚)
    i = src.find(anchor)
    assert i >= 0, f'{name}: 检测锚 {anchor} 不在主循环(分支被删?矩阵须同步)'
    assert i < prep_i, (
        f'{name}: 判定序落在备战双锚之后(index {i} ≥ {prep_i})——'
        f'浮层下双锚透出会抢分发 = 死循环形态(第四局投资策略节点实锤),'
        f'分支必须前移到 0 系')


def test_dissolved_opening_sequence_in_matrix() -> None:
    """退役批守卫:OpeningSequence 拆解后,开局两屏(简报/投资环境)必须
    以主循环分支承接且登记本矩阵(防「删壳忘接线」的结构性缺口)。"""
    from sr_od.application.currency_war.operations import cw_loop as cw_loop_mod
    src = inspect.getsource(cw_loop_mod)
    assert 'OpeningSequence(self.ctx)' not in src, '开局编排壳未拆解退役(仍有实例化)'
    assert 'opening_sequence import' not in src, '开局编排壳模块仍被导入'
    assert 'CwScreenBriefing(self.ctx)' in src, '位面简报分支缺失(0r)'
    assert 'CwScreenInvestEnv' in src, '投资环境分支缺失(0s)'
    assert 'CwScreenWaitOneOne' in src, '等待1-1 链缺失(退役序列终步语义承接)'
    matrix_anchors = {row[2] for row in ORDER_MATRIX}
    assert '标识-本场对局首领' in matrix_anchors and '标识-投资环境' in matrix_anchors, (
        '开局两屏未登记序锁矩阵')

def test_boss_briefing_vs_plane_transition_exclusion_wired() -> None:
    """排他对接线锁(矩阵内两行的互斥关系,P4R3):boss 简报 ⇄ 位面过渡
    共享「点击空白处继续」——位面过渡分支必须带「强敌」片段排他,否则
    boss 帧误分发 CwScreenPlaneTransition(第五局 fail 2s 无限循环实锤)。"""
    src = _loop_src()
    i_plane = src.find("self.round_by_ocr(screen, '点击空白处继续', lcs_percent=0.8)")
    assert i_plane >= 0
    # 排他在位面过渡分支体内(分支判定之后、CwScreenPlaneTransition 分发之前)
    i_excl = src.find('if _is_boss_frame(', i_plane)
    i_dispatch = src.find('CwScreenPlaneTransition(self.ctx)', i_plane)
    assert 0 < i_excl < i_dispatch, '位面过渡分支缺 boss 排他(或排他在分发之后)'
    # 判别单一源 = cw_screen_boss_briefing.is_boss_briefing_texts(CwScreenBattleWait 白名单同源)
    assert 'is_boss_briefing_texts as _is_boss_frame' in src
    from sr_od.application.currency_war.operations.cw_screen import cw_screen_battle_wait
    assert 'is_boss_briefing_texts' in inspect.getsource(cw_screen_battle_wait)
