// Copyright Epic Games, Inc. All Rights Reserved.

#include "MineprepSubsystem.h"
#include "Framework/Commands/Commands.h"
#include "Framework/Commands/UICommandList.h"
#include "LevelEditor.h"
#include "Framework/Application/SlateApplication.h"
#include "Styling/AppStyle.h"
#include "Engine/Engine.h"
#include "Kismet/GameplayStatics.h"


// 动态命令类定义
class FDynamicHotkeyCommands : public TCommands<FDynamicHotkeyCommands>
{
public:
    FDynamicHotkeyCommands()
        : TCommands<FDynamicHotkeyCommands>(
              TEXT("Mineprep自定义快捷键"),
              NSLOCTEXT("Contexts", "MineprepDynamicCommands", "Mineprep自定义快捷键"),
              NAME_None,
              FAppStyle::GetAppStyleSetName())
    {
    }

    // 注册命令时不做任何事，我们会动态添加命令
    virtual void RegisterCommands() override {}

    // 动态添加命令
    TSharedPtr<FUICommandInfo> AddCommand(const FString& CommandName, const FString& DisplayName, const FString& Description, const FInputChord& Chord)
    {
        TSharedPtr<FUICommandInfo> Command;
        
        FUICommandInfo::MakeCommandInfo(
            AsShared(),
            Command,
            *CommandName,
            FText::FromString(DisplayName),
            FText::FromString(Description),
            FSlateIcon(),
            EUserInterfaceActionType::Button,
            Chord);

        // 存储命令信息用于后续访问
        CommandMap.Add(CommandName, Command);
        return Command;
    }

    // 获取命令
    TSharedPtr<FUICommandInfo> GetCommand(const FString& CommandName)
    {
        return CommandMap.FindRef(CommandName);
    }

private:
    // 存储所有创建的命令
    TMap<FString, TSharedPtr<FUICommandInfo>> CommandMap;
};

void UMineprepSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    // 获取编辑器命令列表
    if (FLevelEditorModule* LevelEditorModule = FModuleManager::GetModulePtr<FLevelEditorModule>("LevelEditor"))
    {
        CommandList = LevelEditorModule->GetGlobalLevelEditorActions();

        if (!CommandList.IsValid())
        {
            UE_LOG(LogTemp, Error, TEXT("MineprepSubsystem初始化失败：无法获取编辑器命令列表"));
        }
    }

    // 初始化动态命令
    InitializeDynamicCommands();
    UE_LOG(LogTemp, Log, TEXT("MineprepSubsystem 初始化完成"));
}

void UMineprepSubsystem::Deinitialize()
{
    // 清除快捷键对象
    HotkeyObject = nullptr;
    
    // 清除所有映射
    CommandToEventMap.Empty();
    DynamicCommands.Reset();
    CommandList.Reset();
    
    UE_LOG(LogTemp, Log, TEXT("MineprepSubsystem 已关闭"));
}

void UMineprepSubsystem::InitializeDynamicCommands()
{
    // 创建动态命令处理程序
    if (!DynamicCommands.IsValid())
    {
        DynamicCommands = MakeShareable(new FDynamicHotkeyCommands());
        DynamicCommands->RegisterCommands();
    }
}

