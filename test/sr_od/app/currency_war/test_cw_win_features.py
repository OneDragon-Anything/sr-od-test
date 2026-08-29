"""cw_win_features 锁测试(win_model M1,ADR 草稿 §1)。

合成输入(不依赖 replay 真实数据);数值断言全部手算对照注册表:
- cw_chars:椒丘 cost1(狼狩/持续伤害、减益)、藿藿 cost1(仙舟/治疗、能量)、
  丹恒·饮月 cost2(仙舟、列车同行/战技点)、青雀 cost1(仙舟/战技点)、
  停云 cost1(仙舟/能量);
- cw_factions tiers:仙舟(3,5,7,10)、战技点(2,4,6,8)、治疗(2,4,6)、
  能量(3,5,7,10)、列车同行(2,4,6)、狼狩(3,5,6,8)、持续伤害(2,4,6)、
  减益(2,4,6,8)。
"""
import pytest

from sr_od.application.currency_war.telemetry.cw_win_features import features_from_deployed


def _d(char_id: str, star: int = 1, equips: list | None = None) -> dict:
    """合成 deployed 项(与 decisions 帧 state.deployed 同构)。"""
    return {'slot': 1, 'char_id': char_id, 'faction': '', 'star': star,
            'position_pref': 'back', 'equips': equips or []}


class TestFeaturesBasics:
    def test_three_deployed_with_empty_slot_and_equips(self):
        """3 人 deployed(含空 char_id 槽/不同 star/装备)。

        手算:椒丘 star2 带 1 装备 + 藿藿 star1 + 丹恒·饮月 star1 + 空槽。
        - char_count=3;bow={椒丘:1, 藿藿:1, 丹恒·饮月:1}(空槽不计);
        - star_sum=2+1+1=4;star_hist={1:2, 2:1};
        - equip_count=1;total_cost=1+1+2=4;
        - 阵营计数(factions+flows 并计):
          椒丘→狼狩/持续伤害/减益;藿藿→仙舟/治疗/能量;
          丹恒·饮月→仙舟/列车同行/战技点
          ⇒ 狼狩1 持续伤害1 减益1 仙舟2 治疗1 能量1 列车同行1 战技点1;
        - 档位:仙舟2<3→0;狼狩1<3→0;治疗1<2→0;其余 1 人均未过
          第一层阈值 ⇒ tier_hist 空、max_tier=0。
        """
        feats = features_from_deployed([
            _d('椒丘', star=2, equips=['虚拟装备']),
            _d('藿藿'),
            _d('丹恒·饮月'),
            _d(''),  # 空占位槽
        ])
        assert feats['char_count'] == 3
        assert feats['bow'] == {'椒丘': 1, '藿藿': 1, '丹恒·饮月': 1}
        assert feats['star_sum'] == 4
        assert feats['star_hist'] == {'1': 2, '2': 1}
        assert feats['equip_count'] == 1
        assert feats['total_cost'] == 4
        assert feats['unknown_char_count'] == 0
        assert feats['faction_counts'] == {
            '狼狩': 1, '持续伤害': 1, '减益': 1, '仙舟': 2,
            '治疗': 1, '能量': 1, '列车同行': 1, '战技点': 1,
        }
        assert feats['tier_hist'] == {}
        assert feats['max_tier'] == 0

    def test_empty_and_unknown_inputs(self):
        """空列表 / 全空槽 / 未注册角色:零特征不崩,unknown 计数披露。"""
        empty = features_from_deployed([])
        assert empty['char_count'] == 0
        assert empty['total_cost'] == 0
        assert empty['faction_counts'] == {}

        placeholders = features_from_deployed([_d(''), _d(' ')])
        assert placeholders['char_count'] == 0

        unknown = features_from_deployed([_d('不存在角色')])
        assert unknown['unknown_char_count'] == 1
        assert unknown['total_cost'] == 0
        assert unknown['bow'] == {'不存在角色': 1}


