"""obs 识别层·安全默认与防线语义(重建合同 ②)。

obs 设计原则「OCR 失败/越界 → 安全默认,不抛错」有三种方向不同的契约——方向错了
会造成错误买入/误触发保血/假复位连胜链。本文件桩化 OCR 底层(monkeypatch 模块内
_ocr/_area_rect 系),检验「OCR 层吐出 X → 读取器产出 Y」的合同:
- gold 失读 → 0(plan 不买);*_opt/settled 失读 → None(保真,退路归调用方);
- hp 失读 → None(决策层经 reconcile_hp 沿用,不冒认真 100);
- 越界读(sanity bounds)一律拒信——越界读比读不到更危险;
- cap 域外防抖:重读入域采重读/双帧一致域外采信/其余拒信(ADR-0286/0420)。
组织蓝图 = obs 先删后重建规格 §2②(.debug 产物,语义以本文件 docstring 为准)。
"""
from types import SimpleNamespace

import numpy as np

from one_dragon.base.geometry.rectangle import Rect
from sr_od.application.currency_war.obs import cw_observation as cobs
from sr_od.application.currency_war.obs import cw_resume_lock as rlock
from sr_od.application.currency_war.obs import cw_shop_refresh_obs as srefresh

_SCREEN = np.zeros((200, 2000, 3), dtype=np.uint8)
_SMALL_RECT = Rect(10, 10, 50, 30)


def _fake_ocr(texts: list[str]):
    """伪 ocr_service:无视图像恒返回给定文本(仓内既有约定:mock 不承载像素)。"""
    return SimpleNamespace(get_ocr_result_list=lambda image=None, rect=None, **k: [
        SimpleNamespace(data=t, x=0, y=0, width=10, height=10) for t in texts])


def _patch_area(monkeypatch, rect=_SMALL_RECT):
    monkeypatch.setattr(cobs, '_area_rect', lambda ctx, name, screen_name=None: rect)


# ===== gold 家族:0 默认(决策) vs None 保真(判读) vs 越界拒信 =====

class TestGoldSafety:
    """gold 三契约:read_gold 失读 0(不买)/ *_opt 失读 None / 越界拒信。"""

    def test_miss_returns_zero_for_plan(self, monkeypatch):
        _patch_area(monkeypatch)
        monkeypatch.setattr(cobs, '_first_int', lambda texts: None)
        ctx = SimpleNamespace(ocr_service=_fake_ocr([]), controller=None)
        assert cobs.read_gold(ctx, _SCREEN) == 0

    def test_opt_miss_is_none(self, monkeypatch):
        _patch_area(monkeypatch)
        monkeypatch.setattr(cobs, '_first_int', lambda texts: None)
        ctx = SimpleNamespace(ocr_service=_fake_ocr([]), controller=None)
        assert cobs.read_gold_opt(ctx, _SCREEN) is None
        assert cobs.read_gold_settled(ctx, _SCREEN) is None

    def test_out_of_bounds_rejected(self, monkeypatch):
        # GOLD_MAX=400:读成 500 = OCR 假阳;越界读比读不到更危险 → None
        _patch_area(monkeypatch)
        assert cobs.read_gold_opt(
            SimpleNamespace(ocr_service=_fake_ocr(['500']), controller=None),
            _SCREEN) is None

    def test_in_bounds_passes(self, monkeypatch):
        _patch_area(monkeypatch)
        assert cobs.read_gold_opt(
            SimpleNamespace(ocr_service=_fake_ocr(['320']), controller=None),
            _SCREEN) == 320

    def test_settled_no_controller_single_frame(self, monkeypatch):
        # 无控制器(离线/单测):稳定门退单帧读,行为与修前一致
        _patch_area(monkeypatch)
        monkeypatch.setattr(cobs.time, 'sleep', lambda s: None)
        ctx = SimpleNamespace(ocr_service=_fake_ocr(['320']), controller=None)
        assert cobs.read_gold_settled(ctx, _SCREEN) == 320

    def test_settled_disagree_takes_last(self, monkeypatch):
        # 入账计数器在动:两帧不一致采末帧(入账后真值)+ 留证,不静默
        monkeypatch.setattr(cobs, 'GOLD_SETTLE_INTERVAL_S', 0.0)
        _patch_area(monkeypatch)
        conflicts = []
        monkeypatch.setattr(cobs, 'obs_conflict',
                            lambda *a, **k: conflicts.append(a[0]))
        frames = [[SimpleNamespace(data='320', x=0, y=0, width=10, height=10)],
                  [SimpleNamespace(data='325', x=0, y=0, width=10, height=10)],
                  [SimpleNamespace(data='325', x=0, y=0, width=10, height=10)]]
        ctx = SimpleNamespace(ocr_service=SimpleNamespace(
            get_ocr_result_list=lambda image=None, **k: frames.pop(0)),
            controller=SimpleNamespace(screenshot=lambda: _SCREEN))
        assert cobs.read_gold_settled(ctx, _SCREEN) == 325
        assert conflicts == ['gold']


