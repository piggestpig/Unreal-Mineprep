// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "EditorSubsystem.h"
#include "Framework/Commands/InputChord.h"
#include "Framework/Commands/UICommandInfo.h"
#include "MineprepSubsystem.generated.h"

class FUICommandList;
class UObject;

// 快捷键动态多播委托：广播 CommandName
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FMineprepHotkeyPressedSignature, const FString&, CommandName);

UCLASS(BlueprintType, Blueprintable)
class MINEPREP_API UMineprepSubsystem : public UEditorSubsystem
{
    GENERATED_BODY()

public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;

    // 快捷键触发动态多播委托（Python端直连监听）
    UPROPERTY(BlueprintAssignable, Category = "Mineprep|快捷键")
    FMineprepHotkeyPressedSignature OnHotkeyPressed;

    // 注册快捷键
    UFUNCTION(BlueprintCallable, Category = "Mineprep|快捷键")
    bool RegisterHotkey(const FString& CommandName, const FString& DisplayName, const FString& Description, const FInputChord& Chord);

    // 注销快捷键
    UFUNCTION(BlueprintCallable, Category = "Mineprep|快捷键")
    bool UnregisterHotkey(const FString& CommandName);

    // 统一快捷键触发入口（广播委托）
    UFUNCTION(BlueprintCallable, Category = "Mineprep|快捷键")
    void ExecuteHotkey(FString CommandName);

    /**
     * 检测给定快捷键是否与已注册命令冲突
     * @param Chord                  待检测的快捷键
     * @param OutConflictName        冲突命令的内部名称（输出）
     * @param OutConflictDisplayName 冲突命令的显示名称（输出）
     * @return 有冲突时返回 true
     */
    UFUNCTION(BlueprintCallable, Category = "Mineprep|快捷键")
    bool CheckHotkeyConflict(const FInputChord& Chord, FString& OutConflictName, FString& OutConflictDisplayName);

    // 获取快捷键对象（供 AddKeyframes/Mineprep.cpp 等模块调用）
    UFUNCTION(BlueprintCallable, Category = "Mineprep|快捷键")
    UObject* GetHotkeyObject();

    // 重新加载快捷键对象
    UFUNCTION(BlueprintCallable, Category = "Mineprep|快捷键")
    UObject* ReloadHotkeyObject();

public:
    // 供 AddKeyframes 兼容保留
    UPROPERTY(BlueprintReadWrite, Category = "Mineprep")
    FString BlueprintPath = TEXT("/Mineprep/Mineprep自定义快捷键.Mineprep自定义快捷键_C");

    // 快捷键对象（供 AddKeyframes 兼容保留）
    UPROPERTY(BlueprintReadWrite, Category = "Mineprep")
    UObject* HotkeyObject = nullptr;

    // 命令列表
    TSharedPtr<FUICommandList> CommandList;

    // 动态命令类
    TSharedPtr<class FDynamicHotkeyCommands> DynamicCommands;

    // 初始化动态命令
    void InitializeDynamicCommands();
};
