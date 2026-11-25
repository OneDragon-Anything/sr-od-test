"""忘却之庭-编队画面结构化识别测试(fixture = screens/忘却之庭-编队/ 实机帧)。

锁设计约定(见 src/sr_od/application/treasures_lightward/obs/tl_team_obs.py 模块 docstring):
- tab 态判别驱动左侧列表分支(角色列表→网格 / 预设编队→队伍绑组),右侧槽位始终识别;
- 头像识别诚实歧义:置信门槛 + 歧义比不足时返回候选集不硬猜(真值须落候选内);
- 空槽判定(平均 V 门槛)—— 空队伍帧槽位全 empty。

身份真值 = 2026-11-04 实机帧探针标定(槽位 SIFT + 视觉仲裁一致)。
"""

from __future__ import annotations

import pytest
from test.conftest import SrTestContext

from sr_od.application.treasures_lightward.obs.tl_team_obs import (
    MemberGuess,
    collect_tl_team_info,
)

_SCREEN = '忘却之庭-编队'


def _collect(ctx: SrTestContext, state: str):
    if not ctx.has_screen(_SCREEN, state):
        pytest.skip(f'存档截图缺失:screens/{_SCREEN}/{state}.webp')
    return collect_tl_team_info(ctx, ctx.load_screen(_SCREEN, state))


def _names(guess: MemberGuess) -> set[str]:
    """候选 ∪ 置信结论的名字集合(歧义格断言用)。"""
    names = {name for name, _ in guess.candidates}
    if guess.char is not None:
        names.add(guess.char)
    return names


def test_character_list_tab_empty_slots(test_context: SrTestContext) -> None:
    """角色列表 tab + 空队伍帧:tab 分支、关卡信息、波次(弱点+空编队)。"""
    view = _collect(test_context, '编队屏-角色列表')
    assert view.left_tab == '角色列表'
    assert view.character_grid is not None
    assert view.preset_teams is None
    assert view.stage_name is not None and view.stage_name.startswith('物竞天择')
    assert view.environment_text is not None and '笑点' in view.environment_text
    joined = ''.join(view.star_targets)
    assert '10' in joined and '20' in joined and '无法战斗' in joined
    # 该帧关卡 = 物竞天择其十,2 节点(弱点真值 2026-11-04 实机帧,视觉仲裁)
    assert len(view.nodes) == 2
    assert [n.node_idx for n in view.nodes] == [1, 2]
    assert view.nodes[0].weaknesses == ['虚数', '火']
    assert view.nodes[1].weaknesses == ['量子', '冰']
    for node in view.nodes:
        for member in node.members:
            assert member.empty, f'空队伍帧不应识别出头像: {member}'


def test_character_grid_first_row(test_context: SrTestContext) -> None:
    """网格几何与首行身份(列表按等级排序,当日内稳定)。"""
    view = _collect(test_context, '编队屏-角色列表')
    grid = view.character_grid
    assert grid is not None and len(grid) == 16
    by_pos = {(cell.row, cell.col): cell for cell in grid}
    assert '爻光' in _names(by_pos[(0, 0)].guess)
    assert '丹恒•腾荒' in _names(by_pos[(0, 1)].guess)
    assert '海瑟音' in _names(by_pos[(0, 2)].guess)
    assert '波提欧' in _names(by_pos[(0, 3)].guess)


def test_preset_tab_teams_binding(test_context: SrTestContext) -> None:
    """预设编队 tab:4 卡绑组返回;成员身份按探针真值断言(歧义格查候选集)。"""
    view = _collect(test_context, '编队屏-预设编队')
    assert view.left_tab == '预设编队'
    assert view.preset_teams is not None
    assert view.character_grid is None
    teams = view.preset_teams
    assert len(teams) == 4
    assert [t.team_idx for t in teams] == [1, 2, 3, 4]
    for team in teams:
        assert len(team.members) == 4
    t1, t2, t3, t4 = teams
    # 卡1 = 大丽花/飞霄/加拉赫/知更鸟(第4格小头像歧义,真值不落候选 → 只断非空)
    assert '大丽花' in _names(t1.members[0])
    assert '飞霄' in _names(t1.members[1])
    assert _names(t1.members[2]) & {'加拉赫', '灵砂'}
    assert not t1.members[3].empty
    # 卡2 = 黑塔/知更鸟/布洛妮娅/停云
    assert '黑塔' in _names(t2.members[0])
    assert _names(t2.members[1]) & {'知更鸟', '白厄'}
    assert '布洛妮娅' in _names(t2.members[2])
    assert '停云' in _names(t2.members[3])
    # 卡3 = 黄泉/加拉赫/银狼/花火(加拉赫小头像歧义,查候选)
    assert '黄泉' in _names(t3.members[0])
    assert _names(t3.members[1]) & {'加拉赫', '灵砂'}
    assert '银狼' in _names(t3.members[2])
    assert '花火' in _names(t3.members[3])
    # 卡4 = 遐蝶/风堇/缇宝/长夜月(全高置信)
    assert '遐蝶' in _names(t4.members[0])
    assert '风堇' in _names(t4.members[1])
    assert '缇宝' in _names(t4.members[2])
    assert '长夜月' in _names(t4.members[3])


def test_applied_slots_filled(test_context: SrTestContext) -> None:
    """预设已应用帧:节点绑定(弱点+编队)真值 + 槽1第4位空槽(角色冲突被自动撤下)。"""
    view = _collect(test_context, '编队屏-预设编队-已应用')
    assert view.left_tab == '预设编队'
    assert len(view.nodes) == 2
    n1, n2 = view.nodes
    assert [g.char for g in n1.members] == ['大丽花', '飞霄', '加拉赫', None]
    assert n1.members[3].empty
    assert [g.char for g in n2.members] == ['黑塔', '知更鸟', '布洛妮娅', '停云']
    # 该帧关卡 = 物竞天择其一(弱点真值 2026-11-04 实机帧,视觉仲裁)
    assert n1.weaknesses == ['雷']
    assert n2.weaknesses == ['虚数', '物理']