# ===== hp 家族:None 保真 + 双通道对账采放大值 =====

class TestHpSafety:
    """hp:失读 None(不冒认真 100);原生/放大不一致采放大(丢十位实证)。"""

    def _patch_hp_reads(self, monkeypatch, native: list[str], upscaled: list[str]):
        _patch_area(monkeypatch)
        monkeypatch.setattr(cobs, '_ocr', lambda ctx, screen, rect: [
            SimpleNamespace(data=t) for t in native])
        monkeypatch.setattr(cobs, '_ocr_upscaled', lambda ctx, screen, rect, scale=3: [
            SimpleNamespace(data=t) for t in upscaled])
        monkeypatch.setattr(cobs, '_ocr_upscaled_binarized',
                            lambda ctx, screen, rect, scale=3: [])

    def test_miss_is_none(self, monkeypatch):
        # shop 开态 HP 区空:None 由 reconcile 层沿用,读取器不造假值
        self._patch_hp_reads(monkeypatch, [], [])
        assert cobs.read_hp_opt(
            SimpleNamespace(ocr_service=_fake_ocr([])), _SCREEN) is None

    def test_out_of_bounds_rejected(self, monkeypatch):
        # HP_MAX=200:读成 500 = OCR 假阳 → None(决策层对 None 有安全路径)
        self._patch_hp_reads(monkeypatch, ['500'], [])
        assert cobs.read_hp_opt(
            SimpleNamespace(ocr_service=_fake_ocr([])), _SCREEN) is None

    def test_dual_channel_agree(self, monkeypatch):
        self._patch_hp_reads(monkeypatch, ['47'], ['47'])
        assert cobs.read_hp_opt(
            SimpleNamespace(ocr_service=_fake_ocr([])), _SCREEN) == 47

    def test_dual_channel_disagree_takes_upscaled(self, monkeypatch):
        # 原生丢十位实证(47→4):不一致采放大值 + obs_conflict 留证
        self._patch_hp_reads(monkeypatch, ['4'], ['47'])
        conflicts = []
        monkeypatch.setattr(cobs, 'obs_conflict',
                            lambda *a, **k: conflicts.append(a[0]))
        assert cobs.read_hp_opt(
            SimpleNamespace(ocr_service=_fake_ocr([])), _SCREEN) == 47
        assert conflicts == ['hp']

    def test_native_miss_upscaled_recovers(self, monkeypatch):
        # 低血小数值原生 det 漏检、放大即恢复(局21 P2 r4 先例)
        self._patch_hp_reads(monkeypatch, [], ['12'])
        assert cobs.read_hp_opt(
            SimpleNamespace(ocr_service=_fake_ocr([])), _SCREEN) == 12


# ===== level 家族:值域拒信 + 三级兜底 =====

