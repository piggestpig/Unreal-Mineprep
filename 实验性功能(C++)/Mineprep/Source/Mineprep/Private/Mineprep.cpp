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
        UI_COMMAND(Key0Command, "快捷键 Key0", "可在Plugins文件夹的“Mineprep自定义快捷键”蓝图中添加自定义操作", EUserInterfaceActionType::Button, FInputChord(EKeys::Zero, EModifierKey::Control | EModifierKey::Alt));
        UI_COMMAND(Key1Command, "快捷键 Key1", "【预设】切换新旧Gizmo小工具", EUserInterfaceActionType::Button, FInputChord(EKeys::One, EModifierKey::Control | EModifierKey::Alt));
        UI_COMMAND(Key2Command, "快捷键 Key2", "【预设】启用/禁用预览摄像机窗口", EUserInterfaceActionType::Button, FInputChord(EKeys::Two, EModifierKey::Control | EModifierKey::Alt));
        UI_COMMAND(Key3Command, "快捷键 Key3", "可在Plugins文件夹的“Mineprep自定义快捷键”蓝图中添加自定义操作", EUserInterfaceActionType::Button, FInputChord(EKeys::Three, EModifierKey::Control | EModifierKey::Alt));
        UI_COMMAND(Key4Command, "快捷键 Key4", "可在Plugins文件夹的“Mineprep自定义快捷键”蓝图中添加自定义操作", EUserInterfaceActionType::Button, FInputChord(EKeys::Four, EModifierKey::Control | EModifierKey::Alt));
        UI_COMMAND(Key5Command, "快捷键 Key5", "可在Plugins文件夹的“Mineprep自定义快捷键”蓝图中添加自定义操作", EUserInterfaceActionType::Button, FInputChord(EKeys::Five, EModifierKey::Control | EModifierKey::Alt));
        UI_COMMAND(Key6Command, "快捷键 Key6", "可在Plugins文件夹的“Mineprep自定义快捷键”蓝图中添加自定义操作", EUserInterfaceActionType::Button, FInputChord(EKeys::Six, EModifierKey::Control | EModifierKey::Alt));
        UI_COMMAND(Key7Command, "快捷键 Key7", "可在Plugins文件夹的“Mineprep自定义快捷键”蓝图中添加自定义操作", EUserInterfaceActionType::Button, FInputChord(EKeys::Seven, EModifierKey::Control | EModifierKey::Alt));
        UI_COMMAND(Key8Command, "快捷键 Key8", "可在Plugins文件夹的“Mineprep自定义快捷键”蓝图中添加自定义操作", EUserInterfaceActionType::Button, FInputChord(EKeys::Eight, EModifierKey::Control | EModifierKey::Alt));
        UI_COMMAND(Key9Command, "快捷键 Key9", "可在Plugins文件夹的“Mineprep自定义快捷键”蓝图中添加自定义操作", EUserInterfaceActionType::Button, FInputChord(EKeys::Nine, EModifierKey::Control | EModifierKey::Alt));
        UI_COMMAND(KeyViewCamCommand, "快捷键 KeyViewCam", "进入摄像机视图", EUserInterfaceActionType::Button, FInputChord(EKeys::NumPadZero));
        UI_COMMAND(KeyAlignCamCommand, "快捷键 KeyAlignCam", "对齐摄像机至视图", EUserInterfaceActionType::Button, FInputChord(EKeys::NumPadZero, EModifierKey::Control | EModifierKey::Alt));
        UI_COMMAND(KeySetParentCommand, "快捷键 KeySetParent", "绑定父级至最后一个视口选中项", EUserInterfaceActionType::Button, FInputChord(EKeys::P, EModifierKey::Control | EModifierKey::Alt));
        UI_COMMAND(KeyRenderImageCommand, "快捷键 KeyRenderImage", "渲染图片", EUserInterfaceActionType::Button, FInputChord(EKeys::F12));
        UI_COMMAND(KeyRenderVideoCommand, "快捷键 KeyRenderVideo", "渲染视频", EUserInterfaceActionType::Button, FInputChord(EKeys::F12, EModifierKey::Control));
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
    TSharedPtr<FUICommandInfo> KeyViewCamCommand;
    TSharedPtr<FUICommandInfo> KeyAlignCamCommand;
    TSharedPtr<FUICommandInfo> KeySetParentCommand;
    TSharedPtr<FUICommandInfo> KeyRenderImageCommand;
    TSharedPtr<FUICommandInfo> KeyRenderVideoCommand;
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
    else
    {
        // 处理材质参数
        TSharedPtr<IPropertyHandle> ParentHandle = PropertyHandle->GetParentHandle();
        if (!ParentHandle.IsValid())
        {
            return;
        }

        // 获取参数信息
        TSharedPtr<IPropertyHandle> ParameterInfoHandle = ParentHandle->GetChildHandle(GET_MEMBER_NAME_CHECKED(FScalarParameterValue, ParameterInfo));
        if (!ParameterInfoHandle.IsValid())
        {
            return;
        }

        FMaterialParameterInfo ParamInfo;
        void* ValuePtr = nullptr;
        if (ParameterInfoHandle->GetValueData(ValuePtr) == FPropertyAccess::Success)
        {
            ParamInfo = *static_cast<FMaterialParameterInfo*>(ValuePtr);
        }

        // 获取材质实例
        TArray<UObject*> OuterObjects;
        PropertyHandle->GetOuterObjects(OuterObjects);
        UMaterialInstance* MaterialInstance = nullptr;
        for (UObject* OuterObj : OuterObjects)
        {
            MaterialInstance = Cast<UMaterialInstance>(OuterObj);
            if (MaterialInstance)
            {
                break;
            }
        }

        if (MaterialInstance)
        {
            // 遍历 MeshComponent
            for (TObjectIterator<UMeshComponent> It; It; ++It)
            {
                UMeshComponent* MeshComp = *It;
                bool bFound = false;
                for (int32 i = 0; i < MeshComp->GetNumMaterials(); ++i)
                {
                    UMaterialInterface* Mat = MeshComp->GetMaterial(i);
                    if (Mat == MaterialInstance)
                    {
                        // 创建MaterialInfo
                        FComponentMaterialInfo MaterialInfo;
                        MaterialInfo.MaterialSlotIndex = i;
                        MaterialInfo.MaterialType = EComponentMaterialType::IndexedMaterial;
                        MaterialInfo.MaterialSlotName = MeshComp->GetMaterialSlotNames().IsValidIndex(i) ? 
                            MeshComp->GetMaterialSlotNames()[i] : NAME_None;

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

                                    Params.Component = MeshComp;
                                    Params.MaterialInfo = MaterialInfo;
                                    Params.ParamInfo = ParamInfo;
                                    Params.ParamType = ParamType;
                                    Params.ParamValue = ParamValueStr;
                                    Params.ParamName = DisplayName;
                                    Params.NiagaraVar = FNiagaraVariable(); // 空NiagaraVar

                                    CustomHotkeyWidget->ProcessEvent(KeyVarFunc, &Params);
                                }
                            }
                        }
                        bFound = true;
                        break;
                    }
                }
                if (bFound)
                {
                    break;
                }
            }
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
    static const FName ScalarParamName("ScalarParameterValues");
    static const FName VectorParamName("VectorParameterValues");
    static const FName TextureParamName("TextureParameterValues");

    TSharedPtr<IPropertyHandle> ParentHandle = PropertyHandle->GetParentHandle();
    FString PropertyPath = PropertyHandle->GetProperty()->GetPathName();

    if (PropertyPath.StartsWith(NiagaraParamPath) && PropertyHandle->GetProperty()->GetMetaData(FName("Category")).IsEmpty())
    {
        return true;
    }

    if (ParentHandle.IsValid())
    {
        if (FProperty* ParentProperty = ParentHandle->GetProperty())
        {
            FName PropName = ParentProperty->GetFName();
            if (PropName == ScalarParamName || PropName == VectorParamName || PropName == TextureParamName)
            {
                return true;
            }
        }
    }

    return false;
}

