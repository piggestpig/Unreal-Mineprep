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
#include "Framework/Application/SlateApplication.h"
#include "Styling/SlateIconFinder.h"
#include "Subsystems/AssetEditorSubsystem.h"
#include "ILevelSequenceEditorToolkit.h"
#include "LevelSequence.h"
#include "LevelSequenceEditorBlueprintLibrary.h"
#include "ISequencer.h"
#include "Tracks/MovieSceneMaterialTrack.h"
#include "MovieScene.h"
#include "NiagaraTypes.h"
#include "NiagaraComponent.h"
#include "NiagaraSystem.h"
#include "MovieScene/Parameters/MovieSceneNiagaraBoolParameterTrack.h"
#include "MovieScene/Parameters/MovieSceneNiagaraColorParameterTrack.h"
#include "MovieScene/Parameters/MovieSceneNiagaraFloatParameterTrack.h"
#include "MovieScene/Parameters/MovieSceneNiagaraIntegerParameterTrack.h"
#include "MovieScene/Parameters/MovieSceneNiagaraParameterTrack.h"
#include "MovieScene/Parameters/MovieSceneNiagaraVectorParameterTrack.h"
#include "Sections/MovieSceneBoolSection.h"
#include "Sections/MovieSceneColorSection.h"
#include "Sections/MovieSceneFloatSection.h"
#include "Sections/MovieSceneIntegerSection.h"
#include "Sections/MovieSceneVectorSection.h"
#include "Channels/MovieSceneChannelProxy.h"
#include "Channels/MovieSceneFloatChannel.h"
#include "MineprepSubsystem.h"
#include "Interfaces/IPluginManager.h"
#include "Containers/Ticker.h"

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



///////////////////////////////////////////////////////////// Niagara本地化

// 待应用的 Niagara 参数本地化：原始参数名 -> 本地化 FText
static TMap<FString, FText> GPendingParamLocalizations;
static bool GLocTickerScheduled = false;

// 递归遍历控件树，对每个 STextBlock 尝试本地化，返回替换数量
// LocalizationMap: 预定义的映射（优先使用）
// 如果 LocalizationMap 中没有，则尝试从本地化表中查找
static int32 LocalizeTextBlocksInWidget(const TSharedRef<SWidget>& Widget, const TMap<FString, FText>& LocalizationMap)
{
    int32 Count = 0;
    if (Widget->GetType() == FName("STextBlock"))
    {
        TSharedPtr<STextBlock> TB = StaticCastSharedRef<STextBlock>(Widget);
        FString CurrentText = TB->GetText().ToString();

        // 优先使用预定义映射
        if (const FText* NewText = LocalizationMap.Find(CurrentText))
        {
            TB->SetText(*NewText);
            ++Count;
        }
        // 否则尝试从本地化表中查找（用于类别等未预定义的文本）
        else if (!CurrentText.IsEmpty())
        {
            FText LocalizedText;
            FString SourceStr = CurrentText;
            bool bFound = FText::FindTextInLiveTable_Advanced(
                FTextKey(TEXT("UObjectDisplayNames")),
                FTextKey(*CurrentText),
                LocalizedText,
                &SourceStr);

            if (bFound)
            {
                TB->SetText(LocalizedText);
                ++Count;
            }
        }
        return Count;
    }
    FChildren* Children = Widget->GetAllChildren();
    if (Children)
    {
        for (int32 i = 0; i < Children->Num(); ++i)
        {
            Count += LocalizeTextBlocksInWidget(Children->GetChildAt(i), LocalizationMap);
        }
    }
    return Count;
}



/////////////////////////////////////////////////////////////// Niagara关键帧

static const FName GNiagaraKeyedStyleName("Sequencer.KeyedStatus.Keyed");
static const FName GNiagaraUnkeyedStyleName("Sequencer.KeyedStatus.NotKeyed");

struct FResolvedNiagaraParameterContext
{
    UNiagaraComponent* Component = nullptr;
    FNiagaraVariable Parameter;
    FString ParamType;
    FString ParamName;
    FString ParamValue;
};

static bool CanKeyResolvedNiagaraParameter(const FResolvedNiagaraParameterContext& Context)
{
    return Context.Component != nullptr && Context.Parameter.IsValid();
}