class TestLevelSafety:
    """level:直读值域 1..10 外按失读;三级兜底 OCR→XP 反推→期望曲线。"""

    def test_raw_out_of_domain_is_miss(self, monkeypatch):
        _patch_area(monkeypatch)
        monkeypatch.setattr(cobs, '_ocr_upscaled', lambda ctx, screen, rect, scale=3: [
            SimpleNamespace(data='15')])
        assert cobs.read_level_raw_opt(
            SimpleNamespace(ocr_service=_fake_ocr([])), _SCREEN) is None

    def test_raw_in_domain(self, monkeypatch):
        _patch_area(monkeypatch)
        monkeypatch.setattr(cobs, '_ocr_upscaled', lambda ctx, screen, rect, scale=3: [
            SimpleNamespace(data='7')])
        assert cobs.read_level_raw_opt(
            SimpleNamespace(ocr_service=_fake_ocr([])), _SCREEN) == 7

    def test_level_falls_to_expected_curve(self, monkeypatch):
        # OCR 失读 + 无 XP + 无 session 先验 → 期望曲线兜底;
        # 期望值从单一源(cw_economy)现算对照,不手抄常数(纪律第 9 条)
        monkeypatch.setattr(cobs, 'read_level_raw_opt', lambda ctx, screen: None)
        monkeypatch.setattr(cobs, 'read_xp_progress',
                            lambda ctx, screen, expected_level=None: None)
        ctx = SimpleNamespace()   # 无 cw_match → 无先验
        from sr_od.application.currency_war.kernel.cw_economy import _expected_level
        assert cobs.read_level(ctx, _SCREEN, plane=2, round_num=3) == \
            _expected_level(3, 2)

    def test_level_miss_inverts_from_xp_bar(self, test_context, monkeypatch):
        # 真帧锁(2026-08-26 佩佩局实弹修复):等级漏读 → 经验条反推真级
        # ("0/4"→lv3);仍读不到才退期望曲线。旧期望兜底 4 → cap−level=0 →
        # 后排选 6 格档 → 佩佩@slot7 窗口未被枚举丢读(事故背书)
        from one_dragon.utils import cv2_utils
        from one_dragon.utils.file_utils import get_project_root
        img = cv2_utils.read_image(str(
            get_project_root() / 'sr-od-test' / 'screens' / '货币战争-备战'
            / '后排7槽-佩佩局-拖测后.png'))
        assert img is not None, '佩佩局真帧缺失'
        monkeypatch.setattr(cobs, 'read_level_raw_opt', lambda ctx, scr: None)
        got = cobs.read_level(test_context, img, 1, 1)
        assert got == 3, f'经验条反推应为 lv3(0/4),实得 {got}'
        monkeypatch.setattr(cobs, 'read_xp_progress', lambda ctx, scr, **kw: None)
        assert cobs.read_level(test_context, img, 1, 1) == cobs._expected_level(1, 1)


# ===== cap 防抖门(ADR-0286/0420):域内直通 / 重读入域 / 双帧一致采信 / 其余拒信 =====

class TestCapDebounce:
    """cap 真值防抖:合法域 level..level+2;域外重读一帧,四种出口各有语义。"""

    def _patch_cap_reads(self, monkeypatch, caps: list[int | None]):
        """桩 read_deploy_cap 依序返回 caps;记录 screenshot 调用次数。"""
        calls = {'shots': 0}
        seq = list(caps)

        def fake_read(ctx, screen, level=None):
            return seq.pop(0) if seq else None
        monkeypatch.setattr(cobs, 'read_deploy_cap', fake_read)

        def fake_shot():
            calls['shots'] += 1
            return _SCREEN
        return calls, fake_shot

    def test_in_domain_direct(self, monkeypatch):
        calls, shot = self._patch_cap_reads(monkeypatch, [6])
        ctx = SimpleNamespace(controller=SimpleNamespace(screenshot=shot))
        assert cobs._debounce_cap(ctx, _SCREEN, 6, level=5) == 6
        assert calls['shots'] == 0   # 域内直通,零重读成本

    def test_none_passthrough(self, monkeypatch):
        calls, shot = self._patch_cap_reads(monkeypatch, [])
        ctx = SimpleNamespace(controller=SimpleNamespace(screenshot=shot))
        assert cobs._debounce_cap(ctx, _SCREEN, None, level=5) is None
        assert calls['shots'] == 0   # 失读无防抖对象,不重读

    def test_out_of_domain_reread_in_domain_adopted(self, monkeypatch):
        # 瞬时误读族:重读入域 → 采重读值
        calls, shot = self._patch_cap_reads(monkeypatch, [6])
        ctx = SimpleNamespace(controller=SimpleNamespace(screenshot=shot))
        assert cobs._debounce_cap(ctx, _SCREEN, 12, level=5) == 6
        assert calls['shots'] == 1

    def test_out_of_domain_consistent_pair_adopted(self, monkeypatch):
        # 域外双帧一致(≤绝对上界 13)采信:真实高档 e4972b43 diff=5 实拍(ADR-0420)
        calls, shot = self._patch_cap_reads(monkeypatch, [12])
        ctx = SimpleNamespace(controller=SimpleNamespace(screenshot=shot))
        assert cobs._debounce_cap(ctx, _SCREEN, 12, level=5) == 12

    def test_beyond_abs_max_rejected_even_if_consistent(self, monkeypatch):
        # 超 13:即使双帧一致也拒(OCR 结构性误读可跨帧复现)
        calls, shot = self._patch_cap_reads(monkeypatch, [15])
        ctx = SimpleNamespace(controller=SimpleNamespace(screenshot=shot))
        assert cobs._debounce_cap(ctx, _SCREEN, 15, level=5) is None

    def test_out_of_domain_inconsistent_rejected(self, monkeypatch):
        # 重读仍域外且不一致 → None(决策兜底 level,与未读到同态)
        calls, shot = self._patch_cap_reads(monkeypatch, [3])
        ctx = SimpleNamespace(controller=SimpleNamespace(screenshot=shot))
        assert cobs._debounce_cap(ctx, _SCREEN, 12, level=5) is None


