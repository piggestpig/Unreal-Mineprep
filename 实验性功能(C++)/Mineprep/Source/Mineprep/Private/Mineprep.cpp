// Copyright Epic Games, Inc. All Rights Reserved.

#include "Mineprep.h"
#include "Selection.h"
#include "Framework/Commands/Commands.h"
#include "Framework/Commands/UICommandList.h"
#include "Framework/Commands/InputChord.h"
#include "LevelEditor.h"
#include "ToolMenus.h"
#include "PropertyEditorModule.h"
#include "IDetailTreeNode.h"
#include "IDetailPropertyRow.h"
#include "IPropertyRowGenerator.h"
#include "PropertyHandle.h"
#include "Framework/MultiBox/MultiBoxBuilder.h"
#include "Framework/MultiBox/MultiBoxDefs.h"
#include "Styling/SlateIconFinder.h"
#include "Tracks/MovieSceneMaterialTrack.h"
#include "NiagaraTypes.h"
#include "NiagaraComponent.h"
#include "NiagaraSystem.h"
#include "MovieScene/Parameters/MovieSceneNiagaraParameterTrack.h"
#include "MineprepSubsystem.h"
#include "Interfaces/IPluginManager.h"

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

static FSlateIcon GetKeyframeIcon(TWeakPtr<IDetailTreeNode> OwnerTreeNode, TSharedPtr<IPropertyHandle> PropertyHandle)
{
    // 返回关键帧图标
    return FSlateIcon(FAppStyle::GetAppStyleSetName(), "Sequencer.AddKey.Details");
}

static void OnAddKeyframeClicked(TWeakPtr<IDetailTreeNode> OwnerTreeNode, TSharedPtr<IPropertyHandle> PropertyHandle)
{
    if (!PropertyHandle.IsValid())
    {
        return;
    }

    // 获取参数类型和值
    FString ParamType;
    FProperty* Property = PropertyHandle->GetProperty();
    if (Property)
    {
        ParamType = Property->GetCPPType();
    }

    //获取显示名称
    FString DisplayName = PropertyHandle->GetPropertyDisplayName().ToString();
    
    FString ParamValueStr;
    PropertyHandle->GetValueAsFormattedString(ParamValueStr);

    // 获取参数路径，用于判断是否为Niagara参数
    FString PropertyPath = PropertyHandle->GetProperty()->GetPathName();
    static const FString NiagaraParamPath("/Engine/Transient.StructOnScope:");
    bool bIsNiagaraParam = PropertyPath.StartsWith(NiagaraParamPath);

    if (bIsNiagaraParam)
    {
        // 处理Niagara参数
        UNiagaraComponent* NiagaraComponent = nullptr;
        
        // 尝试获取当前选中的Actor和组件
        USelection* SelectedActors = GEditor->GetSelectedActors();
        for (FSelectionIterator Iter(*SelectedActors); Iter; ++Iter)
        {
            AActor* Actor = Cast<AActor>(*Iter);
            if (!Actor)
            {
                continue;
            }
    
            // 检查Actor的组件
            TArray<UActorComponent*> Components;
            Actor->GetComponents(UNiagaraComponent::StaticClass(), Components);
            
            if (Components.Num() > 0)
            {
                // 使用最后选中的Actor中的第一个NiagaraComponent
                NiagaraComponent = Cast<UNiagaraComponent>(Components[0]);
                
                // 如果有多个NiagaraComponent，尝试查找当前在细节面板中显示的那个
                if (Components.Num() > 1)
                {
                    USelection* SelectedComponents = GEditor->GetSelectedComponents();
                    for (FSelectionIterator CompIter(*SelectedComponents); CompIter; ++CompIter)
                    {
                        UNiagaraComponent* SelNiagaraComp = Cast<UNiagaraComponent>(*CompIter);
                        if (SelNiagaraComp && Components.Contains(SelNiagaraComp))
                        {
                            NiagaraComponent = SelNiagaraComp;
                            break;
                        }
                    }
                }
                
                break;
            }
        }
    
        if (NiagaraComponent)
        {
            // 从系统中获取正确的Niagara变量
            FNiagaraVariable NiagaraVar;
            UNiagaraSystem* System = NiagaraComponent->GetAsset();
            
            if (System)
            {
                TArray<FNiagaraVariable> ParameterVariables;
                System->GetExposedParameters().GetUserParameters(ParameterVariables);
                
                // 查找匹配的参数名
                for (const FNiagaraVariable& ParamVar : ParameterVariables)
                {
                    if (ParamVar.GetName().ToString() == DisplayName)
                    {
                        NiagaraVar = ParamVar;
                        break;
                    }
                }
                
                if (!NiagaraVar.IsValid())
                {
                    UE_LOG(LogTemp, Error, TEXT("未找到匹配的Niagara变量"));
                    return;
                }

                
                // 调用事件
                FString BlueprintPath = TEXT("/Mineprep/Mineprep自定义快捷键.Mineprep自定义快捷键_C");
                if (UClass* LoadedClass = LoadClass<UObject>(nullptr, *BlueprintPath))
                {
                    if (UObject* CustomHotkeyWidget = NewObject<UObject>(GetTransientPackage(), LoadedClass))
                    {
                        if (UFunction* KeyVarFunc = CustomHotkeyWidget->FindFunction(FName(TEXT("KeyVariable"))))
                        {
                            struct
                            {
                                USceneComponent* Component;
                                FComponentMaterialInfo MaterialInfo;
                                FMaterialParameterInfo ParamInfo;
                                FString ParamType;
                                FString ParamValue;
                                FString ParamName;
                                FNiagaraVariable NiagaraVar;
                            } Params;
    
                            Params.Component = NiagaraComponent;
                            Params.MaterialInfo = FComponentMaterialInfo(); // 空MaterialInfo
                            Params.ParamInfo = FMaterialParameterInfo();    // 空ParamInfo
                            Params.ParamType = ParamType;
                            Params.ParamValue = ParamValueStr;
                            Params.ParamName = DisplayName;
                            Params.NiagaraVar = NiagaraVar;
    
                            CustomHotkeyWidget->ProcessEvent(KeyVarFunc, &Params);
                        }
                    }
                }
            }
            else
            {
                UE_LOG(LogTemp, Error, TEXT("无法获取Niagara系统资产"));
            }
        }
        else
        {
            UE_LOG(LogTemp, Warning, TEXT("未找到选中的NiagaraComponent"));
        }
    }
}

