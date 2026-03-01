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
#include "Engine/UserDefinedStruct.h"
#include "Engine/UserDefinedEnum.h"
#include "StructUtils/UserDefinedStruct.h"  // UE5.5中的新路径
#include "CoreMinimal.h"
#include "Engine/UserDefinedStruct.h"
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
#include "Materials/MaterialInterface.h"
#include "Framework/Notifications/NotificationManager.h"
#include "Widgets/Notifications/SNotificationList.h"

#include "MineprepBPLibrary.generated.h"

/** 编辑器右下角通知弹窗的状态图标 */
UENUM(BlueprintType)
enum class EEditorNotificationState : uint8
{
	None    UMETA(DisplayName = "无"),
	Pending UMETA(DisplayName = "进行中（旋转图标）"),
	Success UMETA(DisplayName = "成功（勾号）"),
	Fail    UMETA(DisplayName = "失败（叉号）"),
};

UCLASS()
class Umineprep : public UBlueprintFunctionLibrary
{
	GENERATED_UCLASS_BODY()

	//设置编辑器UI缩放
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static float SetEditorUIScale(float Scale);

	//获取鼠标指针下的文本和Tooltip
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static void GetWidgetTextUnderMouse(FString& OutWidgetText, FString& OutTooltipText);

	//翻译鼠标指针下的文本：NewText为空时查找本地化表并设置，不为空时直接设置
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static int32 LocWidgetTextUnderMouse(const FString& NewText = TEXT(""));

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

	//收集公开的蓝图变量和函数名，返回三个数组：类型、Key、SourceString
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static void GatherPropertyNames(UObject* BlueprintObject, TArray<FString>& OutTypes, TArray<FString>& OutKeys, TArray<FString>& OutSourceStrings);

	//为蓝图变量或函数注入DisplayName元数据，已弃用
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)", meta=(DeprecatedFunction))
	static bool InjectDisplayName(UObject* BlueprintObject, const TMap<FString, FString>& PropertyDisplayMap, const bool save = false, const bool debug = false);

	//为蓝图变量或函数设置工具提示
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)", meta=(DeprecatedFunction))
	static bool SetPropertyTooltip(UObject* BlueprintObject, const TMap<FString, FString>& PropertyTooltipMap, const bool save = false, const bool debug = false);

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

};

