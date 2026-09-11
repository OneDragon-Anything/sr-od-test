# deploy 围栏视图装配单一源收口批(T-82)语义锁。
# 依据单一源 = .debug/progress/2026-09-11-cw-clear-run/定谳记录-deploy围栏.md
# (裁案 B:围栏目标视图归属成型面装配语义;B2 修正条件 = 双轨期框架方向
# 键面完备表达;行为差申报 = 第七节 ①-⑤)。
# 锁的存在性纪律:每条锁 docstring 引出处;行为分布/发射频率归批判读,
# 本文件只锁视图装配语义与围栏身份判定(纯函数面,单帧可锁)。
from types import SimpleNamespace as _NS

from sr_od.application.currency_war.data.cw_chars import get_char
from sr_od.application.currency_war.kernel.cw_comps import Comp
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    assemble_swap_plan_inputs,
    deploy_target_sets,
    select_deployments_reasoned,
    target_view_char_is,
)
from sr_od.application.currency_war.kernel.cw_recipe import recipe_comp
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState
from sr_od.application.currency_war.kernel.cw_transition import (
    FRAMEWORK_FACTIONS,
    FRAMEWORKS,
    TRANSITION_PACK,
)


def _bc(name: str, slot: int = 1, star: int = 1) -> BenchChar:
    ch = get_char(name)
    return BenchChar(slot=slot, char_id=name, star=star,
                     faction=(ch.factions[0] if ch and ch.factions else '?'))


# ==================== B2 修正条件:配方键面完备性 ====================


def test_b2_recipe_faction_keys_complete() -> None:
    """B2 完备性锁(定谳记录-deploy围栏.md 攻击线 B2/第六节 3 条):三框架
    配方伪 comp 的 all_factions 必须**超集** FRAMEWORK_FACTIONS[fw]——
    仙舟配方原 factions=['仙舟'] 缺持续伤害键时,以配方为围栏视图的路径
    (装配单一源)把框架 drop 件挤出 tgt 桶:卡芙卡(星核猎手+持续伤害
    flow)/椒丘(狼狩+持续伤害 flow)注册表均无仙舟阵营,其围栏身份只系于
    持续伤害键(r70「框架牌不上场被卖」回归向量的真实形状)。键面补全后
    框架并集语义由配方单一承载,deploy_target_sets 的显式 ∪ 退役。"""
    for fw in FRAMEWORKS:
        rc = recipe_comp(fw)
        assert rc is not None, f'{fw} 配方必须注册'
        missing = set(FRAMEWORK_FACTIONS[fw]) - set(rc.all_factions)
        assert not missing, f'{fw} 配方键面不完备,缺 {missing}' \
            '(框架 drop 件围栏身份断锚 = B2 回归向量)'


# ==================== B2 前置波:m1p 回归锁(卡芙卡/椒丘围栏身份) ====================


def _dual_track_session(final_comp) -> _NS:
    """双轨期会话夹具:框架已选仙舟 ∧ 未定型(plane=1 ∧ ist 无锁无 pair)
    → decision_target 返回配方伪 comp(与装配单一源同链)。
    字段挂 ``session.strategy_state``(strategy_state_of 统一读口)。"""
    sess = _NS(last_state=None)
    sess.strategy_state = _NS(target_comp=final_comp,
                              transition_framework='仙舟')
    sess.strategy_state.v3_intention = _NS(locked_comp='', p1_pair=(),
                                           phase='', transition_pair=())
    return sess