static bool IsKeyframeButtonEnabled(TWeakPtr<IDetailTreeNode> OwnerTreeNode)
{
    // 返回关键帧按钮是否可用
    return true;
}

static bool IsKeyframeButtonVisible(TWeakPtr<IDetailTreeNode> OwnerTreeNode, TSharedPtr<IPropertyHandle> PropertyHandle)
{
    // 返回关键帧按钮是否可见
    return true;
}

static bool IsPropertyKeyframable(const TSharedPtr<IPropertyHandle>& PropertyHandle)
{
    if (!PropertyHandle.IsValid() || PropertyHandle->GetProperty() == nullptr)
    {
        return false;
    }

    static const FString NiagaraParamPath("/Engine/Transient.StructOnScope:");

    FString PropertyPath = PropertyHandle->GetProperty()->GetPathName();
    
    // 只检查 Niagara 参数
    if (PropertyPath.StartsWith(NiagaraParamPath) && PropertyHandle->GetProperty()->GetMetaData(FName("Category")).IsEmpty())
    {
        return true;
    }

    return false;
}

// 注册 Niagara 参数的关键帧扩展按钮处理器
// 注意：材质参数的关键帧按钮已迁移到 InlineMaterialInstance 插件
static void RegisterKeyframeExtensionHandler(const FOnGenerateGlobalRowExtensionArgs& Args, TArray<FPropertyRowExtensionButton>& OutExtensionButtons)
{
    TSharedPtr<IPropertyHandle> PropertyHandle = Args.PropertyHandle;
    if (!IsPropertyKeyframable(PropertyHandle))
    {
        return;
    }

    // 获取参数名
    FString ParamNameStr = PropertyHandle->GetPropertyDisplayName().ToString();
    
    FText ParamTooltip;
    
    // 从Mineprep子系统获取自定义快捷键对象
    UObject* HotkeyObject = GEditor->GetEditorSubsystem<UMineprepSubsystem>()->GetHotkeyObject();
    if (HotkeyObject)
    {
        // 通过调用GetMatParamTooltip函数获取工具提示
        if (UFunction* GetTooltipFunc = HotkeyObject->FindFunction(FName("GetMatParamTooltip")))
        {
            struct {
                FString ParamName;
                FString ReturnValue;
            } Params;
            
            Params.ParamName = ParamNameStr;
            Params.ReturnValue = "";
            
            HotkeyObject->ProcessEvent(GetTooltipFunc, &Params);
            
            if (!Params.ReturnValue.IsEmpty())
            {
                ParamTooltip = FText::FromString(Params.ReturnValue);
                PropertyHandle->SetToolTipText(ParamTooltip);
                ParamTooltip = FText::Format(FText::FromString("{0}{1}"), FText::FromString("\n\n"), FText::FromString(Params.ReturnValue));
            }
        }
    }

    FPropertyRowExtensionButton& CreateKey = OutExtensionButtons.AddDefaulted_GetRef();
    CreateKey.Icon = TAttribute<FSlateIcon>::Create(TAttribute<FSlateIcon>::FGetter::CreateStatic(&GetKeyframeIcon, Args.OwnerTreeNode, PropertyHandle));
    CreateKey.Label = NSLOCTEXT("PropertyEditor", "CreateKey", "Create Key");
    static FText baseTooltip = NSLOCTEXT("PropertyEditor", "CreateKeyToolTip", "Add a keyframe for this property.");
    CreateKey.ToolTip = FText::Format(FText::FromString("{0}{1}"), baseTooltip, ParamTooltip);
    CreateKey.UIAction = FUIAction(
        FExecuteAction::CreateStatic(&OnAddKeyframeClicked, Args.OwnerTreeNode, PropertyHandle),
        FCanExecuteAction::CreateStatic(&IsKeyframeButtonEnabled, Args.OwnerTreeNode),
        FIsActionButtonVisible::CreateStatic(&IsKeyframeButtonVisible, Args.OwnerTreeNode, PropertyHandle)
    );
}

