# -*- coding: utf-8 -*-
"""合成/合并机制主题锁(结构合并批 W1,机械拼接)。

成员与出处(原文件 docstring 语义索引;逐字搬运,断言零改动):
- w282 合成预览✦读取器(read_merge_preview,SIFT/模板,fixture 真值)
- w292 合成特效帧态门(签名正负样本)+ reconcile 门拦截 + 注入槽装配
- w436 非正分门 merge 完成豁免(ADR-0438;默认开/回退关/金地板/定向性)
- w544 满栏合成买(ADR-0453;k 公式/容量门/金账 k×/simulate 多买/carry_gate)
- w566 sim 满栏购买守卫解冻(桩策略走真实 sim 执行层)
- w601 合成预览对账激活(W600 语料真值表 + _merge_preview_inputs)
冲突改名:后来者顶层名加来源前缀(_<tag>_原名);断言与夹具语义零改动。
"""
from __future__ import annotations


# ==================== w282 ====================

from typing import TYPE_CHECKING

import pytest

from sr_od.application.currency_war.obs.cw_identity_obs import (
    _load_preview_sparkle_tmpl,
    read_merge_preview,
)
from sr_od.application.currency_war.obs.cw_observation import read_shop_cards
from sr_od.application.currency_war.kernel.cw_state import ShopCard

if TYPE_CHECKING:
    from test.conftest import SrTestContext

SCREEN = '货币战争-备战-开商店'
STATE = 'shop_open_preview_star'
# 商店牌-1..5 area(assets/game_data/screen_info/currency_war_battle_prep_shop_open.yml)
CARD_RECTS = [(392, 70, 610, 260), (645, 70, 863, 260), (898, 70, 1116, 260),
              (1151, 70, 1369, 260), (1405, 70, 1623, 260)]


def test_sparkle_template_asset_exists() -> None:
    """模板资产在库(缺 = read_merge_preview 恒 0,信号静默失能)。"""
    assert _load_preview_sparkle_tmpl() is not None, \
        'assets/template/currency_war/star/shop_preview_sparkle_tmpl.png 缺失'


def test_read_merge_preview_fixture_lock(test_context: SrTestContext) -> None:
    """fixture 单帧锁:card5 万敌头顶 2✦ → 读 2;card1-4 无✦ → 读 0。

    直接裁 area rect 调读取器(锁视觉算法本体,不经 SIFT/OCR 门)。
    """
    if not test_context.has_screen(SCREEN, STATE):
        pytest.skip(f'存档截图缺失:screens/{SCREEN}/{STATE}.webp')
    screen = test_context.load_screen(SCREEN, STATE)
    got = [read_merge_preview(screen[y1:y2, x1:x2]) for (x1, y1, x2, y2) in CARD_RECTS]
    assert got == [0, 0, 0, 0, 2], f'升星预览✦读取错,实际 {got}(期望仅 card5=2)'


def test_read_shop_cards_fills_merge_preview(test_context: SrTestContext) -> None:
    """生产路径锁:read_shop_cards 全链(收起门+SIFT+✦读取)→ card5.merge_preview=2。

    兼锁字段默认与 0 双义语义:无✦牌 merge_preview=0(未观测,勿当「确认无副本」)。
    """
    if not test_context.has_screen(SCREEN, STATE):
        pytest.skip(f'存档截图缺失:screens/{SCREEN}/{STATE}.webp')
    screen = test_context.load_screen(SCREEN, STATE)
    cards = read_shop_cards(test_context, screen)
    assert len(cards) == 5, f'应读满 5 张牌,实际 {len(cards)}'
    assert cards[4].name == '万敌', f'card5 应 SIFT 识别为万敌,实际 {cards[4].name!r}'
    assert [c.merge_preview for c in cards] == [0, 0, 0, 0, 2]
    assert ShopCard(x=1).merge_preview == 0, '新字段默认 0(旧构造点零改动)'


def test_read_merge_preview_template_missing_failsilent(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """模板缺失 → 返 0(fail-silent),不抛异常不误报✦。"""
    if not test_context.has_screen(SCREEN, STATE):
        pytest.skip(f'存档截图缺失:screens/{SCREEN}/{STATE}.webp')
    screen = test_context.load_screen(SCREEN, STATE)
    x1, y1, x2, y2 = CARD_RECTS[4]
    monkeypatch.setattr(
        'sr_od.application.currency_war.obs.cw_identity_obs._load_preview_sparkle_tmpl',
        lambda: None)
    assert read_merge_preview(screen[y1:y2, x1:x2]) == 0


# ==================== w292 ====================

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / 'src'))
sys.path.insert(0, str(_REPO / 'sr-od-test'))

from sr_od.application.currency_war.kernel.cw_reconcile import (  # noqa: E402
    reconcile_tracking,
)
from sr_od.application.currency_war.obs.cw_identity_obs import (  # noqa: E402
    is_merge_effect_frame,
)


def _banner_frame() -> np.ndarray:
    """合成拖拽过渡帧:满席警告横幅带(深红,R 主导)——签名②正样本。"""
    img = np.zeros((1080, 1920, 3), dtype=np.uint8)
    img[515:555, 470:1450] = (160, 30, 40)   # RGB:R−max(G,B)=120>40
    return img


