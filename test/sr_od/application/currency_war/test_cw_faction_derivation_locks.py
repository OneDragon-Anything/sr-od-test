"""faction 三类注册表派生口径锁(benchchar-retirement design §2.1)。

faction/position_pref 不入容器形状,消费点经注册表按 char_id 派生,三类
消费口径(§2.1):
- 类2 板面阵营计数/体系卡身份:注册表派生,未知名 = '?'(不计);
- 类3 羁绊(按排聚合 board_by_row):行归属 + 注册表派生,开拓者形态归一
  随迁(前排=记忆/后排=欢愉,design §3 不变量 5 的计数侧承载体)。

锁面:
① board_by_row 容器行输入:排归属 = 行入参(前排/后排分桶),多羁绊角色
   每系都计,total = 两行之和;
② 开拓者形态按排归一(防御性再归一):前排槽携带后台形态 id 时按前排
   形态取羁绊(欢愉不计),后排照旧;
③ 未知名/注册表无羁绊名 = 零标签(未知 '?' 不计);
④ 类2 体系卡 _faction_count:身份计数(board_by_row)与 board OCR 兜底
   取 max;未知名不进身份计数;
⑤ char_first_faction 派生式(主阵营单一源):命中 → factions[0],
   注册但无阵营 = '',未注册/空名 = '?'。
"""
from __future__ import annotations

from sr_od.application.currency_war.data.cw_chars import char_first_faction
from sr_od.application.currency_war.kernel.cw_board_by_row import (
    board_by_row,
    board_by_row_of,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    GameState,
    Unit,
)


def _unit(cid: str, slot: int, star: int = 1) -> Unit:
    return Unit(char_id=cid, star=star, equips=[], slot=slot)


def _gs(front: list[Unit] | None = None,
        back: list[Unit] | None = None,
        board: dict[str, int] | None = None) -> GameState:
    from sr_od.application.currency_war.kernel.cw_game_state import ChannelSig
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    _sig = ChannelSig(family='obs', actor='CwScreenPrep')
    if front is not None:
        gs.observe(gs.front_row, list(front), sig=_sig)
    if back is not None:
        gs.observe(gs.back_row, list(back), sig=_sig)
    if board is not None:
        gs.observe(gs.board, dict(board), sig=_sig)
    return gs


# ===== ① 行域输入:排归属 + 多羁绊计数 + 合计 =====

def test_board_by_row_rows_bucket_and_multibond_count():
    """前排/后排分桶按行入参;多羁绊角色(桑博=贝洛伯格+星间旅人+持续伤害)
    每系都计;total = 两行之和。"""
    bb = board_by_row([_unit('桑博', 1), _unit('希儿', 2)],
                      [_unit('三月七', 1)])
    assert bb.front == {'贝洛伯格': 2, '星间旅人': 1, '持续伤害': 1,
                        '量子同频': 1}, '前排逐系计数(希儿=贝洛伯格+量子同频)'
    assert bb.back == {'列车同行': 1, '护盾': 1}, '后排逐系计数'
    assert bb.total() == {'贝洛伯格': 2, '星间旅人': 1, '持续伤害': 1,
                          '量子同频': 1, '列车同行': 1, '护盾': 1}
    assert bb.count('列车同行') == 1 and bb.count('列车同行', 'back') == 1 \
        and bb.count('列车同行', 'front') == 0


# ===== ② 开拓者形态按排归一(计数侧) =====

def test_board_by_row_trailblazer_row_normalization():
    """开拓者形态归一随迁(design §3 不变量 5 计数侧):前排槽携带后台
    形态 id(欢愉)→ 按前排形态(记忆)取羁绊——列车同行计入、欢愉不计;
    后排槽携带后台形态照旧计欢愉。"""
    bb = board_by_row([_unit('开拓者·欢愉', 1)],   # 直构未归一态(防御域)
                      [_unit('开拓者·欢愉', 1)])
    assert bb.front == {'列车同行': 1, '能量': 1}, \
        '前排按记忆形态取羁绊(欢愉不计)'
    assert bb.back == {'列车同行': 1, '能量': 1, '欢愉': 1}, \
        '后排按欢愉形态取羁绊'


# ===== ③ 未知名/无羁绊名 = 零标签 =====

def test_board_by_row_unknown_and_bondless_names_not_counted():
    """未注册名(='?' 口径)与注册表无阵营无流派名(白厄,独立羁绊不进
    板面阵营计数)都不产生标签;空行 = 空聚合。"""
    bb = board_by_row([_unit('无名氏', 1), _unit('白厄', 2), _unit('', 3)],
                      [])
    assert bb.front == {} and bb.back == {} and bb.total() == {}


# ===== ④ 类2:体系卡 _faction_count(身份 × board OCR 取 max)=====

def test_system_card_faction_count_identity_and_board_max():
    """身份计数 = board_by_row 全板合计(注册表派生);board OCR 缺漏时
    身份侧兜判,身份缺漏时 OCR 侧兜判(取 max 容错,判激活侧)。"""
    from sr_od.application.currency_war.kernel.cw_system_cards import (
        SYSTEM_CARDS,
        card_active,
    )
    # 身份侧 2 列车(board OCR 未写)→ train2 激活(身份兜判)
    gs = _gs(front=[], back=[_unit('三月七', 1), _unit('姬子', 2)])
    assert card_active(SYSTEM_CARDS['train2'], gs), \
        '身份计数 2/2 → 列车卡激活'
    # 未知名不进身份计数:1 真列车 + 1 未知名 → 未激活
    gs2 = _gs(front=[], back=[_unit('三月七', 1), _unit('无名氏', 2)])
    assert not card_active(SYSTEM_CARDS['train2'], gs2), \
        '未知名(? 口径)不进身份计数'
    # OCR 侧兜判:板面 OCR 报 2 而身份侧 1(重建缺身份)→ 仍激活(max 容错)
    gs3 = _gs(front=[], back=[_unit('三月七', 1)], board={'列车同行': 2})
    assert card_active(SYSTEM_CARDS['train2'], gs3), \
        'board OCR 兜判取 max(漏判激活比多判更伤)'


# ===== ⑤ 主阵营派生式(§2.1 单一源)=====

def test_char_first_faction_derivation():
    """主阵营派生:命中 → factions[0];注册但无阵营登记 = '';未注册/
    空名 = '?'(与退役换形层派生式逐位同值)。"""
    assert char_first_faction('三月七') == '列车同行'
    assert char_first_faction('白厄') == ''
    assert char_first_faction('无名氏') == '?'
    assert char_first_faction('') == '?'


# ===== 便捷入口:容器直读聚合 =====

def test_board_by_row_of_reads_container_rows():
    """board_by_row_of(gs) = deployed_rows_of 现读 + 聚合(便捷入口同口径)。"""
    gs = _gs(front=[_unit('希儿', 1)], back=[_unit('桑博', 1)],
             board={'贝洛伯格': 99})   # board 字段不进行域(行域现读)
    bb = board_by_row_of(gs)
    assert bb.front == {'量子同频': 1, '贝洛伯格': 1}
    assert bb.back == {'贝洛伯格': 1, '星间旅人': 1, '持续伤害': 1}
    assert bb.count('贝洛伯格') == 2
