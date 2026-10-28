"""grant_char_pool 牌库时点池语义测试(镜像 src = kernel/cw_pool.py 的
该被测函数;随机角色授予采样空间 = 规格域 ∩ 当时牌库)。

测试面依据 = gain-chain.md §3 随机支段(牌库时点池语义)+ economy.md §8
「专家顾问未解锁不入随机授予候选;授予候选 = 当时牌库」(用户裁定
2026-10-28)+ 语义描述「概念股族展开卡登记约定」:
- **阵营轴过滤**:空解锁容器 → 仙舟域候选 = 注册表全域 − 专家
  (青雀/停云),现算比对非手抄;
- **解锁态回归**:专家解锁后回到候选(专家入池时机与商店同源,
  economy.md §1);
- **费用轴过滤**:4 费档 = chars_by_cost(4) − 开拓者·记忆(双形态
  合并随基底)− 银狼(专家),现算比对;
- **非专家域零扰**:银河学者域无专家成员,过滤前后同值;
- **分层职责**:静态基底 random_char_pool 仍含专家(过滤只发生在
  grant_char_pool 层,两层语义不混写)。
"""
from __future__ import annotations

from sr_od.application.currency_war.data.cw_chars import (
    CHARACTER_ROSTER,
    chars_by_cost,
    chars_by_faction,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    RandomCharSpec,
    random_char_pool,
)
from sr_od.application.currency_war.kernel.cw_pool import grant_char_pool


def _fresh_gs() -> GameState:
    """空解锁容器(开局种子底座,专家候选面 = 过滤态)。"""
    return GameState(schema_version=GAME_STATE_SCHEMA_VERSION)


def _unlocked_gs(names: tuple[str, ...]) -> GameState:
    """解锁态容器(unlocked_experts 单口直写)。"""
    gs = _fresh_gs()
    from sr_od.application.currency_war.sim.cw_sim_base import logic_sig
    gs.write_logic(gs.unlocked_experts, names, produced_by='test-seed',
                   evidence='test:unlock', sig=logic_sig('test:grant-pool'))
    return gs


def test_xianzhou_faction_pool_excludes_locked_experts() -> None:
    """阵营轴过滤(牌库时点池约定,economy.md §8):空解锁容器 → 仙舟域
    候选 = chars_by_faction('仙舟') 名集 − {'青雀','停云'} 现算比对
    (注册表派生非快照不手抄;池规模只记注释零断言值——现值 7 名,随
    版本正常变动);显式断言两名专家 ∉ 候选(选投资环境在开局、彼时专家
    结构性未激活)。"""
    pool = grant_char_pool(_fresh_gs(),
                           RandomCharSpec(faction='仙舟', star=1))
    expected = {c.name for c in chars_by_faction('仙舟')} - {'青雀', '停云'}
    assert set(pool) == expected, \
        '仙舟域候选 = 全域剔除未解锁专家(牌库时点过滤)'
    assert '青雀' not in pool and '停云' not in pool, \
        '专家未解锁不入候选(用户裁定 2026-10-28)'
    assert set(pool) <= CHARACTER_ROSTER


def test_unlocked_expert_returns_to_candidate_pool() -> None:
    """解锁态回归(economy.md §1 解锁入池:专家解锁后与商店同源入候选):
    解锁 {'青雀'} → 仙舟域候选 8 名(青雀回归),其余候选不变。"""
    pool = grant_char_pool(_unlocked_gs(('青雀',)),
                           RandomCharSpec(faction='仙舟', star=1))
    expected = {c.name for c in chars_by_faction('仙舟')} - {'停云'}
    assert set(pool) == expected, '已解锁专家回到候选(牌库时点口径)'
    assert '停云' not in pool, '未解锁专家仍不在候选'


def test_cost_axis_pool_excludes_locked_expert_and_merged_form() -> None:
    """费用轴过滤(牌库时点池约定):空解锁容器 → 4 费候选 =
    chars_by_cost(4) − {'开拓者·记忆'(双形态合并随基底), '银狼'(专家)}
    现算比对(池规模只记注释零断言值——现值 12 名,随版本正常变动)。"""
    pool = grant_char_pool(_fresh_gs(), RandomCharSpec(cost=4, star=1))
    expected = {c.name for c in chars_by_cost(4)} \
        - {'开拓者·记忆', '银狼'}
    assert set(pool) == expected, \
        '4 费候选 = 全档 − 双形态键侧 − 未解锁专家(两层叠加)'


def test_expert_free_domain_unchanged() -> None:
    """非专家域零扰:银河学者域无专家成员,过滤前后同值(注册表现算
    双射;对照面 = 已落地登记域中唯一无专家域,防过滤层误伤)。"""
    spec = RandomCharSpec(faction='银河学者', star=1)
    expected = {c.name for c in chars_by_faction('银河学者')}
    assert set(grant_char_pool(_fresh_gs(), spec)) == expected, \
        '无专家域过滤零扰(域 = 原始注册表全域)'
    assert set(random_char_pool(spec)) == expected, \
        '静态基底同值(两层面在本域重合)'


def test_static_base_pool_still_contains_experts() -> None:
    """分层职责(防两层语义混写):静态基底 random_char_pool 仍含专家
    (青雀 ∈ 仙舟域静态池)——牌库时点过滤只发生在 grant_char_pool 层,
    构建期校验与静态消费面语义不变。"""
    spec = RandomCharSpec(faction='仙舟', star=1)
    assert '青雀' in random_char_pool(spec) \
        and '停云' in random_char_pool(spec), \
        '静态基底含全部注册成员(过滤在下层)'
    filtered = grant_char_pool(_fresh_gs(), spec)
    assert len(filtered) < len(random_char_pool(spec)), \
        '过滤层严格收窄(基底 ⊃ 牌库时点池)'


def test_langshou_faction_pool_expert_filter_instance() -> None:
    """狼狩域专家过滤实例锁(牌库时点池约定,概念股族展开卡登记约定,
    沿仙舟域锁同款三分层断言形态):①空解锁容器 → 狼狩域候选 =
    chars_by_faction('狼狩') 名集 − {'貊泽'} 现算比对(注册表派生非
    快照不手抄;池规模只记注释零断言值——现值 6 名,随版本正常变动;
    选投资环境在开局、彼时专家结构性未激活);②解锁 {'貊泽'} → 7 名
    回归(专家入池时机与商店同源,economy.md §1);③静态基底
    random_char_pool 仍含貊泽(专家剔除只发生在 grant_char_pool 层,
    两层语义不混写)。"""
    spec = RandomCharSpec(faction='狼狩', star=1)
    pool = grant_char_pool(_fresh_gs(), spec)
    expected = {c.name for c in chars_by_faction('狼狩')} - {'貊泽'}
    assert set(pool) == expected, \
        '狼狩域候选 = 全域剔除未解锁专家(牌库时点过滤)'
    assert '貊泽' not in pool, '专家未解锁不入候选(用户裁定 2026-10-28)'
    assert set(pool) <= CHARACTER_ROSTER
    unlocked = grant_char_pool(_unlocked_gs(('貊泽',)), spec)
    assert set(unlocked) == {c.name for c in chars_by_faction('狼狩')}, \
        '已解锁专家回到候选(牌库时点口径)'
    assert '貊泽' in random_char_pool(spec), \
        '静态基底含全部注册成员(过滤归 grant_char_pool 层,分层职责)'
