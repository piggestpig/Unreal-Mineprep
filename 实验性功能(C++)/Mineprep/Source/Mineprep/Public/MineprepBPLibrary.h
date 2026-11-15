// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "Kismet/BlueprintFunctionLibrary.h"
#include "Framework/Application/SlateApplication.h"
#include "Editor/UnrealEdTypes.h"
#include "Editor.h"
#include "Editor/EditorEngine.h"
#include "Settings/LevelEditorViewportSettings.h"
#include "Framework/Application/IMenu.h"
#include "Tracks/MovieSceneMaterialTrack.h"
#include "MaterialGraph/MaterialGraph.h"
#include "MaterialGraph/MaterialGraphNode.h"
#include "MaterialGraph/MaterialGraphSchema.h"
#include "ScopedTransaction.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "ISettingsModule.h"
#include "ISettingsSection.h"
#include "ISettingsContainer.h"
#include "ISettingsEditorModule.h"
#include "ISettingsCategory.h"
#include "Engine/UserDefinedEnum.h"
#include "StructUtils/UserDefinedStruct.h"  // UE5.5中的新路径
#include "CoreMinimal.h"
#include "Engine/Blueprint.h"
#include "UObject/UnrealType.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "K2Node_FunctionEntry.h"
#include "UObject/Class.h"
#include "NiagaraTypes.h"
#include "NiagaraSystem.h"
#include "MovieScene/Parameters/MovieSceneNiagaraVectorParameterTrack.h"
#include "PhysicsInterfaceDeclaresCore.h"
#include "PhysicsEngine/PhysicsSettings.h"
#include "Physics/Experimental/PhysScene_Chaos.h"
#include "EditorModeManager.h"
#include "InteractiveToolManager.h"
#include "Tools/UEdMode.h"
#include "Internationalization/TextLocalizationResource.h"
#include "Internationalization/PolyglotTextData.h"
#include "Materials/MaterialInterface.h"
#include "Framework/Notifications/NotificationManager.h"
#include "Widgets/Notifications/SNotificationList.h"

#include "MineprepBPLibrary.generated.h"

class UTextureRenderTarget2D;
class UWidget;
class UInstancedStaticMeshComponent;
class USkeletalMesh;
class UPhysicsAsset;
class UMovieSceneScriptingKey;

UENUM(BlueprintType)
enum class EMineprepPostProcessStage : uint8
{
	SceneColorBeforeDOF UMETA(DisplayName = "Scene Color Before DOF"),
	SceneColorAfterDOF UMETA(DisplayName = "Scene Color After DOF"),
	TranslucencyAfterDOF UMETA(DisplayName = "Translucency After DOF"),
	SSRInput UMETA(DisplayName = "SSR Input"),
	SceneColorBeforeBloom UMETA(DisplayName = "Scene Color Before Bloom"),
	ReplacingTonemapper UMETA(DisplayName = "Replacing the Tonemapper"),
	SceneColorAfterTonemapping UMETA(DisplayName = "Scene Color After Tonemapping"),
};

/** 编辑器右下角通知弹窗的状态图标 */
UENUM(BlueprintType)
enum class EEditorNotificationState : uint8
{
	None    UMETA(DisplayName = "无"),
	Pending UMETA(DisplayName = "进行中（旋转图标）"),
	Success UMETA(DisplayName = "成功（勾号）"),
	Fail    UMETA(DisplayName = "失败（叉号）"),
};

/** 物理形体的模拟模式（对应 EPhysicsType） */
UENUM(BlueprintType)
enum class EMineprepBodyPhysicsMode : uint8
{
	Default   UMETA(DisplayName = "跟随组件默认"),
	Kinematic UMETA(DisplayName = "运动学"),
	Simulated UMETA(DisplayName = "模拟"),
};

/** 物理约束单轴角度运动模式（对应 EAngularConstraintMotion） */
UENUM(BlueprintType)
enum class EMineprepAngularMotion : uint8
{
	Locked  UMETA(DisplayName = "锁定"),
	Limited UMETA(DisplayName = "限制"),
	Free    UMETA(DisplayName = "自由"),
};

/** 骨骼在参考姿势下的局部顶点包围盒与父子局部变换 */
USTRUCT(BlueprintType)
struct FMineprepBoneBounds
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	FName BoneName = NAME_None;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	FName ParentBoneName = NAME_None;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	FTransform LocalTransform = FTransform::Identity;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	FVector LocalMin = FVector::ZeroVector;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	FVector LocalMax = FVector::ZeroVector;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	int32 VertexCount = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	bool bHasBounds = false;
};