static TSharedPtr<ISequencer> GetFocusedLevelSequencer()
{
    if (!GEditor)
    {
        return nullptr;
    }

    ULevelSequence* FocusedLevelSequence = ULevelSequenceEditorBlueprintLibrary::GetFocusedLevelSequence();
    if (!FocusedLevelSequence)
    {
        return nullptr;
    }

    UAssetEditorSubsystem* AssetEditorSubsystem = GEditor->GetEditorSubsystem<UAssetEditorSubsystem>();
    if (!AssetEditorSubsystem)
    {
        return nullptr;
    }

    IAssetEditorInstance* AssetEditor = AssetEditorSubsystem->FindEditorForAsset(FocusedLevelSequence, false);
    if (!AssetEditor)
    {
        return nullptr;
    }

    ILevelSequenceEditorToolkit* LevelSequenceEditor = static_cast<ILevelSequenceEditorToolkit*>(AssetEditor);
    return LevelSequenceEditor ? LevelSequenceEditor->GetSequencer() : nullptr;
}

template <typename ValueType>
static void CopyValueToByteArray(const ValueType& Value, TArray<uint8>& OutData)
{
    OutData.SetNumUninitialized(sizeof(ValueType));
    FMemory::Memcpy(OutData.GetData(), &Value, sizeof(ValueType));
}

static bool UpdateOrAddFloatKey(FMovieSceneFloatChannel& Channel, const FFrameNumber KeyTime, const float Value)
{
    const int32 ExistingKeyIndex = Channel.GetData().FindKey(KeyTime);
    if (ExistingKeyIndex == INDEX_NONE)
    {
        Channel.GetData().UpdateOrAddKey(KeyTime, FMovieSceneFloatValue(Value));
    }
    else
    {
        Channel.GetData().GetValues()[ExistingKeyIndex].Value = Value;
    }
    return true;
}

static bool CanCreateNiagaraParameterTrack(const FNiagaraVariable& Parameter)
{
    const UScriptStruct* TypeStruct = Parameter.GetType().GetScriptStruct();
    return TypeStruct == FNiagaraBool::StaticStruct()
        || TypeStruct == FNiagaraFloat::StaticStruct()
        || TypeStruct == FNiagaraInt32::StaticStruct()
        || TypeStruct == FNiagaraTypeDefinition::GetVec2Struct()
        || TypeStruct == FNiagaraTypeDefinition::GetVec3Struct()
        || TypeStruct == FNiagaraTypeDefinition::GetVec4Struct()
        || TypeStruct == FNiagaraTypeDefinition::GetPositionStruct()
        || TypeStruct == FNiagaraTypeDefinition::GetColorStruct();
}

static UMovieSceneNiagaraParameterTrack* CreateNiagaraParameterTrack(const FNiagaraVariable& Parameter)
{
    const UScriptStruct* TypeStruct = Parameter.GetType().GetScriptStruct();
    if (TypeStruct == FNiagaraBool::StaticStruct())
    {
        return NewObject<UMovieSceneNiagaraBoolParameterTrack>();
    }

    if (TypeStruct == FNiagaraFloat::StaticStruct())
    {
        return NewObject<UMovieSceneNiagaraFloatParameterTrack>();
    }

    if (TypeStruct == FNiagaraInt32::StaticStruct())
    {
        return NewObject<UMovieSceneNiagaraIntegerParameterTrack>();
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetVec2Struct())
    {
        UMovieSceneNiagaraVectorParameterTrack* VectorTrack = NewObject<UMovieSceneNiagaraVectorParameterTrack>();
        VectorTrack->SetChannelsUsed(2);
        return VectorTrack;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetVec3Struct() || TypeStruct == FNiagaraTypeDefinition::GetPositionStruct())
    {
        UMovieSceneNiagaraVectorParameterTrack* VectorTrack = NewObject<UMovieSceneNiagaraVectorParameterTrack>();
        VectorTrack->SetChannelsUsed(3);
        return VectorTrack;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetVec4Struct())
    {
        UMovieSceneNiagaraVectorParameterTrack* VectorTrack = NewObject<UMovieSceneNiagaraVectorParameterTrack>();
        VectorTrack->SetChannelsUsed(4);
        return VectorTrack;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetColorStruct())
    {
        return NewObject<UMovieSceneNiagaraColorParameterTrack>();
    }

    return nullptr;
}

template <typename ChannelType>
static bool ChannelHasAnyKeys(const ChannelType& Channel)
{
    return Channel.GetData().GetTimes().Num() > 0;
}

