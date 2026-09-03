# w546 数量锁识别结果 fixture

`w546_count_ocr_fixture.json` 是 `test_cw_w546_equip_grid.py::TestEquipCount::
test_count_digits_and_infinity` 的**识别结果 fixture**:把数量锁依赖的两类真识别输出
一次性提取入库,测试不再跑逐帧网格分类(~7s/帧)与 OCR 引擎装载推理,从 20.3s 降到
亚秒级(2026-09-01 实测 16.0s call → 0.08s)。

## 内容与语义

每代表帧两份录制(帧 = `sr-od-test/screens/货币战争-备战/` 下样本):

- `cell: [cx, cy]` — 目标格心,取自真 `read_equip_grid` 的 TM 峰心(非名义格点;
  实测峰心与名义格点差 5px 即足以让 OCR 读错,勿手改)。
- `ocr: {裁片md5: [原文...]}` — `read_equip_count` 实际发出的每张数量裁片,经真
  OCR 引擎(ppocrv5 det+rec)识别的原文逐条录制。

测试侧 `_ReplayCountOcr` 按裁片内容 md5 回放:裁剪区域/变体管线任何改动使裁片内容
变 → 哈希未命中 → 失读(空结果),与真引擎面对错裁片的行为一致。锁的仍是
`read_equip_count` 的判读逻辑(区域裁剪/变体/∞ 结构预判/`_parse_equip_count`),
不是 OCR 引擎本身。

## 再生

样本帧或模板更新后重录:

```shell
$env:PYTHONPATH="src"
uv run python -X utf8 sr-od-test/test/sr_od/app/currency_war/fixtures/regen_w546_count_ocr_fixture.py
```

脚本内部跑真 `read_equip_grid` + 真 OCR 引擎并断言读取结果等于 case 期望值
(`拆装扳手×4` / `精密拆装扳手∞`),录制失败即报错,不落脏 fixture。
已验证同环境重跑产物逐字节一致。
