"""r132 修正:read_row_equipped 真实 import 路径(cw_identity_obs 非
cw_equipment——cw_type_gate 抓到 unknown symbol,测试绿是因为方法体
只在运行时 import)。锁 import 路径防再犯。

出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
import sys

sys.path.insert(0, 'src')


def test_read_row_equipped_import_path():
    """r132 的 import 路径必须可解析(防运行时才炸)。"""
    from sr_od.application.currency_war.obs.cw_identity_obs import read_row_equipped
    assert callable(read_row_equipped)


def test_deploy_equips_snapshot_method_exists():
    """DeployBench._snapshot_equips_into_tracking 在位(r132 采集钩子)。"""
    from sr_od.application.currency_war.operations.prep.deploy_bench import DeployBench
    assert hasattr(DeployBench, '_snapshot_equips_into_tracking')