static bool ParseNiagaraParameterDefaultValueData(const FNiagaraVariable& Parameter, const FString& ValueString, TArray<uint8>& OutDefaultValueData)
{
    const UScriptStruct* TypeStruct = Parameter.GetType().GetScriptStruct();
    if (!TypeStruct)
    {
        return false;
    }

    if (TypeStruct == FNiagaraBool::StaticStruct())
    {
        const bool bValue = ValueString.ToBool() || ValueString == TEXT("1") || ValueString.Equals(TEXT("true"), ESearchCase::IgnoreCase);
        CopyValueToByteArray(FNiagaraBool(bValue), OutDefaultValueData);
        return true;
    }

    if (TypeStruct == FNiagaraFloat::StaticStruct())
    {
        CopyValueToByteArray(FCString::Atof(*ValueString), OutDefaultValueData);
        return true;
    }

    if (TypeStruct == FNiagaraInt32::StaticStruct())
    {
        CopyValueToByteArray(FCString::Atoi(*ValueString), OutDefaultValueData);
        return true;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetVec2Struct())
    {
        FVector2f Value(ForceInitToZero);
        if (TypeStruct->ImportText(*ValueString, &Value, nullptr, PPF_None, nullptr, TypeStruct->GetName()) == nullptr)
        {
            return false;
        }
        CopyValueToByteArray(Value, OutDefaultValueData);
        return true;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetVec3Struct())
    {
        FVector3f Value(ForceInitToZero);
        if (TypeStruct->ImportText(*ValueString, &Value, nullptr, PPF_None, nullptr, TypeStruct->GetName()) == nullptr)
        {
            return false;
        }
        CopyValueToByteArray(Value, OutDefaultValueData);
        return true;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetVec4Struct())
    {
        FVector4f Value(ForceInitToZero);
        if (TypeStruct->ImportText(*ValueString, &Value, nullptr, PPF_None, nullptr, TypeStruct->GetName()) == nullptr)
        {
            return false;
        }
        CopyValueToByteArray(Value, OutDefaultValueData);
        return true;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetPositionStruct())
    {
        FNiagaraPosition Value(ForceInitToZero);
        if (TypeStruct->ImportText(*ValueString, &Value, nullptr, PPF_None, nullptr, TypeStruct->GetName()) == nullptr)
        {
            return false;
        }
        CopyValueToByteArray(static_cast<FVector3f>(Value), OutDefaultValueData);
        return true;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetColorStruct())
    {
        FLinearColor Value(ForceInitToZero);
        if (TypeStruct->ImportText(*ValueString, &Value, nullptr, PPF_None, nullptr, TypeStruct->GetName()) == nullptr)
        {
            return false;
        }
        CopyValueToByteArray(Value, OutDefaultValueData);
        return true;
    }

    return false;
}

