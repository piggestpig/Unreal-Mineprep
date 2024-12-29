// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "Kismet/BlueprintFunctionLibrary.h"
#include "Framework/Application/SlateApplication.h"
#include "Editor/UnrealEdTypes.h"
#include "Editor.h"
#include "Editor/EditorEngine.h"
#include "Settings/LevelEditorViewportSettings.h"
#include "Framework/Application/IMenu.h"
#include "MineprepBPLibrary.generated.h"

UCLASS()
class Umineprep : public UBlueprintFunctionLibrary
{
	GENERATED_UCLASS_BODY()

	UFUNCTION(BlueprintCallable, meta = (DisplayName = "Set Editor UI Scale", Keywords = "Mineprep UI Scale Editor"), Category = "Mineprep|实验性功能(C++)")
	static float SetEditorUIScale(float Scale);

	UFUNCTION(BlueprintCallable, meta = (DisplayName = "Set Preview Selected Cameras", Keywords = "Mineprep Camera Preview"), Category = "Mineprep|实验性功能(C++)")
	static void SetPreviewSelectedCameras(bool bPreview);

	UFUNCTION(BlueprintCallable, meta = (DisplayName = "Set Camera Preview Size", Keywords = "Mineprep Camera Preview"), Category = "Mineprep|实验性功能(C++)")
	static void SetCameraPreviewSize(float PreviewSize);

	UFUNCTION(BlueprintCallable, meta = (DisplayName = "Get Widget Text Under Mouse", Keywords = "Mineprep UI Widget Text"), Category = "Mineprep|实验性功能(C++)")
	static FString GetWidgetTextUnderMouse();

	UFUNCTION(BlueprintCallable, meta = (DisplayName = "Set Tick Run On Any Thread", Keywords = "Mineprep Tick Thread"), Category = "Mineprep|实验性功能(C++)") 
	static void SetTickRunOnAnyThread(UObject* Object, bool bRunOnAnyThread);
};