/** 用于构建骨骼物理资产的单盒体形体描述 */
USTRUCT(BlueprintType)
struct FMineprepPhysicsBox
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	FName BoneName = NAME_None;

	/** 盒体中心（骨骼局部空间，cm） */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	FVector Center = FVector::ZeroVector;

	/** 盒体旋转（骨骼局部空间） */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	FRotator Rotation = FRotator::ZeroRotator;

	/** 盒体完整边长 X/Y/Z（cm，对应 FKBoxElem::X/Y/Z） */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	FVector Size = FVector(10.0, 10.0, 10.0);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	bool bCollisionEnabled = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	bool bConsiderForBounds = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	EMineprepBodyPhysicsMode PhysicsMode = EMineprepBodyPhysicsMode::Default;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	float MassScale = 0.25f;

	/** 大于 0 时启用质量覆盖（kg），用于代理骨骼避免极端质量比 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	float MassOverrideKg = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	float LinearDamping = 0.01f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	float AngularDamping = 0.01f;
};

/** 用于构建骨骼物理资产的关节约束描述 */
USTRUCT(BlueprintType)
struct FMineprepPhysicsJoint
{
	GENERATED_BODY()

	/** 为空时默认使用 ChildBone */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	FName JointName = NAME_None;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	FName ChildBone = NAME_None;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	FName ParentBone = NAME_None;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	EMineprepAngularMotion Swing1Motion = EMineprepAngularMotion::Limited;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	float Swing1LimitDegrees = 45.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	EMineprepAngularMotion Swing2Motion = EMineprepAngularMotion::Limited;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	float Swing2LimitDegrees = 45.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	EMineprepAngularMotion TwistMotion = EMineprepAngularMotion::Limited;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	float TwistLimitDegrees = 45.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	bool bDisableCollision = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	bool bEnableProjection = true;
};

/** 物理资产内部显式禁用碰撞的形体名称对 */
USTRUCT(BlueprintType)
struct FMineprepDisabledBodyPair
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	FName BodyA = NAME_None;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mineprep|Physics")
	FName BodyB = NAME_None;
};


UCLASS()
class Umineprep : public UBlueprintFunctionLibrary
{
	GENERATED_UCLASS_BODY()

	/** Write a complete per-instance custom-data buffer in one game-thread call. */
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static bool SetISMCustomData(UInstancedStaticMeshComponent* Component, const TArray<float>& Values, int32 NumFloats = 8);

	//设置编辑器UI缩放
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static float SetEditorUIScale(float Scale);

	//获取鼠标指针下的文本和Tooltip
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static void GetWidgetTextUnderMouse(FString& OutWidgetText, FString& OutTooltipText);

	//翻译鼠标指针下的文本：NewText为空时查找本地化表并设置，不为空时直接设置
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static int32 LocWidgetTextUnderMouse(const FString& NewText = TEXT(""));

	/** 批量注册 Polyglot 文本并返回对应的 Text；保持输入顺序，无效条目返回空 Text。主线程调用。 */
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static TArray<FText> RegisterPolyglotTexts(const TArray<FPolyglotTextData>& TextData);

	//启用Tick多线程
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static void SetTickRunOnAnyThread(UObject* Object, bool bRunOnAnyThread);

	//辅助函数，获取材质信息
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static FComponentMaterialInfo GetMaterialInfo(UMovieSceneComponentMaterialTrack* Track);

	//清理材质节点
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static bool CleanMaterial(UMaterial* Material);

	//修改项目设置
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static bool SetProjectSetting(const FString& SettingName, const FString& Value);

	//获取项目设置
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static FString GetProjectSetting(const FString& SettingName);

	//打开项目设置栏目
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static void OpenProjectSetting(const FName& ContainerName, const FName& CategoryName, const FName& SectionName);

	//公开结构体变量的关键帧按钮
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static bool ExposeStructVariables(UUserDefinedStruct* Structure); 

	//收集公开的蓝图变量和函数名，返回三个数组：类型、Key、SourceString。SetEnumKey 为真时按同一规则写入用户枚举的本地化 Namespace/Key
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static void GatherPropertyNames(UObject* BlueprintObject, TArray<FString>& OutTypes, TArray<FString>& OutKeys, TArray<FString>& OutSourceStrings, const bool SetEnumKey = false);

	//设置Niagara参数轨道绑定的变量
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static void BindNiagaraParam(UMovieSceneNiagaraParameterTrack* ParameterTrack, FNiagaraVariable Parameter, TArray<uint8> DefaultValueData);

	//修改全局重力方向
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static void SetGlobalGravity(FVector Gravity);

