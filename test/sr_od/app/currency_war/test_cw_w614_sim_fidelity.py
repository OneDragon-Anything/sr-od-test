"""W614 迁移批 0:sim 保真 P0 三补的单测(G1 装备记账/G2 上阵代理/G3 xp_per_refresh)。

蓝图出处:.debug/temp/currency_war/w613_strategy_refactor/BLUEPRINT.md §5
(批 0 前置件;临时文件,语义已固化进 cw_sim 注释与本测试)。

覆盖:
- 零漂移锚:不含新效果(默认 invest=False)的局行为投影 digest 逐位不变;
- G3:付费刷新产经验(淘金客 +2;数值源单一面 = cw_investments.STRATEGY_EFFECTS
  overlay,overlay 值变更 sim 跟随;免费刷不计),off 臂恒 0;
- G1:装备事件计数 + 逐轮未穿滞留/生锈暴露(min(10,n),词条语义
  cw_comps.RUST_AFFIX_NAME)+ 穿戴后滞留清零 + P1 出口滞留件数;
- G2:配方件躺 bench 轮数与上阵战力贡献代理的账本一致性。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace as _dc_replace

import pytest

from sr_od.application.currency_war.kernel.cw_effect_inventory import EffectSpec
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
    EconomyEffect,
)

from sr_od.application.currency_war.sim.cw_sim_invest import SimInvestProfile
SimInvestProfile
# 分包期 6 U1 双 runner 归家:P1 引擎(含 STRATEGY_EFFECTS overlay 消费面)
# = sim/engine_p1;overlay 值跟随测桩点钉引擎模块消费址
from sr_od.application.currency_war.sim import engine_p1 as cw_sim_mod

# 零漂移锚:seeds 0..5(pool='snapshot'),行为投影 = 每轮
# (plane, round_num, gold, hp, level, actions(类型, reason, result))
# + 局级 (dir_round, final_hp, level, refreshes)。改 G1-G3 前抓取
# (2026-09-01);20 seed 全量锚见 w614_sim_fidelity/baseline_digest.md
# (digest 93989ec7…,与改前逐位一致已验证)。
# 批 3 重锚(2026-09-03):预算收权换核(W615 查表核替换 DP 姿态供给)
# 是行为批,digest c13c365b… = 最终基线(批 2 末 93ca26cc… 起的行为位移
# 由 w633 A/B 判据管辖,本锚此后继续做「 unintended drift 」哨兵)。
# 中间值 60aa8ced… 为 R3 驱逐度量修正前的过渡锚(作废,记档防二次踩)。
# P4 小修簇重锚:sim 满级语义对齐(cw_sim.sim_decision_registry 把
# LEVEL_CAP 注入决策层,lv9 帧决策层不再发起必然被拒付的升级;行为
# 批,位移由 .debug/temp/currency_war/w652_p4_fixes/REPORT.md 记档)
# ——digest cdec4400…;本锚继续做 unintended drift 哨兵。
# 分配器落码批重锚(2026-09-06):死亡窗支出分配器(ADR-0474)接入
# decide_prep 默认路径是行为批,坐息/攥金帧出现分配器出清支出 → 行为
# 位移由 .debug/temp/currency_war/w715_allocator_impl/REPORT.md §四
# 记档(配对双窗 n=200 持平判定)——digest 687e5168…;本锚继续做
# unintended drift 哨兵。
# overlay A/B 行为批重锚(w729 残差收尾批):687e… 之后、分包期 6 之前的
# 行为批——overlay A 通道边际排序接线(e0e4f9d8/66e2b562,ADR-0475/0476)
# 与 overlay B 帽腿绑定面行为增量(ca320c81)——未随批重锚,欠账由本批
# 收口。归因实证:分包期 6 前 worktree(3cd79869,含全部 overlay 行为)
# 与期 6 后 HEAD 投影 digest 逐位一致(= 本锚,双跑确定性核验),期 6
# 四切零漂移成立;新锚 b80e101d…,继续做 unintended drift 哨兵。
# 确定性专项批重锚(w910_sim_determinism/REPORT.md):W748 F1 补部署
# 保留集收窄(16f1f2be,bench 同名对不再保留)是 sim 行为批但未随批
# 重锚,digest 由 b80e101d… 位移至 cabdf2893…。归因证据:worktree 钉
# db27854c(w729 锚点 commit)复现 b80e101d…、HEAD 复现 cabdf2893…,
# git bisect 逐 commit 定位首个位移点 = 16f1f2be(父 commit 仍 b80e);
# 同 digest 跨 6 进程(PYTHONHASHSEED 0/42/缺省、全局 random.seed、
# 生产 journal 隐藏各臂)逐位一致 = 确定性本身无破洞。
# W935 返修重锚(编排者裁决 2026-08-31;锁红≠改动错):危机臂预算门
# 从失明恢复为执行(买/升消费经 _accrue_release_frame_spend 计入
# v3_release_spent 钳制,ADR-0503 设计预算如实执行)——旧锚 cabdf2893…
# 钉的是「预算门失明」的 bug 形态,digest 位移至 b01e6b80… 即预算执行
# 生效的指纹;单变量差分归因(短路 accrual → digest 复位 cabdf)落
# .debug/temp/currency_war/w935_budget_enforce_ab/。新锚继续做
# unintended drift 哨兵;armed 态 A/B(w935_budget_enforce_ab/REPORT.md)
# 实证预算执行不劣化后此锚方为有效基线。
# 预算-回执契约除开关批重锚(ADR-0504,用户裁定无条件生效):**复合窗口
# 位移,单变量归因未做**——b01e6b80…→d0051d19… 的重锚窗口实际含至少三个
# 行为批(W951 危机刷新不变量无条件化 / R* 储备线降档 / 本契约无条件化),
# 逐批单独重放定贡献的 bisect 未执行,本锚注释不对单一机制作排他归因。
# 锚有效性前提 = 契约 A/B v2 渠道级判据(docs/develop/currency_war/prereg/
# w937_spend_receipt/PREREG.md:未兑现占比下降+同帧集配对零损害)与各批
# 自身 A/B;新锚继续做 unintended drift 哨兵,后续行为批重锚须按 w910
# 先例补单变量 bisect 或同款如实声明。
# W956 治本批复合重锚(同款如实声明:**复合窗口,单变量 bisect 未做**)
# ——d0051d19…→297d7eb4… 窗口含至少三个行为批:①death 帧供给解锁
# (w-only 拒供退役+刷新估计器死亡域保底,设计单一源=
# .debug/temp/currency_war/w956_death_allocator/DESIGN.md §1-§3);
# ②必死子带机会成本重定价(ADR-0510,hp≤L_c 带内 I 项退役);
# ③F5 部署供给(板缺帧 deploy 候选不截断,同 DESIGN §1.4)。
# 锚有效性前提 = 各批自身验证(REPORT §6/§6.4 与 ADR-0510);新锚继续做
# unintended drift 哨兵。
# M4 残余重锚(2026-09-07):W956 锚 297d7eb4… 之后两个已提交行为批未随批
# 重锚,git worktree 逐 commit bisect 定谳(父 1e819f84 复现 297d7eb4…):
# ①fdac8186(CW 代码面收口:轮岗建模修复,触面 cw_battle_calib/
# cw_deploy_logic/cw_economy 等)首位移至 278e8401…;
# ②4cbfb64a(输入基线定稿:机制修改器审计 16 项,触面 cw_comps/
# cw_effect_ledger/cw_investments)再位移至 1d3b6c29…;
# a642d28c..HEAD 对本锚三观测量(digest/胜负带/保有)零位移。
# 两批均为设计内校准/输入重锚(非 unintended drift),锚有效性前提 =
# 各批自身验证;新锚继续做 unintended drift 哨兵,后续行为批重锚须按
# w910 先例补单变量 bisect。
# F6 语料治理重锚(编排者批):校准数据面两处设计内变更使 digest
# 由 1d3b6c29… 位移至 098ea088…——①Δ池快照随 hp=0 伪影治理再生
# (指纹 6400d5d8→bfaf1c95,reward/supply 池采样变);②粗模型败局
# 直方剔除 hp=0 伪影伤害档(COARSE_CALIB_VERSION 2→3,战斗败态
# 采样变)。单批内两变量,归因即本批任务书范围(校准语料治理),
# 未触策略/决策代码。双跑确定性核验通过;新锚继续做 unintended
# drift 哨兵。
# p15 重拟合重锚(2026-09-02,dd-012):P1 _LOSS_FIT intercept/slope
# 改由对局档案真值语料重估(旧值系已灭且污染的 w324 语料回归值,
# COARSE_CALIB_VERSION 3→4,战斗败态均值匹配偏移变)→ digest
# 由 098ea088… 位移至 3e71aaaf…。单变量批(仅 _LOSS_FIT 三元组);
# 双跑确定性核验通过;新锚继续做 unintended drift 哨兵。
_ZERO_DRIFT_DIGEST_6 = (
    '3e71aaaf341c8c86f49fc9b79951d4351d0d8e2292bd86fc874c41e05b47a070')


def _behavior_projection(results) -> str:
    proj = []
    for seed, r in enumerate(results):
        rows = []
        for row in r.ledger:
            acts = tuple(
                (a.get('__type__', ''), str(a.get('reason', '')),
                 str(a.get('result', '')))
                for a in row.get('actions') or [])
            rows.append((row.get('plane'), row.get('round_num'),
                         row.get('gold'), row.get('hp'),
                         (row.get('state') or {}).get('level'), acts))
        proj.append((seed, r.dir_round, r.final_hp, r.level,
                     r.refreshes, tuple(rows)))
    blob = json.dumps(proj, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()


def _p1_rows(result):
    return [row for row in result.ledger if (row.get('plane') or 1) == 1]


class TestZeroDriftAnchor:
    """零漂移锚:不含新效果的局合成结果逐位不变(迁移批 0 纪律)。"""

    def test_default_path_behavior_digest_unchanged(self):
        results = [simulate_p1(s, pool='snapshot') for s in range(6)]
        assert _behavior_projection(results) == _ZERO_DRIFT_DIGEST_6

    def test_default_path_new_fields_neutral(self):
        """默认路径(无投资注入)下新记账出口应全为零/中性值。"""
        r = simulate_p1(11, pool='snapshot')
        assert r.refresh_xp_total == 0
        assert all((row.get('sim') or {}).get('refresh_xp', 0) == 0
                   for row in r.ledger)


class TestG3XpPerRefresh:
    """G3:xp_per_refresh 合成器接入(付费刷新产经验;免费刷不计)。"""

    def test_overlay_source_single_source(self):
        """数值源单一面 = STRATEGY_EFFECTS overlay(非 STRATEGY_ECONOMY 聚合)。"""
        spec = STRATEGY_EFFECTS['淘金客']
        assert isinstance(spec, EffectSpec)
        assert isinstance(spec.payload, EconomyEffect)
        # 淘金客官方文本:每次消耗金币刷新 +2 经验;overlay 供值,sim 跟随
        assert spec.payload.xp_per_refresh == 2
        assert spec.pending is False   # 定谳条目直供数值,不走保守支

    def test_overlay_value_change_follows(self, monkeypatch):
        """源断言:overlay 值变更 sim 跟随(改 overlay,注册表聚合面不动)。"""
        spec = STRATEGY_EFFECTS['淘金客']
        patched = dict(STRATEGY_EFFECTS)
        patched['淘金客'] = _dc_replace(
            spec, payload=_dc_replace(spec.payload, xp_per_refresh=7))
        monkeypatch.setattr(cw_sim_mod, 'STRATEGY_EFFECTS', patched)
        prof = SimInvestProfile(active_env='',
                                picks=((1, 1, '淘金客'),))
        r = simulate_p1(0, pool='snapshot', invest=prof)
        assert r.refreshes > 0
        assert r.refresh_xp_total == 7 * r.refreshes

    def test_paid_refresh_grants_xp_on_arm(self):
        prof = SimInvestProfile(active_env='',
                                picks=((1, 1, '淘金客'),))
        for seed in (0, 3):
            r = simulate_p1(seed, pool='snapshot', invest=prof)
            # 淘金客不带免费刷额度 → 全部刷新都是付费刷 → 严格 2×刷新数
            assert r.refreshes > 0
            assert r.refresh_xp_total == 2 * r.refreshes
            # 经验真到 xp_progress 消费面:有 xp 入账的局,level 轨迹合法
            assert r.level >= 3

    def test_off_arm_no_xp(self):
        prof = SimInvestProfile(active_env='',
                                picks=((1, 1, '魔丸'),))
        for seed in (0, 3):
            r = simulate_p1(seed, pool='snapshot', invest=prof)
            assert r.refreshes > 0
            assert r.refresh_xp_total == 0

    def test_ledger_round_disclosure(self):
        prof = SimInvestProfile(active_env='',
                                picks=((1, 1, '淘金客'),))
        r = simulate_p1(0, pool='snapshot', invest=prof)
        round_xp = sum((row.get('sim') or {}).get('refresh_xp', 0)
                       for row in r.ledger)
        assert round_xp == r.refresh_xp_total


_SEED_CACHE: dict[int, object] = {}


def _seeded_result(seed: int):
    """同 seed 的单局结果同次运行只算一次(昂贵计算共享)。"""
    if seed not in _SEED_CACHE:
        _SEED_CACHE[seed] = simulate_p1(seed, pool='snapshot')
    return _SEED_CACHE[seed]


class TestG1EquipAccounting:
    """G1:装备事件落账(发放/穿戴/合成计数 + 滞留/生锈出口)。"""

    def test_event_counters_consistent(self):
        r = _seeded_result(7)
        assert r.equip_grants >= 1      # 供给/奖励节点必有发放
        assert r.equip_wears >= 0
        assert r.equip_syntheses >= 0
        # 发放 ≥ 穿戴 + 合成耗件之外的余量方向:持有量(末态)有界
        owned = _p1_rows(r)[-1]['state']['owned_equips']
        assert len(owned) <= r.equip_grants + r.equip_syntheses

    def test_rust_units_formula_and_exit(self):
        r = _seeded_result(7)
        rows = _p1_rows(r)
        for row in rows:
            sim = row['sim']
            assert sim['rust_units'] == min(10, sim['unworn_equips'])
            assert sim['unworn_equips'] == \
                len(row['state']['owned_equips'])
        # P1 出口滞留件数 = 末轮未穿件数;峰值 = 逐轮生锈暴露最大值
        assert r.p1_unworn_exit == rows[-1]['sim']['unworn_equips']
        assert r.p1_rust_units_peak == max(
            row['sim']['rust_units'] for row in rows)

    def test_wear_clears_stagnation(self):
        """穿戴后滞留清零:某轮穿上的件,同轮 owned 池里不再出现。"""
        r = _seeded_result(7)
        hit = False
        for row in _p1_rows(r):
            equipped = [e['equip'] for e in
                        (row['state'].get('equipped') or [])]
            if not equipped:
                continue
            owned = row['state']['owned_equips']
            for name in equipped:
                if name not in owned:
                    hit = True
        assert hit, '语料内未找到可验证的穿戴轮(采样缺陷,需换 seed)'

    def test_worn_total_field(self):
        r = _seeded_result(7)
        for row in _p1_rows(r):
            worn = sum(len(d.get('equips') or [])
                       for d in row['state'].get('deployed') or [])
            worn += sum(len(b.get('equips') or [])
                        for b in row['state'].get('bench') or [])
            assert row['sim']['worn_equips_total'] == worn


class TestG2DeployProxy:
    """G2:上阵代理记账(配方件躺 bench 轮数 + 战力贡献代理)。"""

    def test_bench_recipe_rounds_aggregate(self):
        r = _seeded_result(7)
        rows = _p1_rows(r)
        assert r.p1_bench_recipe_piece_rounds == sum(
            (row.get('sim') or {}).get('bench_recipe_pieces', 0)
            for row in rows)

    def test_deployed_power_aggregate(self):
        r = _seeded_result(7)
        rows = _p1_rows(r)
        values = [(row.get('sim') or {}).get('deployed_power', 0)
                  for row in rows]
        assert all(v >= 0 for v in values)
        assert r.p1_deployed_power_avg == pytest.approx(
            sum(values) / len(values), abs=0.011)

    def test_deployed_power_semantics(self):
        """代理语义锁:deployed_power = Σ(star + core∈target 计 1)。

        target 集不可从账本逐轮复原(部署块读 session 现读),此处锁
        下界:场上有人时 power ≥ 上阵人数(每人 star≥1 贡献)。
        """
        r = _seeded_result(7)
        for row in _p1_rows(r):
            n = len(row['state'].get('deployed') or [])
            assert row['sim']['deployed_power'] >= n


from sr_od.application.currency_war.sim.engine_p1 import simulate_p1


class TestSimDeterminismAndIsolation:
    """sim 判定路径确定性/生产态隔离锁(w910_sim_determinism/REPORT.md)。

    诊断嫌疑定谳:①生产态 journal(obs_conflicts.jsonl)无读入 sim 判定
    路径——sim 读生产 replay 只在 pool='auto' 显式臂,锚路径用
    pool='snapshot'(主仓提交数据);②session.rng 已显式种子化(kernel
    default 固定种子,sim 引擎从局 seed 派生,生产 run loop 按
    strategy_seed 覆盖)。本组锁固化这两条前提防回洞。
    """

    def test_default_path_reads_no_production_replay(self):
        """sim 默认路径(pool='snapshot')不触生产 replay 目录任何文件。"""
        import sys
        from pathlib import Path

        from one_dragon.utils.file_utils import get_project_root

        replay_dir = (get_project_root() / '.debug' / 'temp'
                      / 'currency_war' / 'replay')
        hits: list[str] = []

        def _hook(event, args):
            if event not in ('open', 'os.open'):
                return
            try:
                path = args[0]
                if isinstance(path, int):
                    return
                resolved = str(Path(path))
                if resolved.startswith(str(replay_dir)):
                    mode = args[1] if len(args) > 1 else ''
                    hits.append(f'{resolved}({mode})')
            except Exception:
                pass    # 审计钩子内禁抛,漏记可容忍

        sys.addaudithook(_hook)
        simulate_p1(0, pool='snapshot')
        assert not hits, f'sim 默认路径读入生产 replay 文件: {hits[:5]}'

    def test_same_seed_twice_identical(self):
        """同 seed 同进程两局投影逐位一致(确定性哨兵,进程内口径)。"""
        proj_a = _behavior_projection([simulate_p1(3, pool='snapshot')])
        proj_b = _behavior_projection([simulate_p1(3, pool='snapshot')])
        assert proj_a == proj_b

    def test_session_rng_default_deterministic(self):
        """裸 StrategySession() 的 rng 默认流确定(default 固定种子,
        禁 OS 熵回洞;消费方显式注入真实种子 = 生产 run loop / sim 引擎)。"""
        import random

        from sr_od.application.currency_war.decision.cw_strategy import (
            StrategySession,
        )

        s1, s2 = StrategySession(), StrategySession()
        assert isinstance(s1.rng, random.Random)
        seq1 = [s1.rng.random() for _ in range(8)]
        seq2 = [s2.rng.random() for _ in range(8)]
        assert seq1 == seq2
