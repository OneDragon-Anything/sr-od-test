"""按排羁绊聚合 API(契约包 C6 契约 1)单帧锁测试(W38)。

验收(对应 C6「验收测试想法」1):
- 正/反例板面聚合与手算对拍(含多羁绊角色每系都计、流派羁绊);
- 开拓者形态按当前排归一(W21 #13 口径:前台=记忆/后台=欢愉,换排后羁绊随之变);
- 未识别角色 faction 兜底 / '?' 不计(与 ``_recount_board`` 口径一致);
- 全板合计视图 = front+back 之和(total 恒不丢计数)。

单一源反查(验收 2,grep 全仓无第二处按排聚合)是 review 项,不进测试。
"""
from sr_od.application.currency_war.kernel.cw_board_by_row import (
    BoardByRow,
    board_by_row,
    board_by_row_of,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState


def _char(name: str, slot: int = 0, row: str = 'back',
          char_id: str | None = None, faction: str | None = None) -> BenchChar:
    """直构 BenchChar(char_id/faction 可覆写——开拓者/未识别用例不走注册表)。"""
    return BenchChar(slot=slot, char_id=char_id if char_id is not None else name,
                     faction=faction if faction is not None else '?',
                     position_pref=row)


# ---------- 1. 正例:双排板面聚合与手算对拍 ----------

def test_front_back_split_matches_hand_count():
    """手算板面:三月七/饮月前排,桑博/卡芙卡后排。

    注册表真值(cw_chars):
    - 三月七 = 列车同行 + 护盾(流派);
    - 丹恒·饮月 = 仙舟、列车同行(多羁绊每系都计)+ 战技点;
    - 桑博 = 贝洛伯格、星间旅人 + 持续伤害(流派);
    - 卡芙卡 = 星核猎手 + 持续伤害。
    """
    deployed = [
        _char('三月七', slot=1, row='front'),
        _char('丹恒·饮月', slot=2, row='front'),
        _char('桑博', slot=1, row='back'),
        _char('卡芙卡', slot=2, row='back'),
    ]
    b = board_by_row(deployed)
    assert b.front == {'列车同行': 2, '护盾': 1, '仙舟': 1, '战技点': 1}
    assert b.back == {'贝洛伯格': 1, '星间旅人': 1, '持续伤害': 2, '星核猎手': 1}
    # 全板合计视图 = 两排之和(契约明示的第三视图)
    assert b.total() == {
        '列车同行': 2, '护盾': 1, '仙舟': 1, '战技点': 1,
        '贝洛伯格': 1, '星间旅人': 1, '持续伤害': 2, '星核猎手': 1,
    }


def test_total_is_sum_of_rows_never_loses_count():
    """total 恒等于 front+back 逐标签求和(不丢计数;未知排值计后排)。"""
    deployed = [
        _char('希儿', slot=1, row='front'),
        _char('符玄', slot=1, row='back'),
        _char('桑博', slot=2, row='weird'),   # 异常排值 → 后排(聚合口径)
    ]
    b = board_by_row(deployed)
    for tag in set(b.front) | set(b.back):
        assert b.total()[tag] == b.front.get(tag, 0) + b.back.get(tag, 0)
    assert b.count('量子同频') == 2      # 希儿+符玄(合计视图不分排)
    assert b.count('量子同频', 'front') == 1
    assert b.count('量子同频', 'back') == 1
    assert b.row('front') is b.front


# ---------- 2. 开拓者形态按当前排归一(W21 #13 口径) ----------

def test_trailblazer_form_normalized_by_current_row():
    """欢愉形态拖上前排 → 归一成记忆(欢愉羁绊消失,能量/列车保留);反排同理。

    注册表:开拓者·记忆 = 列车同行 + 能量;开拓者·欢愉 = 列车同行 + 能量、欢愉。
    """
    b = board_by_row([_char('开拓者·欢愉', slot=1, row='front')])
    assert b.front == {'列车同行': 1, '能量': 1}
    assert '欢愉' not in b.total()          # 前排没有欢愉(形态已归一)

    b2 = board_by_row([_char('开拓者·记忆', slot=1, row='back')])
    assert b2.back == {'列车同行': 1, '能量': 1, '欢愉': 1}   # 后台独有欢愉


def test_trailblazer_base_name_normalizes_too():
    """基名「开拓者」(未带形态后缀)同样按排归一。"""
    b = board_by_row([_char('开拓者', slot=1, row='front')])
    assert b.front == {'列车同行': 1, '能量': 1}


# ---------- 3. 未识别角色兜底 / 空板 ----------

def test_unknown_char_falls_back_to_faction_field():
    """char_id 未识别 → 按 BenchChar.faction 计一个标签;空/'?' 不计
    (与 ``_recount_board`` 口径一致)。"""
    b = board_by_row([
        _char('', slot=1, row='front', faction='仙舟'),
        _char('', slot=2, row='back', faction='?'),
        _char('', slot=3, row='back', faction=''),
    ])
    assert b.front == {'仙舟': 1}
    assert b.back == {}


def test_empty_board_gives_empty_aggregate():
    b = board_by_row([])
    assert b.front == {} and b.back == {} and b.total() == {}
    assert board_by_row(None) == BoardByRow()    # None 防御 = 空聚合


def test_board_by_row_of_state_convenience():
    st = GameState()
    st.deployed = [_char('希儿', slot=1, row='front')]
    assert board_by_row_of(st).count('贝洛伯格') == 1
    assert board_by_row_of(st).count('量子同频', 'front') == 1