def _burst_frame() -> np.ndarray:
    """合成星爆帧:前排带 4 个金色四角星爆点(每个 ~80px)——签名①正样本。"""
    img = np.zeros((1080, 1920, 3), dtype=np.uint8)
    for cx in (700, 900, 1100, 1300):
        img[500:505, cx - 8:cx + 8] = (255, 215, 0)   # RGB 纯金:H≈25/S=255/V=255
    return img


def test_gate_banner_signature() -> None:
    """签名②:满席横幅帧 → True;空帧/None → False(离线不拦)。"""
    assert is_merge_effect_frame(_banner_frame()) is True
    assert is_merge_effect_frame(np.zeros((1080, 1920, 3), dtype=np.uint8)) is False
    assert is_merge_effect_frame(None) is False


def test_gate_burst_signature() -> None:
    """签名①:星爆粒子帧 → True;仅 2 个粒子(阈 3 之下)→ False。"""
    assert is_merge_effect_frame(_burst_frame()) is True
    img = np.zeros((1080, 1920, 3), dtype=np.uint8)
    for cx in (700, 900):
        img[500:505, cx - 8:cx + 8] = (255, 215, 0)
    assert is_merge_effect_frame(img) is False


def _sess() -> SimpleNamespace:
    return SimpleNamespace(
        tracked_bench_chars=[SimpleNamespace(char_id='万敌', star=2, slot=1,
                                             position_pref='back')],
        tracked_deployed=[],
        star_regression_count={}, star_pending_regression={})


def _read(star: int) -> list[SimpleNamespace]:
    return [SimpleNamespace(char_id='万敌', star=star, slot=1, position_pref='back')]


def test_gate_blocks_confirm_and_freezes_pending(monkeypatch) -> None:
    """特效帧上的第 2 次回退:**保旧 + 防抖冻结**(pending 不推进、不计数、
    不采新)——star 层 2/2 采新帧全错(动画窗 ≥2 帧骗过连续确认)的
    直接回归锁。随后干净帧(screen=None)同回退 → 仍走确认采新(门冻结非清零)。

    分包期5 补遗(§3.3-⑥ SIFT 上移)后门实现经注入槽进 kernel:
    测试同生产装配点同语义,显式注入真 ``is_merge_effect_frame``。"""
    import sr_od.application.currency_war.kernel.cw_reconcile as cr
    monkeypatch.setattr(cr, '_conflict', lambda *a, **k: None)
    monkeypatch.setattr(cr, '_IS_MERGE_EFFECT_FRAME', is_merge_effect_frame)
    s = _sess()
    s.star_pending_regression = {'万敌': 1}   # 上帧已防抖挂起
    reconcile_tracking(s, _read(1), [], _burst_frame(), source='t', ctx=None)
    assert s.tracked_bench_chars[0].star == 2, '特效帧读数不进 tracking(保旧)'
    assert s.star_pending_regression.get('万敌') == 1, '防抖冻结(不推进到确认)'
    assert not s.star_regression_count.get('万敌'), '特效帧不计数'
    # 门后干净帧:同回退仍确认采新(冻结 ≠ 清零)
    reconcile_tracking(s, _read(1), [], None, source='t', ctx=None)
    assert s.tracked_bench_chars[0].star == 1, '干净帧确认采新'
    assert s.star_pending_regression.get('万敌') == 1, '确认后防抖仍挂起(既有语义)'

    s2 = _sess()
    s2.star_pending_regression = {'万敌': 1}
    reconcile_tracking(s2, _read(1), [], _banner_frame(), source='t', ctx=None)
    assert s2.tracked_bench_chars[0].star == 2, '横幅帧(拖拽过渡)同样保旧'


def test_gate_source_lock() -> None:
    """静态口径锁(分包期5 补遗重钉):kernel 只持注入槽不直依 obs 桶;
    生产装配点(decision_assembly)接通真门实现,防未来重构绕过或回接直依。"""
    src = (_REPO / 'src' / 'sr_od' / 'application' / 'currency_war'
           / 'kernel' / 'cw_reconcile.py').read_text(encoding='utf-8')
    assert '_IS_MERGE_EFFECT_FRAME' in src, '采新确认前未引用合成特效帧态门注入槽'
    assert 'cw_identity_obs' not in src, 'kernel 不得直依 obs 桶(分包矩阵)'
    asm = (_REPO / 'src' / 'sr_od' / 'application' / 'currency_war'
           / 'decision_assembly.py').read_text(encoding='utf-8')
    assert 'is_merge_effect_frame' in asm, '生产装配点未接通特效帧态门'


# ==================== w436 ====================

import logging
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.arbiter import arbitrate
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    Candidate,
    Synthesize,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
    DecisionV2Registry,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BuyCard,
    GameState,
    ShopCard,
)


@pytest.fixture(autouse=True)
def _quiet_logging():
    """本模块测试期间静音日志(测试域收口)。

    进程级 logging.disable 是全局态:pytest 在收集期 import 本模块,模块级
    调用即对整个测试会话生效,会静默饿死其他测试依赖日志落盘的断言
    (判例:test_log_utils_utf8_rollover_continuity 因此 FileNotFoundError)。
    收口为 autouse fixture:进入本模块测试时禁用,退出时还原原级别。
    """
    prev = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(prev)


