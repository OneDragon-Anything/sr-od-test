"""obs 识别层·入口与契约冒烟(重建合同 ⑥)。

装配件的薄冒烟:每条 = 一条行为断言,不追求覆盖率——
- read_game_state 阶段字段门(PHASE_FIELD_SPEC 单一源):阶段声明面 +
  battle_or_transit 只读位面轮次的 spy 验证;
- observe_full 组装合同(ADR-0213 v4):tier 回显/templates 未加载 None 沿用/
  MED-2 gold==0 重读只带 op+shop_open/离线不重读/substate 尽力读标注;
- recognizer 纯读契约:失读返 None 不伪造(并发安全的全局不写由
  _read_phase_round_pure 与 read_phase_round 的行为差承载);
- 词缀效果注册表落盘 roundtrip(garbage 拒写/divergent 不覆盖,D-81 语义)。
组织蓝图 = obs 先删后重建规格 §2⑥。
"""
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.obs import cw_briefing_obs as cwb
from sr_od.application.currency_war.obs import cw_observation as cobs
from sr_od.application.currency_war.obs import cw_observe_full as of_mod
from sr_od.application.currency_war.obs import cw_settlement_obs as settle_obs
from sr_od.application.currency_war.obs.recognizers import battle_prep_recognizer as bpr

# ===== read_game_state 阶段字段门(PHASE_FIELD_SPEC 单一源) =====

class TestPhaseFieldSpec:
    """阶段声明面:三阶段在册;hp 只在干净备战;退役键不复活。"""

    def test_three_phases_registered(self):
        assert set(cobs.PHASE_FIELD_SPEC) == {
            cobs.PHASE_PREP_CLEAN, cobs.PHASE_PREP_SHOP_OPEN,
            cobs.PHASE_BATTLE_OR_TRANSIT}

    def test_hp_only_in_prep_clean(self):
        # hp 区物理只在 shop 关态可见:开态/战斗帧 OCR 必 miss,是死读(ADR-0462)
        assert 'hp' in cobs.PHASE_FIELD_SPEC[cobs.PHASE_PREP_CLEAN]
        assert 'hp' not in cobs.PHASE_FIELD_SPEC[cobs.PHASE_PREP_SHOP_OPEN]
        assert 'hp' not in cobs.PHASE_FIELD_SPEC[cobs.PHASE_BATTLE_OR_TRANSIT]

    def test_bench_full_key_not_resurrected(self):
        # 「bench_full」通道已退役(迁移批次二 §3.2.5):键位删除防复活
        for fields in cobs.PHASE_FIELD_SPEC.values():
            assert 'bench_full' not in fields

    def test_battle_phase_reads_only_phase_round(self, monkeypatch):
        # spy 验证:battle_or_transit 阶段只真读位面轮次,其余字段全被门跳过
        called = {'phase_round': 0, 'gold': 0, 'hp': 0}
        monkeypatch.setattr(cobs, 'read_phase_round',
                            lambda ctx, screen: called.__setitem__(
                                'phase_round', called['phase_round'] + 1) or (2, 7))
        monkeypatch.setattr(cobs, 'read_gold_settled',
                            lambda ctx, screen: called.__setitem__('gold', 1))
        monkeypatch.setattr(cobs, 'read_hp_opt',
                            lambda ctx, screen: called.__setitem__('hp', 1))
        monkeypatch.setattr(
            'sr_od.application.currency_war.kernel.cw_observe.set_obs_phase',
            lambda phase: None)
        monkeypatch.setattr(
            'sr_od.application.currency_war.kernel.cw_reconcile.reconcile_hp',
            lambda *a, **k: (85, True))
        state = cobs.read_game_state(SimpleNamespace(), None,
                                     phase=cobs.PHASE_BATTLE_OR_TRANSIT)
        assert called == {'phase_round': 1, 'gold': 0, 'hp': 0}
        assert (state.plane, state.round_num) == (2, 7)


# ===== observe_full 组装合同(ADR-0213 v4;r331 模块级 import 打桩面) =====

