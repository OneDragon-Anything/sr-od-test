"""CW 身份识别三层漏斗回归测试(实机故障测试)。

故障出处:2026-09-14 run_20260914_210200 停机钩子 exec_fail_mismatch——
漏斗 L2「本局已见集」子集仲裁里,真身(黄泉,全库 27 内点)缺席时,
基准线上的跨身份弱命中(忘归人 10 内点)称王,毒化漏斗状态后整槽丢读 →
跟踪备战席 8/9,席满被当有空位,策略发幻影买牌被游戏全拒。

钉住两条设计契约:
1. L1/L2 子集命中必须清加严线(``_FUNNEL_SUBSET_MIN_INLIERS_FACTOR`` ×
   min_inliers),弱命中一律下探 L3 全库仲裁——子集冠军 ≠ 全局冠军;
2. 漏斗路径(read_bench_view_tiered,heavy 生产主路径)必须挂召唤物
   停机钩子(_summon_unknown_hook)——「占用未识别」的槽不允许静默丢弃。
"""

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_game_state import Unit
from sr_od.application.currency_war.obs import cw_identity_obs as obs


class _FakeRect:
    """槽位矩形替身(漏斗只透传给 identify_slots,本测试不读像素)。"""


def test_funnel_subset_weak_champion_falls_through_to_full(monkeypatch):
    """子集弱命中冠军必须下探 L3:真身缺席子集时弱命中不得称王。

    模型:甲=全局强(30 内点,本局未见),乙=全局弱(12 内点,本局已见)。
    旧行为(基准线 10):L2 子集 {乙} 收乙 → 返回错名;
    契约行为(加严线 2×):L2 拒乙(12<20)→ L3 全库收甲。
    """
    calls = []  # (子集键集, min_inliers) 记录

    def fake_identify_slots(screen, templates, slots, row, min_inliers=10,
                            live_only=False, center_gate=False,
                            variant_keys=None):
        names = {k.split('#')[0] for k in templates}
        inliers = 30 if '甲' in names else 12
        calls.append((frozenset(names), min_inliers))
        if inliers >= min_inliers:
            winner = '甲' if '甲' in names else '乙'
            return [(1, Unit(char_id=winner, star=1))]
        return []

    monkeypatch.setattr(obs, 'identify_slots', fake_identify_slots)
    session = SimpleNamespace()
    last, seen = obs._funnel_state(session)
    seen.add('乙')  # 乙 本局已见;甲 首次上场(真身只在全库)
    slots = [(1, _FakeRect())]

    out = obs.identify_slots_tiered(session, screen=object(),
                                    templates={'甲': object(), '乙': object()},
                                    slots=slots, row='', min_inliers=10)

    assert [u.char_id for _s, u in out] == ['甲']
    # 加严线契约:L1/L2 子集调用 = 2× 基准档;L3 全库调用 = 基准档原样
    subset_calls = [(s, m) for s, m in calls if s == frozenset({'乙'})]
    full_calls = [(s, m) for s, m in calls if s == frozenset({'甲', '乙'})]
    assert subset_calls and all(m == 20 for _, m in subset_calls)
    assert full_calls and all(m == 10 for _, m in full_calls)
    # 全局冠军进漏斗状态(后续帧 L1 快配对准真身)
    assert last[('', 1)] == '甲'


def test_tiered_bench_read_wires_summon_hook(monkeypatch):
    """漏斗路径备战席读必须挂召唤物停机钩子(占用未识别不允许静默丢弃)。"""
    sent_ctx, sent_screen, sent_templates = object(), object(), object()
    sent_hits = [(1, Unit(char_id='甲', star=1))]   # 槽位对(3.1 载体)
    hook_calls = []
    kind_calls = []
    monkeypatch.setattr(obs, 'identify_slots_tiered',
                        lambda *a, **k: list(sent_hits))
    monkeypatch.setattr(obs, '_ctx_slots', lambda ctx, prefix, count: [])
    monkeypatch.setattr(obs, '_summon_unknown_hook',
                        lambda ctx, screen, hits: hook_calls.append(
                            (ctx, screen, hits)))
    monkeypatch.setattr(obs, '_bench_item_kind_by_slot',
                        lambda ctx, screen: kind_calls.append((ctx, screen)) or {})

    out = obs.read_bench_view_tiered(SimpleNamespace(), sent_ctx,
                                     sent_screen, sent_templates)

    assert [s.unit for s in out.slots if s.kind == 'unit'] \
        == [u for _s, u in sent_hits]
    assert out.capacity == 9
    assert hook_calls == [(sent_ctx, sent_screen, sent_hits)]
    assert kind_calls == [(sent_ctx, sent_screen)]


