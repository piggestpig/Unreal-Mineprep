// Copyright Epic Games, Inc. All Rights Reserved.

#include "Mineprep.h"
#include "Framework/Commands/Commands.h"
#include "Framework/Commands/UICommandList.h"
#include "Framework/Commands/InputChord.h"
#include "LevelEditor.h"
#include "ToolMenus.h"

// 添加控制台变量
static float GMineprepTickInterval = 0.5f;
static FAutoConsoleVariableRef CVarMineprepTickInterval(
    TEXT("Mineprep.TickInterval"),
    GMineprepTickInterval,
    TEXT("设置Mineprep Editor Tick时间间隔(秒)。\n")
    TEXT("默认值: 0.5"),
    ECVF_Default
);

#define LOCTEXT_NAMESPACE "FMineprepModule"

class FMineprepCommands : public TCommands<FMineprepCommands>
{
public:
    FMineprepCommands()
        : TCommands<FMineprepCommands>(
            TEXT("Mineprep自定义快捷键"),
            LOCTEXT("Mineprep自定义快捷键", "Mineprep自定义快捷键"),
            NAME_None,
            FAppStyle::GetAppStyleSetName())
    {
    }

    virtual void RegisterCommands() override
    {
        UI_COMMAND(Key0Command, "快捷键 Key0", "可在Plugins文件夹的“Mineprep自定义快捷键”蓝图中修改操作", EUserInterfaceActionType::Button, FInputChord(EKeys::Zero, EModifierKey::Control | EModifierKey::Alt));
        UI_COMMAND(Key1Command, "快捷键 Key1", "可在Plugins文件夹的“Mineprep自定义快捷键”蓝图中修改操作", EUserInterfaceActionType::Button, FInputChord(EKeys::One, EModifierKey::Control | EModifierKey::Alt));
        UI_COMMAND(Key2Command, "快捷键 Key2", "可在Plugins文件夹的“Mineprep自定义快捷键”蓝图中修改操作", EUserInterfaceActionType::Button, FInputChord(EKeys::Two, EModifierKey::Control | EModifierKey::Alt));
        UI_COMMAND(Key3Command, "快捷键 Key3", "可在Plugins文件夹的“Mineprep自定义快捷键”蓝图中修改操作", EUserInterfaceActionType::Button, FInputChord(EKeys::Three, EModifierKey::Control | EModifierKey::Alt));
        UI_COMMAND(Key4Command, "快捷键 Key4", "可在Plugins文件夹的“Mineprep自定义快捷键”蓝图中修改操作", EUserInterfaceActionType::Button, FInputChord(EKeys::Four, EModifierKey::Control | EModifierKey::Alt));
        UI_COMMAND(Key5Command, "快捷键 Key5", "可在Plugins文件夹的“Mineprep自定义快捷键”蓝图中修改操作", EUserInterfaceActionType::Button, FInputChord(EKeys::Five, EModifierKey::Control | EModifierKey::Alt));
        UI_COMMAND(Key6Command, "快捷键 Key6", "可在Plugins文件夹的“Mineprep自定义快捷键”蓝图中修改操作", EUserInterfaceActionType::Button, FInputChord(EKeys::Six, EModifierKey::Control | EModifierKey::Alt));
        UI_COMMAND(Key7Command, "快捷键 Key7", "可在Plugins文件夹的“Mineprep自定义快捷键”蓝图中修改操作", EUserInterfaceActionType::Button, FInputChord(EKeys::Seven, EModifierKey::Control | EModifierKey::Alt));
        UI_COMMAND(Key8Command, "快捷键 Key8", "可在Plugins文件夹的“Mineprep自定义快捷键”蓝图中修改操作", EUserInterfaceActionType::Button, FInputChord(EKeys::Eight, EModifierKey::Control | EModifierKey::Alt));
        UI_COMMAND(Key9Command, "快捷键 Key9", "可在Plugins文件夹的“Mineprep自定义快捷键”蓝图中修改操作", EUserInterfaceActionType::Button, FInputChord(EKeys::Nine, EModifierKey::Control | EModifierKey::Alt));
    }

public:
    TSharedPtr<FUICommandInfo> Key0Command;
    TSharedPtr<FUICommandInfo> Key1Command;
    TSharedPtr<FUICommandInfo> Key2Command;
    TSharedPtr<FUICommandInfo> Key3Command;
    TSharedPtr<FUICommandInfo> Key4Command;
    TSharedPtr<FUICommandInfo> Key5Command;
    TSharedPtr<FUICommandInfo> Key6Command;
    TSharedPtr<FUICommandInfo> Key7Command;
    TSharedPtr<FUICommandInfo> Key8Command;
    TSharedPtr<FUICommandInfo> Key9Command;
};

class FMineprepEditorTicker : public FTickableEditorObject
{
public:
    virtual void Tick(float DeltaTime) override
    {
        TimeSinceLastTick += DeltaTime;
        
        if (TimeSinceLastTick >= GMineprepTickInterval)
        {
            // 延迟加载蓝图资产
            if (!CustomHotkeyWidget.IsValid())
            {
                FString BlueprintPath = TEXT("/Mineprep/Mineprep自定义快捷键.Mineprep自定义快捷键_C");
                UClass* LoadedClass = LoadClass<UObject>(nullptr, *BlueprintPath);
                if (LoadedClass)
                {
                    CustomHotkeyWidget = NewObject<UObject>(GetTransientPackage(), LoadedClass);
                }
                else
                {
                    UE_LOG(LogTemp, Error, TEXT("无法加载蓝图类: %s"), *BlueprintPath);
                    TimeSinceLastTick = 0.0f;
                    return;
                }
            }

            // 通过反射调用Run函数
            if (CustomHotkeyWidget.IsValid())
            {
                if (UFunction* RunFunc = CustomHotkeyWidget->FindFunction(FName(TEXT("Run"))))
                {
                    CustomHotkeyWidget->ProcessEvent(RunFunc, nullptr);
                }
                else
                {
                    UE_LOG(LogTemp, Error, TEXT("无法找到函数"));
                }
            }
            
            TimeSinceLastTick = 0.0f;
        }
    }