_FILLER = '娜塔莎'
_FAC = '贝洛伯格'


def _w436_sess() -> StrategySession:
    from sr_od.application.currency_war.kernel.cw_intention import (
        HoardTarget,
        IntentionState,
    )
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    s.v3_mode = 'economy'
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '姬子列车'
    s.v3_intention = ist
    s.v3_hoard = HoardTarget(
        frozenset({'姬子·启行', '三月七', '花火', '瓦尔特'}),
        frozenset(), 'locked')
    s.v3_core_names = {'姬子·启行'}
    s.target_comp = SimpleNamespace(factions=('列车同行',),
                                    core_chars=('姬子·启行',))
    return s


def _deployed(name: str, faction: str, star: int = 1,
              slot: int = 0) -> SimpleNamespace:
    return SimpleNamespace(char_id=name, faction=faction, star=star,
                           position_pref='back', equips=(), slot=slot)


def _state(**kw) -> GameState:
    """差一张凑 2★ 帧:P1 r5(非末窗,gap=0——豁免无条件于 gap 的
    证明帧)。"""
    base = {'plane': 1, 'round_num': 5, 'gold': 55, 'level': 5,
            'hp': 60,
            'board': {'列车同行': 1, _FAC: 1},
            'deployed': [_deployed('姬子·启行', '列车同行'),
                         _deployed(_FILLER, _FAC)],
            'bench': [], 'shop': [], 'node_type': 'battle'}
    base.update(kw)
    return GameState(**base)


def _merge_cand(cost: int = 3) -> Candidate:
    """第三张副本买候选(merge=True;tag= W431 实测主病灶人群
    line_opportunistic,非 'copy'——C 豁免不辖该人群)。"""
    return Candidate(action=BuyCard(
        ShopCard(x=1, faction=_FAC, name=_FILLER, cost=cost), reason=''),
        tag='line_opportunistic', source='shop', merge=True)


_REG_ON = DecisionV2Registry(merge_completion_exempt=True)
_REG_OFF = DecisionV2Registry(merge_completion_exempt=False)


def test_default_on_and_off_fallback_rejects() -> None:
    """生产默认=开(ADR-0438 开臂);显式关=回退非正分拒(W431
    病灶历史行为,回退通道保持可用)。"""
    assert DEFAULT_REGISTRY.merge_completion_exempt is True
    st = _state()
    res = arbitrate([(_merge_cand(), 0.0, {'cost': 3})], st, _w436_sess(),
                    _REG_OFF)
    assert res.log[0]['reject'] == '非正分'
    assert not any(isinstance(a, BuyCard) for a in res.actions)


def test_merge_exempt_passes_gate_gap_independent() -> None:
    """主通道:开关开时非正分 merge 买候选放行进约束链并采纳;r5
    非末窗(gap=0)即放行——完成素材豁免无条件于定向授权窗。"""
    st = _state()
    res = arbitrate([(_merge_cand(), 0.0, {'cost': 3})], st, _w436_sess(),
                    _REG_ON)
    assert res.log[0]['accepted'] is True, f'log={res.log[0]}'
    assert any(isinstance(a, BuyCard) for a in res.actions)


def test_exempt_not_must_buy_gold_floor_governs() -> None:
    """豁免≠必买:低金帧(金 < 地板)放行后 gold_floor 照拒——
    豁免只跳过非正分门,约束链不豁免。"""
    st = _state(gold=20)   # HOARD 段:跨息档买(20→17 破 2 档)攒息拒
    res = arbitrate([(_merge_cand(), 0.0, {'cost': 3})], st, _w436_sess(),
                    _REG_ON)
    assert res.log[0]['accepted'] is False
    assert not any(isinstance(a, BuyCard) for a in res.actions)


def test_non_merge_and_synthesize_not_exempted() -> None:
    """定向性:非 merge 候选不豁免;synthesize 候选虽 merge=True 但
    非 BuyCard,不辖(防语义外溢)。"""
    st = _state()
    sess = _w436_sess()
    plain = Candidate(action=BuyCard(
        ShopCard(x=1, faction=_FAC, name='三月七', cost=3), reason=''),
        tag='line_opportunistic', source='shop', merge=False)
    res = arbitrate([(plain, 0.0, {'cost': 3})], st, sess, _REG_ON)
    assert res.log[0]['reject'] == '非正分'
    syn = Candidate(action=Synthesize(name=_FILLER, star=1, copies=3),
                    tag='synthesize', source='merge_pool', merge=True)
    res_syn = arbitrate([(syn, 0.0, {'cost': 0})], st, sess, _REG_ON)
    assert res_syn.log[0]['reject'] == '非正分'


# ==================== w544 ====================

from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
    merge_buy_completes,
    merge_buy_k,
    same_star_count,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

_REG = DEFAULT_REGISTRY


def _card(name: str, x: int = 0, cost: int = 2,
          star: int = 1) -> ShopCard:
    return ShopCard(x=x, name=name, faction='仙舟', cost=cost, star=star)


def _bench(name: str, slot: int, star: int = 1) -> BenchChar:
    return BenchChar(slot=slot + 1, char_id=name, faction='仙舟', star=star)