	// 切换编辑器模式
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static void SwitchEditorMode(FName ModeID = TEXT("EM_ScriptableToolsEditorMode"));

	//获取某个编辑器模式是否激活
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static bool IsEditorModeActive(FName ModeID = TEXT("EM_Default"));

	// 激活 Scriptable Tool 编辑器模式并启动指定的工具
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static bool ActivateScriptableTool(UBlueprint* ToolBlueprint);

	/**
	 * 在编辑器右下角显示通知弹窗（类似烘焙进度弹窗）
	 * @param Message       主提示文本
	 * @param SubText       次级说明文本（可为空）
	 * @param State         图标状态：None / Pending（旋转）/ Success（勾号）/ Fail（叉号）
	 * @param Duration      弹窗自动消失时间（秒），<=0 表示不自动消失
	 * @param bUseThrobber  是否显示旋转加载动画（Pending 状态时生效）
	 */
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static void ShowEditorNotification(
		const FString& Message,
		const FString& SubText,
		EEditorNotificationState State = EEditorNotificationState::None,
		float Duration = 3.0f,
		bool bUseThrobber = false);

	// 将当前视口画面绘制到渲染目标
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static bool DrawViewportToRenderTarget(UTextureRenderTarget2D* RenderTarget, bool bAutoResize = true, bool bBlockUntilReady = false);

	// 将当前编辑器视口在指定后处理阶段的结果绘制到渲染目标
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static bool DrawPostProcessStageToRenderTarget(UTextureRenderTarget2D* RenderTarget, EMineprepPostProcessStage Stage, bool bAutoResize = true, bool bBlockUntilReady = false);

	/**
	 * 截取 UMG 控件（或当前顶层编辑器窗口）为 PNG。
	 * 仅当 GeneratePathToWidgetUnchecked 成功时才调用 TakeScreenshot（避免 Checked 断言闪退）；
	 * 控件不在可见 Slate 树中时改为离屏绘制。
	 * @param Widget  要截取的 UMG 控件；为空则截取当前顶层窗口
	 * @param Path    输出路径。空=Saved/Screenshots/WidgetScreenshot.png；相对路径相对该目录；无后缀则补 .png
	 * @param Delay   秒数；立即保存第一张，Delay>0 时延时再截并覆盖同一路径；目标不再可见时跳过刷新
	 * @return        成功：保存的绝对路径（.png）；失败：以 WidgetScreenshot: 开头的错误说明（不是文件路径）
	 */
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static FString WidgetScreenshot(UWidget* Widget, const FString& Path = TEXT(""), float Delay = 0.f);

	/**
	 * 等待贴图平台数据编译完成。不调用 Modify()，因此不会取消正在进行的编译。
	 * 若仍是占位图或没有 Mip，则强制重建一次并再次等待。
	 * @return 之后不再使用编译器占位图
	 */
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static bool FinishBuildTexture(UTexture* Texture);

	/** 手动释放默认骨骼网格体/Skeleton 缩略图预览缓存并执行 GC。仅编辑器主线程、非 PIE/SIE；可能短暂卡顿。 */
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static bool ClearSkeletalThumbnailCache();

	/** Synchronize Float/Double channel rates in the keys' owning sections. */
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static bool SyncKeyTickResolution(const TArray<UMovieSceneScriptingKey*>& Keys);

	/**
	 * 只读查询骨骼网格体指定 LOD 的逐骨骼参考姿势局部顶点包围盒。
	 * 若网格 CPU 顶点/蒙皮缓冲不可读或参数无效，不会自动修改网格设置，而是返回空数组并写入 OutError。
	 */
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static TArray<FMineprepBoneBounds> GetBoneLocalBounds(
		USkeletalMesh* SkeletalMesh,
		FString& OutError,
		int32 LODIndex = 0,
		bool bDominantWeightOnly = true);

	/**
	 * 按给定盒体形体、约束与禁用碰撞对原子构建或覆盖指定路径的物理资产（仅设置物理资产内部状态，不改动目标网格本身）。
	 * 覆盖已有资产时不记录编辑器撤销事务；新建与生成的子对象仍保留事务标记供后续在物理资产编辑器中手动编辑。
	 */
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static UPhysicsAsset* BuildBoxPhysicsAsset(
		USkeletalMesh* ReferenceMesh,
		const FString& AssetPath,
		const TArray<FMineprepPhysicsBox>& Boxes,
		const TArray<FMineprepPhysicsJoint>& Joints,
		const TArray<FMineprepDisabledBodyPair>& DisabledPairs,
		FString& OutError,
		bool bOverwriteExisting = true);


};