static bool AddKeyToNiagaraSection(UMovieSceneSection* Section, const FNiagaraVariable& Parameter, const FString& ValueString, const FFrameNumber KeyTime)
{
    if (!Section)
    {
        return false;
    }

    const UScriptStruct* TypeStruct = Parameter.GetType().GetScriptStruct();
    if (!TypeStruct)
    {
        return false;
    }

    if (TypeStruct == FNiagaraBool::StaticStruct())
    {
        UMovieSceneBoolSection* BoolSection = Cast<UMovieSceneBoolSection>(Section);
        if (!BoolSection)
        {
            return false;
        }

        const bool bValue = ValueString.ToBool() || ValueString == TEXT("1") || ValueString.Equals(TEXT("true"), ESearchCase::IgnoreCase);
        BoolSection->GetChannel().GetData().UpdateOrAddKey(KeyTime, bValue);
        BoolSection->ExpandToFrame(KeyTime);
        return true;
    }

    if (TypeStruct == FNiagaraFloat::StaticStruct())
    {
        UMovieSceneFloatSection* FloatSection = Cast<UMovieSceneFloatSection>(Section);
        if (!FloatSection)
        {
            return false;
        }

        UpdateOrAddFloatKey(FloatSection->GetChannel(), KeyTime, FCString::Atof(*ValueString));
        FloatSection->ExpandToFrame(KeyTime);
        return true;
    }

    if (TypeStruct == FNiagaraInt32::StaticStruct())
    {
        FMovieSceneIntegerChannel* IntegerChannel = Section->GetChannelProxy().GetChannel<FMovieSceneIntegerChannel>(0);
        if (!IntegerChannel)
        {
            return false;
        }

        IntegerChannel->GetData().UpdateOrAddKey(KeyTime, FCString::Atoi(*ValueString));
        Section->ExpandToFrame(KeyTime);
        return true;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetVec2Struct())
    {
        FVector2f Value(ForceInitToZero);
        if (TypeStruct->ImportText(*ValueString, &Value, nullptr, PPF_None, nullptr, TypeStruct->GetName()) == nullptr)
        {
            return false;
        }

        TArrayView<FMovieSceneFloatChannel*> Channels = Section->GetChannelProxy().GetChannels<FMovieSceneFloatChannel>();
        if (Channels.Num() < 2)
        {
            return false;
        }

        UpdateOrAddFloatKey(*Channels[0], KeyTime, Value.X);
        UpdateOrAddFloatKey(*Channels[1], KeyTime, Value.Y);
        Section->ExpandToFrame(KeyTime);
        return true;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetVec3Struct())
    {
        FVector3f Value(ForceInitToZero);
        if (TypeStruct->ImportText(*ValueString, &Value, nullptr, PPF_None, nullptr, TypeStruct->GetName()) == nullptr)
        {
            return false;
        }

        TArrayView<FMovieSceneFloatChannel*> Channels = Section->GetChannelProxy().GetChannels<FMovieSceneFloatChannel>();
        if (Channels.Num() < 3)
        {
            return false;
        }

        UpdateOrAddFloatKey(*Channels[0], KeyTime, Value.X);
        UpdateOrAddFloatKey(*Channels[1], KeyTime, Value.Y);
        UpdateOrAddFloatKey(*Channels[2], KeyTime, Value.Z);
        Section->ExpandToFrame(KeyTime);
        return true;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetPositionStruct())
    {
        FNiagaraPosition Value(ForceInitToZero);
        if (TypeStruct->ImportText(*ValueString, &Value, nullptr, PPF_None, nullptr, TypeStruct->GetName()) == nullptr)
        {
            return false;
        }

        TArrayView<FMovieSceneFloatChannel*> Channels = Section->GetChannelProxy().GetChannels<FMovieSceneFloatChannel>();
        if (Channels.Num() < 3)
        {
            return false;
        }

        UpdateOrAddFloatKey(*Channels[0], KeyTime, Value.X);
        UpdateOrAddFloatKey(*Channels[1], KeyTime, Value.Y);
        UpdateOrAddFloatKey(*Channels[2], KeyTime, Value.Z);
        Section->ExpandToFrame(KeyTime);
        return true;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetVec4Struct())
    {
        FVector4f Value(ForceInitToZero);
        if (TypeStruct->ImportText(*ValueString, &Value, nullptr, PPF_None, nullptr, TypeStruct->GetName()) == nullptr)
        {
            return false;
        }

        TArrayView<FMovieSceneFloatChannel*> Channels = Section->GetChannelProxy().GetChannels<FMovieSceneFloatChannel>();
        if (Channels.Num() < 4)
        {
            return false;
        }

        UpdateOrAddFloatKey(*Channels[0], KeyTime, Value.X);
        UpdateOrAddFloatKey(*Channels[1], KeyTime, Value.Y);
        UpdateOrAddFloatKey(*Channels[2], KeyTime, Value.Z);
        UpdateOrAddFloatKey(*Channels[3], KeyTime, Value.W);
        Section->ExpandToFrame(KeyTime);
        return true;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetColorStruct())
    {
        UMovieSceneColorSection* ColorSection = Cast<UMovieSceneColorSection>(Section);
        if (!ColorSection)
        {
            return false;
        }

        FLinearColor Value(ForceInitToZero);
        if (TypeStruct->ImportText(*ValueString, &Value, nullptr, PPF_None, nullptr, TypeStruct->GetName()) == nullptr)
        {
            return false;
        }

        UpdateOrAddFloatKey(ColorSection->GetRedChannel(), KeyTime, Value.R);
        UpdateOrAddFloatKey(ColorSection->GetGreenChannel(), KeyTime, Value.G);
        UpdateOrAddFloatKey(ColorSection->GetBlueChannel(), KeyTime, Value.B);
        UpdateOrAddFloatKey(ColorSection->GetAlphaChannel(), KeyTime, Value.A);
        ColorSection->ExpandToFrame(KeyTime);
        return true;
    }

    return false;
}

static UMovieSceneNiagaraParameterTrack* FindNiagaraParameterTrack(UMovieScene* MovieScene, const FGuid& ObjectBinding, const FNiagaraVariable& Parameter)
{
    if (!MovieScene)
    {
        return nullptr;
    }

    const FMovieSceneBinding* Binding = MovieScene->FindBinding(ObjectBinding);
    if (!Binding)
    {
        return nullptr;
    }

    for (UMovieSceneTrack* Track : Binding->GetTracks())
    {
        UMovieSceneNiagaraParameterTrack* ParameterTrack = Cast<UMovieSceneNiagaraParameterTrack>(Track);
        if (!ParameterTrack)
        {
            continue;
        }

        const FNiagaraVariable& TrackParameter = ParameterTrack->GetParameter();
        if (TrackParameter.GetName() == Parameter.GetName() && TrackParameter.GetType() == Parameter.GetType())
        {
            return ParameterTrack;
        }
    }

    return nullptr;
}

