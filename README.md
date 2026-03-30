# MultiLoader Template

这个模板用于同时维护 `common / fabric / neoforge` 三端代码，并提供基于 `gradle.properties` 的一键同步脚本。

## 使用流程

1. 克隆或使用模板创建项目。
2. 修改根目录 [gradle.properties](./gradle.properties) 中与你项目相关的配置。
3. 执行 `syncProjectFromProperties` 同步项目结构和命名。
4. 如果你写了 `accesstransformer.cfg`，再执行 `generateClassTweakerFromAt` 生成 Fabric 侧的 `.classtweaker`。

## 需要修改的关键配置

至少确认以下字段：

- `group`：Java 包名根路径（例如 `com.yourname.yourmod`）
- `mod_id`：模组 ID（小写）
- `mod_name`：模组显示名
- `common_mainclassname`：Common 主类名
- `fabric_mainclassname`：Fabric 主类名
- `neoforge_mainclassname`：NeoForge 主类名
- `license`：许可证标识（标准 SPDX/GitHub license key 时会自动同步 LICENSE 文本）

## 同步命令

### 1) 一键同步模板命名

```powershell
.\gradlew syncProjectFromProperties
```

该任务会根据 `gradle.properties`：

- 同步三模块包名
- 同步 common/fabric/neoforge 各自主类名
- 同步 `mod_id` 相关文件名与文本引用（包括 mixin 文件名等）
- 更新 common 主类中的 `MOD_ID` / `MOD_NAME`
- 当 `license` 为标准许可证名时，通过 GitHub API 更新根目录 `LICENSE`
- 自动触发一次 classtweaker 生成

### 2) 仅生成 classtweaker

```powershell
.\gradlew generateClassTweakerFromAt
```

输入文件：

- `common/src/main/resources/META-INF/accesstransformer.cfg`

输出文件：

- `common/src/main/resources/<mod_id>.classtweaker`

## AT -> CT 转换说明

- 转换器会忽略注释行。
- 只自动处理 `net.minecraft.*`（原版）访问加宽。
- 非原版类或无法可靠转换的条目会标记为 `SKIPPED`，请手动处理。
- 对于 AT 字段未写 descriptor 的情况，会尝试从 `common/build/moddev/artifacts/vanilla-*-sources.jar` 推断类型。

## 发布任务（可选）

- 聚合发布：`publishLoaderReleases`
- 单端发布：
  - `:fabric:publishToPlatformServices`
  - `:neoforge:publishToPlatformServices`

发布参数见 `gradle.properties` 的 `Release Publishing` 段。
