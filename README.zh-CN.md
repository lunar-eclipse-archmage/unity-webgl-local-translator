# Unity WebGL Local Translator

[English](README.md) | 简体中文

Unity WebGL 资源采集、文本翻译、Bundle 打包验证及 DevTools Overrides 部署工具。

当前版本：1.0.0。支持本地处理已有补丁，不包含游戏资源或字体补丁。

## 环境

- Python 3.10 或更新版本，命令为 `python3`
- Chrome 或兼容的 Chromium 浏览器
- Tampermonkey
- 支持 Responses API 的接口；自动翻译需要 API key

## 安装

1. 解压项目，运行 `install.bat`。发布包仅提供配置模板 `local.example.py`，不包含 `local.py`。
2. 安装脚本在缺少 `local.py` 时从 `local.example.py` 创建本地配置，不覆盖已有配置。依赖安装到项目内 `python_libs`。所有 Python 命令入口自动加载该目录。
3. 编辑 `local.py`：填写 `OPENAI_API_KEY`，默认模型为 `gpt-4.1`。仅采集、登记、打包或部署不需要 API key。
4. 生成本地服务认证值：

```bat
python3 -c "import secrets; print(secrets.token_hex(32))"
```

将结果填写到 `local.py` 的 `LOCAL_SERVICE_TOKEN`，以及油猴脚本的 `serviceToken`。两处必须一致。

## Overrides 路径

默认目录是 `local.py` 所在目录下的 `Overrides`。项目所在路径较长时，建议使用短绝对路径：

```python
OVERRIDES_ROOT = r"G:\Overrides"
```

DevTools → Sources → Overrides 中选择相同的目录，允许访问并启用 **Enable Local Overrides**。加载补丁时保持 DevTools 打开。

保留请求对应的目录结构：

```text
Overrides/资源主机名/资源路径/完整文件名.bundle
```

DevTools 可能把较长路径映射为 `主机名/longurls/短文件名`。当前自动部署和登记不支持该映射。出现 `longurls` 时，应缩短 Overrides 根路径，并通过浏览器的 **Override content** 核对实际映射。不要将短文件名直接作为原 Bundle 文件名登记。

## 油猴配置

安装 `Unity_Translation_Toolkit.user.js`，修改顶部 `@match` 和 `GAME_CONFIG`。默认占位地址不会在真实网站运行。

| 配置 | 说明 |
| --- | --- |
| `@match` | 实际游戏页面或 iframe 的匹配规则 |
| `serviceToken` | 与 `LOCAL_SERVICE_TOKEN` 相同的认证值 |
| `resourceHosts` | 允许采集和清理缓存的精确主机名数组，不含协议或路径 |
| `catalogURL` | 实际 Addressables Catalog 地址；留空禁用目录修改 |
| `catalogIgnoreSearch` | 默认 `true`，Catalog 只比较 origin 和 pathname，兼容动态 token；需要精确查询参数时设为 `false` |
| `mainPatch.enabled` | 可选主资源字体替换，默认关闭 |
| `mainPatch.url` | 要替换的完整主资源 URL，包含版本查询参数 |
| `mainPatch.bytes` | 本地解压后主资源补丁的精确字节数 |

配置示例中的地址仅为占位值：

```javascript
// @match        https://game.example.invalid/*
const GAME_CONFIG = Object.freeze({
  serviceToken: "填写随机认证值",
  resourceHosts: ["cdn.example.invalid"],
  catalogURL: "https://game.example.invalid/app_data/StreamingAssets/aa/catalog.json",
  catalogIgnoreSearch: true,
  mainPatch: { enabled: false, url: "", bytes: 0 }
});
```

Catalog 的查询参数忽略规则仅用于 Catalog。主资源 URL 仍精确匹配，Bundle 缓存键仍保留查询参数，不混用不同资源版本。

开启主资源替换后，每次刷新需要选择本地补丁；匹配的请求会等待文件选择。只支持解压后的 `UnityWebData1.0` 文件。依赖外部字体 Bundle 的补丁必须配套使用。

## 首次启动及迁移

首次切换版本时，先验证原资源加载：

1. 将已有补丁保留在 Overrides 之外的备份目录。
2. 禁用游戏相关油猴脚本和 DevTools 本地覆盖。
3. 若已有旧缓存，清理实际游戏页面的 Cache Storage 和 UnityCache；不必删除 Cookies。
4. 使用原资源启动游戏一次，确认正常加载。
5. 启用配置好的新版脚本、启动 `start_collector.bat`，并启用本地覆盖。
6. 将配套补丁放入选定的 Overrides 根目录，按下一节登记。

这是一项首次迁移步骤，不要求每次启动都使用原资源。浏览器清理 IndexedDB 会删除脚本待发送队列，不删除磁盘上的译文和补丁。

## 登记已有补丁

已翻译或修改好的 Bundle 无需重新翻译、打包。确认 Overrides 中均为要使用的补丁后，在项目目录执行：

```bat
python3 register_overrides.py
```

只登记指定文件或目录：

```bat
python3 register_overrides.py "G:\Overrides\cdn.example.invalid\资源路径"
```

登记会读取文件大小、SHA-256 和 Overrides 相对路径，更新 `deployed.json`，并备份旧记录。不修改或复制 Bundle。空文件、重复哈希、不支持的格式或 `longurls` 短文件名导致整次登记失败。

登记完成后：

1. 保持 `start_collector.bat` 运行。
2. 面板“检查本地服务”应显示已部署资源数量。
3. 点击“清理补丁缓存并刷新”；启用字体主资源替换时重新选择 `.data`。
4. 确认目录日志出现 `Catalog patched: target CRC=0`，并查看对应 Bundle GET 的本地覆盖标记。