bool UMineprepSubsystem::RegisterHotkey(const FString& CommandName, const FString& DisplayName, const FString& Description,
                                      const FInputChord& Chord, const FString& BlueprintEventName)
{
    // 如果没有提供BlueprintEventName，使用CommandName作为默认值
    FString EventName = BlueprintEventName.IsEmpty() ? CommandName : BlueprintEventName;

    // 检查FSlateApplication是否已准备好
    if (!FSlateApplication::IsInitialized())
    {
        UE_LOG(LogTemp, Error, TEXT("无法注册快捷键，Slate应用程序尚未初始化"));
        return false;
    }

    // 确保命令列表已初始化
    if (!CommandList.IsValid())
    {
        UE_LOG(LogTemp, Error, TEXT("无法注册快捷键：命令列表未初始化"));
        return false;
    }
    
    // 确保动态命令已初始化
    if (!DynamicCommands.IsValid())
    {
        InitializeDynamicCommands();
    }

    // 检查键是否有效
    if (!Chord.Key.IsValid())
    {
        UE_LOG(LogTemp, Error, TEXT("注册快捷键失败：无效的按键"));
        return false;
    }

    // 添加命令到动态命令集
    TSharedPtr<FUICommandInfo> Command = DynamicCommands->AddCommand(CommandName, DisplayName, Description, Chord);
    
    if (!Command.IsValid())
    {
        UE_LOG(LogTemp, Error, TEXT("创建命令失败：%s"), *CommandName);
        return false;
    }
    
    // 存储命令到事件的映射
    CommandToEventMap.Add(CommandName, EventName);
    
    // 使用值传递而不是引用传递
    CommandList->MapAction(
        Command,
        FExecuteAction::CreateUObject(this, &UMineprepSubsystem::ExecuteBlueprintEvent, EventName)
    );

    // 设置活动快捷键并确保FInputBindingManager知道该变更
    Command->SetActiveChord(Chord, EMultipleKeyBindingIndex::Primary);
    
    // 通知InputBindingManager快捷键已更改，更新UI和配置文件
    FInputBindingManager::Get().NotifyActiveChordChanged(*Command, EMultipleKeyBindingIndex::Primary);
    FInputBindingManager::Get().SaveInputBindings();

    // 记录日志
    UE_LOG(LogTemp, Display, TEXT("成功注册快捷键：%s"), *CommandName);
    return true;
}


// 修改参数类型为值传递，而不是const引用
void UMineprepSubsystem::ExecuteBlueprintEvent(FString EventName)
{
    // 获取或创建快捷键对象
    UObject* CustomHotkeyWidget = GetHotkeyObject();
    
    if (CustomHotkeyWidget)
    {
        if (UFunction* Func = CustomHotkeyWidget->FindFunction(FName(*EventName)))
        {
            CustomHotkeyWidget->ProcessEvent(Func, nullptr);
        }
        else
        {
            UE_LOG(LogTemp, Error, TEXT("无法找到蓝图函数：%s"), *EventName);
        }
    }
    else
    {
        UE_LOG(LogTemp, Error, TEXT("无法获取快捷键对象，蓝图路径：%s"), *BlueprintPath);
    }
}

UObject* UMineprepSubsystem::GetHotkeyObject()
{
    // 如果已存在，直接返回
    if (HotkeyObject != nullptr)
    {
        return HotkeyObject;
    }
    
    // 检查编辑器是否已完全初始化
    if (!GEditor || !GEditor->IsInitialized())
    {
        UE_LOG(LogTemp, Warning, TEXT("无法创建快捷键对象：编辑器尚未完全初始化"));
        return nullptr;
    }
    
    // 加载蓝图类
    UClass* LoadedClass = LoadClass<UObject>(nullptr, *BlueprintPath);
    if (LoadedClass)
    {
        // 创建新对象
        HotkeyObject = NewObject<UObject>(GetTransientPackage(), LoadedClass);
        if (HotkeyObject)
        {
            // 确保对象不被垃圾回收
            HotkeyObject->AddToRoot();
            UE_LOG(LogTemp, Display, TEXT("成功创建快捷键对象: %s"), *BlueprintPath);
            return HotkeyObject;
        }
    }
    
    UE_LOG(LogTemp, Error, TEXT("无法加载蓝图类：%s"), *BlueprintPath);
    return nullptr;
}

void UMineprepSubsystem::LoadHotkeysFromFile()
{
    // 获取或创建快捷键对象
    UObject* HotkeyWidgetObj = GetHotkeyObject();

    // 查找LoadHotkeysFromFile函数
    UFunction* LoadFunc = HotkeyWidgetObj->FindFunction(FName("LoadHotkeysFromFile"));
    if (!LoadFunc)
    {
        UE_LOG(LogTemp, Error, TEXT("无法找到LoadHotkeysFromFile函数，请确保蓝图中实现了该函数"));
        return;
    }

    // 调用蓝图函数
    HotkeyWidgetObj->ProcessEvent(LoadFunc, nullptr);
    return;
}

void UMineprepSubsystem::UnloadHotkeysFromFile()
{
    // 获取或创建快捷键对象
    UObject* HotkeyWidgetObj = GetHotkeyObject();

    // 查找UnloadHotkeysFromFile函数
    UFunction* UnloadFunc = HotkeyWidgetObj->FindFunction(FName("UnloadHotkeysFromFile"));
    if (!UnloadFunc)
    {
        UE_LOG(LogTemp, Error, TEXT("无法找到UnloadHotkeysFromFile函数，请确保蓝图中实现了该函数"));
        return;
    }

    // 调用蓝图函数
    HotkeyWidgetObj->ProcessEvent(UnloadFunc, nullptr);
    return;
}


