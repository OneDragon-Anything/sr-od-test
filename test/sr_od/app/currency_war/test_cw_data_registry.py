"""装备识别与身份真值锚主题锁(obs 域;2026-09-12 data 域解体批改题)。

2026-09-12 拆分:本文件原为「数据/标定族」杂物抽屉——data 表四种合同
(引用完整/值域守恒/派生一致/登记门 + plaza 快照对拍)已迁
``test_cw_data_tables.py``;公式路由/CV 探针帧 → test_cw_obs_layout /
test_cw_obs_ground_truth;等级 XP 反推 → test_cw_obs_safety_semantics。
本文件现役主题 = **装备识别与身份真值锚**(read_equipped_below /
identify_slots / find_tomes / find_supply_boxes / read_star / below-icon
diff / owned-order 管线计算 / layout 钩子降级),待装备识别主题批再归并。

判据(用户三次递进裁定):保留核四类——①读取正确性直接喂决策的真值锚
(每生产分支 1 行)②金钱净守恒 ③fail-closed 拒绝 ④入口 smoke;登记门
每文件 ≤1。事故背书不再是保留理由(实机对账+sim 已兜底);
被砍测试 git 可复活。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils import cv2_utils
from sr_od.application.currency_war.data import cw_synthesis as synth
from sr_od.application.currency_war.data.cw_chars import (
    CHARACTERS,
    chars_by_cost,
)
from sr_od.application.currency_war.obs.cw_equipment import EQUIPMENT_ROSTER
from test.conftest import SrTestContext

_REPO_ROOT = Path(__file__).resolve().parents[5]   # 仓库根(StarRailOneDragon)
_TEST_ROOT = Path(__file__).resolve().parents[4]   # 测试仓根(sr-od-test)
FIXTURES = _TEST_ROOT / 'screens' / '货币战争-备战'  # 备战屏 fixture 目录



# ==================== equipment ====================

from sr_od.application.currency_war.obs.cw_equipment import (  # noqa: E402
    _owned_order_anomaly,
    load_equip_tm_grays,
    read_equipped_below,
)
from sr_od.application.currency_war.obs.cw_identity_obs import (  # noqa: E402
    avatar_to_below,
)

_EQUIP_DIR = _REPO_ROOT / 'assets' / 'template' / 'currency_war' / 'equip_legacy'

# icon 固定 ~32px(98px×scale0.33),不随装备数变(D-49);half_w=70 覆盖3件横排跨度。
_GT_FEIXIAO_3 = {'光能电池', '步步生花', '武器大师'}  # 飞霄3件(D-49 CV 验全中)
_GT_FEIXIAO_2 = {'步步生花', '折叠小刀'}  # 飞霄2件(轮滑鞋+生命之花合成步步生花)
_FRONT1 = Rect(677, 329, 810, 467)  # screen_info 前排-1 avatar rect


def test_owned_order_row_wrap_not_anomaly() -> None:
    """换行跳变 ≠ 跳格(live 2026-08-18 10:45/10:47 实锤回归):row1 两件 +
    row2 两件,行尾→行首 x 大跳(220 vs 行内 78)是正常布局 —— 旧欧氏全局中位
    每逢跨行必误报;新行内判定放行。"""
    # live 10:47 实测坐标形态:row1(冶金炉 1785,163 / 拆装扳手 1836,172),
    # row2 两件(cy ~260+,x 1836/1785 同列)
    pts = [(1785, 163), (1836, 172), (1836, 261), (1785, 268)]
    assert _owned_order_anomaly(pts) is None


def test_owned_order_real_gap_in_row_detected() -> None:
    """行内真跳格检出:同行 4 个 x,中段空一格(51×2=102 > 1.8×51)→ 报。"""
    xs = (1836, 1785, 1734, 1632)   # 第三→第四间距 102,中位 51
    pts = [(x, 170) for x in xs]
    anomaly = _owned_order_anomaly(pts)
    assert anomaly is not None and '跳格' in anomaly


@pytest.fixture(scope='module')
def equip_grays():
    """98px TM 模板(全装备);模块内复用。"""
    return load_equip_tm_grays(_EQUIP_DIR)


def test_read_equipped_front_feixiao_3(test_context: SrTestContext, equip_grays) -> None:
    """飞霄前排-1(3件态):read_equipped_below = {光能电池,步步生花,武器大师}。

    D-49 核心:icon 固定 ~32px,3件全中(0.745-0.802@scale0.33),推翻 D-48「3件分辨率墙」。
    half_w=70 覆盖3件横排(cx±43),55 会切边缘 icon(步步生花漏)。
    """
    if not test_context.has_screen('货币战争-备战', 'equipped_front1_feixiao_3'):
        pytest.skip('fixture equipped_front1_feixiao_3 未采')
    screen = test_context.load_screen('货币战争-备战', 'equipped_front1_feixiao_3')
    out = read_equipped_below(screen, equip_grays, [(1, avatar_to_below(_FRONT1))])
    assert set(out.get(1, [])) == _GT_FEIXIAO_3


def test_read_equipped_front_feixiao_2(test_context: SrTestContext, equip_grays) -> None:
    """飞霄前排-1(2件态):read_equipped_below = {步步生花,折叠小刀}。"""
    if not test_context.has_screen('货币战争-备战', 'equipped_front1_feixiao_2'):
        pytest.skip('fixture equipped_front1_feixiao_2 未采')
    screen = test_context.load_screen('货币战争-备战', 'equipped_front1_feixiao_2')
    out = read_equipped_below(screen, equip_grays, [(1, avatar_to_below(_FRONT1))])
    assert set(out.get(1, [])) == _GT_FEIXIAO_2


def test_read_equipped_back6_feixiao_3(test_context: SrTestContext, equip_grays) -> None:
    """后排-6(cx1316 最右)飞霄3件:read_equipped_below = {光能电池,步步生花,武器大师}。

    D-51(已修):icon 尺寸随位置变(梯形视角:前排~32px/后排最右~34px)。武器大师后排-6 best scale=0.35
    val0.601,step 0.03 漏 0.35(0.36=0.481)致漏检;scales 加 0.35 后全中。非裁切/遮挡(pi+用户确认无遮挡)。
    """
    if not test_context.has_screen('货币战争-备战', 'equipped_back6_feixiao_3'):
        pytest.skip('fixture equipped_back6_feixiao_3 未采')
    screen = test_context.load_screen('货币战争-备战', 'equipped_back6_feixiao_3')
    out = read_equipped_below(screen, equip_grays, [(6, avatar_to_below(Rect(1245, 600, 1386, 739)))])
    assert set(out.get(6, [])) == _GT_FEIXIAO_3


def test_read_equipped_front_feixiao_0(test_context: SrTestContext, equip_grays) -> None:
    """飞霄前排-1(0件/裸装):read_equipped_below = 空(无假阳性)。

    验证空装备槽 below-avatar 无 icon → 不误识别(防 VLM 误判空槽有装备;D-38/D-45 教训:以 CV 为准)。
    """
    if not test_context.has_screen('货币战争-备战', 'equipped_front1_feixiao_0'):
        pytest.skip('fixture equipped_front1_feixiao_0 未采')
    screen = test_context.load_screen('货币战争-备战', 'equipped_front1_feixiao_0')
    out = read_equipped_below(screen, equip_grays, [(1, avatar_to_below(_FRONT1))])
    assert out.get(1, []) == []  # 裸装:无装备 icon,不误识别


def test_read_equipped_back_multi_positions(test_context: SrTestContext, equip_grays) -> None:
    """后排多 cx(2/3/5)多件数(3/1/1):avatar_to_below 后排各 cx 通用(一张图多角色)。

    drag 多前排角色到后排同图:后排-2(cx747 飞霄3件)/后排-3(cx888 减益星徽)/后排-5(cx1174 治疗星徽)。
    与 test_read_equipped_back_feixiao_3(后排-1/4)合证后排 1-5 各 cx 通用(D-49)。
    """
    if not test_context.has_screen('货币战争-备战', 'equipped_back_235'):
        pytest.skip('fixture equipped_back_235 未采')
    screen = test_context.load_screen('货币战争-备战', 'equipped_back_235')
    below = [
        (2, avatar_to_below(Rect(679, 600, 814, 739))),   # 后排-2 cx747
        (3, avatar_to_below(Rect(823, 600, 953, 739))),   # 后排-3 cx888
        (5, avatar_to_below(Rect(1106, 600, 1241, 739))),  # 后排-5 cx1174
    ]
    out = read_equipped_below(screen, equip_grays, below)
    assert set(out.get(2, [])) == _GT_FEIXIAO_3
    assert set(out.get(3, [])) == {'减益星徽'}
    assert set(out.get(5, [])) == {'治疗星徽'}


def test_below_icon_diff_detects_equip(test_context: SrTestContext) -> None:
    """equip_all CV-diff 验穿(D-56):飞霄 0→1→2→3 件连续态 below-icon diff >> 阈值,同态 ~0。

    ``equip_all._below_icon_diff``(R19 avatar-slot CV-diff,替 count-verify)验 drag 是否落地穿。
    fixture ``equipped_front1_feixiao_0/1/2/3``(front-1 飞霄 0→3 件顺序态):加 icon 的连续态
    diff 应远 > ``BELOW_DIFF_THRESHOLD``(8.0),同态 ~0。offline 验证验穿逻辑可靠(剩 live drag 待游戏条件)。
    """
    from sr_od.application.currency_war.operations.cw_op.cw_op_equip_all import (
        CwOpEquipAll,
        _below_icon_diff,
    )
    if not test_context.has_screen('货币战争-备战', 'equipped_front1_feixiao_0'):
        pytest.skip('fixture equipped_front1_feixiao_0/1/2/3 未采')
    states = [test_context.load_screen('货币战争-备战', f'equipped_front1_feixiao_{i}') for i in range(4)]
    avatar_x = CwOpEquipAll.FRONT_AVATAR_FALLBACK[0].x    # front-1 avatar x=743(坐标单一源整改:主源=screen_info 前排-N 派生,常量为兜底)
    thr = CwOpEquipAll.BELOW_DIFF_THRESHOLD              # 8.0
    for i in range(3):                                # 连续态(加 icon)→ diff >> 阈值
        d = _below_icon_diff(states[i], states[i + 1], avatar_x,
                             CwOpEquipAll.BELOW_ICON_Y, CwOpEquipAll.BX_HALF, CwOpEquipAll.BY_HALF)
        assert d > thr, f'{i}→{i + 1} 加 icon 应 diff > {thr},实际 {d:.1f}'
    # 同态 → ~0(无变化)
    assert _below_icon_diff(states[0], states[0], avatar_x,
                            CwOpEquipAll.BELOW_ICON_Y, CwOpEquipAll.BX_HALF, CwOpEquipAll.BY_HALF) < thr


def test_empty_slots_skips_occupied() -> None:
    """equip_all P0-2 占位检测(``_empty_slots``):已穿槽跳过,只返空槽(1-based)。

    ``read_row_equipped`` 返 ``{slot_idx: [装备名]}``(1-based);槽不在 dict = 空。
    全空 → 全槽;部分已穿 → 跳过;全已穿 → 空(op 应停)。
    修原 bug:``target=FRONT_AVATARS[equipped]`` 按已穿计数索引 → 已穿槽被覆盖。
    """
    from sr_od.application.currency_war.operations.cw_op.cw_op_equip_all import (
        _empty_slots,
    )
    assert _empty_slots({}, 4) == [1, 2, 3, 4]                            # 全空 → 全槽
    assert _empty_slots({1: ['x']}, 4) == [2, 3, 4]                       # slot1 已穿 → 跳过
    assert _empty_slots({1: ['x'], 3: ['y']}, 4) == [2, 4]                # 多个已穿 → 跳过对应
    assert _empty_slots({1: ['x'], 2: ['y'], 3: ['z'], 4: ['w']}, 4) == []  # 全已穿 → 空(停)


def test_select_layout_no_complete_returns_empty() -> None:
    """D-61: 无完整1/2/3件布局(单件落非合法候选)→ 返 [](不返 fallback 候选,防空槽误匹配)。

    完美投影仪 val0.62 单件落 +21 候选(2件布局右位,缺 -21)= 无完整布局 → 误检,返空。
    修前返 fallback ``[完美投影仪]``(D-61 实测 front_equips 假阳);修后返 ``[]``。
    另验合法 1件{0} 仍返该件(修不破坏合法路径)。
    """
    import numpy as np

    from sr_od.application.currency_war.obs.cw_equipment import _select_equipped_layout
    dummy = np.zeros((100, 200, 3), dtype=np.uint8)
    rect = Rect(0, 0, 200, 100)
    cx = 100
    # 单件落 +21(非合法 1件{0}/2件{±21}完整)→ 无完整布局 → 返 [](D-61 修)
    assert _select_equipped_layout([('完美投影仪', 0.62, cx + 21)], cx, 2, dummy, rect) == []
    # 合法 1件落 0 → 返 [该件](修不破坏合法路径)
    assert _select_equipped_layout([('和平手枪', 0.80, cx)], cx, 1, dummy, rect) == ['和平手枪']


# ==================== tome/box 真值帧 ====================

from sr_od.application.currency_war.obs import cw_identity_obs as cio  # noqa: E402

# 备战栏-1..9 pc_rect(assets/game_data/screen_info/currency_war_battle_prep.yml;
# 与 cw_identity_obs._ctx_slots 同一坐标系的离线硬编码,同 find_supply_boxes 分层约定)
SLOTS = [
    Rect(382, 845, 495, 979), Rect(507, 844, 620, 978), Rect(632, 844, 743, 978),
    Rect(757, 845, 869, 979), Rect(882, 846, 995, 980), Rect(1004, 847, 1118, 978),
    Rect(1132, 846, 1244, 977), Rect(1256, 845, 1368, 979), Rect(1379, 844, 1493, 980),
]
_IDX = list(enumerate(SLOTS, 1))

_FRAME_GOLD = FIXTURES / 'shop_closed_lowhp.webp'      # slot1/7 金卡典籍 + slot4/9 银箱


def _slots(screen: np.ndarray) -> list[tuple[int, Rect]]:
    """1080p 整帧校验 + 带槽号 rect 对(防 fixture 尺寸漂移静默错位)。"""
    assert screen.shape[:2] == (1080, 1920), f'真值帧应为 1080p,实得 {screen.shape}'
    return _IDX


@pytest.fixture(scope='module')
def gold_frame() -> np.ndarray:
    img = cv2_utils.read_image(str(_FRAME_GOLD))
    assert img is not None, f'真值帧缺失:{_FRAME_GOLD}'
    return img


def test_gold_card_slots_hit_tomes(gold_frame) -> None:
    """slot1/slot7 金票券卡必须被 find_tomes 命中(旧模板在 slot7 被 shape 守卫
    判盲 → 箱模板低分接走 → 误判为箱)。"""
    tomes = cio.find_tomes(gold_frame, _slots(gold_frame))
    tome_slots = {idx for idx, _ in tomes}
    assert {1, 7} <= tome_slots, f'金卡典籍槽应命中,实得 {sorted(tome_slots)}'


def test_silver_box_slots_not_tomes(gold_frame) -> None:
    """银箱槽(slot4/9)互斥判定必须走箱:箱命中且不被认成典籍。"""
    boxes = cio.find_supply_boxes(gold_frame, _slots(gold_frame))
    tomes = cio.find_tomes(gold_frame, _slots(gold_frame))
    box_slots = {idx for idx, _ in boxes}
    tome_slots = {idx for idx, _ in tomes}
    assert {4, 9} <= box_slots, f'银箱槽应报箱,实得 {sorted(box_slots)}'
    assert not ({4, 9} & tome_slots), f'银箱槽不得判典籍,实得 {sorted(tome_slots)}'


# ==================== 布局档:8 格/7 格 OCR 真值 + CV 探针 + 钩子代表 ====================

from sr_od.application.currency_war.obs.currency_war_char_id import (  # noqa: E402
    identify_character,
    load_avatar_templates,
)
from sr_od.application.currency_war.obs.cw_identity_obs import (  # noqa: E402
    identify_slots,
)

TPL_DIR = _REPO_ROOT / 'assets/template/currency_war/portrait_plaza'
# 8 格档槽位中心(狸猫局交互实拍;ADR-0281 真值布局)
_C8 = (464, 606, 748, 889, 1031, 1174, 1316, 1458)


def _slots8():
    return [(i, Rect(x - 71, 600, x + 71, 739)) for i, x in enumerate(_C8, 1)]


@pytest.fixture(scope='module')
def templates():
    return load_avatar_templates(TPL_DIR)


@pytest.fixture(scope='module')
def frame():
    return cv2_utils.read_image(str(FIXTURES / '后排8槽-狸猫局.webp'))


def test_slot8_all_positions_identified(templates):
    """全位验证 fixture(用户实机逐位拖拽,2026-08-19):位1-8 逐一识别。"""
    frame2 = cv2_utils.read_image(str(FIXTURES / '后排8槽-全位验证.webp'))
    got = {c.slot: c.char_id for c in identify_slots(frame2, templates, _slots8(), 'back')}
    assert got == {1: '藿藿', 2: '爻光', 6: '开拓者·欢愉', 7: '狸小虎', 8: '狸小龙'}, got




def test_resolve_back_slots_feeds_container(monkeypatch: pytest.MonkeyPatch):
    """back_max 语义裁决·闸门二写端锁(值源定谳 = W5 方案稿 §2.3 + 机制
    正本 board_structure.md 量化公式节):resolve_back_slots 已知帧裁决值
    随写 BoardState.back_layout(挂三信号裁决单一源,零新增读)——
    - 已建档裁决(7 = 佩佩局档)→ 容器 7、无 superset 标记(精确值);
    - 域外裁决(9 → 8 格超集运行)→ 容器 8 + evidence 'superset'
      (裁决值与坐标档分离:值=运行档 8,标记防超集近似被当精确值消费);
    - 未知态帧(公式弃权 ∧ CV 不可判)不写(宁缺勿造,容器保持上一已知值);
    - 防抖未过帧(公式弃权 ∧ CV 未建档读数 ∧ 三读不一致)不写——兜底
      运行档 8 禁以「无 superset 标记的精确值」形态入容器(落地审阻断1
      判别分支;n_raw=None 唯一对应此泄漏路径);
    - 无 session(离线/测试桩/MCP 纯读)不写。"""
    from types import SimpleNamespace

    import sr_od.application.currency_war.obs.cw_back_layout as cbl
    from sr_od.application.currency_war.kernel.cw_board_state import (
        board_state_of,
    )
    cbl.reset_layout_unknown_state()
    try:
        sess = SimpleNamespace()
        ctx = SimpleNamespace(cw_match=SimpleNamespace(session=sess))
        bs = board_state_of(sess)
        # 已建档 7 档(diff=1,screen=None → CV 通道弃权,公式单源一致)
        cbl.resolve_back_slots(ctx, None, level=7, cap=8)
        assert bs.back_layout.value == 7 \
            and bs.back_layout.evidence is None, '已建档档直读落容器,无标记'
        # 域外 9(cap9/lv6 → 公式 9)→ 运行值 8 格超集 + superset 标记
        cbl.resolve_back_slots(ctx, None, level=6, cap=9)
        assert bs.back_layout.value == 8 \
            and bs.back_layout.evidence == 'superset', \
            '域外裁决记运行档 8 + superset(裁决值 9 不入坐标域)'
        # 未知态(公式弃权 ∧ CV 不可判):不写,保持上一已知值
        cbl.resolve_back_slots(ctx, None, level=6, cap=9, level_trusted=False)
        assert bs.back_layout.value == 8 \
            and bs.back_layout.evidence == 'superset', '未知态帧不写'
        # 防抖未过(公式弃权 ∧ CV 读 9 未建档 ∧ W209h 三读不一致):
        # n_raw=None → 兜底 8 禁入容器,保持上一已知值(上一态=8+superset,
        # 值面同 8 不可分,判别位 = evidence——泄漏形态会把 superset 翻成
        # 无标记精确值)
        monkeypatch.setattr(cbl, 'cv_back_slots', lambda s: 9)
        monkeypatch.setattr(cbl, '_cv_confirm_readings',
                            lambda ctx, screen, first, formula: [9, 8, 8])
        cbl.resolve_back_slots(ctx, object(), level=6, cap=9,
                               level_trusted=False)
        assert bs.back_layout.value == 8 \
            and bs.back_layout.evidence == 'superset', \
            '防抖未过帧不写:兜底 8 禁以无标记精确值覆写容器'
        # 无 session:不写(上一已知值保持)
        cbl.resolve_back_slots(SimpleNamespace(), None, level=7, cap=8)
        assert bs.back_layout.value == 8, '无 session 形态不落容器'
    finally:
        cbl.reset_layout_unknown_state()


@pytest.fixture()
def _layout_fresh(monkeypatch, tmp_path):
    """布局选档家族共享桩前导(F8:原 17 处复制 monkeypatch 前导收敛于此,
    以此为范,防桩面漂移):
    ①模块级全局复位——未知态计数器/通道冲突节流表/选档日志(测试纪律 4:
    生产路径含模块级全局时 setup 一并桩化),用例结束再清一次防泄漏;
    ②观察冲突证据归宿装 tmp 账本 + 截图采集桩(测试纪律 2:不写真实
    .debug/)。原独立证据文件桩 ``_CONFLICT_JOURNAL`` 已随删除波 1 退役
    (cw_observe 写端收编,入库 3d4461438),证据行现归宿 = 统一 state
    账本 obs_event 行型——装配 sink + run_id 供给槽(局外行账本拒写),
    并注入 BoardState 供给 provider(该槽缺省关,不注入则证据行不落,
    与生产「无 sink 拒写」同语义)。
    yield 出账本 jsonl 路径,留证断言直接读它(obs_event 行形状:field/
    verdict 顶层,old/new/ctx 附加键内嵌 ``observed``)。"""
    import sr_od.application.currency_war.kernel.cw_observe as cobs
    import sr_od.application.currency_war.obs.cw_back_layout as cbl
    from sr_od.application.currency_war.kernel import (
        cw_state_journal,
        cw_telemetry_exit,
    )
    from sr_od.application.currency_war.kernel.cw_board_state import (
        board_state_of,
    )
    cbl.reset_layout_unknown_state()
    journal = tmp_path / 'state' / 'journal.jsonl'
    cw_state_journal.install_state_telemetry(
        journal, flush_every=1, run_id_provider=lambda: 'run-layout-hook')
    bs = board_state_of(None)
    monkeypatch.setattr(cw_telemetry_exit, '_obs_event_board_provider',
                        lambda: bs)
    monkeypatch.setattr(cobs, 'cw_shot_unique', lambda img, label: f'{label}.png')
    monkeypatch.setattr(cbl, '_channel_conflict_ts', {})
    monkeypatch.setattr(cbl, '_last_sel_log', None)
    yield journal
    cw_state_journal.reset_state_telemetry()
    cbl.reset_layout_unknown_state()




# ===== 7. 佩佩局真 7 格板面识别(2026-08-26 用户口述真值;ADR-0389/0390) =====
# 识别层三件:①现场变体模板(raw_board.png,真窗口采——错位残片变体会致
# live_only 假阴,万敌@s2 丢读实证后全量重采);②佩佩入库(roster cost=0
# + raw.png);③相邻幽灵去重 + 部署排门槛 15。
# 几何(ADR-0390):7 格=整排居中重排 中心 534..1386(旧记 604..1458 错位
# +71px 已勘误;错位时代的「假阳带/弱命中/幽灵」全族伪象随真窗口消失)。

_C7 = (534, 676, 818, 960, 1102, 1244, 1386)   # 居中重排(ADR-0390;排中心恒 960)


def _slots7():
    return [(i, Rect(x - 71, 600, x + 71, 739)) for i, x in enumerate(_C7, 1)]


def test_pepe_board_truth_current(templates):
    """佩佩局当前帧(用户口述真值):1=万敌/3=乱破/5=卡芙卡/7=佩佩,
    2/4/6 空。**生产参数**(min15+live_only);真窗口下空槽全库 0 假阳、
    残影幽灵自然消失(错位窗口时代的伪象,ADR-0390 勘误)。"""
    fix = cv2_utils.read_image(str(FIXTURES / '后排7槽-佩佩局-拖测后.png'))
    got = {c.slot: c.char_id for c in identify_slots(
        fix, templates, _slots7(), 'back', min_inliers=15, live_only=True,
        center_gate=True)}
    assert got == {1: '万敌', 3: '乱破', 5: '卡芙卡', 7: '佩佩'}, got


def test_true_grid_empty_slots_zero_baseline(templates):
    """真窗口空槽零假阳锁(ADR-0390 勘误后):全库对空槽(2/4/6)最高内点
    应为 0(错位时代的 11-26 假阳带=邻卡残影伪影,已消)。"""
    fix = cv2_utils.read_image(str(FIXTURES / '后排7槽-佩佩局-拖测后.png'))
    for cx in (676, 960, 1244):
        crop = fix[600:739, cx - 71:cx + 71]
        _, inliers = identify_character(crop, templates, min_inliers=1)
        assert inliers == 0, f'空槽@{cx} 出非零本底 {inliers}(假阳带回流)'


def test_pepe_roster_and_template(templates):
    """佩佩建档三面:立绘模板在库;roster cost=0(系统召唤单位);deploy
    候选剔除(不可拖,同狸猫对)。"""
    assert '佩佩' in templates
    from sr_od.application.currency_war.data.cw_chars import get_char
    ch = get_char('佩佩')
    assert ch is not None and ch.cost == 0
    from sr_od.application.currency_war.kernel.cw_state import BenchChar
    from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
        exclude_system_units,
    )
    out = exclude_system_units([BenchChar(slot=7, char_id='佩佩'),
                                BenchChar(slot=1, char_id='万敌')])
    assert [c.char_id for c in out] == ['万敌']




# ===== layout 钩子代表(CUT8:布局留证/停机降级族只留此 1 行)=====

def test_layout_hook_no_stop_only_evidence(
        test_context, templates, _layout_fresh, monkeypatch, frame):
    """降级锁(7 格建档后语义):n_raw 未建档(用 9 模拟未来新档,
    CV 三读稳定)→ **不停机**,落 back_layout_unarchived_grid 留证(带公式/
    CV/防抖序列),无 flag 文件;真实 7 格(diff==1)已建档 → 见
    test_layout_hook_silent_on_archived。"""
    import json as _json

    import sr_od.application.currency_war.kernel.cw_obs_core as core
    import sr_od.application.currency_war.obs.cw_back_layout as cbl
    import sr_od.application.currency_war.obs.cw_identity_obs as cio
    import sr_od.application.currency_war.obs.cw_observation as cwo
    ctx = test_context

    class _FakeRunCtx:
        stopped = False
        stop_calls: list[str] = []

        def stop_running(self, reason: str = ''):
            self.stopped = True
            self.stop_calls.append(reason)

    monkeypatch.setattr(ctx, 'run_context', _FakeRunCtx())
    monkeypatch.setattr(core, 'is_prep_like_frame', lambda c, s: True)
    monkeypatch.setattr(cio, '_session_level', lambda c: 8)
    # 公式 8(lv8 cap10 diff2)且 CV 三读稳定 9(防抖过)→ n_raw=9 未建档
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda c, s, level=None: 10)
    monkeypatch.setattr(cbl, 'cv_back_slots', lambda s: 9)
    monkeypatch.setattr(ctx, 'screenshot', lambda: frame, raising=False)
    out = cio.read_deployed_chars(ctx, frame, templates, level=8)
    assert isinstance(out, list) and out                    # 读板照常不抛
    assert not ctx.run_context.stopped and not ctx.run_context.stop_calls, \
        'W209i:未建档档不得停机(实时制游戏停 bot 不停游戏,run 27 实证)'
    journal = _layout_fresh
    assert journal.exists(), '降级后必须留证'
    rec = _json.loads(journal.read_text(encoding='utf-8').strip().splitlines()[-1])
    assert rec['row'] == 'obs_event' and rec['field'] == 'back_layout_unarchived_grid'
    assert rec['observed']['old'] == 9 and rec['observed']['cv_readings'] == [9, 9, 9]
    assert '不停机' in rec['verdict']                        # 如实声明画面可能推进
    assert not (journal.parents[1] / '.debug/temp/currency_war/back_layout_stop_hook.flag').exists(), \
        '停机 flag 机制已废弃不得回流'


# ==================== test_star3_positions ====================

from sr_od.application.currency_war.kernel.cw_obs_core import _area_rect  # noqa: E402
from sr_od.application.currency_war.obs.cw_identity_obs import read_star  # noqa: E402

_SLOTS = [f'前排-{i}' for i in range(1, 5)] + [f'后排-{i}' for i in range(1, 7)] \
    + [f'备战栏-{i}' for i in range(1, 10)]
_FIX_DIR = _TEST_ROOT / 'screens' / 'star3_slots'


def _load_truth() -> dict[str, dict[str, int]] | None:
    p = _FIX_DIR / 'truth.json'
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding='utf-8'))


def test_star3_full_frame_truth(test_context: SrTestContext) -> None:
    """层2(全帧校验):每张 fixture 全部 19 槽位与真值表一致(361 校验点)。

    真值 = 采集时同帧其余槽位的真实星级(2星占位角色/1星/空槽 fallback=1)。
    防 read_star 在非 3 星槽上的回归(此前只测过目标位)。
    """
    sr_ctx = test_context
    truth = _load_truth()
    if truth is None:
        pytest.skip('truth.json 缺(先跑 star3_truth_gen.py)')
    fixes = sorted(_FIX_DIR.glob('*.webp'))
    assert fixes, 'star3_slots/ fixture 缺'
    rects = {s: _area_rect(sr_ctx, s, '货币战争-备战') for s in _SLOTS}
    checked = 0
    for fix in fixes:
        row = truth.get(fix.stem)
        assert row is not None, f'{fix.stem} 不在 truth.json'
        img = cv2_utils.read_image(str(fix))
        for slot, expected in row.items():
            rect = rects.get(slot)
            assert rect is not None, f'{slot} area 缺'
            got = read_star(img[rect.y1:rect.y2, rect.x1:rect.x2])
            assert got == expected, (
                f'{fix.stem}/{slot}: 真值 {expected} 实得 {got}(read_star 回归)')
            checked += 1
    assert checked >= 19 * 15, f'校验点异常少: {checked}(应≈361)'


# ==================== K8 闭合锁(自 test_cw_synthesis.py 逐字迁入) ====================

if __name__ == '__main__':
    pytest.main([__file__])
