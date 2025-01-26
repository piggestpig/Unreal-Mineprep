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
#include "MineprepBPLibrary.generated.h"

UCLASS()
class Umineprep : public UBlueprintFunctionLibrary
{
	GENERATED_UCLASS_BODY()

	UFUNCTION(BlueprintCallable, meta = (DisplayName = "Set Editor UI Scale", Keywords = "Mineprep UI Scale Editor"), Category = "Mineprep|实验性功能(C++)")
	static float SetEditorUIScale(float Scale);

	UFUNCTION(BlueprintCallable, meta = (DisplayName = "Get Widget Text Under Mouse", Keywords = "Mineprep UI Widget Text"), Category = "Mineprep|实验性功能(C++)")
	static FString GetWidgetTextUnderMouse();

	UFUNCTION(BlueprintCallable, meta = (DisplayName = "Set Tick Run On Any Thread", Keywords = "Mineprep Tick Thread"), Category = "Mineprep|实验性功能(C++)") 
	static void SetTickRunOnAnyThread(UObject* Object, bool bRunOnAnyThread);

	UFUNCTION(BlueprintCallable, meta = (DisplayName = "Get Material Info", Keywords = "Mineprep Material Info"), Category = "Mineprep|实验性功能(C++)")
	static FComponentMaterialInfo GetMaterialInfo(UMovieSceneComponentMaterialTrack* Track);

	UFUNCTION(BlueprintCallable, meta = (DisplayName = "Clean Material", Keywords = "Mineprep Material Clean"), Category = "Mineprep|实验性功能(C++)")
	static bool CleanMaterial(UMaterial* Material);

	UFUNCTION(BlueprintCallable, meta = (DisplayName = "Set Project Setting", Keywords = "Mineprep Settings"), Category = "Mineprep|实验性功能(C++)")
	static bool SetProjectSetting(const FString& SettingName, const FString& Value);

	UFUNCTION(BlueprintCallable, meta = (DisplayName = "Get Project Setting", Keywords = "Mineprep Settings"), Category = "Mineprep|实验性功能(C++)")
	static FString GetProjectSetting(const FString& SettingName);

	UFUNCTION(BlueprintCallable, meta = (DisplayName = "Open Project Setting", Keywords = "Mineprep Settings"), Category = "Mineprep|实验性功能(C++)")
	static void OpenProjectSetting(const FName& ContainerName, const FName& CategoryName, const FName& SectionName);

	UFUNCTION(BlueprintCallable, meta = (DisplayName = "Expose Struct Variables"), Category = "Mineprep|实验性功能(C++)")
	static bool ExposeStructVariables(UUserDefinedStruct* Structure); 
};