def test_b2_m1p_assembly_keeps_drop_piece_fence_identity() -> None:
    """m1p 回归锁(任务书 B2 前置波验证锚;定谳记录-deploy围栏.md 攻击线
    B2「不补则案 B 在 m1p 轮复现 r70 回归向量」):双轨仙舟框架期经装配
    单一源(围栏视图 = 配方伪 comp all_factions)——
    ①框架 drop 件卡芙卡/椒丘围栏 tgt 身份**零漂移**(target_view_char_is
    判定单一源);②纯 DOT 散件(桑博/海瑟音/黑天鹅,持续伤害 flow 无仙舟
    阵营)同键放行,身份与现状零漂移;③终局 comp 特有键不混入双轨视图
    (方向混装移除,定谳行为差①);④fw_carry 面**零漂移**:drop/散件不入
    carry 名单(drop=P1 末弃,买了就上但不追)。"""
    # 终局 comp 键面与仙舟/DOT 全无交集(万敌线形态)——若配方键面缺
    # 持续伤害,卡芙卡/椒丘在该帧的围栏身份断锚(回归向量)。
    final = _NS(all_factions={'夜之半神', '燃血'}, factions=['夜之半神'],
                core_chars=['万敌'], flex_factions=['燃血'],
                form_tiers={'夜之半神': 2}, char_positions={})
    sess = _dual_track_session(final)
    st = GameState(plane=1, round_num=2, board={'仙舟': 2},
                   deployed=[_bc('藿藿', 1), _bc('爻光', 2)], bench=[])
    ctx = assemble_swap_plan_inputs(sess, state=st, deployed=st.deployed,
                                    bench=[], cap=6)
    assert ctx is not None
    # ①配方视图胜出:双轨 tgt = {仙舟, 持续伤害}(非终局键并集)
    assert ctx.target_factions == frozenset({'仙舟', '持续伤害'}), \
        f'双轨围栏视图 = 配方 all_factions,实得 {sorted(ctx.target_factions)}'
    for name in ('卡芙卡', '椒丘', '桑博', '海瑟音', '黑天鹅'):
        assert target_view_char_is(ctx, name), \
            f'{name} 围栏 tgt 身份断锚(B2 回归向量:持续伤害键缺席)'
    # ③终局特有键(夜之半神/燃血)不因终局 comp 混入双轨围栏视图
    assert not target_view_char_is(ctx, '飞霄'), \
        '终局特有键件在双轨期不应获围栏 tgt(方向混装回归)'
    # ④fw_carry 零漂移:drop(卡芙卡/椒丘)与散件(艾丝妲)不入
    assert '卡芙卡' not in ctx.fw_carry and '椒丘' not in ctx.fw_carry
    assert '艾丝妲' not in ctx.fw_carry
    assert {'藿藿', '丹恒·饮月', '爻光', '千冶·刃'} <= set(ctx.fw_carry), \
        f'carry/通用件名单漂移,实得 {sorted(ctx.fw_carry)}'


def test_b2_fence_deploy_drop_piece_not_scatter_held() -> None:
    """围栏行为级回归锁(m1p 身份锁的 select 层差分绑定):双轨仙舟框架期,
    vacancy=2(非 fill_mode)且 cap 富余——卡芙卡(配方视图 tgt)进 tgt 桶
    上场;非目标对照件(黑塔=银河学者,键面全无交集)走 rest_capacity 留
    bench 形成差分——证明卡芙卡上场走的是 tgt 身份而非填空。"""
    final = _NS(all_factions={'夜之半神'}, factions=['夜之半神'],
                core_chars=['万敌'], flex_factions=[],
                form_tiers={'夜之半神': 2}, char_positions={})
    sess = _dual_track_session(final)
    st = GameState(plane=1, round_num=2, board={'仙舟': 2},
                   deployed=[_bc('藿藿', 1), _bc('爻光', 2)], bench=[])
    ctx = assemble_swap_plan_inputs(sess, state=st, deployed=st.deployed,
                                    bench=[], cap=4)
    assert ctx is not None
    bench = [_bc('卡芙卡', 1), _bc('黑塔', 2)]   # 黑塔=银河学者,非目标件
    # 2 前排+2 后排小面板:占用 2 → vacancy=2(fill_mode 关);must_up=1
    # < vacancy=2 → roomy 开,黑塔按 rest_capacity 留置(差分成立前提)。
    up, held, reasons = select_deployments_reasoned(
        bench, deployed_cids={'藿藿', '爻光'}, deployed_fac={'仙舟': 2},
        board={'仙舟': 2}, cap=4, front_total=2, back_total=2,
        target_factions=ctx.target_factions, target_cores=ctx.target_cores,
        fw_carry=ctx.fw_carry, locked_factions=ctx.locked_factions)
    up_names = {bench[i].char_id for i in up}
    held_names = {bench[i].char_id for i in held}
    assert '卡芙卡' in up_names, \
        f'卡芙卡应进 tgt 桶上场(B2 回归向量),up={up_names} reasons={reasons}'
    assert '黑塔' in held_names, \
        f'非目标对照件应留 bench(差分前提),held={held_names} reasons={reasons}'


# ==================== 案 B 收口:deploy_target_sets 语义锁 ====================


def test_deploy_target_sets_committed_phase_flex_keys_enter() -> None:
    """案 B 行为差③锁(定谳记录-deploy围栏.md 第七节③/攻击线 B3③):
    定型/无框架帧围栏视图 = comp.all_factions(factions ∪ flex)——flex 键
    入场,与装配单一源的 target 视图同链同值(旧口径 = factions 裸集,
    C-A2 病灶机制「义务件 flex 键 ∈ all_factions、∉ comp.factions」的
    围栏侧根除位)。"""
    comp = Comp(name='测试线', factions=['仙舟'], core_chars=[],
                form_tiers={}, strength='A', form_difficulty='easy',
                flex_factions=['减益'])
    tgt, _fw = deploy_target_sets(comp, '')
    assert tgt == {'仙舟', '减益'}, f'flex 键应入场,实得 {sorted(tgt)}'


