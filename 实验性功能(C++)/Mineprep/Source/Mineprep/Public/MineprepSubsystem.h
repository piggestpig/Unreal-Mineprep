// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "EditorSubsystem.h"
#include "Framework/Commands/InputChord.h"
#include "Framework/Commands/UICommandInfo.h"
#include "MineprepSubsystem.generated.h"

class FUICommandList;
class UObject;

UCLASS(BlueprintType, Blueprintable)
class MINEPREP_API UMineprepSubsystem : public UEditorSubsystem
{
    GENERATED_BODY()

public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;

    //从蓝图对象中加载快捷键配置
    UFUNCTION(BlueprintCallable, Category = "Mineprep|快捷键")
    void LoadHotkeysFromFile();

    //从蓝图对象中注销快捷键配置
    UFUNCTION(BlueprintCallable, Category = "Mineprep|快捷键")
    void UnloadHotkeysFromFile();

    //注册快捷键
    UFUNCTION(BlueprintCallable, Category = "Mineprep|快捷键")
    bool RegisterHotkey(const FString& CommandName, const FString& DisplayName, const FString& Description,
                        const FInputChord& Chord, const FString& BlueprintEventName = TEXT(""));

    //注销指定的快捷键
    UFUNCTION(BlueprintCallable, Category = "Mineprep|快捷键")
    bool UnregisterHotkey(const FString& CommandName);

    //执行"Mineprep自定义快捷键"蓝图中的事件
    UFUNCTION(BlueprintCallable, Category = "Mineprep|快捷键")
    void ExecuteBlueprintEvent(FString EventName);

    //获取自定义快捷键对象
    UFUNCTION(BlueprintCallable, Category = "Mineprep|快捷键")
    UObject* GetHotkeyObject();

    //重新加载快捷键对象
    UFUNCTION(BlueprintCallable, Category = "Mineprep|快捷键")
    UObject* ReloadHotkeyObject();

public:
    // 存储命令名到蓝图事件名的映射
    UPROPERTY(BlueprintReadWrite, Category = "Mineprep")
    TMap<FString, FString> CommandToEventMap;
    
    // 用于执行蓝图事件的蓝图路径
    UPROPERTY(BlueprintReadWrite, Category = "Mineprep")
    FString BlueprintPath = TEXT("/Mineprep/Mineprep自定义快捷键.Mineprep自定义快捷键_C");
    
    // 快捷键对象
    UPROPERTY(BlueprintReadWrite, Category = "Mineprep")
    UObject* HotkeyObject = nullptr;
    
    // 命令列表
    TSharedPtr<FUICommandList> CommandList;
    
    // 创建动态命令类(Forward声明)
    TSharedPtr<class FDynamicHotkeyCommands> DynamicCommands;
    
    // 初始化动态命令
    void InitializeDynamicCommands();
};