# ===== 刷新钮标价/免费次数:0 拒信(免费≠标价0)+ 域外失读(不猜截位) =====

class TestRefreshPriceDigit:
    """_parse_price_digit:图标并入归一(O→0)+ 可信域 1..9 + 逐条扫描。"""

    def test_plain_digit(self):
        assert srefresh._parse_price_digit(['5']) == 5

    def test_icon_prefix_normalized(self):
        # 金币图标并入('GO'/'G2'):O→0 映射后逐条取首个域内整数
        assert srefresh._parse_price_digit(['G5']) == 5
        assert srefresh._parse_price_digit(['O2']) == 2

    def test_icon_only_then_digit_scanned(self):
        # 图标与数字拆两条('GO'+'2'):首条产出 0 域外继续扫,不丢真值
        assert srefresh._parse_price_digit(['GO', '2']) == 2

    def test_zero_rejected_free_frame_is_not_price_zero(self):
        # 免费帧读不到 ≠ 标价 0(§3.3.4):产出 0 一律拒信
        assert srefresh._parse_price_digit(['GO']) is None
        assert srefresh._parse_price_digit(['0']) is None

    def test_two_digits_rejected_not_truncated(self):
        # 一位数渲染域,两位数无在册证据 → 失读,不猜测截位
        assert srefresh._parse_price_digit(['12']) is None


class TestRefreshPriceReader:
    """read_shop_refresh_price:两级管线读空 → None;禁兜底改值(ADR-0622)。"""

    def test_miss_is_none_no_fallback(self, monkeypatch):
        monkeypatch.setattr(srefresh, '_area_rect',
                            lambda ctx, name, screen_name=None: _SMALL_RECT)
        monkeypatch.setattr(srefresh, '_ocr_upscaled', lambda ctx, screen, rect, scale=3: [])
        monkeypatch.setattr(srefresh, '_ocr_upscaled_binarized',
                            lambda ctx, screen, rect, scale=3: [])
        # None = 失读,调用方按失读处理;不回退基价常量
        assert srefresh.read_shop_refresh_price(
            SimpleNamespace(ocr_service=_fake_ocr([])), _SCREEN) is None

    def test_price_read(self, monkeypatch):
        monkeypatch.setattr(srefresh, '_area_rect',
                            lambda ctx, name, screen_name=None: _SMALL_RECT)
        monkeypatch.setattr(srefresh, '_ocr_upscaled', lambda ctx, screen, rect, scale=3: [
            SimpleNamespace(data='2')])
        assert srefresh.read_shop_refresh_price(
            SimpleNamespace(ocr_service=_fake_ocr([])), _SCREEN) == 2


class TestFreeCount:
    """_parse_free_count:域 1..9999;0 不渲染免费钮(在场即余额>0)。"""

    def test_plain(self):
        assert srefresh._parse_free_count(['免费刷新', '2']) == 2

    def test_upper_bound(self):
        assert srefresh._parse_free_count(['9999']) == 9999

    def test_zero_rejected(self):
        assert srefresh._parse_free_count(['0']) is None

    def test_over_registry_max_rejected(self):
        assert srefresh._parse_free_count(['10000']) is None


# ===== 恢复局判定(W62/ADR-0329):判定门/探针裁决/锁定解除 =====

class TestResumeLock:
    """恢复局三判据:新 match + round>1 候选;商店可开=非锁定;出战成功=解锁。"""

    def test_resume_candidate_mid_run(self):
        assert rlock.resume_candidate(is_new_match=True, plane=1, round_num=3) is True

    def test_resume_candidate_later_plane(self):
        assert rlock.resume_candidate(is_new_match=True, plane=2, round_num=1) is True

    def test_normal_new_match_not_candidate(self):
        assert rlock.resume_candidate(is_new_match=True, plane=1, round_num=1) is False

    def test_existing_match_never_candidate(self):
        assert rlock.resume_candidate(is_new_match=False, plane=2, round_num=3) is False

    def test_probe_shop_opens(self):
        assert rlock.probe_resolve(shop_opened_after_click=True) == 'normal'

    def test_probe_shop_dead(self):
        # 锁定唯一可观测特征 = 商店按钮零响应
        assert rlock.probe_resolve(shop_opened_after_click=False) == 'locked'

    def test_battle_progressed_unlocks(self):
        assert rlock.locked_after_start_battle(progressed=True) is False

    def test_battle_failed_keeps_lock(self):
        assert rlock.locked_after_start_battle(progressed=False) is True
