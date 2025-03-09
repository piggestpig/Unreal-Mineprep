// // Copyright Epic Games, Inc. All Rights Reserved.

// #pragma once

// #include "CoreMinimal.h"
// #include "Kismet/BlueprintFunctionLibrary.h"
// #include "Engine/UserDefinedStruct.h"
// #include "Engine/Blueprint.h"
// #include "TempBPLibrary.generated.h"

// /**
//  * 临时函数库，用于实验性功能
//  */
// UCLASS()
// class MINEPREP_API UTempBPLibrary : public UBlueprintFunctionLibrary
// {
// 	GENERATED_BODY()

// public:
// 	//打印公开的蓝图变量和函数名
// 	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
// 	static void GatherPropertyNames(UObject* BlueprintObject);

// 	//为蓝图变量或函数注入DisplayName元数据
// 	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
// 	static bool InjectDisplayName(UObject* BlueprintObject, const TMap<FString, FString>& PropertyDisplayMap, const bool save = false, const bool debug = false);

// 	//为蓝图变量或函数设置工具提示
// 	UFUNCTION(BlueprintCallable, Category = "Mineprep|实验性功能(C++)")
// 	static bool SetPropertyTooltip(UObject* BlueprintObject, const TMap<FString, FString>& PropertyTooltipMap, const bool save = false, const bool debug = false);
// };