static UMovieSceneSection* FindNiagaraParameterSection(UMovieSceneNiagaraParameterTrack* ParameterTrack)
{
    return ParameterTrack && ParameterTrack->GetAllSections().Num() > 0
        ? ParameterTrack->GetAllSections()[0]
        : nullptr;
}

static bool HasAnyNiagaraParameterKeys(UMovieSceneSection* Section, const FNiagaraVariable& Parameter)
{
    if (!Section)
    {
        return false;
    }

    const UScriptStruct* TypeStruct = Parameter.GetType().GetScriptStruct();
    if (!TypeStruct)
    {
        return false;
    }

    if (TypeStruct == FNiagaraBool::StaticStruct())
    {
        if (const UMovieSceneBoolSection* BoolSection = Cast<UMovieSceneBoolSection>(Section))
        {
            return ChannelHasAnyKeys(BoolSection->GetChannel());
        }
        return false;
    }

    if (TypeStruct == FNiagaraFloat::StaticStruct())
    {
        if (const UMovieSceneFloatSection* FloatSection = Cast<UMovieSceneFloatSection>(Section))
        {
            return ChannelHasAnyKeys(FloatSection->GetChannel());
        }
        return false;
    }

    if (TypeStruct == FNiagaraInt32::StaticStruct())
    {
        if (const FMovieSceneIntegerChannel* IntegerChannel = Section->GetChannelProxy().GetChannel<FMovieSceneIntegerChannel>(0))
        {
            return ChannelHasAnyKeys(*IntegerChannel);
        }
        return false;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetColorStruct())
    {
        if (const UMovieSceneColorSection* ColorSection = Cast<UMovieSceneColorSection>(Section))
        {
            return ChannelHasAnyKeys(ColorSection->GetRedChannel())
                || ChannelHasAnyKeys(ColorSection->GetGreenChannel())
                || ChannelHasAnyKeys(ColorSection->GetBlueChannel())
                || ChannelHasAnyKeys(ColorSection->GetAlphaChannel());
        }
        return false;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetVec2Struct()
        || TypeStruct == FNiagaraTypeDefinition::GetVec3Struct()
        || TypeStruct == FNiagaraTypeDefinition::GetVec4Struct()
        || TypeStruct == FNiagaraTypeDefinition::GetPositionStruct())
    {
        TArrayView<FMovieSceneFloatChannel*> Channels = Section->GetChannelProxy().GetChannels<FMovieSceneFloatChannel>();
        for (FMovieSceneFloatChannel* Channel : Channels)
        {
            if (Channel && ChannelHasAnyKeys(*Channel))
            {
                return true;
            }
        }
        return false;
    }

    return false;
}

static bool TryGetNiagaraScalarValueString(TSharedPtr<IPropertyHandle> PropertyHandle, const FNiagaraVariable& Parameter, FString& OutValue)
{
    if (!PropertyHandle.IsValid())
    {
        return false;
    }

    const UScriptStruct* TypeStruct = Parameter.GetType().GetScriptStruct();
    if (!TypeStruct)
    {
        return false;
    }

    TArray<const void*> RawData;
    PropertyHandle->AccessRawData(RawData);

    const void* ValueData = nullptr;
    for (const void* RawValue : RawData)
    {
        if (RawValue)
        {
            ValueData = RawValue;
            break;
        }
    }

    if (!ValueData)
    {
        return false;
    }

    if (TypeStruct == FNiagaraFloat::StaticStruct())
    {
        const FNiagaraFloat* NiagaraFloat = reinterpret_cast<const FNiagaraFloat*>(ValueData);
        OutValue = FString::SanitizeFloat(NiagaraFloat->Value);
        return true;
    }

    if (TypeStruct == FNiagaraInt32::StaticStruct())
    {
        const FNiagaraInt32* NiagaraInt = reinterpret_cast<const FNiagaraInt32*>(ValueData);
        OutValue = FString::FromInt(NiagaraInt->Value);
        return true;
    }

    if (TypeStruct == FNiagaraBool::StaticStruct())
    {
        const FNiagaraBool* NiagaraBool = reinterpret_cast<const FNiagaraBool*>(ValueData);
        OutValue = NiagaraBool->GetValue() ? TEXT("true") : TEXT("false");
        return true;
    }

    return false;
}