class TestTierDerivation:
    def test_known_faction_combo_tiers(self):
        """已知阵营组合的激活层(手算对照注册表 tiers)。

        4 仙舟成员:青雀/停云/藿藿/丹恒·饮月 → 仙舟计数 4,
        tiers=(3,5,7,10) ⇒ 4≥3 且 4<5 → tier1。
        流派并计:战技点 = 青雀+丹恒·饮月 = 2,tiers=(2,4,6,8) ⇒ tier1;
        能量 = 停云+藿藿 = 2 < 3 → 0;治疗 = 藿藿 1 < 2 → 0;
        列车同行 = 丹恒·饮月 1 < 2 → 0。
        ⇒ tier_hist={1:2}(仙舟、战技点),max_tier=1;
        total_cost = 1+1+1+2 = 5。
        """
        feats = features_from_deployed([
            _d('青雀'), _d('停云'), _d('藿藿'), _d('丹恒·饮月'),
        ])
        assert feats['faction_counts']['仙舟'] == 4
        assert feats['faction_counts']['战技点'] == 2
        assert feats['faction_counts']['能量'] == 2
        assert feats['tier_hist'] == {'1': 2}
        assert feats['max_tier'] == 1
        assert feats['tier3_count'] == 0
        assert feats['total_cost'] == 5

    def test_tier2_boundary(self):
        """第二层边界:仙舟 5 人 → tiers(3,5,7,10) 中 3、5 均达标 → tier2。

        5 仙舟 = 4 人组合(青雀/停云/藿藿/丹恒·饮月)+ 符玄(仙舟,flows
        治疗、量子同频)。流派侧:战技点 2→tier1;能量 2→0;治疗
        藿藿+符玄=2,tiers(2,4,6)→tier1;量子同频 1 < 2 → 0。
        ⇒ tier_hist={1:2(战技点、治疗), 2:1(仙舟)},max_tier=2。
        """
        feats = features_from_deployed([
            _d('青雀'), _d('停云'), _d('藿藿'), _d('丹恒·饮月'), _d('符玄'),
        ])
        assert feats['faction_counts']['仙舟'] == 5
        assert feats['faction_counts']['治疗'] == 2
        assert feats['tier_hist'] == {'1': 2, '2': 1}
        assert feats['max_tier'] == 2
        assert feats['tier3_count'] == 0


class TestTier3Count:
    def test_single_tier3_bond(self):
        """1 个 t3 羁绊:7 仙舟 → tiers(3,5,7,10) 中 3、5、7 达标 → tier3。

        7 仙舟 = 青雀/停云/景元/符玄/彦卿/丹恒·饮月/藿藿(全部仙舟,
        对照 cw_chars 注册表)。流派侧:战技点=青雀+丹恒·饮月=2→tier1;
        能量=停云+藿藿=2→0;治疗=符玄+藿藿=2→tier1;群攻=景元 1→0;
        狼狩=彦卿 1→0;减益=彦卿 1→0;量子同频=符玄 1→0。
        ⇒ tier_hist={1:2, 3:1},max_tier=3,**tier3_count=1**。
        """
        feats = features_from_deployed([
            _d('青雀'), _d('停云'), _d('景元'), _d('符玄'),
            _d('彦卿'), _d('丹恒·饮月'), _d('藿藿'),
        ])
        assert feats['faction_counts']['仙舟'] == 7
        assert feats['tier_hist'] == {'1': 2, '3': 1}
        assert feats['max_tier'] == 3
        assert feats['tier3_count'] == 1

    def test_three_tier3_bonds(self):
        """3 个 t3 羁绊:6× 椒丘(同角色复用,狼狩/持续伤害/减益并计)。

        椒丘 traits=(狼狩,持续伤害,减益),6 人 ⇒ 三羁绊计数均 6:
        狼狩 tiers(3,5,6,8): 6≥3,5,6 → tier3;
        减益 tiers(2,4,6,8): 6≥2,4,6 → tier3;
        持续伤害 tiers(2,4,6): 6≥2,4,6 → tier3。
        ⇒ tier_hist={3:3},max_tier=3,**tier3_count=3**(批39 分界语义:
        t3=3 板与 t3=1 板 max_tier 同值,靠本特征区分)。
        """
        feats = features_from_deployed([_d('椒丘')] * 6)
        assert feats['faction_counts'] == {'狼狩': 6, '持续伤害': 6, '减益': 6}
        assert feats['tier_hist'] == {'3': 3}
        assert feats['max_tier'] == 3
        assert feats['tier3_count'] == 3


if __name__ == '__main__':
    pytest.main([__file__])