void FMineprepModule::StartupModule()
{
    // 创建编辑器Ticker
    MineprepEditorTicker = MakeShareable(new FMineprepEditorTicker());

    // 注册全局行扩展处理程序
    FPropertyEditorModule& PropertyEditorModule = FModuleManager::LoadModuleChecked<FPropertyEditorModule>("PropertyEditor");
    PropertyEditorModule.GetGlobalRowExtensionDelegate().AddStatic(&RegisterKeyframeExtensionHandler);
    
    // 延迟绑定快捷键，直到引擎完全初始化  还有插件
    PostEngineInitDelegateHandle = FCoreDelegates::OnAllModuleLoadingPhasesComplete.AddLambda([]() 
    {
        if (!GEditor)
        {
            UE_LOG(LogTemp, Error, TEXT("无法绑定快捷键：GEditor不可用"));
            return;
        }

        // 获取Mineprep子系统
        UMineprepSubsystem* MineprepSubsystem = GEditor->GetEditorSubsystem<UMineprepSubsystem>();
        if (MineprepSubsystem)
        {
            // 先初始化快捷键对象，然后再从中加载快捷键
            UObject* HotkeyObject = MineprepSubsystem->GetHotkeyObject();
            if (!HotkeyObject)
            {
                UE_LOG(LogTemp, Error, TEXT("无法创建快捷键对象，无法加载快捷键"));
                return;
            }
            
            // 从蓝图对象加载快捷键
            MineprepSubsystem->LoadHotkeysFromFile();
            UE_LOG(LogTemp, Display, TEXT("Mineprep快捷键注册完成"));
        }
        else
        {
            UE_LOG(LogTemp, Error, TEXT("无法获取MineprepSubsystem，快捷键将不可用"));
        }
    });
}

void FMineprepModule::ShutdownModule()
{
    // 移除PostEngineInit委托
    if (PostEngineInitDelegateHandle.IsValid())
    {
        FCoreDelegates::OnPostEngineInit.Remove(PostEngineInitDelegateHandle);
        PostEngineInitDelegateHandle.Reset();
    }

    // 重置编辑器Ticker
    MineprepEditorTicker.Reset();

    // 注销全局行扩展处理程序
    if (FModuleManager::Get().IsModuleLoaded("PropertyEditor"))
    {
        FPropertyEditorModule& PropertyEditorModule = FModuleManager::GetModuleChecked<FPropertyEditorModule>("PropertyEditor");
        PropertyEditorModule.GetGlobalRowExtensionDelegate().RemoveAll(this);
    }
}

#undef LOCTEXT_NAMESPACE
    
IMPLEMENT_MODULE(FMineprepModule, Mineprep)