    virtual TStatId GetStatId() const override
    {
        RETURN_QUICK_DECLARE_CYCLE_STAT(FMineprepEditorTicker, STATGROUP_Tickables);
    }

    // 允许在编辑器下运行
    bool IsTickableInEditor() const
    {
        return true;
    }

private:
    float TimeSinceLastTick = 0.0f;
    TWeakObjectPtr<UObject> CustomHotkeyWidget;
};

static TSharedPtr<FMineprepEditorTicker> MineprepEditorTicker;

void FMineprepModule::StartupModule()
{
    // 注册命令
    FMineprepCommands::Register();

    // 绑定命令
    const FLevelEditorModule& LevelEditorModule = FModuleManager::GetModuleChecked<FLevelEditorModule>("LevelEditor");
    TSharedPtr<FUICommandList> CommandList = LevelEditorModule.GetGlobalLevelEditorActions();

    CommandList->MapAction(FMineprepCommands::Get().Key0Command, FExecuteAction::CreateRaw(this, &FMineprepModule::ExecuteKey0Command));
    CommandList->MapAction(FMineprepCommands::Get().Key1Command, FExecuteAction::CreateRaw(this, &FMineprepModule::ExecuteKey1Command));
    CommandList->MapAction(FMineprepCommands::Get().Key2Command, FExecuteAction::CreateRaw(this, &FMineprepModule::ExecuteKey2Command));
    CommandList->MapAction(FMineprepCommands::Get().Key3Command, FExecuteAction::CreateRaw(this, &FMineprepModule::ExecuteKey3Command));
    CommandList->MapAction(FMineprepCommands::Get().Key4Command, FExecuteAction::CreateRaw(this, &FMineprepModule::ExecuteKey4Command));
    CommandList->MapAction(FMineprepCommands::Get().Key5Command, FExecuteAction::CreateRaw(this, &FMineprepModule::ExecuteKey5Command));
    CommandList->MapAction(FMineprepCommands::Get().Key6Command, FExecuteAction::CreateRaw(this, &FMineprepModule::ExecuteKey6Command));
    CommandList->MapAction(FMineprepCommands::Get().Key7Command, FExecuteAction::CreateRaw(this, &FMineprepModule::ExecuteKey7Command));
    CommandList->MapAction(FMineprepCommands::Get().Key8Command, FExecuteAction::CreateRaw(this, &FMineprepModule::ExecuteKey8Command));
    CommandList->MapAction(FMineprepCommands::Get().Key9Command, FExecuteAction::CreateRaw(this, &FMineprepModule::ExecuteKey9Command));

    // 创建编辑器Ticker
    MineprepEditorTicker = MakeShareable(new FMineprepEditorTicker());
}

void FMineprepModule::ShutdownModule()
{
    // 注销命令
    FMineprepCommands::Unregister();

    // 重置编辑器Ticker
    MineprepEditorTicker.Reset();
}

void FMineprepModule::ExecuteKey0Command() {ExecuteBlueprintEvent(TEXT("key0"));}
void FMineprepModule::ExecuteKey1Command() {ExecuteBlueprintEvent(TEXT("key1"));}
void FMineprepModule::ExecuteKey2Command() {ExecuteBlueprintEvent(TEXT("key2"));}
void FMineprepModule::ExecuteKey3Command() {ExecuteBlueprintEvent(TEXT("key3"));}
void FMineprepModule::ExecuteKey4Command() {ExecuteBlueprintEvent(TEXT("key4"));}
void FMineprepModule::ExecuteKey5Command() {ExecuteBlueprintEvent(TEXT("key5"));}
void FMineprepModule::ExecuteKey6Command() {ExecuteBlueprintEvent(TEXT("key6"));}
void FMineprepModule::ExecuteKey7Command() {ExecuteBlueprintEvent(TEXT("key7"));}
void FMineprepModule::ExecuteKey8Command() {ExecuteBlueprintEvent(TEXT("key8"));}
void FMineprepModule::ExecuteKey9Command() {ExecuteBlueprintEvent(TEXT("key9"));}

void FMineprepModule::ExecuteBlueprintEvent(FName EventName)
{
    FString BlueprintPath = TEXT("/Mineprep/Mineprep自定义快捷键.Mineprep自定义快捷键_C");
    UClass* LoadedClass = LoadClass<UObject>(nullptr, *BlueprintPath);
    if (LoadedClass)
    {
        UObject* CustomHotkeyWidget = NewObject<UObject>(GetTransientPackage(), LoadedClass);
        if (CustomHotkeyWidget)
        {
            if (UFunction* Func = CustomHotkeyWidget->FindFunction(EventName))
            {
                CustomHotkeyWidget->ProcessEvent(Func, nullptr);
            }
            else
            {
                UE_LOG(LogTemp, Error, TEXT("无法找到 %s 函数"), *EventName.ToString());
            }
        }
    }
    else
    {
        UE_LOG(LogTemp, Error, TEXT("无法加载蓝图类: %s"), *BlueprintPath);
    }
}

#undef LOCTEXT_NAMESPACE
    
IMPLEMENT_MODULE(FMineprepModule, Mineprep)