class TestObserveFullAssembly:
    """heavy 组装:字段回显/templates 缺失沿用/gold 重读门/substate 标注。"""

    def _patch_heavy(self, monkeypatch, gold=0):
        monkeypatch.setattr(of_mod, 'ensure_portrait_templates',
                            lambda ctx: object())
        monkeypatch.setattr(of_mod, 'read_bench_chars',
                            lambda ctx, frame, tpl: [('bench',)])
        monkeypatch.setattr(of_mod, 'read_deployed_chars',
                            lambda ctx, frame, tpl: [('deployed',)])
        states = [SimpleNamespace(gold=gold)]
        monkeypatch.setattr(of_mod, 'read_game_state',
                            lambda ctx, frame: states[len(states) - 1]
                            if len(states) == 1 else states.pop(0))
        monkeypatch.setattr(of_mod, 'read_node_sequence',
                            lambda ctx, frame: None)          # shop 开态:圆数门 → None
        monkeypatch.setattr(of_mod, 'read_shop_cards',
                            lambda ctx, frame: ['card'])      # 开态有牌
        monkeypatch.setattr('time.sleep', lambda s: None)
        return states

    def test_heavy_assembly_and_substate(self, monkeypatch):
        self._patch_heavy(monkeypatch, gold=91)
        out = of_mod.observe_full(SimpleNamespace(), None, tier='heavy',
                                  source='director', shop_open=True)
        assert out['tier'] == 'heavy' and out['source'] == 'director'
        assert out['bench_chars'] == [('bench',)]
        assert out['deployed_chars'] == [('deployed',)]
        # substate 尽力读:标注各模块可读性,不强行全读(A5)
        assert out['substate'] == {'node_seq': False, 'shop_cards': True}
        assert out['gold_reread'] is False

    def test_templates_missing_keeps_none(self, monkeypatch):
        # 立绘库未加载 → 身份字段 None(调用方沿用缓存),不崩不造假
        monkeypatch.setattr(of_mod, 'ensure_portrait_templates', lambda ctx: None)
        monkeypatch.setattr(of_mod, 'read_game_state',
                            lambda ctx, frame: SimpleNamespace(gold=5))
        monkeypatch.setattr(of_mod, 'read_node_sequence', lambda ctx, frame: [])
        monkeypatch.setattr(of_mod, 'read_shop_cards', lambda ctx, frame: [])
        out = of_mod.observe_full(SimpleNamespace(), None, tier='heavy',
                                  source='deploy_bench')
        assert out['bench_chars'] is None
        assert out['deployed_chars'] is None

    def test_gold_zero_no_op_skips_reread(self, monkeypatch):
        # 离线契约:op 不可传 → 重读跳过(同帧重读结果恒同,无意义)
        self._patch_heavy(monkeypatch, gold=0)
        out = of_mod.observe_full(SimpleNamespace(), None, tier='heavy',
                                  source='director', shop_open=True)
        assert out['gold_reread'] is False

    def test_gold_zero_with_op_rereads_new_frame(self, monkeypatch):
        # MED-2:gold==0 ∧ op 可用 ∧ shop 开态 → 重新截图重读,成功换入
        self._patch_heavy(monkeypatch, gold=0)
        reread = {'n': 0}

        def fake_read(ctx, frame):
            reread['n'] += 1
            return SimpleNamespace(gold=75 if reread['n'] > 1 else 0)
        monkeypatch.setattr(of_mod, 'read_game_state', fake_read)
        op = SimpleNamespace(screenshot=lambda: object())
        out = of_mod.observe_full(SimpleNamespace(), None, tier='heavy',
                                  source='director', op=op, shop_open=True)
        assert out['gold_reread'] is True
        assert out['state'].gold == 75

    def test_gold_reread_only_when_shop_open(self, monkeypatch):
        # r334 F2 门:关态 gold 恒 0 是常态,重读只发生在开态(否则白付 3 帧)
        self._patch_heavy(monkeypatch, gold=0)
        reread = {'n': 0}

        def fake_read(ctx, frame):
            reread['n'] += 1
            return SimpleNamespace(gold=0)
        monkeypatch.setattr(of_mod, 'read_game_state', fake_read)
        out = of_mod.observe_full(SimpleNamespace(), None, tier='heavy',
                                  source='director', op=SimpleNamespace(
                                      screenshot=lambda: object()),
                                  shop_open=False)
        assert out['gold_reread'] is False
        assert reread['n'] == 1   # 未触发重读

    def test_light_tier_reads_state_only(self, monkeypatch):
        # light:无身份识别无 substate(轻字段读留 _observe 每步现读)
        monkeypatch.setattr(of_mod, 'read_game_state',
                            lambda ctx, frame: SimpleNamespace(gold=3))
        out = of_mod.observe_full(SimpleNamespace(), None, tier='light',
                                  source='director')
        assert 'bench_chars' not in out
        assert out['substate'] == {}


# ===== recognizer 纯读契约(并发安全的行为承载面) =====