static bool ResolveCurrentNiagaraParameterContext(TSharedPtr<IPropertyHandle> PropertyHandle, FResolvedNiagaraParameterContext& OutContext)
{
    if (!PropertyHandle.IsValid())
    {
        return false;
    }

    FProperty* Property = PropertyHandle->GetProperty();
    if (!Property)
    {
        return false;
    }

    static const FString NiagaraParamPath("/Engine/Transient.StructOnScope:");
    if (!Property->GetPathName().StartsWith(NiagaraParamPath))
    {
        return false;
    }

    OutContext.ParamName = PropertyHandle->GetPropertyDisplayName().ToString();
    PropertyHandle->GetValueAsFormattedString(OutContext.ParamValue);
    OutContext.ParamType = Property->GetCPPType();

    USelection* SelectedActors = GEditor ? GEditor->GetSelectedActors() : nullptr;
    if (!SelectedActors)
    {
        return true;
    }

    for (FSelectionIterator Iter(*SelectedActors); Iter; ++Iter)
    {
        AActor* Actor = Cast<AActor>(*Iter);
        if (!Actor)
        {
            continue;
        }

        TArray<UActorComponent*> Components;
        Actor->GetComponents(UNiagaraComponent::StaticClass(), Components);
        if (Components.Num() == 0)
        {
            continue;
        }

        OutContext.Component = Cast<UNiagaraComponent>(Components[0]);
        if (Components.Num() > 1)
        {
            if (USelection* SelectedComponents = GEditor->GetSelectedComponents())
            {
                for (FSelectionIterator CompIter(*SelectedComponents); CompIter; ++CompIter)
                {
                    UNiagaraComponent* SelectedNiagaraComp = Cast<UNiagaraComponent>(*CompIter);
                    if (SelectedNiagaraComp && Components.Contains(SelectedNiagaraComp))
                    {
                        OutContext.Component = SelectedNiagaraComp;
                        break;
                    }
                }
            }
        }
        break;
    }

    if (!OutContext.Component)
    {
        return true;
    }

    UNiagaraSystem* System = OutContext.Component->GetAsset();
    if (!System)
    {
        return true;
    }

    TArray<FNiagaraVariable> ParameterVariables;
    System->GetExposedParameters().GetUserParameters(ParameterVariables);
    for (const FNiagaraVariable& ParamVar : ParameterVariables)
    {
        if (ParamVar.GetName().ToString() == OutContext.ParamName)
        {
            OutContext.Parameter = ParamVar;
            OutContext.ParamType = ParamVar.GetType().GetName();

            FString ScalarValueString;
            if (TryGetNiagaraScalarValueString(PropertyHandle, ParamVar, ScalarValueString))
            {
                OutContext.ParamValue = ScalarValueString;
            }

            return true;
        }
    }

    return true;
}

static void NotifyNiagaraKeyVariable(UObject* TargetObject, UObject* ComponentObject, UMovieSceneTrack* Track, UMovieSceneSection* Section, const FString& ParamType, const FString& ParamName, const FString& ParamValue)
{
    if (!GEditor)
    {
        return;
    }

    UMineprepSubsystem* MineprepSubsystem = GEditor->GetEditorSubsystem<UMineprepSubsystem>();
    if (!MineprepSubsystem)
    {
        return;
    }

    UObject* HotkeyObject = MineprepSubsystem->GetHotkeyObject();
    if (!HotkeyObject)
    {
        return;
    }

    UFunction* KeyVarFunc = HotkeyObject->FindFunction(FName(TEXT("KeyVariable")));
    if (!KeyVarFunc)
    {
        return;
    }

    struct FKeyVariableParams
    {
        UObject* Target;
        UObject* Object;
        UMovieSceneTrack* Track;
        UMovieSceneSection* Section;
        FString ParamType;
        FString ParamName;
        FString ParamValue;
    } Params;

    Params.Target = TargetObject;
    Params.Object = ComponentObject;
    Params.Track = Track;
    Params.Section = Section;
    Params.ParamType = ParamType;
    Params.ParamName = ParamName;
    Params.ParamValue = ParamValue;

    HotkeyObject->ProcessEvent(KeyVarFunc, &Params);
}

