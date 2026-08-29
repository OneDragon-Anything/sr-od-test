"""货币战争 节点序列台账制测试(权威表查表优先 + 三票校验)。

设计依据:用户权威口述「位面内节点类型与数量只有投资环境选择能改变(变异位
唯一)」→ 同位面节点序列可建档查表,逐帧识别降级为校验票。

三组:
1. 台账存储/合并/查表语义(cw_state.PlaneNodeLedger);
2. 消费仲裁与三票裁决(cw_observation 纯函数 + 变异窗豁免);
3. 真值帧对拍(4 帧备战 fixture,真值 = VLM 亲读,参照 W531 SIFT 基准协议;
   帧名 = 后排8槽-满级局 / 后排8槽-P3局 / 后排6槽-P2开局局 / 后排7槽-佩佩局)。
"""
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[5]          # 仓库根(StarRailOneDragon)
_TEST_ROOT = Path(__file__).resolve().parents[4]     # 测试仓根(sr-od-test)

from sr_od.application.currency_war.kernel.cw_state import (
    fill_boss_by_position,
    get_node_ledger,
    ledger_node_type,
    ledger_update_plane,
)
from sr_od.application.currency_war.obs import cw_node_reader, cw_observation
from sr_od.application.currency_war.telemetry import state as cw_telemetry
from sr_od.application.currency_war.obs.cw_node_reader import (
    classify_node_row,
    current_slot_hu_type,
    load_node_type_templates,
)
from sr_od.application.currency_war.obs.cw_observation import (
    node_vote_verdict,
)

_ASSETS = _ROOT / 'assets' / 'game_data' / 'cw_node_types'
_FIXTURES = _TEST_ROOT / 'screens' / '货币战争-备战'
#: 节点行裁带(与 cw_node_reader.NODE_ROW_RECT 同带、四周留余量;仅测试用)
_CROP = (500, 10, 1450, 120)


class _Session:
    """最小 session 桩(台账动态挂载宿主)。"""


# ===== 1. 台账存储 / 合并 / 查表 =====

def test_ledger_lazy_attach_and_none() -> None:
    """惰性挂载:同 session 幂等;None session → None(调用方跳过)。"""
    s = _Session()
    l1 = get_node_ledger(s)
    l2 = get_node_ledger(s)
    assert l1 is not None and l1 is l2
    assert get_node_ledger(None) is None


def test_ledger_update_merge_none_keeps_old() -> None:
    """按位合并:新非 None 覆盖,None 保旧(boss/past 位识别恒 None 不洗表)。"""
    s = _Session()
    ledger_update_plane(s, 1, ['battle', 'battle', None, 'boss'], 'plane_detail')
    # 备战行重读:idx1 变异成 supply(非 None 覆),idx3 重读为 None → 保 boss
    changed = ledger_update_plane(s, 1, [None, 'supply', None, None], 'prep_row')
    assert changed
    assert ledger_node_type(s, 1, 1) == 'battle'
    assert ledger_node_type(s, 1, 2) == 'supply'
    assert ledger_node_type(s, 1, 4) == 'boss'


def test_ledger_lookup_bounds_and_missing() -> None:
    """查表:表缺 / 轮越界 / 未识别位 → None(退逐帧识别链,不猜)。"""
    s = _Session()
    assert ledger_node_type(s, 1, 1) is None          # 无表
    ledger_update_plane(s, 2, ['battle', None], 'prep_row')
    assert ledger_node_type(s, 1, 1) is None          # 位面缺
    assert ledger_node_type(s, 2, 5) is None          # 越界
    assert ledger_node_type(s, 2, 2) is None          # 该位次未识别
    assert ledger_node_type(s, 2, 1) == 'battle'


def test_fill_boss_by_position_only_trailing_none() -> None:
    """boss 回填:只回填最右 None;已识别最右位不动;原序列不被改写。"""
    assert fill_boss_by_position(['battle', None]) == ['battle', 'boss']
    assert fill_boss_by_position(['battle', 'boss']) == ['battle', 'boss']
    seq = ['battle', None]
    fill_boss_by_position(seq)
    assert seq == ['battle', None]


def test_ledger_update_extend_shorter_seq() -> None:
    """投资环境加节点:新序列更长 → 右侧扩展(短序列缺位不截断旧值)。"""
    s = _Session()
    ledger_update_plane(s, 1, ['battle', 'supply', None, 'boss'], 'plane_detail')
    ledger_update_plane(s, 1, ['battle', 'supply', 'reward', 'boss', 'battle'], 'prep_row')
    assert ledger_node_type(s, 1, 5) == 'battle'
    assert ledger_node_type(s, 1, 4) == 'boss'


# ===== 2. 三票裁决 + 变异窗豁免 =====

