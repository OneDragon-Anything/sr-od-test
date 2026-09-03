"""选择伙伴 overlay 分发回归锁(dd-029 第三起实机卡死,2026-09-04 01:02 局)。

事故:运行时画面加载源 = ``screen_loader.reload()`` 默认读 ``_od_merged.yml``;
「列车同行」改名批(git 75880dd1)只改了分文件 yml + 代码引用 + overlay 注册表,
merged 未随之再生 → cw_loop 0a 分支 ``round_by_find_area('货币战争-列车同行',
'标识-选择伙伴')`` 拿到 AREA_NO_CONFIG → 静默跳过 → 伙伴遮罩下备战双锚透出命中
→ 反复 RunDeploy 拖拽落遮罩上 → 部署死局 ~8min。识别层(analyze_screen 走同一
merged,精准命中旧名「货币战争-选择伙伴」)与分发层(查新名)各说各话。

三条锁:
1. merged 新鲜度 = 分文件全集(本事故的直接回归锁;改名/建 area 后必须再生 merged);
2. overlay 注册表 + 主循环序锁矩阵的全部锚在 merged(运行时真源)可解析;
3. 事故帧 fixture:伙伴锚命中(= 路由到 CwScreenPartner 处理链,不再漏到备战分支)。

处理链归属说明:选择伙伴 overlay 的专属 handler 是 ``CwScreenPartner``
(选择 → 确认 → step2 强化目标,生命周期 owner;注册表 handler_id 同源)。
「专家邀请函 CwScreenExpertInvite」是另一画面(货币战争-备战-专家邀请函)的
handler,与本 overlay 无关。
"""
from __future__ import annotations

from pathlib import Path

import yaml

from sr_od.application.currency_war.kernel import cw_overlay_registry as reg

REPO = Path(__file__).resolve().parents[5]
SCREEN_INFO_DIR = REPO / 'assets' / 'game_data' / 'screen_info'
MERGED_PATH = SCREEN_INFO_DIR / '_od_merged.yml'


def _load_separated() -> dict[str, dict]:
    """分文件 screen_id → 原始 dict(测试仓内独立实现,与
    .debug/temp/currency_war/hotfix_partner_overlay/audit_merged_drift.py 同判据)。"""
    out: dict[str, dict] = {}
    for fp in sorted(SCREEN_INFO_DIR.glob('*.yml')):
        if fp.name == '_od_merged.yml':
            continue
        data = yaml.safe_load(fp.read_text(encoding='utf-8'))
        if isinstance(data, dict) and data.get('screen_id'):
            out[data['screen_id']] = data
    return out


def _load_merged() -> dict[str, dict]:
    """merged screen_id → 原始 dict(= 运行时 screen_loader 唯一加载源)。"""
    data = yaml.safe_load(MERGED_PATH.read_text(encoding='utf-8')) or []
    out: dict[str, dict] = {}
    for item in data:
        if isinstance(item, dict) and item.get('screen_id'):
            out[item['screen_id']] = item
    return out


def _merged_area_keys() -> set[str]:
    """merged 的 ``画面名.area名`` 全集(= round_by_find_area 可解析键空间)。"""
    keys: set[str] = set()
    for screen in _load_merged().values():
        for area in (screen.get('area_list') or []):
            keys.add(f'{screen["screen_name"]}.{area["area_name"]}')
    return keys


# ── 锁 1:merged 新鲜度(本事故直接回归锁)─────────────────────────────────

def test_merged_yml_fresh_with_separated_files() -> None:
    """运行时加载源 merged 必须与分文件全集一致(screen_id 集 + 画面名 +
    area 名集)。分文件被改名/增删 area 后未再生 merged = 本锁红,提示跑
    ``audit_merged_drift.py --regen``(dd-029:改名批漏再生 → 分发层查新名
    AREA_NO_CONFIG 静默跳过 → 伙伴遮罩下部署死局)。"""
    sep = _load_separated()
    merged = _load_merged()
    assert set(sep) == set(merged), (
        f'merged 与分文件 screen_id 集不一致: '
        f'仅分文件有={sorted(set(sep) - set(merged))} '
        f'仅 merged 有={sorted(set(merged) - set(sep))}(后者为过期孤儿)')
    for sid in sorted(set(sep) & set(merged)):
        assert sep[sid].get('screen_name') == merged[sid].get('screen_name'), (
            f'screen_id={sid} 画面名漂移: merged={merged[sid].get("screen_name")!r} '
            f'分文件={sep[sid].get("screen_name")!r}——运行时只见 merged 名,'
            f'按新名查询的区域判定全部 AREA_NO_CONFIG(dd-029 事故形态);'
            f'请再生 merged(audit_merged_drift.py --regen)后提交')
        sa = {a['area_name'] for a in (sep[sid].get('area_list') or [])}
        ma = {a['area_name'] for a in (merged[sid].get('area_list') or [])}
        assert sa == ma, (
            f'{sep[sid].get("screen_name")} area 集漂移: '
            f'仅分文件有={sorted(sa - ma)} 仅 merged 有={sorted(ma - sa)}')


# ── 锁 2:分发面锚全部在运行时真源可解析 ─────────────────────────────────