static bool KeyFocusedNiagaraParameter(UNiagaraComponent* NiagaraComponent, const FNiagaraVariable& Parameter, const FString& ValueString, UMovieSceneNiagaraParameterTrack** OutTrack = nullptr, UMovieSceneSection** OutSection = nullptr)
{
    if (!NiagaraComponent)
    {
        UE_LOG(LogTemp, Warning, TEXT("KeyFocusedNiagaraParameter: NiagaraComponent 为空"));
        return false;
    }

    if (OutTrack)
    {
        *OutTrack = nullptr;
    }

    if (OutSection)
    {
        *OutSection = nullptr;
    }

    TSharedPtr<ISequencer> Sequencer = GetFocusedLevelSequencer();
    if (!Sequencer.IsValid())
    {
        UE_LOG(LogTemp, Warning, TEXT("KeyFocusedNiagaraParameter: 未找到当前激活的 Level Sequence Sequencer"));
        return false;
    }

    UMovieSceneSequence* FocusedSequence = Sequencer->GetFocusedMovieSceneSequence();
    UMovieScene* MovieScene = FocusedSequence ? FocusedSequence->GetMovieScene() : nullptr;
    if (!MovieScene || MovieScene->IsReadOnly())
    {
        UE_LOG(LogTemp, Warning, TEXT("KeyFocusedNiagaraParameter: 当前序列不可编辑"));
        return false;
    }

    TArray<uint8> DefaultValueData;
    if (!ParseNiagaraParameterDefaultValueData(Parameter, ValueString, DefaultValueData))
    {
        UE_LOG(LogTemp, Warning, TEXT("KeyFocusedNiagaraParameter: 不支持的 Niagara 参数类型 '%s'，或值解析失败: %s"), *Parameter.GetType().GetName(), *ValueString);
        return false;
    }

    if (!CanCreateNiagaraParameterTrack(Parameter))
    {
        UE_LOG(LogTemp, Warning, TEXT("KeyFocusedNiagaraParameter: 不支持参数类型 '%s' 的轨道创建"), *Parameter.GetType().GetName());
        return false;
    }

    const FScopedTransaction Transaction(LOCTEXT("MineprepKeyNiagaraParameter", "Key Niagara User Parameter"));
    MovieScene->Modify();

    const FGuid ObjectBinding = Sequencer->GetHandleToObject(NiagaraComponent, true);
    if (!ObjectBinding.IsValid())
    {
        UE_LOG(LogTemp, Warning, TEXT("KeyFocusedNiagaraParameter: 无法为 NiagaraComponent 创建或获取 Sequencer 绑定"));
        return false;
    }

    bool bCreatedTrackOrSection = false;
    UMovieSceneNiagaraParameterTrack* ParameterTrack = FindNiagaraParameterTrack(MovieScene, ObjectBinding, Parameter);
    if (!ParameterTrack)
    {
        ParameterTrack = CreateNiagaraParameterTrack(Parameter);
        if (!ParameterTrack)
        {
            UE_LOG(LogTemp, Warning, TEXT("KeyFocusedNiagaraParameter: 创建 Niagara 参数轨失败"));
            return false;
        }
        MovieScene->AddGivenTrack(ParameterTrack, ObjectBinding);
        ParameterTrack->Modify();
        ParameterTrack->SetParameter(Parameter);
        ParameterTrack->SetDisplayName(FText::FromName(Parameter.GetName()));
        bCreatedTrackOrSection = true;
    }

    UMovieSceneSection* ParameterSection = FindNiagaraParameterSection(ParameterTrack);
    if (!ParameterSection)
    {
        ParameterSection = ParameterTrack->CreateNewSection();
        ParameterSection->Modify();
        ParameterTrack->SetSectionChannelDefaults(ParameterSection, DefaultValueData);
        ParameterSection->SetRange(TRange<FFrameNumber>::All());
        ParameterTrack->AddSection(*ParameterSection);
        bCreatedTrackOrSection = true;
    }

    const FFrameNumber KeyTime = Sequencer->GetLocalTime().Time.FrameNumber;
    ParameterTrack->Modify();
    ParameterSection->Modify();

    if (!AddKeyToNiagaraSection(ParameterSection, Parameter, ValueString, KeyTime))
    {
        UE_LOG(LogTemp, Warning, TEXT("KeyFocusedNiagaraParameter: 向轨道写入关键帧失败，参数: %s"), *Parameter.GetName().ToString());
        return false;
    }

    Sequencer->NotifyMovieSceneDataChanged(
        bCreatedTrackOrSection
            ? EMovieSceneDataChangeType::MovieSceneStructureItemAdded
            : EMovieSceneDataChangeType::TrackValueChanged);

    if (OutTrack)
    {
        *OutTrack = ParameterTrack;
    }

    if (OutSection)
    {
        *OutSection = ParameterSection;
    }

    return true;
}