bool UMineprepSubsystem::UnregisterHotkey(const FString& CommandName)
{
    if (!CommandList.IsValid() || !DynamicCommands.IsValid())
    {
        UE_LOG(LogTemp, Warning, TEXT("注销快捷键失败：命令列表或动态命令未初始化"));
        return false;
    }
    
    // 检查映射是否存在
    if (!CommandToEventMap.Contains(CommandName))
    {
        UE_LOG(LogTemp, Warning, TEXT("注销快捷键失败：没有找到命令名 %s"), *CommandName);
        return false;
    }
    
    // 获取动态命令实例
    TSharedPtr<class FDynamicHotkeyCommands> DynamicCommandsPtr = StaticCastSharedPtr<FDynamicHotkeyCommands>(DynamicCommands);
    TSharedPtr<FUICommandInfo> Command = DynamicCommandsPtr->GetCommand(CommandName);
    
    if (!Command.IsValid())
    {
        UE_LOG(LogTemp, Warning, TEXT("注销快捷键失败：没有找到对应的命令实例 %s"), *CommandName);
        return false;
    }
    
    // 从映射中移除
    CommandToEventMap.Remove(CommandName);
    
    // 从命令列表中解绑该命令
    CommandList->UnmapAction(Command);
    
    // 重要：通知InputBindingManager该命令已被删除，以便它可以更新UI和用户配置
    // 这对于解决快捷键在编辑器设置中仍可见的问题很重要
    static FName BindingContextName = TEXT("Mineprep自定义快捷键");
    TSharedPtr<FBindingContext> BindingContext = FInputBindingManager::Get().GetContextByName(BindingContextName);
    if (BindingContext.IsValid())
    {
        // 从绑定管理器中删除命令
        FInputBindingManager::Get().RemoveInputCommand(BindingContext.ToSharedRef(), Command.ToSharedRef());
            
        // 移除用户定义的快捷键 - 对每个可能的绑定索引都尝试清除
        for (int32 ChordIdx = 0; ChordIdx < static_cast<int32>(EMultipleKeyBindingIndex::NumChords); ++ChordIdx)
        {
            FInputChord EmptyChord;
            // 保存空的快捷键以覆盖现有的
            Command->SetActiveChord(EmptyChord, static_cast<EMultipleKeyBindingIndex>(ChordIdx));
            // 通知变更以确保UI和配置更新
            FInputBindingManager::Get().NotifyActiveChordChanged(*Command, static_cast<EMultipleKeyBindingIndex>(ChordIdx));
        }
            
        // 强制保存更改
        FInputBindingManager::Get().SaveInputBindings();
    }
    
    UE_LOG(LogTemp, Display, TEXT("成功注销快捷键：%s"), *CommandName);
    return true;
}


UObject* UMineprepSubsystem::ReloadHotkeyObject()
{
    // 如果当前有对象，先移除
    if (HotkeyObject != nullptr)
    {
        HotkeyObject->RemoveFromRoot();
        HotkeyObject = nullptr;
    }
    
    // 检查编辑器是否已完全初始化
    if (!GEditor || !GEditor->IsInitialized())
    {
        UE_LOG(LogTemp, Warning, TEXT("无法重新加载快捷键对象：编辑器尚未完全初始化"));
        return nullptr;
    }
    
    // 加载蓝图类
    UClass* LoadedClass = LoadClass<UObject>(nullptr, *BlueprintPath);
    if (LoadedClass)
    {
        // 创建新对象
        HotkeyObject = NewObject<UObject>(GetTransientPackage(), LoadedClass);
        if (HotkeyObject)
        {
            // 确保对象不被垃圾回收
            HotkeyObject->AddToRoot();
            UE_LOG(LogTemp, Display, TEXT("成功重新加载快捷键对象"));
            return HotkeyObject;
        }
    }
    
    UE_LOG(LogTemp, Error, TEXT("无法重新加载快捷键对象：无法加载蓝图类"));
    return nullptr;
}