def _full_bench(own_names: list[str]) -> list[BenchChar | None]:
    """9 槽满员(own_names 之外用垫件 F* 填)。"""
    names = own_names + [f'F{i}' for i in range(BENCH_CAPACITY
                                                - len(own_names))]
    return [_bench(n, i) for i, n in enumerate(names)]


def _w544_state(bench, shop, gold=50, deployed=None) -> GameState:
    return GameState(plane=1, round_num=4, gold=gold, level=5,
                     board={}, bench=bench, deployed=deployed or [],
                     shop=shop, hp=80, xp_progress=(0, 4))


# --- ① k 公式单一源 ------------------------------------------------------------


def test_merge_buy_k_formula() -> None:
    """k = min(店内张数, 3−已有数 mod 3)(merge_mechanics §2.5)。

    - 已有 1 份、店内 2 张 → k=2(一次点击自动多买 2 张凑合成);
    - 已有 1 份、店内 1 张 → k=1 但不完成合成(买进也无槽 → 拒);
    - 已有 2 份、店内 1 张 → k=1(旧 S3/ADR-0325 特例的一般式重现);
    - 店内 3 张超额不买:缺 2 张时店里 3 张只买 2(§2.5 绝不多买);
    - 不同星不计数(分组键 = 同名同星,与 _merge_bench 同口径)。
    """
    dep = [_bench('D', 0)]
    # 已有 1 份 X,店内 3 张 X:只买 3−1=2
    bench = _full_bench(['X'])
    shop = [_card('X', x=i) for i in range(3)]
    assert merge_buy_k('X', 1, bench, dep, shop) == 2
    assert merge_buy_completes('X', 1, bench, dep, shop) is True
    # 已有 1 份,店内 1 张:不完成合成
    assert merge_buy_completes('X', 1, bench, dep, [_card('X')]) is False
    # 已有 2 份,店内 1 张:k=1 完成
    bench2 = _full_bench(['X', 'X'])
    assert merge_buy_k('X', 1, bench2, dep, [_card('X')]) == 1
    assert merge_buy_completes('X', 1, bench2, dep, [_card('X')]) is True
    # 星级不同不计数:已有 2 份 1★,买 2★ 不合成
    assert merge_buy_completes('X', 2, bench2, dep, [_card('X', star=2)]) \
        is False
    # deploy 计入全场域:场上 1 份 + 店内 2 张 → k=2
    assert merge_buy_k('D', 1, _full_bench([]), dep,
                       [_card('D', x=0), _card('D', x=1)]) == 2
    # same_star_count 与 _merge_bench 分组键同域(bench∪deployed)
    assert same_star_count('D', 1, _full_bench([]), dep) == 1


# --- ② 满栏购买门(arbiter bench_capacity)--------------------------------------


def _bc_verdict(st: GameState, card: ShopCard):
    from sr_od.application.currency_war.decision.cw_strategy import StrategySession
    from sr_od.application.currency_war.decision.decision_v2.arbiter import (
        _check_constraint,
    )
    from sr_od.application.currency_war.decision.decision_v2.candidates import (
        Candidate,
    )
    cand = Candidate(action=BuyCard(card), tag='line_opportunistic',
                     source='shop')
    return _check_constraint('bench_capacity', cand, st, st,
                             StrategySession(), _REG)


def test_gate_allows_merge_buy_at_full_bench() -> None:
    """满栏 + 触发合成(own=1 + 店 2 张,k=2)→ 放行(ADR-0453 主升级面;
    旧门 own≠2 一律拒,用户裁决:被迫卖有用角色不可接受)。"""
    st = _w544_state(_full_bench(['X']),
                [_card('X', x=0), _card('X', x=1), _card('Y', x=2)])
    assert _bc_verdict(st, _card('X')) is None, 'k=2 合成买应放行'


def test_gate_rejects_non_merge_at_full_bench() -> None:
    """满栏 + 不触发合成 → 仍拒(ADR-0283 守卫语义保留为兜底):
    ①未持有且店仅 1 张;②已有 1 份但店仅 1 张(k=1 凑不满 3)。"""
    st = _w544_state(_full_bench(['X']),
                [_card('Z', x=0), _card('X', x=1)])
    reason = _bc_verdict(st, _card('Z'))
    assert reason is not None and reason.resource == 'bench'
    reason2 = _bc_verdict(st, _card('X'))
    assert reason2 is not None and reason2.resource == 'bench'


def test_gate_k1_case_unchanged() -> None:
    """旧 S3(ADR-0325)k=1 特例(own=2 + 店 1 张)行为不变(零漂移)。"""
    st = _w544_state(_full_bench(['X', 'X']), [_card('X', x=0)])
    assert _bc_verdict(st, _card('X')) is None


# --- ③ 金账 k×单价 ---------------------------------------------------------------