static FSlateIcon GetKeyframeIcon(TWeakPtr<IDetailTreeNode> OwnerTreeNode, TSharedPtr<IPropertyHandle> PropertyHandle)
{
    FResolvedNiagaraParameterContext Context;
    TSharedPtr<ISequencer> Sequencer = GetFocusedLevelSequencer();
    bool bIsKeyed = false;

    if (Sequencer.IsValid() && ResolveCurrentNiagaraParameterContext(PropertyHandle, Context) && CanKeyResolvedNiagaraParameter(Context))
    {
        UMovieSceneSequence* FocusedSequence = Sequencer->GetFocusedMovieSceneSequence();
        UMovieScene* MovieScene = FocusedSequence ? FocusedSequence->GetMovieScene() : nullptr;
        if (MovieScene)
        {
            const FGuid ObjectBinding = Sequencer->GetHandleToObject(Context.Component, false);
            if (ObjectBinding.IsValid())
            {
                if (UMovieSceneNiagaraParameterTrack* ParameterTrack = FindNiagaraParameterTrack(MovieScene, ObjectBinding, Context.Parameter))
                {
                    if (UMovieSceneSection* ParameterSection = FindNiagaraParameterSection(ParameterTrack))
                    {
                        bIsKeyed = HasAnyNiagaraParameterKeys(ParameterSection, Context.Parameter);
                    }
                }
            }
        }
    }

    return FSlateIcon(FAppStyle::GetAppStyleSetName(), bIsKeyed ? GNiagaraKeyedStyleName : GNiagaraUnkeyedStyleName);
}

static void OnAddKeyframeClicked(TWeakPtr<IDetailTreeNode> OwnerTreeNode, TSharedPtr<IPropertyHandle> PropertyHandle)
{
    FResolvedNiagaraParameterContext Context;
    if (!ResolveCurrentNiagaraParameterContext(PropertyHandle, Context))
    {
        return;
    }

    UMovieSceneNiagaraParameterTrack* ParameterTrack = nullptr;
    UMovieSceneSection* ParameterSection = nullptr;
    if (CanKeyResolvedNiagaraParameter(Context)
        && !KeyFocusedNiagaraParameter(Context.Component, Context.Parameter, Context.ParamValue, &ParameterTrack, &ParameterSection))
    {
        UE_LOG(LogTemp, Warning, TEXT("为 Niagara 参数添加关键帧失败: %s"), *Context.ParamName);
    }

    NotifyNiagaraKeyVariable(Context.Component ? Context.Component->GetAsset() : nullptr, Context.Component, ParameterTrack, ParameterSection, Context.ParamType, Context.ParamName, Context.ParamValue);
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

    // 尝试本地化参数显示名称
    {
        FText LocalizedParamName;
        FString SourceStr = ParamNameStr;
        bool bLocFound = FText::FindTextInLiveTable_Advanced(
            FTextKey(TEXT("UObjectDisplayNames")),
            FTextKey(*ParamNameStr),
            LocalizedParamName,
            &SourceStr);

        if (bLocFound)
        {
            // 记录待本地化映射
            GPendingParamLocalizations.Add(ParamNameStr, LocalizedParamName);
        }
    }

    // 首次记录时注册一个一次性延迟帧，参数面板构建完毕后统一 SetText
    // 注意：类别名称的本地化现在由 LocalizeTextBlocksInWidget 自动处理
    if (GPendingParamLocalizations.Num() > 0 && !GLocTickerScheduled)
    {
        GLocTickerScheduled = true;
        FTSTicker::GetCoreTicker().AddTicker(
            FTickerDelegate::CreateLambda([](float) -> bool
            {
                if (FSlateApplication::IsInitialized() && GPendingParamLocalizations.Num() > 0)
                {
                    const TArray<TSharedRef<SWindow>>& TopWindows =
                        FSlateApplication::Get().GetInteractiveTopLevelWindows();
                    int32 TotalSet = 0;
                    for (const TSharedRef<SWindow>& Window : TopWindows)
                    {
                        TotalSet += LocalizeTextBlocksInWidget(Window, GPendingParamLocalizations);
                    }
                    // UE_LOG(LogTemp, Verbose, TEXT("Niagara参数本地化：共设置 %d 个标签"), TotalSet);
                    GPendingParamLocalizations.Empty();
                }
                GLocTickerScheduled = false;
                return false; // 只执行一次，自动销毁
            }),
            0.0f // 下一帧执行
        );
    }

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



///////////////////////////////////////////////////////////////////// 插件初始化

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