# ============================================================ 惊喜盒板件观察
# 锁面 = 迭代设计 .debug/progress/2026-10-19-giftbox-piece-obs/designs/
# giftbox-piece-obs.md §4.1(检测纯函数三 fixtures)。fixtures = 真实截图
# 纪律:reward_giftbox_phantom(⏳12 唯一取证帧,真值 (12,) 人工确认)/
# reward_spheres_8(晶矿球同区无盒)/ reward_panel_empty(空面板)。

def test_find_giftbox_sight_fixtures(test_context) -> None:
    """检测纯函数三 fixtures:盒帧命中读 12;球帧/空面板零误报。

    一图一测聚合断言(识别贵):三帧各检测一次;负例在段1 模板匹配即
    返回空、不触 OCR,成本单腿 = 盒帧一次徽章 OCR(conftest 内容哈希
    memo 跨测试复用)。区域 rect 经 test_context 真实 screen_info 通道
    (「区域-奖励」现役建档),模板 = 仓内生产资产同源 fixture。
    """
    if not test_context.has_screen('货币战争-备战', 'reward_giftbox_phantom'):
        pytest.skip(
            '存档截图缺失:screens/货币战争-备战/reward_giftbox_phantom.webp')
    assert test_context.has_screen('货币战争-备战', 'reward_spheres_8')
    assert test_context.has_screen('货币战争-备战', 'reward_panel_empty')

    assert obs.find_giftbox_sight(
        test_context,
        test_context.load_screen('货币战争-备战',
                                 'reward_giftbox_phantom')) == (12,), \
        '盒帧命中且读出徽章数字 12'
    assert obs.find_giftbox_sight(
        test_context,
        test_context.load_screen('货币战争-备战', 'reward_spheres_8')) == (), \
        '晶矿球同区帧零误报'
    assert obs.find_giftbox_sight(
        test_context,
        test_context.load_screen('货币战争-备战', 'reward_panel_empty')) == (), \
        '空面板负例零命中'


def test_giftbox_badge_reading_confusion_repair() -> None:
    """徽章读数结构修复:真数字恒在尾部(沙漏徽记在首且可被 OCR 误读成
    形近字符);修复规则 = 尾 2 字符窗 + l/I/i/| → 1 + 1..12 越界作废。
    越界作废是上报语义的安全失败形态(宁可丢样本不报误读数)。"""
    assert obs._giftbox_badge_reading('12') == 12
    assert obs._giftbox_badge_reading('⏳12') == 12, '徽记原文随行 → 尾窗取数'
    assert obs._giftbox_badge_reading('X12') == 12, '徽记误读成形近字母'
    assert obs._giftbox_badge_reading('812') == 12, '徽记误读成数字并位'
    assert obs._giftbox_badge_reading('1 2') == 12, '空白混淆'
    assert obs._giftbox_badge_reading('l2') == 12, '1 → l 形近'
    assert obs._giftbox_badge_reading('I2') == 12, '1 → I 形近'
    assert obs._giftbox_badge_reading('11') == 11
    assert obs._giftbox_badge_reading('3') == 3
    assert obs._giftbox_badge_reading('72') is None, '不可修复误读 → 作废'
    assert obs._giftbox_badge_reading('13') is None, '越上界(初始 ≤12)作废'
    assert obs._giftbox_badge_reading('0') is None, '越下界作废'
    assert obs._giftbox_badge_reading('') is None, '空读作废'
    assert obs._giftbox_badge_reading('⏳') is None, '只有徽记无数字 → 作废'