def test_cost_of_charges_k_times_unit_cost() -> None:
    """满栏合成买金校验按 k×单价(§2.5 无价格优惠);非满栏恒 1×
    (arbiter._cost_of,gold_floor/interest_rule 同源取数)。"""
    from sr_od.application.currency_war.decision.cw_strategy import StrategySession
    from sr_od.application.currency_war.decision.decision_v2.arbiter import _cost_of
    from sr_od.application.currency_war.decision.decision_v2.candidates import (
        Candidate,
    )
    cand = Candidate(action=BuyCard(_card('X', cost=2)),
                     tag='line_opportunistic', source='shop')
    st_full = _w544_state(_full_bench(['X']),
                     [_card('X', x=0), _card('X', x=1)])
    assert _cost_of(cand, st_full) == 4, 'k=2 × 单价 2'
    st_open = _w544_state([_bench('F', 0)], [_card('X', x=0)])
    assert _cost_of(cand, st_open) == 2, '非满栏 1×(零漂移)'


# --- ④ simulate 满栏多买执行 ------------------------------------------------------


def test_simulate_full_bench_multi_buy() -> None:
    """执行层:金扣 k×单价、店 k 张下架、合成产物落位、bench 恒 9 槽。"""
    bench = _full_bench(['X'])
    shop = [_card('X', x=1, cost=2), _card('X', x=2, cost=2),
            _card('Y', x=3, cost=1)]
    st = _w544_state(bench, shop, gold=50)
    st2 = GameState.copy(st)
    from sr_od.application.currency_war.kernel.cw_state import (
        bench_occupied,
        simulate,
    )
    out = simulate(st2, BuyCard(shop[0]))
    assert out.gold == 50 - 4, 'k=2 × 单价 2 = 全款 4'
    assert bench_occupied(out.bench) == BENCH_CAPACITY, '满栏买入后仍满'
    assert len(out.bench) == BENCH_CAPACITY, '临时尾槽截回定长 9'
    two_star = [b for b in out.bench
                if b is not None and b.char_id == 'X' and b.star == 2]
    assert len(two_star) == 1, '3×1★ 合成 1×2★(落 bench,三张全备战栏)'
    assert [(c.name, c.x) for c in out.shop] == [('Y', 3)], \
        '店内 2 张同身份牌全部下架(自动多买)'


def test_simulate_full_bench_non_merge_noop() -> None:
    """执行层兜底:不触发合成 → 整动作 no-op(金不扣/牌不下架)。"""
    from sr_od.application.currency_war.kernel.cw_state import simulate
    bench = _full_bench(['X'])
    shop = [_card('Z', x=1, cost=2)]
    st = _w544_state(bench, shop, gold=50)
    out = simulate(st, BuyCard(shop[0]))
    assert out.gold == 50
    assert [c.x for c in out.shop] == [1]


# --- ⑤ carry_gate:满栏合成买不腾位 ------------------------------------------------


def _locked_sess():
    from sr_od.application.currency_war.kernel.cw_intention import IntentionState
    from sr_od.application.currency_war.decision.cw_strategy import StrategySession
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '列车同行'
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    s.v3_mode = 'economy'
    s.v3_intention = ist
    return s


def _carry_fixture(shop_cards: list[ShopCard]) -> GameState:
    """carry_gate 可达态(引 test_cw_w35 既有夹具口径):bench 满=全保护
    件(7 互异+2 重复份,重复份加权≥2 是 3合1 素材不进卖序),意向
    核心=姬子·启行 未持有、在店。"""
    from sr_od.application.currency_war.kernel.cw_intention import HoardTarget
    sess_bench_names = ['三月七', '花火', '瓦尔特', '丹恒·饮月', '希儿',
                        '爻光', '藿藿', '花火', '三月七']
    bench = [BenchChar(slot=i + 1, char_id=n, faction='列车同行', star=1)
             for i, n in enumerate(sess_bench_names)]
    st = _w544_state(bench, shop_cards, gold=50)
    return st


def _locked_carry_sess():
    from sr_od.application.currency_war.kernel.cw_intention import HoardTarget
    sess = _locked_sess()
    sess.v3_hoard = HoardTarget(frozenset({'姬子·启行', '三月七', '花火',
                                           '瓦尔特'}), frozenset(), 'locked')
    sess.v3_core_names = {'姬子·启行'}
    sess.v2_round_key = (1, 4)
    return sess


def test_carry_gate_mergebuy_skips_forced_sell() -> None:
    """意向核心未持有、店内 3 张(own=0 → k=3 完成合成)且 bench 满 →
    不卖任何件直接买(ADR-0453;裁决=「否则被迫卖有用角色」)。"""
    from sr_od.application.currency_war.decision.decision_v2.discipline import (
        carry_gate_actions,
    )
    sess = _locked_carry_sess()
    shop = [_card('姬子·启行', x=i, cost=4) for i in range(3)]
    st = _carry_fixture(shop)
    acts = carry_gate_actions(st, sess, _REG)
    assert len(acts) == 1 and isinstance(acts[0], BuyCard), \
        '合成触发买直达,无 SellBench'
    assert acts[0].card.name == '姬子·启行'


def test_carry_gate_non_merge_keeps_sell_chain() -> None:
    """不满足合成条件(own=0 + 店 1 张)→ 原腾位链逐位不动(零漂移):
    [SellBench(最弱保护件), BuyCard(核心)]。"""
    from sr_od.application.currency_war.decision.decision_v2.discipline import (
        carry_gate_actions,
    )
    sess = _locked_carry_sess()
    st = _carry_fixture([_card('姬子·启行', x=0, cost=4)])
    acts = carry_gate_actions(st, sess, _REG)
    assert len(acts) == 2, '原语义:腾位卖 + 买核心'