static void RegisterKeyframeExtensionHandler(const FOnGenerateGlobalRowExtensionArgs& Args, TArray<FPropertyRowExtensionButton>& OutExtensionButtons)
{
    TSharedPtr<IPropertyHandle> PropertyHandle = Args.PropertyHandle;
    if (!IsPropertyKeyframable(PropertyHandle))
    {
        return;
    }

    FPropertyRowExtensionButton& CreateKey = OutExtensionButtons.AddDefaulted_GetRef();
    CreateKey.Icon = TAttribute<FSlateIcon>::Create(TAttribute<FSlateIcon>::FGetter::CreateStatic(&GetKeyframeIcon, Args.OwnerTreeNode, PropertyHandle));
    CreateKey.Label = NSLOCTEXT("PropertyEditor", "CreateKey", "Create Key");
    CreateKey.ToolTip = NSLOCTEXT("PropertyEditor", "CreateKeyToolTip", "Add a keyframe for this property.");
    CreateKey.UIAction = FUIAction(
        FExecuteAction::CreateStatic(&OnAddKeyframeClicked, Args.OwnerTreeNode, PropertyHandle),
        FCanExecuteAction::CreateStatic(&IsKeyframeButtonEnabled, Args.OwnerTreeNode),
        FIsActionButtonVisible::CreateStatic(&IsKeyframeButtonVisible, Args.OwnerTreeNode, PropertyHandle)
    );
}

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
    CommandList->MapAction(FMineprepCommands::Get().KeyViewCamCommand, FExecuteAction::CreateRaw(this, &FMineprepModule::ExecuteBlueprintEvent, FName(TEXT("keyViewCam"))));
    CommandList->MapAction(FMineprepCommands::Get().KeyAlignCamCommand, FExecuteAction::CreateRaw(this, &FMineprepModule::ExecuteBlueprintEvent, FName(TEXT("keyAlignCam"))));
    CommandList->MapAction(FMineprepCommands::Get().KeySetParentCommand, FExecuteAction::CreateRaw(this, &FMineprepModule::ExecuteBlueprintEvent, FName(TEXT("keySetParent"))));
    CommandList->MapAction(FMineprepCommands::Get().KeyRenderImageCommand, FExecuteAction::CreateRaw(this, &FMineprepModule::ExecuteBlueprintEvent, FName(TEXT("keyRenderImage"))));
    CommandList->MapAction(FMineprepCommands::Get().KeyRenderVideoCommand, FExecuteAction::CreateRaw(this, &FMineprepModule::ExecuteBlueprintEvent, FName(TEXT("keyRenderVideo"))));

    // 创建编辑器Ticker
    MineprepEditorTicker = MakeShareable(new FMineprepEditorTicker());

    // 注册全局行扩展处理程序
    FPropertyEditorModule& PropertyEditorModule = FModuleManager::LoadModuleChecked<FPropertyEditorModule>("PropertyEditor");
    PropertyEditorModule.GetGlobalRowExtensionDelegate().AddStatic(&RegisterKeyframeExtensionHandler);
}

void FMineprepModule::ShutdownModule()
{
    // 注销命令
    FMineprepCommands::Unregister();

    // 重置编辑器Ticker
    MineprepEditorTicker.Reset();

    // 注销全局行扩展处理程序
    if (FModuleManager::Get().IsModuleLoaded("PropertyEditor"))
    {
        FPropertyEditorModule& PropertyEditorModule = FModuleManager::GetModuleChecked<FPropertyEditorModule>("PropertyEditor");
        PropertyEditorModule.GetGlobalRowExtensionDelegate().RemoveAll(this);
    }
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
void FMineprepModule::ExecuteKeyViewCamCommand() {ExecuteBlueprintEvent(TEXT("keyViewCam"));}
void FMineprepModule::ExecuteKeyAlignCamCommand() {ExecuteBlueprintEvent(TEXT("keyAlignCam"));}
void FMineprepModule::ExecuteKeySetParentCommand() {ExecuteBlueprintEvent(TEXT("keySetParent"));}
void FMineprepModule::ExecuteKeyRenderImageCommand() {ExecuteBlueprintEvent(TEXT("keyRenderImage"));}
void FMineprepModule::ExecuteKeyRenderVideoCommand() {ExecuteBlueprintEvent(TEXT("keyRenderVideo"));}

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