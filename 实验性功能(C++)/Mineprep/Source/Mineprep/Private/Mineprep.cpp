// Copyright Epic Games, Inc. All Rights Reserved.

#include "Mineprep.h"
#include "AddKeyframes.h"
#include "CustomDetailsPanel.h"
#include "Editor.h"
#include "MineprepSubsystem.h"
#include "TickableEditorObject.h"

// 添加控制台变量
static float GMineprepTickInterval = 9999999.0f;
static FAutoConsoleVariableRef CVarMineprepTickInterval(
    TEXT("Mineprep.TickInterval"),
    GMineprepTickInterval,
    TEXT("设置Mineprep Editor Tick时间间隔(秒)。\n")
    TEXT("默认值: 9999999 (即不会触发Tick操作)"),
    ECVF_Default
);

#define LOCTEXT_NAMESPACE "FMineprepModule"

class FMineprepEditorTicker : public FTickableEditorObject
{
public:
    virtual void Tick(float DeltaTime) override
    {
        TimeSinceLastTick += DeltaTime;
        
        if (TimeSinceLastTick >= GMineprepTickInterval)
        {
            // 使用MineprepSubsystem获取快捷键对象
            if (GEditor)
            {
                UMineprepSubsystem* MineprepSubsystem = GEditor->GetEditorSubsystem<UMineprepSubsystem>();
                if (MineprepSubsystem)
                {
                    UObject* HotkeyObject = MineprepSubsystem->GetHotkeyObject();
                    if (HotkeyObject)
                    {
                        // 通过反射调用Run函数
                        if (UFunction* RunFunc = HotkeyObject->FindFunction(FName(TEXT("Run"))))
                        {
                            HotkeyObject->ProcessEvent(RunFunc, nullptr);
                        }
                        else
                        {
                            UE_LOG(LogTemp, Error, TEXT("无法找到Run函数"));
                        }
                    }
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
};

static TSharedPtr<FMineprepEditorTicker> MineprepEditorTicker;
///////////////////////////////////////////////////////////////////// 插件初始化

void FMineprepModule::StartupModule()
{
    // 创建编辑器Ticker
    MineprepEditorTicker = MakeShareable(new FMineprepEditorTicker());

    Mineprep::AddKeyframes::Register();
    Mineprep::CustomDetailsPanel::Register();
}

void FMineprepModule::ShutdownModule()
{
    Mineprep::AddKeyframes::Unregister();
    Mineprep::CustomDetailsPanel::Unregister();

    // 重置编辑器Ticker
    MineprepEditorTicker.Reset();
}

#undef LOCTEXT_NAMESPACE
    
IMPLEMENT_MODULE(FMineprepModule, Mineprep)