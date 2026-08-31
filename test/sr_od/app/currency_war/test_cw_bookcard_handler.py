"""书册卡处理链(HandleBookcard)测试。

锁四件事:
① 默认策略 choose_expert_index 判据(主力阵营同线 → 在场阵营同线 → 现金为王
   -1;board 空/读数失败走兜底;并列计数取名字序首个保证确定性);
② 书册卡模板在位判定(文件存在 + find_bookcards 灰度 TM 自检命中);
③ 专家邀请函弹窗画面注册(UPPER_SCREENS → 弹窗在场 = 非备战帧);
④ 停机钩子 → 自动处理链的接线锁(battle_loop/prep_director)。


出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / 'src'))

import numpy as np  # noqa: E402

from one_dragon.base.geometry.rectangle import Rect  # noqa: E402
from sr_od.application.currency_war.operations.handlers.handle_bookcard import (  # noqa: E402
    choose_expert_index,
)

# ===== ① 默认策略判据 =====


def test_policy_dominant_faction_match() -> None:
    """主力阵营同线优先:board 仙舟3(最大)→ 选仙舟卡(实机首例 2026-08-30 背书)。"""
    bonds = ['贝洛伯格', '星核猎手', '星核猎手', '仙舟']
    board = {'仙舟': 3, '持续伤害': 2, '击破': 1}
    assert choose_expert_index(bonds, board) == 3


def test_policy_secondary_faction_match() -> None:
    """无主力同线 → 退而选任一在场阵营同线的卡(凑档边际仍正)。"""
    bonds = ['贝洛伯格', '星核猎手', None, '仙舟']
    board = {'星核猎手': 1, '追击': 2}   # 主力=追击,无卡同线;星核猎手在场
    assert choose_expert_index(bonds, board) == 1


def test_policy_no_match_cash_fallback() -> None:
    """全无同线 → -1(现金为王经济兜底,不引入板外新阵营)。"""
    assert choose_expert_index(['贝洛伯格', '星核猎手'], {'仙舟': 3}) == -1


def test_policy_empty_board_cash_fallback() -> None:
    """board 空(读数失败)→ -1:选卡无依据时经济兜底优于盲选。"""
    assert choose_expert_index(['仙舟'], {}) == -1
    assert choose_expert_index([], {'仙舟': 3}) == -1


def test_policy_tie_deterministic() -> None:
    """并列最大计数取名字序首个(确定性,防跨轮抖动)。"""
    bonds = ['仙舟', '狼狩', None, None]
    board = {'仙舟': 2, '狼狩': 2}
    assert choose_expert_index(bonds, board) == 0   # sorted 后「仙舟」<「狼狩」


# ===== ② 书册卡模板在位判定 =====

_SLOTS = [Rect(382, 845, 495, 979), Rect(507, 844, 620, 978)]


def test_bookcard_template_loadable() -> None:
    """模板文件在位且可加载(灰度非 None);换名/移动路径即红。"""
    from sr_od.application.currency_war.obs import cw_identity_obs as cio
    assert cio._get_bookcard_gray() is not None


def test_find_bookcards_hits_pasted_template() -> None:
    """灰度 TM 自检:模板贴进槽位画布 → find_bookcards 命中该槽(检测链通路)。"""
    from sr_od.application.currency_war.obs import cw_identity_obs as cio
    tm = cio._get_bookcard_gray()
    assert tm is not None
    canvas = np.full((1080, 1920, 3), 40, dtype=np.uint8)
    rect = _SLOTS[1]
    h, w = tm.shape[:2]
    x = rect.x1 + (rect.x2 - rect.x1 - w) // 2
    y = rect.y1 + (rect.y2 - rect.y1 - h) // 2
    canvas[y:y + h, x:x + w, :] = tm[:, :, None]   # 灰度贴 3 通道画布(find_bookcards 内部自转灰度)
    hits = cio.find_bookcards(canvas, list(enumerate(_SLOTS, 1)))
    assert [i for i, _ in hits] == [2], f'slot2 应命中,实得 {[i for i, _ in hits]}'


# ===== ③④ 注册与接线锁 =====


def test_invite_screen_registered_as_upper() -> None:
    """邀请函弹窗进 UPPER_SCREENS:弹窗在场 = 非备战帧(环不在弹窗上做备战动作)。"""
    from sr_od.application.currency_war.kernel import cw_obs_core
    assert '货币战争-备战-专家邀请函' in cw_obs_core.UPPER_SCREENS


def test_bookcard_handler_wired() -> None:
    """停机钩子 → 自动处理链接线:battle_loop 引用 HandleBookcard,
    prep_director 弹窗 bail 清单含 bookcard 标签。"""
    import inspect

    from sr_od.application.currency_war import prep_director
    from sr_od.application.currency_war.kernel.cw_overlay_registry import (
        derive_decision,
    )
    from sr_od.application.currency_war.operations import battle_loop
    assert 'HandleBookcard' in inspect.getsource(battle_loop)
    # bail 扫描单一源已收拢至 registry(B 面切换):成员判定改为派生集三元组
    assert ('货币战争-备战-专家邀请函', '标识-专家邀请函', 'bookcard') in {
        (s.screen_name, s.anchor_area, s.bail_tag) for s in derive_decision()}
