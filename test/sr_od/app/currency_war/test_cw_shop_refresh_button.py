"""test_cw_shop_refresh_button 主题锁(T-13 免费刷新按钮/机制建档接入)。

通道 = 刷新钮按钮态现场读数(reader ``cw_shop_refresh_obs.
read_shop_refresh_button``,T-15 实机三态取证):免费态=「免费刷新」锚+
剩余次数(§3.3.6 free_refresh_balance 的 UI 观察通道)/付费耗尽=「刷新」+
标价/不可用灰态=同付费渲染+金<标价(逻辑面判别)。

三锁面:
1. **真值通道闸**(apply_action_outcome 免费判定):按钮真值优先(观察赢),
   失读回退逻辑账(接线前保守形态,行为逐位一致);
2. **免费帧喂入口闸**(cw_observation 商店开态):免费态次数与标价同 rect,
   锚命中即 carry,禁落次数当 shop_refresh_cost(§3.3.4 免费帧不写;
   T-15 推翻「免费帧渲染无数字」旧假设后的结构性防线);同帧 gold 透传闸
   (灰态判别输入,失读保真 None 禁 0 假值);
3. **真帧锁**(三态归档 fixture × 项目真 OCR):免费帧锚命中读数 2 /
   付费帧标价 2 / 灰态帧标价 2+金 1 不可负担;「标识-免费刷新」锚判别
   边界直锁(免费帧命中 / 付费帧+灰态帧不命中)。

证据帧持久家 = 测试仓归档 ``screens/货币战争-备战-开商店/``(免费刷新可用|
刷新耗尽付费态|刷新不可用灰态 .webp 三态 fixture + 刷新不可用灰态-暗钮
模板源帧 .png = 暗钮后备模板的整帧源,按模板资产纪律无损入库;本文件
真帧锁只消费前三态 webp)。易失原始证据目录 = ``.debug/currency_war/
evidence/20260912_t15_t13_t18/``(暂记溯源,勿作持久指针)。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from one_dragon.base.geometry.rectangle import Rect
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    board_state_of,
    register_sig_actors,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwWorkFrame,
    RefreshShop,
)
from sr_od.application.currency_war.obs import cw_shop_refresh_obs
from sr_od.application.currency_war.obs.cw_shop_refresh_obs import (
    ShopRefreshButton,
    _parse_free_count,
    read_shop_refresh_button,
)
from sr_od.application.currency_war.operations.cw_op import cw_op_buy_cards
from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
    RefreshShopOp,
    ShopVisitLedger,
)
from sr_od.application.currency_war.telemetry import defects as _defects
from test.conftest import SrTestContext

# 写入口签名 actor 在册(测试写面,ADR-0634;同 test_cw_game_state_consume 先例)
register_sig_actors('TestRefreshButtonWriter')

_PRICE_RECT = Rect(1584, 513, 1664, 558)   # = screen_info「文本-刷新价格」建档值


def _fake_ctx(ocr_results: list) -> SimpleNamespace:
    """带「文本-刷新价格」area 的假 ctx(composite 只经模块桩读 area,
    ocr_service 走 screen=None 透传约定,同 test_cw_shop_refresh_price)。"""
    area = SimpleNamespace(area_name='文本-刷新价格', pc_rect=_PRICE_RECT)
    si = SimpleNamespace(area_list=[area])
    return SimpleNamespace(
        screen_loader=SimpleNamespace(get_screen=lambda name: si),
        ocr_service=SimpleNamespace(get_ocr_result_list=lambda **kw: ocr_results),
    )


def _ocr_item(data: str) -> SimpleNamespace:
    return SimpleNamespace(data=data)


def _patch_button_frame(monkeypatch: pytest.MonkeyPatch,
                        anchor: bool | None,
                        price_texts: list[str],
                        count_texts: list[str] | None = None) -> dict:
    """composite 三读桩:锚命中值 + 价格/次数 rect OCR 文本(分离注入)。"""
    calls = {'binarized': 0}
    monkeypatch.setattr(cw_shop_refresh_obs, '_free_anchor_hit',
                        lambda ctx, screen: anchor)
    monkeypatch.setattr(cw_shop_refresh_obs, '_area_rect',
                        lambda ctx, name, screen_name=None: _PRICE_RECT)
    monkeypatch.setattr(
        cw_shop_refresh_obs, '_ocr_upscaled',
        lambda ctx, screen, rect, scale=3:
        [_ocr_item(t) for t in (count_texts if anchor is True else price_texts)])
    monkeypatch.setattr(
        cw_shop_refresh_obs, '_ocr_upscaled_binarized',
        lambda ctx, screen, rect, scale=3:
        (calls.__setitem__('binarized', calls['binarized'] + 1)
         or [_ocr_item(t) for t in (count_texts or [])]))
    return calls


# ===== 1a. 次数解析纯函数层(可信域 1..9999) =====

def test_parse_count_domain() -> None:
    """可信域锁:基值 2 / 两位数 11(免费午餐) / 上界 9999(高效决策)全收;
    0(免费钮不渲染 0)/ 越界 / 无数字 → None,禁猜截位。"""
    assert _parse_free_count(['2']) == 2
    assert _parse_free_count(['11']) == 11
    assert _parse_free_count(['9999']) == 9999
    assert _parse_free_count(['0']) is None
    assert _parse_free_count(['10000']) is None
    assert _parse_free_count(['免费']) is None
    assert _parse_free_count(['']) is None
    assert _parse_free_count([]) is None


def test_parse_count_icon_prefix_tolerated() -> None:
    """图标形变容错('G2'/'G0'):免费帧渲染纯数字(T-15 实证),但 O→0
    归一沿用既有规则不碍事——残留图标前缀不阻断数字位解读。"""
    assert _parse_free_count(['G2']) == 2
    assert _parse_free_count(['G0']) is None   # 0 仍落域外拒信


# ===== 1b. composite reader(锚桩 + OCR 桩;判定序矩阵) =====

def test_button_free_state_never_touches_price_channel(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """免费态:锚命中 → free=True + 次数读出;**标价通道零触**
    (次数数字禁进标价解析——同 rect 异语义的结构隔离)。"""
    monkeypatch.setattr(cw_shop_refresh_obs, 'read_shop_refresh_price',
                        lambda ctx, screen: pytest.fail(
                            '免费态分支不得进标价通道'))
    _patch_button_frame(monkeypatch, anchor=True, price_texts=[],
                        count_texts=['2'])
    btn = read_shop_refresh_button(_fake_ctx([]), None)
    assert btn == ShopRefreshButton(free=True, free_remaining=2,
                                    price=None, affordable=True)


def test_button_paid_state_affordable(monkeypatch: pytest.MonkeyPatch) -> None:
    """付费耗尽态:锚未中+标价读出 → free=False;金 5≥2 → 可负担。"""
    _patch_button_frame(monkeypatch, anchor=False, price_texts=['G2'])
    btn = read_shop_refresh_button(_fake_ctx([]), None, gold=5)
    assert btn == ShopRefreshButton(free=False, free_remaining=None,
                                    price=2, affordable=True)


def test_button_paid_state_unaffordable_gray(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """不可用灰态:文本面与付费态相同(T-15 实证),判别 = 逻辑面对比
    ——金 1<2 → affordable=False。"""
    _patch_button_frame(monkeypatch, anchor=False, price_texts=['G2'])
    btn = read_shop_refresh_button(_fake_ctx([]), None, gold=1)
    assert btn == ShopRefreshButton(free=False, free_remaining=None,
                                    price=2, affordable=False)


def test_button_paid_state_gold_unread(monkeypatch: pytest.MonkeyPatch) -> None:
    """金失读(gold=None)→ affordable=None,禁猜可负担。"""
    _patch_button_frame(monkeypatch, anchor=False, price_texts=['G2'])
    btn = read_shop_refresh_button(_fake_ctx([]), None, gold=None)
    assert btn.free is False and btn.price == 2 and btn.affordable is None


def test_button_anchor_miss_price_none_is_unknown(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """锚未中∧标价也读不出 → free=**None**(禁判 False:真免费帧双 OCR
    双漏误判付费会混进付费计数,§3.3.7 毒化;回退逻辑账 = 保守形态)。"""
    _patch_button_frame(monkeypatch, anchor=False, price_texts=[])
    btn = read_shop_refresh_button(_fake_ctx([]), None, gold=5)
    assert btn.free is None and btn.price is None


def test_button_anchor_unread_is_unknown(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """锚失读(area 缺失/识别异常)→ free=None 即使标价读出(免费帧次数
    1-9 与标价值域重叠,锚不可用时数字不可归边);price 仍透传供观察。"""
    _patch_button_frame(monkeypatch, anchor=None, price_texts=['G2'])
    btn = read_shop_refresh_button(_fake_ctx([]), None)
    assert btn.free is None and btn.price == 2 and btn.affordable is None


def test_button_count_two_level_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """次数读数两级管线:第一级(3x 放大)读空 → 第二级(OTSU)重试出值。"""
    calls = _patch_button_frame(monkeypatch, anchor=True, price_texts=[],
                                count_texts=['7'])
    monkeypatch.setattr(
        cw_shop_refresh_obs, '_ocr_upscaled',
        lambda ctx, screen, rect, scale=3: [])   # 第一级恒空
    btn = read_shop_refresh_button(_fake_ctx([]), None)
    assert btn.free_remaining == 7, '第二级必须出值'
    assert calls['binarized'] == 1, '第一级空后必须实调第二级'


# ===== 2. 真值通道闸(apply_action_outcome 免费判定) =====

def _drive_refresh(monkeypatch: pytest.MonkeyPatch,
                   ledger: object,
                   balance: int | None,
                   defect_calls: list | None = None) -> \
        object:   # GameState(惰性注解,免内核导入面上移)
    """驱动一次 RefreshShop 落地门;每用例新 session(新局新 GameState,
    防跨用例计数串染),返回该局 bs 供断言。"""
    if defect_calls is not None:
        monkeypatch.setattr(_defects, 'record_defect',
                            lambda *a, **kw: defect_calls.append((a, kw)))
    session = SimpleNamespace(shop_state_frame=None)
    if balance is not None:
        bs0 = board_state_of(session)
        bs0.write_logic(bs0.free_refresh_balance, balance,
                        produced_by='effect', sig=ChannelSig(
                            family='logic_hook', actor='TestRefreshButtonWriter',
                            mode='compute'))
    aop = RefreshShopOp(RefreshShop())
    state = CwWorkFrame(bench=[])
    cw_op_buy_cards.apply_action_outcome(
        aop, aop.action, True, state,
        SimpleNamespace(session=session), ledger, [])
    return board_state_of(session)


def _ticket_kinds(defect_calls: list) -> list:
    """缺陷票 kind 提取(record_defect 桩收集形态:args[1] = kind 位置参)。"""
    kinds = []
    for args, kw in defect_calls:
        kinds.append(args[1] if len(args) > 1 else kw.get('kind'))
    return kinds


def test_truth_free_with_unmodeled_balance(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """真值=True∧账未建模(概率事件 proc 形态:UI 免费但余额恒空)→
    按免费记账:paid 计数禁写(§3.3.7 付费域纯净性),total 照计。"""
    ledger = ShopVisitLedger()
    ledger.refresh_free_truth = True
    bs = _drive_refresh(monkeypatch, ledger, balance=None)
    assert bs.paid_refresh_count.value is None
    assert bs.total_refresh_count.value == 1
    assert bs.free_refresh_balance.value == 0, '免费消耗下限 0'


def test_truth_paid_overrides_stale_balance(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """真值=False∧账>0(幽灵余额:窗期回收未建模)→ 观察赢按付费记账,
    幽灵余额不被消耗(写入=仅逻辑,观察通道不改写余额,fields.md §3.3.6)。"""
    ledger = ShopVisitLedger()
    ledger.refresh_free_truth = False
    bs = _drive_refresh(monkeypatch, ledger, balance=3)
    assert bs.paid_refresh_count.value == 1
    assert bs.free_refresh_balance.value == 3, '观察通道禁改写逻辑账'


def test_truth_none_falls_back_to_balance(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """真值失读(None,含旧 ledger 无字段形态)→ 回退逻辑账判定
    (接线前保守形态,行为逐位一致:余额>0 → 免费路径)。"""
    ledger = SimpleNamespace(refresh_first_action=True)   # 旧形态无真值字段
    bs = _drive_refresh(monkeypatch, ledger, balance=2)
    assert bs.free_refresh_balance.value == 1, '免费余额消耗'
    assert bs.paid_refresh_count.value is None


def test_divergence_ticket_on_truth_logic_split(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """真值↔逻辑账分歧 → 分歧票落账(kind=free_truth_logic_divergence)。"""
    calls: list = []
    ledger = ShopVisitLedger()
    ledger.refresh_free_truth = False
    ledger.refresh_free_remaining_truth = None
    _drive_refresh(monkeypatch, ledger, balance=3, defect_calls=calls)
    assert 'free_truth_logic_divergence' in _ticket_kinds(calls), \
        f'分歧票未落: {_ticket_kinds(calls)}'


def test_count_mismatch_ticket_on_free_frame(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """免费帧次数余量联动:UI 次数 vs 逻辑账刷前值失配 → 联动票落账
    (发放桥/消耗闸漂移的唯一在环检测位,零决策)。"""
    calls: list = []
    ledger = ShopVisitLedger()
    ledger.refresh_free_truth = True
    ledger.refresh_free_remaining_truth = 2
    _drive_refresh(monkeypatch, ledger, balance=3, defect_calls=calls)
    kinds = _ticket_kinds(calls)
    assert 'free_balance_ui_mismatch' in kinds, f'联动票未落: {kinds}'
    assert 'free_truth_logic_divergence' not in kinds, \
        '真值(True)与账判定(2>0=True)一致,禁产分歧噪声'


def test_consistent_truth_no_ticket(monkeypatch: pytest.MonkeyPatch) -> None:
    """真值与账一致 + 次数相等 → 零票(联动只报失配,不产噪声)。"""
    calls: list = []
    ledger = ShopVisitLedger()
    ledger.refresh_free_truth = True
    ledger.refresh_free_remaining_truth = 2
    bs = _drive_refresh(monkeypatch, ledger, balance=2, defect_calls=calls)
    assert calls == [], f'一致态不得落票: {calls}'
    assert bs.free_refresh_balance.value == 1


# ===== 3. 免费帧喂入口闸(read_game_state 商店开态) =====

def _feed_ctx(sess: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(
        cw_match=SimpleNamespace(session=sess),
        screen_loader=SimpleNamespace(get_screen=lambda name: None),
        ocr_service=SimpleNamespace(get_ocr_result_list=lambda **kw: []),
    )


def _patch_feed_readers(monkeypatch: pytest.MonkeyPatch) -> None:
    """观察流其他 reader 桩(零像素,复刻 test_cw_game_state._feed 套路)。"""
    from sr_od.application.currency_war.kernel import cw_reconcile
    from sr_od.application.currency_war.obs import cw_observation as obs

    monkeypatch.setattr(obs, 'read_gold_settled', lambda ctx, screen: 20,
                        raising=False)
    monkeypatch.setattr(obs, 'read_phase_round', lambda ctx, screen: (1, 5),
                        raising=False)
    monkeypatch.setattr(cw_reconcile, 'reconcile_hp',
                        lambda sess_, opt, screen, source='', node_t=None:
                        (82, False), raising=False)
    monkeypatch.setattr(obs, 'read_level_up_cost', lambda ctx, screen: 4,
                        raising=False)
    monkeypatch.setattr(obs, 'board_from_tracked', lambda tracked: None,
                        raising=False)
    monkeypatch.setattr(obs, '_board_pairs',
                        lambda ctx, screen, max_count=9, expected=None:
                        ({}, False), raising=False)
    monkeypatch.setattr(obs, 'read_shop_cards', lambda ctx, screen: [],
                        raising=False)
    monkeypatch.setattr(obs, 'read_refresh_probs', lambda ctx, screen: None,
                        raising=False)


def test_feed_free_frame_carries_never_writes_count_as_price(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """免费帧喂入口闸:先有付费帧写的旧标价,再喂免费帧(锚命中)→
    shop_refresh_cost carry 沿旧值,**禁落次数当标价**(§3.3.4 免费帧不写;
    T-15 推翻「免费帧无数字」旧假设后的结构性防线)。"""
    from sr_od.application.currency_war.obs import cw_observation as obs

    _patch_feed_readers(monkeypatch)
    sess = SimpleNamespace(last_streak=0, active_strategies=[])
    # 前置:付费帧写入旧标价 2(独立 session,零桩污染)
    monkeypatch.setattr(
        cw_shop_refresh_obs, 'read_shop_refresh_button',
        lambda ctx, screen, gold=None: ShopRefreshButton(
            free=False, free_remaining=None, price=2, affordable=True),
    )
    obs.read_game_state(_feed_ctx(sess), None, phase='prep_shop_open')
    bs = board_state_of(sess)
    assert bs.shop_refresh_cost.value == 2, '前置付费帧应已写标价'

    # 免费帧:锚命中(次数 2)→ carry 沿旧值,次数禁入标价通道
    monkeypatch.setattr(
        cw_shop_refresh_obs, 'read_shop_refresh_button',
        lambda ctx, screen, gold=None: ShopRefreshButton(
            free=True, free_remaining=2, price=None, affordable=True),
    )
    obs.read_game_state(_feed_ctx(sess), None, phase='prep_shop_open')
    bs2 = board_state_of(sess)
    assert bs2.shop_refresh_cost.value == 2, '免费帧沿旧标价'
    assert bs2.shop_refresh_cost.source == 'carried', \
        f'免费帧必须走 carry,实得 {bs2.shop_refresh_cost.source}'


def test_feed_paid_frame_observes_price(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """对照(付费帧):锚未中+标价读出 → 照旧 observe(行为逐位一致);
    同帧 gold 透传闸:喂入口必须把 state.gold 传按钮态闸(灰态判别定谳
    =逻辑面金价对比,观察侧 affordable 由本透传活化)。"""
    from sr_od.application.currency_war.obs import cw_observation as obs

    _patch_feed_readers(monkeypatch)
    captured: dict = {}

    def _btn_spy(ctx: object, screen: object, gold: int | None = None) \
            -> ShopRefreshButton:
        captured['gold'] = gold
        return ShopRefreshButton(free=False, free_remaining=None,
                                 price=2, affordable=True)

    monkeypatch.setattr(cw_shop_refresh_obs, 'read_shop_refresh_button',
                        _btn_spy)
    sess = SimpleNamespace(last_streak=0, active_strategies=[])
    obs.read_game_state(_feed_ctx(sess), None, phase='prep_shop_open')
    bs = board_state_of(sess)
    assert bs.shop_refresh_cost.value == 2
    assert bs.shop_refresh_cost.source == 'observation'
    assert captured['gold'] == 20, \
        f'喂入口必须透传同帧 state.gold(read_gold_settled 桩=20),实得 {captured}'


def test_feed_gold_unread_passes_none(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """金失读帧:read_gold_settled 失读 → gold_readable=False,喂入口传
    gold=**None** 保真(禁 0 假值混进可负担对比:0≥价恒 False 会把失读
    误判成不可负担)→ composite 内 affordable=None 按失读处理。"""
    from sr_od.application.currency_war.obs import cw_observation as obs

    _patch_feed_readers(monkeypatch)
    monkeypatch.setattr(obs, 'read_gold_settled', lambda ctx, screen: None,
                        raising=False)
    captured: dict = {}

    def _btn_spy(ctx: object, screen: object, gold: int | None = None) \
            -> ShopRefreshButton:
        captured['gold'] = gold
        return ShopRefreshButton(free=False, free_remaining=None,
                                 price=2, affordable=None)

    monkeypatch.setattr(cw_shop_refresh_obs, 'read_shop_refresh_button',
                        _btn_spy)
    sess = SimpleNamespace(last_streak=0, active_strategies=[])
    obs.read_game_state(_feed_ctx(sess), None, phase='prep_shop_open')
    assert captured['gold'] is None, \
        f'金失读必须传 None 禁 0 假值,实得 {captured}'


# ===== 4. 真帧锁(三态归档 fixture × 项目真 OCR;本地跑,模型缺 → skip) =====

_SHOP_SCREEN_DIR = '货币战争-备战-开商店'
_FREE_FRAME = '免费刷新可用'
_PAID_FRAME = '刷新耗尽付费态'
_GRAY_FRAME = '刷新不可用灰态'


@pytest.fixture(scope='module')
def real_ocr_ctx(test_context: SrTestContext):
    """module 级真 OCR 服务(T-84 R2):OnnxOcrMatcher 模型加载一次,
    本文件三条真帧锁用例共享(原逐用例 helper 每条重付模型 init 3-5s);
    模型缺 → 整组 skip。替换值拆卸时还原,不向 session 级 test_context 泄漏。"""
    from one_dragon.base.matcher.ocr.ocr_service import OcrService
    from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher
    try:
        matcher = OnnxOcrMatcher()
        if not matcher.init_model(download_by_github=False,
                                  download_by_gitee=True):
            pytest.skip('OCR 模型不可用')
    except Exception:
        pytest.skip('OCR 模型不可用')
    prev = test_context.ocr_service
    test_context.ocr_service = OcrService(ocr_matcher=matcher)
    yield test_context
    test_context.ocr_service = prev


def test_button_real_fixtures(real_ocr_ctx: SrTestContext) -> None:
    """三态真帧锁(T-15 采证帧归档;同帧离线重放 = analyze_screen 对账的
    测试内形态):免费帧锚命中读数 2 / 付费帧标价 2 可负担 / 灰态帧标价 2
    金 1 不可负担。fixture/模型缺 → skip;area 缺 = fail(配置缺陷非环境
    缺失,T-85 区分告警:分文件已建而 merged 缺 = 漏再生/漏随批提交)。"""
    fix_dir = Path(__file__).resolve().parents[4] / 'screens' / _SHOP_SCREEN_DIR
    frames = [fix_dir / f'{n}.webp' for n in
              (_FREE_FRAME, _PAID_FRAME, _GRAY_FRAME)]
    if not all(p.exists() for p in frames):
        pytest.skip('fixture 缺失')
    if real_ocr_ctx.screen_loader.get_area(
            '货币战争-备战-开商店', '标识-免费刷新') is None:
        pytest.fail(
            '标识-免费刷新 area 未入运行时 screen_info(merged)——配置缺陷'
            '非环境缺失:分文件已建而 merged 缺 = 漏再生/漏随批提交'
            '(dd-029/T-13 形态),请再生 merged 并随批提交')

    from one_dragon.utils import cv2_utils

    img_free = cv2_utils.read_image(str(frames[0]))
    btn = read_shop_refresh_button(real_ocr_ctx, img_free, gold=48)
    assert btn.free is True, f'免费帧锚应命中: {btn}'
    assert btn.free_remaining == 2, f'免费帧次数应读 2: {btn}'
    assert btn.price is None

    img_paid = cv2_utils.read_image(str(frames[1]))
    btn = read_shop_refresh_button(real_ocr_ctx, img_paid, gold=61)
    assert btn.free is False, f'付费帧锚应未中: {btn}'
    assert btn.price == 2 and btn.affordable is True, f'{btn}'

    img_gray = cv2_utils.read_image(str(frames[2]))
    btn = read_shop_refresh_button(real_ocr_ctx, img_gray, gold=1)
    assert btn.free is False, f'灰态帧锚应未中(渲染同付费): {btn}'
    assert btn.price == 2 and btn.affordable is False, f'{btn}'


def test_free_anchor_three_state_boundary(real_ocr_ctx: SrTestContext) -> None:
    """「标识-免费刷新」锚判别边界直锁(三态归档帧 × 真 OCR,直接打锚
    函数):免费帧命中(True)/付费帧不命中/灰态帧不命中(False)。本 area
    ``id_mark=false``(画面级判定不依赖它),通用 id_mark 扫描不覆盖其
    判别边界——lcs 0.7 对付费/灰态「刷新」两字的拒识在此独立锁死,防
    rect/阈值调整或 OCR 行为漂移静默破坏三态判别(T-84)。fixture/模型缺
    → skip;area 缺 = fail(配置缺陷非环境缺失,T-85 区分告警)。"""
    fix_dir = Path(__file__).resolve().parents[4] / 'screens' / _SHOP_SCREEN_DIR
    frames = [fix_dir / f'{n}.webp' for n in
              (_FREE_FRAME, _PAID_FRAME, _GRAY_FRAME)]
    if not all(p.exists() for p in frames):
        pytest.skip('fixture 缺失')
    if real_ocr_ctx.screen_loader.get_area(
            '货币战争-备战-开商店',
            cw_shop_refresh_obs._FREE_ANCHOR_AREA) is None:
        pytest.fail(
            '标识-免费刷新 area 未入运行时 screen_info(merged)——配置缺陷'
            '非环境缺失:分文件已建而 merged 缺 = 漏再生/漏随批提交'
            '(dd-029/T-13 形态),请再生 merged 并随批提交')

    from one_dragon.utils import cv2_utils

    img_free = cv2_utils.read_image(str(frames[0]))
    assert cw_shop_refresh_obs._free_anchor_hit(real_ocr_ctx, img_free) is True, \
        '免费帧锚应命中(真阳性——免费态判定的唯一 UI 事实源)'
    for name, img_path in ((_PAID_FRAME, frames[1]),
                           (_GRAY_FRAME, frames[2])):
        img = cv2_utils.read_image(str(img_path))
        assert cw_shop_refresh_obs._free_anchor_hit(real_ocr_ctx, img) is False, \
            f'{name} 锚必须不命中(「刷新」两字 lcs 2/4=0.5 < 0.7 拒识边界)'


def test_price_reader_free_frame_count_is_not_price_via_gate(
        real_ocr_ctx: SrTestContext) -> None:
    """隐患锁(T-15 发现):免费帧次数数字同 rect,标价 reader 直调会误读
    ——免费帧的正确消费路径 = 按钮态闸先行(喂入口已接),本锁钉住
    「免费帧经 composite 不产标价」;直调误读行为如实留证不回退。area 缺
    = fail(配置缺陷非环境缺失,T-85 区分告警)。"""
    fix_dir = Path(__file__).resolve().parents[4] / 'screens' / _SHOP_SCREEN_DIR
    frame = fix_dir / f'{_FREE_FRAME}.webp'
    if not frame.exists():
        pytest.skip('fixture 缺失')
    if real_ocr_ctx.screen_loader.get_area(
            '货币战争-备战-开商店', '标识-免费刷新') is None:
        pytest.fail(
            '标识-免费刷新 area 未入运行时 screen_info(merged)——配置缺陷'
            '非环境缺失:分文件已建而 merged 缺 = 漏再生/漏随批提交'
            '(dd-029/T-13 形态),请再生 merged 并随批提交')
    from one_dragon.utils import cv2_utils
    from sr_od.application.currency_war.obs.cw_shop_refresh_obs import (
        read_shop_refresh_price,
    )
    img = cv2_utils.read_image(str(frame))
    assert read_shop_refresh_price(real_ocr_ctx, img) == 2, \
        '免费帧次数 2 会被标价 reader 误读为 2(隐患实证;消费方必须先过按钮态闸)'
    btn = read_shop_refresh_button(real_ocr_ctx, img)
    assert btn.free is True and btn.price is None, \
        '经 composite 消费则结构性隔离(free 分支零标价通道)'