def test_deploy_target_sets_dual_track_no_final_faction_mixing() -> None:
    """案 B 行为差①锁(定谳记录-deploy围栏.md 第七节①/攻击线 A2「方向
    混装」):双轨期围栏视图 = 配方伪 comp all_factions,**终局 comp 特有键
    不混入**(旧口径 = comp.factions ∪ FRAMEWORK_FACTIONS,把终局方向并进
    转型期围栏桶)。视图与配方键面逐键相等。"""
    final = Comp(name='终局线', factions=['夜之半神', '星核猎手'],
                 core_chars=['万敌'], form_tiers={'夜之半神': 2},
                 strength='A', form_difficulty='easy',
                 flex_factions=['燃血'])
    tgt, fw_carry = deploy_target_sets(final, '仙舟')
    assert tgt == {'仙舟', '持续伤害'}, \
        f'双轨视图 = 配方键面,终局特有键禁混入,实得 {sorted(tgt)}'
    assert '万敌' not in fw_carry and '终局线' not in fw_carry


def test_deploy_target_sets_fw_carry_zero_drift() -> None:
    """fw_carry 面零漂移锁(定谳记录-deploy围栏.md 第六节 3 条验证锚):
    视图重锚不触 fw_carry——双轨分支 = 框架(或通用)非 drop 件(drop 档
    卡芙卡/椒丘与散件 drop 艾丝妲恒不入);定型/无框架分支 = 空集(与旧
    行为逐位一致,fw_carry 是框架派生量,无框架即无 carry)。"""
    expect = {n for n, (f, t) in TRANSITION_PACK.items()
              if (f == '仙舟' or f == '通用') and t != 'drop'}
    assert expect == {'藿藿', '丹恒·饮月', '爻光', '千冶·刃'}, \
        '锁前提:仙舟 carry/partial + 通用 carry 名单(注册表直核)'
    _tgt1, fw1 = deploy_target_sets(None, '仙舟')
    comp = Comp(name='测试线', factions=['仙舟'], core_chars=[],
                form_tiers={}, strength='A', form_difficulty='easy')
    _tgt2, fw2 = deploy_target_sets(comp, '')
    assert fw1 == expect, f'双轨 fw_carry 漂移,实得 {sorted(fw1)}'
    assert fw2 == set(), '定型帧 fw_carry 应恒空(旧行为)'
    assert '卡芙卡' not in fw1 and '椒丘' not in fw1 and '艾丝妲' not in fw1


def test_deploy_target_sets_duck_type_fallback_zero_drift() -> None:
    """防御退型零漂移锁:①comp 无 all_factions 属性(测试鸭子型)→ 退
    factions 旧语义;②框架无配方注册(理论态)→ 退旧并集语义——两条
    退型路径逐位同旧,禁因重锚引入新异常面。"""
    duck = _NS(factions=['仙舟'])   # 无 all_factions 属性
    tgt, _fw = deploy_target_sets(duck, '')
    assert tgt == {'仙舟'}
    # 未注册框架:退 comp.factions ∪ FRAMEWORK_FACTIONS(旧并集;未知键
    # 查表得空集 → 等于 factions 裸集);fw_carry 旧语义 = 通用 carry 恒在
    # (框架子句不匹配、通用子句无框架前提)——逐位同旧,零漂移。
    tgt2, fw2 = deploy_target_sets(duck, '不存在的框架')
    assert tgt2 == {'仙舟'} and fw2 == {'千冶·刃'}


# ==================== 滞留扫描原义务:rest→tgt 改判帧归因键 ====================


def test_obligation_piece_rest_to_tgt_reflip_ab() -> None:
    """滞留扫描原义务的静态语义锁(T-27 criteria 2 语义随定谳改写,定谳
    记录-deploy围栏.md 卷尾 1:扫描口径 = tgt 桶判 rest 改判帧 = 义务件
    滞留归因键):C-A2 病灶机制(ADR-0640 :9)的围栏侧根除验证——义务件
    带 flex 键(椒丘=减益 flow)在 comp.factions 旧视图判 rest、在
    all_factions 新视图判 tgt:改判键 = flex 键入场(案 B 行为差③)。
    边界申报:动态分母扫描辖域 = t190_c 检查器族 C-A1..C-A4(已知边界,
    定谳记录 1.4 节),超界检查器不在本批辖域(禁触 sim/),本锁钉语义面。
    """
    comp = Comp(name='测试线', factions=['仙舟'], core_chars=[],
                form_tiers={}, strength='A', form_difficulty='easy',
                flex_factions=['减益'])
    old_view = set(comp.factions)             # 旧口径(收口前围栏视图)
    new_view, _fw = deploy_target_sets(comp, '')
    jq = get_char('椒丘')
    bonds = set(jq.factions) | set(jq.flows)   # {狼狩, 持续伤害, 减益}
    assert not (bonds & old_view), '锁前提:旧视图判椒丘 rest(病灶机制)'
    assert bonds & new_view, '新视图必须判 tgt(改判发生,义务件不再滞留)'
    assert (bonds & new_view) - (bonds & old_view) == {'减益'}, \
        '改判归因键 = flex 键入场(滞留归因键单一面)'