# ==================== w566 ====================

class _FullBenchStub:
    """一次性桩:首次 decide_prep 构造满栏态并提议一张店内牌,
    第二次调用记录执行后金(同轮内,无收入插入)→ 金差 = 执行账。"""

    def __init__(self, own_copies: int, shop_copies: int,
                 buy_name_idx: int = 0) -> None:
        self.own_copies = own_copies
        self.shop_copies = shop_copies
        self.buy_name_idx = buy_name_idx
        self.armed = True
        self.gold_before: int | None = None
        self.gold_after: int | None = None
        self.shop_target_left: int | None = None

    def update_target(self, st, sess, cfg) -> None:  # noqa: ANN001
        pass

    def decide_prep(self, st, sess, cfg):  # noqa: ANN001
        from sr_od.application.currency_war.data.cw_chars import CHARACTERS
        from sr_od.application.currency_war.kernel.cw_state import (
            BenchChar,
            BuyCard,
            ShopCard,
        )
        if not self.armed:
            if self.gold_after is None:
                # 首次记录 = 执行后同轮(轮内无收入插入,金差纯执行账)
                self.gold_after = st.gold
                names1 = sorted(n for n, c in CHARACTERS.items()
                                if c.cost == 1)
                self.shop_target_left = sum(
                    1 for c in st.shop
                    if c.name == names1[self.buy_name_idx])
            return []
        self.armed = False
        self.gold_before = st.gold
        names1 = sorted(n for n, c in CHARACTERS.items() if c.cost == 1)
        tgt = names1[self.buy_name_idx]
        fillers = [n for i, n in enumerate(names1)
                   if i != self.buy_name_idx][:9]
        # 满栏构造:filler 铺底 + own_copies 张目标(同星 1★)
        st.bench = [BenchChar(slot=i, char_id=fillers[i], faction='?')
                    for i in range(9 - self.own_copies)] \
            + [BenchChar(slot=8 - j, char_id=tgt, faction='?')
               for j in range(self.own_copies)]
        st.shop = [ShopCard(x=100 + j, faction='?', name=tgt, cost=1)
                   for j in range(self.shop_copies)]
        return [BuyCard(card=st.shop[0], reason='stub')]


def _run(stub) -> object:  # noqa: ANN001

    from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
    return simulate_p1(1, pool='fallback', strategy=stub)


def _ledger_buys(res) -> list[dict]:  # noqa: ANN001
    return [a for row in res.ledger for a in (row.get('actions') or [])
            if a.get('__type__') == 'BuyCard']


def _total_skipped(res) -> int:  # noqa: ANN001
    return sum((row.get('sim') or {}).get('bench_full_skipped_buys', 0)
               for row in res.ledger)


def test_sim_fullbench_merge_buy_executes_k2() -> None:
    """满栏 own=1 + 店 2 张 → 自动多买 k=2 执行:金 2×全款、
    合成发生、bench 不超容、不计入 skipped。"""
    stub = _FullBenchStub(own_copies=1, shop_copies=2)
    res = _run(stub)
    cost = 1
    buys = _ledger_buys(res)
    assert any(a.get('count') == 2 for a in buys), \
        '满栏合成买未执行或 count 披露缺失(W566 回归)'
    assert stub.gold_before is not None and stub.gold_after is not None
    assert stub.gold_before - stub.gold_after == 2 * cost, \
        f'金账非 k×单价全款:{stub.gold_before - stub.gold_after}'
    assert _total_skipped(res) == 0, '合成买被计入 skipped(计数语义未收窄)'
    # 店 k 张同身份牌下架(槽消费语义)
    assert stub.shop_target_left == 0, \
        f'店内应下架 {stub.shop_copies} 张,剩 {stub.shop_target_left}'
    # 合成链照走:触发轮 sim.merges ≥1;全程 bench 不超容
    trig = [row for row in res.ledger
            if any(a.get('count') == 2 for a in (row.get('actions') or []))]
    assert trig and (trig[0].get('sim') or {}).get('merges', 0) >= 1
    from sr_od.application.currency_war.kernel.cw_state import BENCH_CAPACITY
    for row in res.ledger:
        bench_n = len((row.get('state') or {}).get('bench') or [])
        assert bench_n <= BENCH_CAPACITY, '满栏合成买后 bench 超容'


def test_sim_fullbench_merge_buy_executes_k1() -> None:
    """满栏 own=2 + 店 1 张 → k=1 合成买执行(旧 k=1 特例的
    守卫路径等价面),不计入 skipped。"""
    stub = _FullBenchStub(own_copies=2, shop_copies=1)
    res = _run(stub)
    buys = _ledger_buys(res)
    assert len(buys) == 1 and buys[0].get('count', 1) == 1
    assert stub.gold_before - stub.gold_after == 1
    assert _total_skipped(res) == 0
    trig = [row for row in res.ledger
            if any(a.get('__type__') == 'BuyCard'
                   for a in (row.get('actions') or []))]
    assert trig and (trig[0].get('sim') or {}).get('merges', 0) >= 1