登记成功不等于本地覆盖已应用，也不证明文件已翻译。手动修改 Bundle 内容后需要重新登记。仅迁移 Overrides 根路径、内部相对路径与内容不变时，登记记录可继续使用。

## 采集与翻译

运行 `start_collector.bat` 不调用翻译 API。采集发现文本的资源保存到 `inbox`。对选定原始 Bundle 执行：

```bat
python3 pipeline.py all "inbox\选定目录\文件.bundle"
```

`all` 顺序执行提取、翻译、打包验证和部署。目录输入递归处理；同名多版本会跳过，应指定唯一原始文件。不要将已经翻译过的 Bundle 混入原始资源。

浏览器持久队列最多64项、合计256MiB；每项最多发送5次，失败后退避重试，达到次数上限后保留任务。面板支持查看队列及重试暂停任务。队列满或写入失败时需处理后重新加载资源。清理站点存储或浏览器回收存储可能删除队列。

面板支持最小化、隐藏及关闭日志，油猴菜单可重新打开面板。

## 手动修正译文

编辑对应 `work` 目录的 `translated.json`，仅修改 `translation` 字段。保留 `id`、`source`、`asset`、`path_id`、`mode`、`path`，以及标签、变量和换行。

对对应的原始 Bundle 执行：

```bat
python3 pipeline.py pack "inbox\选定目录\文件.bundle"
python3 pipeline.py deploy "inbox\选定目录\文件.bundle"
```

这两条不调用 API。未完成、被阻止或校验失败的任务不会部署。修改译文后必须重新打包；部署前已有覆盖文件自动备份。

提示“译文定位或原文变化”时，对照 `extracted.json` 恢复该 ID 的定位与原文字段，保留修改后的 `translation`。

同一任务应固定模型和提示词。现有任务不支持中途切换模型或提示词；需要切换时，使用独立项目目录重新处理原始资源。

## 任务恢复

成功翻译批次即时保存。临时错误重试耗尽后可重跑续传；拒绝或校验耗尽的任务暂停，不无限调用 API。

即使首次请求全部失败、尚未生成翻译缓存，也可以人工补齐 `pending.json` 的 `translation` 后执行：

```bat
python3 manual_import.py "work\任务目录" "work\任务目录\pending.json"
```

全部补齐后再运行 `pack` 和 `deploy`。不要删除状态文件来绕过校验。同一任务只允许一个进程修改；部署记录更新串行执行。

## 检查与排障

| 现象 | 检查 |
| --- | --- |
| HTTP 401 | Python 与油猴认证值是否一致 |
| 已部署 0 个 | 服务与登记命令是否使用同一项目、Overrides 根路径是否正确 |
| 有登记数量但没有覆盖标记 | DevTools 是否启用、文件夹是否一致、请求是否为 GET、实际映射是否进入 longurls |
| 只有 HEAD 请求 | 查看缓存读取日志；HEAD 不返回 Bundle 内容，不能单凭标记判断覆盖结果 |
| CRC Mismatch | 对应补丁是否登记、Catalog 是否实际匹配并输出修改日志、是否有解析错误或部分目标未匹配 |
| Catalog 有动态 token | 默认忽略 Catalog 查询参数；检查配置中的 origin 和 pathname 是否与实际请求一致 |
| 字体仍为方框 | 确认 `.data` GET 替换日志及配套字体 Bundle 覆盖，不仅检查登记数量 |

只有登记或部署记录与实际文件哈希、相对路径一致的资源进入 Catalog 修改清单。除匹配的目录请求外，其他请求不等待本地清单；服务不可用时放行原请求。

## 兼容范围

- 文本提取支持已实现的 TextAsset 和剧情字段结构，包括 `textMap/idToText/values`。
- Catalog 修改依赖当前实现的 Addressables JSON 二进制附加数据格式，不保证所有 Unity 版本兼容。
- 自动部署和登记要求 UnityFS Bundle，文件名末尾含32位十六进制资源哈希；自动部署实际格式由打包模块产生。
- 不支持自动生成字体补丁，也不支持 DevTools `longurls` 映射部署。
- 已完成配置范围内的实际使用测试，并通过自动化回归检查。该测试范围不代表所有游戏、Unity 版本或浏览器均兼容。

## 免责声明

本项目用于学习与研究，与 Unity、游戏开发商或平台无隶属关系。使用者应确认拥有处理资源的权限，遵守适用法律和服务条款。学习用途不构成免责或授权。第三方游戏资源与字体的权利属于其权利人，API 费用由使用者承担。

本软件按“现状”提供，不提供任何形式的担保。使用者应自行确认资源处理权限，遵守适用法律和平台条款，并评估使用、修改或分发本工具的风险，包括数据丢失或损坏、翻译错误、服务或账号受限以及 API 费用。在适用法律允许的最大范围内，作者及贡献者不对因本软件或其使用产生的索赔、损失或其他责任承担责任。本声明不排除或限制依法不得排除或限制的责任。完整 MIT 许可条款见 `LICENSE`。

## 许可

项目源码采用 MIT License，见 `LICENSE`。该许可不覆盖第三方游戏资源或依赖；分发依赖时应保留其各自要求的版权与许可声明。直接依赖及许可文本见 `THIRD_PARTY_NOTICES.md` 和 `licenses/`。

发布内容仅为工具源码、空白配置模板和项目文档，不包含已安装依赖、游戏资源、字体补丁、剧情译文或运行数据。`glossary.json` 默认为空，由使用者填写术语。自动翻译会把选定文本及上下文发送至配置的 API 服务；本地采集、登记、打包和部署不调用翻译 API。