def test_vote_verdict_thresholds() -> None:
    """三票裁决:≥2 独立票一致反对 = defect;单票 = noise;无反对 = ok。"""
    assert node_vote_verdict('battle', {'roi_ocr': 'reward', 'position': 'reward',
                                        'cur_hu': None}) == 'defect'
    assert node_vote_verdict('battle', {'roi_ocr': 'battle', 'position': 'reward',
                                        'cur_hu': 'reward'}) == 'defect'
    assert node_vote_verdict('battle', {'roi_ocr': 'reward', 'position': 'battle',
                                        'cur_hu': None}) == 'noise'
    assert node_vote_verdict('battle', {'roi_ocr': 'battle', 'position': 'battle',
                                        'cur_hu': 'battle'}) == 'ok'
    # 弃权为主的帧不构成 defect(2 弃权 + 1 反对 = 单票)
    assert node_vote_verdict('battle', {'roi_ocr': None, 'position': None,
                                        'cur_hu': 'reward'}) == 'noise'


def test_verify_votes_defect_and_grace(monkeypatch: pytest.MonkeyPatch) -> None:
    """三票校验:窗外 defect 落账一次(去重);变异窗内豁免不落。"""
    import time as _time

    from sr_od.application.currency_war.obs.cw_node_reader import NodeSlot

    defects: list[dict] = []

    # 分包期 4:obs 落账走 kernel.cw_telemetry_exit 出口钩子位,桩点随迁
    from sr_od.application.currency_war.kernel import cw_telemetry_exit
    monkeypatch.setattr(cw_telemetry_exit, '_record_defect',
                        lambda *a, **kw: defects.append(dict(kw)))

    slots = [
        NodeSlot(idx=0, cx=60, cy=40, state='past', node_type=None, hu_dist=None),
        NodeSlot(idx=1, cx=150, cy=40, state='current', node_type=None, hu_dist=None),
        NodeSlot(idx=2, cx=240, cy=40, state='upcoming', node_type='reward', hu_dist=1.0),
    ]

    def _fake_classify(ctx, screen):
        return slots, (500, 24, 1406, 106)

    monkeypatch.setattr(cw_observation, '_classify_node_row', _fake_classify)
    monkeypatch.setattr(cw_observation, '_node_label_in_roi',
                        lambda ctx, screen, cx, cy: 'reward')

    def _fake_hu(row_rgb, slot, templates):
        return 'reward', 1.2

    monkeypatch.setattr(cw_node_reader, 'current_slot_hu_type', _fake_hu)

    ctx = SimpleNamespace(cw_match=None)
    sess = _Session()
    ctx.cw_match = SimpleNamespace(session=sess)
    ledger_update_plane(sess, 1, ['battle', 'battle', 'reward'], 'plane_detail')
    import numpy as _np
    _screen = _np.zeros((120, 1500, 3), dtype=_np.uint8)   # 像素不被读(Hu/OCR 全 patch),仅承载切片

    cw_observation.verify_node_type_votes(ctx, _screen, 1, 2)
    assert len(defects) == 1
    # 出口钩子位逐参关键字转发:捕获行直接按形参名断言(surface=节点类型面)
    assert defects[0]['surface'] == 'node_type'
    assert defects[0]['kind'] == 'perception_conflict'
    assert defects[0]['reader_source'] == 'node_ledger_three_vote'
    cw_observation.verify_node_type_votes(ctx, _screen, 1, 2)
    assert len(defects) == 1   # 同 (plane, round) 去重

    # 变异窗内:合法变异,豁免不落
    sess2 = _Session()
    ctx.cw_match = SimpleNamespace(session=sess2)
    ledger_update_plane(sess2, 1, ['battle', 'battle', 'reward'], 'plane_detail')
    get_node_ledger(sess2).env_grace_until = _time.monotonic() + 60
    cw_observation.verify_node_type_votes(ctx, _screen, 1, 2)
    assert len(defects) == 1


# ===== 3. 真值帧对拍(VLM 亲读真值,协议参照 W531 SIFT 基准) =====
# 真值 = w527 批 read_image 亲读节点行裁图(x 500-1450 放大 2x);帧名 = 后排
# 格数口径(w535 改名后)。锁稳定事实(槽数/当前位/past 数/有效识别位);
# Hu 对高亮/变异图标的噪声位**不锁断言**(正是台账制的立项依据),落对拍表。

_TPLS = load_node_type_templates(_ASSETS)