def test_sim_fullbench_non_merge_buy_still_rejected() -> None:
    """满栏且不满足合成(own=0、店 1 张凑不满)→ 仍拒(ADR-0283
    兜底语义保留):金不动、牌不下架、计数披露。"""
    stub = _FullBenchStub(own_copies=0, shop_copies=1)
    res = _run(stub)
    assert _ledger_buys(res) == [], '非合成满栏买被错误执行'
    assert _total_skipped(res) == 1, '非合成拒买未计数'
    # 拒买路径无执行账:两时点间金只增(收入)不减——无购买/刷新支出
    assert stub.gold_after >= stub.gold_before, '拒买路径出现金支出'


# ==================== w601 ====================

from types import SimpleNamespace

import pytest

import sr_od.application.currency_war.prep_director as pd
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState, ShopCard
from sr_od.application.currency_war.obs.cw_shop_obs import (
    MergePreviewCompareRow,
    compare_merge_preview,
)

from sr_od.application.currency_war.prep_director import PrepDirector, _merge_preview_inputs

#: W600 非零事件语料的 (槽位, ✦数) 形状(13 个唯一形状;fixture 素材单一源)。
_W600_NONZERO_SHAPES: list[list[tuple[int, int]]] = [
    [(2, 2)], [(3, 2), (4, 2)], [(2, 1), (4, 1)], [(4, 2)], [(0, 2)],
    [(0, 2)], [(2, 1)], [(0, 2), (1, 2), (4, 2)], [(4, 2)], [(0, 1)],
    [(1, 2)], [(2, 2), (3, 2)], [(3, 2)],
]


# ===== _merge_preview_inputs(入参折算单一源,纯函数) =====


def _state_with_shop(cards: list[ShopCard],
                     bench: list[BenchChar | None] | None = None,
                     deployed: list[BenchChar] | None = None) -> GameState:
    st = GameState(plane=2, round_num=5, level=7)
    st.shop = cards
    if bench is not None:
        st.bench = bench
    if deployed is not None:
        st.deployed = deployed
    return st


def test_merge_inputs_det_mapping_and_unnamed() -> None:
    """det = merge_preview>0(W600 语义映射);未识别牌两侧不参评只计数。"""
    st = _state_with_shop([
        ShopCard(x=100, name='甲', merge_preview=2),
        ShopCard(x=200, name='', merge_preview=0),
        ShopCard(x=300, name='乙', merge_preview=0),
        ShopCard(x=400, name='丙', merge_preview=1),
    ])
    our, det, unnamed = _merge_preview_inputs(st)
    assert det == {0: True, 2: False, 3: True}
    assert our == {0: False, 2: False, 3: False}
    assert unnamed == 1


def test_merge_inputs_our_from_same_star_holding() -> None:
    """our = 全场域同名同星持有 >0(bench∪deployed;跨星不算——3合1 须同星)。"""
    st = _state_with_shop(
        [ShopCard(x=100, name='甲'), ShopCard(x=200, name='乙')],
        bench=[BenchChar(slot=0, char_id='甲', star=1), None,
               BenchChar(slot=2, char_id='乙', star=2)],
        deployed=[BenchChar(slot=0, char_id='甲', star=1)])
    our, det, unnamed = _merge_preview_inputs(st)
    assert our == {0: True, 1: False}   # 甲:bench1+deployed1;乙:仅 2★ 不同星
    assert det == {0: False, 1: False}
    assert unnamed == 0


def test_merge_inputs_empty_shop() -> None:
    """空 shop → 三空(关店帧调用方自带锚门,双保险)。"""
    assert _merge_preview_inputs(_state_with_shop([])) == ({}, {}, 0)
    assert _merge_preview_inputs(GameState()) == ({}, {}, 0)


# ===== compare_merge_preview 行为锁(fixture=W600 非零事件语料,数据驱动) =====


