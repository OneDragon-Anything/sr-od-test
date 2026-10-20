"""结算屏「获得金币总览」面板息行读数测试(镜像 src =
obs/cw_settlement_obs.py 的息行解析族 + 来源 B/C 推算单一源;同文件
既有读数测试 = operations/cw_op/test_settle.py〔存量非镜像位,只读〕,
本文件按 src 镜像规范落位)。

测试面依据 = 迭代 T-27 公司契约利息累计触发设计(v2.3 定稿)§2.5 + §4.8①②:
- **真帧锁**(fixture = window_batch 批 h_004_012710 有息 / h_004_084253
  无息整帧 webp 提交测试仓,走生产读链 = 建档 area 裁剪 + 放大 OCR):
  有息帧息值/行序(基础奖励/利息/连胜,息在连胜之上)、无息帧息行整行
  缺席 = 零值形态;
- **纯函数三态**(合成 token 面):面板锚不在 → None 不计数;息行在
  数值失读 → None(0 是合法读数不冒认);标签粘连数值形态;
- **推算公式锁**(§4.8②,来源 B/C 计数单一源):息 = interest(基座金,
  resolved cap) + flat,策略经注册表名注入;基座 None → None 宁缺;
  买断制 cap 0 不被真值折叠(买断制+狸财经狸 = 每节点 2)。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import cw4_box

from one_dragon.utils import cv2_utils
from sr_od.application.currency_war.kernel.cw_economy import (
    DEFAULT_INTEREST_CAP,
    interest,
)
from sr_od.application.currency_war.kernel.cw_game_state import ChannelSig
from sr_od.application.currency_war.obs.cw_settlement_obs import (
    estimate_node_interest,
    parse_settle_coin_overview,
    parse_settle_interest,
    read_settle_gold_opt,
    read_settle_interest_panel,
)

FIXTURES = Path(__file__).parent / 'fixtures'
_FIX_INTEREST2 = FIXTURES / 'settle_coin_panel_interest2.webp'
_FIX_INTEREST0 = FIXTURES / 'settle_coin_panel_interest0.webp'

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')


def test_settle_interest_panel_real_frames(test_context) -> None:
    """真帧锁(T-27 设计 §4.8①):有息帧息值 2、无息帧息行整行缺席 =
    0(锚在)。两帧各 OCR 一次(慢计算共享)。fixture 缺失 skip 不
    error(缺帧恢复自动转绿)。

    断言面刻意只锁息值两态(计数判据本体):面板分量行(总览/基础/
    连胜金额)的 det 可读率随 provider(DML/CPU)与帧浮动(实测同一帧
    两环境可读集不同),不作跨环境断言面——行序铁证(基础/利息/连胜)
    由 fixture 帧本体存档承载,闭合校验在消费端是留证面非计数门
    (T-27 设计 §2.5)。"""
    if not _FIX_INTEREST2.exists() or not _FIX_INTEREST0.exists():
        pytest.skip(f'结算息行 fixture 缺失: {FIXTURES}')
    # 有息帧(1-2 奖励胜局,总览 7 = 基础 4 + 息 2 + 连胜 1;实拍行序
    # = 基础/利息/连胜,息在连胜之上)
    img2 = cv2_utils.read_image(str(_FIX_INTEREST2))
    items2 = read_settle_interest_panel(test_context, img2)
    assert parse_settle_interest(items2) == 2, '息行读数(标签+独立数值形态)'
    assert any('金币总览' in (getattr(it, 'data', '') or '')
               for it in items2), '面板锚在(读链前置态)'
    # 无息帧(1-1 奖励胜局,息 0 息行整行缺席)
    img0 = cv2_utils.read_image(str(_FIX_INTEREST0))
    items0 = read_settle_interest_panel(test_context, img0)
    assert parse_settle_interest(items0) == 0, '锚在息行缺席 = 零值形态'


def test_settle_interest_parse_synthetic_states() -> None:
    """纯函数三态(合成 token 面,T-27 设计 §4.8①):面板锚不在 → None
    不计数;息行在数值失读 → None(宁缺,0 是合法读数不冒认);标签
    粘连数值形态(「利息5」)→ 5。token 属性面 = MatchResult 消费面。"""

    def _tok(data: str, x: int = 40, y: int = 0, w: int = 60, h: int = 30):
        return SimpleNamespace(data=data, x=x, y=y, w=w, h=h)

    # 锚不在(败局页/异常帧形态)→ None
    assert parse_settle_interest([]) is None
    assert parse_settle_interest([_tok('基础奖励'), _tok('利息'),
                                  _tok('2', x=1000)]) is None
    # 锚在、息行在、数值 token 缺(失读)→ None 不冒认 0
    anchor_only = [_tok('获得金币总览'), _tok('利息', y=218)]
    assert parse_settle_interest(anchor_only) is None
    # 粘连形态:标签 token 尾粘数值(「利息5」;允许夹图标类非数字)
    glued = [_tok('获得金币总览'), _tok('利息5', y=218)]
    assert parse_settle_interest(glued) == 5
    # 分量读数形态(闭合校验兜底用):三行各取右侧最近纯数字 token,
    # 「×0」次数修饰(在标签 token 内)不冒认连胜金额
    panel_full = [_tok('获得金币总览', y=17), _tok('7', x=1000, y=20),
                  _tok('基础奖励', y=119), _tok('4', x=1000, y=126),
                  _tok('连胜×0', y=320), _tok('1', x=1000, y=332)]
    assert parse_settle_coin_overview(panel_full) == \
        {'overview': 7, 'base': 4, 'streak': 1}


def test_estimate_node_interest_formula() -> None:
    """推算公式锁(T-27 设计 §4.8②,来源 B/C 计数单一源):息 =
    interest(基座金, resolved cap) + flat;策略经注册表名注入(值锚
    注册表直调,禁裸数字);基座 None → None 宁缺;买断制 cap 0 不被
    真值折叠(买断制+狸财经狸 = 每节点 2,若折叠回缺省 5 会算出 7)。"""
    gs_plain = cw4_box(gold=100, active_env='公司契约')
    assert estimate_node_interest(gs_plain, 100) == \
        interest(100, DEFAULT_INTEREST_CAP), '无策略局 = 缺省 cap 息'
    assert estimate_node_interest(gs_plain, None) is None, \
        '基座从未观察 → 宁缺'
    gs_buyout = cw4_box(gold=0, active_env='公司契约',
                        active_strategies=('买断制', '狸财经狸'))
    assert estimate_node_interest(gs_buyout, 100) == 2, \
        '买断制 cap 0(不折叠)+ 狸财经狸 flat 2'
    gs_rich = cw4_box(gold=0, active_env='公司契约',
                      active_strategies=('利息上调',))
    assert estimate_node_interest(gs_rich, 100) == 10, \
        '利息上调 resolved cap 10'


def test_settle_merged_areas_real_frames(test_context, monkeypatch) -> None:
    """结算屏退役合并后迁入 3 area 的真帧对拍(fixture = screens/货币战争-
    结算/ended+win 整帧,与 test_id_mark 同一存档通道)。

    锁面 = 战斗结算屏退役合并(同画面双登记 id_mark 撞车销案)的对拍验收:
    currency_war_battle_settle 退役、3 个消费 area 迁入 currency_war_settlement
    后,经生产读链(真实 screen_info 通道)在两真帧上读数与迁移前一致——
    右上金币存量 73(ended)/60(win);金币总览面板带含 基础奖励/利息/连胜
    词面;利息行含「利息」。yml 坐标与 cw_settlement_obs 常量改名不一致时
    本测立刻红(迁移一致性网)。controller 置 None 走离线单帧读
    (read_settle_gold_opt 声明的单测行为,不进稳定门)。fixture 缺失 skip
    不 error。真值来源:两帧人工视觉核对(73 位于右上计数区、win 帧面板
    另有掉落晶矿行不碍词面存在性)。"""
    if not (test_context.has_screen('货币战争-结算', 'ended')
            and test_context.has_screen('货币战争-结算', 'win')):
        pytest.skip('结算 ended/win 真帧 fixture 缺失')
    monkeypatch.setattr(test_context, 'controller', None)

    ended = test_context.load_screen('货币战争-结算', 'ended')
    win = test_context.load_screen('货币战争-结算', 'win')

    # 右上金币存量(生产读链:迁入 area 裁剪 + 3x 放大 OCR)
    assert read_settle_gold_opt(test_context, ended) == 73, 'ended 帧右上金币存量'
    assert read_settle_gold_opt(test_context, win) == 60, 'win 帧右上金币存量'

    for name, img in (('ended', ended), ('win', win)):
        # 金币总览面板带(生产读链:迁入 area 裁剪 + 2x 放大 OCR)词面。
        # 子串判断:连胜带 ×N 次数修饰粘连成单 token(实测「连胜×0」),
        # 词面存在性按子序列会误杀,与既有锚断言同款子串。
        items = read_settle_interest_panel(test_context, img)
        texts = [getattr(it, 'data', '') or '' for it in items]
        for word in ('基础奖励', '利息', '连胜'):
            assert any(word in t for t in texts), \
                f'{name} 帧面板带缺词面「{word}」(可读集: {texts})'
        # 利息行(迁入 area 直读:screen_info 坐标 + 裁剪 OCR)
        area = test_context.screen_loader.get_area('货币战争-结算', '结算-利息行')
        assert area is not None, '结算-利息行 area 已随迁在档'
        r = area.pc_rect
        row_items = test_context.ocr_service.get_ocr_result_list(
            image=img[r.y1:r.y2, r.x1:r.x2])
        assert any('利息' in (getattr(it, 'data', '') or '')
                   for it in row_items), f'{name} 帧利息行缺「利息」词面'
