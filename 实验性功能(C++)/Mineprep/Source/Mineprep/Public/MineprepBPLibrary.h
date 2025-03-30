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
#include "MovieScene/Parameters/MovieSceneNiagaraVectorParameterTrack.h"
#include "PhysicsInterfaceDeclaresCore.h"
#include "PhysicsEngine/PhysicsSettings.h"
#include "Physics/Experimental/PhysScene_Chaos.h"
#include "MineprepBPLibrary.generated.h"


UCLASS()
class Umineprep : public UBlueprintFunctionLibrary
{
	GENERATED_UCLASS_BODY()

	//设置编辑器UI缩放
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static float SetEditorUIScale(float Scale);

	//获取鼠标指针下的文本
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static FString GetWidgetTextUnderMouse();

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

	//打印公开的蓝图变量和函数名
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static void GatherPropertyNames(UObject* BlueprintObject);

	//为蓝图变量或函数注入DisplayName元数据
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static bool InjectDisplayName(UObject* BlueprintObject, const TMap<FString, FString>& PropertyDisplayMap, const bool save = false, const bool debug = false);

	//为蓝图变量或函数设置工具提示
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static bool SetPropertyTooltip(UObject* BlueprintObject, const TMap<FString, FString>& PropertyTooltipMap, const bool save = false, const bool debug = false);

	//设置Niagara参数轨道绑定的变量
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static void BindNiagaraParam(UMovieSceneNiagaraParameterTrack* ParameterTrack, FNiagaraVariable Parameter, TArray<uint8> DefaultValueData);

	//修改全局重力方向
	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
	static void SetGlobalGravity(FVector Gravity, float DeltaSeconds);
};