def test_overlay_registry_resolvable_in_runtime_merged() -> None:
    """激活 overlay 条目的 screen/识别锚/第二锚/关闭钮都在 merged 中
    (注册表一致性测试读分文件,w559 形态;本锁补「运行时真源」一侧——
    两侧同绿才保证分发判定真实可执行)。"""
    keys = _merged_area_keys()
    for spec in reg.OVERLAY_REGISTRY:
        if not spec.active:
            continue
        assert f'{spec.screen_name}.{spec.anchor_area}' in keys, (
            f'{spec.screen_name}.{spec.anchor_area} 不在运行时 merged——'
            f'该 overlay 的分发分支每帧 AREA_NO_CONFIG 静默跳过(dd-029 形态)')
        if spec.anchor_area_alt:
            assert f'{spec.screen_name}.{spec.anchor_area_alt}' in keys
        if spec.close_area:
            assert f'{spec.screen_name}.{spec.close_area}' in keys


def test_dispatch_order_matrix_anchors_resolvable_in_runtime_merged() -> None:
    """主循环浮层序锁矩阵(仅 area 行)的全部锚都在 merged 中——矩阵锁住
    「序位」,本锁住「可解析」:任一锚名漂移(改名/merged 过期)即红。"""
    from test.sr_od.app.currency_war.test_cw_dispatch_order_matrix import (
        ORDER_MATRIX,
    )
    keys = _merged_area_keys()
    for name, screen, anchor, method in ORDER_MATRIX:
        if method != 'area':
            continue
        assert f'{screen}.{anchor}' in keys, (
            f'序锁矩阵行「{name}」的锚 {screen}.{anchor} 不在运行时 merged'
            f'(分发分支静默失效形态,dd-029)')


def test_loop_dispatch_anchor_table_resolvable_in_runtime_merged() -> None:
    """主循环 iter1 分发锚预检表(dd-029)的全部锚都在 merged 中——预检在
    生产侧只 log.error 不 fail(不中止对局),本锁补「测试侧 fail 硬门」:
    预检表里有漂移锚 = 本锁红,与生产日志双通道。"""
    from sr_od.application.currency_war.operations.cw_loop import CwLoop
    keys = _merged_area_keys()
    for branch, screen, anchor in CwLoop.DISPATCH_AREA_ANCHORS:
        assert f'{screen}.{anchor}' in keys, (
            f'分发锚预检表条目「{branch}」的 {screen}.{anchor} 不在运行时 '
            f'merged——该分支每帧静默跳过(dd-029 事故形态)')


# ── 锁 3:事故帧路由 fixture ────────────────────────────────────────────

_FIXTURE_SCREEN = '货币战争-列车同行'
_FIXTURE_STATE = '伙伴遮罩-备战透出'   # 2026-09-04 01:02 局 1-9 备战期失败帧


def test_partner_anchor_routes_on_incident_fixture(test_context) -> None:
    """事故帧上伙伴锚必须命中 = cw_loop 0a 分支接管(路由到 CwScreenPartner
    处理链),不再因 AREA_NO_CONFIG 漏到备战部署分支。

    同帧并断言备战「购买经验」锚也命中:这正是事故的透出机制(遮罩只盖
    板面,左下购买经验仍可 OCR)——两锚同帧命中时,分发正确性完全依赖
    「overlay 分支先于备战分支」(序位由 test_cw_dispatch_order_matrix 锁)。
    """
    if not test_context.has_screen(_FIXTURE_SCREEN, _FIXTURE_STATE):
        from pytest import skip
        skip(f'fixture 缺:screens/{_FIXTURE_SCREEN}/{_FIXTURE_STATE}.webp')
    from one_dragon.base.screen import screen_utils
    from one_dragon.base.screen.screen_utils import FindAreaResultEnum

    frame = test_context.load_screen(_FIXTURE_SCREEN, _FIXTURE_STATE)
    # 事故当时:此判定 AREA_NO_CONFIG(merged 只有旧名「货币战争-选择伙伴」)
    assert screen_utils.find_area(
        test_context, frame, _FIXTURE_SCREEN, '标识-选择伙伴',
    ) is FindAreaResultEnum.TRUE, (
        f'事故帧上 {_FIXTURE_SCREEN}.标识-选择伙伴 未命中——伙伴遮罩下部署'
        f'死局(dd-029)的直因仍存活')
    # 确认选择按钮也在(= CwScreenPartner 处理链完整可执行)
    assert screen_utils.find_area(
        test_context, frame, _FIXTURE_SCREEN, '按钮-确认选择',
    ) is FindAreaResultEnum.TRUE
    # 透出机制存证:备战锚在同帧命中(遮罩未盖住)
    assert screen_utils.find_area(
        test_context, frame, '货币战争-备战', '备战标识-购买经验',
    ) is FindAreaResultEnum.TRUE, (
        'fixture 帧上备战购买经验锚未命中——透出机制存证失效,'
        '请核对 fixture 是否为事故同型帧')


def test_partner_overlay_handler_is_partner_not_expert_invite() -> None:
    """处理链归属锁(防误接线):选择伙伴 overlay 的专属 handler 是
    CwScreenPartner(注册表 handler_id 同源),不是专家邀请函的
    CwScreenExpertInvite(另一画面「货币战争-备战-专家邀请函」的 handler)。"""
    partner = next(s for s in reg.OVERLAY_REGISTRY if s.bail_tag == 'partner')
    assert partner.screen_name == _FIXTURE_SCREEN
    assert partner.handler_id == 'CwScreenPartner'
    expert = next(s for s in reg.OVERLAY_REGISTRY
                  if s.handler_id == 'CwScreenExpertInvite')
    assert expert.screen_name != _FIXTURE_SCREEN