class TestRecognizerPureRead:
    """备战识别器纯读:失读返 None 不伪造 (1,1)——与 read_phase_round
    (last-known-good 全局)的行为差即并发安全契约的承载点。"""

    def _patch_phase_ocr(self, monkeypatch, texts):
        monkeypatch.setattr(bpr, '_area_rect', lambda ctx, name: object())
        monkeypatch.setattr(bpr, '_ocr', lambda ctx, screen, rect: [
            SimpleNamespace(data=t) for t in texts])

    def test_plain_pair(self, monkeypatch):
        self._patch_phase_ocr(monkeypatch, ['2-7'])
        assert bpr._read_phase_round_pure(SimpleNamespace(), None) == (2, 7)

    def test_single_digit_form(self, monkeypatch):
        self._patch_phase_ocr(monkeypatch, ['第3位面'])
        assert bpr._read_phase_round_pure(SimpleNamespace(), None) == (3, 3)

    def test_miss_returns_none_not_fabricated(self, monkeypatch):
        # 读不到 → None:伪造 (1,1) 会把恢复局/过渡帧错记开局(M23 定因)
        self._patch_phase_ocr(monkeypatch, [])
        assert bpr._read_phase_round_pure(SimpleNamespace(), None) is None


# ===== 词缀效果注册表落盘 roundtrip(D-81/ADR-0081 语义) =====

class TestAffixEffectsRoundtrip:
    """write/load roundtrip:新 key 写入、garbage 拒写、existing divergent 不覆盖。"""

    def _patch_path(self, monkeypatch, tmp_path):
        target = tmp_path / 'affix_effects_data.py'
        monkeypatch.setattr(cwb, '_AFFIX_EFFECTS_PATH', target)
        return target

    def test_new_key_written_and_read_back(self, monkeypatch, tmp_path):
        self._patch_path(monkeypatch, tmp_path)
        assert cwb.write_affix_effects({'火之熄火': '效果原文'}) is True
        assert cwb.load_affix_effects_from_file() == {'火之熄火': '效果原文'}

    def test_garbage_rejected(self, monkeypatch, tmp_path):
        # 「下一步」= 简报按钮文字混入 → 拒写 ground truth
        self._patch_path(monkeypatch, tmp_path)
        assert cwb.write_affix_effects({'下一步': 'x'}) is False
        assert cwb.load_affix_effects_from_file() == {}

    def test_existing_divergent_not_overwritten(self, monkeypatch, tmp_path):
        # 静态数据现有值更可信:OCR 重读 divergent → 不覆盖仅留证
        self._patch_path(monkeypatch, tmp_path)
        assert cwb.write_affix_effects({'后台熄火': '旧效果'}) is True
        assert cwb.write_affix_effects({'后台熄火': '误读效果'}) is False
        assert cwb.load_affix_effects_from_file() == {'后台熄火': '旧效果'}

    def test_empty_updates_noop(self, monkeypatch, tmp_path):
        self._patch_path(monkeypatch, tmp_path)
        assert cwb.write_affix_effects({}) is False


# ===== 结算读点链组装(read_round_outcome;迁移自 test_cw_settle_telemetry 独家语义) =====

def _fake_settle_ctx(texts: list[str]) -> SimpleNamespace:
    """结算屏桩 ctx:OCR 恒返回给定文本(read_round_outcome 全屏读共用载体)。"""
    tokens = [SimpleNamespace(data=t, x=100, y=i * 40, width=60, height=30)
              for i, t in enumerate(texts)]
    return SimpleNamespace(ocr_service=SimpleNamespace(
        get_ocr_result_list=lambda image=None, rect=None, crop_first=False: tokens))