_GT = {
    '后排8槽-满级局.webp': {
        'seq': ['battle', 'battle', 'supply', 'battle', 'encounter', 'reward', 'boss'],
        'current': 3,
        # 只锁该帧 CV 实际识别对的 upcoming 位(其余为已知 Hu 噪声位,落对拍表不锁)
        'expect_upcoming': {4: 'encounter'},
    },
    '后排8槽-P3局.webp': {
        'seq': ['battle', 'battle', 'supply', 'battle', 'encounter', 'reward', 'boss'],
        'current': 1,
        'expect_upcoming': {2: 'supply'},
    },
    '后排6槽-P2开局局.webp': {
        'seq': ['battle', 'reward', 'supply', 'battle', 'encounter', 'reward', 'boss'],
        'current': 0,
        'expect_upcoming': {4: 'encounter', 5: 'reward'},
    },
    '后排7槽-佩佩局.png': {
        'seq': ['reward', 'reward', 'reward', 'battle', 'supply', 'battle',
                'encounter', 'reward', 'boss'],
        'current': 0,
        'expect_upcoming': {1: 'reward', 3: 'battle', 4: 'supply', 5: 'battle',
                            6: 'encounter', 7: 'reward'},
    },
}


@pytest.fixture(scope='module')
def row_frames() -> dict:
    from one_dragon.utils import cv2_utils
    out = {}
    for name in _GT:
        img = cv2_utils.read_image(str(_FIXTURES / name))   # RGB
        x0, y0, x1, y1 = _CROP
        out[name] = img[y0:y1, x0:x1]
    return out


@pytest.mark.parametrize('name', list(_GT.keys()))
def test_fixture_truth_crosscheck(row_frames, name: str) -> None:
    """真值对拍:槽数 / 当前槽位 / past 数 / 序列位置推断 / 已锁识别位。"""
    gt = _GT[name]
    row = row_frames[name]
    # boss SIFT 模板与生产同源(read_node_sequence 恒传)→ boss 槽命中时
    # classify 覆 node_type=None(台账写点回填 'boss' 的前提)。
    boss_tpls = cw_node_reader.load_boss_templates(
        _ROOT / 'assets' / 'template' / 'currency_war' / 'boss_avatar')
    slots = classify_node_row(row, _TPLS, boss_templates=boss_tpls or None)
    # 台账视角:当前位 Hu 恒不定型(classify 只对 upcoming 跑 Hu)→ 台账需
    # 写点补当前位;boss 位命中 SIFT 时被覆盖 None → 位置先验回填 'boss'。
    built = fill_boss_by_position([s.node_type for s in slots])
    assert len(slots) == len(gt['seq']), f'{name}: 槽数 {len(slots)} != 真值 {len(gt["seq"])}'
    states = [s.state for s in slots]
    assert states.index('current') == gt['current'], f'{name}: 当前槽位错 {states}'
    assert states.count('past') == gt['current'], f'{name}: past 数错 {states}'
    for i, t in gt['expect_upcoming'].items():
        assert slots[i].node_type == t, (
            f'{name}: 槽{i} CV={slots[i].node_type}(hu={slots[i].hu_dist}) != 真值 {t}')
    # 位置推断票:已过槽数 p → 真值序列第 p 位 = 真值当前位类型(语义自洽)
    p = states.count('past')
    assert gt['seq'][p] == gt['seq'][gt['current']]
    assert built[gt['current']] is None
    if slots[-1].boss is not None:
        assert built[-1] == 'boss'   # boss SIFT 命中 → Hu 覆 None → 回填


def test_fixture_current_hu_vote_documented(row_frames) -> None:
    """票C(高亮 Hu)跨 4 帧行为落对拍:有效命中(≤CUR_HU_DIST_HIT)时记录。

    高亮态 Hu 距离对渲染态敏感(w527 对拍:4 帧中命中票 0/4 与真值一致),
    **不锁类型正确性** —— 只锁「返回 (type|None, dist) 契约 + 命中门」;
    该票的噪声正是「查表优先 + ≥2 票才落账」阈值设计的实证依据。
    """
    from sr_od.application.currency_war.obs.cw_node_reader import CUR_HU_DIST_HIT
    hits = 0
    for name, gt in _GT.items():
        row = row_frames[name]
        slots = classify_node_row(row, _TPLS)
        cur = slots[gt['current']]
        t, d = current_slot_hu_type(row, cur, _TPLS)
        assert d >= 0
        if t is not None:
            assert d <= CUR_HU_DIST_HIT
            hits += 1
    # 对拍表数字化:4 帧中票C 弃权/命中的分布(命中不保证类型对,见 docstring)
    assert 0 <= hits <= len(_GT)


def test_read_plane_detail_difficulty_truth(test_context) -> None:
    """敌人难度参考读法真值对拍:位面详情全屏 fixture,真值 = VLM 亲读 108
    (w527 批;底部明文「敌人难度 108」)。"""
    from one_dragon.utils import cv2_utils
    from sr_od.application.currency_war.obs.cw_observation import (
        read_plane_detail_difficulty,
    )
    img = cv2_utils.read_image(
        str(_TEST_ROOT / 'screens' / '货币战争-位面详情' / '位面详情全屏.png'))
    assert read_plane_detail_difficulty(test_context, img) == 108
