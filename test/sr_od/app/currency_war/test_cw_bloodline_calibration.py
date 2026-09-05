"""死亡线标定落地锁(用户裁定=按 15)。

- 阈值单一源 = kernel ``lambda_death.HP_BAND_NEAR_DEATH``(=15);
  BLOODLINE_HP_THRESHOLD provisional 注入源退役(两源归一,注入值不作
  决策源);
- hp ≤ 阈值 ⇒ 解锁包三件武装(F7 禁令/M3 分流/arm2 门,行为介入
  开启)+ advisor_bloodline_armed 分键;影子键保留对照;
- λ 顾问:标定前置影子维持声明撤销——注入形态触发即真键武装,
  lambda_shadow 保留对照。
"""
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.strategies.impl.mandate_v1 import entry
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
    lambda_death,
)


def _eval_hp(hp):
    st = SimpleNamespace(node_type='战斗', enemy_difficulty=None, plane=1)
    return entry._upgrader_evaluate(SimpleNamespace(), st, 0, hp)


class TestBloodlineCalibration:

    def test_hp_below_band_arms_unlock_package(self):
        """hp≤15 ⇒ 解锁包三件武装(行为介入开启)+ 影子对照键。"""
        sig = _eval_hp(10)
        assert sig.neardeath_unlock is True
        assert sig.arm2_gate_open is True
        assert sig.f7_ban_armed is True
        assert sig.bloodline_shadow_armed is True, '影子键保留对照'

    def test_hp_band_boundary_inclusive(self):
        """hp=15(=HP_BAND_NEAR_DEATH)⇒ 武装(≤15 族,在册授权);hp=16
        ⇒ 不武装。"""
        assert _eval_hp(15).neardeath_unlock is True
        assert _eval_hp(16).neardeath_unlock is False

    def test_threshold_single_source_ignores_injected_value(self,
                                                            monkeypatch):
        """标定值单源锁:注入 BLOODLINE_HP_THRESHOLD=20 不改决策阈值
        (两源归一,单一源 = HP_BAND_NEAR_DEATH)——hp=18(<20 但 >15)
        不武装。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.audit import (
            provisional,
        )

        def _fake_get(key):
            if key == 'BLOODLINE_HP_THRESHOLD':
                return SimpleNamespace(value=20, injected_form=True)
            return None
        monkeypatch.setattr(provisional, 'get', _fake_get)
        assert _eval_hp(18).neardeath_unlock is False, (
            '注入值不得改决策阈值(单一源锁)')
        assert _eval_hp(14).neardeath_unlock is True

    def test_hp_none_fails_closed(self):
        """hp 不可得 ⇒ fail 向不武装(既有语义零变化)。"""
        sig = _eval_hp(None)
        assert sig.neardeath_unlock is False
        assert sig.bloodline_shadow_armed is False

    def test_armed_counter_written_by_emit(self, monkeypatch):
        """hp≤15 帧 → emit 决策面计 advisor_bloodline_armed +
        neardeath_unlock 分键(armed 分键在案)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            mandate,
        )
        monkeypatch.setattr(mandate, 'run_mandate',
                            lambda frame, session, **kw: [])
        st = SimpleNamespace(
            gold=40, level=6, round_num=2, hp=10, plane=1,
            node_type='战斗', shop=[], bench=[], deployed=[],
            max_units=lambda: 6, level_readable=True,
            enemy_difficulty=None, refresh_probs=None,
            shop_refresh_cost=2)
        obs = SimpleNamespace(
            box_overlay_open=False, boxes=(), tomes=(), spheres=(),
            event_overlay='', bench_chars=(), deployed_chars=(),
            deploy_vacancy=0, state=st)
        sess = SimpleNamespace(cw4_counters={}, v3_intention=IntentionState())
        entry.emit(obs, SimpleNamespace(), sess, None)
        assert sess.cw4_counters.get('advisor_bloodline_armed') == 1
        assert sess.cw4_counters.get('neardeath_unlock') == 1


class TestLambdaShadowRevoked:

    def test_injected_form_arms_real_key(self, monkeypatch):
        """λ 影子维持声明撤销:注入形态触发 ⇒ 真键 lambda_armed 武装
        (行为介入),影子键保留对照。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.audit import (
            provisional,
        )
        monkeypatch.setattr(
            entry, '_lambda_quantile_armed',
            lambda state, hp, p_value: True)
        monkeypatch.setattr(
            provisional, 'get',
            lambda key: (SimpleNamespace(value=0.5, injected_form=True)
                         if key == 'P_LAMBDA_QUANTILE' else None))
        st = SimpleNamespace(node_type='战斗', enemy_difficulty=None,
                             plane=1)
        sig = entry._upgrader_evaluate(SimpleNamespace(), st, 0, 60)
        assert sig.lambda_armed is True, '注入形态触发即真键武装'
        assert sig.lambda_shadow_armed is True, '影子键保留对照'
        assert lambda_death.HP_BAND_NEAR_DEATH == 15   # 单一源常量在册值