class TestRoundOutcomeChain:
    """结算屏 → RoundOutcome 的组装语义:页态门/透传/失败屏真值(DD-006/T-83)。"""

    def test_killed_and_progress_passthrough(self):
        # 败轮屏:挑战结束 -22 → killed=False;赢轮:挑战成功 → killed=True
        obs = settle_obs.read_round_outcome(
            _fake_settle_ctx(['2-1战斗', '-22', '挑战进度', '前往结算']),
            None, plane=2, round_num=1, comp_tag='x')
        assert obs.killed is False and obs.progress_delta == -22
        obs2 = settle_obs.read_round_outcome(
            _fake_settle_ctx(['31', '挑战成功', '挑战进度', '46', '继续挑战']),
            None, plane=1, round_num=8, comp_tag='x')
        assert obs2.killed is True

    def test_defeat_screen_hp_is_zero_ground_truth(self):
        # 失败屏读不到 HP 数字(garble 形态)→ hp_after=0 是 ground truth
        # (团灭确定值,confidence=1.0;与「读不到→0.0 不进 trend」的失读语义区分)
        obs = settle_obs.read_round_outcome(
            _fake_settle_ctx(['挑战失败', '下一步']), None,
            plane=1, round_num=2, comp_tag='x')
        assert obs.hp_after == 0 and obs.hp_confidence == 1.0

    def test_fill_ratio_only_on_page1(self):
        # 页态门(DD-006):页 2 帧同矩形罩 HP 心形恒读假值(0.392 三局同值实证)
        # → 无「点击空白加速」标记词不读条;页 1 帧才读
        import numpy as np
        img = np.zeros((1080, 1920, 3), np.uint8)
        img[424:440, 710:1010] = (200, 40, 40)   # 进度条 60% 红填充
        obs_p2 = settle_obs.read_round_outcome(
            _fake_settle_ctx(['挑战结束', '1-9首领', '继续挑战']), img,
            plane=1, round_num=9, comp_tag='x')
        assert obs_p2.progress_fill_ratio is None
        obs_p1 = settle_obs.read_round_outcome(
            _fake_settle_ctx(['挑战结束', '1-9首领', '点击空白加速']), img,
            plane=1, round_num=9, comp_tag='x')
        assert obs_p1.progress_fill_ratio == pytest.approx(0.6, abs=0.01)

    def test_heal_longline_passthrough_and_net_identity(self):
        # heal_longline 补链(T-83/ADR-0609):旧实现丢弃第三行 → 遥测只能靠猜;
        # 净变化恒等式:链差 = 掉血两分量 + 回血(-10 + -1 + 2 = -9)
        import numpy as np
        panel = [SimpleNamespace(data=t, x=x, y=y, width=w, height=h)
                 for t, x, y, w, h in [
                     ('小队生命值结算说明', 1348, 503, 240, 30),
                     ('基础伤害', 1250, 555, 100, 33), ('-10', 1630, 553, 60, 35),
                     ('未完成进度伤害', 1250, 588, 160, 34), ('-1', 1630, 588, 60, 34),
                     ('长线作战', 1250, 622, 100, 33), ('+2', 1630, 620, 60, 35)]]

        class _PanelOcr:
            def get_ocr_result_list(self, image, rect, crop_first):
                return list(panel)

        obs = settle_obs.read_round_outcome(
            SimpleNamespace(ocr_service=_PanelOcr()),
            np.zeros((1080, 1920, 3), np.uint8),
            plane=1, round_num=5, comp_tag='x')
        assert obs.heal_longline == 2, '回血分量未透传(补链断裂)'
        assert obs.damage_base == -10 and obs.damage_unfinished_progress == -1
        assert obs.damage_base + obs.damage_unfinished_progress \
            + obs.heal_longline == -9

    def test_outcome_row_carries_heal_longline(self):
        # RoundOutcome 行内字段(删除波 1 退役重写:观察半 history 行仍携该键)
        from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome
        from sr_od.application.currency_war.kernel.cw_state import GameState
        from sr_od.application.currency_war.strategies.impl.cw_strategy import (
            StrategySession,
        )
        sess = StrategySession()
        sess.last_state = GameState()
        o = RoundOutcome(
            round_num=5, plane=1, node_type='普通战斗', comp_tag='x',
            hp_after=91, killed=True,
            damage_base=-10, damage_unfinished_progress=-1, heal_longline=2)
        sess.pending_round_outcomes.append(o)
        sess.performance.history.append(o)
        row = sess.performance.history[-1]
        assert row.heal_longline == 2
        assert row.damage_base == -10

    def test_battle_wait_page1_stash_covers_heal_longline(self):
        # 接线存在性烟雾(纪律第 8 条容忍档;事故背书 = 旧实现丢弃第三行):
        # 页 1 暂存写入两处 + 合并键列表一处任一漏键 → 胜轮 heal_longline 恒 None
        import inspect

        from sr_od.application.currency_war.operations.cw_screen import (
            cw_screen_battle_wait,
        )
        src = inspect.getsource(cw_screen_battle_wait)
        assert src.count("'heal_longline'") >= 4, \
            '页1 暂存/合并键面漏 heal_longline(期望暂存×2+合并×1+注释面≥1)'


class TestObserveFullRereadGiveup:
    """MED-2 重读放弃分支:3 次重读仍 0 → 接受 0,不无限重试。"""

    def test_gold_reread_keeps_zero_when_all_reads_zero(self, monkeypatch):
        monkeypatch.setattr(of_mod, 'ensure_portrait_templates', lambda ctx: None)
        monkeypatch.setattr(of_mod, 'read_node_sequence', lambda ctx, frame: [])
        monkeypatch.setattr(of_mod, 'read_shop_cards', lambda ctx, frame: [])
        monkeypatch.setattr('time.sleep', lambda s: None)
        reads = {'n': 0}

        def fake_read(ctx, frame):
            reads['n'] += 1
            return SimpleNamespace(gold=0)
        monkeypatch.setattr(of_mod, 'read_game_state', fake_read)
        out = of_mod.observe_full(
            SimpleNamespace(), None, tier='heavy', source='director',
            op=SimpleNamespace(screenshot=lambda: object()), shop_open=True)
        assert out['gold_reread'] is False
        assert reads['n'] == 4   # 首读 + 3 次补采(重读上限),不无限重试