class TestCompareAgainstW600Fixture:
    """真值面 = W600 非零事件形状逐条过 compare 真值表(激活的规格锁)。"""

    @staticmethod
    def _det_of(shape: list[tuple[int, int]]) -> dict[int, bool]:
        return {slot: cnt > 0 for slot, cnt in shape}

    def test_fixture_det_mapping_all_true(self) -> None:
        """事件语料全部 merge_preview>0 → det 恒 True(非零事件语义)。"""
        for shape in _W600_NONZERO_SHAPES:
            det = self._det_of(shape)
            assert det and all(det.values()), f'shape={shape} 应全映射 True'

    def test_holding_matches_detection_is_match(self) -> None:
        """持有台账与识别相符形态(W600 15 事件中 8 例精确相符的形状):
        our=True 且 det=True → match,suspect 空。"""
        for shape in _W600_NONZERO_SHAPES:
            our = {slot: True for slot, _ in shape}
            r = compare_merge_preview(our, self._det_of(shape))
            assert {row.verdict for row in r.rows} == {'match'}
            assert r.suspect_slots == []

    def test_holding_without_sparkle_is_suspect(self) -> None:
        """我方持有 ≥1 副本而识别无✦ → our_suspect(单向罚则唯一对象;
        也是暗相漏检疑云的票形态,双义不逐票判死)。"""
        r = compare_merge_preview({2: True, 4: True}, {2: True, 4: False})
        by_slot = {row.slot: row.verdict for row in r.rows}
        assert by_slot == {2: 'match', 4: 'our_suspect'}
        assert r.suspect_slots == [4]

    def test_sparkle_without_holding_is_game_extra(self) -> None:
        """识别有✦而我方无账 → game_extra 留证不判罚,不出 suspect。"""
        for shape in _W600_NONZERO_SHAPES:
            our = {slot: False for slot, _ in shape}
            r = compare_merge_preview(our, self._det_of(shape))
            assert {row.verdict for row in r.rows} == {'game_extra'}
            assert r.suspect_slots == []

    def test_detected_none_still_pending(self) -> None:
        """preview_detected=None 登记形态保留(全 pending),激活不删契约。"""
        r = compare_merge_preview({0: True}, None)
        assert [row.verdict for row in r.rows] == ['pending']
        assert r.suspect_slots == []
        assert isinstance(r.rows[0], MergePreviewCompareRow)

    def test_zero_preview_is_legal_false_not_missing(self) -> None:
        """merge_preview=0 映射 False 是合法语义(无✦),不等于识别端缺席
        (缺席 = dict 整体 None)——两者分道。"""
        r = compare_merge_preview({0: False}, {0: False})
        assert r.rows[0].verdict == 'match'
        assert r.rows[0].detected is False


# ===== 行为锁(假台账,零 OCR/零游戏;形态同 W564) =====


def _capture_defects(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    from sr_od.application.currency_war.telemetry import defects as tel
    calls: list[dict] = []
    monkeypatch.setattr(tel, 'record_defect',
                        lambda *a, **k: calls.append({'args': a, 'kwargs': k}))
    return calls


def _director() -> PrepDirector:
    d = object.__new__(PrepDirector)
    d.ctx = SimpleNamespace(cw_match=SimpleNamespace(session=SimpleNamespace()))
    return d


def _obs(st: GameState | None, shop_open: bool = True) -> pd.PrepObservation:
    obs = pd.PrepObservation()
    obs.shop_open = shop_open
    obs.state = st
    return obs


def test_merge_wire_mismatch_records_defect(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """our_suspect → 落台账(surface=shop,kind=merge_preview_mismatch),
    带双义不判死 verdict 与槽位 refs。"""
    calls = _capture_defects(monkeypatch)
    d = _director()
    st = _state_with_shop(
        [ShopCard(x=100, name='甲', merge_preview=0)],
        bench=[BenchChar(slot=0, char_id='甲', star=1)])
    d._reconcile_merge_preview(_obs(st))
    assert len(calls) == 1
    assert calls[0]['args'] == ('shop', 'merge_preview_mismatch')
    kw = calls[0]['kwargs']
    assert kw['plane'] == 2 and kw['round_num'] == 5
    assert kw['reader_source'] == 'merge_preview_reconcile'
    assert kw['gap_large'] is True
    assert 'our_suspect' in kw['observed']
    refs = {r['field']: r['value'] for r in kw['refs']}
    assert refs['our_suspect'] == '0'
    assert refs['game_extra'] == ''
    assert refs['unnamed'] == '0'
    assert '已产线' in refs['reader']


def test_merge_wire_game_extra_also_records(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """game_extra(识别有✦而我方无账)同为开票形态(留证不判罚≠不记账)。"""
    calls = _capture_defects(monkeypatch)
    d = _director()
    st = _state_with_shop([ShopCard(x=100, name='甲', merge_preview=2)])
    d._reconcile_merge_preview(_obs(st))
    assert len(calls) == 1
    refs = {r['field']: r['value'] for r in calls[0]['kwargs']['refs']}
    assert refs['game_extra'] == '0' and refs['our_suspect'] == ''


def test_merge_wire_clean_or_closed_or_no_holding_skips(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """全 match / 关店帧 / 空牌 / 无任何持有(our 空集)→ 零台账(一致不打扰)。"""
    calls = _capture_defects(monkeypatch)
    d = _director()
    match_st = _state_with_shop([ShopCard(x=100, name='甲', merge_preview=0)])
    d._reconcile_merge_preview(_obs(match_st))                    # 全 match
    d._reconcile_merge_preview(_obs(match_st, shop_open=False))   # 关店帧
    d._reconcile_merge_preview(_obs(_state_with_shop([])))        # 空牌
    d._reconcile_merge_preview(_obs(None))                        # 无 state
    unnamed_st = _state_with_shop([ShopCard(x=100, name='', merge_preview=1)])
    d._reconcile_merge_preview(_obs(unnamed_st))                  # 仅未识别牌
    assert calls == []


def test_merge_wire_best_effort_on_error(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """对账异常 → 静默跳过,不阻塞环(best-effort 契约)。"""
    _capture_defects(monkeypatch)
    d = _director()
    monkeypatch.setattr(pd, 'compare_merge_preview',
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError('down')))
    st = _state_with_shop(
        [ShopCard(x=100, name='甲', merge_preview=2)],
        bench=[BenchChar(slot=0, char_id='甲', star=1)])
    d._reconcile_merge_preview(_obs(st))   # 不抛即过

